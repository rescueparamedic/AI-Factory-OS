# AI Factory OS Project Status

## AFDE-3.1 Safe Auto Approval Engine

- Existing Approval Guardian and Controlled Execution policies are enforced
  together at the real runtime side-effect boundary.
- AUTO_APPROVE requires both policies and durable evidence; ASK_USER preserves
  exact action/context and waits; DENY and subsystem failures fail closed.
- Resume revalidates branch, cwd, repository, environment, task/session,
  action payload, target, and one-time approval state.
- Sprint Auto Runner and Sprint 5 lifecycle/handoff/revision behavior remain
  compatible without double execution.

## AFDE-3.0 Sprint 5

- Runtime lifecycle finalization and structured failure propagation are
  implemented from the verified Sprint 4 merge baseline
  `7546487699b79495fd4f8ad1b39bd06dd638e895`.
- `RuntimeTask` remains the lifecycle state owner and now persists validated
  terminal/pause state, ordered transitions, per-role attempts, normalized
  failures, and a derived final execution summary.
- Successful, revision, revision-exhaustion, required-role failure, invalid
  result, approval wait/resume, and approval rejection paths now finalize
  deterministically without replacing role results or result handoffs.
- AFDE-2.7 approval and Guardian semantics, controlled execution, Execution
  Truth, provider behavior, and Sprint 1-4 public contracts remain preserved.

## AFDE-3.0 Sprint 4

- Multi-Agent Result Handoff and QA Revision Loop is implemented on
  `feature/afde-3.0-sprint-4-result-handoff-qa-revision` from the verified
  Sprint 3 merge baseline.
- Typed Planner-to-Developer, Developer-to-QA, QA-to-Developer, and
  QA-to-Documentation result handoffs now persist producer/consumer roles,
  task identity, result reference, validation metadata, revision state, and
  append-only delivery history.
- Typed QA decisions persist acceptance, revision request, limit exhaustion,
  reason, count, configured maximum, and the source QA result reference.
- `RuntimeOrchestrator` owns handoff creation/delivery and QA decisions while
  retaining the existing pipeline, role executor, task, and context layers.
- Approval, Guardian, controlled execution, Execution Truth, provider
  behavior, and deterministic bounded revision limits remain unchanged.

## AFDE-3.0 Sprint 3

- Agent Role Execution is implemented on
  `feature/afde-3.0-sprint-3-agent-role-execution` from the verified Sprint 2
  merge baseline.
- Planner, Developer, QA, and Documentation now execute through one typed,
  provider-neutral `RoleExecutor` boundary requested by `RuntimeOrchestrator`.
- Typed role requests/results persist task, role, worker, state, output,
  evidence references, handoff, error, and append-only execution history.
- Role failures, invalid results, identity mismatches, invalid handoffs,
  missing evidence, and terminal execution fail through existing task/session
  and event semantics.
- AFDE-2.7 approval, Guardian, controlled execution, Execution Truth, provider
  behavior, and bounded QA revisions remain authoritative and unchanged.

## AFDE-3.0 Sprint 2

- The first real Multi-Agent Runtime Orchestrator is implemented on
  `feature/afde-3.0-sprint-2-runtime-orchestrator`.
- `RuntimeOrchestrator` now owns deterministic Planner, Developer, QA,
  Documentation, approval-boundary, and bounded revision routing through the
  existing `RuntimePipeline` and registered workers.
- Revision count, decisions, limits, and safe limit errors persist with the
  existing `RuntimeTask`; `WorkerContext` remains the canonical serialized
  handoff and approval-continuation context.
- Actual orchestration decisions are append-only event evidence alongside the
  existing task, pipeline, approval, provider, controlled-execution, and
  Execution Truth events.
- QA revision-controlled actions can pause and resume through the unchanged
  AFDE-2.7 approval boundary before returning to QA.

## AFDE-3.0 Sprint 1

- Multi-Agent Development Pipeline Foundation is implemented on
  `feature/afde-3.0-sprint-1-runtime-pipeline`.
- Planner-created tasks now carry explicit ownership and handoff metadata
  through Developer, QA, Documentation, and Runtime completion.
- Controlled actions enter the existing AFDE-2.7 approval boundary and resume
  into QA without changing approval records, binding, or consumption.
- Pipeline lifecycle and events are additive to the AFDE-2.9 task state engine
  and AFDE-2.8 Worker Context.

## AFDE-2.9

- Runtime Task and Worker State Engine is implemented on
  `feature/afde-2.9-runtime-task-state`.
- Planner output creates one persisted Developer task with validated state
  transitions, task history, runtime-owned evidence, and task-scoped events.
- Approval pause/resume uses `WAITING_APPROVAL` and `RESUMED` task states while
  retaining the exact AFDE-2.7 approval records, bindings, and single-use
  execution path.
- AFDE-2.8 Worker Context remains the sole Planner-to-Developer context layer.

## AFDE-2.8 PR-1

- Worker Context is implemented on
  `feature/afde-2.8-worker-context`.
- Planner output, task metadata, runtime evidence, and prior worker artifacts
  now move through one runtime-owned context to the Developer.
- Legacy mapping access and approval continuation restoration preserve the
  AFDE-2.7 provider, Guardian, controlled-execution, and Execution Truth paths.

## AFDE-2.7

- Human approval pause/resume is implemented on its feature branch.
- Existing-file writes persist exact `ASK_USER` state and remain unchanged until
  one bound approval is consumed.
- The Product Owner-gated live lifecycle completed with an exact LF payload,
  one runtime-observed bounded fixture test, and Execution Truth `VERIFIED`.
- The invalid provider payload from the earlier fail-closed attempt remains
  unapproved evidence; runtime data is excluded from the source commit set.

## AFDE-2.5

- Executable five-worker mock Demo operates without external API keys.

## AFDE-2.4

- Sprint Auto Runner implemented on a feature branch.
- Every Runner command is evaluated by Approval Guardian v2.
- ASK_USER state is resumable only with matching definition and context.
- Direct pushes to protected branches remain forbidden and merge remains a
  user-controlled operation.

## AFDE-2.3

- Approval Guardian v2 implemented on a feature branch.
- Command decisions use `AUTO_APPROVE`, `ASK_USER`, and `DENY` with fail-closed
  and deny-overrides behavior.
- Existing release approval workflows remain backward compatible.
- Central enforcement across every worker executor remains planned work.

## 현재 상태

| 항목 | 내용 |
|---|---|
| Version | v1.0.0 |
| 상태 | Baseline Frozen |
| 목적 | AI 개발회사 워크플로우 구현 전 안정 기준점 |
| 기준 | OS Core / Agent / Team / Worker / Update / Repository 기반 완료 |

## 완료

- OS Core MVP
- Task Engine
- Workflow Engine
- Agent / Team Architecture
- Worker Standard
- Update Manager
- Project Doctor
- CLI Modularization
- Product Development Pipeline MVP
- Repository Mode

## 다음 목표

AI Factory v1.1 Planning Agent 실작동 구현
