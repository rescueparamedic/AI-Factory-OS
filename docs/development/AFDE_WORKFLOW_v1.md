# AFDE Workflow v1

## Standard Sprint Workflow

Chat classifies every Sprint before implementation begins. The classification
determines whether Work is required.

### General Sprint

General Sprints include:

- extension of an existing Capability;
- Adapter or Provider implementation;
- UI, Presenter, or Projection work;
- Repository implementation that preserves the existing Contract;
- Persistence, tests, bug fixes, and documentation changes.

The default workflow is:

```text
Chat
↓
Codex
↓
Chat
↓
PowerShell
```

Work is not used for a General Sprint.

### Architecture Sprint

Architecture Sprints include:

- Runtime or Architecture changes;
- Public Contract or Repository Contract changes;
- a new Layer;
- Build vs Buy decisions;
- Open Source research;
- large-scale refactoring.

The workflow is:

```text
Chat
↓
Work
↓
Codex
↓
Chat
↓
PowerShell
```

Work is required only for the bounded audit or architecture review that
justifies the implementation direction.

## Collaboration Roles

### Chat

Chat:

- classifies the Sprint;
- decides whether Work is required;
- generates the Codex prompt;
- reviews the result;
- decides whether to approve merge.

### Work

Work is used only for:

- Repository Audit;
- Existing Capability Audit;
- Open Source Audit;
- Architecture Audit;
- Architecture Review.

Work does not implement, test, build, merge, synchronize `develop`, or clean
branches. It is not used for a General Sprint.

### Codex

Codex:

- implements the approved Sprint scope;
- runs tests and required validation;
- runs repository-defined builds;
- provides the final implementation report.

### PowerShell

After Chat approves merge, PowerShell:

- merges the approved pull request;
- synchronizes local `develop`;
- removes completed local and remote feature branches as authorized.

PowerShell does not replace Chat classification or approval, Work audits, or
Codex implementation and validation.

## Development Process

1. Chat receives the Sprint request and classifies it.
2. For a General Sprint, Chat sends the generated prompt directly to Codex.
3. For an Architecture Sprint, Work completes only the required audits or
   review, then Chat sends the bounded implementation prompt to Codex.
4. Codex implements, tests, builds, pushes the feature branch, and reports.
5. Chat reviews scope, diff, validation, and pull-request checks and decides
   whether merge is approved.
6. Only after that approval, PowerShell performs merge, `develop`
   synchronization, and authorized branch cleanup.

The previous default workflow is retired. There is no post-Codex Work stage
in either Sprint type.

## Historical AFDE-1 Scope

AFDE-1 implemented the local foundation only.

- Create task JSON
- Create workspace folders
- Save mock execution artifact
- Report provider configuration status
- Prepare Git commit command list

## Historical AFDE-1 Completion Criteria

AFDE-1 was complete when:

- `pytest tests/test_afde.py` passed
- `python -m afde.cli providers` worked
- `python -m afde.cli run-mock ...` created a report artifact

## Git Rule

Development changes are made on a dedicated `feature/*` branch based on
synchronized `develop`. Codex commits and pushes the validated change and
updates or opens a pull request targeting `develop`.

Merge is never automatic. Chat must explicitly approve merge before
PowerShell performs the merge, synchronizes `develop`, and cleans branches.
