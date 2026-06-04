#!/usr/bin/env python3
"""
AgentReady concurrent assessment runner.

Modes:
  --mode demo   Read repos from runner/repos.yaml
  --mode prod   Discover all public repos in the org via GitHub API
  --from-file   Read repo names from a file (one per line, e.g. failed-repos.txt)
"""
import argparse
import os
import sys
from pathlib import Path

SCRIPT_DIR = Path(__file__).parent
REPO_ROOT = SCRIPT_DIR.parent


def parse_args():
    parser = argparse.ArgumentParser(description="Run agentready assessments concurrently")
    mode_group = parser.add_mutually_exclusive_group(required=True)
    mode_group.add_argument(
        "--mode", choices=["demo", "prod"],
        help="demo: use repos.yaml; prod: discover all org repos via GitHub API"
    )
    mode_group.add_argument(
        "--from-file", metavar="PATH",
        help="Assess only repos listed in this file (one repo name per line)"
    )
    parser.add_argument(
        "--workers", type=int, default=5,
        help="Max concurrent assessments (default: 5)"
    )
    parser.add_argument(
        "--retries", type=int, default=1,
        help="Retry attempts per failed repo (default: 1)"
    )
    parser.add_argument(
        "--output-dir", type=Path, default=REPO_ROOT / "submissions",
        help="Path to submissions directory (default: ../submissions)"
    )
    parser.add_argument(
        "--org", default=None,
        help="GitHub org to assess (overrides repos.yaml org in prod mode)"
    )
    return parser.parse_args()


def main():
    args = parse_args()

    sys.path.insert(0, str(SCRIPT_DIR))
    from runner_lib import (
        load_demo_repos,
        discover_prod_repos,
        load_repos_from_file,
        run_batch,
        commit_results,
        write_failed_repos,
    )

    # Discover repos
    if args.from_file:
        org, repos = load_repos_from_file(Path(args.from_file))
    elif args.mode == "demo":
        org, repos = load_demo_repos(SCRIPT_DIR / "repos.yaml")
    else:  # prod
        org = args.org or load_demo_repos(SCRIPT_DIR / "repos.yaml")[0]
        repos = discover_prod_repos(org)

    if not repos:
        print("No repos to assess. Exiting.")
        sys.exit(0)

    print(f"Assessing {len(repos)} repos in {org} with {args.workers} workers...")

    # Run batch with retries
    succeeded, failed = run_batch(
        org=org,
        repos=repos,
        output_dir=args.output_dir,
        workers=args.workers,
        retries=args.retries,
    )

    # Commit all results
    if succeeded:
        commit_results(REPO_ROOT, org, succeeded)

    # Write failures
    failed_file = SCRIPT_DIR / "failed-repos.txt"
    if failed:
        write_failed_repos(failed_file, org, failed)
        print(f"\n{len(failed)} repos failed. Written to {failed_file}")
    elif failed_file.exists():
        failed_file.unlink()  # Clean up stale failures file

    print(f"\nDone: {len(succeeded)} succeeded, {len(failed)} failed")
    sys.exit(1 if failed else 0)


if __name__ == "__main__":
    main()
