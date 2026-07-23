# Knowledge Registry Standard v1

## Status

- Standard ID: `STD-KREG-0001`
- Status: Active
- Owner: AI Factory OS Architecture
- Effective Sprint: AFDE-4.7

## Purpose

The Knowledge Registry records which repository-derived propositions are
official, their authority and scope, their source documents, their conflicts
and supersession lineage, and the capabilities that depend on them.

It is an index over Source of Record documents. It does not ingest arbitrary
content, execute retrieval, choose capabilities, or operate Runtime.

## Knowledge ID

Knowledge IDs use:

```text
KNW-<DOMAIN>-<four-digit sequence>
```

IDs are stable and are never reused after retirement. A wording change that
does not change meaning may retain the ID. A scope or semantic change requires
review for a new ID or explicit supersession.

## Knowledge Entry Schema

| Field | Required | Meaning |
| --- | --- | --- |
| `knowledge_id` | yes | Stable Knowledge ID |
| `title` | yes | Short proposition name |
| `statement` | yes | Exact knowledge claim |
| `knowledge_type` | yes | Taxonomy value |
| `authority_level` | yes | Authority classification |
| `scope` | yes | Repository, product, subsystem, or operation boundary |
| `status` | yes | Knowledge lifecycle status |
| `owner` | yes | Accountable role or team |
| `source_documents` | yes | One or more registered official document IDs and anchors |
| `capability_bindings` | yes | Capabilities that require or are described by the entry |
| `conflicts_with` | yes | Conflicting Knowledge IDs, or an empty list |
| `supersedes` | yes | Replaced Knowledge IDs, or an empty list |
| `effective_date` | yes | Date authority begins |
| `validation` | yes | Review method and evidence reference |
| `known_gaps` | yes | Unresolved limitations, or an empty list |

Free-form copied source text is not stored as a substitute for
`source_documents`.

## Authority Level

From highest to lowest:

1. `constitutional`: repository operating principles and explicitly frozen
   baseline constraints;
2. `normative`: approved architecture, standards, policies, and decisions;
3. `contractual`: approved public contracts and schemas within their scope;
4. `validated`: implementation statements supported by repository Evidence;
5. `informative`: guides, status summaries, and reports;
6. `external_unverified`: outside information not promoted into the repository.

Higher authority does not override a more specific contractual rule outside
its scope. Apparent conflicts are resolved by the AI Reference Policy, never by
silently changing an entry.

## Scope

Scope must name the narrowest applicable boundary, such as:

- `repository`;
- `architecture.knowledge_foundation`;
- `product_layer`;
- `runtime`;
- `public_contract.beta_execute`;
- `governance.documents`.

An entry outside the active task scope is not applicable merely because it has
higher general authority.

## Status

Allowed values:

- `proposed`
- `validated`
- `active`
- `superseded`
- `rejected`
- `retired`

Only `active` entries are default official references. `validated` entries
still require activation through governance.

## Source Document and Capability Binding

- Every Active entry has at least one Active registered official source.
- A source binding includes a Document ID and a heading or stable anchor.
- A capability may bind knowledge as `required`, `supporting`, or `evidence`.
- Required knowledge must be Active before a capability can pass registry
  validation for the relevant maturity claim.
- A capability binding is metadata; it does not make the capability implemented.

## Conflict and Supersession

- Direct conflicts are recorded symmetrically with `conflicts_with`.
- An unresolved conflict makes all affected claims ineligible for automatic
  authoritative use.
- `supersedes` forms an acyclic lineage.
- A superseded entry remains readable for audit and points to its successor.
- Updating a source without synchronizing affected knowledge and capability
  entries is invalid.

## Initial Knowledge Entries

### KNW-KNOW-0001

- Title: Knowledge Foundation responsibility
- Statement: Knowledge Foundation indexes official documents, validates
  repository-derived knowledge and capability metadata, and reports gaps; it
  does not select capabilities, invoke adapters, or execute Runtime.
- Type: architectural
- Authority: normative
- Scope: `architecture.knowledge_foundation`
- Status: active
- Owner: AI Factory OS Architecture
- Sources: `DOC-ARCH-0001`, `DOC-DKM-0001`
- Capability bindings: `CAP-KNOW-0001` required
- Conflicts: none
- Supersedes: none
- Effective date: 2026-07-23
- Validation: AFDE-4.7 architecture review
- Known gaps: implementation is not present

### KNW-KNOW-0002

- Title: Registry Source of Record boundary
- Statement: Document, Knowledge, and Capability Registries are governed
  indexes and never replace the repository documents, implementation, Runtime
  state, or Evidence that they reference.
- Type: governance
- Authority: normative
- Scope: `repository`
- Status: active
- Owner: AI Factory OS Architecture
- Sources: `DOC-DKM-0001`, `DOC-DGOV-0001`
- Capability bindings: `CAP-KNOW-0001` required
- Conflicts: none
- Supersedes: none
- Effective date: 2026-07-23
- Validation: AFDE-4.7 architecture review
- Known gaps: none

### KNW-KNOW-0003

- Title: Capability state separation
- Statement: Capability lifecycle status, maturity, and implementation status
  are independent fields and must not be inferred from document existence.
- Type: capability
- Authority: normative
- Scope: `repository`
- Status: active
- Owner: AI Factory OS Architecture
- Sources: `DOC-CREG-0001`
- Capability bindings: `CAP-KNOW-0001` required
- Conflicts: none
- Supersedes: none
- Effective date: 2026-07-23
- Validation: AFDE-4.7 architecture review
- Known gaps: none

## Registry Validation

A registry change is valid only when:

1. IDs and enum values are valid and unique;
2. every Active entry resolves to an eligible Active source document;
3. scopes and owners are non-empty;
4. conflict links are symmetric and supersession is acyclic;
5. capability bindings resolve to registered capability IDs;
6. required source, knowledge, and capability changes appear in the same
   governance unit;
7. no Draft, Deprecated, generated, or external material is elevated
   implicitly;
8. Git review history provides the audit trail.

Validation is architectural in AFDE-4.7. Machine-readable registry validation
is a later implementation capability and is not implied by this standard.
