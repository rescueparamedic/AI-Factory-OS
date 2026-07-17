# AFDE-3.9 Runtime History Foundation Report

## Objective and outcome

AFDE-3.9 adds a lightweight foundation for recording and querying major Runtime
events while preserving RuntimePipeline and Dashboard architecture. It reuses
the existing per-session `events.jsonl` ledger and existing Runtime emission
points. No database, external dependency, new runtime engine, or mutation API is
introduced.

## Architecture

The event path is:

`Runtime lifecycle -> EventStream -> RuntimeHistoryStore -> events.jsonl`

The read path is:

`events.jsonl -> RuntimeHistoryStore -> Dashboard Snapshot / CLI`

RuntimePipeline and RuntimeSession remain authoritative for current state.
History is append-only evidence and a read-only projection, not a state replay
engine or alternative orchestrator.

## Runtime Event model

Newly appended events require:

- `event_id`: unique `EVT-*` identifier;
- `session_id`: validated runtime session ID;
- timezone-aware ISO `timestamp`;
- canonical `event_type`;
- `actor` and `status`;
- optional `worker_id` and `metadata`.

The existing `event`, `detail`, `task_id`, `state`, and `payload` fields remain
for backward compatibility. New appends fail closed when required fields or a
valid timestamp are absent.

Canonical types include SESSION_STARTED, WORKER_STARTED, WORKER_COMPLETED,
APPROVAL_REQUESTED, APPROVAL_COMPLETED, QA_COMPLETED, ERROR_OCCURRED, and
SESSION_COMPLETED. The original event name is retained alongside the canonical
type. Status is deterministically derived as running, waiting, completed,
failed, rejected, or an existing lifecycle state.

## History Store

RuntimeHistoryStore validates session IDs and never accepts arbitrary paths.
It appends one JSON object per line to the existing session ledger, reads one
session, returns deep copies, sorts valid timezone-aware timestamps in stable
chronological order, and places invalid legacy timestamps last without inventing
times. Filters cover event type, actor, status, worker, since, until, and a
bounded limit.

Legacy rows are not rewritten. At read time they receive deterministic
`EVT-LEGACY-*` identifiers and canonical event fields. The same bytes always
produce the same projection.

## Runtime integration

The existing Runtime already emits creation, worker, task, role, approval, QA,
provider failure, lifecycle, and completion records. EventStream now supplies
the expanded model and delegates appends to RuntimeHistoryStore, so those flows
gain history coverage without invasive edits. Approval Guardian, Controlled
Execution, RuntimePipeline transitions, worker ordering, and completion logic
are unchanged.

## Dashboard

RuntimeDashboard Snapshot now includes:

- `event_history`: normalized append-only events;
- `error_events`: ERROR_OCCURRED subset;
- `history_summary`: counts, range, and read-only marker;
- enriched existing `timeline` rows with event ID, canonical type, actor,
  status, and metadata.

DashboardAPI adds GET/HEAD-compatible `/history` and `/error-events` views. The
existing browser Timeline remains the presentation surface, now labels canonical
types, shows error events prominently, and retains safe text rendering, filters,
visible limits, polling, and responsive behavior.

## CLI

- `runtime-history`: history summary and event list, with optional JSON.
- `runtime-events`: filtered event list, with optional JSON.
- `runtime-export`: JSON or safely escaped CSV written to stdout.

All commands require a session ID and support event type, actor, status, worker,
time range, and limit filters. They perform no runtime or repository mutation.

## Compatibility and security

The implementation uses only the Python standard library. Session validation
rejects traversal. Dashboard controllers do not access RuntimePipeline directly.
History responses expose no session filesystem paths. CSV protects leading
formula characters. Runtime Session files and legacy history bytes are not
modified by reads or exports.

## Known limitations

The local JSONL ledger has no cross-process lock, transaction, signature,
tamper-evident chain, rotation, or retention. Reads are in-memory per session.
Legacy IDs are deterministic projections rather than persisted migrations.
Remote access, authentication/RBAC/TLS, streaming/WebSocket/SSE, server-side
archives, replay/state reconstruction, and database-backed analytics remain out
of scope.
