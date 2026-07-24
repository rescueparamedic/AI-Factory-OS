# Execution Path Standard v1

## Status

- Standard ID: `STD-EXEP-0001`
- Status: Active
- Owner: AI Factory OS Architecture
- Effective Sprint: AFDE-5.3

## Purpose

Execution Path is the read-only application boundary between Tool Adapter
Selection and future Runtime integration. It transforms one successful
selection plus exact governed Catalog metadata into an immutable structural
handoff route.

An Execution Path is not executable authority. It does not approve, start, or
invoke Runtime, Worker, Tool Adapter, command, task, Provider, Product, or
Evidence behavior.

## Input and Ownership

The Execution Path service owns structural route validation and projection. It
accepts the immutable AFDE-5.1 `ToolAdapterSelectionResult` and reads the exact
AFDE-5.2 `ToolAdapterDescriptor` through a constructor-injected Catalog lookup
boundary.

Catalog remains the Single Source of Truth for adapter discovery metadata.
Execution Path does not load files, parse Registry JSON, discover adapters,
construct a Catalog, or reinterpret Capability mappings.

## Construction Policy

A path is constructed only when:

- Tool Selection uniquely selected one adapter;
- Resolver status is resolved and eligible with no pending decision;
- selection and Catalog adapter identities and Capability mappings agree;
- the adapter is available;
- Runtime compatibility is `compatible`;
- execution contract is `controlled_runtime`;
- required structured metadata is valid.

No-selection, blocked, ambiguous, unresolved, unavailable, incompatible,
unsupported, missing, or conflicting input fails closed with a structured
blocked or unavailable result. Upstream state is never silently repaired.

## Credential Prerequisite

Credential acquisition, storage, authorization, and secret management are
outside Execution Path. When valid Catalog metadata declares credentials
required, the structural path may be constructed with
`prerequisites_required`, but Runtime handoff readiness remains false and the
credential prerequisite stays explicit.

## Authority Policy

The four distinct projections are:

- `path_constructed`: structural route exists;
- `runtime_handoff_ready`: structural prerequisites are complete;
- `runtime_allowed`: always false in AFDE-5.3;
- `execution_allowed`: always false in AFDE-5.3.

Only a future governed Runtime Integration capability may authorize actual
Runtime handoff or execution.

## Determinism and Preservation

Execution Path:

- derives its path ID from stable structured metadata without time or random
  input;
- uses stable ordered steps and trace;
- preserves exact adapter identity and Capability ID;
- preserves relevant Catalog metadata;
- preserves Resolver status, gaps, rationale, references, and trace;
- preserves Tool Selection rationale and trace;
- returns immutable tuples and projections.

## Isolation

Execution Path performs no filesystem or network access and makes no Provider,
Runtime, Worker, Product Layer, Evidence, adapter, command, task, process,
orchestration, recovery, resume, cancellation, or retry call. No lower or
upstream layer may mutate an Execution Path.

## Capability Status

```yaml
capability_id: CAP-EXECPATH-0001
status: implemented
maturity: M3
implementation_status: implemented
```

Runtime authorization and invocation, operational adapters, Worker handoff,
Evidence, Product Assembly, credential handling, operational validation, and
M4 remain deferred.
