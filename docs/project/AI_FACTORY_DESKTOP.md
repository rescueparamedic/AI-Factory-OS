# AI Factory Desktop MVP

## Purpose

AI Factory Desktop is the minimum Windows GUI over the existing AI Factory OS
Beta execution path. It lets an operator select one project directory, enter a
natural-language goal, run the deterministic Mock Provider, review status and
log output, and open the persisted `execution_evidence.json` file.

The product label is **AI Factory Desktop — Powered by AI Factory OS**.

## Install And Run

PySide6 is optional so CLI-only installations do not receive the Qt runtime.

```powershell
python -m pip install -r requirements-desktop.txt
python -m afde.desktop
```

The initial release is launched with Python on Windows. A PyInstaller build and
Windows installer are future packaging work, not AFDE-4.3A deliverables. The
independent `afde.desktop` module entry point is the future packaging boundary.

## Execution Architecture

```text
DesktopMainWindow
  -> QThread DesktopExecutionWorker
  -> DesktopExecutionService
  -> python -m afde.cli execute --provider mock --json
  -> existing Beta Runtime and execution_evidence.json
```

The UI collects input and renders state only. The Qt-independent application
service validates inputs, constructs the fixed Mock command, disables live
OpenAI environment opt-in, parses the existing JSON/exit-code contract, and
resolves Evidence inside the selected workspace. Runtime logic is not copied.

Execution runs outside the main UI thread. While it is active, Run, Browse,
workspace, request, and Open Evidence controls are disabled and the progress
bar is indeterminate. Closing the window is blocked until execution finishes,
which avoids abandoning an orphan subprocess.

## Supported Flow

1. Select Browse or enter an existing Project Workspace.
2. Enter a non-empty bounded goal.
3. Select Run.
4. Review Validating, Running, Completed, or Failed status and log lines.
5. On success, review Session ID, Provider, execution mode, exit code, and the
   absolute Evidence path.
6. Select Open Evidence to use the Windows default JSON file application.

Errors use `Status`, `Error`, `Cause`, and `Next` log fields. Missing workspace,
empty request, Python/CLI startup, nonzero exit, malformed JSON, missing session
identity, unsafe or missing Evidence, and internal worker failures are handled
without terminating the GUI event loop.

## Current Scope And Limitations

- Mock Provider only; there is no Provider selection UI or external API call.
- Python launch only; there is no EXE, installer, updater, or system tray.
- No Approval workflow, Codex execution, Git/GitHub action, dashboard, session
  browser, history viewer, settings, themes, graph, or plugin system.
- Runtime output is persisted by the existing Beta contract under the selected
  workspace. Operators remain responsible for their workspace ignore policy.
- Closing is intentionally blocked during execution instead of forcefully
  terminating the worker process.
