# Sprint AFDE-2 Changelog

## AFDE-2.8 PR-1 Worker Context

- Expanded the runtime-owned `WorkerContext` with planner output, task
  metadata, runtime evidence, and prior worker artifacts.
- Passed one typed context through the Planner-to-Developer boundary while
  retaining the provider-facing mapping contract.
- Added JSON-safe context persistence and restoration across the existing
  AFDE-2.7 approval/resume path.
- Added focused creation, propagation, legacy-mapping, and resume coverage.

## AFDE-2.7 Human Approval Resume and Controlled Existing-File Edit

- Added persisted, exact, single-use approval records for existing-file edits.
- Added `waiting_approval` pause and cross-process runtime continuation.
- Added approval show, approve/resume, and reject CLI commands.
- Added pre-image protection, replay rejection, and runtime approval evidence.
- Preserved AFDE-2.6 new-file and bounded-command behavior.
- Completed the explicitly authorized live lifecycle with one exact existing-file
  write, one runtime-observed bounded pytest execution, and Execution Truth
  `VERIFIED`; the dedicated fixture was restored to its LF baseline afterward.

## AFDE-2.6 Real AI Provider

- Added an opt-in OpenAI Responses API provider with environment-only credentials.
- Added model, timeout, retry, usage, request ID, and structured error handling.
- Preserved deterministic mock execution and offline test behavior.
- Connected OpenAI to the five-worker runtime, revision loop, events, artifacts,
  and the `factory-demo` CLI.

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

- External AI calls remain opt-in. AFDE-2.7 used only the explicitly authorized
  controlled live validation and persisted no provider credential values.
