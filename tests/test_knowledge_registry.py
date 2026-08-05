import json
from copy import deepcopy
from pathlib import Path

import pytest

from afde.knowledge import (
    KnowledgeRegistryLoader,
    RegistryLoadError,
    RegistryNotFoundError,
    RegistryPathError,
    RegistryValidationError,
)

ROOT = Path(__file__).resolve().parents[1]
REGISTRY = ROOT / "docs" / "registry" / "KNOWLEDGE_FOUNDATION_REGISTRY_v1.json"


def _data():
    return json.loads(REGISTRY.read_text(encoding="utf-8"))


def _write_registry(root: Path, value: dict) -> Path:
    for document in value.get("documents", []):
        path = root / Path(document["path"])
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(f"# {document['title']}\n", encoding="utf-8")
    registry = root / "docs" / "registry" / REGISTRY.name
    registry.parent.mkdir(parents=True, exist_ok=True)
    registry.write_text(
        json.dumps(value, ensure_ascii=False, indent=2),
        encoding="utf-8",
    )
    return registry


def _load(root: Path, value: dict):
    _write_registry(root, value)
    return KnowledgeRegistryLoader(root).load()


def test_valid_registry_loads_all_three_projections():
    snapshot = KnowledgeRegistryLoader(ROOT).load()

    assert snapshot.schema_version == "1.0"
    assert len(snapshot.documents) == 20
    assert [item.knowledge_id for item in snapshot.knowledge] == [
        "KNW-KNOW-0001",
        "KNW-KNOW-0002",
        "KNW-KNOW-0003",
    ]
    assert [item.capability_id for item in snapshot.capabilities] == [
        "CAP-KNOW-0001",
        "CAP-RESOLVER-0001",
        "CAP-PLANRES-0001",
        "CAP-TOOLSELECT-0001",
        "CAP-TOOLCATALOG-0001",
        "CAP-EXECPATH-0001",
        "CAP-RUNTIME-0001",
        "CAP-TOOLADAPTER-CONTRACT-0001",
        "CAP-COMPOSITION-0001",
        "CAP-ADAPTERREGISTRY-0001",
        "CAP-PRODUCTIONCOMPOSITION-0001",
        "CAP-PRODUCTIONADAPTERREGISTRATION-0001",
        "CAP-PRODUCTIONADAPTERDISCOVERY-0001",
        "CAP-PRODUCTIONADAPTERAVAILABILITY-0001",
        "CAP-PRODUCTIONADAPTERCREDENTIALREADINESS-0001",
        "CAP-PRODUCTIONADAPTERCREATION-0001",
        "CAP-PRODUCTIONADAPTERINVOCATION-0001",
        "CAP-PRODUCTIONADAPTERRUNTIMESTARTUPINTEGRATION-0001",
        "CAP-PRODUCTIONADAPTERRUNTIMEEXECUTION-0001",
        "CAP-PRODUCTIONADAPTERWORKEREXECUTION-0001",
        "CAP-PRODUCTIONADAPTERRUNTIMEOBSERVATION-0001",
        "CAP-PRODUCTIONADAPTERRUNTIMEEVENTCOLLECTION-0001",
        "CAP-POWERSHELLMERGEAUTOMATIONSTANDARD-0001",
    ]


def test_tool_selection_capability_is_registered_at_m3_only():
    snapshot = KnowledgeRegistryLoader(ROOT).load()
    capability = next(
        item for item in snapshot.capabilities
        if item.capability_id == "CAP-TOOLSELECT-0001"
    )

    assert capability.status == "implemented"
    assert capability.maturity == "M3"
    assert capability.implementation_status == "implemented"
    assert capability.required_capabilities == ("CAP-PLANRES-0001",)
    assert capability.runtime_dependencies == ()
    assert capability.implementation_references == (
        "afde/tool_selection/errors.py",
        "afde/tool_selection/models.py",
        "afde/tool_selection/service.py",
    )


def test_tool_catalog_capability_and_standard_are_registered_at_m3_only():
    snapshot = KnowledgeRegistryLoader(ROOT).load()
    capability = next(
        item for item in snapshot.capabilities
        if item.capability_id == "CAP-TOOLCATALOG-0001"
    )
    standard = next(
        item for item in snapshot.documents
        if item.document_id == "DOC-TCAT-0001"
    )

    assert capability.status == "implemented"
    assert capability.maturity == "M3"
    assert capability.implementation_status == "implemented"
    assert capability.runtime_dependencies == ()
    assert capability.implementation_references == (
        "afde/tool_catalog/errors.py",
        "afde/tool_catalog/models.py",
        "afde/tool_catalog/catalog.py",
    )
    assert standard.path == (
        "docs/standards/TOOL_ADAPTER_CATALOG_STANDARD_v1.md"
    )
    assert standard.capability_ids == ("CAP-TOOLCATALOG-0001",)


def test_execution_path_capability_and_standard_are_registered_at_m3_only():
    snapshot = KnowledgeRegistryLoader(ROOT).load()
    capability = next(
        item for item in snapshot.capabilities
        if item.capability_id == "CAP-EXECPATH-0001"
    )
    standard = next(
        item for item in snapshot.documents
        if item.document_id == "DOC-EXEP-0001"
    )

    assert capability.status == "implemented"
    assert capability.maturity == "M3"
    assert capability.implementation_status == "implemented"
    assert capability.required_capabilities == (
        "CAP-TOOLSELECT-0001",
        "CAP-TOOLCATALOG-0001",
    )
    assert capability.runtime_dependencies == ()
    assert capability.implementation_references == (
        "afde/execution_path/errors.py",
        "afde/execution_path/models.py",
        "afde/execution_path/service.py",
    )
    assert standard.path == (
        "docs/standards/EXECUTION_PATH_STANDARD_v1.md"
    )
    assert standard.capability_ids == ("CAP-EXECPATH-0001",)


def test_runtime_integration_capability_and_standard_are_registered_at_m3_only():
    snapshot = KnowledgeRegistryLoader(ROOT).load()
    capability = next(
        item for item in snapshot.capabilities
        if item.capability_id == "CAP-RUNTIME-0001"
    )
    standard = next(
        item for item in snapshot.documents
        if item.document_id == "DOC-RUNTIME-0001"
    )

    assert capability.status == "implemented"
    assert capability.maturity == "M3"
    assert capability.implementation_status == "implemented"
    assert capability.required_capabilities == ("CAP-EXECPATH-0001",)
    assert capability.runtime_dependencies == ()
    assert capability.implementation_references == (
        "afde/runtime_integration/errors.py",
        "afde/runtime_integration/models.py",
        "afde/runtime_integration/service.py",
    )
    assert standard.path == (
        "docs/standards/RUNTIME_INTEGRATION_STANDARD_v1.md"
    )
    assert standard.capability_ids == ("CAP-RUNTIME-0001",)


def test_tool_adapter_contract_capability_and_standard_are_registered_at_m3():
    snapshot = KnowledgeRegistryLoader(ROOT).load()
    capability = next(
        item for item in snapshot.capabilities
        if item.capability_id == "CAP-TOOLADAPTER-CONTRACT-0001"
    )
    standard = next(
        item for item in snapshot.documents
        if item.document_id == "DOC-TOOLCONTRACT-0001"
    )

    assert capability.status == "implemented"
    assert capability.maturity == "M3"
    assert capability.implementation_status == "implemented"
    assert capability.required_capabilities == (
        "CAP-RUNTIME-0001",
        "CAP-TOOLCATALOG-0001",
    )
    assert capability.runtime_dependencies == ()
    assert capability.implementation_references == (
        "afde/tool_adapter_contract/errors.py",
        "afde/tool_adapter_contract/models.py",
        "afde/tool_adapter_contract/service.py",
    )
    assert standard.path == (
        "docs/standards/TOOL_ADAPTER_EXECUTION_CONTRACT_STANDARD_v1.md"
    )
    assert standard.capability_ids == (
        "CAP-TOOLADAPTER-CONTRACT-0001",
    )


def test_non_executable_composition_is_registered_at_m3_only():
    snapshot = KnowledgeRegistryLoader(ROOT).load()
    capability = next(
        item for item in snapshot.capabilities
        if item.capability_id == "CAP-COMPOSITION-0001"
    )
    standard = next(
        item for item in snapshot.documents
        if item.document_id == "DOC-COMPOSITION-0001"
    )

    assert capability.status == "implemented"
    assert capability.maturity == "M3"
    assert capability.implementation_status == "implemented"
    assert capability.required_capabilities == (
        "CAP-PLANRES-0001",
        "CAP-TOOLSELECT-0001",
        "CAP-TOOLCATALOG-0001",
        "CAP-EXECPATH-0001",
        "CAP-RUNTIME-0001",
        "CAP-TOOLADAPTER-CONTRACT-0001",
    )
    assert capability.tool_dependencies == ()
    assert capability.runtime_dependencies == ()
    assert capability.implementation_references == (
        "afde/non_executable_composition/__init__.py",
        "afde/non_executable_composition/models.py",
        "afde/non_executable_composition/factory.py",
    )
    assert standard.path == (
        "docs/standards/NON_EXECUTABLE_COMPOSITION_STANDARD_v1.md"
    )
    assert standard.capability_ids == (
        "CAP-COMPOSITION-0001",
        "CAP-PRODUCTIONCOMPOSITION-0001",
    )


def test_operational_adapter_registry_is_registered_at_m3_only():
    snapshot = KnowledgeRegistryLoader(ROOT).load()
    capability = next(
        item for item in snapshot.capabilities
        if item.capability_id == "CAP-ADAPTERREGISTRY-0001"
    )
    architecture = next(
        item for item in snapshot.documents
        if item.document_id == "DOC-ARCH-0001"
    )
    standard = next(
        item for item in snapshot.documents
        if item.document_id == "DOC-CREG-0001"
    )

    assert capability.status == "implemented"
    assert capability.maturity == "M3"
    assert capability.implementation_status == "implemented"
    assert capability.required_capabilities == (
        "CAP-TOOLCATALOG-0001",
    )
    assert capability.tool_dependencies == ()
    assert capability.runtime_dependencies == ()
    assert capability.implementation_references == (
        "afde/operational_adapter_registry/__init__.py",
        "afde/operational_adapter_registry/registry.py",
    )
    assert "CAP-ADAPTERREGISTRY-0001" in architecture.capability_ids
    assert "CAP-ADAPTERREGISTRY-0001" in standard.capability_ids


def test_production_composition_is_registered_at_m3_only():
    snapshot = KnowledgeRegistryLoader(ROOT).load()
    capability = next(
        item for item in snapshot.capabilities
        if item.capability_id == "CAP-PRODUCTIONCOMPOSITION-0001"
    )
    architecture = next(
        item for item in snapshot.documents
        if item.document_id == "DOC-ARCH-0001"
    )
    standard = next(
        item for item in snapshot.documents
        if item.document_id == "DOC-CREG-0001"
    )
    composition_standard = next(
        item for item in snapshot.documents
        if item.document_id == "DOC-COMPOSITION-0001"
    )

    assert capability.status == "implemented"
    assert capability.maturity == "M3"
    assert capability.implementation_status == "implemented"
    assert capability.required_capabilities == (
        "CAP-COMPOSITION-0001",
        "CAP-ADAPTERREGISTRY-0001",
    )
    assert capability.tool_dependencies == ()
    assert capability.runtime_dependencies == ()
    assert capability.implementation_references == (
        "afde/production_composition/__init__.py",
        "afde/production_composition/factory.py",
    )
    assert "CAP-PRODUCTIONCOMPOSITION-0001" in architecture.capability_ids
    assert "CAP-PRODUCTIONCOMPOSITION-0001" in standard.capability_ids
    assert (
        "CAP-PRODUCTIONCOMPOSITION-0001"
        in composition_standard.capability_ids
    )


def test_production_adapter_registration_has_reciprocal_m3_binding():
    snapshot = KnowledgeRegistryLoader(ROOT).load()
    capability = next(
        item for item in snapshot.capabilities
        if item.capability_id
        == "CAP-PRODUCTIONADAPTERREGISTRATION-0001"
    )
    documents = {
        item.document_id: item for item in snapshot.documents
    }

    assert capability.status == "implemented"
    assert capability.maturity == "M3"
    assert capability.implementation_status == "implemented"
    assert capability.required_capabilities == (
        "CAP-ADAPTERREGISTRY-0001",
    )
    assert capability.tool_dependencies == ()
    assert capability.runtime_dependencies == ()
    assert capability.implementation_references == (
        "afde/production_adapter_registration/__init__.py",
        "afde/production_adapter_registration/factory.py",
    )
    assert capability.source_documents == (
        "DOC-ARCH-0001",
        "DOC-CREG-0001",
        "DOC-PADREG-0001",
    )
    for document_id in capability.source_documents:
        assert (
            "CAP-PRODUCTIONADAPTERREGISTRATION-0001"
            in documents[document_id].capability_ids
        )
    assert documents["DOC-PADREG-0001"].path == (
        "docs/standards/PRODUCTION_ADAPTER_REGISTRATION_STANDARD_v1.md"
    )


def test_production_adapter_discovery_has_reciprocal_m3_binding():
    snapshot = KnowledgeRegistryLoader(ROOT).load()
    capability = next(
        item for item in snapshot.capabilities
        if item.capability_id
        == "CAP-PRODUCTIONADAPTERDISCOVERY-0001"
    )
    documents = {
        item.document_id: item for item in snapshot.documents
    }

    assert capability.status == "implemented"
    assert capability.maturity == "M3"
    assert capability.implementation_status == "implemented"
    assert capability.required_capabilities == (
        "CAP-PRODUCTIONADAPTERREGISTRATION-0001",
        "CAP-ADAPTERREGISTRY-0001",
    )
    assert capability.runtime_dependencies == ()
    assert capability.implementation_references == (
        "afde/production_adapter_discovery/__init__.py",
        "afde/production_adapter_discovery/errors.py",
        "afde/production_adapter_discovery/models.py",
        "afde/production_adapter_discovery/discovery.py",
    )
    assert capability.source_documents == (
        "DOC-ARCH-0001",
        "DOC-CREG-0001",
        "DOC-PADDISC-0001",
    )
    for document_id in capability.source_documents:
        assert (
            "CAP-PRODUCTIONADAPTERDISCOVERY-0001"
            in documents[document_id].capability_ids
        )
    assert documents["DOC-PADDISC-0001"].path == (
        "docs/standards/PRODUCTION_ADAPTER_DISCOVERY_STANDARD_v1.md"
    )


def test_production_adapter_availability_has_reciprocal_m3_binding():
    snapshot = KnowledgeRegistryLoader(ROOT).load()
    capability = next(
        item for item in snapshot.capabilities
        if item.capability_id
        == "CAP-PRODUCTIONADAPTERAVAILABILITY-0001"
    )
    documents = {
        item.document_id: item for item in snapshot.documents
    }

    assert capability.status == "implemented"
    assert capability.maturity == "M3"
    assert capability.implementation_status == "implemented"
    assert capability.required_capabilities == (
        "CAP-PRODUCTIONADAPTERDISCOVERY-0001",
        "CAP-PRODUCTIONADAPTERREGISTRATION-0001",
        "CAP-ADAPTERREGISTRY-0001",
        "CAP-TOOLCATALOG-0001",
        "CAP-EXECPATH-0001",
        "CAP-RUNTIME-0001",
    )
    assert capability.runtime_dependencies == (
        "existing non-executable ExecutionPathService compatibility",
        "existing RuntimeProjection compatibility",
        "existing RuntimeIntegrationPolicy compatibility",
    )
    assert capability.implementation_references == (
        "afde/production_adapter_availability/__init__.py",
        "afde/production_adapter_availability/errors.py",
        "afde/production_adapter_availability/models.py",
        "afde/production_adapter_availability/service.py",
    )
    assert capability.source_documents == ("DOC-CREG-0001",)
    assert (
        "CAP-PRODUCTIONADAPTERAVAILABILITY-0001"
        in documents["DOC-CREG-0001"].capability_ids
    )


def test_production_adapter_credential_readiness_has_reciprocal_m3_binding():
    snapshot = KnowledgeRegistryLoader(ROOT).load()
    capability = next(
        item for item in snapshot.capabilities
        if item.capability_id
        == "CAP-PRODUCTIONADAPTERCREDENTIALREADINESS-0001"
    )
    documents = {
        item.document_id: item for item in snapshot.documents
    }

    assert capability.status == "implemented"
    assert capability.maturity == "M3"
    assert capability.implementation_status == "implemented"
    assert capability.required_capabilities == (
        "CAP-PRODUCTIONADAPTERDISCOVERY-0001",
        "CAP-PRODUCTIONADAPTERAVAILABILITY-0001",
        "CAP-PRODUCTIONADAPTERREGISTRATION-0001",
        "CAP-ADAPTERREGISTRY-0001",
        "CAP-TOOLCATALOG-0001",
        "CAP-EXECPATH-0001",
        "CAP-RUNTIME-0001",
    )
    assert capability.runtime_dependencies == (
        "existing non-executable ExecutionPathService compatibility",
        "existing RuntimeHandoffProjection compatibility",
        "existing RuntimeProjection compatibility",
        "existing RuntimeIntegrationPolicy compatibility",
    )
    assert capability.implementation_references == (
        "afde/production_adapter_credential_readiness/__init__.py",
        "afde/production_adapter_credential_readiness/errors.py",
        "afde/production_adapter_credential_readiness/models.py",
        "afde/production_adapter_credential_readiness/service.py",
    )
    assert capability.source_documents == ("DOC-CREG-0001",)
    assert (
        "CAP-PRODUCTIONADAPTERCREDENTIALREADINESS-0001"
        in documents["DOC-CREG-0001"].capability_ids
    )


def test_production_adapter_creation_has_reciprocal_m3_binding():
    snapshot = KnowledgeRegistryLoader(ROOT).load()
    capability = next(
        item for item in snapshot.capabilities
        if item.capability_id == "CAP-PRODUCTIONADAPTERCREATION-0001"
    )
    documents = {
        item.document_id: item for item in snapshot.documents
    }

    assert capability.status == "implemented"
    assert capability.maturity == "M3"
    assert capability.implementation_status == "implemented"
    assert capability.required_capabilities == (
        "CAP-PRODUCTIONADAPTERDISCOVERY-0001",
        "CAP-PRODUCTIONADAPTERREGISTRATION-0001",
        "CAP-PRODUCTIONADAPTERAVAILABILITY-0001",
        "CAP-PRODUCTIONADAPTERCREDENTIALREADINESS-0001",
        "CAP-ADAPTERREGISTRY-0001",
        "CAP-TOOLCATALOG-0001",
        "CAP-TOOLADAPTER-CONTRACT-0001",
        "CAP-EXECPATH-0001",
        "CAP-RUNTIME-0001",
    )
    assert capability.runtime_dependencies == (
        "existing non-executable Execution Path compatibility",
        "existing Runtime Projection compatibility",
        "existing Tool Adapter Binding compatibility",
    )
    assert capability.implementation_references == (
        "afde/production_adapter_creation/__init__.py",
        "afde/production_adapter_creation/errors.py",
        "afde/production_adapter_creation/models.py",
        "afde/production_adapter_creation/service.py",
    )
    assert capability.source_documents == ("DOC-CREG-0001",)
    assert (
        "CAP-PRODUCTIONADAPTERCREATION-0001"
        in documents["DOC-CREG-0001"].capability_ids
    )


def test_production_adapter_invocation_has_reciprocal_m3_binding():
    snapshot = KnowledgeRegistryLoader(ROOT).load()
    capability = next(
        item for item in snapshot.capabilities
        if item.capability_id
        == "CAP-PRODUCTIONADAPTERINVOCATION-0001"
    )
    documents = {
        item.document_id: item for item in snapshot.documents
    }

    assert capability.status == "implemented"
    assert capability.maturity == "M3"
    assert capability.implementation_status == "implemented"
    assert capability.required_capabilities == (
        "CAP-PRODUCTIONADAPTERCREATION-0001",
        "CAP-PRODUCTIONADAPTERAVAILABILITY-0001",
        "CAP-PRODUCTIONADAPTERCREDENTIALREADINESS-0001",
        "CAP-TOOLADAPTER-CONTRACT-0001",
        "CAP-TOOLCATALOG-0001",
        "CAP-EXECPATH-0001",
        "CAP-RUNTIME-0001",
    )
    assert capability.runtime_dependencies == (
        "existing non-executable Execution Path compatibility",
        "existing Runtime Projection compatibility",
        "existing Tool Adapter Binding compatibility",
    )
    assert capability.implementation_references == (
        "afde/production_adapter_invocation/__init__.py",
        "afde/production_adapter_invocation/errors.py",
        "afde/production_adapter_invocation/models.py",
        "afde/production_adapter_invocation/service.py",
    )
    assert capability.source_documents == ("DOC-CREG-0001",)
    assert (
        "CAP-PRODUCTIONADAPTERINVOCATION-0001"
        in documents["DOC-CREG-0001"].capability_ids
    )


def test_production_adapter_runtime_startup_has_reciprocal_m3_binding():
    snapshot = KnowledgeRegistryLoader(ROOT).load()
    capability = next(
        item for item in snapshot.capabilities
        if item.capability_id
        == "CAP-PRODUCTIONADAPTERRUNTIMESTARTUPINTEGRATION-0001"
    )
    documents = {item.document_id: item for item in snapshot.documents}

    assert capability.status == "implemented"
    assert capability.maturity == "M3"
    assert capability.implementation_status == "implemented"
    assert capability.required_capabilities == (
        "CAP-PRODUCTIONCOMPOSITION-0001",
        "CAP-PRODUCTIONADAPTERDISCOVERY-0001",
        "CAP-PRODUCTIONADAPTERAVAILABILITY-0001",
        "CAP-PRODUCTIONADAPTERCREDENTIALREADINESS-0001",
        "CAP-PRODUCTIONADAPTERCREATION-0001",
        "CAP-PRODUCTIONADAPTERINVOCATION-0001",
    )
    assert capability.tool_dependencies == ()
    assert capability.runtime_dependencies == (
        "existing non-executable production composition compatibility",
        "existing immutable Runtime policy compatibility",
    )
    assert capability.implementation_references == (
        "afde/production_adapter_runtime_startup_integration/__init__.py",
        "afde/production_adapter_runtime_startup_integration/errors.py",
        "afde/production_adapter_runtime_startup_integration/models.py",
        "afde/production_adapter_runtime_startup_integration/factory.py",
    )
    assert capability.source_documents == ("DOC-CREG-0001",)
    assert (
        capability.capability_id
        in documents["DOC-CREG-0001"].capability_ids
    )


def test_production_adapter_runtime_execution_has_reciprocal_m3_binding():
    snapshot = KnowledgeRegistryLoader(ROOT).load()
    capability = next(
        item for item in snapshot.capabilities
        if item.capability_id
        == "CAP-PRODUCTIONADAPTERRUNTIMEEXECUTION-0001"
    )
    documents = {item.document_id: item for item in snapshot.documents}

    assert capability.status == "implemented"
    assert capability.maturity == "M3"
    assert capability.implementation_status == "implemented"
    assert capability.required_capabilities == (
        "CAP-PRODUCTIONADAPTERREGISTRATION-0001",
        "CAP-PRODUCTIONADAPTERDISCOVERY-0001",
        "CAP-PRODUCTIONADAPTERAVAILABILITY-0001",
        "CAP-PRODUCTIONADAPTERCREDENTIALREADINESS-0001",
        "CAP-PRODUCTIONADAPTERCREATION-0001",
        "CAP-PRODUCTIONADAPTERINVOCATION-0001",
        "CAP-PRODUCTIONADAPTERRUNTIMESTARTUPINTEGRATION-0001",
    )
    assert capability.tool_dependencies == ()
    assert capability.runtime_dependencies == (
        "explicit immutable Runtime execution authority identity",
        "process-local atomic single-use authority consumption",
        "existing Runtime projection identity compatibility",
        "existing Runtime lifecycle ownership unchanged",
    )
    assert capability.implementation_references == (
        "afde/production_adapter_runtime_execution/__init__.py",
        "afde/production_adapter_runtime_execution/errors.py",
        "afde/production_adapter_runtime_execution/models.py",
        "afde/production_adapter_runtime_execution/service.py",
    )
    assert capability.source_documents == ("DOC-CREG-0001",)
    assert (
        capability.capability_id
        in documents["DOC-CREG-0001"].capability_ids
    )


def test_production_adapter_worker_execution_has_reciprocal_m3_binding():
    snapshot = KnowledgeRegistryLoader(ROOT).load()
    capability = next(
        item for item in snapshot.capabilities
        if item.capability_id
        == "CAP-PRODUCTIONADAPTERWORKEREXECUTION-0001"
    )
    documents = {item.document_id: item for item in snapshot.documents}

    assert capability.status == "implemented"
    assert capability.maturity == "M3"
    assert capability.implementation_status == "implemented"
    assert capability.required_capabilities == (
        "CAP-PRODUCTIONADAPTERRUNTIMEEXECUTION-0001",
    )
    assert capability.tool_dependencies == ()
    assert capability.runtime_dependencies == (
        "existing single-use Production Adapter Runtime execution boundary",
        "existing Worker and Runtime lifecycle ownership unchanged",
    )
    assert capability.implementation_references == (
        "afde/production_adapter_worker_execution/__init__.py",
        "afde/production_adapter_worker_execution/errors.py",
        "afde/production_adapter_worker_execution/models.py",
        "afde/production_adapter_worker_execution/service.py",
    )
    assert capability.source_documents == ("DOC-CREG-0001",)
    assert (
        capability.capability_id
        in documents["DOC-CREG-0001"].capability_ids
    )


def test_production_adapter_runtime_observation_has_reciprocal_m3_binding():
    snapshot = KnowledgeRegistryLoader(ROOT).load()
    capability = next(
        item for item in snapshot.capabilities
        if item.capability_id
        == "CAP-PRODUCTIONADAPTERRUNTIMEOBSERVATION-0001"
    )
    documents = {item.document_id: item for item in snapshot.documents}

    assert capability.status == "implemented"
    assert capability.maturity == "M3"
    assert capability.implementation_status == "implemented"
    assert capability.required_capabilities == (
        "CAP-PRODUCTIONADAPTERRUNTIMEEXECUTION-0001",
        "CAP-PRODUCTIONADAPTERWORKEREXECUTION-0001",
    )
    assert capability.tool_dependencies == ()
    assert capability.runtime_dependencies == (
        "caller-supplied completed execution evidence",
        "existing Worker and Runtime execution behavior unchanged",
    )
    assert capability.implementation_references == (
        "afde/production_adapter_runtime_observation/__init__.py",
        "afde/production_adapter_runtime_observation/errors.py",
        "afde/production_adapter_runtime_observation/models.py",
        "afde/production_adapter_runtime_observation/service.py",
    )
    assert capability.source_documents == ("DOC-CREG-0001",)
    assert (
        capability.capability_id
        in documents["DOC-CREG-0001"].capability_ids
    )


def test_production_adapter_runtime_event_collection_has_reciprocal_m3_binding():
    snapshot = KnowledgeRegistryLoader(ROOT).load()
    capability = next(
        item for item in snapshot.capabilities
        if item.capability_id
        == "CAP-PRODUCTIONADAPTERRUNTIMEEVENTCOLLECTION-0001"
    )
    documents = {item.document_id: item for item in snapshot.documents}

    assert capability.name == (
        "Production Adapter Runtime Event Collection Foundation"
    )
    assert capability.status == "implemented"
    assert capability.maturity == "M3"
    assert capability.implementation_status == "implemented"
    assert capability.required_capabilities == ()
    assert capability.tool_dependencies == ()
    assert capability.adapter_dependencies == ()
    assert capability.runtime_dependencies == (
        "caller-supplied immutable Runtime events and collection timestamp",
        "existing Runtime Observation, Runtime Execution, and Worker Execution "
        + "behavior unchanged",
    )
    assert capability.implementation_references == (
        "afde/production_adapter_runtime_event_collection/__init__.py",
        "afde/production_adapter_runtime_event_collection/errors.py",
        "afde/production_adapter_runtime_event_collection/models.py",
        "afde/production_adapter_runtime_event_collection/service.py",
    )
    gaps = " ".join(item.message for item in capability.known_gaps)
    for excluded in (
        "Runtime Event Stream",
        "Runtime History",
        "persistence",
        "background collection",
        "metrics",
        "telemetry",
    ):
        assert excluded.lower() in gaps.lower()
    assert capability.source_documents == ("DOC-CREG-0001",)
    assert (
        capability.capability_id
        in documents["DOC-CREG-0001"].capability_ids
    )


def test_powershell_merge_automation_has_reciprocal_m3_binding():
    snapshot = KnowledgeRegistryLoader(ROOT).load()
    capability = next(
        item for item in snapshot.capabilities
        if item.capability_id
        == "CAP-POWERSHELLMERGEAUTOMATIONSTANDARD-0001"
    )
    documents = {item.document_id: item for item in snapshot.documents}

    assert capability.status == "implemented"
    assert capability.maturity == "M3"
    assert capability.implementation_status == "implemented"
    assert capability.required_capabilities == ()
    assert capability.tool_dependencies == (
        "Git CLI",
        "GitHub CLI",
        "Windows PowerShell 5.1 or PowerShell 7",
    )
    assert capability.adapter_dependencies == ()
    assert capability.runtime_dependencies == ()
    assert capability.implementation_references == (
        "scripts/Invoke-AfdeMergeAutomation.ps1",
        "docs/standards/POWERSHELL_MERGE_AUTOMATION_STANDARD_v1.md",
    )
    assert capability.source_documents == (
        "DOC-CREG-0001",
        "DOC-PSMERGE-0001",
    )
    for document_id in capability.source_documents:
        assert capability.capability_id in documents[document_id].capability_ids


def test_missing_and_malformed_registry_fail_closed(tmp_path):
    with pytest.raises(RegistryNotFoundError):
        KnowledgeRegistryLoader(tmp_path).load()

    registry = tmp_path / "docs" / "registry" / REGISTRY.name
    registry.parent.mkdir(parents=True)
    registry.write_text("{not-json", encoding="utf-8")
    with pytest.raises(RegistryLoadError, match="malformed"):
        KnowledgeRegistryLoader(tmp_path).load()


def test_registry_path_escape_is_rejected(tmp_path):
    repository = tmp_path / "repository"
    repository.mkdir()
    outside = tmp_path / "outside.json"
    outside.write_text("{}", encoding="utf-8")

    with pytest.raises(RegistryPathError, match="escapes repository"):
        KnowledgeRegistryLoader(repository, outside)


def test_unsupported_schema_and_duplicate_ids_are_rejected(tmp_path):
    unsupported = _data()
    unsupported["schema_version"] = "2.0"
    with pytest.raises(RegistryValidationError, match="unsupported schema_version"):
        _load(tmp_path / "unsupported", unsupported)

    duplicate = _data()
    duplicate["documents"].append(deepcopy(duplicate["documents"][0]))
    with pytest.raises(RegistryValidationError, match="duplicate document id"):
        _load(tmp_path / "duplicate", duplicate)


@pytest.mark.parametrize(
    ("collection", "field", "value", "message"),
    [
        ("documents", "status", "Unknown", "invalid status"),
        ("documents", "document_type", "unknown", "invalid document_type"),
        ("knowledge", "status", "unknown", "invalid status"),
        ("knowledge", "knowledge_type", "unknown", "invalid knowledge_type"),
        ("capabilities", "status", "unknown", "invalid status"),
        ("capabilities", "maturity", "M9", "invalid maturity"),
        (
            "capabilities",
            "implementation_status",
            "unknown",
            "invalid implementation_status",
        ),
    ],
)
def test_invalid_enums_are_rejected(
    tmp_path, collection, field, value, message,
):
    data = _data()
    data[collection][0][field] = value
    with pytest.raises(RegistryValidationError, match=message):
        _load(tmp_path / f"{collection}-{field}", data)


def test_authority_order_and_binding_reciprocity_are_enforced(tmp_path):
    authority = _data()
    authority["authority_levels"][0:2] = reversed(
        authority["authority_levels"][0:2]
    )
    with pytest.raises(RegistryValidationError, match="governed priority order"):
        _load(tmp_path / "authority", authority)

    document_to_knowledge = _data()
    document_to_knowledge["documents"][0]["knowledge_ids"] = []
    with pytest.raises(
        RegistryValidationError, match="source binding is not reciprocal",
    ):
        _load(tmp_path / "document-knowledge", document_to_knowledge)

    knowledge_to_capability = _data()
    knowledge_to_capability["knowledge"][0]["capability_bindings"] = []
    with pytest.raises(
        RegistryValidationError,
        match="required knowledge binding is not reciprocal",
    ):
        _load(tmp_path / "knowledge-capability", knowledge_to_capability)

    document_to_capability = _data()
    document_to_capability["documents"][0]["capability_ids"] = []
    with pytest.raises(
        RegistryValidationError, match="source binding is not reciprocal",
    ):
        _load(tmp_path / "document-capability", document_to_capability)


def test_missing_source_and_unknown_bindings_are_rejected(tmp_path):
    source = _data()
    source["knowledge"][0]["source_documents"][0]["document_id"] = "DOC-NO-9999"
    with pytest.raises(RegistryValidationError, match="unknown source document"):
        _load(tmp_path / "source", source)

    knowledge = _data()
    knowledge["capabilities"][0]["required_knowledge"] = ["KNW-NO-9999"]
    with pytest.raises(RegistryValidationError, match="unknown required_knowledge"):
        _load(tmp_path / "knowledge", knowledge)

    capability = _data()
    capability["knowledge"][0]["capability_bindings"][0][
        "capability_id"
    ] = "CAP-NO-9999"
    with pytest.raises(RegistryValidationError, match="unknown capability binding"):
        _load(tmp_path / "capability", capability)

    related = _data()
    related["capabilities"][0]["known_gaps"][0]["related_ids"] = [
        "CAP-NO-9999"
    ]
    with pytest.raises(RegistryValidationError, match="unknown related_id"):
        _load(tmp_path / "related", related)


def test_missing_and_escaping_source_paths_are_rejected(tmp_path):
    missing = _data()
    missing["documents"][0]["path"] = "docs/missing.md"
    root = tmp_path / "missing"
    _write_registry(root, missing)
    (root / "docs" / "missing.md").unlink()
    with pytest.raises(RegistryValidationError, match="source path is missing"):
        KnowledgeRegistryLoader(root).load()

    escaping = _data()
    escaping["documents"][0]["path"] = "../outside.md"
    with pytest.raises(RegistryValidationError, match="source path escapes"):
        _load(tmp_path / "escaping", escaping)


def test_source_symlink_escape_is_rejected_when_supported(tmp_path):
    data = _data()
    root = tmp_path / "repository"
    _write_registry(root, data)
    source = root / data["documents"][0]["path"]
    outside = tmp_path / "outside.md"
    outside.write_text("# Outside\n", encoding="utf-8")
    source.unlink()
    try:
        source.symlink_to(outside)
    except OSError:
        pytest.skip("filesystem does not permit test symlink creation")

    with pytest.raises(RegistryValidationError, match="source path escapes"):
        KnowledgeRegistryLoader(root).load()


def test_conflict_symmetry_and_self_reference_are_rejected(tmp_path):
    conflict = _data()
    conflict["knowledge"][0]["conflicts_with"] = ["KNW-KNOW-0002"]
    with pytest.raises(RegistryValidationError, match="conflict is not symmetric"):
        _load(tmp_path / "conflict", conflict)

    self_reference = _data()
    self_reference["knowledge"][0]["supersedes"] = ["KNW-KNOW-0001"]
    with pytest.raises(RegistryValidationError, match="self-reference"):
        _load(tmp_path / "self", self_reference)


def test_supersession_and_required_capability_cycles_are_rejected(tmp_path):
    supersession = _data()
    supersession["knowledge"][0]["supersedes"] = ["KNW-KNOW-0002"]
    supersession["knowledge"][1]["supersedes"] = ["KNW-KNOW-0001"]
    with pytest.raises(RegistryValidationError, match="supersession cycle"):
        _load(tmp_path / "supersession", supersession)

    dependency = _data()
    second = deepcopy(dependency["capabilities"][0])
    second.update({
        "capability_id": "CAP-KNOW-0002",
        "name": "Cycle fixture",
        "status": "defined",
        "maturity": "M1",
        "implementation_status": "not_implemented",
        "required_capabilities": ["CAP-KNOW-0001"],
        "implementation_references": [],
        "validation_evidence": [],
        "known_gaps": [],
    })
    dependency["capabilities"][0]["required_capabilities"] = ["CAP-KNOW-0002"]
    dependency["capabilities"].append(second)
    with pytest.raises(RegistryValidationError, match="required capability cycle"):
        _load(tmp_path / "dependency", dependency)


def test_implementation_state_contradiction_is_rejected(tmp_path):
    data = _data()
    capability = data["capabilities"][0]
    capability["status"] = "architecture_approved"
    capability["maturity"] = "M2"
    capability["implementation_status"] = "implemented"

    with pytest.raises(RegistryValidationError, match="implemented contradicts"):
        _load(tmp_path, data)


def test_loading_does_not_change_registry_or_source_bytes():
    registry_before = REGISTRY.read_bytes()
    source = ROOT / "docs" / "development" / "AFDE_ARCHITECTURE_v1.md"
    source_before = source.read_bytes()

    KnowledgeRegistryLoader(ROOT).load()

    assert REGISTRY.read_bytes() == registry_before
    assert source.read_bytes() == source_before
