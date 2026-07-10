# Sprint AFDE-2 Changelog

## Added

- AFDE Environment Checker
- Real AI Worker Bootstrap
- CLI commands:
  - `env-check`
  - `bootstrap-worker`
- Development docs for environment checking and worker bootstrap
- Unit tests for AFDE-2

## AFDE-2.3 Approval Guardian v2

### Added

- Deterministic `AUTO_APPROVE`, `ASK_USER`, and `DENY` command classification
- Quote-aware chained-command and shell-wrapper analysis
- Repository, branch, working-tree, and environment context guards
- Redacted decision audit records and ExecPolicy compatibility adapter
- AFDE `approval-check` CLI command
- 86 focused Guardian policy and integration tests

## AFDE-2.4 Sprint Auto Runner

### Added

- Approval-guarded Sprint JSON loader and deterministic run state machine
- AUTO_APPROVE execution, ASK_USER persistence/resume, and DENY blocking
- Non-shell executor with timeout, output capture, and redaction
- Atomic JSON state and JSONL lifecycle audit records
- AFDE sprint validate, run, status, resume, cancel, JSON, and dry-run CLI
- 64 focused Runner tests and demo Sprint definition

## AFDE-2.5 Real AI Worker Runtime

- Added five-worker Demo, dashboard, mock provider, messages/events/artifacts,
  Runner/Guardian validation, revision loop, runtime CLI, and 53 focused tests.

## Safety

- No external AI API call is executed in this Sprint.
- Provider keys are checked only for readiness.
