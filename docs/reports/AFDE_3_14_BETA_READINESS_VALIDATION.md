# AFDE-3.14 Beta Readiness Validation

## Purpose

AFDE-3.14 validates and minimally stabilizes the existing AFDE-3.13 execution
foundation for the AFDE-4.0 Beta. It introduces no second execution engine.
The application service only validates CLI input, creates identities, invokes
existing components, normalizes results, and persists evidence.

The official supported flow is:

    User Request
    -> RuleBasedExecutionPlanner
    -> AIProvider
    -> ProviderResponse
    -> ProviderRuntimeBridge
    -> ExecutionInput
    -> SingleWorkerExecutionAdapter
    -> WorkerExecutionResult
    -> Runtime Evidence
    -> CLI Result

## Installation

From the repository root:

    python -m pip install -r requirements.txt
    python -m compileall -q afde real_worker_runtime tests

Mock execution remains available without the OpenAI SDK being imported and
without provider credentials.

## Official Beta CLI

The one official Beta command is:

    python -m afde.cli execute --request "Prepare a bounded Beta task" --provider mock --workspace . --json

Supported providers are mock and openai. The worker mode is fixed to one
registered development_worker. The Beta service selects the plan's bounded
Execute goal task and performs one provider call and one worker execution.
factory-demo, Operator commands, and the existing five-worker Runtime remain
legacy-compatible separate commands and are not modified by this contract.

## Provider selection

- mock: deterministic, network-free, and the default smoke-test provider.
- openai: uses the existing public OpenAI Provider and requires all of:
  - OPENAI_API_KEY;
  - AI_FACTORY_RUN_LIVE_OPENAI_TESTS=1;
  - --allow-live-api.

OpenAI model selection order is:

1. CLI --model;
2. AI_FACTORY_OPENAI_MODEL;
3. the existing provider default.

No provider routing, fallback, Gemini execution, or Claude execution is part of
the Beta contract.

## Result and exit-code contract

CLI JSON includes:

- schema, execution, session, and request identifiers;
- status and final stage;
- plan and worker identity;
- provider, model, and execution mode;
- bounded worker-result summaries;
- evidence path;
- normalized error or null;
- the process exit code.

Official external statuses are completed and failed.

| Exit code | Meaning |
| --- | --- |
| 0 | Execution completed |
| 2 | Invalid input or provider configuration |
| 5 | Planning, provider, bridge, or worker execution failed |
| 7 | Evidence could not be persisted |

Normal CLI failures return structured output and do not expose uncontrolled
tracebacks.

## Runtime Evidence

Each execution receives unique execution_id, session_id, and request_id values.
Evidence is atomically written through the existing ArtifactStore to:

    data/runtime_sessions/<session_id>/execution_evidence.json

The schema includes:

- schema version and identities;
- start/completion timestamps and duration;
- final status and stage;
- bounded request summary and hash;
- rule-based plan summary;
- provider/model/execution-mode summary;
- single-worker mode and ordered result summaries;
- Runtime evidence including plan, worker, and execution status;
- normalized error and approval applicability;
- relative artifact path;
- explicit security assertions;
- Python major/minor version only.

Provider response bodies and worker output bodies are not persisted. Evidence
records only bounded metadata, output keys, lengths, and SHA-256 summaries.
API keys, authorization headers, access tokens, credentials, and environment
dumps are prohibited.

## Failure behavior

Errors are normalized into:

- stable internal code;
- category;
- stage;
- sanitized message;
- retryable boolean;
- sanitized: true.

Stages are limited to input, planning, provider, bridge, worker, evidence, and
completed. Failure evidence is attempted whenever persistence remains possible.
If evidence persistence itself fails, the CLI returns status failed, stage
evidence, and exit code 7.

## Unsupported behavior

This Beta path does not provide multi-agent execution, autonomous loops,
generated-content execution, memory, RAG, vector databases, provider routing,
UI changes, external integrations, or automatic approval.
