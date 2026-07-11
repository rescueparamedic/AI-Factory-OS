# AFDE-2.4 Sprint Auto Runner Architecture

## Baseline

- Started from `origin/develop` merge commit `f8545a4` after PR #3 merged.
- Baseline pytest: 100 passed.
- Existing env-check, providers, and run-mock commands passed.

## Components

| Component | Responsibility |
|---|---|
| `models.py` | Immutable Sprint definitions and persisted run/step state |
| `loader.py` | Strict JSON loading, validation, and SHA-256 fingerprint |
| `approval_bridge.py` | Mandatory Guardian call plus protected-push DENY overlay |
| `step_executor.py` | Non-shell process execution, timeout, and output capture |
| `state_store.py` | Atomic JSON state persistence and corruption detection |
| `audit.py` | Redacted JSONL lifecycle events |
| `runner.py` | State machine, approval stop/resume, cancellation, and dry-run |
| `adapters/exec_policy_adapter.py` | Reuses Safe Approval Policy v1 mapping |
| `afde/cli.py` | validate/run/status/resume/cancel command surface |

## State flow

`created → running → completed|failed|waiting_approval|blocked|cancelled`

Each pending step moves through evaluating and Guardian decision states before
it can become running. ASK_USER and DENY never reach the executor. Resumed
approval is valid only for the same definition, step, command, cwd,
environment, branch, and HEAD.

## Compatibility

Approval Guardian v2 is reused, not copied. Existing AFDE CLI commands and
Guardian public response schemas are unchanged. The implementation adds a new
execution path rather than replacing legacy executors.
