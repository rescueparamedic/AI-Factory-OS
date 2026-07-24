from copy import deepcopy
import json
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
    assert len(snapshot.documents) == 12
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
