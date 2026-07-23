"""Immutable typed models for the Knowledge Foundation registry."""
from __future__ import annotations

from dataclasses import dataclass
from typing import Any, Mapping, Sequence


DOCUMENT_STATUSES = ("Draft", "In Review", "Active", "Deprecated", "Retired")
DOCUMENT_TYPES = (
    "architecture", "standard", "policy", "decision", "index", "status",
    "baseline", "evidence", "report", "guide", "generated draft",
    "external reference",
)
KNOWLEDGE_STATUSES = (
    "proposed", "validated", "active", "superseded", "rejected", "retired",
)
KNOWLEDGE_TYPES = (
    "architectural", "governance", "capability", "operational",
    "implementation", "evidence", "historical", "external",
)
CAPABILITY_STATUSES = (
    "proposed", "defined", "architecture_approved",
    "implementation_in_progress", "implemented", "validated", "operational",
    "deprecated", "retired",
)
CAPABILITY_MATURITIES = ("M0", "M1", "M2", "M3", "M4", "M5", "M6")
IMPLEMENTATION_STATUSES = (
    "not_implemented", "partially_implemented", "implemented", "not_applicable",
)
GAP_TYPES = (
    "knowledge_gap", "capability_gap", "document_gap", "evidence_gap",
    "decision_required",
)
AUTHORITY_LEVELS = (
    "constitutional", "normative", "contractual", "validated",
    "informative", "external_unverified",
)


@dataclass(frozen=True)
class SourceDocumentBinding:
    document_id: str
    anchor: str

    @classmethod
    def from_value(cls, value: Any) -> "SourceDocumentBinding":
        item = _mapping(value, "source document binding")
        _fields(item, {"document_id", "anchor"}, "source document binding")
        return cls(
            document_id=_text(item["document_id"], "document_id"),
            anchor=_text(item["anchor"], "anchor"),
        )


@dataclass(frozen=True)
class CapabilityBinding:
    capability_id: str
    relation: str

    @classmethod
    def from_value(cls, value: Any) -> "CapabilityBinding":
        item = _mapping(value, "capability binding")
        _fields(item, {"capability_id", "relation"}, "capability binding")
        return cls(
            capability_id=_text(item["capability_id"], "capability_id"),
            relation=_text(item["relation"], "relation"),
        )


@dataclass(frozen=True)
class KnowledgeGap:
    gap_type: str
    subject_id: str
    message: str
    related_ids: tuple[str, ...] = ()

    @classmethod
    def from_value(cls, value: Any) -> "KnowledgeGap":
        item = _mapping(value, "knowledge gap")
        _fields(
            item,
            {"gap_type", "subject_id", "message", "related_ids"},
            "knowledge gap",
        )
        return cls(
            gap_type=_text(item["gap_type"], "gap_type"),
            subject_id=_text(item["subject_id"], "subject_id"),
            message=_text(item["message"], "message"),
            related_ids=_strings(item["related_ids"], "related_ids"),
        )


@dataclass(frozen=True)
class DocumentRegistryEntry:
    document_id: str
    title: str
    path: str
    document_type: str
    owner: str
    scope: str
    status: str
    authority_level: str
    version: str
    effective_date: str
    supersedes: tuple[str, ...]
    knowledge_ids: tuple[str, ...]
    capability_ids: tuple[str, ...]
    source_commit: str | None = None

    @classmethod
    def from_value(cls, value: Any) -> "DocumentRegistryEntry":
        item = _mapping(value, "document entry")
        required = {
            "document_id", "title", "path", "document_type", "owner", "scope",
            "status", "authority_level", "version", "effective_date",
            "supersedes", "knowledge_ids", "capability_ids",
        }
        _fields(item, required, "document entry", optional={"source_commit"})
        source_commit = item.get("source_commit")
        return cls(
            document_id=_text(item["document_id"], "document_id"),
            title=_text(item["title"], "title"),
            path=_text(item["path"], "path"),
            document_type=_text(item["document_type"], "document_type"),
            owner=_text(item["owner"], "owner"),
            scope=_text(item["scope"], "scope"),
            status=_text(item["status"], "status"),
            authority_level=_text(item["authority_level"], "authority_level"),
            version=_text(item["version"], "version"),
            effective_date=_text(item["effective_date"], "effective_date"),
            supersedes=_strings(item["supersedes"], "supersedes"),
            knowledge_ids=_strings(item["knowledge_ids"], "knowledge_ids"),
            capability_ids=_strings(item["capability_ids"], "capability_ids"),
            source_commit=(
                None if source_commit is None else _text(source_commit, "source_commit")
            ),
        )


@dataclass(frozen=True)
class KnowledgeRegistryEntry:
    knowledge_id: str
    title: str
    statement: str
    knowledge_type: str
    authority_level: str
    scope: str
    status: str
    owner: str
    source_documents: tuple[SourceDocumentBinding, ...]
    capability_bindings: tuple[CapabilityBinding, ...]
    conflicts_with: tuple[str, ...]
    supersedes: tuple[str, ...]
    effective_date: str
    validation: str
    known_gaps: tuple[KnowledgeGap, ...]

    @classmethod
    def from_value(cls, value: Any) -> "KnowledgeRegistryEntry":
        item = _mapping(value, "knowledge entry")
        required = {
            "knowledge_id", "title", "statement", "knowledge_type",
            "authority_level", "scope", "status", "owner", "source_documents",
            "capability_bindings", "conflicts_with", "supersedes",
            "effective_date", "validation", "known_gaps",
        }
        _fields(item, required, "knowledge entry")
        return cls(
            knowledge_id=_text(item["knowledge_id"], "knowledge_id"),
            title=_text(item["title"], "title"),
            statement=_text(item["statement"], "statement"),
            knowledge_type=_text(item["knowledge_type"], "knowledge_type"),
            authority_level=_text(item["authority_level"], "authority_level"),
            scope=_text(item["scope"], "scope"),
            status=_text(item["status"], "status"),
            owner=_text(item["owner"], "owner"),
            source_documents=_items(
                item["source_documents"],
                SourceDocumentBinding.from_value,
                "source_documents",
            ),
            capability_bindings=_items(
                item["capability_bindings"],
                CapabilityBinding.from_value,
                "capability_bindings",
            ),
            conflicts_with=_strings(item["conflicts_with"], "conflicts_with"),
            supersedes=_strings(item["supersedes"], "supersedes"),
            effective_date=_text(item["effective_date"], "effective_date"),
            validation=_text(item["validation"], "validation"),
            known_gaps=_items(
                item["known_gaps"], KnowledgeGap.from_value, "known_gaps",
            ),
        )


@dataclass(frozen=True)
class CapabilityRegistryEntry:
    capability_id: str
    name: str
    description: str
    owner: str
    scope: str
    status: str
    maturity: str
    implementation_status: str
    required_knowledge: tuple[str, ...]
    required_capabilities: tuple[str, ...]
    tool_dependencies: tuple[str, ...]
    adapter_dependencies: tuple[str, ...]
    runtime_dependencies: tuple[str, ...]
    implementation_references: tuple[str, ...]
    validation_evidence: tuple[str, ...]
    known_gaps: tuple[KnowledgeGap, ...]
    source_documents: tuple[str, ...]
    supersedes: tuple[str, ...]

    @classmethod
    def from_value(cls, value: Any) -> "CapabilityRegistryEntry":
        item = _mapping(value, "capability entry")
        required = {
            "capability_id", "name", "description", "owner", "scope", "status",
            "maturity", "implementation_status", "required_knowledge",
            "required_capabilities", "tool_dependencies",
            "adapter_dependencies", "runtime_dependencies",
            "implementation_references", "validation_evidence", "known_gaps",
            "source_documents", "supersedes",
        }
        _fields(item, required, "capability entry")
        return cls(
            capability_id=_text(item["capability_id"], "capability_id"),
            name=_text(item["name"], "name"),
            description=_text(item["description"], "description"),
            owner=_text(item["owner"], "owner"),
            scope=_text(item["scope"], "scope"),
            status=_text(item["status"], "status"),
            maturity=_text(item["maturity"], "maturity"),
            implementation_status=_text(
                item["implementation_status"], "implementation_status",
            ),
            required_knowledge=_strings(
                item["required_knowledge"], "required_knowledge",
            ),
            required_capabilities=_strings(
                item["required_capabilities"], "required_capabilities",
            ),
            tool_dependencies=_strings(
                item["tool_dependencies"], "tool_dependencies",
            ),
            adapter_dependencies=_strings(
                item["adapter_dependencies"], "adapter_dependencies",
            ),
            runtime_dependencies=_strings(
                item["runtime_dependencies"], "runtime_dependencies",
            ),
            implementation_references=_strings(
                item["implementation_references"], "implementation_references",
            ),
            validation_evidence=_strings(
                item["validation_evidence"], "validation_evidence",
            ),
            known_gaps=_items(
                item["known_gaps"], KnowledgeGap.from_value, "known_gaps",
            ),
            source_documents=_strings(
                item["source_documents"], "source_documents",
            ),
            supersedes=_strings(item["supersedes"], "supersedes"),
        )


@dataclass(frozen=True)
class KnowledgeFoundationSnapshot:
    schema_version: str
    documents: tuple[DocumentRegistryEntry, ...]
    knowledge: tuple[KnowledgeRegistryEntry, ...]
    capabilities: tuple[CapabilityRegistryEntry, ...]
    authority_levels: tuple[str, ...]
    reference_priority: tuple[str, ...]

    @classmethod
    def from_value(cls, value: Any) -> "KnowledgeFoundationSnapshot":
        item = _mapping(value, "registry snapshot")
        required = {
            "schema_version", "documents", "knowledge", "capabilities",
            "authority_levels", "reference_priority",
        }
        _fields(item, required, "registry snapshot")
        return cls(
            schema_version=_text(item["schema_version"], "schema_version"),
            documents=_items(
                item["documents"], DocumentRegistryEntry.from_value, "documents",
            ),
            knowledge=_items(
                item["knowledge"], KnowledgeRegistryEntry.from_value, "knowledge",
            ),
            capabilities=_items(
                item["capabilities"],
                CapabilityRegistryEntry.from_value,
                "capabilities",
            ),
            authority_levels=_strings(
                item["authority_levels"], "authority_levels",
            ),
            reference_priority=_strings(
                item["reference_priority"], "reference_priority",
            ),
        )


@dataclass(frozen=True)
class CapabilityContext:
    capability: CapabilityRegistryEntry
    required_knowledge: tuple[KnowledgeRegistryEntry, ...]
    source_documents: tuple[DocumentRegistryEntry, ...]
    authority: tuple[str, ...]
    status: str
    scope: str
    reference_priority: tuple[str, ...]
    gaps: tuple[KnowledgeGap, ...]


def _mapping(value: Any, field: str) -> Mapping[str, Any]:
    if not isinstance(value, Mapping):
        raise TypeError(f"{field} must be an object")
    return value


def _fields(
    value: Mapping[str, Any],
    required: set[str],
    field: str,
    *,
    optional: set[str] | None = None,
) -> None:
    missing = sorted(required - set(value))
    if missing:
        raise ValueError(f"{field} is missing fields: {', '.join(missing)}")
    unknown = sorted(set(value) - required - (optional or set()))
    if unknown:
        raise ValueError(f"{field} has unknown fields: {', '.join(unknown)}")


def _text(value: Any, field: str) -> str:
    if not isinstance(value, str) or not value.strip():
        raise TypeError(f"{field} must be a non-empty string")
    return value.strip()


def _strings(value: Any, field: str) -> tuple[str, ...]:
    if (
        isinstance(value, (str, bytes, Mapping))
        or not isinstance(value, Sequence)
    ):
        raise TypeError(f"{field} must be an array")
    return tuple(_text(item, field) for item in value)


def _items(value: Any, builder, field: str) -> tuple[Any, ...]:
    if (
        isinstance(value, (str, bytes, Mapping))
        or not isinstance(value, Sequence)
    ):
        raise TypeError(f"{field} must be an array")
    return tuple(builder(item) for item in value)
