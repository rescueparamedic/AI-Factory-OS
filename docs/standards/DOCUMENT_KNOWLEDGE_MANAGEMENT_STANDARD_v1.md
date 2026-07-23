# Document and Knowledge Management Standard v1

## Status

- Standard ID: `STD-DKM-0001`
- Status: Active
- Owner: AI Factory OS Architecture
- Scope: Repository documentation and repository-derived knowledge
- Effective Sprint: AFDE-4.7

## Purpose

This standard defines how AI Factory OS distinguishes documents from
knowledge, how each is governed through its lifecycle, and how approved
knowledge binds to capabilities.

The repository remains the Source of Record. Registries are validated indexes
over repository sources; they never replace or silently rewrite those sources.

## Definitions

- **Document**: a version-controlled repository artifact written for a stated
  audience and purpose.
- **Knowledge**: a scoped, attributable proposition promoted from one or more
  eligible source documents and recorded in the Knowledge Registry.
- **Registry**: a governed index of identifiers, status, relationships, and
  source references. A registry is not an execution engine or a parallel truth
  store.
- **Official source document**: an Active repository document with an owner,
  scope, and stable path that is eligible under the AI Reference Policy.
- **Gap**: required knowledge or capability that is missing, unresolved,
  conflicting, or not mature enough for the intended use.

Document existence does not prove that knowledge is valid, and neither
document nor knowledge existence proves capability implementation.

## Document Taxonomy

| Type | Purpose | Typical location |
| --- | --- | --- |
| architecture | System boundaries, responsibilities, and invariants | `docs/development/`, `docs/architecture/` |
| standard | Normative definitions, schemas, and governance | `docs/standards/` |
| policy | Mandatory decision or safety rules | `docs/standards/` |
| decision | Accepted architecture or governance decision | `DECISION_LOG.md` |
| index | Discovery map to canonical sources | `MASTER_INDEX.md` |
| status | Current delivery and maturity statement | `PROJECT_STATUS.md` |
| baseline | Frozen historical reference | `PROJECT_BASELINE.md`, `docs/baselines/` |
| evidence | Verifiable result of implementation or validation | `docs/releases/`, Runtime Evidence |
| report | Time-bounded analysis or Sprint result | `docs/reports/` |
| guide | Operational or user instruction | `docs/guides/`, `docs/operations/` |
| generated draft | Non-authoritative generated output pending review | `docs/generated/` |
| external reference | Material outside this repository | not authoritative until promoted |

## Knowledge Taxonomy

| Type | Meaning |
| --- | --- |
| architectural | Accepted system structure, boundary, or invariant |
| governance | Ownership, review, approval, synchronization, or audit rule |
| capability | Definition, dependency, state, or maturity of a capability |
| operational | Approved procedure for operating the system |
| implementation | Verified statement about implemented behavior |
| evidence | Verified observation supporting another knowledge entry |
| historical | Superseded or frozen context retained for audit |
| external | Unpromoted outside information; not official by default |

## Document Lifecycle

```text
Draft -> In Review -> Active -> Deprecated -> Retired
```

- Draft and In Review documents are not default official AI references.
- Active documents may be official sources when registered and eligible.
- Deprecated documents remain available for transition and audit but require a
  `superseded_by` reference.
- Retired documents are historical only.
- A baseline remains immutable unless a separately approved baseline operation
  explicitly creates or replaces the baseline.

## Knowledge Lifecycle

```text
Proposed -> Validated -> Active -> Superseded -> Retired
                  \-> Rejected
```

- Proposed knowledge is a candidate and cannot satisfy a required-knowledge
  dependency.
- Validated knowledge has passed source, scope, and conflict checks.
- Active knowledge may satisfy a capability dependency.
- Superseded knowledge retains lineage but is not selected by default.
- Rejected knowledge is retained only when needed for decision audit.

## Document Registry Minimum Schema

Every registered official document provides the governed fields below.
`source_commit` is optional in the machine-readable MVP; every other field is
required.

| Field | Requirement |
| --- | --- |
| `document_id` | Stable `DOC-<DOMAIN>-NNNN` identifier |
| `title` | Human-readable title |
| `path` | Repository-relative canonical path |
| `document_type` | Value from the Document Taxonomy |
| `owner` | Accountable repository role or team |
| `scope` | Applicability boundary |
| `status` | Document lifecycle status |
| `authority_level` | Authority used by AI reference resolution |
| `version` | Document version or `living` |
| `effective_date` | Date the current authority became effective |
| `supersedes` | Prior document IDs, or an empty list |
| `source_commit` | Optional revision metadata resolved from Git history |
| `knowledge_ids` | Knowledge entries promoted from the document |
| `capability_ids` | Capabilities supported or defined by the document |

An Active entry must resolve to a tracked file at the registered path.
`source_commit` is optional metadata in the machine-readable projection. A
Registry file must not embed a placeholder, stale value, or the SHA of the
Commit that is simultaneously creating that Registry. Git history remains the
authoritative revision audit.

## Machine-readable Registry Projection

AFDE-4.8 implements the governed projection at:

`docs/registry/KNOWLEDGE_FOUNDATION_REGISTRY_v1.json`

The single versioned snapshot contains separate `documents`, `knowledge`, and
`capabilities` collections plus authority and reference-priority metadata.
`afde.knowledge` loads and validates that exact JSON file; it does not search
Markdown.

The JSON snapshot is not a Source of Truth and does not copy complete source
documents or store execution configuration. It is a read-only index over the
official Markdown sources. A source change and its affected JSON Registry
bindings remain one governance unit.

## Initial Authoritative Document Inventory

The table is a compact representation of full Document Registry entries.
Unless a row or its source document narrows a value, the common fields are:
`owner: AI Factory OS Architecture`, `scope: repository`,
`authority_level: normative`, `effective_date: 2026-07-23`,
`supersedes: []`, `source_commit: resolved-from-git-history`,
`knowledge_ids: []`, and `capability_ids: []`. Baseline authority
is `constitutional`; status and changelog authority is `informative`.

Binding overrides are:

- `DOC-ARCH-0001` and `DOC-DKM-0001` bind `KNW-KNOW-0001`;
- `DOC-DKM-0001` and `DOC-DGOV-0001` bind `KNW-KNOW-0002`;
- `DOC-CREG-0001` binds `KNW-KNOW-0003`;
- `DOC-ARCH-0001`, `DOC-ARCH-0002`, `DOC-DKM-0001`, `DOC-KREG-0001`,
  `DOC-CREG-0001`, `DOC-DGOV-0001`, and `DOC-AIREF-0001` bind
  `CAP-KNOW-0001`.

| Document ID | Path | Type | Status | Version |
| --- | --- | --- | --- | --- |
| `DOC-ARCH-0001` | `docs/development/AFDE_ARCHITECTURE_v1.md` | architecture | Active | v1 |
| `DOC-ARCH-0002` | `docs/architecture/AI_DEVELOPMENT_ENGINE_PRODUCT_LAYER.md` | architecture | Active | living |
| `DOC-DKM-0001` | `docs/standards/DOCUMENT_KNOWLEDGE_MANAGEMENT_STANDARD_v1.md` | standard | Active | v1 |
| `DOC-KREG-0001` | `docs/standards/KNOWLEDGE_REGISTRY_STANDARD_v1.md` | standard | Active | v1 |
| `DOC-CREG-0001` | `docs/standards/CAPABILITY_REGISTRY_STANDARD_v1.md` | standard | Active | v1 |
| `DOC-DGOV-0001` | `docs/standards/DOCUMENT_GOVERNANCE_STANDARD_v1.md` | standard | Active | v1 |
| `DOC-AIREF-0001` | `docs/standards/AI_REFERENCE_POLICY_v1.md` | policy | Active | v1 |
| `DOC-INDEX-0001` | `MASTER_INDEX.md` | index | Active | living |
| `DOC-DEC-0001` | `DECISION_LOG.md` | decision | Active | living |
| `DOC-STATUS-0001` | `PROJECT_STATUS.md` | status | Active | living |
| `DOC-CHANGE-0001` | `CHANGELOG.md` | status | Active | living |
| `DOC-BASE-0001` | `PROJECT_BASELINE.md` | baseline | Active | living |

The inventory is the minimum AFDE-4.7 document registry. Later automation may
move entries to a machine-readable representation only through an approved,
compatibility-preserving governance change.

## Document-to-Knowledge Promotion

A document statement becomes registered knowledge only when:

1. the source document is tracked, Active, and eligible for official reference;
2. the proposition is stated precisely with a bounded scope;
3. an owner validates its authority and checks conflicts;
4. a Knowledge ID and source binding are added;
5. dependent capability entries are synchronized in the same change;
6. review and approval evidence is recorded through Git history.

Generated drafts, conversation logs, research notes, and external sources
cannot be promoted implicitly.

## Knowledge-to-Capability Binding

- Capability entries declare `required_knowledge` by Knowledge ID.
- Only Active knowledge can satisfy a required-knowledge dependency.
- Missing, Proposed, Superseded, Rejected, or conflicting knowledge produces a
  `known_gap`; it must never be treated as satisfied.
- A binding provides decision input to the Capability Resolver but does not
  select an adapter or execute a tool.
- Changing a bound source document, knowledge entry, or capability entry is one
  governance unit and must be reviewed together.

## Invariants

- Knowledge Foundation does not run Runtime.
- Knowledge Foundation does not select capabilities or adapters.
- Registries do not replace repository Source of Record documents.
- Status, maturity, and implementation status remain separate.
- RAG, vector databases, embeddings, and multimodal implementation are outside
  this standard.
