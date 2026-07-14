# AFDE-3.0 Sprint 2 Runtime Orchestrator Report

## Objective

Sprint 2 introduces the first explicit Multi-Agent Runtime Orchestrator inside
`real_worker_runtime`. The implementation coordinates the existing
`RealWorkerRuntime`, `RuntimePipeline`, registered workers, `RuntimeTask`, and
`WorkerContext`; it does not introduce a parallel workflow engine.

## Runtime coordination

`RuntimeOrchestrator` owns deterministic routing decisions for the established
pipeline:

`Planner -> Developer -> conditional Approval -> QA -> Documentation -> Done`

QA revision uses the same pipeline and registered worker definitions:

`QA -> Developer -> conditional Approval -> QA`

`RealWorkerRuntime` remains the execution host. Existing `BaseWorker` and
`ProviderBridge` instances perform worker/provider work, and the orchestrator
only selects ownership, validates continuation coherence, records decisions,
and manages the bounded revision count.

## Persisted state and evidence

The existing `RuntimeTask` now carries additive `orchestration_metadata` with:

- the current revision count and configured maximum;
- append-only routing decisions; and
- explicit revision-limit error evidence.

`WorkerContext` remains the canonical cross-worker object. Its existing JSON
round trip preserves planner output, prior artifacts, runtime evidence, task,
pipeline, outputs, and revision state across approval continuation. Task and
pipeline identity and revision state are validated when orchestration resumes.

Every routing choice emits `ORCHESTRATION_DECISION` into the existing runtime
event stream with task identity, source, target, pipeline state, action, and
revision metadata. Existing `TaskForwarded`, worker, QA, approval, provider,
controlled-execution, and Execution Truth events remain in place.

## Bounded QA revision

QA may request multiple revisions up to `max_revisions`. Each accepted request
is persisted before Developer runs again. When the configured limit is
exhausted, orchestration fails safely with a `RevisionLimitExceeded` error,
`ORCHESTRATION_ERROR`, failed task evidence, and no further worker handoff.
There is no unlimited autonomous loop or hidden global mutable state.

## Approval and security compatibility

Controlled actions still enter the AFDE-2.7 approval workflow at the existing
Developer boundary. The orchestrator does not approve, reject, consume, or
execute an action. Approval records remain exact, bound, single-use records;
Guardian and controlled-execution behavior is unchanged. Approval resume
restores the serialized task, pipeline, context, and revision state and routes
the approved Developer result to QA. Rejection retains the existing blocked
session and failed-task semantics.

Provider APIs and provider output validation are unchanged. Tests use only the
deterministic mock provider or monkeypatched failure/revision responses. No live
provider call, release, or deployment is part of Sprint 2.

## Focused coverage

Sprint 2 coverage includes normal and no-approval routing, approval pause and
resume, approval rejection, revision approval continuation, one and multiple
revisions, revision-limit failure, provider failure, context preservation,
task persistence, append-only history, event order/evidence, and AFDE-2.7
through AFDE-3.0 Sprint 1 regressions.

## Validation

- focused pytest: 63 passed;
- full pytest: 372 passed, 1 skipped;
- compile validation: PASS;
- secret scan of the exact nine-file implementation scope: PASS; and
- `git diff --check`: PASS.
