# AFDE-3.1 Safe Auto Approval Engine

## Baseline and objective

AFDE-3.1 started from `origin/develop` merge commit `1606638`, which contains
PR #14 and the completed AFDE-3.0 Sprint 5 runtime lifecycle. The objective is
central approval enforcement at the real runtime protected-execution boundary,
not a replacement policy engine.

## Existing approval architecture reused

- `approval_guardian.ApprovalDecision` remains the canonical
  `AUTO_APPROVE`/`ASK_USER`/`DENY` model.
- `ApprovalGuardian` and its deny-overrides rule classifier remain the
  authoritative command policy.
- `ExecPolicyAdapter` continues to provide Safe Approval Policy v1
  compatibility.
- `ControlledExecutionPolicy` remains the structured file/command execution
  policy and `ControlledExecutor` remains the only runtime side-effect owner.
- `RuntimeApprovalStore` remains the exact, single-use human approval store.
- Sprint Auto Runner retains its direct Guardian evaluation and execution
  model; AFDE-3.1 does not route or execute Runner steps a second time.

## Central runtime interception

`ControlledExecutor.execute()` is the authoritative interception point
immediately before a runtime file write or command execution. It normalizes
the request/context, evaluates existing Controlled Execution policy and
Approval Guardian, applies deny-overrides, records evidence, and only then
executes an allowed action. Runtime workers can propose actions but cannot
perform these side effects directly. Provider prose remains non-executable.

The optional controlled-execution setting is preserved: when disabled,
proposals remain unverified claims and no protected side effect occurs.

## Normalized context and exact identity

`RuntimeApprovalContext` records normalized `cwd`, repository, branch,
environment, runtime task ID, runtime session ID, stage, actor, and sanitized
metadata. Its SHA-256 context fingerprint is deterministic. The action
fingerprint covers action type, source worker, target, content hash or argv,
pre-image hash, and purpose without embedding secret content. Equivalent
actions no longer depend on a random request ID; legacy persisted fingerprints
remain readable under the existing exact request/payload checks.

Human approval is additionally bound to approval ID, execution request ID,
session, continuation, exact payload, target, and one-time approval state.
Resume rebuilds the current context and compares its fingerprint before
changing approval state. A mismatch executes nothing, records invalidation,
and requires a new approval. Valid resume records approver, approval time,
revalidation result/time, and consumption.

## Decision behavior

### AUTO_APPROVE

AUTO_APPROVE requires both existing policies to allow execution. Decision
evidence must be persisted before execution; audit failure blocks execution.
Execution failure remains an execution result, not approval success.

### ASK_USER

ASK_USER executes nothing, persists the exact action/context and reason, and
uses `running -> waiting_approval`. User-visible state exposes
`RUNTIME_APPROVAL_REQUIRED`, redacted action summary, approval ID, reason, and
exact-resume guidance. Valid approval transitions back to `running`, executes
and validates the action, consumes approval once, then resumes later roles.

### DENY and failure safety

Either policy may deny and DENY always wins. Existing workspace, Git metadata,
secret, shell, network, command, and path restrictions remain fail closed.
Guardian exceptions, malformed/unknown decisions, context/policy normalization
failure, fingerprint mismatch, and mandatory audit failure never execute and
expose `RUNTIME_CONTROLLED_EXECUTION_BLOCKED` evidence.

Controlled Execution remains authoritative after permission. DENIED and
PREIMAGE_MISMATCH cannot be overridden by AUTO_APPROVE or human approval.
Approval permits an attempt; it never asserts execution success.

## Runtime, Runner, and CLI integration

RuntimePipeline, RuntimeOrchestrator, RoleExecutor, Result Handoff, bounded QA
revision, structured failures, terminal protection, and transition history are
unchanged. Initial and revision execution pass task/session/stage context to
the same final boundary.

Sprint Auto Runner retains Guardian evaluation, context/command fingerprints,
audit-before-execution, exact resume, and protected-branch rules. It does not
call ControlledExecutor and cannot double-execute a step.

CLI waiting output now includes safe Guardian reason and exact-resume guidance.
Runtime evidence includes decision, rule, reason, actor, stage, runtime IDs,
action/context fingerprints, timestamp, approval state, and result reference.

## Validation

- Baseline: `429 passed, 1 skipped`.
- AFDE-3.1 focused tests: `19 passed`.
- Approval/runtime/runner matrix: `165 passed`.
- Full pytest: `448 passed, 1 skipped`.
- CLI environment, providers, mock runtime, Guardian decision triad, and
  controlled approval pause passed. No paid API call was made.

## Security, compatibility, and limitations

No AUTO_APPROVE rule was added or broadened. There is no shell execution,
approval bypass, deployment, protected-branch mutation, secret transmission,
or paid-provider call. Existing public parameters remain compatible and new
context parameters are optional.

Local JSON lacks multi-process locking, cryptographic signatures, multi-user
RBAC, remote notification, and tamper-evident distributed audit. Unrelated
legacy executors are not globally monkey-patched.

## Rollback plan

Revert the AFDE-3.1 feature commits after preserving runtime/approval evidence.
Sprint 5 records remain readable because this change is additive. Do not
rewrite shared branch history.
