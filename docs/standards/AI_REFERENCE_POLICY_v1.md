# AI Reference Policy v1

## Status

- Policy ID: `POL-AIREF-0001`
- Status: Active
- Owner: AI Factory OS Architecture
- Effective Sprint: AFDE-4.7

## Purpose

This policy defines which materials an AI may use as official evidence, how it
resolves scope, status, priority, and conflicts, and how it reports missing or
external knowledge.

## Reference Eligibility

A source is eligible for official reference only when:

- it is inside the repository and tracked on the applicable branch;
- its registered status is Active;
- its owner, scope, and canonical path are known;
- it is not a generated draft, conversation log, informal research note, or
  unpromoted external source;
- its use complies with the source's scope and authority;
- affected registry bindings are valid.

Draft, In Review, Deprecated, Superseded, Retired, missing, and untracked
sources are excluded by default. They may be cited as historical or
non-authoritative context only with an explicit label.

## Reference Priority

For sources applicable to the same scope, resolve in this order:

1. constitutional repository principles and explicit frozen constraints;
2. approved public contracts and security boundaries for their exact scope;
3. Active architecture, standards, policies, and recorded decisions;
4. Active Knowledge and Capability Registry entries with valid source binding;
5. validated implementation Evidence and release evidence;
6. current project status and changelog;
7. guides and reports;
8. historical, generated, research, conversation, and external material.

A registry entry helps discovery but never outranks or replaces its Source of
Record document.

## Scope Resolution

1. Identify the task, subsystem, product, and contract boundary.
2. Reject sources outside that boundary.
3. Prefer the narrowest applicable authoritative source.
4. Apply broader architecture only where it does not contradict a narrower
   approved contract.
5. Keep Runtime truth, Product projection, and documentation metadata separate.

## Status Resolution

- Active is eligible by default.
- Draft and In Review require explicit user direction and must be labeled.
- Deprecated and Superseded are historical unless the task concerns migration.
- Retired and Rejected cannot support a current claim.
- Missing status fails closed and is treated as a reference gap.

## Conflict Resolution

When two eligible sources disagree:

1. verify both paths, status, scope, and source revision;
2. prefer the source governing the narrower applicable scope;
3. apply contractual and security constraints within their exact boundaries;
4. inspect explicit decision and supersession records;
5. use the more recent effective authority only when governance permits it;
6. if conflict remains, do not choose silently—report a Knowledge Gap and
   request owner resolution.

Conflicting source text must not be rewritten, merged, or omitted merely to
produce a single answer.

## Missing Knowledge Handling

When required knowledge is absent, invalid, stale, or conflicting:

- identify the missing Knowledge ID or required proposition;
- identify the affected capability or decision;
- classify it as a Knowledge Gap;
- avoid claiming certainty or advancing dependent capability status;
- propose the required source, review, or validation action;
- request human direction when the gap changes scope, contract, safety, cost,
  or external effects.

## Missing Capability Handling

When knowledge exists but no eligible capability or implementation can satisfy
the request:

- report a Capability Gap;
- distinguish architecture, implementation, validation, and operational gaps;
- do not invent an adapter, provider, Runtime state, or Evidence;
- do not infer availability from a document or provider claim.

## External Knowledge Handling

- External material is `external_unverified` by default.
- It may inform research but cannot be represented as repository authority.
- Promotion requires an eligible repository source document, ownership, scope,
  conflict review, a Knowledge ID, and governance approval.
- Credentials, secrets, private data, and restricted content must not be copied
  into documents, registries, logs, or Evidence.
- Paid calls, uploads, publication, and deployment require explicit approval.

## Machine-readable Projection

AFDE-4.8 projects the governed document, knowledge, capability, authority, and
reference-priority metadata through
`docs/registry/KNOWLEDGE_FOUNDATION_REGISTRY_v1.json` and the read-only
`afde.knowledge.KnowledgeFoundationProvider`.

The Provider returns deterministic eligible metadata and explicit gaps. It
does not replace official Markdown, search Markdown, choose a Capability
implementation, call a tool, or execute Runtime. If the Registry is malformed
or its bindings are invalid, loading fails closed.

## Reference Traceability

An AI-generated architecture or governance conclusion must be traceable to:

- repository-relative source path;
- heading or stable anchor;
- applicable Document and Knowledge IDs when registered;
- source status and scope;
- repository commit or working-tree state;
- conflicts, gaps, or non-authoritative sources used as context.

The answer must distinguish observed repository facts, registered knowledge,
and inference.

## Prohibited Behavior

An AI must not:

- treat its memory, a conversation, or an external page as repository truth;
- use an untracked, Draft, Deprecated, or generated document as official by
  default;
- hide or resolve a conflict without trace;
- fabricate a document, Knowledge ID, Capability ID, implementation, or
  Evidence;
- equate architecture approval with implementation;
- elevate capability status or maturity without required evidence;
- execute Runtime, select a capability, or invoke a tool from the Knowledge
  Foundation;
- bypass the Capability Resolver, Tool Adapter, Approval, Runtime, or Evidence
  boundaries;
- change public contracts, merge, deploy, publish, or make paid calls without
  the required separate approval.
