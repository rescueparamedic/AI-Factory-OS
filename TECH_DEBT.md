# Technical Debt

## AFDE-3.7 Interactive Operations Dashboard

- Session discovery scans local session directories and projects each snapshot;
  large retention sets need authorized pagination, caching, and indexing later.
- Search/filter/sort is in-memory and single-snapshot. There is no server-side
  query language, saved view, cross-session search, export, or analytics store.
- Detail dialogs are metadata-only and have no evidence content preview,
  download, localization, or formal assistive-technology certification.
- Section navigation is sticky but does not use an observer-driven active
  section marker; richer navigation must remain dependency-free and accessible.
- WebSocket/SSE, authentication, RBAC, TLS, remote/multi-user operation,
  production hosting, and all dashboard mutations remain unimplemented.

## AFDE-3.6 Live Web Dashboard

- Browser refresh still uses fixed-interval polling. Visibility-aware cadence,
  exponential backoff, jitter, WebSocket, and SSE transports are deferred.
- Evidence is intentionally metadata-only; safe content preview would require
  an allowlisted content policy, size limits, MIME validation, and a dedicated
  containment-tested endpoint.
- The localhost server still lacks authentication, RBAC, TLS, CSRF/session
  identity, audit identities, rate limiting, and production hardening.
- The view remains single-session. Remote access and multi-session discovery,
  authorization-aware aggregation, pagination, retention, and routing are not
  implemented.
- Browser coverage validates assets, control invariants, and Node syntax but
  does not replace a future cross-browser assistive-technology certification
  suite or visual-regression service.

## AFDE-3.5 Web Dashboard Foundation

- The server is intended only for trusted localhost use and has no
  authentication, authorization, RBAC, TLS, CSRF framework, or remote-access
  hardening.
- Browser refresh uses HTTP polling; WebSocket and SSE transports, backoff,
  visibility-aware refresh, and server-pushed deltas are deferred.
- One server instance is bound to one runtime session. Session discovery,
  multi-session routing, aggregation, pagination, and retention are deferred.
- Static assets are served from the source tree without bundling,
  fingerprinting, compression, localization, or accessibility certification.
- The standard-library HTTP server has no production process manager,
  observability pipeline, rate limiting, request IDs, or graceful drain API.

## AFDE-3.4 Live Terminal Dashboard

- Polling reads local JSON files without filesystem notifications, locking,
  transactional snapshots, or cross-process consistency guarantees.
- ANSI clearing depends on TTY and terminal capability detection; unsupported
  Windows terminals and redirected output use append-only no-clear frames.
- Lifecycle-derived progress is deterministic but coarse and may move backward
  during valid QA revision loops; it is labeled rather than presented as an
  exact execution estimate.
- Live output is single-session and local. Web UI, WebSocket/SSE delivery,
  multi-session aggregation, remote evidence, identity, and RBAC are deferred.
- No-clear mode suppresses repeated timeline entries but repeats summary
  sections on each refresh for readable redirected logs.

## AFDE-3.3 Runtime Dashboard MVP

- The CLI view is an on-demand local snapshot without a web UI, WebSocket
  updates, refresh loop, authentication, or remote access.
- Evidence availability depends on local artifact paths and has no preview,
  pagination, content-type rendering, retention, or remote object storage.
- The MVP shows one persisted runtime session and one pending approval; it
  does not aggregate concurrent sessions or provide a global approval inbox.
- Repository status uses local read-only Git subprocesses and does not expose
  remote branch protection, CI, pull request, or deployment state.

## AFDE-3.2 Codex Automation Bridge

- Local exclusive claim files prevent duplicate action IDs on one filesystem,
  but do not provide a transactional multi-host queue or recovery leases.
- The JSONL evidence ledger is append-only by convention, without locking,
  rotation, signatures, or a tamper-evident hash chain.
- The existing approval-resume consumer is limited to existing-file
  replacement; new files outside the controlled sandbox can pause but are not
  yet consumable through that legacy resume path.
- GitHub PR creation, merge, deployment, release, and remote policy discovery
  remain deliberately outside the bridge.

## AFDE-3.1 Safe Auto Approval Engine

- Local atomic JSON approval evidence has no multi-process lock,
  cryptographic signature, remote identity attestation, or multi-user RBAC.
- Real AFDE runtime and Sprint Auto Runner have authoritative boundaries;
  unrelated legacy executors are not globally intercepted.
- Context fingerprints cover stable context rather than volatile Git HEAD;
  branch, cwd, repository, environment, task/session, action, target, payload,
  and pre-image remain bound.

## AFDE-3.0 Runtime Lifecycle

- Durable resume after waiting approval remains a future Sprint; Sprint 5 only
  preserves sufficient continuation and lifecycle evidence.
- Crash-safe persistence, a SQLite runtime store, process restart recovery,
  concurrent runtime locking, and distributed worker state are not included.
- Tamper-evident audit chaining, cancellation propagation, per-role timeout
  policy, and provider/role retry policy remain future work.

## AFDE-2.7 Approval Resume

- Atomic local JSON does not yet provide multi-process approval locking.
- Approval pause inside the optional QA revision sub-loop is out of scope.
- Approved writes have no automatic rollback; evidence supports manual Git
  restoration after forensic preservation.
- Remote approval UI and identity attestation remain future work.

## Approval Guardian v2

- Command classification is text-based. Shell syntax differs between Windows,
  POSIX shells, and tool-specific parsers; structured tool permissions should
  eventually replace text inference at execution boundaries.
- Legacy subprocess paths outside the real AFDE runtime and Sprint Auto Runner
  remain executor-specific; AFDE-3.1 avoids global process monkey-patching.
- Symlink and junction containment depends on host filesystem resolution and
  should receive platform-specific integration coverage.
- Protected branches currently default to `main` and `master`; repository-host
  branch protection discovery is intentionally not fetched automatically.
- Audit files are local JSON records without locking, rotation, or a tamper-
  evident append-only store.

## Sprint Auto Runner

- Central interception for every legacy executor remains future work; the new
  Runner path is mandatory-Guardian but does not replace all existing engines.
- JSON state should migrate to SQLite with transaction and schema migration
  support before concurrent production use.
- Concurrent Runner locking and duplicate-run prevention are not implemented.
- JSONL audit needs a tamper-evident hash chain, rotation, and retention policy.
- Cross-platform shell parsing needs a structured-command replacement.
- GitHub PR creation is not yet a first-class structured adapter.
- Approval UI/dashboard integration remains future work.

## Real AI Worker Runtime

- Real LLM evaluation, parallel workers, centralized interception, SQLite,
  web/WebSocket UI, locks, cost tracking, sandboxing, and multi-step revision
  remain future work.
