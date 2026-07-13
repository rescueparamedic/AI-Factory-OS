# AFDE-2.9 Runtime Task and Worker State Engine Report

## Scope

AFDE-2.9 adds a runtime-owned task model to the existing five-worker runtime.
`RuntimeTask` records its identifier, assigned worker, state, priority,
dependencies, inputs, outputs, runtime evidence, and append-only transition
history entries.

## Lifecycle

The task lifecycle uses the existing `WorkerState` type with additive states:

`PLANNING -> READY -> RUNNING -> QA -> COMPLETED`

An existing-file approval pause follows:

`RUNNING -> WAITING_APPROVAL -> RESUMED -> QA`

QA revision may transition `QA -> RUNNING -> QA`. Any active lifecycle state
may fail only through an explicitly allowed transition. Terminal states reject
further transitions.

## Runtime integration

After Planning completes, Runtime converts the normalized Planner output into
one Developer task. The task is attached to the AFDE-2.8 `WorkerContext`, so
the Developer receives the task without a new provider interface or a second
context layer. Task snapshots are stored in the runtime session and
`runtime_task.json`, including across approval continuation serialization.

The existing event stream now records `TASK_CREATED`, `TASK_STARTED`,
`TASK_COMPLETED`, `TASK_FAILED`, `APPROVAL_REQUESTED`, `APPROVAL_GRANTED`, and
`QA_COMPLETED` events with task identity and state. Existing runtime and
approval event names remain available for backward compatibility.

## Security and truth boundaries

Approval Guardian policy, persisted approval records, exact request binding,
pre-image validation, single-use consumption, controlled execution, and
Execution Truth normalization remain in their AFDE-2.7 components. Task
evidence contains runtime observations but does not promote provider claims to
verified truth. The OpenAI and mock provider request contracts are unchanged.

## Validation

- targeted pytest: 108 passed;
- full pytest: 352 passed, 1 skipped;
- compile validation: PASS;
- secret scan: PASS; and
- `git diff --check`: PASS.
