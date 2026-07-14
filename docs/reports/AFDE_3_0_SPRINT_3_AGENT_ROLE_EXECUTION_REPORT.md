# AFDE-3.0 Sprint 3 Agent Role Execution Report

## Objective and baseline

Sprint 3 moves the merged runtime from orchestration-only coordination to
explicit role-owned execution for Planner, Developer, QA, and Documentation.
Development started from the required `origin/develop` baseline
`71fd614b841361aee86187f4063a94a1dbfdbaba` on
`feature/afde-3.0-sprint-3-agent-role-execution`.

## Architecture added

The additive `role_execution` module defines:

- `RuntimeRole` and `RoleExecutionState`;
- `RoleExecutionRequest` and `RoleExecutionResult`;
- role-specific Planner, Developer, QA, and Documentation result types; and
- one provider-neutral `RoleExecutor` boundary.

Every persisted role result carries task, role, and worker identity, execution
state, structured output, evidence references, requested handoff, timestamps,
error information, and append-only state history. `RuntimeTask.role_executions`
persists these normalized results through the existing task artifact and
approval continuation path.

## Role responsibilities

- Planner consumes the original request and `WorkerContext`, produces tasks
  and acceptance criteria, initializes the task input, and requests Developer
  ownership.
- Developer consumes Planner output through `WorkerContext`, executes through
  the existing worker/provider bridge, records structured output and runtime
  evidence references, and surfaces controlled actions to the existing
  approval boundary before requesting QA.
- QA consumes Developer output and task evidence, records a structured pass or
  revision result, and requests Developer or Documentation ownership according
  to the authoritative bounded revision state.
- Documentation requires prior Planner, Developer, and passing QA artifacts,
  references existing runtime evidence, rejects fabricated verification, and
  completes the task and pipeline only after its own successful role result.

## Role execution boundary

`RoleExecutor` wraps the existing `BaseWorker` and `ProviderBridge`. It does not
create another provider registry and does not place provider-specific logic in
the orchestrator. The runtime accepts an additive executor factory for
deterministic scripted tests; production defaults continue to use the selected
existing provider bridge. No provider interface was changed.

## Orchestrator integration

`RuntimeOrchestrator` now determines the current owner, builds a typed role
request, invokes the executor, validates the normalized result, and appends it
to the current task. It rejects mismatched task/role/worker identity, invalid
handoffs, terminal-state execution, and unstructured results. The existing
runtime remains responsible for lifecycle transitions, persistence,
controlled actions, Execution Truth normalization, and pipeline forwarding.

The existing event stream additively records `ROLE_EXECUTION_STARTED`,
`ROLE_RESULT_RECORDED`, `ROLE_EXECUTION_COMPLETED`, `ROLE_EXECUTION_FAILED`, and
`ROLE_HANDOFF_REQUESTED` without removing or renaming prior events.

## Approval and QA revision compatibility

Developer controlled actions still pause only through AFDE-2.7. A waiting
Developer role result requests `approval_guardian`; approval consumption
appends a completed result for the same task before QA, while rejection appends
a failed result and never fabricates successful Developer evidence. Guardian,
approval binding, pre-image validation, single-use consumption, and controlled
execution are unchanged.

QA revision continues to use the Sprint 2 persisted revision counter and
maximum. Each revision appends Developer and QA role executions; limit
exhaustion fails explicitly and never runs Documentation.

## Execution Truth preservation

Provider output remains a claim until the existing Execution Truth contract
normalizes it with runtime-observed evidence. Role results reference proposed
work, controlled requests, approved execution evidence, QA results, and runtime
evidence without promoting claims into verified work. Documentation cannot
introduce verified file or test evidence that differs from `WorkerContext`.

## Failure semantics

Planner, Developer/provider, QA, and Documentation failures produce failed
role results, `ROLE_EXECUTION_FAILED`, failed RuntimeTask state, and failed
session state without a successful handoff. Invalid results, identity mismatch,
invalid handoff, missing Documentation evidence, and terminal execution are
rejected deterministically through `RoleExecutionError` or `InvalidRoleResult`.

## Changed files

The intended Sprint 3 scope is ten files: project status, changelog, this
report, package exports, runtime errors, runtime integration, orchestrator,
task persistence, the new role execution module, and focused role tests.

## Tests and validation

- Sprint 3 focused role tests: 20 passed.
- Combined runtime, approval, Guardian, controlled-execution, Execution Truth,
  and provider regression matrix: 219 passed.
- Full pytest: 392 passed, 1 skipped.
- Python compile validation: PASS.
- Exact ten-file scope secret scan: PASS.
- `git diff --check`: PASS.

## Known limitations

- PM remains the existing pre-planning worker and is intentionally outside the
  four-role Sprint 3 execution model.
- Role results reference runtime evidence; they do not replace the evidence or
  independently verify provider claims.
- No live provider call, release, or deployment is part of this sprint.

## Commit and pull request identity

The exact commit SHA and PR number/URL are authoritative in the Git object, PR
metadata, and final Product Owner handoff. They cannot be embedded in the same
single implementation commit before that commit and subsequent PR exist
without changing the SHA or requiring a prohibited amend/force-push cycle.
