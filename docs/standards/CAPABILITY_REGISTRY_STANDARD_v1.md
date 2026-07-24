# Capability Registry Standard v1

## Status

- Standard ID: `STD-CREG-0001`
- Status: Active
- Owner: AI Factory OS Architecture
- Effective Sprint: AFDE-4.7

## Capability Definition

A capability is a named ability the system can provide or is designed to
provide under explicit knowledge, capability, tool, adapter, Runtime,
validation, and governance dependencies.

A capability entry is discovery and lifecycle metadata. It is not executable
authority and does not prove implementation.

## Capability ID

Capability IDs use:

```text
CAP-<DOMAIN>-<four-digit sequence>
```

IDs are immutable and never reused. Provider- or tool-specific names do not
belong in the ID when multiple adapters may satisfy the same capability.

## Capability Entry Schema

| Field | Required | Meaning |
| --- | --- | --- |
| `capability_id` | yes | Stable Capability ID |
| `name` | yes | Human-readable name |
| `description` | yes | Bounded responsibility |
| `owner` | yes | Accountable architecture or implementation owner |
| `scope` | yes | Applicability boundary |
| `status` | yes | Capability lifecycle status |
| `maturity` | yes | Independent maturity level |
| `implementation_status` | yes | Implementation truth |
| `required_knowledge` | yes | Knowledge IDs required before use |
| `required_capabilities` | yes | Capability dependency IDs |
| `tool_dependencies` | yes | Abstract tool requirements |
| `adapter_dependencies` | yes | Adapter contract or implementation references |
| `runtime_dependencies` | yes | Runtime contracts required for execution |
| `implementation_references` | yes | Repository paths or an empty list |
| `validation_evidence` | yes | Evidence references or an empty list |
| `known_gaps` | yes | Explicit unresolved gaps |
| `source_documents` | yes | Official architecture or standard sources |
| `supersedes` | yes | Replaced capability IDs, or an empty list |

## Capability Status

Allowed lifecycle values:

```text
proposed
defined
architecture_approved
implementation_in_progress
implemented
validated
operational
deprecated
retired
```

Status describes lifecycle position. Transitions require evidence appropriate
to the destination:

- `defined` requires an owner, scope, and responsibility;
- `architecture_approved` requires approved architecture and dependencies;
- `implemented` requires implementation references;
- `validated` requires validation evidence;
- `operational` requires approved operational evidence;
- `deprecated` requires a replacement or migration explanation;
- `retired` prohibits selection for new work.

## Capability Maturity

| Level | Name | Meaning |
| --- | --- | --- |
| M0 | Concept | Candidate idea |
| M1 | Defined | Responsibility and scope are defined |
| M2 | Designed | Architecture and dependency contracts are approved |
| M3 | Implemented | Repository implementation exists |
| M4 | Validated | Expected behavior is verified |
| M5 | Reusable | Reuse contract and operating guidance are proven |
| M6 | Autonomous-ready | Governed autonomous use is explicitly approved |

Maturity does not replace lifecycle status. Neither field is inferred from the
other.

## Implementation Status

Allowed values:

- `not_implemented`
- `partially_implemented`
- `implemented`
- `not_applicable`

Only repository implementation and Evidence may advance implementation truth.
A document, registry entry, test plan, or architecture approval alone cannot.

## Dependency Rules

- `required_knowledge` must resolve to Active Knowledge Registry entries.
- `required_capabilities` must resolve without cycles.
- Tool, Adapter, and Runtime dependencies must name the owning contract rather
  than grant direct execution authority.
- The Capability Resolver foundation may evaluate only registered eligible
  capabilities. Multiple-candidate discovery, implementation ranking, and Tool
  Adapter selection require a future approved Sprint.
- Runtime remains responsible for execution, lifecycle, approval, and Evidence.
- Known gaps remain visible and fail closed where a required dependency cannot
  be established.

## Initial Capability Entry

### CAP-KNOW-0001

| Field | Value |
| --- | --- |
| Name | Knowledge Foundation |
| Description | Index official documents, validate knowledge and capability metadata, resolve reference authority, and expose knowledge or capability gaps |
| Owner | AI Factory OS Architecture |
| Scope | `architecture.knowledge_foundation` |
| Status | `implemented` |
| Maturity | `M3` |
| Implementation status | `implemented` |
| Required knowledge | `KNW-KNOW-0001`, `KNW-KNOW-0002`, `KNW-KNOW-0003` |
| Required capabilities | none |
| Tool dependencies | none |
| Adapter dependencies | none |
| Runtime dependencies | none |
| Implementation references | `afde/knowledge/`, `docs/registry/KNOWLEDGE_FOUNDATION_REGISTRY_v1.json` |
| Validation evidence | AFDE-4.8 focused tests and full repository regression |
| Known gaps | Tool Adapter implementation, operational integration, and M4 validation remain deferred |
| Source documents | `DOC-ARCH-0001`, `DOC-ARCH-0002`, `DOC-DKM-0001`, `DOC-KREG-0001`, `DOC-CREG-0001`, `DOC-DGOV-0001`, `DOC-AIREF-0001` |
| Supersedes | none |

This entry records the minimum read-only Knowledge Provider implementation. It
does not claim Tool Adapter or Runtime integration, operational use, or M4.

### CAP-RESOLVER-0001

| Field | Value |
| --- | --- |
| Name | Capability Resolver |
| Description | Evaluate a structured capability requirement against Knowledge Provider metadata and return deterministic eligibility, gaps, and rationale |
| Owner | AI Factory OS Architecture |
| Scope | `architecture.knowledge_foundation.resolver` |
| Status | `implemented` |
| Maturity | `M3` |
| Implementation status | `implemented` |
| Required knowledge | `KNW-KNOW-0001`, `KNW-KNOW-0002`, `KNW-KNOW-0003` |
| Required capabilities | `CAP-KNOW-0001` |
| Tool dependencies | none |
| Adapter dependencies | none |
| Runtime dependencies | none |
| Implementation references | `afde/resolver/` |
| Validation evidence | AFDE-4.9 focused tests and full repository regression |
| Known gaps | Planner, Tool Adapter, and Runtime integration; multiple-candidate discovery/ranking; operational Evidence; M4 validation |
| Source documents | `DOC-ARCH-0001`, `DOC-ARCH-0002`, `DOC-CREG-0001` |
| Supersedes | none |

This entry records exact-ID eligibility resolution over an injected read-only
Knowledge Provider. It does not select an adapter or implementation, execute a
tool or Runtime, alter Planner output, or claim operational validation.

### CAP-TOOLSELECT-0001

| Field | Value |
| --- | --- |
| Name | Tool Adapter Selection |
| Description | Select one Tool Adapter identity by exact Capability ID from an injected authoritative candidate snapshot |
| Owner | AI Factory OS Architecture |
| Scope | `architecture.tool_adapter_selection` |
| Status | `implemented` |
| Maturity | `M3` |
| Implementation status | `implemented` |
| Required knowledge | none |
| Required capabilities | `CAP-PLANRES-0001` |
| Tool dependencies | none |
| Adapter dependencies | injected read-only `AdapterCandidateSource` contract |
| Runtime dependencies | none |
| Implementation references | `afde/tool_selection/` |
| Validation evidence | AFDE-5.1 focused tests and full repository regression |
| Known gaps | operational adapter catalog and execution contract; Runtime, Worker, Provider, Evidence, and Product Assembly integration; M4 validation |
| Source documents | `DOC-ARCH-0001`, `DOC-ARCH-0002`, `DOC-CREG-0001` |
| Supersedes | none |

This entry records selection only. Registry metadata and selection results grant
no execution authority. Candidate discovery/ranking, adapter execution,
fallback, Runtime integration, operational Evidence, and M4 remain deferred.

### CAP-TOOLCATALOG-0001

| Field | Value |
| --- | --- |
| Name | Tool Adapter Catalog |
| Description | Provide immutable Tool Adapter discovery metadata and exact Capability mappings through the existing candidate-source boundary |
| Owner | AI Factory OS Architecture |
| Scope | `architecture.tool_adapter_catalog` |
| Status | `implemented` |
| Maturity | `M3` |
| Implementation status | `implemented` |
| Required knowledge | none |
| Required capabilities | none |
| Tool dependencies | none |
| Adapter dependencies | `ToolAdapterCandidate` projection and `AdapterCandidateSource` contract |
| Runtime dependencies | none |
| Implementation references | `afde/tool_catalog/` |
| Validation evidence | AFDE-5.2 focused tests and full repository regression |
| Known gaps | operational adapter descriptors, execution, external discovery, Runtime/Worker/Provider/Evidence/Product integration, and M4 |
| Source documents | `DOC-ARCH-0001`, `DOC-ARCH-0002`, `DOC-CREG-0001`, `DOC-TCAT-0001` |
| Supersedes | none |

The Catalog instance, not the Knowledge Registry, is the Single Source of Truth
for adapter discovery metadata in its scope. The Registry governs capability
and document lifecycle only. Catalog metadata grants no execution authority.

### CAP-EXECPATH-0001

| Field | Value |
| --- | --- |
| Name | Execution Path Foundation |
| Description | Construct a deterministic, immutable, non-executable path from one Selection result and exact injected Catalog metadata |
| Owner | AI Factory OS Architecture |
| Scope | `architecture.execution_path` |
| Status | `implemented` |
| Maturity | `M3` |
| Implementation status | `implemented` |
| Required knowledge | none |
| Required capabilities | `CAP-TOOLSELECT-0001`, `CAP-TOOLCATALOG-0001` |
| Tool dependencies | none |
| Adapter dependencies | immutable `ToolAdapterSelectionResult` and exact `ToolAdapterDescriptor` lookup |
| Runtime dependencies | none |
| Implementation references | `afde/execution_path/` |
| Validation evidence | AFDE-5.3 focused tests and full repository regression |
| Known gaps | Runtime Integration authorization and invocation; operational Worker, adapter, credential, Evidence, and Product Assembly integration; M4 validation |
| Source documents | `DOC-ARCH-0001`, `DOC-ARCH-0002`, `DOC-CREG-0001`, `DOC-EXEP-0001` |
| Supersedes | none |

This entry records structural path construction and handoff readiness only.
`runtime_allowed` and `execution_allowed` remain false. Actual Runtime handoff,
authorization, adapter invocation, credential access, and operational Evidence
belong to a future separately governed capability.

### CAP-RUNTIME-0001

| Field | Value |
| --- | --- |
| Name | Runtime Integration Foundation |
| Description | Project one structurally ready Execution Path into deterministic immutable Runtime-ready metadata without execution authority |
| Owner | AI Factory OS Architecture |
| Scope | `architecture.runtime_integration` |
| Status | `implemented` |
| Maturity | `M3` |
| Implementation status | `implemented` |
| Required knowledge | none |
| Required capabilities | `CAP-EXECPATH-0001` |
| Tool dependencies | none |
| Adapter dependencies | immutable `ExecutionPathResult` and constructor-injected `RuntimeIntegrationPolicy` |
| Runtime dependencies | none |
| Implementation references | `afde/runtime_integration/` |
| Validation evidence | AFDE-5.4 focused tests and full repository regression |
| Known gaps | Runtime session creation, execution, lifecycle mutation, Worker/adapter/Provider/Evidence/Product integration, orchestration, and M4 |
| Source documents | `DOC-ARCH-0001`, `DOC-ARCH-0002`, `DOC-CREG-0001`, `DOC-RUNTIME-0001` |
| Supersedes | none |

This entry records readiness projection only. `runtime_ready` is structural;
`runtime_allowed` and `execution_allowed` remain false. Existing executable
Runtime contracts remain unchanged and isolated.

## Registry Validation

A capability registry change is valid only when:

1. the ID, status, maturity, and implementation status are valid;
2. the owner, scope, and official sources are present;
3. all required Knowledge and Capability IDs resolve;
4. dependency graphs are acyclic;
5. implementation claims have repository references;
6. validation and operational claims have durable Evidence;
7. deprecated entries identify migration or replacement;
8. changed source documents and affected registry entries are reviewed in the
   same governance unit;
9. no entry grants execution, approval, merge, deployment, or publication
   authority.

## Known Architecture Gaps

- Tool Adapter execution Contract remains a future architecture item.
- Governed operational adapter population remains deferred.
- Runtime execution and lifecycle integration remain deferred.
- Multiple-candidate discovery and ranking remain deferred.
- M4 validation and operational integration are not complete.
- RAG, vector databases, embeddings, and multimodal adapters are outside
  AFDE-5.4.
