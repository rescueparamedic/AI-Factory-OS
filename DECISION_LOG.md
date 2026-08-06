# Decision Log

## 2026-08-06 - AFDE-6.11 Runtime Event Stream Merge Decision

- Approved `CAP-PRODUCTIONADAPTERRUNTIMEEVENTSTREAM-0001` at M3 with
  `implementation_status: implemented` and merged PR #63 into `develop`
  at `299e3074329a61d9ef43faa77271610b3228faf8`.
- Retained the approved finite synchronous instance-local lifecycle:
  `CREATED` to `OPEN` to `CLOSED`, with lifecycle timestamps supplied explicitly
  by the caller.
- Approved sequential `append()` while `OPEN` and a frozen close snapshot that
  preserves exact Runtime Event order, object identity, count, timestamps, and
  final `CLOSED` state. Closing an empty open Stream remains valid.
- Kept Runtime Event Stream separate from the unchanged point-in-time Runtime
  Event Collection contract; the Stream neither wraps the Collection Service
  nor calls `collect()`.
- Preserved the existing `stream(request)` Request/Result public contract as an
  additive compatibility helper.
- Excluded async streams, `AsyncIterator`, subscription, publishing, brokers,
  queues, polling, background execution, persistence, history, monitoring,
  metrics, telemetry, health projection, replay, aggregation, query, and
  concurrency orchestration.
- This merge records the previously approved Architecture Decision; it does not
  change Architecture, Runtime behavior outside the Stream boundary, public
  contracts, package boundaries, or repository structure.

## 2026-08-05 - AFDE-6.10 Explicit Runtime Event Collection Boundary

- Implemented `CAP-PRODUCTIONADAPTERRUNTIMEEVENTCOLLECTION-0001` at M3 as an
  additive package-scoped public contract under the approved synchronous,
  deterministic, in-memory, and stateless boundary.
- Added immutable Runtime Event, Collection Request, and Collection Result
  models with dedicated boundary errors and one `collect()` service operation.
- Preserved caller event ordering and exact timezone-aware ISO timestamp text;
  supported payload mappings and sequences are defensively copied and deeply
  frozen without mutating caller data.
- Followed existing empty snapshot contracts: an explicit empty event tuple is
  valid and returns a zero-count result. A caller-supplied collection timestamp
  makes repeated calls with the same request deterministic.
- Kept Runtime Event Collection independent from Runtime Observation and made
  no changes to Observation, Runtime Execution, Worker Execution, Startup,
  Invocation, or Creation behavior and contracts.
- Excluded stream/subscription/publishing, history, persistence, background
  collection, polling, replay, aggregation, query, metrics, telemetry, and
  health projection.

## 2026-08-05 - AFDE-6.9 Stateless Runtime Observation Boundary

- Implemented `CAP-PRODUCTIONADAPTERRUNTIMEOBSERVATION-0001` at M3 as an
  additive package-scoped public contract.
- Chose an explicit immutable observation identity bound to the existing
  Worker, Adapter, Runtime projection, Execution Path, Capability, and Tool
  Adapter binding identity chain.
- Reused the exact completed `ProductionAdapterWorkerExecutionResult` as the
  sole observation source instead of duplicating or changing Runtime and Worker
  execution contracts.
- Kept the service synchronous and stateless: it validates and projects one
  caller-supplied result without executing, collecting, polling, or persisting.
- Denied Runtime and execution authority in every observation result and
  preserved package-scoped exports for backward compatibility.
- Excluded Runtime events/history/monitoring/health, background polling,
  persistent storage, metrics, telemetry, aggregation, lifecycle integration,
  operational wiring, M4, and production-readiness claims.

## 2026-08-02 - AFDE-6.8 Fail-closed PowerShell Merge Convergence

- Implemented `CAP-POWERSHELLMERGEAUTOMATIONSTANDARD-0001` at M3 as an
  additive repository operations standard and executable reference script.
- Preserved external merge authority: Work PASS, Chat Merge PASS, and explicit
  user approval are required caller assertions, not decisions made by the
  Capability.
- Bound every run to exact repository, PR, base/head branch, and approved full
  SHA identities before Merge Commit behavior.
- Chose property-discovery normalization for heterogeneous GitHub CheckRun and
  StatusContext JSON so StrictMode never assumes optional properties.
- Chose a process-based native command boundary that captures stdout/stderr
  separately and treats exit code, not stderr presence, as authoritative.
- Required `gh pr merge --merge`, `--ff-only` base synchronization, non-forcing
  local deletion, and current-state revalidation for partial or repeated runs.
- Kept Runtime, Application, Adapter, Worker, Provider, CI workflow, approval,
  and Release Policy ownership unchanged. No live PR is merged by validation.
- Windows PowerShell 5.1 validation is complete for this repository;
  PowerShell 7 and cross-project reusability remain explicitly unverified.

## 2026-08-02 - AFDE-6.7 Worker Facade over Runtime Execution

- Implemented `CAP-PRODUCTIONADAPTERWORKEREXECUTION-0001` at M3 as an
  additive package-scoped single-execution boundary.
- Reused the existing immutable `ExecutionInput`, `WorkerExecutionResult`,
  Runtime execution request/result, and
  `ProductionAdapterRuntimeExecutionService` contracts unchanged.
- Required explicit Worker identity and validated it locally without Worker
  Registry lookup, selection, or dispatch.
- Assembled the existing Runtime execution request from existing startup, Tool
  Adapter request/binding, authority, and invocation metadata contracts inside
  the new Service boundary.
- Chose an existing Worker result as non-lifecycle execution evidence and
  retained the exact Runtime execution result without transformation.
- Existing Runtime execution errors propagate unchanged; no parallel Worker
  error translation was added.
- Preserved Worker Manager, RealWorkerRuntime, RuntimeOrchestrator, Registry,
  ProviderBridge, Provider clients, and Worker/Runtime lifecycle ownership.
- Excluded operational wiring, sessions, scheduling, retry, cancellation,
  background execution, M4, and production-readiness claims.

## 2026-08-02 - AFDE-6.6 Explicit Runtime Execution Authority Boundary

- Implemented `CAP-PRODUCTIONADAPTERRUNTIMEEXECUTION-0001` at M3 as an
  additive package-scoped Runtime execution boundary.
- Required immutable authority bound to adapter, Runtime projection, Execution
  Path, Capability, and Tool Adapter binding identities before any behavior.
- Reused the AFDE-6.5 startup composition and existing Creation and Invocation
  services unchanged, in that order, for one synchronous operation.
- Chose a package-private lock-protected consumption ledger keyed by the unique
  authority reference after full request identity validation. Consumption occurs
  before factory behavior, so sequential
  and concurrent reuse fail closed without Runtime lifecycle mutation.
- Removed the original execution request, authority, and authority reference
  from the completed result. Only non-authoritative identity metadata and the
  existing Creation/Invocation results remain.
- Preserved Runtime lifecycle/session ownership, transitions, root exports,
  and all existing public signatures unchanged.
- Excluded authority issuance/revocation/durable cross-process storage, Worker, Provider,
  Product, CLI, Desktop, transport, retry, timeout, streaming, cancellation,
  background services, M4, and production-readiness claims.

## 2026-08-01 - AFDE-6.5 Composition-only Adapter Startup Boundary

- Implemented `CAP-PRODUCTIONADAPTERRUNTIMESTARTUPINTEGRATION-0001` at M3 as
  a package-scoped application-startup composition entry point.
- Reused `build_discovered_production_adapter_registry()`,
  `build_production_composition()`, Availability, Credential Readiness,
  Creation, and Invocation services and their immutable contracts unchanged.
- Required one exact adapter identity across the discovered Descriptor,
  factory, readiness evidence, Creation Context, and invocation target.
- Chose a frozen result that retains the Registry, shared Catalog production
  composition, prerequisite results, explicit dependencies, and denied
  authority for later caller-controlled operations.
- Startup validates declared availability and caller-supplied credential
  readiness, but deliberately does not call factory `create()` or target
  `invoke()` and does not build an invocation request.
- Preserved all existing builder signatures, Root exports, Runtime lifecycle
  state/transitions, and session ownership unchanged.
- Excluded Runtime sessions, background services, lifecycle mutation,
  Worker/Provider/Product/CLI/Desktop wiring, Provider SDK/network, credential
  secrets, retry, timeout, streaming, external DI/plugin frameworks, M4, and
  production-readiness claims.

## 2026-07-28 - AFDE-6.4 Explicit Caller-supplied Invocation Target

- Implemented `CAP-PRODUCTIONADAPTERINVOCATION-0001` at M3 as a
  package-scoped metadata-only invocation contract.
- Kept `ProductionAdapterInstance` inert and unchanged; invocation behavior is
  owned only by an explicit caller-supplied `InvocationTarget`.
- Required exact object and adapter identity continuity across Creation Result,
  Instance, Descriptor, Availability, Credential Readiness, Tool Adapter
  request, Binding, Target, and target return.
- Separated `InvocationTargetResult` from `InvocationResult` so return type,
  identity, safe opaque metadata, and denied authority are independently
  validated.
- Fail closed before the target call for invalid preconditions and wrap target
  exceptions in a typed error without copying internal exception text.
- Preserved Registry, Catalog, Discovery, Creation, Tool Adapter Contract,
  Execution Path, Runtime Integration, builders, Root exports, startup,
  lifecycle, and session unchanged.
- Excluded target discovery/registry, Provider SDK, HTTP/network, secrets,
  health probes, retry, timeout, streaming, Worker dispatch, Runtime
  integration, DI, and plugin frameworks.

## 2026-07-28 - AFDE-6.3 Explicit Inert Adapter Creation

- Implemented `CAP-PRODUCTIONADAPTERCREATION-0001` at M3 without invocation,
  execution, Runtime binding, operational-health, or production-ready claims.
- Kept `ToolAdapterDescriptor`, `OperationalAdapterRegistry`, and
  `ToolAdapterCatalog` as unchanged metadata authorities and separated them
  from caller-supplied factories and inert instances.
- Added an explicit immutable factory identity snapshot inside the creation
  service; duplicate identities and missing exact factories fail closed.
- Required descriptor, context, Availability, Credential Readiness, optional
  existing `ToolAdapterBinding`, factory, and returned instance identities to
  agree before returning a result.
- Limited configuration and creation metadata to allowlisted safe opaque
  references with no credential or secret-value field.
- Preserved Discovery entry-point returns, all existing builders, Tool Adapter
  Contract, Execution Path, Runtime Integration, Root exports, and Runtime
  lifecycle unchanged.
- Excluded invocation/execution, factory auto-discovery, global instance
  registries, service locators, DI/plugin frameworks, credentials, Provider
  clients, probes, retry/timeout/circuit breaker, Worker, Product, CLI, and
  Desktop.

## 2026-07-28 - AFDE-6.2 Caller-supplied Credential Readiness

- Implemented `CAP-PRODUCTIONADAPTERCREDENTIALREADINESS-0001` at M3 without
  credential validity, authorization, expiry, access, health, M4, or
  production-readiness claims.
- Reused the existing `ToolAdapterDescriptor.credentials_required` metadata as
  the sole requirement declaration.
- Accepted only explicit caller readiness evidence containing adapter
  identity, a boolean, a safe opaque reference, and allowlisted source
  metadata; added no credential or secret-value field.
- Adopted `NOT_REQUIRED`, `READY`, and `NOT_READY`; required credentials
  without explicit ready evidence fail closed as the normal `NOT_READY`
  outcome.
- Preserved Registry, Catalog, Discovery, Availability, Registration,
  Execution Path, Runtime Handoff/Projection, Runtime policy, builder
  signatures, Root public contract, and Runtime lifecycle unchanged.
- Excluded lookup, validation, authorization, storage, encryption, secret
  stores, OAuth, refresh, Adapter creation/binding/invocation/execution,
  probes, Runtime startup/lifecycle/session, Worker, Provider, Product, CLI,
  and Desktop.

## 2026-07-28 - AFDE-6.1 Descriptor-declared Adapter Availability

- Implemented `CAP-PRODUCTIONADAPTERAVAILABILITY-0001` at M3 without claiming
  operational health, reachability, credential readiness, M4, or production
  readiness.
- Reused the existing `ToolAdapterDescriptor.availability` and
  `AdapterAvailability` as the only assessment input and policy.
- Returned one frozen deterministic metadata result that preserves the exact
  descriptor and denies Runtime and execution authority.
- Reused Discovery, static Registration, Registry, and Catalog unchanged as
  the source path for registered descriptors.
- Confirmed compatibility with the existing `ExecutionPathService`,
  `RuntimeProjection`, and `RuntimeIntegrationPolicy` without integrating or
  invoking Runtime behavior.
- Excluded credentials, Adapter construction/factories/binding/invocation,
  health checks, network probes, execution, Runtime startup/lifecycle/session,
  Worker, Provider, Product, CLI, and Desktop.

## 2026-07-28 - AFDE-6.0 Production Adapter Metadata Discovery

- Implemented `CAP-PRODUCTIONADAPTERDISCOVERY-0001` at M3 without claiming
  M4, operational health, production readiness, or execution authority.
- Selected only Python standard-library `importlib.metadata` and the exact
  `ai_factory_os.tool_adapters` entry-point group.
- Added an injectable structural discovery-source boundary so focused tests
  require no installed adapter distribution.
- Required every entry point to load exactly one existing
  `ToolAdapterDescriptor`; source, load, and type failures fail closed with
  typed discovery errors.
- Merged discovered metadata with unchanged static registrations through the
  existing `OperationalAdapterRegistry` and reused the existing Catalog's
  duplicate identity, Capability mapping, and ambiguity validation.
- Preserved both existing builder signatures, production composition, Runtime
  startup/lifecycle, and false Runtime/execution authority.
- Excluded Adapter factories, binding, invocation, credentials, probes, hot
  reload, filesystem/namespace scans, Providers, Workers, CLI, Desktop,
  Pluggy, Stevedore, and DI containers.

## 2026-07-27 - Chat–Work–Codex Sprint Classification

- Required Chat to classify every Sprint before implementation.
- Adopted `Chat → Codex → Chat → PowerShell` for General Sprints and prohibited
  Work in that flow.
- Adopted `Chat → Work → Codex → Chat → PowerShell` for Architecture Sprints.
- Limited Work to Repository Audit, Existing Capability Audit, Open Source
  Audit, Architecture Audit, and Architecture Review.
- Assigned implementation, tests, builds, and final reporting to Codex.
- Retained explicit merge approval and assigned merge, `develop`
  synchronization, and authorized branch cleanup to PowerShell.
- Retired the previous default workflow and its post-Codex Work stage.
- Changed development operations only; Architecture, Runtime, public
  contracts, Capabilities, source code, and tests remain unchanged.

## 2026-07-27 - AFDE-5.9 Static Production Adapter Registration

- Implemented `CAP-PRODUCTIONADAPTERREGISTRATION-0001` at M3 without claiming
  M4, production readiness, execution authority, or operational health.
- Registered exactly one frozen `adapter.codex_automation_bridge` descriptor
  through a package-scoped factory.
- Reused the existing `ToolAdapterDescriptor`,
  `OperationalAdapterRegistry`, and `ToolAdapterCatalog`; each call produces
  an independent Registry and Catalog with a deterministically equal snapshot.
- Kept bridge implementation paths as metadata strings and rejected discovery,
  entry points, dynamic imports, bridge construction, binding, invocation,
  availability probes, and credential operations.
- Confirmed direct injection into the existing production composition while
  retaining the exact Catalog identity and false Runtime/execution authority.
- Added no dependency and changed no existing builder or root package export.

## 2026-07-26 - AFDE-5.8 Explicit Production Dependency Composition

- Implemented `CAP-PRODUCTIONCOMPOSITION-0001` at M3 without claiming M4,
  production readiness, executability, or operational availability.
- Reused the existing frozen `NonExecutableComposition` and all seven existing
  AFDE-5.x service types.
- Made the caller-injected `OperationalAdapterRegistry` the authoritative
  Catalog supplier and shared that same existing Catalog instance across Tool
  Selection, Execution Path, and Tool Adapter Contract.
- Preserved the AFDE-5.6 builder and all upstream public contracts unchanged.
- Rejected `dependency-injector`, `punq`, and `injector`; their container,
  resolution, wiring, scope, configuration, and resource features exceed this
  bounded explicit composition.
- Kept Adapter binding/execution, discovery, Runtime, Worker, Evidence,
  Operator, Product, CLI, Desktop, credentials, external I/O, and lifecycle
  behavior outside this boundary.
- Deferred additional production registrations, executable downstream
  integration, operational Evidence, and M4 validation.

## 2026-07-26 - AFDE-5.7 Explicit Operational Adapter Registrations

- Implemented `CAP-ADAPTERREGISTRY-0001` at M3 without claiming M4 or
  operational availability.
- Accepted only caller-injected existing `ToolAdapterDescriptor` registrations;
  rejected discovery, files, entry points, dynamic imports, and plugins.
- Reused `ToolAdapterCatalog` as the validation, immutable snapshot, lookup,
  and candidate-projection owner rather than creating another Catalog.
- Returned one Catalog instance so Selection, Execution Path, and Tool Adapter
  Contract retain their existing public contracts and shared metadata source.
- Kept Adapter construction/invocation, availability probes, credentials,
  Provider, Runtime, Worker, Evidence, Operator, Product, and lifecycle outside
  the registration boundary.
- Added no third-party dependency and preserved the AFDE-5.6 non-executable
  boundary.
- Deferred additional production registrations, discovery, executable
  composition, downstream integration, and operational M4 evidence.

## 2026-07-26 - AFDE-5.6 Explicit Non-executable Composition

- Implemented `CAP-COMPOSITION-0001` at M3 without claiming M4.
- Composed the seven existing AFDE-5.0 through AFDE-5.5 service objects by
  explicit constructors without adding an execution or orchestration facade.
- Required caller-injected Knowledge Provider, Tool Adapter descriptors, and
  Runtime policy; no hidden Provider, Registry, filesystem, environment, or
  configuration loading was added.
- Required Tool Selection, Execution Path, and Tool Adapter Contract to share
  one constructed Catalog.
- Used one frozen container that rejects Runtime or execution authority and
  exposes no run, execute, invoke, dispatch, lifecycle, or recovery behavior.
- Rejected an external DI framework because declarative providers,
  configuration, and wiring exceed the bounded constructor-only requirement.
- Deferred executable production composition, Operational Adapter Registry,
  Worker/Evidence/Product integration, and operational M4 validation.

## 2026-07-26 - AFDE-5.5 Non-executable Tool Adapter Contract

- Implemented `CAP-TOOLADAPTER-CONTRACT-0001` at M3 without claiming M4.
- Added a dedicated boundary after Runtime Projection and before any future
  adapter invocation; Worker integration remains excluded.
- Reused immutable `RuntimeProjection` and `ToolAdapterDescriptor` contracts.
- Added an additive Catalog descriptor-list method satisfying a narrow,
  constructor-injected, read-only structural protocol.
- Required exact projection, path, Capability, adapter, version, and governed
  descriptor metadata agreement.
- Made malformed snapshots, duplicate identities, mismatches, and unregistered
  adapters deterministic structured failures.
- Preserved all four required identities in request, result, binding, and error
  models while keeping Runtime and execution authority false.
- Adopted Python frozen dataclasses and `typing.Protocol`; no third-party
  dependency was added.
- Deferred adapter/Worker execution, Runtime session behavior, Provider,
  approval, credential, Evidence, lifecycle, Product, Desktop, Operator, Beta
  Execute, and operational M4 validation.

## 2026-07-24 - AFDE-5.4 Read-only Runtime Integration

- Implemented `CAP-RUNTIME-0001` at M3 without claiming M4.
- Kept executable Beta and real-worker Runtime, Worker, Provider, orchestration,
  lifecycle, persistence, and Evidence contracts unchanged and isolated.
- Added dedicated `afde.runtime_integration` ownership after Execution Path.
- Required constructor-injected immutable policy and exact immutable
  `ExecutionPathResult` input.
- Distinguished structural `runtime_ready` from authority;
  `runtime_allowed` and `execution_allowed` remain false.
- Derived stable projection IDs without time, randomness, filesystem, network,
  live process state, or discovery.
- Evaluated Prefect, Dagster, Temporal, Dramatiq, Celery, pluggy, stevedore,
  transitions, graphlib, NetworkX, Pydantic, attrs, psutil, structlog, and Rich.
  No dependency was adopted because none reduces this bounded projection
  without adding excluded execution or unnecessary infrastructure.
- Deferred session creation, Runtime execution, lifecycle mutation, Worker or
  adapter invocation, Provider, Evidence, Product Assembly, orchestration,
  retry, recovery, resume, and operational M4 validation.

## 2026-07-24 - AFDE-5.3 Non-executable Execution Path

- Implemented `CAP-EXECPATH-0001` at M3 without claiming M4.
- Kept Planner `ExecutionPlan` goal/task planning and executable Runtime models
  outside the new structural handoff boundary.
- Added dedicated `afde.execution_path` ownership after Tool Selection and
  before a future Runtime Integration capability.
- Reused immutable `ToolAdapterSelectionResult` and exact
  `ToolAdapterDescriptor` metadata through a constructor-injected Catalog
  lookup without constructing or mutating a Catalog.
- Required identity/Capability agreement, resolved eligible state,
  availability, Runtime compatibility, and controlled execution contract.
- Derived stable path IDs from structured metadata without time, randomness,
  filesystem, network, or environment input.
- Distinguished path construction and structural handoff readiness from
  authority; Runtime and execution remain prohibited.
- Represented credentials only as an explicit prerequisite.
- Preserved Planner, Planner Resolution, Resolver, Selection, Catalog,
  Execution Planner, Runtime, Worker, Product, Provider, Evidence, CLI,
  Desktop, and lifecycle contracts.
- Deferred Runtime authorization/invocation, Worker handoff, adapter execution,
  credentials, Evidence, Product Assembly, operations, and M4 validation.

## 2026-07-24 - AFDE-5.2 Immutable Tool Adapter Catalog

- Implemented `CAP-TOOLCATALOG-0001` at M3 without claiming M4.
- The existing capability audit found no governed Catalog or complete adapter
  descriptor. Reused AFDE-5.1 `ToolAdapterCandidate` directly and preserved
  `AdapterCandidateSource` as the Tool Selection protocol boundary.
- Chose a dedicated `afde.tool_catalog` boundary. Constructor-supplied
  descriptors are defensively snapshotted, validated, deterministically
  ordered, and exposed only through immutable projections and exact lookups.
- Made the constructed Catalog the Single Source of Truth for adapter
  discovery metadata in its scope. The Knowledge Registry governs the Catalog
  capability and standard but does not duplicate adapter rows.
- Required explicit availability, Runtime compatibility, execution contract,
  privacy, cost, credential flag, version, description, and exact Capability
  mappings. Duplicate identity or multiple selectable ownership fails closed.
- Projected only available, Runtime-compatible, controlled-contract
  descriptors into the existing Tool Selection candidate boundary.
- Existing `real_worker_runtime` adapters lack complete governed discovery
  metadata and were not registered or modified.
- Preserved Planner, Planner Resolution, Resolver, Tool Selection, Runtime,
  Worker, Product Layer, Provider, Evidence, CLI, Desktop, and lifecycle
  contracts. Deferred execution, external discovery, ranking, fallback,
  operational population, secrets, and M4 validation.

## 2026-07-24 - AFDE-5.1 Deterministic Tool Adapter Selection

- Implemented `CAP-TOOLSELECT-0001` at M3 without claiming M4.
- The existing capability audit found no Tool Adapter selection service,
  governed descriptor, or reusable adapter Registry. Existing concrete
  `real_worker_runtime` adapters execute work and were not reused across the
  read-only application boundary.
- Reused immutable `CapabilityResolutionResult` and
  `PlannerCapabilityResolutionResult` directly instead of changing Planner,
  Planner Resolution, or Resolver contracts.
- Chose a dedicated `afde.tool_selection` application service with a
  constructor-injected `AdapterCandidateSource`; it performs no hidden Registry
  loading, filesystem or network I/O, Provider call, or Runtime invocation.
- Required an eligible resolved outcome and one exact Capability ID match.
  Zero matches return no-selection; multiple authoritative matches block in
  stable adapter-ID order. No fuzzy matching, scoring, ranking, or fallback was
  added.
- Preserved Resolver status, gaps, rejection reasons, source documents,
  reference priority, and ordered trace in an immutable result that always
  denies Runtime and execution.
- Deferred adapter execution, operational adapter catalog integration,
  Runtime, Worker, Product Layer, Provider, Evidence, orchestration, and M4.

## 2026-07-24 - AFDE-5.0 Planner-Resolver Integration

- Implemented `CAP-PLANRES-0001` at M3 without claiming M4.
- Chose a separate `afde.planner_resolution` application service so existing
  Planner and Resolver public contracts remain unchanged.
- Required immutable structured Planner context and either an explicit
  `CapabilityRequirement` or explicit exact-ID requirement fields.
- Injected the Resolver through a minimal protocol; the service creates no
  Provider or Resolver and performs no Registry, Markdown, file, or network I/O.
- Preserved resolved, unresolved, blocked, and decision-required status,
  Resolver gaps, source references, and ordered trace while always denying
  Runtime execution.
- Deferred natural-language extraction, candidate discovery/ranking, Tool
  Adapter selection, Runtime, Evidence, Product Assembly, and M4 validation.

## 2026-07-23 - AFDE-4.9 Capability Resolver Foundation

- Implemented `CAP-RESOLVER-0001` as an internal deterministic Resolver and
  advanced it from unregistered M0 to M3 Implemented without claiming M4.
- Required structured `CapabilityRequirement` input; natural-language,
  fuzzy, semantic, and multiple-candidate discovery remain outside the MVP.
- Reused the injected Knowledge Provider for all capability, Knowledge,
  document, gap, and reference-priority access.
- Distinguished invalid requirements and invalid Provider state from normal
  unresolved, blocked, and decision-required outcomes.
- Evaluated lifecycle status, implementation status, maturity, scope, required
  Knowledge, direct Capability dependencies, gaps, and constraints in a stable
  order with an ordered rationale.
- Kept the result immutable and read-only, with no Registry JSON parsing,
  Markdown search, file access, network access, implementation-path selection,
  Tool Adapter selection, Runtime call, Worker execution, or Product Assembly.
- Preserved Planner, Runtime, Product Layer, Tool Adapter, CLI, Desktop,
  Evidence, and every existing public contract.

## 2026-07-23 - AFDE-4.8 Read-only Knowledge Foundation Provider

- Implemented `CAP-KNOW-0001` as an internal read-only Provider and advanced it
  from M2 Designed to M3 Implemented without claiming M4 validation.
- Adopted one governed JSON snapshot containing separate Document, Knowledge,
  and Capability collections plus authority and reference-priority metadata.
- Kept official Markdown documents as Source of Record; the JSON Registry is an
  index and neither copies full source content nor stores execution settings.
- Added immutable typed models, a repository-contained UTF-8 JSON loader,
  cross-registry fail-closed validation, deterministic queries,
  Resolver-ready `CapabilityContext`, and structured gaps.
- Distinguished an invalid Registry, which raises a validation error, from a
  valid unmet Capability requirement, which returns an explicit Gap.
- Omitted self-referential source Commit metadata from the MVP snapshot; Git
  history remains the authoritative revision audit.
- Added no Resolver selection, Runtime call, Worker execution, Planner or
  Product Layer change, Tool Adapter behavior, file mutation, network call,
  Markdown search, RAG, vector database, embedding, or multimodal behavior.
- Preserved every existing public contract and Runtime lifecycle.
- Capability Resolver, Tool Adapter implementation, operational integration,
  and M4 validation remain separately approved future work.

## 2026-07-23 - AFDE-4.7 Knowledge Foundation Architecture

- Added Knowledge Foundation between Capability and Capability Resolver as a
  governed architecture boundary for official document discovery, knowledge
  validity, capability metadata, reference authority, and gap reporting.
- Established Document, Knowledge, and Capability Registry standards as
  repository indexes that never replace Source of Record documents,
  implementation, Runtime state, or Evidence.
- Registered `CAP-KNOW-0001` as `architecture_approved`, maturity `M2`, and
  `not_implemented`; capability status, maturity, and implementation truth
  remain independent.
- Required Active Knowledge and Registry entries to bind official Active source
  documents and required document and registry changes to be reviewed as one
  governance unit.
- Established AI reference eligibility, priority, scope, status, conflict,
  missing-knowledge, external-source, and traceability rules.
- Preserved Runtime, Product Layer, Planner, Capability Resolver, Tool Adapter,
  Evidence, Beta Execute, Desktop, and all public contracts unchanged.
- Deferred machine-readable registries, validation services, query APIs,
  Resolver and Adapter implementation, RAG, vector databases, embeddings, and
  multimodal execution to separately approved Sprints.
- Retained `develop` as Source of Truth, feature-branch workflow, Merge Commit
  only policy, and explicit user approval before merge.

## 2026-07-18 - AFDE-3.9 Reuse the Existing Event Ledger

- Keep session `events.jsonl` as the single append-only event ledger instead of
  adding a database, parallel history file, event bus, or analytics store.
- Extend RuntimeEvent additively and preserve `event`, `detail`, `task_id`,
  `state`, and `payload` for Runtime and Dashboard compatibility.
- Route EventStream writes through RuntimeHistoryStore so all existing Session,
  Worker, Approval, QA, failure, and completion emissions gain the new model
  without changing RuntimePipeline transitions or approval execution behavior.
- Normalize legacy records only when read. Deterministic `EVT-LEGACY-*` IDs and
  canonical types are projections and never rewrite historical bytes.
- Keep history CLI exports on stdout and Dashboard access read-only; history
  does not become authority for current runtime state.

## 2026-07-17 - AFDE-3.8 Pure Snapshot Operations Analytics

- Adopted `OperationsAnalytics` as a deterministic transport-neutral projection
  over copied Dashboard Snapshots; it has no RuntimePipeline dependency, cache,
  database, ingestion path, background job, or persistence.
- Limited comparison to 2 through 5 unique IDs from validated session discovery;
  malformed discovered sessions remain visible as Unavailable.
- Required honest duration provenance (`measured`, `inferred`, `unavailable`),
  explicit KPI denominators, centralized thresholds, and explainable advisory
  findings rather than opaque scores or AI-generated root-cause claims.
- Kept comparison selection in URL presentation state and coupled consolidated
  analytics refresh to the existing runtime poll cycle with overlap and stale
  response guards.
- Kept reports read-only and data-equivalent to Operations APIs; Blob downloads
  are browser-local and the HTTP server writes no export file.

## 2026-07-16 - AFDE-3.7 Validated Session Discovery and Presentation Tools

- Discover sessions directly from existing runtime-session directories and
  derive summaries through `RuntimeDashboard.snapshot`; do not add a registry.
- Validate selected IDs syntactically and against discovery results before
  asking the snapshot provider for data. Never accept or return filesystem paths.
- Keep search, filters, sorting, selected-session URL state, dialog state, and
  statistics in the browser presentation layer only; never persist them as
  runtime or analytics state.
- Preserve one guarded runtime poll. Permit a lower-frequency `/sessions` read
  with its own overlap guard because it does not poll or duplicate runtime state.
- Keep evidence detail metadata-only and use text-created DOM plus focus-return
  dialog behavior for safe accessible inspection.

## 2026-07-16 - AFDE-3.6 Live Presentation State

- Preserve Dashboard Snapshot as the only browser data projection and continue
  one complete `/runtime` GET per refresh; individual cards do not poll.
- Treat the last successful snapshot as presentation continuity only. A failed
  request changes connection messaging but never replaces the visible runtime
  data or becomes authoritative state.
- Prevent overlapping requests with one in-flight guard, reschedule only after
  completion, abort on unload, and allow manual refresh through the identical
  read-only request path.
- Keep evidence metadata-only. Only available artifacts resolved inside the
  runtime session directory are projected, and no preview/file-serving route
  is introduced.
- Use semantic sections, text-bearing status badges, visible keyboard focus,
  an ARIA live region, responsive breakpoints, and reduced-motion handling as
  the accessibility baseline.

## 2026-07-16 - AFDE-3.5 Snapshot-Backed Web Boundary

- `DashboardAPI` is the only web-facing data adapter and consumes
  `RuntimeDashboard.snapshot`; HTTP handlers never access RuntimePipeline.
- `/runtime` returns one complete snapshot so browser refresh does not
  duplicate polling across cards. Component endpoints are additive views over
  the same snapshot interface.
- The embedded HTTP transport binds only to localhost and permits GET/HEAD;
  mutation methods fail with JSON 405 responses.
- Static HTML/CSS/JS remains dependency-free and treats API values as text,
  with a same-origin Content Security Policy and no action controls.
- The API remains transport-neutral so later WebSocket, SSE, authentication,
  RBAC, remote, and multi-session adapters can wrap it without parsing HTML.

## 2026-07-16 - AFDE-3.4 Live Dashboard Separation

- RuntimeDashboard remains the reusable read-only snapshot provider over
  RuntimePipeline; polling and terminal presentation cannot mutate runtime.
- LiveDashboardController owns interval validation, bounds, sleeping,
  interruption, and last-valid-snapshot recovery without owning state.
- TerminalLiveDashboardRenderer consumes structured snapshots and is not an
  execution or persistence layer.
- Progress prefers an explicit RuntimePipeline value, then existing explicit
  RuntimeSession progress, then a documented deterministic lifecycle mapping;
  absent state is reported as unavailable.
- The standard library is sufficient. A browser/WebSocket dashboard,
  authentication, and remote aggregation are deferred.

## 2026-07-16 - AFDE-3.3 Read-Only Runtime Dashboard

- RuntimePipeline remains the authoritative delivery-stage state; dashboard
  worker status is a projection and cannot transition the pipeline.
- Existing session approval, event-stream, and artifact references are reused
  for queue, timeline, and evidence views.
- The MVP uses an on-demand CLI snapshot in text or JSON and invokes only
  read-only Git commands for repository status.
- Approval and Release are display stages only; no new runtime worker,
  approval policy, or release execution authority is introduced.

## 2026-07-15 - AFDE-3.2 Structured Automation Boundary

- `ToolAction` is the canonical worker-to-runtime automation contract; raw
  text is never interpreted as executable authority.
- Approval Guardian and ControlledExecutor remain the sole protected
  side-effect policies and boundary.
- Structured actions bind exact repository, cwd, branch, task, session, stage,
  revision, worker, target, and payload evidence before execution.
- Existing proposal fields remain compatible only when `actions` is absent.
- Merge, deployment, release, destructive Git, protected push, and secret input
  are excluded rather than modeled as approvable bridge actions.

## 2026-07-15 — AFDE-3.1 Central Runtime Approval Enforcement

- `ApprovalDecision` and `ApprovalGuardian` remain canonical; no second
  approval classifier is introduced.
- `ControlledExecutor` is the final permission check for real runtime file and
  command side effects.
- AUTO_APPROVE requires durable evidence and agreement between Guardian and
  Controlled Execution; either DENY wins.
- Human approval is bound to deterministic action and context fingerprints
  and revalidated immediately before execution.
- Sprint Auto Runner retains its existing boundary to prevent double execution.

## 2026-07-14 — AFDE-3.0 Runtime Lifecycle Finalization

- AFDE-3.0 Multi-Agent Runtime adopts deterministic lifecycle finalization,
  structured role failure propagation, and append-only runtime transition
  history.
- `RuntimeTask` remains the sole lifecycle owner; `WorkerContext` remains the
  serialized continuation carrier and `RuntimeOrchestrator` remains the role,
  handoff, and bounded-revision coordinator.
- Existing WorkerState and RuntimePipeline transitions remain authoritative for
  their established contracts. The lifecycle status is an additive run-level
  projection with fail-closed transition validation.
- Final summaries are derived from persisted task evidence and never infer
  success from provider claims.

## 2026-07-12 — AFDE-2.7 Human Approval Resume

- Reused atomic Runtime JSON for approval and continuation records.
- Bound approval to session, execution request, normalized payload, target,
  pre-image hash, and a canonical single-use fingerprint.
- Kept existing-file replacement as `ASK_USER`; `AGV2-S004` is unchanged.
- Required runtime-owned edits/evidence and fail-closed pre-image mismatch.

## 2026-07-11 — Approval Guardian v2

- Adopted three decisions: `AUTO_APPROVE`, `ASK_USER`, and `DENY`.
- Adopted fail-closed classification with deny-overrides precedence.
- Allowed verified low-risk actions only within feature-branch workflows.
- Kept the existing release `ApprovalGate` unchanged and added Guardian as a
  command-policy layer.
- Reused the existing JSON audit directory with command redaction and
  fingerprinting.
- Kept Safe Approval Policy v1 compatibility behind `ExecPolicyAdapter`; the
  v1 policy itself is not duplicated because it is not yet on `develop`.

## 2026-07-11 — Sprint Auto Runner

- Adopted a persisted Sprint state machine with mandatory Guardian evaluation
  before every process execution.
- Limited automatic progress to AUTO_APPROVE decisions in verified feature
  workflows; ASK_USER persists and stops, while DENY permanently blocks.
- Explicitly denied direct push to `main`, `master`, and `develop` in the Runner.
- Kept merge as a user-approved operation and excluded automatic merge.
- Chose additive integration instead of replacing all legacy executors.

## 2026-07-11 — Real AI Worker Runtime MVP

- Prioritized an executable deterministic mock Demo.
- Reused Runner/Guardian and prohibited silent real-provider fallback.
