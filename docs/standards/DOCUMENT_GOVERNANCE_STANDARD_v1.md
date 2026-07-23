# Document Governance Standard v1

## Status

- Standard ID: `STD-DGOV-0001`
- Status: Active
- Owner: AI Factory OS Architecture
- Effective Sprint: AFDE-4.7

## Purpose

This standard governs ownership, changes, review, approval, synchronization,
deprecation, and audit for official AI Factory OS documents and registries.

## Document Ownership

Every official document has:

- one accountable owner;
- an explicit scope and document type;
- a lifecycle status;
- a canonical repository path;
- an authority level;
- a version or `living` designation.

The owner validates accuracy and synchronization. Git authorship alone does
not establish ownership.

Default ownership:

| Document class | Default owner |
| --- | --- |
| architecture, registry standard, reference policy | AI Factory OS Architecture |
| Runtime contract and Evidence | Runtime owner |
| Product Layer contract | Product Layer owner |
| public CLI/Desktop contract | Product owner |
| security and approval policy | Approval/Security owner |
| release evidence | Release owner |

## Change Classification

| Class | Description | Minimum gate |
| --- | --- | --- |
| C0 | Formatting or typo with no semantic effect | owner review |
| C1 | Informative clarification, link, or status update | owner review and consistency check |
| C2 | Normative architecture, standard, policy, registry, lifecycle, or authority change | architecture review and synchronized registry update |
| C3 | Public contract, Runtime lifecycle, Evidence schema, security boundary, merge/deployment authority, or breaking change | separate approved implementation Sprint and contract-owner approval |

AFDE-4.7 is a C2 document change. It is not authorization for a C3 change.

## Review and Approval Gate

Before approval:

1. audit current `develop` and working-tree state;
2. identify canonical and untracked documents;
3. map reused capabilities and gaps;
4. identify exact files to modify, create, and preserve.

Before merge:

1. validate document links, identifiers, enums, source bindings, and
   supersession relationships;
2. confirm Registry and source document changes are synchronized;
3. confirm no Runtime, Product Layer, Planner, Resolver, Tool Adapter, public
   contract, or Evidence schema change entered the Sprint;
4. review the complete diff;
5. record the decision, status, and changelog entry;
6. obtain Product Owner approval for merge.

Approval of architecture edits does not imply approval of implementation,
external calls, publication, deployment, or merge.

## Git Workflow

- `develop` is the repository Source of Truth.
- Work occurs on a dedicated `feature/*` branch based on synchronized
  `develop`.
- Unrelated dirty or untracked user work is preserved.
- Commits are focused and auditable.
- Pull requests target `develop`.
- Merge Commit only is the accepted merge strategy.
- Direct push to protected branches and automatic merge are prohibited.
- Merge requires explicit user approval.

## Registry Synchronization

A source document change and every affected Document, Knowledge, and Capability
Registry entry form one governance unit.

The unit is invalid if:

- a source moves without its Document Registry path changing;
- semantics change without affected Knowledge entries being reviewed;
- required knowledge changes without dependent capabilities being reviewed;
- status advances without the required implementation or Evidence;
- an Active entry points to a Draft, Deprecated, missing, or untracked source.

## Deprecation and Supersession

- Deprecation is explicit; deletion is not a substitute.
- Deprecated documents and entries identify `superseded_by` or explain why no
  replacement exists.
- Supersession is directional, traceable, and acyclic.
- Historical baselines and release Evidence remain immutable audit artifacts.
- Package snapshots and generated drafts must identify their non-canonical
  role when they duplicate a living repository document.

## Naming and Versioning

- Living root documents retain stable unversioned names.
- Normative standards use `<SUBJECT>_v<major>.md`.
- Breaking semantic changes increment the major version and explicitly
  supersede the prior standard.
- Compatible clarification updates the existing versioned file through Git;
  it does not create a duplicate version file.
- Sprint reports use the established `AFDE_<major>_<minor>_*` convention.
- Release notes and frozen baselines retain explicit release versions.
- IDs remain stable across filename changes and are never reused.

## Audit Trail

The minimum audit trail is:

- source branch and base commit;
- reviewed Git diff;
- decision and status updates;
- commit history;
- pull request review;
- explicit merge approval;
- merge commit.

Runtime audit logs may provide implementation Evidence but do not replace the
Git audit trail for document governance.

## Prohibited Governance Actions

- treating a registry as a new Source of Record;
- silently promoting generated or external material;
- editing a frozen baseline to describe current behavior;
- inferring implementation from architecture approval;
- changing a public contract under a documentation-only classification;
- auto-approving merge, deployment, release, or publication;
- deleting conflicting history to make a registry appear consistent.
