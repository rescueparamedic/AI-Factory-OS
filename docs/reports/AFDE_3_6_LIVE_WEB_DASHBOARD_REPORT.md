# AFDE-3.6 Live Web Dashboard Report

## Baseline and objective

AFDE-3.6 starts from `origin/develop` commit `5cccc1c`, the merge commit for
AFDE-3.5 PR #19. It upgrades the existing browser presentation into a useful
live operations console without adding execution authority or runtime state.

## Architecture

~~~text
RuntimePipeline
        |
        v
RuntimeDashboard.snapshot
        |
        +-- Terminal renderer
        |
        +-- DashboardAPI
                 |
                 v
        Local HTTP GET/HEAD
                 |
                 v
   One browser polling controller
                 |
                 v
        Safe DOM presentation
~~~

`RuntimePipeline` remains the Single Source of Truth. Dashboard Snapshot is
the authoritative projection, and `DashboardAPI` remains transport-neutral.
HTTP controllers never access the pipeline. Browser state contains only the
polling lifecycle and last successfully rendered snapshot needed to preserve
the view during a temporary connection failure; it cannot transition runtime.

## Dashboard layout

- Runtime overview: session, status, stage, snapshot time, browser refresh,
  and an explicit status badge.
- Current operation: current task, worker, and stage.
- Worker progress: role, status, task, progress indicator, and provenance.
- Lifecycle: Development, QA, Documentation, Approval, and Release.
- Approval queue: ID, action, actor, reason, risk/permission, requested time,
  status, and next action when present.
- Timeline: the latest 20 events in authoritative snapshot order, including
  timestamp, type, actor, task, and summary when present.
- Evidence: safe type, label, session-relative identifier, timestamp, and
  availability metadata only.
- Repository: availability, branch, clean/dirty state, commit hash, summary,
  and error state.
- Connection: configured interval, last successful refresh, disconnect,
  retry, recovery, and manual read-only refresh.

The grid adapts for desktop, tablet, and narrow windows without a CSS
framework or external asset.

## API compatibility

AFDE-3.5 routes remain unchanged: `/runtime`, `/session`, `/workers`,
`/timeline`, `/approval-queue`, `/evidence`, `/repository`, and `/config`.
All return JSON. Existing fields remain available; optional metadata is
additive. Unknown routes return JSON 404 and mutation methods return JSON 405
without requesting a snapshot.

## Polling and recovery

The page obtains its interval and endpoint from `/config`, then performs one
`/runtime` GET at a time. An in-flight guard prevents overlap. The next timer
is scheduled after the current request finishes. Failure leaves the previous
DOM untouched, announces the disconnect, and schedules another attempt. A
later success replaces the view and announces recovery. Page unload clears
the timer and aborts an active request. Manual refresh uses this same guarded
GET-only path.

## Progress provenance

Explicit pipeline progress takes priority, followed by explicit session
progress. Lifecycle-derived progress is visibly labeled as an estimate.
Missing, non-numeric, boolean, non-finite, negative, and over-100 optional
values render as unavailable rather than being fabricated or crashing.

## Read-only security boundary

- The server remains restricted to `127.0.0.1` or `localhost`.
- Only GET and HEAD are accepted; there are no approve, reject, dismiss,
  execute, create, modify, delete, upload, or repository controls.
- Runtime values use `textContent` and created DOM nodes, never HTML parsing.
- CSP retains same-origin script/style/connect, denies objects, frames, base
  changes, and now explicitly denies form actions.
- Responses remain `no-store`, frame-denied, MIME-protected, and referrer-free.
- Evidence outside the runtime session directory is excluded. No arbitrary
  filesystem endpoint or evidence preview is provided.
- Approval Guardian and Controlled Execution are unchanged.

## Accessibility

The page uses a skip link, semantic headings and sections, keyboard-accessible
manual refresh, visible focus, text-bearing status badges, an ARIA live region
for refresh state, high-contrast colors, clear loading/empty/error states, and
reduced-motion behavior. Status meaning never depends on color alone.

## Launch and manual verification

~~~powershell
python -m afde.cli runtime-dashboard-web --session-id RWS-... --host 127.0.0.1 --port 8765 --poll-interval 1
~~~

Open `http://127.0.0.1:8765/`, resize across desktop/tablet/narrow widths,
tab to `Refresh now`, and verify that stopping and restarting the data source
shows disconnect then recovery while retaining the last valid view.

## Deferred capabilities

WebSocket or SSE may later publish the same DashboardAPI snapshot contract.
Authentication and RBAC belong before handler dispatch and require identity,
session, audit, and authorization design. Remote access additionally requires
TLS, trusted origins, production hosting, rate limits, and observability.
Multi-session operation requires authorized discovery, routing, aggregation,
pagination, and retention. None is implemented by AFDE-3.6.

## Verification

- AFDE-3.3 through AFDE-3.6 focused dashboard regression: `83 passed`.
- Full regression: `543 passed, 1 skipped`.
- Compileall for approval_guardian, afde, real_worker_runtime,
  sprint_auto_runner, and tests: PASS.
- `git diff --check`: PASS.
- High-confidence credential-pattern scan: PASS, zero matches.
- Python import and JavaScript syntax smokes: PASS.
- Terminal live and JSON CLI smoke coverage: PASS.
- Real localhost JSON API and browser HTML/CSS/JavaScript assets: PASS.
- Failure/retry/recovery, non-overlap, and unload cleanup coverage: PASS.
- Unknown route, path traversal, and mutation rejection: PASS.
- Persisted runtime session byte invariance after dashboard requests: PASS.

## Known limitations

- Trusted localhost only; no authentication, RBAC, TLS, or remote access.
- Fixed-interval polling; no WebSocket, SSE, backoff, or visibility cadence.
- One server and browser page display one session.
- Evidence preview is intentionally unavailable.
- Standard-library development HTTP server, not a production web service.
- No formal cross-browser or assistive-technology certification suite.
