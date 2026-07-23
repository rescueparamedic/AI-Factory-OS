from dataclasses import FrozenInstanceError
import json
from pathlib import Path

import pytest

from afde.knowledge.models import KnowledgeFoundationSnapshot


ROOT = Path(__file__).resolve().parents[1]
REGISTRY = ROOT / "docs" / "registry" / "KNOWLEDGE_FOUNDATION_REGISTRY_v1.json"


def _data():
    return json.loads(REGISTRY.read_text(encoding="utf-8"))


def test_snapshot_models_are_frozen_and_nested_collections_are_tuples():
    snapshot = KnowledgeFoundationSnapshot.from_value(_data())

    with pytest.raises(FrozenInstanceError):
        snapshot.schema_version = "2.0"

    assert isinstance(snapshot.documents, tuple)
    assert isinstance(snapshot.documents[0].supersedes, tuple)
    assert isinstance(snapshot.knowledge[0].source_documents, tuple)
    assert isinstance(snapshot.capabilities[0].known_gaps, tuple)


def test_snapshot_defensively_copies_input_sequences():
    value = _data()
    snapshot = KnowledgeFoundationSnapshot.from_value(value)

    value["documents"].clear()
    value["knowledge"][0]["source_documents"].clear()
    value["capabilities"][0]["required_knowledge"].clear()

    assert len(snapshot.documents) == 12
    assert len(snapshot.knowledge[0].source_documents) == 2
    assert snapshot.capabilities[0].required_knowledge == (
        "KNW-KNOW-0001",
        "KNW-KNOW-0002",
        "KNW-KNOW-0003",
    )


def test_snapshot_rejects_missing_and_unknown_fields():
    missing = _data()
    missing.pop("documents")
    with pytest.raises(ValueError, match="missing fields: documents"):
        KnowledgeFoundationSnapshot.from_value(missing)

    unknown = _data()
    unknown["execution"] = {}
    with pytest.raises(ValueError, match="unknown fields: execution"):
        KnowledgeFoundationSnapshot.from_value(unknown)


def test_snapshot_rejects_string_in_place_of_array():
    value = _data()
    value["authority_levels"] = "normative"
    with pytest.raises(TypeError, match="authority_levels must be an array"):
        KnowledgeFoundationSnapshot.from_value(value)
