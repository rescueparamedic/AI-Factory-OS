# AFDE-3.0 Sprint 1 Runtime Pipeline Foundation Report

## Scope

Sprint 1 adds a runtime-owned multi-agent pipeline over the existing AFDE-2.9
task engine. `RuntimePipeline` tracks one Planner-created task through
assignment, development, QA, documentation, and completion. `RuntimeTask`
retains its original assigned worker and now also records current ownership and
append-only handoff metadata.

## Pipeline lifecycle

The normal path is:

`PLANNED -> ASSIGNED -> DEVELOPING -> QA_PENDING -> DOCUMENTING -> DONE`

QA revision may return `QA_PENDING -> DEVELOPING`. Controlled existing-file
actions preserve the AFDE-2.7 security boundary:

`DEVELOPING -> APPROVAL_PENDING -> QA_PENDING`

Approval remains conditional. A pipeline with no `ASK_USER` controlled action
does not fabricate human approval or create a duplicate approval layer.

## Events and artifacts

The existing runtime event stream records `TaskAssigned`, `TaskStarted`,
`TaskCompleted`, `TaskForwarded`, `TaskRejected`, and `TaskApproved` objects
with the AFDE-2.9 task ID and pipeline state. Existing uppercase runtime,
approval, QA, and Execution Truth events remain unchanged.

Pipeline state is persisted in the runtime session, the AFDE-2.8
`WorkerContext` approval continuation, and `runtime_pipeline.json`. Task
ownership and every handoff are persisted in `runtime_task.json`.

## Compatibility and security

The implementation does not change provider request construction, Approval
Guardian classification, controlled execution policy, persisted approval
records, exact approval binding, pre-image validation, single-use approval
consumption, or Execution Truth normalization. Approval rejection and QA
rejection are observed by the pipeline without replacing their source
components.

## Validation

- focused pytest: 194 passed;
- full pytest: 363 passed, 1 skipped;
- compile validation: PASS;
- secret scan: PASS; and
- `git diff --check`: PASS.
