# AFDE-4.0 Beta Acceptance Checklist

## Product path

- [x] One official Beta CLI command is defined.
- [x] The command reuses the existing Planner, Provider, bridge, pipeline, and
  single-worker adapter.
- [x] Mock is deterministic and network-free.
- [x] OpenAI remains explicit opt-in.
- [x] Single-worker sequential execution is enforced.
- [x] Existing factory-demo, Operator, and five-worker Runtime remain
  backward-compatible.

## Results and evidence

- [x] CLI result and process exit code use one documented contract.
- [x] Success evidence uses a unique Runtime session directory.
- [x] Failure evidence is attempted where persistence remains possible.
- [x] Evidence writes use the existing atomic ArtifactStore JSON path.
- [x] Provider response bodies and worker output bodies are not persisted.
- [x] API keys, authorization headers, tokens, and environment dumps are
  excluded.
- [x] Errors include category, stage, message, retryable, and sanitized fields.

## Offline validation

- [x] Mock full-path E2E implemented.
- [x] Three-run repeatability test implemented.
- [x] Provider, bridge, worker, and evidence failure tests implemented.
- [x] Secret leakage assertions implemented.
- [x] Final full pytest result recorded in AFDE-3.14 Release Evidence.
- [x] Final compileall result recorded in AFDE-3.14 Release Evidence.
- [x] Final git diff check recorded in AFDE-3.14 Release Evidence.
- [x] Manual three-run CLI smoke result recorded in AFDE-3.14 Release Evidence.

## Live validation

- [x] Complete OpenAI Beta E2E test implemented with three explicit opt-ins.
- [x] Product Owner approval received separately for each paid external call.
- [x] Each approval executed exactly one official Beta OpenAI smoke call with
  automatic retries disabled and no manual retry.
- [x] Approved real OpenAI smoke run completed successfully.

The first approved call returned a sanitized provider InternalServerError with
status failed and exit code 5. It was not retried. A second, separately
approved call completed successfully with exit code 0 using the official Beta
CLI, requested gpt-4.1-mini, a 60-second timeout, and SDK max_retries=0.

Both calls produced isolated Evidence without API keys, authorization headers,
provider response bodies, or full worker output bodies. The successful live
smoke criterion and final local validation evidence are complete.
