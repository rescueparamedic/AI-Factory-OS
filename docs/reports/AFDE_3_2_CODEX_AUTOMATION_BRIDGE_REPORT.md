# AFDE-3.2 Codex Automation Bridge Report

## Outcome

AFDE now accepts a canonical structured `ToolAction` array from worker results,
binds every action to runtime context, evaluates policy, and returns observed,
redacted evidence. Legacy `proposed_file_writes` and
`requested_test_executions` remain compatible only when `actions` is absent.

## Contract

Every action contains `action_id`, `action_type`, `source_worker`, `purpose`,
`target`, `arguments`, `cwd`, `repository`, `branch`, `runtime_task_id`,
`runtime_session_id`, `stage`, `revision`, `preconditions`, `expected_result`,
and `metadata`. Unknown or missing fields fail closed. Supported types are:

- `FILE_READ`, `FILE_WRITE`, `COMMAND_RUN`, and `TEST_RUN`
- `GIT_STATUS`, `GIT_DIFF`, `GIT_ADD`, `GIT_COMMIT`, and `GIT_PUSH_FEATURE`

Merge, deploy, release, force push, hard reset, clean, protected-branch push,
secret input, shell composition, and raw-text command inference are not part of
the contract.

## Governed flow

`CodexAutomationBridge` extracts structured actions, validates and fingerprints
them, checks exact runtime context, and dispatches through `FileToolAdapter`,
`CommandToolAdapter`, `TestToolAdapter`, or `GitToolAdapter`. All protected file,
command, test, and Git side effects are converted to the existing
`ExecutionRequest` and cross the AFDE-3.1 `ControlledExecutor`. Its existing
`ApprovalGuardian` co-policy remains authoritative. `FILE_READ` is non-mutating
but still passes Guardian classification and workspace/secret/size checks.

AUTO executes and records evidence, ASK pauses the exact action through the
existing approval continuation, and DENY blocks the runtime. No second approval
or execution engine was added.

## Safety and evidence

Action fingerprints cover the complete normalized contract. `action_id` is
claimed atomically before execution; a repeated ID returns `DUPLICATE` without
running again. Per-action JSON and an append-only JSONL ledger under
`data/tool_action_evidence` record status, decision, hashes, changed state,
exit code, duration, bounded/redacted output, test evidence, and Git evidence as
applicable. Controlled Execution continues to write its own authoritative
pre/post evidence.

Git automation is restricted to exact read-only status/diff, explicit contained
staging paths, one-message commits on the current feature branch, and pushes to
the exact current `feature/*` branch. Shells, broad staging, branch mismatch,
protected targets, and other Git commands fail closed.

## Operator workflow

The deterministic mock requires no API or credential:

```powershell
python -m afde.cli tool-action-demo --path auto
python -m afde.cli tool-action-demo --path ask
python -m afde.cli tool-action-demo --path deny
python -m afde.cli tool-action-status --action-id <ACTION_ID>
```

The existing `factory-demo --enable-controlled-execution` path also consumes
structured worker actions. Live provider access remains separately opt-in.

## Verification scope

Tests cover contract validation, malformed and unsupported actions,
fingerprints, exact context binding, AUTO/ASK/DENY, all adapter families,
output evidence, duplicate prevention, canonical-over-legacy selection, mock
runtime integration, and existing Controlled Execution/provider regressions.

## Deferred work

The local claim/evidence store is not a transactional multi-host queue and the
JSONL ledger is not cryptographically chained. Human approval of new files
outside the controlled sandbox still follows the older resume constraint that
only existing-file replacement is currently consumable. Remote PR creation,
deployment, release, merge, and protected-branch operations remain outside the
bridge.
