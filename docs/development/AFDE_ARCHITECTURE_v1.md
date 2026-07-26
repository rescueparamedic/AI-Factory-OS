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

### Canonical Flow

The canonical responsibility order through AFDE-5.7 is:

```text
Planner
    |
    v
Planner Resolution
    |
    v
Capability Resolver
    |
    v
Operational Adapter Registry
    |
    v
Tool Adapter Catalog
    |
    v
Tool Adapter Selection
    |
    v
Execution Path
    |
    v
Runtime Integration
    |
    v
Tool Adapter Execution Contract
    |
    v
Worker
    |
    v
Evidence
    |
    v
Product Assembly
```

This flow defines responsibility and handoff order. AFDE-5.6 provides explicit
repeatable construction of the capability services through Tool Adapter
Execution Contract. AFDE-5.7 validates explicitly supplied registrations and
supplies the existing Catalog without discovery or execution. Neither
foundation implements the downstream production path into Worker, Evidence,
and Product Assembly.

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
status: implemented
maturity: M3
implementation_status: implemented
```

AFDE-4.8 implements the minimum read-only Knowledge Provider:

```text
Official Markdown source documents
        |
        v
Governed JSON Registry snapshot
        |
        v
Typed Loader -> Validator -> KnowledgeFoundationProvider
        |
        v
Resolver-ready CapabilityContext and explicit Gaps
```

Implementation is contained in `afde/knowledge/` and the governed snapshot is
`docs/registry/KNOWLEDGE_FOUNDATION_REGISTRY_v1.json`. The Provider does not
search Markdown, write files, select an implementation, call Runtime, or alter
Product Layer, Planner, Tool Adapter, or public contracts.

The Knowledge Foundation status does not claim operational integration, M4
validation, retrieval, vector database, embedding, or multimodal behavior.

### Capability Resolver Foundation

```yaml
capability_id: CAP-RESOLVER-0001
status: implemented
maturity: M3
implementation_status: implemented
```

AFDE-4.9 implements one deterministic read-only resolution boundary:

```text
Structured CapabilityRequirement
        |
        v
Injected Knowledge Provider -> CapabilityResolver
        |
        v
Immutable CapabilityResolutionResult
```

The Resolver evaluates one exact Capability ID against registered status,
implementation status, maturity, scope, required Knowledge, direct Capability
dependencies, gaps, and constraints. It returns resolved, unresolved, blocked,
or decision-required status with ordered rationale. It does not parse Registry
JSON, search Markdown, select a Tool Adapter or implementation path, invoke
Runtime, execute a Worker, change Planner output, or assemble a product.

AFDE-5.0 adds the isolated M3 Planner-to-Resolver composition:

```text
Structured Planner context + explicit CapabilityRequirement
        |
        v
PlannerResolutionService -> injected CapabilityResolver
        |
        v
Immutable PlannerCapabilityResolutionResult
```

The integration preserves the existing Planner and Resolver public contracts,
projects the Resolver status, gaps, source/reference details, and ordered
rationale, and always keeps Runtime disallowed. Natural-language requirement
extraction, multi-candidate discovery/ranking, Tool Adapter execution and
Runtime integration, operational Evidence, Product Assembly, and M4 validation
remain deferred.

### Tool Adapter Selection Foundation

```yaml
capability_id: CAP-TOOLSELECT-0001
status: implemented
maturity: M3
implementation_status: implemented
```

AFDE-5.1 adds one isolated application-level selection boundary:

```text
CapabilityResolutionResult or PlannerCapabilityResolutionResult
        |
        v
ToolAdapterSelectionService -> injected AdapterCandidateSource
        |
        v
Immutable ToolAdapterSelectionResult
```

The service requires a resolved eligible outcome, snapshots and sorts injected
adapter metadata by stable adapter ID, and selects only one exact Capability ID
match. No match is explicit and multiple authoritative matches block as
ambiguous. Resolver status, gaps, rejection reasons, source/reference details,
and ordered trace remain available in the result.

The selection policy performs no Registry or filesystem access, Provider or
network call, Runtime or Worker invocation, adapter execution, orchestration,
ranking, Evidence generation, or Product Assembly. `runtime_allowed` and
`execution_allowed` are always false. Concrete production registrations,
execution, fallback, and M4 validation remain deferred.

### Tool Adapter Catalog Foundation

```yaml
capability_id: CAP-TOOLCATALOG-0001
status: implemented
maturity: M3
implementation_status: implemented
```

AFDE-5.2 adds the governed read-only discovery boundary:

```text
Constructor-injected immutable ToolAdapterDescriptor values
        |
        v
ToolAdapterCatalog -> immutable snapshot and exact lookups
        |
        v
AdapterCandidateSource-compatible ToolAdapterCandidate projection
        |
        v
ToolAdapterSelectionService
```

Each Catalog instance is the Single Source of Truth for adapter discovery
metadata in its scope. The Knowledge Foundation Registry governs the Catalog
capability and normative standard but does not duplicate adapter rows.
Descriptors contain stable identity, semantic version, exact Capability IDs,
availability, Runtime compatibility, execution contract, privacy, cost,
credential requirement, description, and optional metadata references.

Catalog construction snapshots input, orders adapters and mappings
deterministically, rejects duplicate identities, and rejects multiple
selectable adapters mapped to one Capability. Exact lookup performs no fuzzy
or semantic matching. Unavailable, incompatible, unverified, or undeclared-
contract descriptors remain discoverable but are not Selection candidates.

Existing runtime adapters are not cataloged because they do not yet carry the
complete governed metadata contract. Catalog policy performs no Registry or
filesystem access, network or Provider call, Runtime or Worker invocation,
adapter execution, Evidence generation, Product Assembly, or orchestration.
Concrete production registrations, execution, external discovery, ranking,
fallback, credential storage, and M4 validation remain deferred.

### Execution Path Foundation

```yaml
capability_id: CAP-EXECPATH-0001
status: implemented
maturity: M3
implementation_status: implemented
```

AFDE-5.3 adds the structural application boundary after Tool Selection:

```text
Immutable ToolAdapterSelectionResult
        |
        v
ExecutionPathService -> injected exact Catalog metadata lookup
        |
        v
Immutable ExecutionPathResult + RuntimeHandoffProjection
        |
        v
future Runtime Integration capability
```

Execution Path validates unique Selection, resolved eligible state, exact
Catalog identity and Capability mapping, availability, Runtime compatibility,
and controlled execution contract. It preserves Resolver and Selection status,
gaps, rationale, references, and trace plus relevant Catalog metadata. Stable
path identity derives only from structured metadata.

`path_constructed` reports a structural route.
`runtime_handoff_ready` reports complete structural prerequisites. Neither is
authority: `runtime_allowed` and `execution_allowed` remain false. Required
credentials remain an explicit prerequisite without retrieval or authorization.

The boundary does not reuse Planner `ExecutionPlan`, which owns goal/task
planning, or executable Runtime lifecycle models. It performs no
Registry/file/network access, Provider call, Runtime or Worker invocation,
adapter/command/task/process execution, Evidence generation, Product Assembly,
or orchestration.

### Runtime Integration Foundation

```yaml
capability_id: CAP-RUNTIME-0001
status: implemented
maturity: M3
implementation_status: implemented
```

AFDE-5.4 adds a read-only application boundary:

```text
Immutable ExecutionPathResult
        |
        v
RuntimeIntegrationService + injected immutable policy
        |
        v
Immutable RuntimeIntegrationResult + RuntimeProjection
        |
        v
future executable Runtime capability
```

Only a constructed, handoff-ready Execution Path matching the injected
compatibility and contract policy produces `runtime_ready: true`. This state is
structural, not authority: `runtime_allowed` and `execution_allowed` remain
false. Projection identity derives only from stable path and metadata inputs.

The implementation does not reuse executable Beta or real-worker Runtime
models because they own lifecycle, Worker, Provider, orchestration,
persistence, and Evidence behavior. It imports or invokes none of those
surfaces. The AFDE-5.4 External Open-Source Audit found no justified dependency
for this small immutable projection; mature engines and infrastructure remain
reference candidates for later executable capabilities.

### Tool Adapter Execution Contract Foundation

```yaml
capability_id: CAP-TOOLADAPTER-CONTRACT-0001
status: implemented
maturity: M3
implementation_status: implemented
```

AFDE-5.5 adds a read-only validation boundary after Runtime Projection:

```text
Immutable RuntimeProjection
        |
        v
ToolAdapterContractService + injected AdapterLookup
        |
        v
Immutable ToolAdapterResult + ToolAdapterBinding or ToolAdapterError
        |
        v
future adapter execution capability
```

The boundary validates exact adapter identity and governed descriptor metadata,
rejecting malformed snapshots, duplicates, mismatches, and unregistered
identities. It preserves projection, path, Capability, and adapter IDs.
`runtime_allowed` and `execution_allowed` remain false.

The boundary exposes no adapter invocation method and imports no executable
Runtime, Worker, Provider, Product, Evidence, approval, credential, command,
process, filesystem, network, Desktop, Operator, or Beta Execute behavior.

### Non-executable Composition Foundation

```yaml
capability_id: CAP-COMPOSITION-0001
status: implemented
maturity: M3
implementation_status: implemented
```

AFDE-5.6 adds explicit constructor composition:

```text
caller-injected KnowledgeProvider
caller-injected ToolAdapterDescriptor values
caller-injected RuntimeIntegrationPolicy
        |
        v
build_non_executable_composition
        |
        v
frozen NonExecutableComposition
```

The builder constructs the existing Capability Resolver, Planner Resolution,
Tool Adapter Catalog, Tool Adapter Selection, Execution Path, Runtime
Integration, and Tool Adapter Contract services. Selection, Execution Path,
and Tool Adapter Contract share the same Catalog instance.

Construction invokes none of the service methods and performs no Registry,
filesystem, environment, configuration, Provider, Adapter, Runtime, Worker,
Evidence, Product, Operator, CLI, Desktop, network, or subprocess behavior.
The composition has no execution facade, identity, trace, dynamic plugin
container, or lifecycle API. Runtime and execution authority remain false.

### Operational Adapter Registry Foundation

```yaml
capability_id: CAP-ADAPTERREGISTRY-0001
status: implemented
maturity: M3
implementation_status: implemented
```

AFDE-5.7 adds one explicit non-executable registration front door:

```text
caller-injected ToolAdapterDescriptor registrations
        |
        v
OperationalAdapterRegistry
        |
        v
existing immutable ToolAdapterCatalog
        |
        v
existing Selection / Execution Path / Tool Adapter Contract services
```

The Registry reuses the existing descriptor validation, Catalog errors,
deterministic ordering, immutable Catalog snapshot, lookup, and candidate
projection. Empty registrations are valid. Duplicate adapter identities,
malformed descriptors, invalid Capability mappings, and ambiguous selectable
mappings fail closed.

Registration and Catalog projection perform no discovery, dynamic import,
adapter construction or invocation, availability probe, credential check,
filesystem, network, environment, configuration, Provider, Runtime, Worker,
Evidence, Operator, Product, or lifecycle behavior. Registered metadata does
not establish executable or operational availability, and M4 is not claimed.

### Normative Standards

- `docs/standards/DOCUMENT_KNOWLEDGE_MANAGEMENT_STANDARD_v1.md`
- `docs/standards/KNOWLEDGE_REGISTRY_STANDARD_v1.md`
- `docs/standards/CAPABILITY_REGISTRY_STANDARD_v1.md`
- `docs/standards/TOOL_ADAPTER_CATALOG_STANDARD_v1.md`
- `docs/standards/EXECUTION_PATH_STANDARD_v1.md`
- `docs/standards/RUNTIME_INTEGRATION_STANDARD_v1.md`
- `docs/standards/TOOL_ADAPTER_EXECUTION_CONTRACT_STANDARD_v1.md`
- `docs/standards/NON_EXECUTABLE_COMPOSITION_STANDARD_v1.md`
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
