# AFDE-3.14 Beta E2E Scenarios

## Default Mock smoke

Run from the repository root:

    python -m afde.cli execute --request "Prepare a bounded Beta task" --provider mock --workspace . --json

Expected:

- exit code 0;
- status completed;
- three deterministic rule-based plan tasks;
- one development_worker for all tasks;
- deterministic_mock execution mode;
- unique execution, session, and request IDs;
- evidence under the reported session directory;
- no provider response body or credential in output or evidence.

Automated coverage:

    python -m pytest -q tests/test_beta_execution_e2e.py

## Three-run repeatability

The Mock E2E runs three consecutive times with the same request. Each run must
complete, retain the same deterministic plan ID, create unique execution,
session, and request IDs, and write a unique evidence artifact without reading
or overwriting another run.

## Configuration failures

Covered cases:

- unsupported provider;
- missing OPENAI_API_KEY;
- missing --allow-live-api;
- missing AI_FACTORY_RUN_LIVE_OPENAI_TESTS=1;
- empty request or model.

These cases return exit code 2 and attempt sanitized failure evidence.

## Execution failures

Covered cases:

- provider authentication, timeout, transport, and response failure;
- ProviderRuntimeBridge conversion failure;
- worker execution failure;
- evidence persistence failure.

Provider, bridge, and worker failures return exit code 5. Evidence persistence
failure returns exit code 7. CLI status remains failed in every failure case.

## Secret leakage review

Tests inject recognizable API-key and Authorization/Bearer-shaped values and
assert that they are absent from CLI JSON and persisted evidence. Provider
response and worker output bodies are represented only by bounded metadata and
hashes.

## Real OpenAI E2E

The paid test is:

    tests/test_beta_execution_openai_live.py

It is skipped unless OPENAI_API_KEY is configured and
AI_FACTORY_RUN_LIVE_OPENAI_TESTS equals 1. The test command itself also passes
--allow-live-api. All three conditions are required by the application service.

The live test uses the existing OpenAI Provider and the complete official Beta
path. It must be run only after separate Product Owner approval:

    python -m pytest -q tests/test_beta_execution_openai_live.py

The default offline suite explicitly sets the live-test opt-in to 0 during
release validation.
