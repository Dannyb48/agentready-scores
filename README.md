# agentready-scores

A **GitHub template repository** for collecting [AgentReady](https://github.com/ambient-code/agentready) AI readiness scores across a GitHub organization and ingesting them into [DevLake](https://github.com/konflux-ci/devlake) for visualization.

## Using this template

1. Click **Use this template** → **Create a new repository**
2. Edit `runner/repos.yaml` — set your `org` and list repos for demo mode
3. Add repository secrets:
   - `GHCR_TOKEN` — token to pull the `ghcr.io/ambient-code/agentready` image
   - `GH_TOKEN` — GitHub token with `repo` read + `contents: write` access
4. Run the **Assess repos (manual)** workflow to generate your first assessments
5. Point your DevLake AgentReady connection at this repo (`submissions/` path)

## Structure

```
submissions/
  {org}/
    {repo}/
      assessment-YYYYMMDD-HHMMSS.json  ← actual assessment data
      assessment-latest.json           ← symlink to latest assessment
runner/
  assess.py        ← concurrent assessment runner (local + CI)
  repos.yaml       ← org + curated repo list for demo/manual runs
  requirements.txt
.github/workflows/
  assess-manual.yml    ← manual trigger with configurable inputs
  assess-scheduled.yml ← weekly cron for all public repos in org
```

## Running Locally

```bash
# Set up environment
cd agentready-scores
pip install -r runner/requirements.txt

export GH_TOKEN=<your-github-token>
export GHCR_TOKEN=<your-ghcr-token>  # to pull agentready image

# Demo mode — assess repos listed in repos.yaml
python runner/assess.py --mode demo --output-dir submissions --workers 3

# Prod mode — discover and assess ALL public repos in the org
python runner/assess.py --mode prod --output-dir submissions --workers 5

# Re-run only repos that failed
python runner/assess.py --from-file runner/failed-repos.txt
```

## Re-running failures

After any run, failed repos are written to `runner/failed-repos.txt`. Re-run them with:

```bash
python runner/assess.py --from-file runner/failed-repos.txt
```

## DevLake Integration

Configure an **AgentReady connection** in DevLake pointing to this repo:

| Field | Value |
|-------|-------|
| GitHub Connection | your existing GitHub connection |
| Submissions Repo | `your-org/agentready-scores` |
| Submissions Path | `submissions` |
| Branch | `main` |

DevLake auto-discovers all `{org}/{repo}` scopes from the submissions tree.

---

See `docs/superpowers/specs/` for the full design specification.
