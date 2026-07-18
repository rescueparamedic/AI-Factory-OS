# AFDE-3.10 Maturity and Alpha Gap Analysis

Date: 2026-07-18
Baseline: `develop` at `0e5b9b3`
Previous release: AFDE-3.9 Runtime History Foundation

## 1. Executive decision

AI Factory OS is no longer an architecture prototype. Based on the AFDE-3.9 evidence supplied by the Product Owner, it has a substantial executable control-plane foundation: task/runtime orchestration, provider integration, controlled execution, approval handling, dashboard projections, event history, export, and regression coverage.

However, it is not yet an operator-ready Alpha product. Its main deficit is not another engine. The deficit is a coherent, repeatable user journey that combines the existing parts into one entry point and tells the operator exactly what happened, what requires approval, and what to do next.

**Maturity rating: Alpha foundation complete; operator experience incomplete.**

Recommended AFDE-3.10 objective:

> Deliver an Operator Workflow MVP that lets a user start, inspect, approve/resume, and finish one real AI-assisted development run through a small set of stable CLI commands.

## 2. Current maturity reassessment

| Capability area | Current assessment | Maturity |
|---|---|---:|
| Architecture and domain model | Clear separation of runtime, workers, approvals, events, dashboard, and history | High Alpha |
| Test discipline | 585 passed, 1 skipped; focused regression suites and safety checks | High Alpha |
| Runtime observability | Runtime events, append-only history, dashboard projections, CLI history/export | High Alpha |
| Controlled execution | Existing controlled execution and approval policy provide a safe execution base | Mid/High Alpha |
| Real AI provider path | Implemented and previously validated, but still operationally fragmented | Mid Alpha |
| User workflow | Multiple commands and concepts must be understood and manually chained | Low/Mid Alpha |
| Installation and first run | No confirmed single operator-grade path from clean checkout to completed run | Low Alpha |
| Recovery and next-action guidance | History exists, but operator recovery instructions are not yet the primary interface | Mid Alpha |
| Product readiness | Suitable for developer-led demonstrations; not yet suitable for routine owner use | Pre-Alpha product UX |

## 3. What is actually executable now

The following capabilities are considered executable based on the supplied AFDE-3.9 baseline and prior release sequence:

1. Python CLI entry points under `python -m afde.cli`.
2. Runtime sessions and event streams.
3. Runtime dashboard and localhost API projections.
4. Approval policy and controlled execution boundaries.
5. Real AI provider integration path.
6. Codex automation bridge and tool-action evidence.
7. Runtime history querying and JSON/CSV export.
8. Regression and security validation commands.

These parts demonstrate that the system can execute meaningful development automation. The weakness is that the operator must know which command to run, which IDs to copy, where approval is waiting, and how to recover or inspect a run.

## 4. User-perspective gaps

### Critical gaps

1. **No single start command**
   - A new operator should not need to assemble provider, runtime, execution, dashboard, and history commands manually.

2. **No deterministic next-action output**
   - Every operator-facing command should end with one of: completed, failed, waiting for approval, or blocked, plus the exact next command.

3. **Approval/resume path is not a first-class journey**
   - Approval exists technically, but the user needs an explicit command and a clear summary of what is being approved.

4. **No end-to-end acceptance scenario representing normal use**
   - The release needs one canonical, repeatable scenario from request to controlled file change and evidence.

5. **First-run/preflight friction**
   - Environment, provider key, repository state, execution permission, and localhost availability should be checked before starting work.

### Important but not AFDE-3.10 critical

- Rich web task creation UI.
- Multi-project portfolio management.
- Parallel worker orchestration.
- Persistent database migration beyond current needs.
- Remote deployment and hosted dashboard.
- Broad plugin marketplace.
- Autonomous PR merge or production deployment.

## 5. Technical debt reassessment

| Debt | Current effect | Priority before Alpha exit | Decision |
|---|---|---:|---|
| Fragmented CLI commands | High operator friction and error risk | Critical | Address in 3.10 |
| Missing canonical run contract | Hard to guarantee consistent terminal output and recovery | Critical | Address in 3.10 |
| Incomplete clean-checkout quickstart | Blocks repeatable user validation | Critical | Address in 3.10 |
| Dashboard/API command coordination | Requires manual knowledge | High | Wrap or print exact commands in 3.10 |
| Event schema legacy normalization | Already mitigated by 3.9 | Medium | Do not expand now |
| Append-only JSONL scalability | Acceptable for Alpha | Low | Defer |
| Broad architecture/document drift | Older baseline documents no longer reflect implementation maturity | Medium | Update only affected status/roadmap docs |
| Absence of hosted deployment | Not required for local Alpha | Low | Defer |
| Limited multi-user security model | Local single-owner use is acceptable for Alpha | Low | Defer |

## 6. Minimum capabilities required to exit Alpha

Alpha should end only when all of the following are true:

1. Clean-checkout setup and preflight are documented and verified.
2. One command starts a normal operator workflow.
3. The command creates or identifies a runtime session and prints its ID.
4. The run can use mock mode without credentials and live mode with explicit opt-in.
5. Safe operations proceed automatically according to policy.
6. Sensitive operations stop with a human-readable approval request.
7. The operator can approve or reject through a stable CLI command.
8. A paused run can resume without losing its session/event history.
9. Completion produces a concise final summary and evidence locations.
10. Dashboard and history commands can inspect the same session.
11. A canonical end-to-end acceptance test passes on Windows.
12. An operator quickstart can be followed without internal architecture knowledge.

## 7. AFDE-3.10 ROI candidate comparison

| Candidate | User value | Engineering cost | Risk | ROI |
|---|---:|---:|---:|---:|
| A. Operator Workflow MVP | Very high | Medium | Low/Medium | **Highest** |
| B. Rich dashboard task creation | High | High | Medium | Medium |
| C. SQLite event/history migration | Low immediate | High | Medium | Low |
| D. Parallel multi-agent execution | Medium future | Very high | High | Low |
| E. Additional provider adapters | Medium | Medium | Medium | Medium/Low |
| F. GitHub release automation expansion | Medium | Medium | Medium | Medium |

## 8. Selected AFDE-3.10 scope

**Release name:** AFDE-3.10 Operator Workflow MVP

Primary outcome:

- A user can initiate and control one AI development run without manually stitching together the internal subsystems.

Proposed stable commands:

```powershell
python -m afde.cli operator-preflight
python -m afde.cli operator-run --request "..." --provider mock
python -m afde.cli operator-status --session-id <SESSION_ID>
python -m afde.cli operator-approve --session-id <SESSION_ID> --approval-id <APPROVAL_ID>
python -m afde.cli operator-reject --session-id <SESSION_ID> --approval-id <APPROVAL_ID> --reason "..."
python -m afde.cli operator-resume --session-id <SESSION_ID>
```

The implementation may reuse existing commands internally. It must not duplicate runtime, approval, provider, history, or dashboard logic.

## 9. Explicit non-goals

- New autonomous planning engine.
- New database.
- New web framework.
- Hosted deployment.
- Multi-user authentication.
- Automatic PR merge.
- Unattended use of paid APIs.
- Broad refactoring unrelated to the operator journey.

## 10. Final recommendation

Proceed with AFDE-3.10 Operator Workflow MVP.

This is the shortest path from “many strong foundations” to “a system the Product Owner can directly run and understand.” It also creates the acceptance harness needed to decide later features from real usage rather than architectural speculation.
