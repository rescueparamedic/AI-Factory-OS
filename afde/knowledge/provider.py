"""Read-only Knowledge Provider contract for a future Capability Resolver."""
from __future__ import annotations

from pathlib import Path

from .errors import RegistryLookupError
from .loader import KnowledgeRegistryLoader
from .models import (
    CapabilityContext,
    CapabilityRegistryEntry,
    DocumentRegistryEntry,
    KnowledgeFoundationSnapshot,
    KnowledgeGap,
    KnowledgeRegistryEntry,
)
from .validator import KnowledgeRegistryValidator


class KnowledgeFoundationProvider:
    """Expose immutable registry projections without selection or execution."""

    def __init__(
        self,
        repository_root: str | Path,
        registry_path: str | Path | None = None,
        *,
        snapshot: KnowledgeFoundationSnapshot | None = None,
    ) -> None:
        root = Path(repository_root).expanduser().resolve()
        self._snapshot = (
            KnowledgeRegistryValidator(root).validate(snapshot)
            if snapshot is not None
            else KnowledgeRegistryLoader(root, registry_path).load()
        )
        self._documents = {
            item.document_id: item for item in self._snapshot.documents
        }
        self._knowledge = {
            item.knowledge_id: item for item in self._snapshot.knowledge
        }
        self._capabilities = {
            item.capability_id: item for item in self._snapshot.capabilities
        }

    @property
    def snapshot(self) -> KnowledgeFoundationSnapshot:
        return self._snapshot

    def get_document(self, document_id: str) -> DocumentRegistryEntry:
        try:
            return self._documents[document_id]
        except KeyError as exc:
            raise RegistryLookupError(
                f"unknown document_id: {document_id}"
            ) from exc

    def get_knowledge(self, knowledge_id: str) -> KnowledgeRegistryEntry:
        try:
            return self._knowledge[knowledge_id]
        except KeyError as exc:
            raise RegistryLookupError(
                f"unknown knowledge_id: {knowledge_id}"
            ) from exc

    def get_capability(self, capability_id: str) -> CapabilityRegistryEntry:
        try:
            return self._capabilities[capability_id]
        except KeyError as exc:
            raise RegistryLookupError(
                f"unknown capability_id: {capability_id}"
            ) from exc

    def query_documents(
        self, scope: str | None = None, status: str | None = None,
    ) -> tuple[DocumentRegistryEntry, ...]:
        return tuple(
            item
            for item in self._snapshot.documents
            if _applies(item.scope, scope) and _status(item.status, status)
        )

    def query_knowledge(
        self, scope: str | None = None, status: str | None = "active",
    ) -> tuple[KnowledgeRegistryEntry, ...]:
        return tuple(
            item
            for item in self._snapshot.knowledge
            if _applies(item.scope, scope) and _status(item.status, status)
        )

    def query_capabilities(
        self, scope: str | None = None, status: str | None = None,
    ) -> tuple[CapabilityRegistryEntry, ...]:
        return tuple(
            item
            for item in self._snapshot.capabilities
            if _applies(item.scope, scope) and _status(item.status, status)
        )

    def reference_priority(self, scope: str | None = None) -> tuple[str, ...]:
        _optional_scope(scope)
        return self._snapshot.reference_priority

    def capability_context(
        self, capability_id: str, scope: str | None = None,
    ) -> CapabilityContext:
        requested_scope = _optional_scope(scope)
        capability = self.get_capability(capability_id)
        required: list[KnowledgeRegistryEntry] = []
        gaps: list[KnowledgeGap] = list(capability.known_gaps)
        if requested_scope is not None and not _applies(
            capability.scope, requested_scope,
        ):
            gaps.append(
                KnowledgeGap(
                    gap_type="capability_gap",
                    subject_id=capability_id,
                    message=(
                        f"capability is outside scope {requested_scope}: "
                        f"{capability_id}"
                    ),
                    related_ids=(capability_id,),
                )
            )

        for knowledge_id in capability.required_knowledge:
            item = self.get_knowledge(knowledge_id)
            if item.status != "active":
                gaps.append(
                    KnowledgeGap(
                        gap_type="knowledge_gap",
                        subject_id=capability_id,
                        message=f"required knowledge is inactive: {knowledge_id}",
                        related_ids=(knowledge_id,),
                    )
                )
                continue
            if requested_scope is not None and not _applies(
                item.scope, requested_scope,
            ):
                gaps.append(
                    KnowledgeGap(
                        gap_type="knowledge_gap",
                        subject_id=capability_id,
                        message=(
                            f"required knowledge is outside scope "
                            f"{requested_scope}: {knowledge_id}"
                        ),
                        related_ids=(knowledge_id,),
                    )
                )
                continue
            required.append(item)
            gaps.extend(item.known_gaps)

        document_ids: list[str] = list(capability.source_documents)
        for item in required:
            document_ids.extend(
                binding.document_id for binding in item.source_documents
            )
        unique_document_ids = tuple(dict.fromkeys(document_ids))
        documents = tuple(
            self.get_document(document_id) for document_id in unique_document_ids
        )
        authority = tuple(dict.fromkeys(
            item.authority_level for item in required
        ))
        return CapabilityContext(
            capability=capability,
            required_knowledge=tuple(required),
            source_documents=documents,
            authority=authority,
            status=capability.status,
            scope=capability.scope,
            reference_priority=self.reference_priority(requested_scope),
            gaps=tuple(gaps),
        )

    def gaps(
        self, capability_id: str, scope: str | None = None,
    ) -> tuple[KnowledgeGap, ...]:
        return self.capability_context(capability_id, scope).gaps


def _status(actual: str, requested: str | None) -> bool:
    if requested is None:
        return True
    if not isinstance(requested, str) or not requested.strip():
        raise ValueError("status must be a non-empty string")
    return actual.casefold() == requested.strip().casefold()


def _optional_scope(value: str | None) -> str | None:
    if value is None:
        return None
    if not isinstance(value, str) or not value.strip():
        raise ValueError("scope must be a non-empty string")
    return value.strip()


def _applies(entry_scope: str, requested_scope: str | None) -> bool:
    scope = _optional_scope(requested_scope)
    if scope is None:
        return True
    return (
        entry_scope == "repository"
        or entry_scope == scope
        or scope.startswith(f"{entry_scope}.")
    )
