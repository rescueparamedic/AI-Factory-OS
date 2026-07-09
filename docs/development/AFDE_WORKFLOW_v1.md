# AFDE Workflow v1

## Standard Sprint Workflow

```text
User Request
↓
AFDE Task
↓
Workspace
↓
Planning
↓
Development
↓
QA
↓
Documentation
↓
Artifact Save
↓
Git Commit Candidate
↓
User Approval
```

## AFDE-1 Scope

AFDE-1 implements the local foundation only.

- Create task JSON
- Create workspace folders
- Save mock execution artifact
- Report provider configuration status
- Prepare Git commit command list

## Completion Criteria

AFDE-1 is complete when:

- `pytest tests/test_afde.py` passes
- `python -m afde.cli providers` works
- `python -m afde.cli run-mock ...` creates a report artifact

## Git Rule

Development is performed on `develop`.

After test PASS:

```powershell
git add .
git commit -m "Sprint-AFDE-1 foundation"
git push
```
