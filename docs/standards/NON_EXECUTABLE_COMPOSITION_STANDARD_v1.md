# Non-executable Composition Standard v1

## Status

- Standard ID: `STD-COMPOSITION-0001`
- Status: Active
- Owner: AI Factory OS Architecture
- Effective Sprint: AFDE-5.6

## Purpose and Ownership

Non-executable Composition is the explicit construction boundary for the
existing AFDE-5.0 through AFDE-5.5 capability services. It creates one frozen
container holding the seven existing service instances without executing any
service behavior.

The composition owns constructor wiring only. It is not an orchestration
request, result, execution facade, service locator, plugin container,
configuration loader, Runtime session, or production application.

## Required Construction

`build_non_executable_composition` accepts:

- a caller-supplied read-only `KnowledgeProvider`;
- caller-supplied in-memory `ToolAdapterDescriptor` values;
- a caller-supplied immutable `RuntimeIntegrationPolicy`.

It constructs, in order:

1. `CapabilityResolver`;
2. `PlannerResolutionService`;
3. `ToolAdapterCatalog`;
4. `ToolAdapterSelectionService`;
5. `ExecutionPathService`;
6. `RuntimeIntegrationService`;
7. `ToolAdapterContractService`.

Tool Adapter Selection, Execution Path, and Tool Adapter Contract receive the
same `ToolAdapterCatalog` instance. The builder never creates a
`KnowledgeFoundationProvider` and never reads Registry JSON, files,
environment variables, or configuration.

## Contract and Authority

`NonExecutableComposition` is a frozen dataclass containing only the seven
service fields and these authority fields:

- `runtime_allowed: false`;
- `execution_allowed: false`.

Any composition that grants either authority fails closed. The composition
does not expose `run`, `execute`, `invoke`, `dispatch`, `start`, `resume`,
`recover`, or `cancel`.

## Isolation

Construction does not call Planner, Provider, Adapter, Runtime, Worker,
Evidence, filesystem, network, subprocess, Operator, Product, Desktop, CLI, or
API behavior. It adds no dynamic import, plugin discovery, DI container,
configuration loading, external dependency, composition ID, trace, or hidden
registry.

Existing request and result contracts remain the only way to call the
constructed services explicitly. The builder and container make no such
calls.

## External Open-source Audit

Audit date: 2026-07-26.

- Python frozen dataclasses fit the repository's immutable container
  convention and require no dependency.
- Dependency Injector provides declarative containers, providers,
  configuration, and wiring. Those features exceed this constructor-only
  boundary and would introduce an unnecessary framework surface.

Decision: use explicit constructors and the standard library only.

## Capability Status

```yaml
capability_id: CAP-COMPOSITION-0001
status: implemented
maturity: M3
implementation_status: implemented
```

Executable production composition, concrete production Adapter registrations,
Worker/Evidence/Product integration, and operational M4 Evidence remain
deferred.
