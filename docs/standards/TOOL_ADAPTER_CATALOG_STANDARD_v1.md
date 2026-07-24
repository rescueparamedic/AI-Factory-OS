# Tool Adapter Catalog Standard v1

## Status

- Standard ID: `STD-TCAT-0001`
- Status: Active
- Owner: AI Factory OS Architecture
- Effective Sprint: AFDE-5.2

## Purpose

The Tool Adapter Catalog is the read-only Single Source of Truth for adapter
discovery metadata supplied to Tool Adapter Selection. It identifies adapters
and exact Capability mappings; it grants no execution, approval, credential,
Runtime, Worker, Provider, Evidence, or Product authority.

The Knowledge Foundation Registry continues to govern documents, Knowledge,
and Capability lifecycle. It does not duplicate adapter entries. A constructed
Catalog snapshot owns adapter discovery metadata for its scope.

## Descriptor Contract

Every descriptor contains:

- stable adapter identity;
- display name and semantic version;
- one or more exact governed Capability IDs;
- explicit availability and Runtime compatibility;
- explicit execution-contract, privacy, and cost classifications;
- explicit credential-requirement flag;
- description and optional metadata references.

Descriptors and their collections are immutable after validation. Invalid
identity, version, Capability mapping, classification, or collection shape
fails closed.

## Catalog Policy

- Constructor input is defensively snapshotted.
- Adapter identities are unique and ordered deterministically.
- Capability mappings use exact IDs and stable adapter-ID ordering.
- Exact adapter and Capability lookups perform no fuzzy or semantic matching.
- Multiple selectable adapters for one Capability are ambiguous and rejected.
- Unavailable, Runtime-incompatible, unverified, or execution-contract-
  undeclared descriptors remain discoverable but are not selection candidates.
- Empty Catalogs are valid and return empty immutable projections.
- `list_candidates()` projects the existing AFDE-5.1
  `ToolAdapterCandidate` contract without changing Tool Selection.

## Classification Values

The M3 foundation uses only the minimum explicit values:

- availability: `available`, `unavailable`;
- Runtime compatibility: `compatible`, `incompatible`, `unverified`;
- execution contract: `controlled_runtime`, `not_declared`;
- privacy: `local`, `external`;
- cost: `no_cost`, `variable`.

These values are discovery metadata, not proof of operational availability,
compatibility, safety, price, credentials, or execution authorization.

## Isolation

Catalog construction and lookup perform no filesystem or network access and
make no Provider, Runtime, Worker, Product Layer, Evidence, or adapter calls.
Runtime, Worker, Provider, and Tool Selection must not mutate the Catalog.

Existing `real_worker_runtime` adapters are not automatically registered.
They lack the complete governed metadata required by this standard. Operational
population requires separate review and validation.

## Capability Status

```yaml
capability_id: CAP-TOOLCATALOG-0001
status: implemented
maturity: M3
implementation_status: implemented
```

M4 validation, operational adapter population, execution integration, dynamic
discovery, ranking, fallback, and credential or secret management remain
deferred.
