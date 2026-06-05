"""Tests for runner_lib.py"""
import json
import os
import subprocess
import textwrap
from pathlib import Path
from unittest.mock import MagicMock, call, patch

import pytest

# Ensure runner/ is on the path
import sys
sys.path.insert(0, str(Path(__file__).parent.parent))

from runner_lib import (
    commit_results,
    discover_org_repos,
    load_repos_from_file,
    run_batch,
    write_failed_repos,
)


# ---------------------------------------------------------------------------
# Fixtures
# ---------------------------------------------------------------------------

@pytest.fixture
def repos_yaml(tmp_path):
    f = tmp_path / "repos.yaml"
    f.write_text(textwrap.dedent("""\
        org: my-org
        repos:
          - repo-a
          - repo-b
          - repo-c
    """))
    return f


@pytest.fixture
def failed_repos_yaml(tmp_path):
    f = tmp_path / "failed-repos.yaml"
    f.write_text(textwrap.dedent("""\
        # Failed repos from 2026-06-05
        org: my-org
        repos:
          - repo-x
          - repo-y
    """))
    return f


# ---------------------------------------------------------------------------
# load_repos_from_file (YAML format — same for repos.yaml and failed-repos.yaml)
# ---------------------------------------------------------------------------

class TestLoadReposFromFile:
    def test_returns_org_and_repos(self, repos_yaml):
        org, repos = load_repos_from_file(repos_yaml)
        assert org == "my-org"
        assert repos == ["repo-a", "repo-b", "repo-c"]

    def test_parses_failed_repos_yaml(self, failed_repos_yaml):
        org, repos = load_repos_from_file(failed_repos_yaml)
        assert org == "my-org"
        assert repos == ["repo-x", "repo-y"]

    def test_missing_file_raises(self, tmp_path):
        with pytest.raises(FileNotFoundError):
            load_repos_from_file(tmp_path / "nonexistent.yaml")


# ---------------------------------------------------------------------------
# discover_org_repos
# ---------------------------------------------------------------------------

class TestDiscoverOrgRepos:
    def test_paginates_until_empty(self):
        page1 = [{"name": "repo-a"}, {"name": "repo-b"}]
        page2 = []

        mock_resp1 = MagicMock()
        mock_resp1.json.return_value = page1
        mock_resp2 = MagicMock()
        mock_resp2.json.return_value = page2

        with patch("runner_lib.requests.get", side_effect=[mock_resp1, mock_resp2]) as mock_get:
            repos = discover_org_repos("my-org")

        assert repos == ["repo-a", "repo-b"]
        assert mock_get.call_count == 2

    def test_uses_gh_token_from_env(self):
        mock_resp = MagicMock()
        mock_resp.json.return_value = []

        with patch.dict(os.environ, {"GH_TOKEN": "test-token"}):
            with patch("runner_lib.requests.get", return_value=mock_resp) as mock_get:
                discover_org_repos("my-org")

        _, kwargs = mock_get.call_args
        assert kwargs["headers"]["Authorization"] == "Bearer test-token"

    def test_raises_on_api_error(self):
        mock_resp = MagicMock()
        mock_resp.raise_for_status.side_effect = Exception("403 Forbidden")

        with patch("runner_lib.requests.get", return_value=mock_resp):
            with pytest.raises(Exception, match="403"):
                discover_org_repos("my-org")


# ---------------------------------------------------------------------------
# write_failed_repos
# ---------------------------------------------------------------------------

class TestWriteFailedRepos:
    def test_writes_yaml_with_org_and_repos(self, tmp_path):
        import yaml as _yaml
        out = tmp_path / "failed-repos.yaml"
        write_failed_repos(out, "my-org", ["repo-x", "repo-y"])
        content = out.read_text()
        # Comment header present
        assert content.startswith("#")
        # Parseable as YAML with correct structure
        data = _yaml.safe_load(content)
        assert data["org"] == "my-org"
        assert data["repos"] == ["repo-x", "repo-y"]

    def test_output_can_be_reloaded_by_runner(self, tmp_path):
        out = tmp_path / "failed-repos.yaml"
        write_failed_repos(out, "my-org", ["repo-x"])
        org, repos = load_repos_from_file(out)
        assert org == "my-org"
        assert repos == ["repo-x"]


# ---------------------------------------------------------------------------
# run_batch
# ---------------------------------------------------------------------------

class TestRunBatch:
    def test_returns_succeeded_and_failed(self, tmp_path):
        def fake_assess(org, repo, output_dir):
            if repo == "bad-repo":
                raise RuntimeError("clone failed")
            return str(output_dir / org / repo / "assessment.json")

        with patch("runner_lib.assess_repo", side_effect=fake_assess):
            succeeded, failed = run_batch(
                org="my-org",
                repos=["repo-a", "bad-repo"],
                output_dir=tmp_path,
                workers=2,
                retries=0,
            )

        assert "repo-a" in succeeded
        assert "bad-repo" in failed

    def test_retries_failed_repos(self, tmp_path):
        call_count = {"bad": 0}

        def fake_assess(org, repo, output_dir):
            if repo == "flaky":
                call_count["bad"] += 1
                if call_count["bad"] < 2:
                    raise RuntimeError("transient error")
            return "ok"

        with patch("runner_lib.assess_repo", side_effect=fake_assess):
            succeeded, failed = run_batch(
                org="my-org",
                repos=["flaky"],
                output_dir=tmp_path,
                workers=1,
                retries=1,
            )

        assert "flaky" in succeeded
        assert failed == []
        assert call_count["bad"] == 2


# ---------------------------------------------------------------------------
# commit_results
# ---------------------------------------------------------------------------

class TestCommitResults:
    def test_runs_git_add_commit_push(self, tmp_path):
        with patch("runner_lib.subprocess.run") as mock_run:
            mock_run.return_value = MagicMock(returncode=0)
            commit_results(tmp_path, "my-org", ["repo-a", "repo-b"])

        calls = [str(c) for c in mock_run.call_args_list]
        assert any("git" in c and "add" in c for c in calls)
        assert any("git" in c and "commit" in c for c in calls)
        assert any("git" in c and "push" in c for c in calls)

    def test_commit_message_includes_org_and_repos(self, tmp_path):
        with patch("runner_lib.subprocess.run") as mock_run:
            mock_run.return_value = MagicMock(returncode=0)
            commit_results(tmp_path, "my-org", ["repo-a"])

        commit_call = next(
            c for c in mock_run.call_args_list
            if "'git', 'commit'" in str(c)
        )
        msg = str(commit_call)
        assert "my-org" in msg
