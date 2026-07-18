# AFDE-3.10 Release Evidence

## Release identity

- Release: AFDE-3.10 Operator Workflow MVP
- Feature branch: `feature/afde-3.10-operator-workflow-mvp`
- Base branch: `develop`
- Implementation commit: `3806ed5260b198aba141cd3e181d1b1dd065d881`
- Pull request: [#24 - AFDE-3.10 Operator Workflow MVP](https://github.com/rescueparamedic/AI-Factory-OS/pull/24)
- Release stage: pre-merge release candidate evidence
- Merge status: `OPEN` / unmerged

## Purpose

AFDE-3.10 provides an operator-facing workflow over the existing Runtime,
Provider, Approval Guardian, Controlled Execution, Runtime History, and Runtime
Dashboard components. An operator can perform preflight checks, start a guided
run, inspect status, approve or reject an exact action, resume execution, and
inspect persisted evidence through one coherent CLI journey.

## Architecture reuse

No new orchestration engine was introduced. The implementation reuses:

- RealWorkerRuntime;
- RuntimeSession and RuntimePipeline;
- ProviderBridge and ProviderManager;
- RuntimeApprovalStore and Approval Guardian;
- ControlledExecutor and existing workspace containment;
- RuntimeHistoryStore;
- RuntimeDashboard;
- the existing deterministic mock approval-resume flow.

Exact approval recording and execution resume are exposed as separate operator
steps. The existing approve-and-resume Runtime API remains backward compatible,
and resume continues to enforce policy, context, action, preimage, and
single-use approval validation.

## Implemented commands

- `operator-preflight`
- `operator-run`
- `operator-status`
- `operator-approve`
- `operator-reject`
- `operator-resume`

Operator exit codes are:

- `0`: successful command;
- `2`: invalid input;
- `3`: preflight blocked;
- `4`: session or approval not found;
- `5`: execution failed.

Waiting and blocked results provide an exact next command containing the
session ID, approval ID when applicable, and governed workspace.

## Changed scope

The implementation commit changed 16 files with 1,269 insertions and 10
deletions:

- six new modules in the `afde/operator` application layer;
- `afde/cli.py`;
- two Runtime approval/resume compatibility files;
- four focused Operator test files;
- `docs/operations/AFDE_OPERATOR_QUICKSTART.md`;
- `README.md`;
- `CHANGELOG.md`.

This evidence document is a separate documentation-only PR update and is not
included in the implementation statistics above.

## Acceptance smoke evidence

A complete network-free CLI smoke flow ran in a temporary Git workspace.

- Preflight result: `WARN`
- Preflight blocking: `false`
- Session: `RWS-20260718-171600-57bde4`
- Initial status: `waiting_approval`
- Approval: `APR-dacd059461334ad0947ce4d2c36f9567`
- Status after approve: `waiting_approval`
- Status after resume: `completed`
- Approved target: `tests/fixtures/afde_2_7_approval_target.txt`
- Final content: `approval_state=approved`
- Evidence count: 7
- Runtime history event count: 70
- Dashboard projection: successful and read-only
- Evidence workspace:
  `C:\tmp\afde310-smoke-b6afeedcf76a49fe8091d7d41a5c2586\data\runtime_sessions\RWS-20260718-171600-57bde4`

The exact waiting response directed the operator to:

```powershell
python -m afde.cli operator-approve --session-id RWS-20260718-171600-57bde4 --approval-id APR-dacd059461334ad0947ce4d2c36f9567 --workspace "C:\tmp\afde310-smoke-b6afeedcf76a49fe8091d7d41a5c2586"
```

The approved response then directed the operator to:

```powershell
python -m afde.cli operator-resume --session-id RWS-20260718-171600-57bde4 --workspace "C:\tmp\afde310-smoke-b6afeedcf76a49fe8091d7d41a5c2586"
```

A separate rejection flow used session
`RWS-20260718-171606-c62302`, finished as `blocked`, and did not apply the
proposed file write.

## Test evidence

- Full pytest: 600 passed, 1 skipped.
- Focused Runtime, CLI, Approval, Controlled Execution, History, Dashboard, and
  Provider regression: 336 passed.
- Final Operator focused suite: 15 passed.
- `python -m compileall -q afde real_worker_runtime approval_guardian tests`:
  passed.
- `git diff --check`: passed.
- CLI registration smoke: passed.
- JavaScript changes: none.
- Skipped test: the existing explicitly opted-in paid OpenAI live test.

The repository uses top-level `afde`, `real_worker_runtime`, and
`approval_guardian` packages rather than a `src` directory, so compilation was
adapted to the actual package layout.

## Security evidence

- High-confidence credential scan: no matches.
- New external-network usage scan: no matches.
- Live providers require both API configuration and `--allow-live-api`.
- Approval policy validation retained.
- Context fingerprint validation retained.
- Action fingerprint validation retained.
- Preimage validation retained.
- Single-use approval consumption retained.
- Workspace containment retained.
- Operator request credential redaction applied before Runtime persistence.

## Read-only invariance

SHA-256 values were captured before and after Operator status, Runtime History,
and Runtime Dashboard reads:

- `session.json`: unchanged;
- `events.jsonl`: unchanged.

Runtime History and Runtime Dashboard therefore remain read-only projections and
do not mutate Runtime persistence during operator inspection.

## Repository hygiene

The following pre-existing untracked paths are excluded from AFDE-3.10 changes:

- `AFDE_2_2_UPDATE_PACKAGE/`
- `SPRINT_AFDE_2_6_REAL_AI_PROVIDER_CODEX_INSTRUCTION.md`

They were not modified, deleted, moved, or staged.

## Pull request evidence

State verified immediately before this evidence update:

- PR: #24
- Title: AFDE-3.10 Operator Workflow MVP
- State: `OPEN`
- Draft: `false`
- Base: `develop`
- Head: `feature/afde-3.10-operator-workflow-mvp`
- Implementation head SHA:
  `3806ed5260b198aba141cd3e181d1b1dd065d881`
- Mergeability: `MERGEABLE`
- Merge state: `CLEAN`
- Registered GitHub checks: none
- Merged at: not set

The documentation-only evidence commit becomes the new PR head after push. Its
exact SHA and the final GitHub PR state are recorded in the delivery report for
this update.

## Known limitations

- Mock workflow uses the existing deterministic approval fixture.
- Live providers may incur cost and external communication and remain explicit
  opt-in.
- This sprint adds no database, dependency, provider adapter, web framework,
  hosted service, automatic merge, deployment, tag, or release.
- GitHub checks are not configured for this branch/repository; local validation
  is the primary verification evidence.

## Decision boundary

This document records pre-merge release-candidate evidence. It does not
authorize or perform PR merge, direct `develop` changes, release tagging,
deployment, branch deletion, or any approval-policy relaxation. PR #24 remains
subject to separate user approval before merge.
