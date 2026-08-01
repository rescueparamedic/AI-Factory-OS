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
CAP-<DOMAIN SEGMENT>[-<DOMAIN SEGMENT>...]-<four-digit sequence>
```

Domain segments use uppercase alphanumeric characters. IDs are immutable and
never reused. Provider- or tool-specific names do not belong in the ID when
multiple adapters may satisfy the same capability.

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
  capabilities. Exact Tool Adapter selection is implemented separately;
  multiple-candidate discovery and implementation ranking remain deferred.
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
| Known gaps | operational Tool Adapter execution, production composition, and M4 validation remain deferred |
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
| Known gaps | AFDE-5.x production composition, multiple-candidate discovery/ranking, operational Evidence, and M4 validation |
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
| Known gaps | Concrete production Adapter registrations, adapter execution, production contract use, Worker, Provider, Evidence, Product Assembly, and M4 validation |
| Source documents | `DOC-ARCH-0001`, `DOC-ARCH-0002`, `DOC-CREG-0001` |
| Supersedes | none |

This entry records selection only. Registry metadata and selection results grant
no execution authority. Candidate discovery/ranking, adapter execution,
fallback, production composition, operational Evidence, and M4 remain deferred.

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
| Known gaps | Concrete production Adapter registrations, execution, external discovery, production composition, Worker/Provider/Evidence/Product integration, and M4 |
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
`runtime_allowed` and `execution_allowed` remain false. Runtime handoff
authority, adapter invocation, credential access, and operational Evidence
remain deferred to separately governed executable capabilities.

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

### CAP-TOOLADAPTER-CONTRACT-0001

| Field | Value |
| --- | --- |
| Name | Tool Adapter Execution Contract Foundation |
| Description | Validate one Runtime Projection against constructor-injected read-only adapter metadata and produce deterministic immutable binding metadata without execution authority. |
| Owner | AI Factory OS Architecture |
| Scope | `architecture.tool_adapter_contract` |
| Status | `implemented` |
| Maturity | `M3` |
| Implementation status | `implemented` |
| Required knowledge | none |
| Required capabilities | `CAP-RUNTIME-0001`, `CAP-TOOLCATALOG-0001` |
| Tool dependencies | none |
| Adapter dependencies | `RuntimeProjection`, constructor-injected `AdapterLookup` |
| Runtime dependencies | none |
| Implementation references | `afde/tool_adapter_contract/errors.py`, `afde/tool_adapter_contract/models.py`, `afde/tool_adapter_contract/service.py` |
| Validation evidence | `tests/test_tool_adapter_contract.py`, `tests/test_tool_adapter_contract_boundaries.py` |
| Known gaps | Adapter and Worker execution remain deferred.<br>Runtime session, Provider, Evidence, approval, credential, lifecycle, Product Assembly, Desktop, Operator, and Beta Execute integration remain deferred.<br>Operational Evidence and M4 validation are not complete. |
| Source documents | `DOC-ARCH-0001`, `DOC-ARCH-0002`, `DOC-CREG-0001`, `DOC-TOOLCONTRACT-0001` |
| Supersedes | none |

This entry records deterministic non-executable binding validation between
Runtime Projection and Tool Adapter. It preserves projection, path,
Capability, and adapter identity while `runtime_allowed` and
`execution_allowed` remain false. Adapter and Worker execution remain
deferred.

### CAP-COMPOSITION-0001

| Field | Value |
| --- | --- |
| Name | Non-executable Composition Foundation |
| Description | Construct the existing Planner Resolution, Capability Resolver, Tool Adapter Catalog, Tool Adapter Selection, Execution Path, Runtime Integration, and Tool Adapter Execution Contract services without executing behavior. |
| Owner | AI Factory OS Architecture |
| Scope | `architecture.non_executable_composition` |
| Status | `implemented` |
| Maturity | `M3` |
| Implementation status | `implemented` |
| Required knowledge | none |
| Required capabilities | `CAP-PLANRES-0001`, `CAP-TOOLSELECT-0001`, `CAP-TOOLCATALOG-0001`, `CAP-EXECPATH-0001`, `CAP-RUNTIME-0001`, `CAP-TOOLADAPTER-CONTRACT-0001` |
| Tool dependencies | none |
| Adapter dependencies | caller-injected `KnowledgeProvider`, caller-injected `ToolAdapterDescriptor` values, caller-injected `RuntimeIntegrationPolicy` |
| Runtime dependencies | none |
| Implementation references | `afde/non_executable_composition/__init__.py`, `afde/non_executable_composition/models.py`, `afde/non_executable_composition/factory.py` |
| Validation evidence | `tests/test_non_executable_composition.py`, `tests/test_non_executable_composition_boundaries.py` |
| Known gaps | Executable production composition and concrete production Adapter registrations remain deferred.<br>Worker, Evidence, Product Assembly, Runtime session, Provider, credential, and lifecycle integration remain deferred.<br>Operational Evidence and M4 validation are not complete. |
| Source documents | `DOC-ARCH-0001`, `DOC-ARCH-0002`, `DOC-CREG-0001`, `DOC-COMPOSITION-0001` |
| Supersedes | none |

This entry records explicit construction only. It does not grant execution
authority or call the constructed services. The caller owns all injected
dependencies, and `runtime_allowed` and `execution_allowed` remain false.

### CAP-ADAPTERREGISTRY-0001

| Field | Value |
| --- | --- |
| Name | Operational Adapter Registry Foundation |
| Description | Validate explicitly supplied Tool Adapter registrations and expose one deterministic immutable snapshot and the existing Tool Adapter Catalog without discovery or execution. |
| Owner | AI Factory OS Architecture |
| Scope | `architecture.operational_adapter_registry` |
| Status | `implemented` |
| Maturity | `M3` |
| Implementation status | `implemented` |
| Required knowledge | none |
| Required capabilities | `CAP-TOOLCATALOG-0001` |
| Tool dependencies | none |
| Adapter dependencies | caller-injected `ToolAdapterDescriptor` registrations, existing `ToolAdapterCatalog` projection |
| Runtime dependencies | none |
| Implementation references | `afde/operational_adapter_registry/__init__.py`, `afde/operational_adapter_registry/registry.py` |
| Validation evidence | `tests/test_operational_adapter_registry.py`, `tests/test_operational_adapter_registry_boundaries.py` |
| Known gaps | Adapter discovery, import, instantiation, invocation, availability validation, and concrete production registrations remain deferred.<br>Executable composition and Runtime, Worker, Evidence, Operator, Product Assembly, credential, and lifecycle integration remain deferred.<br>Operational Evidence and M4 validation are not complete. |
| Source documents | `DOC-ARCH-0001`, `DOC-CREG-0001` |
| Supersedes | none |

This entry records registration validation and Catalog supply only. Registered
metadata does not guarantee that an adapter is executable, reachable, healthy,
credential-ready, or operationally available.

### CAP-PRODUCTIONCOMPOSITION-0001

| Field | Value |
| --- | --- |
| Name | Production Composition Foundation |
| Description | Compose the existing non-executable AFDE services with the authoritative Catalog supplied by the Operational Adapter Registry without binding or executing adapters. |
| Owner | AI Factory OS Architecture |
| Scope | `architecture.production_composition` |
| Status | `implemented` |
| Maturity | `M3` |
| Implementation status | `implemented` |
| Required knowledge | none |
| Required capabilities | `CAP-COMPOSITION-0001`, `CAP-ADAPTERREGISTRY-0001` |
| Tool dependencies | none |
| Adapter dependencies | caller-injected `KnowledgeProvider`, `OperationalAdapterRegistry`, and `RuntimeIntegrationPolicy`; Registry-projected existing `ToolAdapterCatalog` |
| Runtime dependencies | none |
| Implementation references | `afde/production_composition/__init__.py`, `afde/production_composition/factory.py` |
| Validation evidence | `tests/test_production_composition.py`, `tests/test_production_composition_boundaries.py` |
| Known gaps | Adapter discovery, binding, instantiation, invocation, availability validation, credentials, and concrete production registrations remain deferred.<br>Runtime, Worker, Evidence, Operator, Product Assembly, CLI, Desktop, and lifecycle integration remain deferred.<br>Operational Evidence and M4 validation are not complete. |
| Source documents | `DOC-ARCH-0001`, `DOC-CREG-0001`, `DOC-COMPOSITION-0001` |
| Supersedes | none |

This entry records an official dependency composition root, not executable
authority or production readiness. The Registry remains the authoritative
Catalog supplier, and `runtime_allowed` and `execution_allowed` remain false.

### CAP-PRODUCTIONADAPTERREGISTRATION-0001

| Field | Value |
| --- | --- |
| Name | Production Adapter Registration Foundation |
| Description | Construct an independent Operational Adapter Registry containing the single approved static Codex Automation Bridge descriptor without importing, binding, or invoking the adapter. |
| Owner | AI Factory OS Architecture |
| Scope | `architecture.production_adapter_registration` |
| Status | `implemented` |
| Maturity | `M3` |
| Implementation status | `implemented` |
| Required knowledge | none |
| Required capabilities | `CAP-ADAPTERREGISTRY-0001` |
| Tool dependencies | none |
| Adapter dependencies | static Codex Automation Bridge metadata references, existing `OperationalAdapterRegistry`, existing `ToolAdapterCatalog` |
| Runtime dependencies | none |
| Implementation references | `afde/production_adapter_registration/__init__.py`, `afde/production_adapter_registration/factory.py` |
| Validation evidence | `tests/test_production_adapter_registration.py`, `tests/test_production_adapter_registration_boundaries.py` |
| Known gaps | Discovery, binding, instantiation, invocation, availability probes, and credential operations remain deferred.<br>Runtime, Worker, Evidence, Operator, Product, Provider, CLI, Desktop, startup, and lifecycle integration remain deferred.<br>Operational Evidence, production readiness, and M4 validation are not complete. |
| Source documents | `DOC-ARCH-0001`, `DOC-CREG-0001`, `DOC-PADREG-0001` |
| Supersedes | none |

This entry governs static registration metadata only. It grants no Runtime or
execution authority and makes no availability, credential-readiness,
production-readiness, or M4 claim.

### CAP-PRODUCTIONADAPTERDISCOVERY-0001

| Field | Value |
| --- | --- |
| Name | Production Adapter Discovery Foundation |
| Description | Discover installed entry-point metadata that loads exactly one existing ToolAdapterDescriptor per entry point, then merge it with unchanged static registrations through the existing Registry and Catalog. |
| Owner | AI Factory OS Architecture |
| Scope | `architecture.production_adapter_discovery` |
| Status | `implemented` |
| Maturity | `M3` |
| Implementation status | `implemented` |
| Required knowledge | none |
| Required capabilities | `CAP-PRODUCTIONADAPTERREGISTRATION-0001`, `CAP-ADAPTERREGISTRY-0001` |
| Tool dependencies | Python standard-library `importlib.metadata` |
| Adapter dependencies | caller-injected `ProductionAdapterDiscoverySource`, existing `ToolAdapterDescriptor`, static production registrations, existing `OperationalAdapterRegistry`, existing `ToolAdapterCatalog` |
| Runtime dependencies | none |
| Implementation references | `afde/production_adapter_discovery/__init__.py`, `afde/production_adapter_discovery/errors.py`, `afde/production_adapter_discovery/models.py`, `afde/production_adapter_discovery/discovery.py` |
| Validation evidence | `tests/test_production_adapter_discovery.py`, `tests/test_production_adapter_discovery_compatibility.py`, `tests/test_production_adapter_discovery_boundaries.py` |
| Known gaps | Adapter binding, invocation, health checks, network probes, credential handling, hot reload, filesystem and namespace scans remain excluded.<br>Runtime, Worker, Provider, CLI, Desktop, startup, and lifecycle integration remain deferred.<br>Operational Evidence, production readiness, and M4 validation are not complete. |
| Source documents | `DOC-ARCH-0001`, `DOC-CREG-0001`, `DOC-PADDISC-0001` |
| Supersedes | none |

This entry governs descriptor metadata discovery only. Entry-point failures,
invalid types, duplicate identities, and selectable Capability ambiguity fail
closed. `runtime_allowed` and `execution_allowed` remain false.

### CAP-PRODUCTIONADAPTERAVAILABILITY-0001

| Field | Value |
| --- | --- |
| Name | Production Adapter Availability Foundation |
| Description | Project one registered ToolAdapterDescriptor's exact AdapterAvailability metadata into an immutable non-executable availability result. |
| Owner | AI Factory OS Architecture |
| Scope | `architecture.production_adapter_availability` |
| Status | `implemented` |
| Maturity | `M3` |
| Implementation status | `implemented` |
| Required knowledge | none |
| Required capabilities | `CAP-PRODUCTIONADAPTERDISCOVERY-0001`, `CAP-PRODUCTIONADAPTERREGISTRATION-0001`, `CAP-ADAPTERREGISTRY-0001`, `CAP-TOOLCATALOG-0001`, `CAP-EXECPATH-0001`, `CAP-RUNTIME-0001` |
| Tool dependencies | none |
| Adapter dependencies | existing `ToolAdapterDescriptor`, existing `AdapterAvailability`, existing `OperationalAdapterRegistry`, existing `ToolAdapterCatalog` |
| Runtime dependencies | existing non-executable `ExecutionPathService`, `RuntimeProjection`, and `RuntimeIntegrationPolicy` compatibility only; no Runtime invocation |
| Implementation references | `afde/production_adapter_availability/__init__.py`, `afde/production_adapter_availability/errors.py`, `afde/production_adapter_availability/models.py`, `afde/production_adapter_availability/service.py` |
| Validation evidence | `tests/test_production_adapter_availability.py`, `tests/test_production_adapter_availability_compatibility.py`, `tests/test_production_adapter_availability_boundaries.py` |
| Known gaps | Availability is declared descriptor metadata, not health, reachability, credential readiness, or operational Evidence.<br>Adapter creation, binding, invocation, execution, credential operations, health checks, and network probes remain excluded.<br>Runtime startup/lifecycle/session, Worker, Provider, Product, CLI, Desktop, production readiness, and M4 validation remain incomplete. |
| Source documents | `DOC-CREG-0001` |
| Supersedes | none |

This entry performs an exact metadata projection only. It does not inspect
credentials or call Adapter, Runtime, Worker, Provider, Product, CLI, or
Desktop behavior. `runtime_allowed` and `execution_allowed` remain false.

### CAP-PRODUCTIONADAPTERCREDENTIALREADINESS-0001

| Field | Value |
| --- | --- |
| Name | Production Adapter Credential Readiness Foundation |
| Description | Determine one registered ToolAdapterDescriptor's credential readiness from existing credentials_required metadata and caller-supplied safe opaque evidence without accessing credential or secret material. |
| Owner | AI Factory OS Architecture |
| Scope | `architecture.production_adapter_credential_readiness` |
| Status | `implemented` |
| Maturity | `M3` |
| Implementation status | `implemented` |
| Required knowledge | none |
| Required capabilities | `CAP-PRODUCTIONADAPTERDISCOVERY-0001`, `CAP-PRODUCTIONADAPTERAVAILABILITY-0001`, `CAP-PRODUCTIONADAPTERREGISTRATION-0001`, `CAP-ADAPTERREGISTRY-0001`, `CAP-TOOLCATALOG-0001`, `CAP-EXECPATH-0001`, `CAP-RUNTIME-0001` |
| Tool dependencies | none |
| Adapter dependencies | existing `ToolAdapterDescriptor.credentials_required`, existing `OperationalAdapterRegistry`, existing `ToolAdapterCatalog` |
| Runtime dependencies | existing non-executable `ExecutionPathService`, `RuntimeHandoffProjection`, `RuntimeProjection`, and `RuntimeIntegrationPolicy` compatibility only; no Runtime invocation |
| Implementation references | `afde/production_adapter_credential_readiness/__init__.py`, `afde/production_adapter_credential_readiness/errors.py`, `afde/production_adapter_credential_readiness/models.py`, `afde/production_adapter_credential_readiness/service.py` |
| Validation evidence | `tests/test_production_adapter_credential_readiness.py`, `tests/test_production_adapter_credential_readiness_compatibility.py`, `tests/test_production_adapter_credential_readiness_boundaries.py` |
| Known gaps | Caller evidence is a readiness assertion, not credential validity, authorization, expiry, API access, network reachability, health, or production Evidence.<br>Credential lookup, validation, storage, encryption, secret stores, OAuth, refresh, Adapter binding/invocation/execution, and Runtime startup/lifecycle/session remain excluded.<br>Worker, Provider, Product, CLI, Desktop, operational validation, production readiness, and M4 remain incomplete. |
| Source documents | `DOC-CREG-0001` |
| Supersedes | none |

This entry accepts only an allowlisted evidence source, boolean readiness, and
safe opaque evidence reference supplied explicitly by the caller. It has no
field or dependency for credential values or secret material, performs no
automatic lookup, and grants no Runtime or execution authority.

### CAP-PRODUCTIONADAPTERCREATION-0001

| Field | Value |
| --- | --- |
| Name | Production Adapter Creation Foundation |
| Description | Validate descriptor, availability, credential readiness, optional existing binding, and caller-supplied factory metadata before creating one inert non-executable ProductionAdapterInstance. |
| Owner | AI Factory OS Architecture |
| Scope | `architecture.production_adapter_creation` |
| Status | `implemented` |
| Maturity | `M3` |
| Implementation status | `implemented` |
| Required knowledge | none |
| Required capabilities | `CAP-PRODUCTIONADAPTERDISCOVERY-0001`, `CAP-PRODUCTIONADAPTERREGISTRATION-0001`, `CAP-PRODUCTIONADAPTERAVAILABILITY-0001`, `CAP-PRODUCTIONADAPTERCREDENTIALREADINESS-0001`, `CAP-ADAPTERREGISTRY-0001`, `CAP-TOOLCATALOG-0001`, `CAP-TOOLADAPTER-CONTRACT-0001`, `CAP-EXECPATH-0001`, `CAP-RUNTIME-0001` |
| Tool dependencies | none |
| Adapter dependencies | existing `ToolAdapterDescriptor`, `OperationalAdapterRegistry`, `ToolAdapterCatalog`, `ToolAdapterBinding`, `ProductionAdapterAvailabilityResult`, `ProductionAdapterCredentialReadinessResult`, caller-supplied `ProductionAdapterFactory` |
| Runtime dependencies | existing non-executable Execution Path, Runtime Projection, and Tool Adapter Binding compatibility only; no Runtime binding, startup, lifecycle, session, or invocation |
| Implementation references | `afde/production_adapter_creation/__init__.py`, `afde/production_adapter_creation/errors.py`, `afde/production_adapter_creation/models.py`, `afde/production_adapter_creation/service.py` |
| Validation evidence | `tests/test_production_adapter_creation.py`, `tests/test_production_adapter_creation_compatibility.py`, `tests/test_production_adapter_creation_boundaries.py` |
| Known gaps | Instances are inert structural contracts and expose no invocation or execution behavior.<br>Factory automatic discovery, global instance registries, service locators, ranking, fallback, hot reload, Provider clients, credentials, probes, and Runtime integration remain excluded.<br>Operational Evidence, production readiness, M4, Worker, Product, CLI, and Desktop integration remain incomplete. |
| Source documents | `DOC-CREG-0001` |
| Supersedes | none |

Descriptor, Registry, and Catalog remain metadata authorities and do not own
factories or instances. Factories are caller-supplied and exact-identity
scoped. Creation returns only an inert immutable instance; it grants no
invocation, execution, Runtime, health, or production-ready authority.

### CAP-PRODUCTIONADAPTERINVOCATION-0001

| Field | Value |
| --- | --- |
| Name | Production Adapter Invocation Contract Foundation |
| Description | Validate an existing creation, instance, binding, request, availability, and credential-readiness identity chain before calling one explicit caller-supplied metadata-only InvocationTarget. |
| Owner | AI Factory OS Architecture |
| Scope | `architecture.production_adapter_invocation` |
| Status | `implemented` |
| Maturity | `M3` |
| Implementation status | `implemented` |
| Required knowledge | none |
| Required capabilities | `CAP-PRODUCTIONADAPTERCREATION-0001`, `CAP-PRODUCTIONADAPTERAVAILABILITY-0001`, `CAP-PRODUCTIONADAPTERCREDENTIALREADINESS-0001`, `CAP-TOOLADAPTER-CONTRACT-0001`, `CAP-TOOLCATALOG-0001`, `CAP-EXECPATH-0001`, `CAP-RUNTIME-0001` |
| Tool dependencies | none |
| Adapter dependencies | existing `ProductionAdapterCreationResult`, `ProductionAdapterInstance`, `ToolAdapterRequest`, `ToolAdapterBinding`, `ToolAdapterDescriptor`, `ProductionAdapterAvailabilityResult`, `ProductionAdapterCredentialReadinessResult`, caller-supplied `InvocationTarget` |
| Runtime dependencies | existing non-executable Execution Path, Runtime Projection, and Tool Adapter Binding compatibility only; no Runtime startup, lifecycle, session, or integration |
| Implementation references | `afde/production_adapter_invocation/__init__.py`, `afde/production_adapter_invocation/errors.py`, `afde/production_adapter_invocation/models.py`, `afde/production_adapter_invocation/service.py` |
| Validation evidence | `tests/test_production_adapter_invocation.py`, `tests/test_production_adapter_invocation_compatibility.py`, `tests/test_production_adapter_invocation_boundaries.py` |
| Known gaps | Target inputs and outputs contain only safe opaque metadata references; Provider payload, network, retry, timeout, streaming, and operational execution semantics are absent.<br>Target discovery, mutable target registries, Runtime integration, Worker dispatch, credentials, Provider clients, and lifecycle ownership remain excluded.<br>Operational Evidence, production readiness, and M4 validation remain incomplete. |
| Source documents | `DOC-CREG-0001` |
| Supersedes | none |

The target is supplied explicitly for each service call and must match the
complete immutable identity chain. The existing instance stays inert. Neither
request, target result, nor service result can grant Runtime or execution
authority.

### CAP-PRODUCTIONADAPTERRUNTIMESTARTUPINTEGRATION-0001

| Field | Value |
| --- | --- |
| Name | Production Adapter Runtime Startup Integration Foundation |
| Description | Assemble discovered production adapter metadata and the existing production composition, availability, credential-readiness, creation, and invocation capabilities at an explicit application-startup boundary without creating a Runtime session, creating an Adapter instance, or invoking a target. |
| Owner | AI Factory OS Architecture |
| Scope | `architecture.production_adapter_runtime_startup_integration` |
| Status | `implemented` |
| Maturity | `M3` |
| Implementation status | `implemented` |
| Required knowledge | none |
| Required capabilities | `CAP-PRODUCTIONCOMPOSITION-0001`, `CAP-PRODUCTIONADAPTERDISCOVERY-0001`, `CAP-PRODUCTIONADAPTERAVAILABILITY-0001`, `CAP-PRODUCTIONADAPTERCREDENTIALREADINESS-0001`, `CAP-PRODUCTIONADAPTERCREATION-0001`, `CAP-PRODUCTIONADAPTERINVOCATION-0001` |
| Tool dependencies | none |
| Adapter dependencies | caller-supplied `ProductionAdapterDiscoverySource`, `ProductionAdapterFactory`, `CredentialReadinessEvidence`, allowlisted `ProductionAdapterConfigurationMetadata`, and `InvocationTarget`; existing Registry, Catalog, Descriptor, Availability, Credential Readiness, Creation, Invocation, and immutable composition contracts |
| Runtime dependencies | existing non-executable production composition and immutable Runtime policy compatibility only; no Runtime startup, lifecycle mutation, session creation, invocation, or execution |
| Implementation references | `afde/production_adapter_runtime_startup_integration/__init__.py`, `afde/production_adapter_runtime_startup_integration/errors.py`, `afde/production_adapter_runtime_startup_integration/models.py`, `afde/production_adapter_runtime_startup_integration/factory.py` |
| Validation evidence | `tests/test_production_adapter_runtime_startup_integration.py`, `tests/test_production_adapter_runtime_startup_integration_compatibility.py`, `tests/test_production_adapter_runtime_startup_integration_boundaries.py` |
| Known gaps | Startup produces only a validated dependency graph; Adapter instance creation and target invocation require separate explicit downstream calls.<br>Runtime session/lifecycle integration, Worker/Provider/Product/CLI/Desktop wiring, credential secrets, network, retry, timeout, streaming, and background services remain excluded.<br>Operational Evidence, production readiness, and M4 validation remain incomplete. |
| Source documents | `DOC-CREG-0001` |
| Supersedes | none |

This entry governs composition at application startup only. Exact Registry,
Descriptor, factory, evidence, Creation Context, and target identities and
availability/readiness prerequisites fail closed. `runtime_allowed` and
`execution_allowed` remain false throughout the assembled graph.

### CAP-PRODUCTIONADAPTERRUNTIMEEXECUTION-0001

| Field | Value |
| --- | --- |
| Name | Production Adapter Runtime Execution Foundation |
| Description | Atomically consume one explicitly Runtime-authorized identity for at most one production adapter creation and invocation operation through the existing startup composition, returning authority-free completion evidence while preserving existing Runtime lifecycle and public contracts. |
| Owner | AI Factory OS Architecture |
| Scope | `architecture.production_adapter_runtime_execution` |
| Status | `implemented` |
| Maturity | `M3` |
| Implementation status | `implemented` |
| Required knowledge | none |
| Required capabilities | `CAP-PRODUCTIONADAPTERREGISTRATION-0001`, `CAP-PRODUCTIONADAPTERDISCOVERY-0001`, `CAP-PRODUCTIONADAPTERAVAILABILITY-0001`, `CAP-PRODUCTIONADAPTERCREDENTIALREADINESS-0001`, `CAP-PRODUCTIONADAPTERCREATION-0001`, `CAP-PRODUCTIONADAPTERINVOCATION-0001`, `CAP-PRODUCTIONADAPTERRUNTIMESTARTUPINTEGRATION-0001` |
| Tool dependencies | none |
| Adapter dependencies | existing startup composition, `ToolAdapterRequest`, `ToolAdapterBinding`, Creation Service, Invocation Service, and explicit caller-supplied target |
| Runtime dependencies | explicit immutable Runtime execution authority bound to adapter, projection, path, Capability, and binding identities; package-private process-local atomic consumption; existing lifecycle ownership remains unchanged |
| Implementation references | `afde/production_adapter_runtime_execution/__init__.py`, `afde/production_adapter_runtime_execution/errors.py`, `afde/production_adapter_runtime_execution/models.py`, `afde/production_adapter_runtime_execution/service.py` |
| Validation evidence | focused tests proving completed-result authority non-exposure, same-request reuse rejection, same-identity new-request rejection, and concurrent exactly-once consumption in `tests/test_production_adapter_runtime_execution.py`; compatibility and Architecture Boundary tests |
| Known gaps | Runtime authority issuance, revocation, durable cross-process consumption persistence, and lifecycle transitions remain external to this boundary; in-process sequential and concurrent reuse fail closed.<br>Worker/Provider/Product/CLI/Desktop wiring, network transport, retry, timeout, streaming, cancellation, and background execution remain excluded.<br>Operational Evidence, production readiness, and M4 validation remain incomplete. |
| Source documents | `DOC-CREG-0001` |
| Supersedes | none |

This entry grants authority only through an explicit immutable execution-scoped
contract. The authority must match the existing startup, Runtime projection,
Tool Adapter request, and binding identity chain, then its unique authority
reference is atomically consumed before creation occurs. Sequential or concurrent reuse is
rejected before factory or target behavior. The completed result stores no
original execution request, authority object, or authority reference; it
contains only non-authoritative identity metadata and the existing Creation and
Invocation results. No Runtime lifecycle state is read or mutated.

### CAP-PRODUCTIONADAPTERWORKEREXECUTION-0001

| Field | Value |
| --- | --- |
| Name | Production Adapter Worker Execution Foundation |
| Description | Preserve one explicit existing Worker input and Worker result around exactly one existing Production Adapter Runtime execution call without Worker or Runtime lifecycle ownership, Provider binding, registry lookup, or dispatch. |
| Owner | AI Factory OS Architecture |
| Scope | `architecture.production_adapter_worker_execution` |
| Status | `implemented` |
| Maturity | `M3` |
| Implementation status | `implemented` |
| Required knowledge | none |
| Required capabilities | `CAP-PRODUCTIONADAPTERRUNTIMEEXECUTION-0001` |
| Tool dependencies | none |
| Adapter dependencies | existing `ExecutionInput`, `WorkerExecutionResult`, `ProductionAdapterRuntimeExecutionRequest`, `ProductionAdapterRuntimeExecutionResult`, and `ProductionAdapterRuntimeExecutionService` |
| Runtime dependencies | existing single-use Production Adapter Runtime execution boundary; existing Worker and Runtime lifecycle ownership remains unchanged |
| Implementation references | `afde/production_adapter_worker_execution/__init__.py`, `afde/production_adapter_worker_execution/errors.py`, `afde/production_adapter_worker_execution/models.py`, `afde/production_adapter_worker_execution/service.py` |
| Validation evidence | `tests/test_production_adapter_worker_execution.py`, `tests/test_production_adapter_worker_execution_compatibility.py`, `tests/test_production_adapter_worker_execution_boundaries.py` |
| Known gaps | Caller-invoked only; Worker Manager dispatch, Registry selection, RealWorkerRuntime, RuntimeOrchestrator, sessions, scheduling, and lifecycle transitions remain excluded.<br>Provider binding/SDK, network, retry, cancellation, and background execution remain excluded.<br>Operational Evidence, production readiness, and M4 validation remain incomplete. |
| Source documents | `DOC-CREG-0001` |
| Supersedes | none |

This entry accepts one immutable existing Worker input plus existing startup,
Tool Adapter request/binding, authority, and invocation metadata contracts. It
validates Worker identity without consulting the Worker Registry, assembles the
existing Runtime execution request, calls the existing Runtime execution service
exactly once, and returns the unchanged Runtime result alongside an existing
immutable Worker result. Runtime errors propagate unchanged. Provider metadata
is copied from the input only; no Provider is selected or called. No Worker or
Runtime lifecycle state is read or mutated.

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

- The production composition is non-executable and has no executable consumer.
- Additional production Adapter registrations remain deferred.
- Discovery remains metadata-only and has no binding or executable consumer.
- Availability remains declared metadata and is not a health or network probe.
- Credential readiness remains caller-declared metadata and is not credential
  validation, authorization, or secret handling.
- Adapter creation remains separated from invocation, execution, Runtime
  binding, and lifecycle ownership.
- Adapter invocation remains caller-target scoped, metadata-only, and
  separated from Provider, Worker, Network, and Runtime integration.
- Production Adapter startup integration remains composition-only and does
  not create a Runtime session, Adapter instance, or invocation request.
- Production Adapter Worker execution is caller-invoked only; operational
  dispatch and lifecycle integration remain deferred.
- Multiple-candidate discovery and ranking remain deferred.
- M4 validation and operational integration are not complete.
- RAG, vector databases, embeddings, and multimodal adapters are outside
  the current foundation scope.
