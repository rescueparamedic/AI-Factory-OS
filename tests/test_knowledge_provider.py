from pathlib import Path

import pytest

from afde.knowledge import (
    KnowledgeFoundationProvider,
    RegistryLookupError,
)


ROOT = Path(__file__).resolve().parents[1]


@pytest.fixture
def provider():
    return KnowledgeFoundationProvider(ROOT)


def test_provider_gets_document_knowledge_and_capability(provider):
    assert provider.get_document("DOC-ARCH-0001").path.endswith(
        "AFDE_ARCHITECTURE_v1.md"
    )
    assert provider.get_knowledge("KNW-KNOW-0001").status == "active"
    capability = provider.get_capability("CAP-KNOW-0001")
    assert capability.status == "implemented"
    assert capability.maturity == "M3"
    assert capability.implementation_status == "implemented"


def test_unknown_ids_fail_closed(provider):
    with pytest.raises(RegistryLookupError, match="unknown document_id"):
        provider.get_document("DOC-NO-9999")
    with pytest.raises(RegistryLookupError, match="unknown knowledge_id"):
        provider.get_knowledge("KNW-NO-9999")
    with pytest.raises(RegistryLookupError, match="unknown capability_id"):
        provider.get_capability("CAP-NO-9999")


def test_scope_and_status_filters_are_deterministic(provider):
    assert len(provider.query_documents(status="active")) == 18
    assert provider.query_documents(status="Draft") == ()

    product_knowledge = provider.query_knowledge(scope="product_layer")
    assert [item.knowledge_id for item in product_knowledge] == [
        "KNW-KNOW-0002",
        "KNW-KNOW-0003",
    ]
    assert provider.query_knowledge(status=None) == provider.snapshot.knowledge

    capabilities = provider.query_capabilities(
        scope="architecture.knowledge_foundation",
        status="IMPLEMENTED",
    )
    assert [item.capability_id for item in capabilities] == ["CAP-KNOW-0001"]


def test_reference_priority_is_stable_and_immutable(provider):
    first = provider.reference_priority()
    second = provider.reference_priority("product_layer")

    assert first is provider.snapshot.reference_priority
    assert second == first
    assert first[0] == (
        "constitutional_repository_principles_and_frozen_constraints"
    )


def test_capability_context_resolves_knowledge_sources_and_gaps(provider):
    context = provider.capability_context("CAP-KNOW-0001")

    assert context.capability.capability_id == "CAP-KNOW-0001"
    assert [item.knowledge_id for item in context.required_knowledge] == [
        "KNW-KNOW-0001",
        "KNW-KNOW-0002",
        "KNW-KNOW-0003",
    ]
    assert len(context.source_documents) == 7
    assert context.authority == ("normative",)
    assert context.status == "implemented"
    assert context.scope == "architecture.knowledge_foundation"
    assert [gap.gap_type for gap in context.gaps] == [
        "capability_gap",
        "evidence_gap",
    ]
    assert provider.gaps("CAP-KNOW-0001") == context.gaps


def test_context_reports_valid_scope_gaps_without_selecting_implementation(
    provider,
):
    context = provider.capability_context(
        "CAP-KNOW-0001", scope="public_contract.beta_execute",
    )

    messages = [gap.message for gap in context.gaps]
    assert any("capability is outside scope" in message for message in messages)
    assert any("required knowledge is outside scope" in message for message in messages)
    assert context.capability.adapter_dependencies == ()
    assert context.capability.tool_dependencies == ()
    assert context.capability.runtime_dependencies == ()


@pytest.mark.parametrize("method", ["query_documents", "query_knowledge", "query_capabilities"])
def test_query_rejects_empty_scope(provider, method):
    with pytest.raises(ValueError, match="scope must be a non-empty string"):
        getattr(provider, method)(scope=" ")
