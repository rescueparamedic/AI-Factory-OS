# AFDE-3.10 Sprint Plan — Operator Workflow MVP

Date: 2026-07-18
Base branch: `develop`
Required baseline: `0e5b9b3`
Feature branch: `feature/afde-3.10-operator-workflow-mvp`

## 1. Sprint goal

Integrate existing AFDE runtime, provider, approval, controlled execution, dashboard, and history capabilities into a minimal operator-facing workflow.

A user must be able to start a run, understand its current state, perform an approval decision when required, resume the run, and locate final evidence without knowing AFDE internals.

## 2. Product outcome

Canonical journey:

```text
Preflight
  -> Start run
  -> Runtime session created
  -> Work executes
  -> Completed
     OR approval required
       -> approve/reject
       -> resume
       -> completed/failed
  -> final summary + evidence paths
```

## 3. Deliverables

### D1. Operator workflow application service

Create a thin orchestration layer that composes existing services. It must not reimplement core runtime or approval rules.

Suggested module:

```text
src/afde/operator/
  __init__.py
  models.py
  preflight.py
  service.py
  presenter.py
  errors.py
```

Responsibilities:

- Validate request and execution mode.
- Run environment/repository/provider preflight.
- Start or attach to a runtime session.
- Delegate execution to the existing pipeline/runtime.
- Detect terminal state or approval-required state.
- Produce a stable operator result model.
- Generate exact next-action commands.

### D2. Operator CLI commands

Add:

```text
operator-preflight
operator-run
operator-status
operator-approve
operator-reject
operator-resume
```

Requirements:

- Human-readable default output.
- `--json` output where consistent with existing CLI conventions.
- Stable exit codes.
- No secret values in output.
- Every nonterminal result includes the exact next command.

### D3. Canonical operator result contract

Minimum fields:

```json
{
  "status": "completed|failed|waiting_approval|blocked|running",
  "session_id": "...",
  "request": "...",
  "provider": "mock|openai|...",
  "approval_id": null,
  "summary": "...",
  "next_action": null,
  "evidence": [],
  "dashboard_hint": "...",
  "history_hint": "..."
}
```

Use existing domain types where possible. Add only operator-specific projection models.

### D4. Preflight checks

At minimum:

- Python/runtime import viability.
- Repository/workspace path exists.
- Repository branch and dirty-state information.
- Provider availability.
- Explicit live API opt-in when applicable.
- Controlled execution permission compatibility.
- Runtime data directory writable.
- No credential values printed.

Preflight should distinguish:

```text
PASS
WARN
FAIL
```

Warnings do not block unless existing policy requires it.

### D5. End-to-end operator acceptance scenario

Add a deterministic mock scenario that:

1. Starts from CLI.
2. Creates a session.
3. Proposes exactly one controlled file write in a temporary workspace.
4. Reaches approval-required state when policy requires.
5. Approves and resumes.
6. Completes.
7. Confirms written file and evidence.
8. Confirms runtime history can retrieve the session.
9. Confirms dashboard projection can represent the session.

No network dependency for the required acceptance test.

### D6. Operator documentation

Create:

```text
docs/operations/AFDE_OPERATOR_QUICKSTART.md
docs/releases/AFDE_3_10_RELEASE_EVIDENCE.md   # after merge, per release process
```

Quickstart must include:

- Clean checkout preparation.
- Mock first run.
- Optional live-provider run.
- Approval/resume example.
- Dashboard/history inspection.
- Failure recovery.
- Exact PowerShell commands.

## 4. Implementation priority

| Priority | Work item | Rationale |
|---:|---|---|
| P0 | Operator result contract and service | Prevents CLI-only glue and output inconsistency |
| P0 | `operator-run`, `operator-status` | Establishes usable journey |
| P0 | Approval/reject/resume commands | Completes human decision loop |
| P0 | Deterministic acceptance test | Defines Alpha usability evidence |
| P1 | Preflight command | Reduces first-run failure and support burden |
| P1 | Human/JSON presenters and exit codes | Supports both owner and automation use |
| P1 | Quickstart | Makes the release independently usable |
| P2 | Minor dashboard hints/link output | Convenience only; no new dashboard architecture |

## 5. Acceptance criteria

### Functional

- `operator-preflight` reports checks without exposing secrets.
- `operator-run --provider mock` starts a session and returns a valid session ID.
- The operator can determine state using `operator-status`.
- An approval-required run returns approval ID, reason, proposed action, and exact next command.
- Approval and rejection are both supported.
- Approved runs can resume and reach a terminal state.
- Final output includes evidence and history inspection commands.

### Compatibility

- Existing runtime, dashboard, history, provider, approval, and controlled-execution tests remain green.
- Existing CLI commands retain behavior.
- Existing event/session files remain byte-invariant in read-only operations.
- Legacy event normalization remains unchanged unless a failing test proves a required correction.

### Safety

- Live provider requires existing explicit opt-in semantics.
- No automatic merge or deployment.
- No branch-destructive Git operations.
- No credential material is persisted in runtime events or terminal output.
- Workspace containment rules remain enforced.

### Quality gates

```text
python -m pytest
python -m compileall -q src tests
node --check <all changed JavaScript files, if any>
git diff --check
credential scan
focused operator tests
focused CLI regression
focused dashboard/runtime/history regression
canonical localhost smoke, if dashboard code changes
```

## 6. Test plan

Suggested test files:

```text
tests/test_operator_preflight.py
tests/test_operator_service.py
tests/test_operator_cli.py
tests/test_operator_acceptance.py
```

Required cases:

- Mock provider happy path.
- Missing/invalid request.
- Unknown provider.
- Live provider without explicit opt-in.
- Dirty repository reported, not silently modified.
- Approval required.
- Approval granted then resume.
- Approval rejected.
- Unknown session/approval ID.
- Already-terminal session.
- Idempotent status/read operations.
- JSON output schema.
- No secrets in output/events.
- Windows path handling.

## 7. Change constraints

- Prefer adapter/facade composition over core rewrites.
- Do not add a database.
- Do not introduce a new UI framework.
- Do not rename existing stable commands.
- Do not alter approval policy to make the demo easier.
- Do not auto-approve actions currently classified as manual approval.
- Do not broaden controlled execution permissions.

## 8. Git and delivery flow

```text
1. Confirm develop == origin/develop and baseline commit.
2. Create feature/afde-3.10-operator-workflow-mvp.
3. Implement service and tests.
4. Add CLI and acceptance coverage.
5. Add operator quickstart and changelog entry.
6. Run all quality gates.
7. Commit and push feature branch.
8. Open PR to develop.
9. Review evidence and merge with Merge Commit.
10. Create AFDE_3_10_RELEASE_EVIDENCE.md on develop.
11. Commit/push release evidence.
12. Delete local branch with safe delete and delete remote branch.
```

## 9. Definition of done

AFDE-3.10 is complete when the Product Owner can copy a documented PowerShell sequence and complete the canonical mock operator journey without manually invoking internal runtime subcommands or interpreting raw event files.
