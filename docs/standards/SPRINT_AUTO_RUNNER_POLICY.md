# Sprint Auto Runner Policy

## Execution contract

Every Sprint step is converted to an `ApprovalRequest` and evaluated by
Approval Guardian v2 before execution:

- `AUTO_APPROVE`: record the decision, execute with `shell=False`, persist the
  result, and continue.
- `ASK_USER`: do not execute; persist `waiting_approval` and return the run ID,
  step ID, redacted command, rule ID, reason, and resume token.
- `DENY`: do not execute; mark the step `denied` and run `blocked`.

The Runner adds one stricter invariant: direct pushes to `main`, `master`, or
`develop` are always denied. Merge remains approval-sensitive and is never
automatic.

## Definition and state

Sprint definitions are UTF-8 JSON files with non-empty identifiers, title,
version, and steps. Duplicate step IDs, empty commands, invalid timeouts,
unknown environments, malformed exit-code lists, and malformed JSON are
rejected.

Run state is atomically persisted under `data/sprint_runs/<run_id>.json`.
Audit events are appended to `<run_id>.audit.jsonl`. Definition, command,
execution context, branch, and HEAD fingerprints prevent unsafe resume after a
change.

## Resume

Only the currently waiting step may be approved. Approval requires an explicit
`approved` decision and `approved_by`. Immediately before execution the Runner
re-evaluates Guardian and verifies the stored command/context fingerprints.
Changed definitions, commands, context, rules, or a new DENY invalidate the
approval. Passed steps are never executed again.

## Executor

The executor parses command tokens using the existing Guardian parser and
passes argument arrays to `subprocess.run(shell=False)`. It captures stdout,
stderr, exit code, duration, start/end timestamps, timeout, and process-start
failures. Output and audit data are redacted before persistence.

## Audit failure

If audit recording fails before a safe command executes, the step becomes
`waiting_approval` and no process starts. If completion audit fails after a
process ran, the run becomes `failed` and automatic retry is disabled.

## CLI

- `sprint-validate --file <json>`
- `sprint-run --file <json> [--dry-run]`
- `sprint-status --run-id <id>`
- `sprint-resume --run-id <id> --approve-step <step>`
- `sprint-cancel --run-id <id>`

Each supports human-readable output; operational commands support `--json`.
Dry-run performs Guardian evaluation without creating a run state file or
executing commands.
