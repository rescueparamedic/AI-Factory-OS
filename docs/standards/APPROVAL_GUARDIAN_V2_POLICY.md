# Approval Guardian v2 Policy

## Contract

`ApprovalGuardian.evaluate(ApprovalRequest)` returns an immutable
`ApprovalResult` with one decision:

- `AUTO_APPROVE`: verified low-risk inspection, validation, or feature workflow
- `ASK_USER`: human approval is required before execution
- `DENY`: execution is forbidden and no approval choice is offered

Precedence is `DENY`, then `ASK_USER`, then `AUTO_APPROVE`. Unknown commands
default to `ASK_USER`. Evaluation failures fail closed.

## Rule families

| Family | Meaning |
|---|---|
| `AGV2-D001` | Destructive Git operation |
| `AGV2-D002` | Destructive filesystem operation |
| `AGV2-D003` | Credential exfiltration or security bypass |
| `AGV2-D004` | Obfuscated or policy-bypass execution |
| `AGV2-A001` | Protected branch or merge action |
| `AGV2-A002` | External network or data transfer |
| `AGV2-A003` | Dependency or system configuration change |
| `AGV2-A004` | Bulk, external, or irreversible file operation |
| `AGV2-A005` | Production, deployment, or release action |
| `AGV2-A999` | Unknown, malformed, or unclassified command |
| `AGV2-S001` | Read-only inspection |
| `AGV2-S002` | Test or static verification |
| `AGV2-S003` | Verified feature-branch Git workflow |
| `AGV2-S004` | Reserved for repository-local structured edits |

## Context requirements

Evaluation considers repository root, working directory, current and target
branch, working-tree cleanliness, environment, actor, and task ID. Writes
outside the repository and production mutations cannot be auto-approved.
Feature pushes require both a feature target and feature-branch context.

## Compound commands and wrappers

The parser separates quote-aware `&&`, `||`, `;`, pipe, and newline chains.
Every subcommand is evaluated. It unwraps `bash -c`, `sh -c`, `cmd /c`,
`powershell -Command`, and `python -c`. A single denied subcommand denies the
whole chain; otherwise a single approval requirement makes the whole chain
`ASK_USER`.

Encoded commands, command substitution, and other policy-bypass forms are not
auto-approved.

## Audit and secrets

Every evaluated decision writes an `APPROVAL_GUARDIAN_DECISION` JSON record to
the existing `data/audit/` path. Records include decision, risk, rule, reason,
actor, task, cwd, branch, timestamp, redacted command, and SHA-256 fingerprint.
Plaintext `.env`, token, password, credential, and authorization values are not
stored.

## Execution boundary

Guardian classifies requests; it never executes them. An executor may continue
only for `AUTO_APPROVE`, must enter `waiting_approval` for `ASK_USER`, and must
stop for `DENY`.
