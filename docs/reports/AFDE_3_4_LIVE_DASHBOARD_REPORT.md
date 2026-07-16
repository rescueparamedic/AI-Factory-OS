# AFDE-3.4 Live Terminal Dashboard Report

## Baseline and objective

AFDE-3.4 starts from `origin/develop` commit `d472853`, the merge commit for
PR #17. The objective is a practical live terminal view over the existing
AFDE-3.3 Runtime Dashboard without adding execution authority or another state
store.

## Architecture audit

- CLI entry point: `afde.cli runtime-dashboard`.
- Snapshot provider: `RuntimeDashboard`.
- State authority: persisted `RuntimePipeline` in RuntimeSession.
- Runtime status: centralized dashboard derivation from session and pipeline.
- Worker/task progress: existing RuntimeSession progress plus pipeline
  lifecycle state and history.
- Approval queue: existing `pending_approval` session projection.
- Timeline: existing `events.jsonl`, with RuntimePipeline history fallback.
- Evidence: existing registered session artifacts whose files are available.
- Repository: existing read-only Git status projection.
- Existing polling: no compatible runtime poller existed; the legacy HTML
  dashboard is a separate subsystem and was not adopted.

## Implementation

### Snapshot provider

`RuntimeDashboard.snapshot` remains compatible as a dictionary API and now
returns a safely copied structured snapshot containing session, runtime
status, current stage/task/worker, five team statuses, progress with source,
approval queue, deduplicated chronological timeline, available evidence,
repository fields, and snapshot timestamp.

Progress precedence is:

1. explicit RuntimePipeline progress;
2. existing explicit RuntimeSession progress;
3. deterministic RuntimePipeline lifecycle mapping; or
4. unavailable when no authoritative lifecycle state exists.

The lifecycle mapping is state-based and never uses elapsed time. Approval
pending derives from the immediately preceding pipeline state so pre-QA and
post-documentation waits remain distinguishable.

### Polling controller

`LiveDashboardController` owns refresh validation, sleeping, optional
maximum refresh count/duration, Ctrl+C handling, and last-valid-snapshot
recovery after a read failure. It calls only the snapshot provider and cannot
transition or persist RuntimePipeline state.

### Terminal renderer

`TerminalLiveDashboardRenderer` renders session/status, task/worker,
progress provenance, team lifecycle, pending approvals, newest timeline
events, evidence, repository state, refresh time/interval, and Ctrl+C
guidance. ANSI clearing is limited to detected supported TTYs. `--no-clear`
and redirected or unsupported terminals use safe append-only frames. Timeline
events are not repeated solely because no-clear polling occurred.

## CLI

~~~powershell
python -m afde.cli runtime-dashboard --session-id RWS-... --live
python -m afde.cli runtime-dashboard --session-id RWS-... --live --refresh-interval 0.5 --max-refreshes 5 --no-clear
python -m afde.cli runtime-dashboard --session-id RWS-... --live --max-duration 30
~~~

Existing non-live text and `--json` commands remain supported. `--live`
and `--json` are explicitly mutually exclusive.

## Security and policy

- RuntimePipeline remains the Single Source of Truth.
- Polling is read-only and executes no runtime work.
- Approval records are displayed but never approved, rejected, consumed,
  dismissed, or changed.
- Approval Guardian and Controlled Execution code and policy are unchanged.
- Codex Automation Bridge is not invoked by snapshot, polling, or rendering.
- Evidence is observed only; the dashboard produces, changes, or deletes none.
- No duplicate execution engine, pipeline, or runtime store was introduced.
- No external provider call, paid service, credential, or new dependency was
  used.

## Test coverage

Focused tests cover:

- AFDE-3.3 non-live compatibility;
- pipeline state, current task, current worker, worker status, and progress
  changes between snapshots;
- pending approval visibility without mutation;
- chronological timeline update and duplicate suppression;
- newly available evidence;
- Running, Waiting, Completed, and Failed derivation;
- incomplete-pipeline protection against false completion;
- explicit progress precedence, deterministic lifecycle progress, and
  unavailable progress;
- safely copied snapshots;
- interval validation, refresh count and duration bounds, non-busy sleeping,
  refresh-error recovery, and Ctrl+C;
- ANSI clear, forced no-clear, non-TTY fallback, and no-clear timeline
  behavior;
- bounded live CLI, JSON compatibility, and live/JSON conflict; and
- byte-for-byte confirmation that controller refresh does not mutate session
  state.

Focused result: `39 passed`.

Full regression result: `499 passed, 1 skipped`.

## Verification

- Full `python -m pytest`: PASS, 499 passed and 1 skipped.
- Targeted AFDE-3.4 and compatibility tests: PASS, 39 passed.
- Compileall for approval_guardian, afde, real_worker_runtime,
  sprint_auto_runner, and tests: PASS.
- `git diff --check`: PASS.
- Exact changed-scope common credential scan: PASS, no matches.
- Existing non-live dashboard CLI smoke: PASS.
- Bounded one-refresh live/no-clear CLI smoke: PASS.
- JSON snapshot CLI smoke: PASS with `explicit_session` progress.
- Public import smoke: PASS.
- Repository status: feature branch only; intended tracked changes plus two
  pre-existing user-owned untracked items that remain untouched.

## Known limitations

- Polling uses local file reads rather than filesystem notifications and has
  no transactional multi-process snapshot lock.
- Lifecycle-derived progress is coarse, explicitly labeled, and may regress
  during a legitimate QA revision loop.
- Unsupported or redirected terminals do not clear; summary frames repeat
  while already-seen timeline events are suppressed.
- The dashboard remains a local single-session terminal view.
- Web Dashboard, WebSocket/SSE transport, remote authentication, RBAC,
  multi-session aggregation, and remote evidence/repository state are deferred.

## Rollback

Revert the AFDE-3.4 feature commit after preserving runtime evidence needed for
investigation. The change is additive: AFDE-3.3 text/JSON output, runtime
pipeline persistence, approval behavior, Controlled Execution, and automation
contracts remain available without data migration.
