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

## Safety

- No external AI API call is executed in this Sprint.
- Provider keys are checked only for readiness.
