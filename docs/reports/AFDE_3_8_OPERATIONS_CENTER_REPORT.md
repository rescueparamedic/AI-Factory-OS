# AFDE-3.8 Operations Center Report

## Outcome

AFDE-3.8 extends the AFDE-3.7 Interactive Operations Dashboard with read-only
multi-session comparison and operational analytics. It adds no runtime engine,
state store, database, dependency, telemetry service, or mutation route.

## Architecture

The authority chain is:

`RuntimePipeline -> RuntimeDashboard Snapshot -> OperationsAnalytics -> DashboardAPI -> Browser`

`OperationsAnalytics` receives mappings, deep-copies them, produces stable
session/finding ordering, and returns safely copied JSON-compatible values. It
never imports or accesses RuntimePipeline. DashboardAPI performs discovery and
session-ID validation before loading snapshots. An unreadable discovered
session is represented as Unavailable without exposing a path.

## API and validation

- Existing `/runtime`, `/session`, `/sessions`, `/workers`, `/timeline`,
  `/approval-queue`, `/evidence`, `/repository`, and `/config` routes remain.
- `/operations` derives analytics for the selected primary session.
- `/compare` requires 2 to 5 unique `session_id` query values.
- `/operations-report` returns a JSON report, CSV text, and sanitized suggested
  filenames in a JSON response.
- Duplicate IDs retain their first position before the analytics projection's
  stable session-ID ordering. Invalid/traversal IDs return JSON 400; valid but
  unknown IDs return JSON 404; more than five returns JSON 400.
- GET and HEAD are the only allowed methods. Mutation methods return JSON 405
  before provider or snapshot access.

## KPI definitions

All KPIs are labeled snapshot-derived. Discovered count is the validated
discovery result size; selected count is the number of compared unique IDs.
Runtime status counts include Running, Waiting, Completed, Failed, and
Unavailable. Worker, failed-worker, pending-approval, and evidence counts sum
rows present in selected snapshots. Progress counts group explicit pipeline or
session values as explicit, lifecycle-derived values separately, and everything
else as unavailable.

Elapsed time uses valid timezone-aware timestamps. Terminal sessions end at
their valid updated timestamp; Running/Waiting sessions end at the common
projection snapshot time. Negative intervals are rejected. Average and median
use only available elapsed durations and publish that denominator. No available
duration produces `null`, not zero.

## Stage duration provenance

Target names normalize to Planning, Development, QA, Documentation, Approval,
and Release without modifying source records. A non-negative explicit
`duration_seconds` is measured and takes precedence. Timeline transition gaps
or current active-stage elapsed time are inferred only when valid timestamps
exist. All other values are unavailable. Negative durations and naive or
malformed timestamps are rejected.

## Bottleneck rules and thresholds

Findings contain type, severity, session, optional stage/worker/approval,
evidence fields, reason, provenance, and advisory-only status. Rules are:

- longest available stage: info, measured or inferred provenance;
- Waiting plus pending approval: warning, measured;
- pending approval age at least 30 minutes: warning; at least 2 hours: critical;
- failed workers: critical, measured;
- a normalized failure category repeated at least twice: warning, heuristic;
- active updated age at least 30 minutes: aging warning; at least 2 hours:
  stale critical.

Thresholds are centralized in `operations_analytics.py` and returned by the API.
They avoid an opaque score and do not trigger corrective action. Completed and
failed sessions do not receive active-staleness findings.

## Approval delay and failure analysis

Pending approval rows expose only existing ID, actor/worker, risk/permission,
action, request time, and derived age. Oldest and median ages use only rows with
valid request timestamps and publish their denominator. Missing timestamps stay
unavailable and approval records are never consumed or changed.

Failure summaries count failed workers and reported failure-like timeline
events, bound displayed messages to 500 sanitized characters, normalize repeated
reported categories, retain the most recent reported record, and correlate only
already-exposed evidence identifiers. They explicitly distinguish reported
errors from heuristic repeated signals and state that root cause is unavailable.

## Browser behavior

The multi-select accepts 2 to 5 discovered sessions. Selection exists only as
repeated URL `compare` parameters, survives runtime/discovery refresh, and is
revalidated when discovery changes. Inaccessible selections are removed with a
live notice. One consolidated comparison request refreshes alongside the
existing primary runtime poll. Operations requests do not overlap; a generation
token discards responses from an obsolete selection; abort controllers are
cleaned up on unload.

KPIs, comparison table, durations, approval delays, failures, staleness, and
findings render from one projection. Finding session/severity/type/stage/search
filters and severity/duration/timestamp sorting operate on copied arrays and
preserve controls across polling where options remain valid. Findings are capped
at 100 visible rows. JSON and CSV are generated from the current projection
through browser Blobs with sanitized names; the server writes nothing.

## Accessibility and security

Controls have explicit labels and keyboard-native multi-selection. Results use
an ARIA polite live region, the comparison uses a captioned semantic table,
severity is stated in text, focus styles and AFDE-3.7 dialog focus trapping
remain, tables scroll at narrow widths, and reduced-motion behavior remains.

The server remains localhost-only with CSP (including `form-action 'none'`),
frame denial, no-store, JSON 404/405 responses, GET/HEAD-only APIs, textContent
rendering, no external assets, validated IDs, traversal rejection, no paths in
responses, and metadata-only evidence. No runtime executor, Automation Bridge,
Approval Guardian mutation, Controlled Execution mutation, repository mutation,
or dashboard action control is invoked or exposed.

## Deferred limitations

Authentication/RBAC/TLS, remote/production/multi-user access, WebSocket/SSE,
persistent analytics/history, telemetry ingestion, AI-generated root-cause
analysis, historical approval analytics, mutation controls, PDF reports, and
server-side export storage remain outside AFDE-3.8.
