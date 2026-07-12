# AI Factory OS Sprint v2.7.3 적용 방법

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
