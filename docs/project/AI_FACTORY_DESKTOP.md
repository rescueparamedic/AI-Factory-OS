# AI Factory Desktop MVP

## Purpose

AI Factory Desktop is the minimum Windows GUI over the existing AI Factory OS
Beta execution path. It lets an operator select one project directory, enter a
natural-language goal, run the deterministic Mock Provider, review status and
log output, and open the persisted `execution_evidence.json` file.

AFDE-4.4 presents that unchanged execution path as three Korean-labeled steps:
`1. 프로젝트 폴더`, `2. AI에게 맡길 작업`, and `3. AI 실행`.

The product label is **AI Factory Desktop — Powered by AI Factory OS**.

## Install And Run

PySide6 is optional so CLI-only installations do not receive the Qt runtime.

```powershell
python -m pip install -r requirements-desktop.txt
python -m afde.desktop
```

Source execution remains available. AFDE-4.3B also provides an optional
PyInstaller windowed onedir build at
`dist\AI Factory Desktop\AI Factory Desktop.exe`. See
`AI_FACTORY_DESKTOP_PACKAGING.md` for build and validation details. The
package is not an installer and does not change the default CLI dependencies.

## Execution Architecture

```text
DesktopMainWindow
  -> QThread DesktopExecutionWorker
  -> DesktopExecutionService
  -> existing afde.cli execute --provider mock --json contract
  -> existing Beta Runtime and execution_evidence.json
```

The UI collects input and renders state only. The Qt-independent application
service validates inputs, constructs the fixed Mock command, disables live
OpenAI environment opt-in, parses the existing JSON/exit-code contract, and
resolves Evidence inside the selected workspace. Runtime logic is not copied.

Execution runs outside the main UI thread. Run remains unavailable until both
inputs contain text. While execution is active, Run, folder selection,
workspace, request, and result controls are disabled and the progress bar is
indeterminate beside the current status. Closing the window is blocked until
execution finishes, which avoids abandoning an orphan subprocess.

## Supported Flow

1. Select `폴더 선택` or enter an existing path under
   `1. 프로젝트 폴더`.
2. Enter a non-empty bounded goal under `2. AI에게 맡길 작업`.
3. Select the prominent `3. AI 실행` action.
4. Review `입력 확인 중`, `AI 작업 실행 중`, `실행 완료`, or
   `실행 실패` beside the progress bar. Internal status values remain
   Validating, Running, Completed, and Failed.
5. On success, review Session ID, Provider, execution mode, exit code, and the
   absolute Evidence path in `상세 실행 기록`.
6. Select `실행 결과 열기` to use the Windows default JSON file application.

Errors use `Status`, `Error`, `Cause`, and `Next` log fields. Missing workspace,
empty request, Python/CLI startup, nonzero exit, malformed JSON, missing session
identity, unsafe or missing Evidence, and internal worker failures are handled
without terminating the GUI event loop.

## Current Scope And Limitations

- Mock Provider only; there is no Provider selection UI or external API call.
- Python and packaged Windows EXE launch are supported; there is no installer,
  updater, code signing, or system tray.
- No Approval workflow, Codex execution, Git/GitHub action, dashboard, session
  browser, history viewer, settings, themes, graph, or plugin system.
- Runtime output is persisted by the existing Beta contract under the selected
  workspace. Operators remain responsible for their workspace ignore policy.
- Closing is intentionally blocked during execution instead of forcefully
  terminating the worker process.
