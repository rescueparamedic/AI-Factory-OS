# AFDE-2.8 PR-1 Worker Context Report

## Scope

AFDE-2.8 PR-1 introduces one runtime-owned `WorkerContext` for sequential
worker handoff. The context carries:

- the original task request and task metadata;
- the Planning Worker output;
- runtime-observed execution evidence; and
- snapshots of prior worker artifacts.

## Runtime integration

`RealWorkerRuntime` creates the context and passes the same instance through
the existing worker sequence. After Planning completes, its normalized output
is recorded before Development starts. Providers retain their existing
mapping-style access to `request`, `outputs`, and `revision`.

Approval continuations serialize the context to plain JSON data and restore it
at the approval boundary. Approval Guardian decisions, action fingerprints,
pre-image checks, single-use approval consumption, controlled execution, and
Execution Truth normalization remain in their existing components.

## Compatibility and validation

Legacy dictionary contexts remain accepted by workers and persisted runtime
continuations. Focused tests cover context creation, independent defaults,
planner-to-developer propagation, serialization round trips, legacy mappings,
and the AFDE-2.7 approval-resume lifecycle. Runtime evidence in the context is
runtime-owned and does not convert provider claims into verified truth.

Final local validation:

- focused tests: 64 passed;
- full pytest: 335 passed, 1 skipped;
- compile validation: PASS;
- secret scan: PASS; and
- `git diff --check`: PASS.
