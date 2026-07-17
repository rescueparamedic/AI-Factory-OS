# AI Factory OS Sprint v2.7.3 적용 방법

## AFDE-3.2 Codex Automation Bridge

Worker results can now provide a canonical `actions` array using the strict
`ToolAction` contract. The bridge binds each action to its runtime context and
routes protected writes, commands, tests, and bounded Git operations through
the existing Approval Guardian and `ControlledExecutor`.

```powershell
python -m afde.cli tool-action-demo --path auto
python -m afde.cli tool-action-demo --path ask
python -m afde.cli tool-action-demo --path deny
python -m afde.cli tool-action-status --action-id <ACTION_ID>
```

The mock demo makes no API call. Merge, deploy, release, destructive Git,
protected-branch push, secret input, and raw shell-text extraction remain
unsupported. See `docs/reports/AFDE_3_2_CODEX_AUTOMATION_BRIDGE_REPORT.md`.

## AFDE-3.1 safe runtime approval enforcement

Protected real-runtime file and command actions now pass through one final
Controlled Execution boundary that evaluates the existing Approval Guardian,
records redacted decision evidence, and applies `AUTO_APPROVE`, `ASK_USER`, or
`DENY`. Waiting approvals bind the exact action and runtime context and are
revalidated before single-use resume. See
`docs/reports/AFDE_3_1_SAFE_AUTO_APPROVAL_ENGINE_REPORT.md`.

## AFDE-3.0 runtime lifecycle evidence

Each persisted `RuntimeTask` now includes additive `lifecycle_status`,
`lifecycle_transitions`, `role_lifecycle`, `failures`, and
`execution_summary` fields. Completed, failed, blocked, and approval-paused
runs therefore expose the exact stage, role attempts, revision count, result
references, and safe failure or approval details without changing existing CLI
commands. This evidence is local and provider-neutral; it does not enable live
API access, deployment, release, or automatic approval.

## Real Worker Demo

```powershell
python -m afde.cli factory-demo --request "Analyze a small feature and produce a plan and test result" --provider mock
```

Mock mode requires no API key. See `docs/guides/REAL_WORKER_DEMO_GUIDE.md`.

## OpenAI Provider (AFDE-2.6)

OpenAI execution is opt-in and can incur API charges. Credentials are read only
from `OPENAI_API_KEY`; never place a real key in project files or command output.

```powershell
$env:OPENAI_API_KEY = "<set-your-key-in-the-shell>"
$env:AI_FACTORY_OPENAI_MODEL = "gpt-4.1-mini"
$env:AI_FACTORY_OPENAI_TIMEOUT_SECONDS = "60"
$env:AI_FACTORY_OPENAI_MAX_RETRIES = "2"
python -m afde.cli factory-demo --provider openai --model gpt-4.1-mini --allow-live-api --request "Create a small Python utility"
```

Without both the key and `--allow-live-api`, no external request is made. The
default pytest suite also makes no live calls. Live validation must additionally
be explicitly enabled by setting `AI_FACTORY_RUN_LIVE_OPENAI_TESTS=1` for a
separately selected live test. For authentication errors verify the environment
variable; for timeouts increase the timeout; for rate limits retry later. Logs
and exceptions contain structured metadata, never authorization headers or keys.

To diagnose Responses API connectivity without running the Factory Runtime, use
one explicitly opted-in minimal probe at a time. A tests model/input only, B adds
instructions, and C adds the PM strict JSON Schema payload. Output is restricted
to response identifiers/lengths or sanitized error fields.

```powershell
python -m afde.cli openai-probe --probe A --model gpt-4.1-mini --allow-live-api
python -m afde.cli openai-probe --probe B --model gpt-4.1-mini --allow-live-api
python -m afde.cli openai-probe --probe C --model gpt-4.1-mini --allow-live-api
```

If Probe A fails before reaching OpenAI, the SDK-free raw HTTPS probe can isolate
the transport path. It sends only `model` and the fixed minimal input. Non-JSON
responses are represented only by content type, byte length, a short SHA-256
fingerprint, and an HTML flag; response bodies and headers are never printed.

```powershell
python -m afde.cli openai-raw-probe --model gpt-4.1-mini --allow-live-api
```

For HTTP-boundary diagnosis, the following command checks DNS, TLS certificate
summary, unauthenticated urllib/httpx HEAD requests, and an independent
unauthenticated Windows `curl.exe` HEAD request. It does
not send an API POST:

```powershell
python -m afde.cli openai-http-boundary --model gpt-4.1-mini
```

Add both `--include-post` and `--allow-live-api` only for one controlled minimal
POST. Diagnostic output contains header names but never header values, resolved
IP counts but never addresses, and environment variable state but never values.

The curl-specific one-time POST uses an in-memory curl config sent through an
anonymous stdin pipe, so the API key is absent from the visible command line and
is never written to a config file. The key still briefly exists in process memory
and the pipe; privileged process inspection or debugging could observe either.

```powershell
python -m afde.cli openai-http-boundary --model gpt-4.1-mini --include-curl-post --allow-live-api
```

To classify a non-2xx OpenAI JSON error response, add
`--include-curl-error-details`. This exposes only `error.message`,
`error.type`, `error.code`, `error.param`, and `request_id`, plus the bounded
HTTP classification; the complete response body remains undisclosed.

### Controlled real execution MVP

Local execution remains disabled by default. `--enable-controlled-execution`
allows only structured provider proposals to cross a runtime-owned request,
policy, Approval Guardian, and bounded-executor boundary. Raw provider prose is
never executed.

The initial file capability creates allowlisted UTF-8 text files only under
`controlled_execution/`. Existing-file replacement stops at mandatory approval;
workspace escape, `.git`, credential targets/content, and unsupported suffixes
are denied. The initial command capability uses `shell=False` and permits only a
small local validation allowlist. Executable sandbox Python is restricted to
literal `print(...)` statements for the deterministic MVP proof.

Executor observations—not provider claims—populate `verified_changed_files` and
`verified_test_executions`. This is a bounded validation bridge, not autonomous
coding or unrestricted repository modification.

## 1. ZIP 저장 위치
다운로드한 ZIP 파일을 아래 폴더에 저장합니다.

```text
C:\AIFactory\AI Factory OS\updates\
```

## 2. 압축 해제
ZIP을 압축 해제하면 다음 구조가 보입니다.

```text
patch
CHANGELOG.md
README.md
```

## 3. patch 폴더 열기
`patch` 폴더를 엽니다.

## 4. patch 안의 내용 복사
`patch` 폴더 안에서 모든 항목을 선택합니다.

```text
Ctrl + A
Ctrl + C
```

주의: `patch` 폴더 자체를 복사하는 것이 아니라, `patch` 안의 내용물을 복사합니다.

## 5. 프로젝트 루트에 붙여넣기
아래 폴더에 붙여넣습니다.

```text
C:\AIFactory\AI Factory OS\
```

즉, `main.py`가 있는 폴더입니다.

같은 이름의 파일이 있다고 나오면 **대상 파일로 바꾸기 / 덮어쓰기**를 선택합니다.

## 6. 테스트 명령
PowerShell 또는 VS Code Terminal에서 아래 명령을 순서대로 실행합니다.

```powershell
cd "C:\AIFactory\AI Factory OS"
python main.py -h
```

정상이라면 명령 목록에 `scheduler`가 보여야 합니다.

그다음 아래 명령을 순서대로 실행합니다.

```powershell
python main.py version
python main.py doctor
python main.py dashboard live-build
python main.py chat latest
python main.py scheduler status
python main.py scheduler enqueue --title "v2.7.3 Scheduler Final 테스트" --worker markdown_worker --priority high --payload '{"filename":"docs/operations/v2_7_3_scheduler_final_test.md","title":"v2.7.3 Scheduler Final Test","body":["Scheduler final package completed"]}'
python main.py scheduler next
python main.py scheduler run-next
python main.py scheduler list --limit 5
python main.py dashboard live-build
```

## AFDE-3.8 Operations Center

The localhost Web Dashboard now compares 2 to 5 validated discovered sessions
through one consolidated read-only request. `OperationsAnalytics` is a pure,
transport-neutral projection over safely copied Runtime Dashboard snapshots;
it does not access `RuntimePipeline`, persist analytics, or mutate session data.

Read-only endpoints are:

- `GET /operations` for the selected primary session.
- `GET /compare?session_id=RWS-...&session_id=RWS-...` for 2 to 5 unique
  discovered sessions.
- `GET /operations-report?...` for JSON report data plus a safely escaped CSV
  representation and sanitized filenames. The browser also exports the current
  exposed projection with a client-side Blob; the server writes no report file.

The Operations Center presents snapshot-derived status counts, worker and
approval totals, evidence totals, progress-source counts, and average/median
elapsed duration. Elapsed duration includes only sessions with valid,
timezone-aware, non-negative start/end timestamps, and the API reports the
duration denominator. Missing values remain `null`/unavailable.

Stage durations are `measured` only when an explicit non-negative duration is
present, `inferred` from defensible timeline transitions or an active stage
start, and otherwise `unavailable`; measured values take precedence. Advisory
findings use centralized deterministic rules: longest available stage, Waiting
with pending approval, approval age (warning at 30 minutes, critical at 2
hours), failed workers, repeated failure category, and active-session aging
(30 minutes) or staleness (2 hours). Completed and failed sessions are excluded
from active staleness warnings. Failure summaries report available errors and
correlated evidence identifiers but never claim root cause.

Comparison selection is URL-only presentation state, survives polling, and is
revalidated after lower-frequency discovery. Operations requests cannot
overlap, stale responses are discarded after selection changes, findings are
capped at 100 visible rows, and all filters/sorts operate on copies. Rendering
uses `textContent`, semantic tables, labeled controls, ARIA live status, visible
focus, reduced-motion support, and responsive overflow. The boundary remains
localhost-only, GET/HEAD-only, metadata-only for evidence, and contains no
approval, execution, runtime, repository, or filesystem mutation operation.

## AFDE-3.7 Interactive Operations Dashboard

The localhost dashboard now discovers existing persisted runtime sessions and
allows switching without restarting the server:

~~~powershell
python -m afde.cli runtime-dashboard-web --session-id RWS-... --host 127.0.0.1 --port 8765 --poll-interval 1
~~~

`GET /sessions` returns safe summary data only. The browser requests a selected
snapshot with `/runtime?session_id=RWS-...`; the server accepts only a valid ID
that is present in current discovery results. Session paths are never returned.

The browser adds global snapshot search, worker/approval/timeline/evidence
filters, stable sorting, snapshot-derived statistics, sticky section
navigation, and keyboard-accessible metadata detail dialogs. Active filters
remain presentation state across polling updates. Timeline rendering is capped
at 50 visible events and session discovery refreshes independently at a lower
frequency with its own overlap guard.

All interaction remains inspection-only. Details use safe DOM text, evidence
is metadata-only, and there are no approval, execution, download, file-open,
delete, or repository mutation controls. Existing AFDE-3.3 through AFDE-3.6
CLI and API routes remain available.

## AFDE-3.6 Live Web Dashboard

Start the localhost operations console for one persisted runtime session:

~~~powershell
python -m afde.cli runtime-dashboard-web --session-id RWS-... --host 127.0.0.1 --port 8765 --poll-interval 1
~~~

Open `http://127.0.0.1:8765/`. The live dashboard shows runtime and current
operation, five lifecycle stages, worker progress with provenance, pending
approvals, the chronological timeline, evidence metadata, repository state,
and connection/refresh status. A keyboard-accessible `Refresh now` button
performs the same read-only GET as the automatic loop.

The browser makes one non-overlapping `GET /runtime` per configured interval.
On a temporary failure it keeps the last valid snapshot visible, reports the
disconnect through an ARIA live region, retries, and reports recovery after a
successful response. Polling is cancelled on page unload. Runtime values are
written with safe DOM text APIs; no runtime value is interpreted as markup.

Progress is labeled as `explicit_pipeline`, `explicit_session`,
`lifecycle_derived`, or `unavailable`. Evidence remains metadata-only and is
limited to available artifacts inside the selected runtime session directory;
there is no arbitrary file-serving or preview route.

The API routes and CLI commands documented below remain compatible with
AFDE-3.3 through AFDE-3.5. The dashboard remains localhost-only and has no
authentication, TLS, RBAC, WebSocket/SSE, remote access, or multi-session
aggregation.

## AFDE-3.5 Web Dashboard Foundation

Serve one persisted runtime session on localhost:

~~~powershell
python -m afde.cli runtime-dashboard-web --session-id RWS-...
~~~

Configure the local port and browser polling interval:

~~~powershell
python -m afde.cli runtime-dashboard-web --session-id RWS-... --host 127.0.0.1 --port 8765 --poll-interval 1
~~~

Open `http://127.0.0.1:8765/` in a browser. The responsive dashboard shows
Runtime, Workers, Timeline, Approval Queue, Evidence, and Repository cards.
The browser performs one GET of `/runtime` per interval and updates all cards
from that snapshot.

Read-only JSON endpoints:

- `GET /runtime`
- `GET /session`
- `GET /workers`
- `GET /timeline`
- `GET /approval-queue`
- `GET /evidence`
- `GET /repository`
- `GET /config`

`RuntimePipeline` remains the Single Source of Truth.
`DashboardAPI` consumes only the AFDE-3.4 `RuntimeDashboard.snapshot`
interface; HTTP controllers do not access pipeline state. The server permits
GET and HEAD only. It has no approve, execute, modify, create, or delete
operation, and polling never changes runtime, approval, or evidence state.

AFDE-3.5 is intentionally localhost-only and has no authentication, database,
external service, TLS, or cloud deployment. The transport-neutral API prepares
for future WebSocket/SSE, authentication, RBAC, remote dashboard, and
multi-session adapters without implementing them in this sprint.

## AFDE-3.4 Live Terminal Dashboard

Refresh a persisted runtime session once per second until Ctrl+C:

~~~powershell
python -m afde.cli runtime-dashboard --session-id RWS-... --live
~~~

Bounded no-clear output is suitable for scripts, redirected logs, tests, and
terminals without reliable ANSI clearing:

~~~powershell
python -m afde.cli runtime-dashboard --session-id RWS-... --live --refresh-interval 0.5 --max-refreshes 5 --no-clear
~~~

`--max-duration <seconds>` provides an optional time bound. Refresh interval,
refresh count, and duration must be positive. `--live` and `--json` are
mutually exclusive; use the existing non-live `--json` command for one
machine-readable snapshot.

The live view polls the existing read-only Runtime Dashboard projection.
`RuntimePipeline` remains the Single Source of Truth. Polling never executes
work, transitions state, produces evidence, or approves, rejects, consumes, or
dismisses approvals. Progress is labeled `explicit_pipeline`,
`explicit_session`, `lifecycle_derived`, or `unavailable`; derived
progress is a deterministic lifecycle indicator, not a time estimate.

ANSI clearing is used only when supported. Redirected and unsupported output
falls back safely without clearing, and `--no-clear` forces that behavior.
The provider/controller/renderer interfaces are reusable by a later Web
Dashboard, which is not implemented in AFDE-3.4.

## AFDE-3.3 Runtime Dashboard

Show a persisted runtime session as a human-readable snapshot:

~~~powershell
python -m afde.cli runtime-dashboard --session-id RWS-...
~~~

Use JSON for automation:

~~~powershell
python -m afde.cli runtime-dashboard --session-id RWS-... --json
~~~

The view reports runtime status; Development, QA, Documentation, Approval, and
Release status/current task/progress; pending approvals; chronological runtime
events; available evidence artifacts; and current Git branch, tree state, and
latest commit. It reads the existing RuntimePipeline and persisted runtime
records and does not perform transitions or side effects.

## AFDE-2.7 approval pause and resume

An existing-file `FILE_WRITE` is never auto-approved. Runtime persists the exact
typed request, expected pre-image SHA-256, normalized payload, Guardian decision,
session, and single-use fingerprint before entering `waiting_approval`. The
target remains unchanged and later workers do not run.

```powershell
python -m afde.cli approval-show --id APR-...
python -m afde.cli approval-approve --id APR-...
python -m afde.cli approval-reject --id APR-...
```

Approval validates the saved session and continuation, checks the current
pre-image, executes only the bound request, consumes once, and resumes at the
next worker. Unknown, changed, rejected, consumed, stale, and replayed approvals
fail closed. `PREIMAGE_MISMATCH` writes nothing.

The tracked `tests/fixtures/afde_2_7_approval_target.txt` is reserved for the
separately authorized live test. Stop at `waiting_approval` for Product Owner
approval. Do not stage a live-modified fixture. Rollback is manual after evidence
preservation; no automatic rollback, wildcard approval, delete, rename, shell,
network, or package capability is added.

## 7. 정상 기대 결과

- `python main.py -h` 결과에 `scheduler` 표시
- `version` 정상 출력
- `doctor` 결과 HEALTHY 또는 기존 Warning 수준
- `dashboard live-build` 결과 `status : completed`
- `chat latest` 결과 기존 Conversation 출력
- `scheduler status` 결과 `status : available`
- `scheduler enqueue` 결과 `Scheduler Job Queued`
- `scheduler next` 결과 다음 Job 표시
- `scheduler run-next` 결과 `status : completed`
- `scheduler list --limit 5` 결과 completed Job 표시

## 8. 캡처해서 전달할 화면
아래 3개 결과가 보이는 터미널 화면을 캡처해서 전달하면 됩니다.

```text
python main.py -h
python main.py scheduler run-next
python main.py dashboard live-build
```
