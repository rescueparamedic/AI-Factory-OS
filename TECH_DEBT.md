# Technical Debt

## AFDE-6.1 Production Adapter Availability Foundation

- Availability is derived only from declared `AdapterAvailability` metadata;
  it is not health, reachability, credential readiness, or operational
  Evidence.
- There is no live refresh, health check, network probe, Adapter invocation,
  credential operation, or environment-specific availability policy.
- The service is package-scoped and is not wired into Runtime startup,
  lifecycle, session, Worker, Provider, Product, CLI, or Desktop flows.
- Operational validation, production readiness, and M4 remain incomplete.

## AFDE-6.0 Production Adapter Discovery Foundation

- Discovery is an explicit one-shot metadata operation; hot reload, caching,
  change notification, filesystem scans, and namespace-package scans are not
  implemented.
- Installed entry points must expose already-constructed
  `ToolAdapterDescriptor` values. Adapter factories, binding, invocation,
  health/network probes, credentials, and Provider/Worker wiring remain
  outside the boundary.
- The static production descriptor and discovered descriptors are merged only
  through the new additive builder; existing application startup and Runtime
  lifecycle do not call discovery.
- Operational Evidence, installed third-party adapter certification,
  production readiness, and M4 validation remain incomplete.

## AFDE-5.9 Production Adapter Registration Foundation

- Only the Codex Automation Bridge has approved static production metadata;
  additional internal adapters and Providers remain unregistered.
- Registration deliberately provides no discovery, binding, instantiation,
  invocation, availability probe, credential lookup/validation/storage,
  executable downstream integration, or application-startup ownership.
- Static `available` and `compatible` classifications are governance metadata,
  not health, reachability, credential readiness, or operational Evidence.
- Operational Evidence, production-ready validation, and M4 remain incomplete.

## AFDE-5.8 Production Composition Foundation

- The production composition is intentionally non-executable; Runtime, Worker,
  Evidence, Operator, Product, CLI, Desktop, and lifecycle integration remain
  unimplemented.
- The Operational Adapter Registry has one static production registration but
  no discovery, binding, import, instantiation, invocation, availability
  validation, or credential integration.
- Knowledge Provider, Registry, and Runtime policy dependencies are still
  supplied by the caller; environment-specific application startup ownership
  remains future work.
- Registry JSON structure and references are validated, but no automated check
  compares capability field values against their Markdown registry entries.
- Operational Evidence and M4 validation remain incomplete.

## AFDE-5.7 Operational Adapter Registry Foundation

- The seven AFDE-5.x services now have explicit repeatable construction, but
  executable production composition remains unimplemented.
- Registry JSON structure and references are validated, but no automated check
  compares capability field values against their Markdown registry entries.
- Capability ID grammar is duplicated across AFDE model and validation modules
  instead of being owned by one shared definition.
- The Operational Adapter Registry foundation accepts explicit registrations,
  but additional production Adapter registrations, discovery, availability
  validation, import, instantiation, and invocation remain unimplemented.
- Worker, Evidence, and Product Assembly are not integrated with this
  non-executable composition.
- Operational Evidence and M4 validation remain incomplete.

## AFDE-3.9 Runtime History Foundation

- JSONL append is local and lightweight but has no multi-process lock,
  transaction, signature, tamper-evident chain, rotation, or retention policy.
- Legacy event IDs are deterministic read-time projections because historical
  rows predate event IDs; no migration rewrites those files.
- Canonical type/status mapping is rule-based and retains each original event
  name for audit context. A formal schema-version registry remains future work.
- History reads load one session ledger in memory. Pagination and streaming are
  deferred until retention volume justifies them.
- CLI export is stdout-only, and Dashboard history remains localhost read-only;
  server-side archives, remote history, RBAC, and multi-user access are deferred.

## AFDE-3.8 Operations Center

- Analytics is intentionally point-in-time. There is no persistent history,
  trend store, telemetry ingestion, background aggregation, or cross-host view.
- Stage inference depends on timestamps and recognizable stage signals already
  present in snapshots; missing boundaries remain unavailable.
- Bottleneck rules are deterministic heuristics, not service-level objectives
  or root-cause analysis. Threshold tuning is code/configuration work and is not
  learned from historical data.
- Only the current pending approval projection is generally available; broad
  approved/rejected timing history is not fabricated.
- JSON/CSV reports are local snapshot representations. PDF, scheduled reports,
  server-side file archives, and unrestricted downloads are deferred.
- Authentication, RBAC, TLS, remote access, production hosting, WebSocket/SSE,
  multi-user coordination, and all dashboard mutations remain deferred.

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
