# AI Development Engine Product Layer

## 1. Decision summary

AFDE-4.5 established a product-facing composition layer, not another execution
engine. The implementation is now present on `develop` under `afde/product/`;
the design language retained below records the approved implementation plan.

The repository already contains the complete execution capabilities needed for
an end-to-end development run:

- planning and typed role handoffs;
- the multi-role Runtime and registered workers;
- structured `ToolAction` validation and adaptation;
- bounded `ControlledExecutor` policy;
- Approval Guardian and exact approval resume;
- QA, execution-truth reconciliation, artifacts, history, and Evidence.

The missing capability is a product-level coordinator and projection that make
those components feel like one development operation.

The recommended product execution path is:

```text
Product execute operation
  -> existing Operator preflight
  -> existing OperatorService
  -> existing RealWorkerRuntime(enable_controlled_execution=True)
  -> existing PM / Planner / Developer / QA / Documentation roles
  -> existing ToolAction / CodexAutomationBridge
  -> existing ControlledExecutor / Approval Guardian
  -> existing Runtime session, history, artifacts, and Evidence
  -> product-facing projection
```

`Product execute operation` in this document is an internal Product Layer
operation. It is not a replacement for, or a behavioral expansion of, the
public `python -m afde.cli execute` command.

This distinction is required to preserve the AFDE-4.0 Beta Execute Contract and
the Desktop Contract. The literal public `execute` path only supports terminal
`completed` and `failed` results, while controlled development may enter
`waiting_approval` and later resume. Routing public `execute` directly into the
stateful Runtime would therefore be a contract change even if its command-line
syntax stayed the same.

AFDE-4.7 extends the future capability boundary with a Knowledge Foundation.
It is an architecture/document extension only and does not change Product
Layer code or public behavior.

AFDE-4.9 implements an isolated exact-ID Capability Resolver foundation over
the read-only Knowledge Provider. It does not change Product Layer code or
behavior and does not implement the future adapter/provider selection described
below.

AFDE-5.0 composes structured Planner context with that Resolver through an
isolated injected application service. It preserves the Resolver result and
keeps Runtime disallowed; Product Layer code and behavior remain unchanged.

## 2. Scope and invariants

### In scope

- compare the current `execute`, Operator, and `factory-demo` paths;
- identify the existing canonical owner of each development capability;
- define one Product Layer architecture over those owners;
- identify the minimum future integration seams;
- define contract, security, Evidence, and migration gates.

### Out of scope

- implementation;
- a new Runtime, worker, planner, provider, approval system, or Evidence schema;
- Runtime lifecycle or Runtime state changes;
- changes to the Beta Execute Contract;
- changes to the Desktop execution contract;
- replacing Operator commands;
- automatic approval, merge, deployment, or live-provider calls.

### Non-negotiable invariants

1. `RealWorkerRuntime` remains the only stateful development Runtime.
2. Runtime lifecycle states and transitions remain unchanged.
3. `ToolAction`, `ControlledExecutor`, Approval Guardian, and approval resume
   remain the only mutation boundary.
4. Runtime session and Evidence files remain owned by existing Runtime stores.
5. Public `execute` JSON fields, statuses, exit codes, and Evidence location
   remain unchanged.
6. Existing Operator commands and `OperatorResult` remain unchanged.
7. Desktop continues to invoke the existing Mock Beta `execute --json` path.
8. No product component may execute provider text or shell text directly.

## 3. Current path comparison

| Concern | Public `execute` | Operator workflow | `factory-demo` |
| --- | --- | --- | --- |
| Entry point | `cmd_execute` | `operator-*` commands | `cmd_factory_demo` |
| Application service | `BetaExecutionService` | `OperatorService` | none; calls Runtime directly |
| Workspace | explicit `--workspace` | explicit `--workspace` | current working directory |
| Preflight | input/provider validation inside Beta service | explicit read-only `OperatorPreflight` | no product preflight |
| Planner | `RuleBasedExecutionPlanner` | Runtime Planner role and orchestrator | Runtime Planner role and orchestrator |
| Worker path | one `development_worker` identity through `SingleWorkerExecutionAdapter` | registered Runtime roles and workers | registered Runtime roles and workers |
| Runtime session lifecycle | not `RealWorkerRuntime`; creates bounded Beta identity and Evidence | full `RealWorkerRuntime` lifecycle | full `RealWorkerRuntime` lifecycle |
| ToolAction | not consumed | consumed when controlled execution is enabled | optional with `--enable-controlled-execution` |
| Controlled execution | unavailable | always enabled by `OperatorService.run` | disabled by default |
| Approval | Beta Evidence records `not_applicable` | `waiting_approval` -> grant/reject -> resume | optional demo behavior |
| QA | no QA role; plan's verify task is not executed | existing QA role, revision, and truth contract | existing QA role, revision, and truth contract |
| Evidence | bounded `execution_evidence.json` with summarized output | Runtime session, events, artifacts, execution Evidence, history, dashboard | raw Runtime session and artifacts |
| Public statuses | `completed`, `failed` | `running`, `waiting_approval`, `blocked`, `completed`, `failed` | Runtime statuses |
| Public role | stable Beta compatibility path and Desktop backend | closest existing end-to-end product workflow | diagnostic and acceptance-demo surface |

### 3.1 Public execute

`cmd_execute` calls `BetaExecutionService.execute`. That service:

1. validates a request of at most 1,000 characters and the Beta provider set;
2. creates Beta execution, session, and request identities;
3. builds a deterministic three-task plan;
4. selects only the `Execute goal` task;
5. calls one provider;
6. converts the provider response to `ExecutionInput`;
7. passes it through `SingleWorkerExecutionAdapter`;
8. persists bounded `execution_evidence.json`.

The adapter's default executor consumes the provider instruction into a simple
structured output. This path does not run `RealWorkerRuntime`,
`RuntimeOrchestrator`, role handoffs, `CodexAutomationBridge`,
`ControlledExecutor`, approval resume, or Runtime QA.

This is intentional AFDE-4.0 compatibility behavior, not a missing Runtime
implementation.

### 3.2 Operator workflow

`OperatorService` is already a thin application layer over existing
capabilities. It provides:

- read-only readiness checks;
- governed workspace and provider validation;
- `RealWorkerRuntime.run(..., enable_controlled_execution=True)`;
- status projection;
- exact approval grant, rejection, and separate resume;
- existing Runtime history and dashboard hints;
- artifact and execution-Evidence references.

Inside the Runtime, completed worker output passes through
`_execute_proposals`. Structured `actions` are validated by
`CodexAutomationBridge`; legacy developer file proposals and QA test requests
are also adapted to `ExecutionRequest`. `ControlledExecutor` classifies the
request, calls Approval Guardian, executes only allowed operations, and
persists execution Evidence. The Runtime merges observed Evidence into
`execution_verification`, applies the execution-truth contract, and forwards
verified results to QA.

This is the canonical end-to-end development capability.

The current deterministic Mock Operator flow injects
`[approval-resume-mvp]` and deliberately targets an approval fixture. That is
valuable acceptance coverage but is demo behavior, not a general product
request contract.

The live OpenAI role adapter already requests strict structured Developer
`proposed_file_writes` and QA `requested_test_executions` for normal goals.
The missing proposal seam is therefore limited to a deterministic,
network-free Product acceptance path; it is not a missing production
ToolAction or Controlled Execution capability.

### 3.3 factory-demo

`factory-demo` directly calls `RealWorkerRuntime` and exposes low-level Runtime
flags. It is useful for Runtime demonstrations, provider experiments, revision
coverage, and controlled-execution acceptance tests.

It is not the recommended product foundation because it:

- has no application-level preflight or product projection;
- uses the current directory rather than a product workspace abstraction;
- exposes Runtime/demo controls directly;
- leaves controlled execution opt-in;
- returns the raw Runtime session shape.

It must remain a diagnostic surface.

## 4. Capability Reuse Map

| Capability | Canonical implementation | Current proven use | Product Layer decision | New execution logic |
| --- | --- | --- | --- | --- |
| Request readiness | `OperatorPreflight` | Operator | reuse unchanged | none |
| Product framing | existing PM worker | Operator/demo | reuse unchanged | none |
| Planning | Runtime Planner role, `RuntimeOrchestrator` | Operator/demo | reuse unchanged for development runs | none |
| Provider selection | `ProviderBridge`, `ProviderManager` | Operator/demo | reuse through Operator/Runtime | none |
| Worker registry | `WorkerRegistry` | Runtime | reuse unchanged | none |
| Role execution | `RoleExecutor`, typed role results/handoffs | Runtime | reuse unchanged | none |
| Runtime lifecycle | `RealWorkerRuntime`, `RuntimeTask`, `RuntimePipeline` | Operator/demo | reuse unchanged | none |
| Tool contract | `ToolAction`, `ToolActionType` | structured action tests/demo | reuse unchanged | none |
| Tool adaptation | `CodexAutomationBridge` | Runtime controlled path | reuse unchanged | none |
| Mutation policy | `ControlledExecutionPolicy` | Operator/demo/tests | reuse unchanged | none |
| Mutation execution | `ControlledExecutor` | Operator/demo/tests | reuse unchanged | none |
| Approval decision | `ApprovalGuardian` | controlled execution | reuse unchanged | none |
| Approval persistence/resume | `RuntimeApprovalStore`, Runtime approval APIs | Operator | reuse unchanged | none |
| QA and revision | QA role, orchestrator, truth contract | Runtime | reuse unchanged | none |
| Artifacts and Evidence | `ArtifactStore`, EventStream, Runtime Evidence | all current paths | reference existing artifacts | none |
| History/dashboard | `RuntimeHistoryStore`, `RuntimeDashboard` | Operator | project read-only | none |
| Product coordination | not currently explicit | fragmented across commands | add thin Product Layer | required |
| Product projection | Operator projection is CLI-oriented | Operator presenter | add read-only product view over `OperatorResult` | required |

All execution and safety capabilities are reused. New logic is limited to
application-level coordination, intent selection, and presentation.

## 5. Product Layer Architecture

```text
User / future product surface
              |
              v
+-------------------------------------------+
| AI Development Engine Product Layer       |
|                                           |
| DevelopmentRunService                     |
| - select compatibility vs development use |
| - call preflight                          |
| - delegate run/status/approve/resume       |
| - return ProductRunView                    |
+----------------------+--------------------+
                       |
             development intent
                       |
                       v
+-------------------------------------------+
| Existing Operator application layer       |
| OperatorPreflight + OperatorService        |
+----------------------+--------------------+
                       |
                       v
+-------------------------------------------+
| Existing RealWorkerRuntime                 |
| PM -> Planner -> Developer -> QA -> Docs   |
|             |                              |
|             v                              |
| ToolAction -> CodexAutomationBridge        |
|             -> ControlledExecutor          |
|             -> Approval Guardian           |
|             -> approval resume when needed |
+----------------------+--------------------+
                       |
                       v
+-------------------------------------------+
| Existing Runtime truth and Evidence        |
| session / events / artifacts / execution   |
| Evidence / history / dashboard             |
+-------------------------------------------+

Compatibility adapters remain beside this path:

Public Beta execute -> BetaExecutionService -> Beta Evidence
Desktop            -> unchanged public Beta execute --provider mock --json
factory-demo       -> unchanged direct Runtime diagnostic path
```

### 5.1 Proposed Product Layer responsibilities

The Product Layer may:

- accept a workspace, user goal, provider selection, and explicit live opt-in;
- run existing preflight;
- choose the stateful development path for development intent;
- expose one product view containing status, current activity, approval
  requirement, exact next action, and Evidence references;
- delegate approve, reject, resume, status, and Evidence reads;
- translate existing internal results for a product surface.

The Product Layer must not:

- plan work itself;
- construct or execute shell commands;
- write files directly;
- approve actions;
- invent Runtime states;
- rewrite Runtime session or Evidence files;
- merge Beta and Runtime Evidence into a new truth source;
- parse untrusted provider prose into executable commands.

### 5.2 Product identity and Evidence

The Runtime session ID must be the canonical identity for a development run.
The Product Layer should not create a second persisted session identity.

For the MVP, `ProductRunView` should be derived from `OperatorResult` and
read-only Runtime projections. It should reference, rather than copy:

- Runtime session ID;
- pending approval ID;
- Runtime artifacts;
- controlled-execution request IDs;
- ToolAction IDs and fingerprints where present;
- Runtime history and dashboard views.

No `product_run_manifest.json` is required for the MVP. Adding a new persisted
manifest before a demonstrated query need would create another schema and
another recovery responsibility.

## 6. Minimal Integration Plan

This section is the implementation plan that preceded the current
`afde/product/` package. It is retained as design history and as a compatibility
checklist; it is not evidence that the current Product Layer is unimplemented.

### Step 1: Characterize contracts before composition

Add contract tests that freeze:

- public Beta `execute` JSON keys, statuses, exit codes, and Evidence location;
- Operator result fields and status projection;
- Desktop source and frozen use of Beta `execute --json`;
- Runtime lifecycle transitions for completed, waiting, rejected, resumed, and
  failed development sessions.

No production change is needed in this step.

### Step 2: Add a Product Layer package

Add an application-only package such as:

```text
afde/product/
  models.py
  service.py
  presenter.py
```

`DevelopmentRunService` should compose `OperatorService`; it must not subclass
or wrap `RealWorkerRuntime` directly. This preserves the existing preflight,
error normalization, approval separation, and read-only projection behavior.

The first internal operations should be:

- `preflight(workspace, provider, allow_live_api)`;
- `run(goal, workspace, provider, model, allow_live_api)`;
- `status(session_id, workspace)`;
- `approve(session_id, approval_id, workspace)`;
- `reject(session_id, approval_id, reason, workspace)`;
- `resume(session_id, workspace)`.

These operations delegate one-for-one to existing Operator capabilities and
return a product projection. They do not introduce public CLI commands in the
first implementation slice.

### Step 3: Establish a product-safe action proposal contract

Do not expose Mock markers such as `[approval-resume-mvp]` or
`[tool-action-auto]` as product inputs.

The Product Layer should accept only normal user goals. Developer output must
continue to use the existing structured proposal fields or existing
`ToolAction` schema. The Runtime already adapts both forms.

The deterministic Product MVP needs a bounded fixture owned by Product Layer
tests and an injected role executor. `RealWorkerRuntime` already provides the
`role_executor_factory` injection point. A narrow optional dependency seam in
`OperatorService` can pass an existing Runtime instance or factory from Product
Layer tests while preserving its current default behavior and public commands.
The injected executor is a test adapter over existing registered worker
identities, not a new Runtime worker.

It must not add marker semantics to Runtime lifecycle, ProviderBridge, or
public requests. Live-provider validation remains separately opted in and is
not required for offline acceptance.

This is the only material integration seam: arranging a normal product request
and an existing structured action-producing worker result. Action validation,
policy, execution, approval, and Evidence require no redesign.

### Step 4: Project existing Runtime progress

Build `ProductRunView` from `OperatorResult` plus existing read-only status,
history, and dashboard projections. Suggested product fields are internal and
non-persisted:

- `status`;
- `session_id`;
- `goal`;
- `provider`;
- `current_activity`;
- `approval_id`;
- `next_action`;
- `evidence_references`;
- `history_hint`;
- `dashboard_hint`.

Do not add these fields to `BetaExecutionResult` or the Desktop JSON contract.

### Step 5: Add a product surface only after the service proves stable

A later Sprint may add an additive CLI or Desktop product surface. That needs
separate Product Owner approval. It must call `DevelopmentRunService` and must
not alter the meaning of current commands.

The existing public `execute` command remains the Beta compatibility operation.
The existing Operator commands remain supported. `factory-demo` remains
diagnostic.

### Step 6: End-to-end acceptance

Offline acceptance must demonstrate:

1. product preflight;
2. normal goal submission;
3. existing Planner and Developer role execution;
4. a structured ToolAction;
5. ControlledExecutor classification;
6. auto-approved execution or `waiting_approval`;
7. exact grant/reject and resume behavior;
8. QA against observed execution Evidence;
9. completed Runtime Evidence and read-only product projection;
10. unchanged Beta execute and Desktop regression suites.

## 7. Why not extend public execute directly

A literal sequence of:

```text
current Beta execute
  -> full Runtime
  -> ToolAction
  -> approval
```

is rejected for the Product MVP.

It would create at least five incompatibilities:

1. **State mismatch:** Beta exposes only `completed` and `failed`; Runtime may
   expose `waiting_approval`, `blocked`, and `running`.
2. **Identity mismatch:** Beta creates its own `RWS-BETA-*` identity while
   `RealWorkerRuntime` creates `RWS-*`; serial invocation would create two
   sessions for one user operation.
3. **Evidence mismatch:** Beta Evidence records approval as `not_applicable`;
   Runtime Evidence records actual policy, approval, action, and lifecycle.
4. **Duplicate work:** running Beta planning/provider/worker and then Runtime
   planning/provider/workers repeats execution and may repeat paid calls.
5. **Desktop mismatch:** Desktop treats a zero-exit terminal Beta result as the
   successful end of its worker thread and has no approval/resume contract.

An internal replacement of `BetaExecutionService` with `RealWorkerRuntime`
would hide, not solve, those differences. It would also turn a compatibility
service into a second projection over the Runtime.

The Product Layer therefore composes the existing stateful Operator path and
leaves public Beta execute untouched.

## 8. Rejected alternatives

| Alternative | Decision | Reason |
| --- | --- | --- |
| Add a second Runtime for product runs | reject | duplicates lifecycle, persistence, recovery, and truth ownership |
| Add product-specific workers | reject | existing registered roles already own planning, development, QA, and documentation |
| Teach `BetaExecutionService` to execute ToolActions | reject | duplicates Runtime proposal, policy, approval, truth, and resume logic |
| Invoke Beta execute and then invoke Runtime | reject | duplicate planning/provider calls, identities, costs, and Evidence |
| Use `factory-demo` as the product API | reject | diagnostic flags and raw Runtime session are not a product application contract |
| Let Product Layer write files or run tests | reject | bypasses ControlledExecutor and Approval Guardian |
| Persist a new product Evidence schema immediately | defer | existing Runtime Evidence is already canonical |
| Expose Mock marker strings to users | reject | acceptance-fixture control is not product intent |
| Change Desktop to handle approval now | defer | violates AFDE-4.5 design-only and Desktop-contract boundaries |

## 9. Risk analysis

| Risk | Level | Failure mode | Mitigation |
| --- | --- | --- | --- |
| Beta/Runtime contract conflation | High | `execute` gains non-terminal states or changed JSON | keep compatibility path separate; golden contract tests |
| Duplicate execution | High | two provider calls or two worker runs for one goal | Product Layer chooses one path; never chain Beta and Runtime |
| Approval bypass | High | product code executes an action directly | all mutation delegates to ToolAction bridge and ControlledExecutor |
| Runtime lifecycle drift | High | Product Layer invents or rewrites states | project existing Operator/Runtime states read-only |
| Demo-marker leakage | High | product behavior depends on hidden request strings | use injected deterministic test outputs; no public markers |
| Evidence ambiguity | Medium | Beta Evidence and Runtime Evidence both appear canonical | Runtime session is canonical for development; Beta remains compatibility-only |
| Desktop regression | Medium | Desktop receives waiting approval or changed result fields | leave Desktop and Beta service untouched |
| Provider-output trust | High | prose becomes an executable action | accept only existing structured proposal/ToolAction validation |
| Live-provider cost | High | duplicated or implicit paid calls | single selected path and existing explicit live opt-in |
| Product projection staleness | Medium | cached product status disagrees with Runtime | derive on demand; do not persist duplicate state |
| Operator fixture coupling | Medium | general Mock run edits acceptance fixture | do not reuse marker injection as the product contract |
| Scope growth | Medium | settings, chat, dashboard, or new orchestration enters MVP | limit first slice to coordinator and product view |

## 10. Public Contract impact analysis

### Required impact for the recommended MVP

None.

| Contract | Impact |
| --- | --- |
| `afde.cli execute` syntax | none |
| Beta JSON result fields | none |
| Beta statuses and exit codes | none |
| Beta Evidence schema/path | none |
| Operator commands | none |
| `OperatorResult` | none |
| `factory-demo` | none |
| Runtime lifecycle/session schema | none |
| ToolAction schema | none |
| ControlledExecutor policy | none |
| Approval records/resume semantics | none |
| Desktop source/frozen contract | none |

The proposed initial `DevelopmentRunService` is internal. A future additive
public CLI or Desktop surface is a separate contract decision and requires a
separate Sprint and approval.

### Compatibility gates for any future implementation

- all existing Beta execution tests pass unchanged;
- source and frozen Desktop service tests pass unchanged;
- Operator acceptance and CLI tests pass unchanged;
- Runtime lifecycle, approval-resume, ToolAction, ControlledExecutor, QA, and
  Evidence tests pass unchanged;
- no new public status is added to Beta results;
- no existing JSON field is removed, renamed, or retyped;
- no existing exit code changes meaning;
- no automatic live call, approval, merge, or deployment is introduced.

## 11. Minimal expected change surface for a later Sprint

Expected new Product Layer files:

- `afde/product/models.py`;
- `afde/product/service.py`;
- `afde/product/presenter.py`;
- focused Product Layer tests.

One existing application-layer file may need a bounded compatibility-preserving
change:

- `afde/operator/service.py`: optional Runtime/factory dependency injection so
  Product Layer offline tests can use the existing Runtime
  `role_executor_factory` seam without magic request markers. Existing
  constructor defaults and Operator behavior must remain unchanged.

Expected reused files with no modification:

- `real_worker_runtime/runtime.py`;
- `real_worker_runtime/runtime_orchestrator.py`;
- `real_worker_runtime/role_execution.py`;
- `real_worker_runtime/tool_actions.py`;
- `real_worker_runtime/automation_bridge.py`;
- `real_worker_runtime/controlled_execution.py`;
- `real_worker_runtime/approval_resume.py`;
- Approval Guardian;
- Runtime artifact, history, dashboard, and Evidence stores.

Potentially touched only if separately approved:

- a future additive CLI registration;
- a future additive Desktop product mode.

Files that should not be modified to deliver the first Product Layer slice:

- `afde/execution/service.py`;
- `afde/execution/pipeline.py`;
- current Desktop execution service and worker;
- Runtime lifecycle models and transitions;
- public Evidence schemas.

## 12. Definition of done for the next implementation Sprint

The next implementation Sprint is complete only when:

- one Product Layer service provides a coherent development run over
  `OperatorService`;
- no new Runtime or worker exists;
- a normal goal reaches an existing structured action boundary without a
  user-visible marker;
- mutations remain governed by ControlledExecutor and Approval Guardian;
- waiting approval, rejection, grant, and resume use existing Runtime behavior;
- QA consumes observed Runtime Evidence;
- product status is a read-only projection;
- Beta execute, Operator, factory-demo, and Desktop contracts remain unchanged;
- offline Mock acceptance and the full regression suite pass;
- live OpenAI execution remains disabled unless separately approved.

## 12A. Future Multi-tool Development Boundary

### Purpose

The long-term AFDE Product Layer may decompose a user's development goal into
capabilities and coordinate code generation, images, video, audio, design
documents, packaging, and distribution tools as one product workflow.

This section defines only an architecture seam for that future. AFDE-4.5 does
not implement these tools, extend Runtime behavior, add new workers, or change
the current ToolAction or Evidence schemas. Any future implementation must
reuse the existing Runtime, safety, approval, artifact, and Evidence boundaries
described in the preceding sections.

### Current MVP and future boundary

| Boundary | Included responsibilities | AFDE-4.5 status |
| --- | --- | --- |
| Current Product Layer MVP | `OperatorService` composition, application-level coordination, read-only `ProductRunView`, existing Runtime/Approval/Evidence reuse | Current design target |
| Future extension boundary | Capability Registry, Capability Resolver, Tool Adapter Contract, capability-aware planning, tool selection, multimodal artifacts, asset pipeline, Product Assembly, multimodal verification | Future / Deferred / Not implemented in AFDE-4.5 |

The future items below are not AFDE-4.5 implementation targets. They must not
be used to expand the current Product Layer MVP change surface.

AFDE-4.7 supersedes only the architecture status of the registry foundation:
the Document, Knowledge, and Capability Registry standards and
`CAP-KNOW-0001` are now architecture-approved. Machine-readable registries,
Capability Resolver, Tool Adapter implementation, RAG, vector databases,
embeddings, and multimodal execution remain not implemented. References below
to ?쏤uture / Deferred / Not implemented in AFDE-4.5??remain accurate historical
statements about the AFDE-4.5 implementation boundary.

### 1. Capability Registry

**Status: Future / Deferred / Not implemented in AFDE-4.5.**

A Capability Registry may let AFDE discover available development capabilities
and their adapters. Example capability identifiers include:

- `code.generate`;
- `image.generate`;
- `image.transform`;
- `video.render`;
- `audio.generate`;
- `document.build`;
- `package.build`.

Each registry entry should describe availability, credentials, expected cost,
input and output types, approval policy, execution locality, and the adapter
that owns the capability. The registry is discovery metadata; it must not
execute a tool or become another Runtime.

### 2. Tool Adapter Contract

**Status: Future / Deferred / Not implemented in AFDE-4.5.**

External programs and APIs should connect through one common adapter contract.
The contract should cover:

1. availability checks;
2. input validation;
3. cost estimation;
4. governed execution;
5. output verification;
6. Evidence collection.

Product Layer and Runtime code must not bind directly to a specific provider,
desktop program, executable, or API. Tool-specific behavior belongs behind its
adapter and remains subject to existing controlled-execution and approval
boundaries.

### 3. Capability-aware Planning

**Status: Future / Deferred / Not implemented in AFDE-4.5.**

Capability-aware planning may decompose a user goal into dependent capability
requirements. It should distinguish:

- work that existing code execution can complete;
- work requiring an external tool;
- work requiring a user-supplied asset;
- work requiring explicit approval, cost, or external data transfer.

The existing Planner and execution-plan dependency structure must be reused as
the extension base. A second Planner must not be introduced.

### Capability Resolver

**AFDE-4.5 status: Future / Deferred. AFDE-4.9 foundation: M3 exact-ID
eligibility evaluation only.**

Planning determines WHAT capabilities are required.

Capability Resolver determines whether the requested capability is eligible.
Tool Adapter Selection identifies WHICH injected adapter candidate may satisfy
an eligible capability.

Selection should consider:

- availability;
- Credential requirements;
- cost;
- quality;
- privacy;
- offline support;
- fallback options.

Capability Resolver delegates execution through the Tool Adapter Contract and does not execute tools directly.

It is a Product Layer responsibility only.

Runtime remains responsible for execution, approval, Evidence, and lifecycle.

The AFDE-4.9 foundation evaluates one supplied Capability ID for eligibility
using injected Knowledge Provider metadata. It returns immutable resolved,
unresolved, blocked, or decision-required rationale. It does not discover or
rank multiple implementations, choose an adapter/provider/tool, or call
Runtime. AFDE-5.1 provides exact-ID Tool Adapter selection as a separate
application boundary without changing Resolver or Product Layer contracts.

Capability Resolver must not duplicate Runtime behavior.

### 4. Tool Selection and Fallback

**AFDE-4.5 status: Future / Deferred. AFDE-5.1 foundation: M3 exact-ID
single-adapter selection only.**

The AFDE-5.1 selection service consumes a resolved eligible Resolver or Planner
Resolution result and an injected authoritative candidate snapshot. It
exact-matches the Capability ID, preserves stable adapter-ID ordering, returns
an explicit no-selection result for zero matches, and blocks multiple matches
as ambiguous. It never executes the selected adapter and always disallows
Runtime and execution.

When several adapters provide the same capability, future selection may
consider safety, cost, speed, privacy, local execution, licensing, and current
availability. If selection or execution fails, control may move to another
eligible adapter or back to the user for an explicit decision.

Fallback must never silently weaken approval, credential, privacy, cost, or
verification policy.

### 5. Multimodal Artifact Contract

**Status: Future / Deferred / Not implemented in AFDE-4.5.**

Code, images, video, audio, documents, and packages may eventually share
common artifact metadata:

- producer and intended consumer;
- path or governed reference;
- media type and format;
- checksum;
- verification status;
- provenance and license information;
- approval state.

The existing Result Handoff, `ArtifactStore`, and Runtime Evidence concepts are
the extension base. AFDE-4.5 does not add these fields to the current Evidence
schema.

### 6. Asset Pipeline

**Status: Future / Deferred / Not implemented in AFDE-4.5.**

A future asset pipeline may distinguish `source`, `generated`, `approved`,
`optimized`, and `packaged` states and track asset versions, provenance,
licenses, and checksums. State transitions and persistence are deferred to a
later approved Sprint.

This concept must not be represented as new Runtime lifecycle states.

### 7. Product Assembly

**Status: Future / Deferred / Not implemented in AFDE-4.5.**

Product Assembly may coordinate code and media artifacts into one runnable or
distributable product, including build, package, integration-test, and
dependency results.

The Product Layer coordinates assembly decisions and references verified
outputs. It must not write files or execute build commands directly; those
actions continue through governed adapters, ToolAction, Controlled Execution,
and Evidence collection.

### 8. Cost, Credential, and Permission Preflight

**Status: Future / Deferred / Not implemented in AFDE-4.5.**

Future preflight may report:

- required external API credentials without exposing their values;
- required local program availability;
- estimated user-visible cost;
- external data-transfer implications;
- hardware capability;
- licensing or account constraints.

Credential availability is reported as readiness metadata only. Credential
values must remain secret and must never be copied into Product Layer state,
tool inputs, logs, artifacts, or Evidence.

Paid calls, external uploads, publication, and deployment must require explicit
approval. The existing `OperatorPreflight` and Approval Guardian boundaries are
the extension base.

### 9. Multimodal verification Evidence

**Status: Future / Deferred / Not implemented in AFDE-4.5.**

Possible future Runtime-observed Evidence categories include:

- `verified_generated_assets`;
- `verified_media_validations`;
- `verified_build_artifacts`;
- `verified_external_actions`.

These names are architecture examples only. AFDE-4.5 does not add them to the
current Runtime Evidence schema. As with the existing execution-truth
principle, provider claims must remain separate from Runtime-observed Evidence.

### Explicit non-goals

AFDE-4.5 does not implement:

- direct Photoshop, Figma, or Blender integration;
- direct image-generation API integration;
- direct video-generation API integration;
- FFmpeg or ImageMagick adapters;
- a plugin marketplace;
- automatic program installation;
- a Runtime per external tool;
- multimodal workers;
- changes to the existing ToolAction schema;
- changes to the existing Evidence schema;
- public CLI changes;
- Desktop changes.

### Architecture Principle

The long-term boundary is:

```text
Capability
    |
    v
Knowledge Foundation
    |
    v
Capability Resolver
    |
    v
Tool Adapter
    |
    v
Runtime
    |
    v
Evidence
    |
    v
Product Assembly
```

Planning decides WHAT.

Knowledge Foundation determines which documents, knowledge, capabilities, and
gaps are valid inputs to resolution.

Capability Resolver decides WHICH implementation.

Tool Adapter decides HOW.

Runtime executes.

Evidence verifies.

Product Layer assembles the final Product.

No external tool may be coupled directly to Runtime. Tool-specific logic must
not be added directly to Runtime or Product Layer. Every future tool connects
through a common adapter contract while existing Runtime, approval, truth,
artifact, and Evidence ownership remain authoritative.

## 13. Final recommendation

AFDE-4.5 should adopt the Operator application path as the execution backbone
of the AI Development Engine Product Layer. The Product Layer is not a new Runtime.
It is the smallest application seam that connects the existing
Operator -> Runtime -> ToolAction -> Controlled Execution -> QA -> Evidence
path into one coherent development experience.

The current MVP remains limited to application-level coordination and a
read-only product projection over `OperatorService` and existing Runtime
results. Public Beta execute remains a compatibility adapter, Desktop remains
unchanged, the Runtime Contract and lifecycle remain authoritative, and
`factory-demo` remains a diagnostic surface.

Future capability and multimodal expansion must connect through Capability
Resolver and the Tool Adapter Contract rather than adding tool-specific logic
to Runtime or Product Layer. Those extensions are deferred to separately
approved Sprints.

Knowledge Foundation sits before Capability Resolver and supplies governed
Document, Knowledge, and Capability metadata. It does not select an adapter,
execute Runtime, or alter Product Layer projection.

## 14. Audit evidence base

The conclusions in this document were derived from the current implementation,
public contracts, and regression boundaries in:

- `afde/cli.py`;
- `afde/execution/service.py`, `pipeline.py`, and `bridge.py`;
- `afde/operator/service.py`, `preflight.py`, `models.py`, and `presenter.py`;
- `real_worker_runtime/runtime.py`, `runtime_orchestrator.py`, and
  `role_execution.py`;
- `real_worker_runtime/provider_bridge.py` and `openai_provider.py`;
- `real_worker_runtime/tool_actions.py`, `automation_bridge.py`,
  `controlled_execution.py`, and `approval_resume.py`;
- Beta execution, Operator, Runtime lifecycle, role execution, ToolAction,
  Controlled Execution, approval-resume, Evidence, and Desktop regression
  tests.

At the capability-ownership level, every execution and safety responsibility
maps to an existing canonical component. Only product coordination and product
projection remain new responsibilities for the current MVP.

The original audit supported a Product Layer-only decision: reuse the existing
Operator and Runtime path, preserve Beta execute and Desktop compatibility, and
defer adapter implementation, multimodal artifacts, asset pipeline, and Product
Assembly implementation. AFDE-4.5 made no Runtime, Worker, lifecycle, state,
ToolAction, Evidence schema, public CLI, or Desktop contract change.

AI Factory OS is evolving from a code-oriented execution engine into a capability-oriented product orchestration platform.

AFDE-4.7 adds the architecture-approved Knowledge Foundation boundary and
registry standards. Its implementation remains deferred and requires a
separate Product Owner-approved Sprint.
