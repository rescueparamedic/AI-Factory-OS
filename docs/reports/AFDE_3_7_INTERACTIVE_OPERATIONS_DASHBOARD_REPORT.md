# AFDE-3.7 Interactive Operations Dashboard Report

## Baseline and objective

AFDE-3.7 starts from `origin/develop` commit `914a5dc`, the merge commit for
AFDE-3.6 PR #20. It adds practical navigation and inspection while preserving
the read-only browser boundary.

## Architecture

~~~text
Persisted Runtime Sessions        RuntimePipeline
           |                            |
           +----------+-----------------+
                      v
          RuntimeDashboard Snapshot Projection
                 |                 |
                 v                 v
       Safe Session Summaries   Selected Snapshot
                 |                 |
                 +------ DashboardAPI ------+
                                           v
                          Local GET/HEAD browser UI
                                           |
                          Search/filter/sort/detail/stats
                          as presentation state only
~~~

RuntimePipeline remains authoritative. `RuntimeDashboard` discovers existing
session folders and reuses its snapshot projection. DashboardAPI remains
transport-neutral, and HTTP controllers never import or access RuntimePipeline.
No session registry, database, analytics store, or second runtime engine exists.

## Session discovery and validation

`GET /sessions` returns session ID, status, created/updated timestamps, current
task/worker, progress and source, approval count, and evidence count. Paths and
raw session data are excluded. Malformed session files produce an `Unavailable`
summary instead of failing discovery.

Session-specific reads accept `?session_id=...`. The ID must match the bounded
alphanumeric/hyphen/underscore syntax and must exactly equal a discovered ID.
Traversal receives JSON 400; a valid but unknown ID receives JSON 404. The
browser selector contains only discovery results and stores its selection only
in page/URL presentation state.

## Search, filters, and sorting

- Global case-insensitive text search covers current snapshot task/workers,
  approvals, timeline, evidence, and repository metadata.
- Worker filters cover status, progress source, and name/role.
- Approval filter options are rebuilt from statuses present in each snapshot,
  preserving the active choice while that status remains available.
- Timeline filters cover event, actor, task, status, and text.
- Evidence filters cover type, availability, label, and identifier.
- Stable deterministic sorting supports workers, progress, approval risk,
  timeline direction, and evidence timestamp. Missing values sort last.

Arrays are copied before filter/sort, so source snapshot objects are unchanged.
Controls persist across polling refresh because they are independent browser
presentation inputs. Clear empty and no-result states are announced.

## Detail inspection and statistics

Worker, approval, timeline, evidence, and session buttons open one native
read-only dialog. Values are rendered as text, Escape closes, keyboard focus is
contained, and focus returns to the invoker. There is no file access or action.

Statistics are recalculated from the current snapshot: total/running/completed/
failed workers, pending approvals, timeline and evidence counts, plus explicit,
derived, and unavailable progress counts. They are not persisted.

## Polling and performance

One guarded `/runtime` request remains authoritative per interval. Session
discovery uses one separate guarded `/sessions` request every 30 seconds. Both
timers and active requests are cleaned up on unload. Session changes abort and
discard stale in-flight results. Timeline output is capped at 50 items. Browser
filtering operates on copied arrays without accumulating events across polls.

## Accessibility

Controls have visible labels and focus indicators. Navigation is sticky and
keyboard accessible. Result/session changes use ARIA live status. The native
dialog supports Escape, Tab containment, and focus return. Status has visible
text, reduced-motion behavior remains active, and layouts adapt to narrow views.

## Read-only security boundary

- Localhost only; GET/HEAD only; mutation methods remain JSON 405.
- CSP, `form-action 'none'`, no-store, frame denial, MIME protection, and
  referrer restrictions remain enabled.
- Runtime data uses safe text DOM APIs; no external scripts, styles, fonts,
  analytics, search service, or network dependency exists.
- Session IDs cannot address paths. Static and evidence path traversal remains
  rejected, and evidence remains session-contained metadata only.
- No Approval Guardian, Controlled Execution, Runtime executor, Automation
  Bridge, approval, evidence, or repository mutation path is invoked.

## API compatibility

Existing `/runtime`, `/session`, `/workers`, `/timeline`, `/approval-queue`,
`/evidence`, `/repository`, and `/config` endpoints remain. `/sessions` is the
only new endpoint. Existing terminal, JSON, live terminal, and web CLI commands
remain compatible.

## Deferred scope and limitations

Authentication, RBAC, TLS, remote access, production hosting, WebSocket/SSE,
multi-user operation, cross-session search, saved filters, server pagination,
evidence preview, and all dashboard mutations are deferred.

## Verification

- AFDE-3.7 targeted tests: `8 passed`.
- AFDE-3.3 through AFDE-3.7 focused dashboard regression: `92 passed`.
- Full regression: `552 passed, 1 skipped`.
- Compileall, `git diff --check`, import, and JavaScript syntax: PASS.
- High-confidence credential scan: PASS, zero matches.
- Explicit CLI/API/browser/discovery/switching/search/filter/sort/malformed/
  traversal/mutation/persisted-byte smoke bundle: `27 passed`.
