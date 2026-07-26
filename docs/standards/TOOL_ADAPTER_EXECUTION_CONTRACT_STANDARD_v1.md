# Tool Adapter Execution Contract Standard v1

## Status

- Standard ID: `STD-TOOLADAPTER-CONTRACT-0001`
- Status: Active
- Owner: AI Factory OS Architecture
- Effective Sprint: AFDE-5.5

## Purpose and Ownership

The Tool Adapter Execution Contract is the read-only validation boundary
between an AFDE-5.4 `RuntimeProjection` and future adapter execution. It
establishes immutable request, binding, result, and error contracts without
invoking an adapter.

AFDE-5.5 owns binding validation only. Runtime, Worker, Provider, adapter
execution, Evidence, approval, credentials, lifecycle, Product Assembly,
Desktop, Operator, and Beta Execute behavior remain outside this capability.

## Input and Lookup

`ToolAdapterContractService` accepts an immutable `ToolAdapterRequest` and a
constructor-injected `AdapterLookup`. The request snapshots the exact
`projection_id`, `path_id`, `capability_id`, and `adapter_id` from one
structurally ready `RuntimeProjection`.

The lookup boundary exposes only a read-only descriptor snapshot. It has no
execution method. `ToolAdapterCatalog.list_adapters()` satisfies this boundary
additively and returns its existing immutable, deterministic descriptor
snapshot.

## Validation and Result

Validation fails closed when:

- the lookup cannot provide an iterable descriptor snapshot;
- any returned entry is malformed;
- any adapter identity is duplicated;
- the projected adapter identity is unregistered; or
- Capability, version, availability, compatibility, execution-contract,
  privacy, cost, credential, or metadata-reference values mismatch.

A successful result contains deterministic `ToolAdapterBinding` metadata.
Rejected results contain immutable `ToolAdapterError` contracts. Every result,
binding, and error preserves the request's projection, path, Capability, and
adapter identities.

All outcomes have:

- `runtime_allowed: false`;
- `execution_allowed: false`.

## Determinism and Isolation

Lookup entries are snapshotted and ordered by exact adapter identity. Binding
identity derives only from stable request and descriptor metadata. Trace and
error ordering are deterministic.

The boundary uses no time, randomness, filesystem, environment, network,
dynamic plugin discovery, Runtime session, Worker, Provider, process, command,
approval, credential, Evidence, Product, or lifecycle behavior.

## Limited External Open-Source Audit

Audit date: 2026-07-26. Official Python documentation was reviewed for frozen
dataclasses, structural protocols, and read-only mapping views.

| Candidate | Fit | Decision |
| --- | --- | --- |
| Python frozen dataclasses | Matches repository immutable contract convention | Adopt standard library |
| Python `typing.Protocol` | Supports a narrow constructor-injected structural lookup boundary | Adopt standard library |
| Python `MappingProxyType` | Provides a read-only mapping view, but the existing Catalog already owns an immutable tuple snapshot | Reference only |

No third-party package was adopted. Runtime-checkable protocols were not used
because their runtime checks establish member presence, not signature or value
validity. Explicit snapshot and model validation is required to fail closed.

Official references reviewed:

- `docs.python.org/3/library/dataclasses.html`
- `docs.python.org/3/library/typing.html`
- `docs.python.org/3/library/types.html`

## Capability Status

```yaml
capability_id: CAP-TOOLADAPTER-CONTRACT-0001
status: implemented
maturity: M3
implementation_status: implemented
```

Adapter execution and operational M4 validation remain deferred.
