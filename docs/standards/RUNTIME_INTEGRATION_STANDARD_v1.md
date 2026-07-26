# Runtime Integration Standard v1

## Status

- Standard ID: `STD-RUNTIME-0001`
- Status: Active
- Owner: AI Factory OS Architecture
- Effective Sprint: AFDE-5.4

## Purpose and Ownership

Runtime Integration is the read-only application boundary between an AFDE-5.3
Execution Path and future executable Runtime behavior. It validates one
immutable `ExecutionPathResult` and produces deterministic Runtime-ready
metadata.

The foundation owns readiness projection only. Existing Beta and real-worker
Runtime components continue to own executable lifecycle, Worker, Provider,
orchestration, persistence, and Evidence behavior. AFDE-5.4 does not import,
invoke, or modify those contracts.

## Input and Policy

`RuntimeIntegrationService` requires constructor-injected immutable
`RuntimeIntegrationPolicy` and accepts an immutable
`RuntimeIntegrationRequest`.

A Runtime projection is ready only when:

- Execution Path status is `constructed`;
- the path and its single handoff step are structurally complete;
- Runtime handoff readiness is true;
- path, adapter, and Capability identities are present;
- compatibility and execution contract match the injected policy;
- neither the path nor handoff step grants Runtime or execution authority.

All other inputs fail closed with a structured blocked result. The service
does not repair upstream state or perform live checks.

## Result and Authority

The immutable result contains an optional immutable `RuntimeProjection`,
preserved path trace, deterministic integration trace, and explicit blocked
reasons.

- `runtime_ready` may be true for a complete structural projection.
- `runtime_allowed` is always false.
- `execution_allowed` is always false.

Runtime-ready state is not permission to create a session, change lifecycle
state, invoke a Worker, execute an adapter, or call a Provider.

## Determinism and Isolation

Projection identity derives from stable ordered path, policy, adapter, and
Catalog metadata. Runtime Integration uses no time, randomness, filesystem
discovery, network discovery, dynamic plugin loading, or environment state.

It performs no Runtime or Worker execution, lifecycle mutation, Provider call,
Product Assembly, Evidence generation, orchestration, retry, recovery, resume,
cancellation, command dispatch, or persistence.

## External Open-Source Audit

Audit date: 2026-07-24. Maintenance status is based on official project
repositories, documentation, and releases reviewed during AFDE-5.4.

| Name | Purpose / license / maintenance | Architecture fit and isolation | Time saved / risk | Decision |
| --- | --- | --- | --- | --- |
| Prefect | Workflow orchestration; Apache-2.0; active | Adapter isolation possible, but introduces an execution engine far beyond readiness projection | No AFDE-5.4 time saved; high operational and dependency surface | Reject |
| Dagster | Data-asset orchestration; Apache-2.0; active | Adapter possible, but data orchestration and execution semantics do not fit the read-only boundary | No near-term saving; high conceptual and operational weight | Reject |
| Temporal Python SDK | Durable workflow execution; MIT; active | Adapter possible, but requires Temporal execution/service concepts expressly excluded | Future execution research value; very high infrastructure and authority risk | Reference only |
| Dramatiq | Background task processing; LGPL-3.0; active | Broker adapter possible, but task dispatch is outside scope | No projection saving; broker and Worker coupling risk | Reject |
| Celery | Distributed task queue; BSD-3-Clause; active | Adapter possible, but broker/Worker execution violates this Sprint boundary | No projection saving; substantial distributed-runtime complexity | Reject |
| pluggy | Plugin and hook system; MIT; active | Isolatable, but AFDE-5.4 must not discover or load plugins | No saving for a single injected policy; premature extension surface | Reject |
| stevedore | Entry-point plugin management; Apache-2.0; active | Isolatable, but dynamic plugin discovery is excluded | No saving; discovery and packaging complexity | Reject |
| transitions | Finite-state machine; MIT; maintained | Could wrap state policy, but AFDE-5.4 has two immutable outcomes and no transitions | Negligible saving; unnecessary dependency and lifecycle confusion | Reject |
| Python `graphlib` | Standard-library DAG ordering; PSF; maintained | Direct use possible, but Runtime Integration builds no task graph | No saving; would imply orchestration not present | Reference only |
| NetworkX | Graph algorithms; BSD-3-Clause; active | Adapter possible, but no graph computation is required | No saving; large unnecessary abstraction surface | Reject |
| Pydantic | Typed validation; MIT; active | Can be isolated, but repository contracts consistently use frozen dataclasses | Minimal saving; public-model and dependency churn | Reject |
| attrs | Declarative data classes; MIT; active | Can be isolated, but duplicates standard-library frozen dataclasses | No saving; inconsistent model convention | Reject |
| psutil | Process/system monitoring; BSD-3-Clause; active | Adapter possible, but live process checks are prohibited | No saving; platform-dependent live-state coupling | Reject |
| structlog | Structured logging; MIT or Apache-2.0; active | Adapter possible, but AFDE-5.4 emits immutable traces and no operational logs | No saving; new logging contract and dependency | Reject |
| Rich | Terminal rendering; MIT; active | UI adapter possible, but CLI/Desktop changes are excluded | No saving; presentation dependency outside capability scope | Reject |

Official references reviewed:

- `github.com/PrefectHQ/prefect`
- `github.com/dagster-io/dagster`
- `github.com/temporalio/sdk-python`
- `github.com/Bogdanp/dramatiq`
- `github.com/celery/celery`
- `github.com/pytest-dev/pluggy`
- `docs.openstack.org/stevedore`
- `github.com/pytransitions/transitions`
- `docs.python.org/3/library/graphlib.html`
- `github.com/networkx/networkx`
- `github.com/pydantic/pydantic`
- `pypi.org/project/attrs`
- `github.com/giampaolo/psutil`
- `github.com/hynek/structlog`
- `github.com/Textualize/rich`

The audit adopts no third-party dependency. Mature projects remain candidates
for future executable capabilities only after their authority, operations,
licensing, and adapter boundaries are separately governed.

## Capability Status

```yaml
capability_id: CAP-RUNTIME-0001
status: implemented
maturity: M3
implementation_status: implemented
```

Runtime execution, session creation, lifecycle mutation, Worker or adapter
invocation, Provider integration, Evidence, Product Assembly, operational
monitoring, and M4 validation remain deferred.
