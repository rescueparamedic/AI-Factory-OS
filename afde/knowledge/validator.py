"""Cross-registry validation for Knowledge Foundation snapshots."""
from __future__ import annotations

from pathlib import Path, PurePosixPath
import re
from typing import Callable, Iterable

from .errors import RegistryValidationError
from .models import (
    AUTHORITY_LEVELS,
    CAPABILITY_MATURITIES,
    CAPABILITY_STATUSES,
    DOCUMENT_STATUSES,
    DOCUMENT_TYPES,
    GAP_TYPES,
    IMPLEMENTATION_STATUSES,
    KNOWLEDGE_STATUSES,
    KNOWLEDGE_TYPES,
    CapabilityRegistryEntry,
    DocumentRegistryEntry,
    KnowledgeFoundationSnapshot,
)


DOCUMENT_ID_PATTERN = re.compile(r"^DOC-[A-Z0-9]+-[0-9]{4}$")
KNOWLEDGE_ID_PATTERN = re.compile(r"^KNW-[A-Z0-9]+-[0-9]{4}$")
CAPABILITY_ID_PATTERN = re.compile(r"^CAP-[A-Z0-9]+-[0-9]{4}$")
SUPPORTED_SCHEMA_VERSIONS = ("1.0",)
CAPABILITY_BINDING_RELATIONS = ("required", "supporting", "evidence")


class KnowledgeRegistryValidator:
    """Validate one immutable snapshot without mutating repository state."""

    def __init__(self, repository_root: str | Path) -> None:
        self.root = Path(repository_root).expanduser().resolve()

    def validate(
        self, snapshot: KnowledgeFoundationSnapshot,
    ) -> KnowledgeFoundationSnapshot:
        errors: list[str] = []
        if snapshot.schema_version not in SUPPORTED_SCHEMA_VERSIONS:
            errors.append(
                f"unsupported schema_version: {snapshot.schema_version}"
            )

        documents = _unique(
            snapshot.documents, lambda item: item.document_id, "document", errors,
        )
        knowledge = _unique(
            snapshot.knowledge, lambda item: item.knowledge_id, "knowledge", errors,
        )
        capabilities = _unique(
            snapshot.capabilities,
            lambda item: item.capability_id,
            "capability",
            errors,
        )

        self._documents(
            snapshot, documents, knowledge, capabilities, errors,
        )
        self._knowledge(snapshot, documents, knowledge, capabilities, errors)
        self._capabilities(snapshot, documents, knowledge, capabilities, errors)
        self._cycles(snapshot, errors)

        if len(set(snapshot.authority_levels)) != len(snapshot.authority_levels):
            errors.append("authority_levels contains duplicates")
        if snapshot.authority_levels != AUTHORITY_LEVELS:
            errors.append(
                "authority_levels does not match the governed priority order"
            )
        if not snapshot.authority_levels:
            errors.append("authority_levels must not be empty")
        if len(set(snapshot.reference_priority)) != len(snapshot.reference_priority):
            errors.append("reference_priority contains duplicates")
        if not snapshot.reference_priority:
            errors.append("reference_priority must not be empty")

        if errors:
            raise RegistryValidationError(sorted(set(errors)))
        return snapshot

    def _documents(
        self,
        snapshot: KnowledgeFoundationSnapshot,
        documents: dict[str, DocumentRegistryEntry],
        knowledge: dict[str, object],
        capabilities: dict[str, object],
        errors: list[str],
    ) -> None:
        authorities = set(snapshot.authority_levels)
        for entry in snapshot.documents:
            _identifier(entry.document_id, DOCUMENT_ID_PATTERN, "document", errors)
            _enum(entry.status, DOCUMENT_STATUSES, entry.document_id, "status", errors)
            _enum(
                entry.document_type,
                DOCUMENT_TYPES,
                entry.document_id,
                "document_type",
                errors,
            )
            if entry.authority_level not in authorities:
                errors.append(
                    f"{entry.document_id} has unknown authority_level: "
                    f"{entry.authority_level}"
                )
            self._source_path(entry, errors)
            _references(entry.supersedes, documents, entry.document_id, "supersedes", errors)
            _references(entry.knowledge_ids, knowledge, entry.document_id, "knowledge_ids", errors)
            _references(entry.capability_ids, capabilities, entry.document_id, "capability_ids", errors)
            for knowledge_id in entry.knowledge_ids:
                item = knowledge.get(knowledge_id)
                if (
                    item is not None
                    and entry.document_id not in {
                        binding.document_id for binding in item.source_documents
                    }
                ):
                    errors.append(
                        f"{entry.document_id} knowledge binding is not reciprocal: "
                        f"{knowledge_id}"
                    )
            for capability_id in entry.capability_ids:
                item = capabilities.get(capability_id)
                if (
                    item is not None
                    and entry.document_id not in item.source_documents
                ):
                    errors.append(
                        f"{entry.document_id} capability binding is not reciprocal: "
                        f"{capability_id}"
                    )

    def _knowledge(
        self,
        snapshot: KnowledgeFoundationSnapshot,
        documents: dict[str, DocumentRegistryEntry],
        knowledge: dict[str, object],
        capabilities: dict[str, object],
        errors: list[str],
    ) -> None:
        authorities = set(snapshot.authority_levels)
        for entry in snapshot.knowledge:
            _identifier(entry.knowledge_id, KNOWLEDGE_ID_PATTERN, "knowledge", errors)
            _enum(entry.status, KNOWLEDGE_STATUSES, entry.knowledge_id, "status", errors)
            _enum(
                entry.knowledge_type,
                KNOWLEDGE_TYPES,
                entry.knowledge_id,
                "knowledge_type",
                errors,
            )
            if entry.authority_level not in authorities:
                errors.append(
                    f"{entry.knowledge_id} has unknown authority_level: "
                    f"{entry.authority_level}"
                )
            if entry.status == "active" and not entry.source_documents:
                errors.append(f"{entry.knowledge_id} active entry has no source")
            for binding in entry.source_documents:
                source = documents.get(binding.document_id)
                if source is None:
                    errors.append(
                        f"{entry.knowledge_id} has unknown source document: "
                        f"{binding.document_id}"
                    )
                elif entry.status == "active" and source.status != "Active":
                    errors.append(
                        f"{entry.knowledge_id} active source is not Active: "
                        f"{binding.document_id}"
                    )
                if (
                    source is not None
                    and entry.knowledge_id not in source.knowledge_ids
                ):
                    errors.append(
                        f"{entry.knowledge_id} source binding is not reciprocal: "
                        f"{binding.document_id}"
                    )
            for binding in entry.capability_bindings:
                if binding.capability_id not in capabilities:
                    errors.append(
                        f"{entry.knowledge_id} has unknown capability binding: "
                        f"{binding.capability_id}"
                    )
                if binding.relation not in CAPABILITY_BINDING_RELATIONS:
                    errors.append(
                        f"{entry.knowledge_id} has invalid binding relation: "
                        f"{binding.relation}"
                    )
                capability = capabilities.get(binding.capability_id)
                if (
                    capability is not None
                    and binding.relation == "required"
                    and entry.knowledge_id not in capability.required_knowledge
                ):
                    errors.append(
                        f"{entry.knowledge_id} required capability binding is "
                        f"not reciprocal: {binding.capability_id}"
                    )
            _references(
                entry.conflicts_with,
                knowledge,
                entry.knowledge_id,
                "conflicts_with",
                errors,
            )
            _references(
                entry.supersedes,
                knowledge,
                entry.knowledge_id,
                "supersedes",
                errors,
            )
            for conflict in entry.conflicts_with:
                other = knowledge.get(conflict)
                if other is not None and entry.knowledge_id not in other.conflicts_with:
                    errors.append(
                        f"conflict is not symmetric: {entry.knowledge_id} -> {conflict}"
                    )
            _gaps(
                entry.known_gaps,
                entry.knowledge_id,
                errors,
                set(documents) | set(knowledge) | set(capabilities),
            )

    def _capabilities(
        self,
        snapshot: KnowledgeFoundationSnapshot,
        documents: dict[str, object],
        knowledge: dict[str, object],
        capabilities: dict[str, CapabilityRegistryEntry],
        errors: list[str],
    ) -> None:
        for entry in snapshot.capabilities:
            _identifier(entry.capability_id, CAPABILITY_ID_PATTERN, "capability", errors)
            _enum(entry.status, CAPABILITY_STATUSES, entry.capability_id, "status", errors)
            _enum(entry.maturity, CAPABILITY_MATURITIES, entry.capability_id, "maturity", errors)
            _enum(
                entry.implementation_status,
                IMPLEMENTATION_STATUSES,
                entry.capability_id,
                "implementation_status",
                errors,
            )
            _references(
                entry.required_knowledge,
                knowledge,
                entry.capability_id,
                "required_knowledge",
                errors,
            )
            for knowledge_id in entry.required_knowledge:
                item = knowledge.get(knowledge_id)
                if item is not None and item.status != "active":
                    errors.append(
                        f"{entry.capability_id} required knowledge is not active: "
                        f"{knowledge_id}"
                    )
                if (
                    item is not None
                    and not any(
                        binding.capability_id == entry.capability_id
                        and binding.relation == "required"
                        for binding in item.capability_bindings
                    )
                ):
                    errors.append(
                        f"{entry.capability_id} required knowledge binding is "
                        f"not reciprocal: {knowledge_id}"
                    )
            _references(
                entry.required_capabilities,
                capabilities,
                entry.capability_id,
                "required_capabilities",
                errors,
            )
            _references(
                entry.source_documents,
                documents,
                entry.capability_id,
                "source_documents",
                errors,
            )
            for document_id in entry.source_documents:
                item = documents.get(document_id)
                if (
                    item is not None
                    and entry.capability_id not in item.capability_ids
                ):
                    errors.append(
                        f"{entry.capability_id} source binding is not reciprocal: "
                        f"{document_id}"
                    )
            _references(
                entry.supersedes,
                capabilities,
                entry.capability_id,
                "supersedes",
                errors,
            )
            _gaps(
                entry.known_gaps,
                entry.capability_id,
                errors,
                set(documents) | set(knowledge) | set(capabilities),
            )
            if (
                entry.status in CAPABILITY_STATUSES
                and entry.maturity in CAPABILITY_MATURITIES
                and entry.implementation_status in IMPLEMENTATION_STATUSES
            ):
                self._implementation_state(entry, errors)

    def _implementation_state(
        self, entry: CapabilityRegistryEntry, errors: list[str],
    ) -> None:
        maturity = CAPABILITY_MATURITIES.index(entry.maturity)
        status = CAPABILITY_STATUSES.index(entry.status)
        implemented_status = CAPABILITY_STATUSES.index("implemented")
        if (
            entry.implementation_status == "not_implemented"
            and (
                maturity >= 3
                or entry.status in ("implemented", "validated", "operational")
            )
        ):
            errors.append(
                f"{entry.capability_id} not_implemented contradicts "
                f"{entry.status}/{entry.maturity}"
            )
        if (
            entry.implementation_status == "implemented"
            and (maturity < 3 or status < implemented_status)
        ):
            errors.append(
                f"{entry.capability_id} implemented contradicts "
                f"{entry.status}/{entry.maturity}"
            )
        if maturity >= 3 and entry.implementation_status != "implemented":
            errors.append(
                f"{entry.capability_id} {entry.maturity} requires implemented status"
            )
        if (
            entry.implementation_status == "implemented"
            and not entry.implementation_references
        ):
            errors.append(
                f"{entry.capability_id} implemented entry has no implementation references"
            )

    def _source_path(
        self, entry: DocumentRegistryEntry, errors: list[str],
    ) -> None:
        relative = PurePosixPath(entry.path)
        if relative.is_absolute() or ".." in relative.parts:
            errors.append(f"{entry.document_id} source path escapes repository")
            return
        target = (self.root / Path(*relative.parts)).resolve()
        if not _inside(target, self.root):
            errors.append(f"{entry.document_id} source path escapes repository")
            return
        if not target.is_file():
            errors.append(f"{entry.document_id} source path is missing: {entry.path}")

    def _cycles(
        self, snapshot: KnowledgeFoundationSnapshot, errors: list[str],
    ) -> None:
        _acyclic(
            {item.document_id: item.supersedes for item in snapshot.documents},
            "document supersession",
            errors,
        )
        _acyclic(
            {item.knowledge_id: item.supersedes for item in snapshot.knowledge},
            "knowledge supersession",
            errors,
        )
        _acyclic(
            {item.capability_id: item.supersedes for item in snapshot.capabilities},
            "capability supersession",
            errors,
        )
        _acyclic(
            {
                item.capability_id: item.required_capabilities
                for item in snapshot.capabilities
            },
            "required capability",
            errors,
        )


def _unique(
    entries: Iterable[object],
    key: Callable[[object], str],
    label: str,
    errors: list[str],
) -> dict[str, object]:
    result: dict[str, object] = {}
    for entry in entries:
        identifier = key(entry)
        if identifier in result:
            errors.append(f"duplicate {label} id: {identifier}")
        else:
            result[identifier] = entry
    return result


def _identifier(
    value: str, pattern: re.Pattern[str], label: str, errors: list[str],
) -> None:
    if not pattern.fullmatch(value):
        errors.append(f"invalid {label} id: {value}")


def _enum(
    value: str,
    allowed: tuple[str, ...],
    identifier: str,
    field: str,
    errors: list[str],
) -> None:
    if value not in allowed:
        errors.append(f"{identifier} has invalid {field}: {value}")


def _references(
    values: tuple[str, ...],
    known: dict[str, object],
    owner: str,
    field: str,
    errors: list[str],
) -> None:
    if len(values) != len(set(values)):
        errors.append(f"{owner} has duplicate {field}")
    for value in values:
        if value == owner:
            errors.append(f"{owner} has self-reference in {field}")
        elif value not in known:
            errors.append(f"{owner} has unknown {field}: {value}")


def _gaps(
    gaps, owner: str, errors: list[str], known_ids: set[str],
) -> None:
    for gap in gaps:
        if gap.gap_type not in GAP_TYPES:
            errors.append(f"{owner} has invalid gap type: {gap.gap_type}")
        if gap.subject_id != owner:
            errors.append(
                f"{owner} has gap with mismatched subject: {gap.subject_id}"
            )
        for related_id in gap.related_ids:
            if related_id not in known_ids:
                errors.append(f"{owner} gap has unknown related_id: {related_id}")


def _acyclic(
    graph: dict[str, tuple[str, ...]], label: str, errors: list[str],
) -> None:
    visiting: set[str] = set()
    visited: set[str] = set()

    def visit(identifier: str) -> bool:
        if identifier in visiting:
            return True
        if identifier in visited:
            return False
        visiting.add(identifier)
        if any(
            dependency in graph and visit(dependency)
            for dependency in graph[identifier]
        ):
            return True
        visiting.remove(identifier)
        visited.add(identifier)
        return False

    for identifier in graph:
        if visit(identifier):
            errors.append(f"{label} cycle detected")
            return


def _inside(path: Path, root: Path) -> bool:
    try:
        path.relative_to(root)
        return True
    except ValueError:
        return False
