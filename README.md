# agentready-scores

Centralized AgentReady assessment scores for konflux-ci repositories.

Assessment files are stored under `submissions/{org}/{repo}/` and ingested by a local DevLake instance using the [agentready plugin](https://github.com/konflux-ci/devlake).

## Structure

```
submissions/
  konflux-ci/
    {repo}/
      assessment-latest.json          ← symlink to latest assessment
      assessment-YYYYMMDD-HHMMSS.json ← actual assessment data
runner/
  assess.py       ← concurrent assessment runner (local + CI)
  repos.yaml      ← curated repo list for demo runs
  requirements.txt
.github/workflows/
  assess-manual.yml     ← workflow_dispatch for demo
  assess-scheduled.yml  ← weekly cron for production
```

## Running Locally

```bash
cd runner
pip install -r requirements.txt
python assess.py --mode demo
```

## Re-running failures

```bash
python runner/assess.py --from-file runner/failed-repos.txt
```

See `docs/superpowers/specs/` for the full design spec.
