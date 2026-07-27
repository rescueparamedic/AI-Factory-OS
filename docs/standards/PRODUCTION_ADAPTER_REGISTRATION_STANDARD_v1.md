# Production Adapter Registration Standard v1

## Status

- Standard ID: `DOC-PADREG-0001`
- Status: Active
- Owner: AI Factory OS Architecture
- Effective Sprint: AFDE-5.9
- Capability: `CAP-PRODUCTIONADAPTERREGISTRATION-0001`

## Purpose and Ownership

Production Adapter Registration is the official static metadata boundary for
approved production Tool Adapter descriptors. The package-scoped
`build_production_adapter_registry()` function returns an existing
`OperationalAdapterRegistry` populated with approved immutable
`ToolAdapterDescriptor` values.

The boundary owns only descriptor declaration and Registry construction. It
does not own discovery, adapter binding, instantiation, invocation,
availability probing, credential handling, Runtime lifecycle, application
startup, or dependency injection.

## Required Registration

AFDE-5.9 registers exactly one descriptor:

| Field | Value |
| --- | --- |
| `adapter_id` | `adapter.codex_automation_bridge` |
| `display_name` | `Codex Automation Bridge` |
| `version` | `1.0.0` |
| `supported_capability_ids` | `CAP-TOOLADAPTER-CONTRACT-0001` |
| `availability` | `available` |
| `runtime_compatibility` | `compatible` |
| `execution_contract` | `controlled_runtime` |
| `privacy_classification` | `external` |
| `cost_classification` | `no_cost` |
| `credentials_required` | `true` |

Its metadata references are:

- `real_worker_runtime/automation_bridge.py`
- `real_worker_runtime/tool_actions.py`
- `docs/reports/AFDE_3_2_CODEX_AUTOMATION_BRIDGE_REPORT.md`

These values are metadata strings only. Registration does not import or
inspect the referenced files and does not establish health, reachability,
credential readiness, execution authority, or production readiness.

## Construction and Identity

Every function call creates a new frozen descriptor and a new
`OperationalAdapterRegistry`. The Registry constructs and retains one existing
`ToolAdapterCatalog`; repeated `project_catalog()` calls on that Registry
return that same Catalog instance. Independent calls produce equal,
deterministically ordered immutable snapshots without sharing a Registry or
Catalog instance.

The returned Registry may be passed directly to
`build_production_composition()`. The composition must retain the exact
Registry-projected Catalog identity across Tool Adapter Selection, Execution
Path, and Tool Adapter Contract.

## Authority and Isolation

Registration and composition preserve:

- `runtime_allowed: false`
- `execution_allowed: false`

Construction performs no filesystem, network, environment, configuration,
discovery, entry-point, dynamic-import, Provider, Adapter, Runtime, Worker,
Evidence, Operator, Product, CLI, Desktop, subprocess, or lifecycle behavior.
It creates no new descriptor model, Registry type, Catalog type, DI container,
module-level mutable Registry, or module-level mutable Catalog.

Internal File, Command, Test, and Git adapters and the OpenAI Provider are not
registered by this standard. Adapter behavior, credential operations,
downstream executable integration, operational Evidence, production-ready
claims, and M4 validation remain outside scope.

## Capability Registration

```yaml
capability_id: CAP-PRODUCTIONADAPTERREGISTRATION-0001
status: implemented
maturity: M3
implementation_status: implemented
required_capabilities:
  - CAP-ADAPTERREGISTRY-0001
```

The Knowledge Registry entry and this Source of Record reciprocally bind
`DOC-PADREG-0001` and `CAP-PRODUCTIONADAPTERREGISTRATION-0001`.
