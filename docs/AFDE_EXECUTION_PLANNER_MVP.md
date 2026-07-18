# AFDE Execution Planner MVP

AFDE-3.11 adds a deterministic, rule-based Execution Planner for the product
path toward AFDE-4.0 Beta. It converts one operator goal into one persisted
ExecutionPlan containing a small dependency-ordered set of ExecutionTasks. It
does not call an AI provider.

## Product flow

```text
Goal -> ExecutionPlan -> ExecutionTask
```

Every plan contains exactly three rule-generated tasks:

1. Prepare execution.
2. Execute goal after preparation.
3. Verify result after execution.

The plan ID is derived deterministically from the normalized goal. Task IDs and
dependencies are derived from that plan ID. Plans are stored as JSON under
`data/execution_plans/`.

## CLI

Create a plan from PowerShell:

```powershell
python -m afde.cli plan create --goal "Deliver the AFDE-4.0 Beta" --workspace .
```

Show the persisted plan using the ID printed by `plan create`:

```powershell
python -m afde.cli plan show --plan-id PLAN-0123456789ABCDEF --workspace .
```

Both commands support `--json`.

## Models

ExecutionPlan contains:

- `plan_id`
- `goal`
- `created_at`
- `status`
- `tasks`

ExecutionTask contains:

- `task_id`
- `title`
- `description`
- `priority`
- `status`
- `depends_on`

`estimated_complexity` is intentionally excluded from this sprint.

## Validation

The MVP validator checks only:

- duplicate task IDs;
- dependencies that do not identify a task in the plan;
- cyclic dependencies.

Validation fails before a generated plan is persisted. Advanced schema,
capacity, optimization, scheduling, and replanning validation are outside the
AFDE-3.11 scope.

## Dashboard

The Runtime Dashboard reads the latest valid persisted plan and shows a
read-only Execution Plan Summary:

- Plan ID
- Goal
- Total Tasks
- Completed
- Pending

The Dashboard does not update plans or task status.

## Non-goals

The MVP does not implement AI planning, multi-agent execution, memory,
analytics, optimization, scheduling, automatic replanning, or CLI export. The
PlannerService includes JSON serialization for internal and API use, but an
export command is deferred until after the Beta-critical workflow is proven.
