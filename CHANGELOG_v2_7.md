# AI Factory OS Sprint v2.7 CHANGELOG

## Sprint
- v2.7 Task Scheduler & Worker Queue

## Added
- `scheduler` CLI command group
- JSON-based Task Scheduler
- Priority Queue: critical > high > medium > low
- Worker Queue execution through existing WorkerManager
- Retry Manager with configurable retry limit
- Scheduler status, next job, list, run-next, run-all, run-job commands
- Live Dashboard Worker Queue monitor
- Scheduler tests

## Changed
- `cli/app.py` registers `scheduler` command.
- `os_core/kernel.py` initializes `TaskScheduler` and exposes scheduler methods.
- `dashboard_engine/live_dashboard.py` includes queue metrics and Worker Queue table.

## Safety
- Existing commands remain unchanged.
- Existing tasks and worker results are not deleted.
- Scheduler uses JSON files only.
- External API calls are not required.
