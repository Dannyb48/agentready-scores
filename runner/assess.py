#!/usr/bin/env python3
"""
AgentReady concurrent assessment runner.

Usage:
  --org <org>           Discover and assess ALL public repos in the org via GitHub API
  --from-file FILE      Assess repos listed in a YAML file (org + repos keys)
                        Works with repos.yaml for curated runs, or failed-repos.yaml
                        to re-run failures from a previous run.
"""
import argparse
import os
import sys
from pathlib import Path

SCRIPT_DIR = Path(__file__).parent
REPO_ROOT = SCRIPT_DIR.parent


def parse_args():
    parser = argparse.ArgumentParser(
        description="Run agentready assessments concurrently",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog=__doc__,
    )

    source_group = parser.add_mutually_exclusive_group(required=True)
    source_group.add_argument(
        "--org",
        metavar="ORG",
        help="GitHub org — discovers all public repos automatically",
    )
    source_group.add_argument(
        "--from-file",
        metavar="PATH",
        help="YAML file with 'org' and 'repos' keys — use repos.yaml for curated "
             "runs or failed-repos.yaml to retry failures",
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
        help="Path to submissions directory (default: submissions/)"
    )
    return parser.parse_args()


def main():
    args = parse_args()

    sys.path.insert(0, str(SCRIPT_DIR))
    from runner_lib import (
        load_repos_from_file,
        discover_org_repos,
        run_batch,
        commit_results,
        write_failed_repos,
    )

    # Resolve repo list
    if args.from_file:
        org, repos = load_repos_from_file(Path(args.from_file))
    else:
        org = args.org
        repos = discover_org_repos(org)

    if not repos:
        print("No repos to assess. Exiting.")
        sys.exit(0)

    print(f"Assessing {len(repos)} repos in {org} with {args.workers} workers...")

    succeeded, failed = run_batch(
        org=org,
        repos=repos,
        output_dir=args.output_dir,
        workers=args.workers,
        retries=args.retries,
    )

    if succeeded:
        commit_results(REPO_ROOT, org, succeeded)

    failed_path = SCRIPT_DIR / "failed-repos.yaml"
    if failed:
        write_failed_repos(failed_path, org, failed)
        print(f"\n{len(failed)} repos failed. Written to {failed_path}")
    elif failed_path.exists():
        failed_path.unlink()

    print(f"\nDone: {len(succeeded)} succeeded, {len(failed)} failed")


if __name__ == "__main__":
    main()
