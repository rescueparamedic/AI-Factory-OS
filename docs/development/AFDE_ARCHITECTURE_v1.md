# AFDE Architecture v1

## Purpose

AFDE, AI Factory Development Environment, is the development workspace layer inside AI Factory OS.

It exists to move the project from manual patch application to AI-assisted development execution.

## Core Modules

```text
afde/
├── task_runner.py
├── workspace_manager.py
├── artifact_manager.py
├── git_manager.py
├── prompt_manager.py
├── provider_manager.py
└── cli.py
```

## Responsibilities

| Module | Responsibility |
|---|---|
| Task Runner | Creates and executes development tasks |
| Workspace Manager | Creates isolated sprint workspaces |
| Artifact Manager | Saves reports, plans, generated code, and manifests |
| Git Manager | Reads Git status and prepares safe commit commands |
| Prompt Manager | Stores and renders prompt templates |
| Provider Manager | Reports OpenAI/Gemini/Claude/Mock configuration |

## Current Architecture Extension

The module list above records the original AFDE workspace foundation. Later
Sprints added the Product Layer, Operator application path, Planner,
RealWorkerRuntime, ToolAction boundary, controlled execution, approval,
Evidence, and product projection without replacing that foundation.

AFDE-4.7 adds the Knowledge Foundation architecture:

```text
Capability
    |
    v
Knowledge Foundation
    |
    v
Capability Resolver
    |
    v
Tool Adapter
    |
    v
Runtime
    |
    v
Evidence
    |
    v
Product Assembly
```

### Knowledge Foundation

Knowledge Foundation answers:

- which official repository documents exist;
- which registered knowledge is valid for a scope;
- which capabilities exist and their independent status, maturity, and
  implementation status;
- which source, knowledge, or capability has authority when several candidates
  exist;
- which repository material AI may use as an official reference;
- which Knowledge Gaps or Capability Gaps remain.

Knowledge Foundation owns governed Document, Knowledge, and Capability
Registry metadata. It does not replace repository Source of Record documents,
execute Runtime, select an implementation, invoke a Tool Adapter, or assemble a
product.

Capability Resolver remains responsible for choosing which eligible
implementation may satisfy a planned capability. Tool Adapter remains
responsible for tool-specific adaptation. Runtime remains responsible for
execution, approval, lifecycle, and Evidence. Product Layer remains responsible
for product coordination and Product Assembly.

### Knowledge Foundation Status

```yaml
capability_id: CAP-KNOW-0001
status: architecture_approved
maturity: M2
implementation_status: not_implemented
```

The status above does not claim a registry service, query API, Resolver,
retrieval system, vector database, embedding pipeline, or multimodal
implementation.

### Normative Standards

- `docs/standards/DOCUMENT_KNOWLEDGE_MANAGEMENT_STANDARD_v1.md`
- `docs/standards/KNOWLEDGE_REGISTRY_STANDARD_v1.md`
- `docs/standards/CAPABILITY_REGISTRY_STANDARD_v1.md`
- `docs/standards/DOCUMENT_GOVERNANCE_STANDARD_v1.md`
- `docs/standards/AI_REFERENCE_POLICY_v1.md`

### Architecture Invariants

- Registry metadata indexes but never replaces its Source of Record.
- Document existence, capability implementation, and validation are different
  facts.
- Capability status and maturity remain independent.
- Draft and Deprecated documents are not default official references.
- Every Active registry entry resolves to an official source document.
- Document and Registry changes are reviewed as one governance unit.
- Runtime and Product Layer public contracts remain unchanged.

## Safety Rule

AFDE-1 runs in local safe mode only.

It does not call paid APIs.
It does not push to GitHub automatically.
It does not delete project files.

## Historical Next Stage

The original AFDE-1 plan was to connect the AFDE runner to AI Factory OS CLI
and then to the real worker runtime. That evolution has since occurred through
later AFDE Sprints. This section is retained as historical context rather than
as the current roadmap.
