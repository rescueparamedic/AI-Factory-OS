# AFDE-2.3 Existing Approval Architecture

## Baseline

The Sprint started from `origin/develop` at `bd67b6d`. The baseline suite had
14 passing tests. AFDE `env-check`, `providers`, and `run-mock` also passed.

Safe Approval Policy v1 exists on pull request #2 but is not part of the
`develop` baseline. Approval Guardian v2 therefore exposes an adapter without
copying project-local Codex rules into this branch.

## Existing paths

| Concern | Existing path | Current behavior | Extension point |
|---|---|---|---|
| Release approval | `approval_gate/approval_gate.py` | Owner approves or rejects documented release candidates | Retained unchanged; this is business approval, not command approval |
| Approval CLI | `cli/approval_cli.py` | Displays and resolves release approval queue items | Retained unchanged |
| General decisions | `os_core/decision_engine.py` | Marks a small set of request types as approval-required | No command parsing or execution guard |
| Worker permissions | `workers/base_worker.py` | Publishes permission metadata | No command-level policy enforcement |
| Shell entry points | `afde/cli.py`, `afde/environment_checker.py`, `afde/git_manager.py` | Limited subprocess calls use argument arrays and `shell=False` | AFDE CLI gains a classification-only `approval-check` path |
| Audit | `workers/audit_log_worker.py`, `data/audit/` | JSON audit records | Guardian writes compatible JSON decision events into `data/audit/` |
| Codex ExecPolicy | PR #2, not merged into baseline | allow/prompt/forbidden project policy | `ExecPolicyAdapter` maps decisions to Guardian v2 terminology |

## Compatibility and risks

- `ApprovalGate` public methods and CLI response schema remain unchanged.
- Guardian is additive and does not execute commands.
- Audit records redact sensitive commands and retain a SHA-256 fingerprint.
- Existing subprocess call sites are not automatically intercepted in this
  Sprint; callers must evaluate before execution. This is recorded as technical
  debt rather than silently changing all execution behavior.
- Text command parsing differs across operating-system shells. Unknown,
  malformed, obfuscated, or unsupported forms fail closed to `ASK_USER` or
  `DENY`.
