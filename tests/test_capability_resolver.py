from dataclasses import FrozenInstanceError, replace
from pathlib import Path

import pytest

from afde.knowledge import (
    KnowledgeFoundationProvider,
    KnowledgeGap,
    RegistryLookupError,
    RegistryValidationError,
)
from afde.resolver import (
    CapabilityRequirement,
    CapabilityResolutionError,
    CapabilityResolver,
    ResolutionStatus,
)


ROOT = Path(__file__).resolve().parents[1]


@pytest.fixture
def provider():
    return KnowledgeFoundationProvider(ROOT)


@pytest.fixture
def resolver(provider):
    return CapabilityResolver(provider)


def test_implemented_capability_resolves_with_complete_projection(resolver):
    result = resolver.resolve(CapabilityRequirement(
        capability_id="CAP-KNOW-0001",
        requested_scope="architecture.knowledge_foundation",
        minimum_maturity="M3",
        required_knowledge_ids=("KNW-KNOW-0001",),
    ))

    assert result.resolution_status is ResolutionStatus.RESOLVED
    assert result.eligible is True
    assert result.capability.capability_id == "CAP-KNOW-0001"
    assert result.capability.status == "implemented"
    assert result.capability.maturity == "M3"
    assert result.capability.implementation_status == "implemented"
    assert tuple(
        item.knowledge_id for item in result.required_knowledge
    ) == (
        "KNW-KNOW-0001",
        "KNW-KNOW-0002",
        "KNW-KNOW-0003",
    )
    assert result.source_documents
    assert result.source_documents[0].document_id == "DOC-ARCH-0001"
    assert result.reference_priority == provider_priority()
    assert result.matched_scope == "architecture.knowledge_foundation"
    assert result.decision_required is False


def test_registered_resolver_capability_resolves_at_m3(resolver):
    result = resolver.resolve(CapabilityRequirement(
        capability_id="CAP-RESOLVER-0001",
        requested_scope="architecture.knowledge_foundation.resolver",
        minimum_maturity="M3",
    ))

    assert result.resolution_status is ResolutionStatus.RESOLVED
    assert result.capability.required_capabilities == ("CAP-KNOW-0001",)
    assert result.required_capabilities[0].capability_id == "CAP-KNOW-0001"
    assert result.capability.runtime_dependencies == ()


def test_repository_scope_and_lower_maturity_threshold_match(resolver):
    result = resolver.resolve(CapabilityRequirement(
        capability_id="CAP-KNOW-0001",
        requested_scope="architecture.knowledge_foundation.resolver",
        minimum_maturity="M2",
    ))

    assert result.resolution_status is ResolutionStatus.RESOLVED
    assert result.matched_scope.endswith(".resolver")
    assert "05.maturity.accepted:M3>=M2" in result.trace


def test_scope_mismatch_blocks_resolution(resolver):
    result = resolver.resolve(CapabilityRequirement(
        capability_id="CAP-KNOW-0001",
        requested_scope="runtime.execution",
    ))

    assert result.resolution_status is ResolutionStatus.BLOCKED
    assert result.eligible is False
    assert any("scope" in reason for reason in result.rejection_reasons)


def test_maturity_threshold_and_operational_requirement_block(resolver):
    maturity = resolver.resolve(CapabilityRequirement(
        capability_id="CAP-KNOW-0001",
        minimum_maturity="M4",
    ))
    operational = resolver.resolve(CapabilityRequirement(
        capability_id="CAP-KNOW-0001",
        require_operational=True,
    ))

    assert maturity.resolution_status is ResolutionStatus.BLOCKED
    assert "below M4" in maturity.rejection_reasons[0]
    assert operational.resolution_status is ResolutionStatus.BLOCKED
    assert any(
        "operational capability was required" in reason
        for reason in operational.rejection_reasons
    )


@pytest.mark.parametrize("status", ["deprecated", "retired"])
def test_deprecated_and_retired_capabilities_are_blocked(provider, status):
    capability = replace(provider.snapshot.capabilities[0], status=status)
    snapshot = replace(
        provider.snapshot,
        capabilities=(capability,) + provider.snapshot.capabilities[1:],
    )
    candidate_provider = KnowledgeFoundationProvider(ROOT, snapshot=snapshot)

    result = CapabilityResolver(candidate_provider).resolve(
        CapabilityRequirement(capability_id="CAP-KNOW-0001")
    )

    assert result.resolution_status is ResolutionStatus.BLOCKED
    assert result.rejection_reasons == (
        f"capability status is ineligible: {status}",
    )


def test_nonimplemented_capability_is_not_presented_as_executable(provider):
    capability = replace(
        provider.snapshot.capabilities[0],
        status="implementation_in_progress",
        maturity="M2",
        implementation_status="partially_implemented",
    )
    snapshot = replace(
        provider.snapshot,
        capabilities=(capability,) + provider.snapshot.capabilities[1:],
    )
    candidate_provider = KnowledgeFoundationProvider(ROOT, snapshot=snapshot)

    result = CapabilityResolver(candidate_provider).resolve(
        CapabilityRequirement(capability_id="CAP-KNOW-0001")
    )

    assert result.resolution_status is ResolutionStatus.BLOCKED
    assert result.eligible is False
    assert any("implementation_status" in item for item in result.rejection_reasons)


def test_unknown_capability_returns_explicit_unresolved_result(resolver):
    result = resolver.resolve(
        CapabilityRequirement(capability_id="CAP-NONE-9999")
    )

    assert result.resolution_status is ResolutionStatus.UNRESOLVED
    assert result.capability is None
    assert result.gaps[0].gap_type == "capability_gap"
    assert result.trace == (
        "01.capability.not_found:CAP-NONE-9999",
        "11.resolution.unresolved",
    )


def test_missing_required_knowledge_returns_blocking_gap(provider):
    candidate_provider = ProviderDouble(provider)
    candidate_provider.missing_knowledge.add("KNW-KNOW-0002")

    result = CapabilityResolver(candidate_provider).resolve(
        CapabilityRequirement(capability_id="CAP-KNOW-0001")
    )

    assert result.resolution_status is ResolutionStatus.BLOCKED
    assert any(
        gap.gap_type == "knowledge_gap"
        and gap.related_ids == ("KNW-KNOW-0002",)
        for gap in result.gaps
    )


def test_missing_required_capability_returns_blocking_gap(provider):
    candidate_provider = ProviderDouble(provider)
    candidate_provider.root_capability = replace(
        provider.get_capability("CAP-KNOW-0001"),
        required_capabilities=("CAP-NONE-9999",),
    )

    result = CapabilityResolver(candidate_provider).resolve(
        CapabilityRequirement(capability_id="CAP-KNOW-0001")
    )

    assert result.resolution_status is ResolutionStatus.BLOCKED
    assert any(
        gap.gap_type == "capability_gap"
        and gap.related_ids == ("CAP-NONE-9999",)
        for gap in result.gaps
    )


def test_constraints_and_provider_decision_gap_require_a_decision(provider):
    constrained = CapabilityResolver(provider).resolve(CapabilityRequirement(
        capability_id="CAP-KNOW-0001",
        constraints={"region": "kr"},
    ))
    candidate_provider = ProviderDouble(provider)
    candidate_provider.extra_gaps = (
        KnowledgeGap(
            gap_type="decision_required",
            subject_id="CAP-KNOW-0001",
            message="authority owner must choose a policy",
        ),
    )
    provider_decision = CapabilityResolver(candidate_provider).resolve(
        CapabilityRequirement(capability_id="CAP-KNOW-0001")
    )

    assert constrained.resolution_status is ResolutionStatus.DECISION_REQUIRED
    assert constrained.decision_required is True
    assert provider_decision.resolution_status is ResolutionStatus.DECISION_REQUIRED


def test_trace_order_is_deterministic(resolver):
    requirement = CapabilityRequirement(capability_id="CAP-KNOW-0001")

    first = resolver.resolve(requirement)
    second = resolver.resolve(requirement)

    assert first == second
    assert tuple(item.split(".", 1)[0] for item in first.trace) == (
        "01", "02", "03", "04", "05", "06",
        "07", "08", "09", "10", "11",
    )


def test_result_is_immutable_and_provider_is_injected(provider):
    candidate_provider = ProviderDouble(provider)
    result = CapabilityResolver(candidate_provider).resolve(
        CapabilityRequirement(capability_id="CAP-KNOW-0001")
    )

    assert candidate_provider.calls[0] == (
        "get_capability",
        "CAP-KNOW-0001",
    )
    with pytest.raises(FrozenInstanceError):
        result.eligible = False
    with pytest.raises(TypeError):
        result.trace[0] = "changed"


def test_invalid_provider_registry_is_wrapped_fail_closed():
    class InvalidProvider:
        def get_capability(self, capability_id):
            raise RegistryValidationError(["invalid registry fixture"])

    resolver = CapabilityResolver(InvalidProvider())
    with pytest.raises(CapabilityResolutionError) as captured:
        resolver.resolve(
            CapabilityRequirement(capability_id="CAP-KNOW-0001")
        )
    assert isinstance(captured.value.__cause__, RegistryValidationError)


def provider_priority():
    return KnowledgeFoundationProvider(ROOT).reference_priority(
        "architecture.knowledge_foundation"
    )


class ProviderDouble:
    def __init__(self, provider):
        self.provider = provider
        self.calls = []
        self.root_capability = provider.get_capability("CAP-KNOW-0001")
        self.missing_knowledge = set()
        self.extra_gaps = ()

    def get_capability(self, capability_id):
        self.calls.append(("get_capability", capability_id))
        if capability_id == "CAP-KNOW-0001":
            return self.root_capability
        return self.provider.get_capability(capability_id)

    def capability_context(self, capability_id, scope=None):
        self.calls.append(("capability_context", capability_id, scope))
        return self.provider.capability_context(capability_id, scope)

    def gaps(self, capability_id, scope=None):
        self.calls.append(("gaps", capability_id, scope))
        return self.provider.gaps(capability_id, scope) + self.extra_gaps

    def get_knowledge(self, knowledge_id):
        self.calls.append(("get_knowledge", knowledge_id))
        if knowledge_id in self.missing_knowledge:
            raise RegistryLookupError(f"unknown knowledge_id: {knowledge_id}")
        return self.provider.get_knowledge(knowledge_id)

    def get_document(self, document_id):
        self.calls.append(("get_document", document_id))
        return self.provider.get_document(document_id)

    def reference_priority(self, scope=None):
        self.calls.append(("reference_priority", scope))
        return self.provider.reference_priority(scope)
