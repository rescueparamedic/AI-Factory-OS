# AFDE-3.5 Web Dashboard Foundation Report

## Baseline and objective

AFDE-3.5 starts from `origin/develop` commit `733d3e9`, the merge commit
for AFDE-3.4 PR #18. It adds a localhost browser presentation layer over the
existing Dashboard Snapshot without creating runtime state or execution
authority.

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
        Browser card renderer
~~~

`RuntimePipeline` remains the Single Source of Truth.
`DashboardAPI` depends only on the AFDE-3.4 `SnapshotProvider` interface
and never imports or accesses RuntimePipeline. Each API request obtains one
safely copied snapshot. The browser polls the complete `/runtime` view once
per configured interval and updates every card, preventing per-card duplicate
polling.

The API is independent of HTTP and HTML so future WebSocket or SSE transports
can publish the same structured views. One API instance is currently bound to
one session; future multi-session routing can compose multiple instances.

## Read-only JSON API

- `GET /runtime`: complete Dashboard Snapshot.
- `GET /session`: session, status, stage, task, worker, progress source, and
  refresh timestamp.
- `GET /workers`: worker status and progress.
- `GET /timeline`: chronological execution events.
- `GET /approval-queue`: pending approval display data.
- `GET /evidence`: currently available evidence artifacts.
- `GET /repository`: branch, working tree, and latest commit.
- `GET /config`: session, polling interval, transport, endpoint, and
  read-only declaration.

Unknown routes return JSON 404. POST, PUT, PATCH, and DELETE return JSON 405
without loading a snapshot. HEAD is supported without a response body.

## Local HTTP server

`RuntimeDashboardWebServer` uses Python `ThreadingHTTPServer`, binds only
to `127.0.0.1` or `localhost`, and accepts no remote binding. It has no
database, external service, cloud deployment, authentication, or new
dependency. Responses include no-store caching, content-type protection,
frame denial, referrer restriction, and a same-origin Content Security Policy.

## Browser dashboard

The dependency-free HTML/CSS/JavaScript view contains responsive Runtime,
Workers, Timeline, Approval Queue, Evidence, and Repository cards. API values
are inserted with DOM `textContent`, not HTML injection. The page contains
no form or action control and sends GET requests only. Recursive timeout
polling avoids overlapping refresh calls.

## CLI

~~~powershell
python -m afde.cli runtime-dashboard-web --session-id RWS-...
python -m afde.cli runtime-dashboard-web --session-id RWS-... --host 127.0.0.1 --port 8765 --poll-interval 1
~~~

The existing terminal live, non-live text, and JSON commands remain unchanged.

## Security and policy confirmation

- Dashboard refresh is read-only and does not persist state.
- Approval requests cannot be approved, rejected, consumed, or dismissed.
- Evidence cannot be created, modified, executed, or deleted.
- Approval Guardian and Controlled Execution are unchanged.
- Codex Automation Bridge and runtime executors are not invoked.
- No duplicate runtime engine, pipeline, polling authority, or state store was
  introduced.
- No secret, credential, paid service, external API, or package was added.

## Tests and verification

- Focused web/live/dashboard tests: `69 passed`.
- Full regression suite: `529 passed, 1 skipped`.
- Compileall: PASS for approval_guardian, afde, real_worker_runtime,
  sprint_auto_runner, and tests.
- `git diff --check`: PASS.
- Exact changed-scope common credential scan: PASS.
- Real localhost API JSON smoke: PASS.
- HTML dashboard and CSS/JavaScript asset smoke: PASS.
- Browser rendering marker smoke: PASS.
- Mutation rejection and persisted-session byte comparison: PASS.

## Future plan

- WebSocket and SSE adapters may publish the existing DashboardAPI views.
- Authentication and RBAC may be inserted at the transport boundary before
  handler dispatch.
- Remote Dashboard requires TLS, trusted origins, identity, authorization,
  rate limiting, observability, and production hosting.
- Multi-session Dashboard requires session discovery, authorization-aware
  routing, aggregation, pagination, and retention.

None of these features is implemented in AFDE-3.5.

## Known limitations

- Trusted localhost only; no authentication, authorization, TLS, or RBAC.
- HTTP polling rather than WebSocket or SSE.
- One server instance displays one runtime session.
- Standard-library development server without production process management,
  rate limiting, request tracing, graceful drain, or compression.
- Static assets are source files without bundling, fingerprinting,
  localization, or formal accessibility certification.

## Rollback

Revert the AFDE-3.5 feature commit. Runtime state requires no migration because
the API, server, and assets are additive consumers of existing snapshots.
