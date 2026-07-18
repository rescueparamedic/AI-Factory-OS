# AFDE-3.14 Beta Readiness Validation Release Evidence

## Release Identity

- Project: AI Factory OS
- Sprint: AFDE-3.14 Beta Readiness Validation
- Baseline: df65725c1d7a13931764ce8dab9ce27d964f0ac4
- Feature branch: feature/afde-3.14-beta-readiness-validation
- Release stage: local release candidate
- Pull request: NOT CREATED
- Merge status: NOT MERGED

## Sprint Objective

Validate and minimally stabilize the existing Provider, Planner,
ProviderRuntimeBridge, RealExecutionPipeline, single-worker adapter, Runtime
Evidence, and CLI contracts for AFDE-4.0 Beta preparation.

## Implemented Scope

- Added one official afde execute Beta CLI.
- Added a bounded application service that invokes existing Planner, Provider,
  RealExecutionPipeline, and single-worker contracts.
- Added unique execution, session, and request identities.
- Added atomic execution_evidence.json persistence under the existing Runtime
  session directory convention.
- Added stable completed/failed results and exit codes 0, 2, 5, and 7.
- Added normalized input, provider, bridge, worker, and evidence failures.
- Added explicit 60-second OpenAI timeout, disabled SDK retries, and allowlisted
  HTTP status/request-ID diagnostics without raw error bodies.
- Added bounded provider and worker summaries without response/output bodies.
- Added three-way OpenAI opt-in enforcement.
- Added deterministic Mock E2E, repeatability, failure, and secret-leakage
  coverage.
- Added a complete opt-in OpenAI Beta E2E test.

## Official Beta Contract

The supported command is:

    python -m afde.cli execute --request "Prepare a bounded Beta task" --provider mock --workspace . --json

Supported providers are mock and openai. Execution uses one registered
development_worker and the plan's bounded Execute goal task, producing exactly
one provider call and one worker result per official Beta CLI execution.
Evidence is written to:

    data/runtime_sessions/<session_id>/execution_evidence.json

Existing factory-demo, Operator, legacy ProviderManager, and five-worker Runtime
behavior remain unchanged.

## Validation Evidence

| Validation | Result |
| --- | --- |
| Single-call AFDE-3.14 targeted regression suite | PASS: 24 passed, 1 skipped |
| OpenAI provider and failure protection regression | PASS: included in targeted suite |
| Full offline pytest suite after retry-readiness changes | PASS: 646 passed, 2 skipped |
| Python compileall for afde, real_worker_runtime, and tests | PASS |
| git diff --check | PASS |
| Manual official Mock CLI smoke, three consecutive runs | PASS: 3 completed, exit code 0 |
| Execution ID uniqueness across three runs | PASS |
| Session ID uniqueness across three runs | PASS |
| Request ID uniqueness across three runs | PASS |
| Evidence path uniqueness and artifact count | PASS: 3 unique paths, 3 files |
| Synthetic API-key and bearer-token CLI scan | PASS: no leakage |
| Synthetic API-key and bearer-token evidence scan | PASS: no leakage |
| Provider response body persistence check | PASS: body not persisted |
| Production/documentation high-confidence credential scan | PASS: 0 matches |
| Real OpenAI Beta E2E implementation | PASS: implemented with three opt-ins |
| First approved real OpenAI execution | FAILED: one call returned InternalServerError; no retry |
| Second separately approved real OpenAI execution | PASS: completed, exit code 0; no retry |
| Clean-environment dependency installation | NOT EXECUTED: no package installation was required or approved |

The two skipped tests in the full offline suite are the existing paid OpenAI
live test and the new official Beta OpenAI E2E. The validation command forced
AI_FACTORY_RUN_LIVE_OPENAI_TESTS to 0, so no paid or external call could run.

## First Real OpenAI Smoke Evidence

Product Owner approval was granted for exactly one official Beta OpenAI smoke
call. The application service selected one bounded Execute goal task, and the
OpenAI SDK was configured with automatic retries disabled.

- Workspace:
  C:\tmp\afde314-openai-smoke-bbf24178032a47f6a797bde38bc43f4b
- Status: failed
- Exit code: 5
- Execution ID: EXEC-6cb15a902533477bbb55ed47b0e267fb
- Session ID: RWS-BETA-20260719-001105-f3f94bc0
- Request ID: REQ-d0121c2ab5ba4340a661ade74e3635cb
- Evidence:
  data/runtime_sessions/RWS-BETA-20260719-001105-f3f94bc0/execution_evidence.json
- Evidence created: yes
- Error code: BETA_PROVIDER_REQUEST
- Error category/stage: provider_request / provider
- Sanitized provider error: OpenAI request failed (InternalServerError)
- Retryable classification: true
- Automatic or manual retry performed: no
- Additional OpenAI call performed: no
- API key in CLI/evidence: no
- Authorization header in evidence: no
- Provider response body persisted: no
- Full worker output body persisted: no

The first approved external attempt did not satisfy the successful
real-provider acceptance criterion. No retry was attempted under that
approval.

## Second Real OpenAI Smoke Evidence

Product Owner approval was separately granted for one additional official Beta
OpenAI smoke call. Preconditions verified the feature branch, SDK
max_retries=0, an explicit 60-second timeout, the official Beta CLI, the
gpt-4.1-mini requested model, and a new isolated workspace.

- Workspace:
  C:	mpafde314-openai-smoke-2-3ac913fb99ae49abb3d190aa929ff17c
- Status: completed
- Exit code: 0
- Execution ID: EXEC-551ae75ee7a4440b83290118f7bdf353
- Session ID: RWS-BETA-20260719-004456-16b95724
- Request ID: REQ-464bc4b7dac14b0199dc14606717c947
- Requested model: gpt-4.1-mini
- Actual served model: gpt-4.1-mini-2025-04-14
- Execution mode: live
- Evidence:
  data/runtime_sessions/RWS-BETA-20260719-004456-16b95724/execution_evidence.json
- Evidence created: yes
- Provider request ID persisted: no
- Automatic or manual retry performed: no
- Additional OpenAI call performed under this approval: no
- API key in CLI/evidence: no
- Authorization header in evidence: no
- Provider response body persisted: no
- Full worker output body persisted: no

The second separately approved call satisfied the successful real-provider
acceptance criterion. The live opt-in was reset to 0 immediately after the
single CLI execution.

## Mock Repeatability Evidence

The official CLI ran three times in the isolated workspace:

    C:\tmp\afde314-smoke-b91a70ea4bbe483eb053947cc3b23c7f

Observed results:

- statuses: completed, completed, completed;
- exit codes: 0, 0, 0;
- execution IDs: all unique;
- session IDs: all unique;
- request IDs: all unique;
- evidence paths: all unique;
- execution_evidence.json files: 3.

The deterministic plan ID remained stable for the identical request while
run-scoped identities and artifacts remained isolated.

## Security Evidence

- API credentials are read only for explicit OpenAI execution.
- Live OpenAI requires OPENAI_API_KEY,
  AI_FACTORY_RUN_LIVE_OPENAI_TESTS=1, and --allow-live-api.
- The CLI and evidence contain bounded request and result summaries.
- Provider response bodies and worker output bodies are not persisted.
- Evidence does not contain authorization headers, access tokens, API keys, or
  a full environment dump.
- Normalized errors use sanitized messages and never serialize raw provider
  exception bodies.

## Scope Exclusions

- No multi-agent execution
- No autonomous loop
- No RAG
- No memory
- No vector database
- No provider routing or fallback
- No UI changes
- No new external integration
- No changes to factory-demo, Operator, or the five-worker Runtime

## Remaining Acceptance Items

- Optionally validate installation in a fresh environment if required for the
  AFDE-4.0 distribution process.
- Push the feature branch and create a pull request only after separate
  approval.

## Final Status

**AFDE-3.14 BETA READINESS VALIDATION COMPLETED**

The deterministic Mock path, complete offline regression suite, evidence
security checks, and separately approved successful real OpenAI Beta smoke are
validated. Commit, push, pull request, and merge remain outside this validation
and were not performed.
