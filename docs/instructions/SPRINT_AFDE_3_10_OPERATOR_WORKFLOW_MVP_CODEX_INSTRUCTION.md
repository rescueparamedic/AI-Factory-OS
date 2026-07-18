# Codex Instruction — AFDE-3.10 Operator Workflow MVP

You are implementing AFDE-3.10 in the AI Factory OS repository.

## Mission

Build a minimal operator-facing workflow over the existing AFDE components. The goal is not to expand the platform. The goal is to make the current system directly usable through a coherent CLI journey.

## Repository and baseline

Repository:

```text
https://github.com/rescueparamedic/AI-Factory-OS
```

Required starting branch and commit:

```text
develop
0e5b9b3
```

Previous release evidence:

```text
docs/releases/AFDE_3_9_RELEASE_EVIDENCE.md
```

Create:

```text
feature/afde-3.10-operator-workflow-mvp
```

Do not proceed from a different baseline. If local `develop` is not aligned with `origin/develop`, report the discrepancy and stop before modifying files.

## Mandatory safety rules

Do not use:

```text
git reset --hard
git clean
git push --force
git branch -D
```

Maintain fast-forward-only synchronization. Do not merge the PR. Do not modify unrelated untracked files. Do not expose credentials. Do not weaken approval or workspace containment policies.

## First action: repository reconnaissance

Before implementation, inspect and summarize:

1. Existing CLI registration and output conventions.
2. Runtime pipeline/session APIs.
3. Approval store/service and approve/reject/resume behavior.
4. Provider registry and live API opt-in checks.
5. Controlled execution service and workspace containment.
6. Runtime history/event stream APIs.
7. Dashboard projection/start commands.
8. Existing factory demo or end-to-end orchestration that can be reused.
9. Existing result/error models and exit-code conventions.

Do not create duplicate orchestration if an existing facade can be extended.

## Required implementation

### 1. Operator package

Add a thin application layer, adapting paths to the repository's actual package structure:

```text
src/afde/operator/__init__.py
src/afde/operator/models.py
src/afde/operator/preflight.py
src/afde/operator/service.py
src/afde/operator/presenter.py
src/afde/operator/errors.py
```

If equivalent modules already exist, extend them rather than creating parallel abstractions.

The operator layer must delegate to existing runtime, provider, approval, controlled execution, history, and dashboard components.

### 2. Operator result model

Implement a stable projection containing at least:

```text
status
session_id
request
provider
approval_id
summary
next_action
evidence
dashboard_hint
history_hint
```

Allowed statuses:

```text
running
waiting_approval
blocked
completed
failed
```

Do not replace existing internal state enums. Normalize them only at the operator boundary.

### 3. Preflight

Implement checks for:

- AFDE import/runtime availability.
- Workspace/repository existence.
- Repository branch and dirty status, read-only.
- Provider availability.
- Explicit live-provider opt-in.
- Controlled execution compatibility.
- Runtime data path writability.
- Credential-safe output.

Return PASS/WARN/FAIL records and a summarized blocking result.

### 4. CLI commands

Integrate with existing `python -m afde.cli` command registration:

```text
operator-preflight
operator-run
operator-status
operator-approve
operator-reject
operator-resume
```

Follow existing argument style. At minimum support:

```text
operator-preflight [--provider PROVIDER] [--workspace PATH] [--json]
operator-run --request TEXT [--provider mock] [--workspace PATH] [existing live opt-in flags] [--json]
operator-status --session-id ID [--json]
operator-approve --session-id ID --approval-id ID [--json]
operator-reject --session-id ID --approval-id ID --reason TEXT [--json]
operator-resume --session-id ID [--json]
```

Use current provider and execution flags rather than introducing incompatible duplicates.

Every waiting/blocked response must print the exact next command. Every completed/failed response must print evidence and history inspection hints.

### 5. Exit codes

Use or extend existing conventions. Required semantic distinction:

```text
0 = successful command / completed read or mutation
2 = invalid CLI input
3 = preflight blocked
4 = session or approval not found
5 = execution failed
```

If the repository already defines different stable codes, preserve them and document the mapping instead of breaking compatibility.

### 6. Canonical deterministic acceptance flow

Implement a network-free mock acceptance test in a temporary workspace:

1. Run operator preflight.
2. Start an operator run.
3. Create a runtime session.
4. Propose exactly one controlled file write.
5. Reach approval-required state where dictated by current policy.
6. Approve.
7. Resume.
8. Reach completed state.
9. Assert target file contents.
10. Assert evidence exists.
11. Assert runtime history returns the session.
12. Assert dashboard projection can represent the session without mutating event/session bytes.

Do not bypass approval policy in the test. Configure the proposed action so the existing policy naturally exercises the desired path.

### 7. Tests

Add focused tests, adapting names to existing layout:

```text
tests/test_operator_preflight.py
tests/test_operator_service.py
tests/test_operator_cli.py
tests/test_operator_acceptance.py
```

Cover:

- Mock happy path.
- Request validation.
- Unknown provider.
- Live provider without opt-in.
- Repository dirty-state reporting.
- Waiting approval projection.
- Approve/resume.
- Reject path.
- Unknown session and approval.
- Already terminal session.
- JSON result contract.
- Secret redaction.
- Windows path semantics.
- Read-only status/history byte invariance.

### 8. Documentation

Create:

```text
docs/operations/AFDE_OPERATOR_QUICKSTART.md
```

Update only relevant existing docs, likely:

```text
README.md
CHANGELOG.md
```

Quickstart must use PowerShell and contain copy-ready commands for:

- Environment preparation.
- Mock preflight and first run.
- Status.
- Approval/rejection and resume.
- Dashboard/history inspection.
- Optional live-provider mode with explicit opt-in.
- Common recovery cases.

Do not create release evidence before PR merge. Release evidence is a post-merge task.

## Non-goals

Do not implement:

- SQLite migration.
- New web UI framework.
- Hosted dashboard.
- Parallel multi-agent execution.
- New provider adapters unless a minimal correction is essential.
- Automatic PR merge or deployment.
- Approval policy relaxation.
- General architecture refactoring.

## Validation gates

Run all repository-standard checks plus:

```powershell
python -m pytest
python -m compileall -q src tests
git diff --check
```

Run JavaScript syntax checks if any JavaScript changes.

Run credential scanning using the repository's established command/pattern.

Run focused suites for:

```text
operator
CLI
runtime
approval
controlled execution
history
dashboard
provider
```

Verify read-only operator status/history/dashboard operations do not mutate session or event bytes.

## Manual smoke evidence

Provide captured output for a complete mock flow. The report must include:

```text
preflight result
operator-run command
session ID
waiting approval output, if applicable
approval ID
approve command
resume command
completed output
written file path/content summary
evidence paths
history command/output summary
dashboard projection smoke summary
```

Also demonstrate one failure or reject path.

## Git delivery

After all checks pass:

1. Review `git status --short` and changed files.
2. Run `git diff --check`.
3. Commit with a focused message, for example:

```text
feat(operator): add guided development workflow MVP
```

4. Push the feature branch.
5. Open a PR to `develop` titled:

```text
AFDE-3.10 Operator Workflow MVP
```

6. Do not merge.

## Final Codex report format

Return exactly these sections:

```text
Summary
Architecture reuse
Changed files
CLI commands
Acceptance flow
Tests and validation
Security and invariance
Git status
Commit
PR
Risks or follow-ups
```

Include exact test counts, commit SHA, PR URL, PR state, mergeability, base/head branches, and confirmation that the PR remains open and unmerged.
