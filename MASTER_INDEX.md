# AI Factory OS Master Index

## Current Architecture and Governance

### Architecture

- `docs/development/AFDE_ARCHITECTURE_v1.md` — canonical AFDE architecture,
  including the AFDE-5.0 Planner-to-Resolver integration flow
- `docs/architecture/AI_DEVELOPMENT_ENGINE_PRODUCT_LAYER.md` — Product Layer,
  future capability, Resolver, Adapter, Runtime, Evidence, and Product Assembly
  boundaries

### Knowledge Foundation Standards

- `docs/standards/DOCUMENT_KNOWLEDGE_MANAGEMENT_STANDARD_v1.md`
- `docs/standards/KNOWLEDGE_REGISTRY_STANDARD_v1.md`
- `docs/standards/CAPABILITY_REGISTRY_STANDARD_v1.md`
- `docs/standards/DOCUMENT_GOVERNANCE_STANDARD_v1.md`
- `docs/standards/AI_REFERENCE_POLICY_v1.md`

### Living Repository Records

- `DECISION_LOG.md` — accepted architecture and governance decisions
- `PROJECT_STATUS.md` — current delivery and capability status
- `CHANGELOG.md` — repository change history
- `PROJECT_BASELINE.md` — frozen historical baseline; not current architecture

### Knowledge Foundation Implementation

- `docs/registry/KNOWLEDGE_FOUNDATION_REGISTRY_v1.json` — governed
  machine-readable Registry projection; not a Source of Truth
- `afde/knowledge/` — immutable models, read-only loader, validator, and
  Resolver-ready Knowledge Provider
- `tests/test_knowledge_*.py` — focused model, Registry, Provider, and
  architecture-boundary validation

### Capability Resolver Implementation

- `afde/resolver/` — immutable requirement/result models and deterministic,
  read-only capability eligibility evaluation over the Knowledge Provider
- `tests/test_capability_resolver*.py` — model, resolution-rule,
  Provider-injection, byte-invariance, and architecture-boundary validation

```yaml
capability_id: CAP-RESOLVER-0001
status: implemented
maturity: M3
implementation_status: implemented
```

Resolver evaluates one exact registered capability candidate. Planner
integration is provided separately by `afde/planner_resolution/`.
Multiple-candidate discovery/ranking, Tool Adapter selection, Runtime
integration, operational Evidence, and M4 validation remain deferred.

### Planner-Resolver Integration

- `afde/planner_resolution/` — immutable request/result models and a small
  application service that invokes an injected Resolver
- `tests/test_planner_resolver_integration*.py` — model, projection,
  dependency-injection, determinism, and architecture-boundary validation

```yaml
capability_id: CAP-PLANRES-0001
status: implemented
maturity: M3
implementation_status: implemented
```

The integration accepts structured Planner context and an explicit Capability
Requirement, preserves Resolver status, gaps, and ordered rationale, and never
grants Runtime execution.

### Tool Adapter Selection

- `afde/tool_selection/` — immutable selection contracts and deterministic
  exact-Capability-ID policy over an injected candidate source
- `tests/test_tool_adapter_selection*.py` — focused behavior, immutability,
  preservation, dependency-injection, and architecture-boundary validation

```yaml
capability_id: CAP-TOOLSELECT-0001
status: implemented
maturity: M3
implementation_status: implemented
```

The service consumes an existing Resolver or Planner Resolution result and
returns one adapter identity, no-selection, or blocked ambiguity. It does not
load a Registry, execute an adapter, call Runtime or a Provider, rank
candidates, generate Evidence, or assemble a product.

### Knowledge Foundation Capability

```yaml
capability_id: CAP-KNOW-0001
status: implemented
maturity: M3
implementation_status: implemented
```

The standards above are the canonical discovery path for official documents,
registered knowledge, capability state, governance, and AI reference rules.
Registry metadata and its JSON projection do not replace linked Source of
Record documents. Tool Adapter execution, Runtime integration, operational
Evidence, and M4 validation remain deferred.

## Sprint 9-3 MVP

- main.py
- os_core/kernel.py
- os_core/event_bus.py
- os_core/decision_engine.py
- os_core/task_engine.py
- os_core/workflow_engine.py
- os_core/worker_manager.py
- workers/
- runtime/
- products/blog_growth_analyzer/

## Sprint 9-3 신규 기능

- CLI 기반 Task 생성
- CLI 기반 Task 목록
- CLI 기반 Task 상세 보기
- CLI 기반 Task 상태 변경
- CLI 기반 Workflow 다음 단계 이동
