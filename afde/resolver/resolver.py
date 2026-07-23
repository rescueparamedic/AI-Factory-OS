"""Deterministic, read-only Capability Resolver foundation."""
from __future__ import annotations

from typing import Protocol

from afde.knowledge import (
    CapabilityContext,
    CapabilityRegistryEntry,
    DocumentRegistryEntry,
    KnowledgeFoundationError,
    KnowledgeGap,
    KnowledgeRegistryEntry,
    RegistryLookupError,
)

from .errors import (
    CapabilityResolutionError,
    InvalidCapabilityRequirementError,
)
from .models import (
    MATURITY_LEVELS,
    CapabilityRequirement,
    CapabilityResolutionResult,
    ResolutionStatus,
)


ELIGIBLE_STATUSES = ("implemented", "validated", "operational")
INELIGIBLE_STATUSES = ("deprecated", "retired")


class KnowledgeProvider(Protocol):
    """Minimal read-only provider contract consumed by the resolver."""

    def get_capability(
        self, capability_id: str,
    ) -> CapabilityRegistryEntry: ...

    def capability_context(
        self, capability_id: str, scope: str | None = None,
    ) -> CapabilityContext: ...

    def gaps(
        self, capability_id: str, scope: str | None = None,
    ) -> tuple[KnowledgeGap, ...]: ...

    def get_knowledge(self, knowledge_id: str) -> KnowledgeRegistryEntry: ...

    def get_document(self, document_id: str) -> DocumentRegistryEntry: ...

    def reference_priority(
        self, scope: str | None = None,
    ) -> tuple[str, ...]: ...


class CapabilityResolver:
    """Evaluate capability eligibility without selecting or executing tools."""

    def __init__(self, provider: KnowledgeProvider) -> None:
        self._provider = provider

    def resolve(
        self, requirement: CapabilityRequirement,
    ) -> CapabilityResolutionResult:
        if not isinstance(requirement, CapabilityRequirement):
            raise InvalidCapabilityRequirementError(
                "requirement must be a CapabilityRequirement"
            )

        capability_id = requirement.capability_id
        assert capability_id is not None
        trace: list[str] = []
        try:
            capability = self._provider.get_capability(capability_id)
        except RegistryLookupError:
            gap = KnowledgeGap(
                gap_type="capability_gap",
                subject_id=capability_id,
                message=f"capability is not registered: {capability_id}",
            )
            return CapabilityResolutionResult(
                requirement=requirement,
                capability=None,
                resolution_status=ResolutionStatus.UNRESOLVED,
                eligible=False,
                matched_scope=None,
                required_knowledge=(),
                required_capabilities=(),
                source_documents=(),
                reference_priority=(),
                gaps=(gap,),
                rejection_reasons=(gap.message,),
                decision_required=False,
                trace=(
                    f"01.capability.not_found:{capability_id}",
                    "11.resolution.unresolved",
                ),
            )
        except KnowledgeFoundationError as exc:
            raise CapabilityResolutionError(
                "knowledge provider failed while reading capability metadata"
            ) from exc

        trace.append(f"01.capability.found:{capability_id}")
        try:
            context = self._provider.capability_context(
                capability_id, requirement.requested_scope,
            )
            provider_gaps = self._provider.gaps(
                capability_id, requirement.requested_scope,
            )
            priority = self._provider.reference_priority(
                requirement.requested_scope,
            )
        except KnowledgeFoundationError as exc:
            raise CapabilityResolutionError(
                "knowledge provider failed while building capability context"
            ) from exc

        rejections: list[str] = []
        gaps: list[KnowledgeGap] = list(provider_gaps)
        decisions: list[str] = []
        trace.append("02.registry.validated_by_provider")

        if capability.status in INELIGIBLE_STATUSES:
            rejections.append(
                f"capability status is ineligible: {capability.status}"
            )
            trace.append(f"03.status.blocked:{capability.status}")
        elif capability.status not in ELIGIBLE_STATUSES:
            rejections.append(
                f"capability status is not implemented: {capability.status}"
            )
            trace.append(f"03.status.not_ready:{capability.status}")
        else:
            trace.append(f"03.status.eligible:{capability.status}")

        if capability.implementation_status != "implemented":
            rejections.append(
                "capability implementation_status is not implemented: "
                f"{capability.implementation_status}"
            )
            trace.append(
                "04.implementation.blocked:"
                f"{capability.implementation_status}"
            )
        else:
            trace.append("04.implementation.eligible:implemented")

        if requirement.minimum_maturity is None:
            trace.append(f"05.maturity.accepted:{capability.maturity}")
        elif _maturity_at_least(
            capability.maturity, requirement.minimum_maturity,
        ):
            trace.append(
                "05.maturity.accepted:"
                f"{capability.maturity}>={requirement.minimum_maturity}"
            )
        else:
            rejections.append(
                f"capability maturity {capability.maturity} is below "
                f"{requirement.minimum_maturity}"
            )
            trace.append(
                "05.maturity.blocked:"
                f"{capability.maturity}<{requirement.minimum_maturity}"
            )

        matched_scope: str | None = None
        if _scope_applies(capability.scope, requirement.requested_scope):
            matched_scope = requirement.requested_scope or capability.scope
            trace.append(f"06.scope.matched:{matched_scope}")
        else:
            rejections.append(
                f"capability scope {capability.scope} does not match "
                f"{requirement.requested_scope}"
            )
            trace.append("06.scope.blocked")

        knowledge, knowledge_gaps, knowledge_rejections = (
            self._required_knowledge(capability, requirement)
        )
        gaps.extend(knowledge_gaps)
        rejections.extend(knowledge_rejections)
        trace.append(
            f"07.knowledge.checked:{len(knowledge)}"
        )

        dependencies, dependency_gaps, dependency_rejections = (
            self._required_capabilities(capability, requirement.requested_scope)
        )
        gaps.extend(dependency_gaps)
        rejections.extend(dependency_rejections)
        trace.append(
            f"08.capabilities.checked:{len(dependencies)}"
        )

        documents, document_gaps, document_rejections = self._source_documents(
            context, knowledge,
        )
        gaps.extend(document_gaps)
        rejections.extend(document_rejections)
        gaps = _unique_gaps(gaps)
        trace.append(f"09.gaps.reviewed:{len(gaps)}")

        for gap in gaps:
            if gap.gap_type == "decision_required":
                decisions.append(gap.message)
        if requirement.constraints:
            decisions.append(
                "requirement constraints need an external policy decision: "
                + ", ".join(sorted(requirement.constraints))
            )
        if requirement.require_operational and capability.status != "operational":
            rejections.append(
                "operational capability was required but status is "
                f"{capability.status}"
            )

        if decisions:
            trace.append(f"10.decision.required:{len(decisions)}")
        else:
            trace.append("10.decision.not_required")

        rejections = list(dict.fromkeys(rejections))
        if rejections:
            status = ResolutionStatus.BLOCKED
            eligible = False
        elif decisions:
            status = ResolutionStatus.DECISION_REQUIRED
            eligible = False
        else:
            status = ResolutionStatus.RESOLVED
            eligible = True
        trace.append(f"11.resolution.{status.value}")

        return CapabilityResolutionResult(
            requirement=requirement,
            capability=capability,
            resolution_status=status,
            eligible=eligible,
            matched_scope=matched_scope,
            required_knowledge=knowledge,
            required_capabilities=dependencies,
            source_documents=documents,
            reference_priority=tuple(priority),
            gaps=tuple(gaps),
            rejection_reasons=tuple(rejections or decisions),
            decision_required=bool(decisions),
            trace=tuple(trace),
        )

    def _required_knowledge(
        self,
        capability: CapabilityRegistryEntry,
        requirement: CapabilityRequirement,
    ) -> tuple[
        tuple[KnowledgeRegistryEntry, ...],
        list[KnowledgeGap],
        list[str],
    ]:
        identifiers = tuple(dict.fromkeys(
            capability.required_knowledge
            + requirement.required_knowledge_ids
        ))
        entries: list[KnowledgeRegistryEntry] = []
        gaps: list[KnowledgeGap] = []
        rejections: list[str] = []
        for knowledge_id in identifiers:
            try:
                entry = self._provider.get_knowledge(knowledge_id)
            except RegistryLookupError:
                message = f"required knowledge is not registered: {knowledge_id}"
                gaps.append(KnowledgeGap(
                    gap_type="knowledge_gap",
                    subject_id=capability.capability_id,
                    message=message,
                    related_ids=(knowledge_id,),
                ))
                rejections.append(message)
                continue
            except KnowledgeFoundationError as exc:
                raise CapabilityResolutionError(
                    "knowledge provider failed while reading required knowledge"
                ) from exc
            entries.append(entry)
            if entry.status != "active":
                rejections.append(
                    f"required knowledge is not active: {knowledge_id}"
                )
            if not _scope_applies(entry.scope, requirement.requested_scope):
                rejections.append(
                    f"required knowledge scope does not match: {knowledge_id}"
                )
        return tuple(entries), gaps, rejections

    def _required_capabilities(
        self,
        capability: CapabilityRegistryEntry,
        requested_scope: str | None,
    ) -> tuple[
        tuple[CapabilityRegistryEntry, ...],
        list[KnowledgeGap],
        list[str],
    ]:
        entries: list[CapabilityRegistryEntry] = []
        gaps: list[KnowledgeGap] = []
        rejections: list[str] = []
        for dependency_id in capability.required_capabilities:
            try:
                dependency = self._provider.get_capability(dependency_id)
            except RegistryLookupError:
                message = (
                    f"required capability is not registered: {dependency_id}"
                )
                gaps.append(KnowledgeGap(
                    gap_type="capability_gap",
                    subject_id=capability.capability_id,
                    message=message,
                    related_ids=(dependency_id,),
                ))
                rejections.append(message)
                continue
            except KnowledgeFoundationError as exc:
                raise CapabilityResolutionError(
                    "knowledge provider failed while reading a dependency"
                ) from exc
            entries.append(dependency)
            if (
                dependency.status not in ELIGIBLE_STATUSES
                or dependency.implementation_status != "implemented"
            ):
                rejections.append(
                    f"required capability is not implemented and eligible: "
                    f"{dependency_id}"
                )
            if not _scope_applies(dependency.scope, requested_scope):
                rejections.append(
                    f"required capability scope does not match: {dependency_id}"
                )
        return tuple(entries), gaps, rejections

    def _source_documents(
        self,
        context: CapabilityContext,
        knowledge: tuple[KnowledgeRegistryEntry, ...],
    ) -> tuple[
        tuple[DocumentRegistryEntry, ...],
        list[KnowledgeGap],
        list[str],
    ]:
        documents: list[DocumentRegistryEntry] = list(context.source_documents)
        known = {item.document_id for item in documents}
        identifiers = [
            binding.document_id
            for entry in knowledge
            for binding in entry.source_documents
        ]
        gaps: list[KnowledgeGap] = []
        rejections: list[str] = []
        for document_id in identifiers:
            if document_id in known:
                continue
            try:
                document = self._provider.get_document(document_id)
            except RegistryLookupError:
                message = f"source document is not registered: {document_id}"
                gaps.append(KnowledgeGap(
                    gap_type="document_gap",
                    subject_id=context.capability.capability_id,
                    message=message,
                    related_ids=(document_id,),
                ))
                rejections.append(message)
                continue
            except KnowledgeFoundationError as exc:
                raise CapabilityResolutionError(
                    "knowledge provider failed while reading source documents"
                ) from exc
            known.add(document_id)
            documents.append(document)
        return tuple(documents), gaps, rejections


def _maturity_at_least(actual: str, required: str) -> bool:
    try:
        return MATURITY_LEVELS.index(actual) >= MATURITY_LEVELS.index(required)
    except ValueError:
        return False


def _scope_applies(
    entry_scope: str, requested_scope: str | None,
) -> bool:
    if requested_scope is None:
        return True
    return (
        entry_scope == "repository"
        or entry_scope == requested_scope
        or requested_scope.startswith(f"{entry_scope}.")
    )


def _unique_gaps(gaps: list[KnowledgeGap]) -> list[KnowledgeGap]:
    result: list[KnowledgeGap] = []
    seen: set[tuple[str, str, str, tuple[str, ...]]] = set()
    for gap in gaps:
        key = (
            gap.gap_type,
            gap.subject_id,
            gap.message,
            gap.related_ids,
        )
        if key not in seen:
            seen.add(key)
            result.append(gap)
    return result
