# AI Factory OS Sprint v2.7.2 Scheduler CLI Final Fix

## Status
- Sprint: v2.7.2
- Type: Hotfix / Final Scheduler CLI connection
- Target: Sprint v2.7 Task Scheduler & Worker Queue

## Fixed
- `scheduler` top-level CLI command is registered through `cli/app.py`.
- `scheduler_cli.py` is included.
- `scheduler_engine` is included.
- `main.py` is included to make patch application visually clear and safe.
- Dashboard queue monitor files are included.
- README commands now match the actual CLI.

## Verified Commands
- `python main.py -h`
- `python main.py scheduler status`
- `python main.py scheduler enqueue ...`
- `python main.py scheduler next`
- `python main.py scheduler run-next`
- `python main.py scheduler list --limit 5`
- `python main.py dashboard live-build`
