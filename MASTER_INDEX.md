# AI Factory OS Master Index

## Current Architecture and Governance

### Architecture

- `docs/development/AFDE_ARCHITECTURE_v1.md` — canonical AFDE architecture,
  including the AFDE-4.7 Knowledge Foundation flow
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
Record documents. Capability Resolver and M4 validation remain deferred.

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
