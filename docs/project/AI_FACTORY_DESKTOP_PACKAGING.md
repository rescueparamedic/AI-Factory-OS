# AI Factory Desktop Windows Packaging

## Build

AI Factory Desktop uses PyInstaller 6.21.0 with PySide6 6.11.1 in
windowed onedir mode. From a Windows checkout with Python 3.13:

```powershell
python -m pip install -r requirements-packaging.txt
.\scripts\build_desktop_exe.ps1
```

The build script removes only the repository-local `build` and `dist`
directories after validating their resolved paths. It builds the committed
`packaging/ai_factory_desktop.spec` and verifies:

```text
dist\AI Factory Desktop\AI Factory Desktop.exe
```

The complete `AI Factory Desktop` directory is the distributable application.
Copying only the EXE is unsupported because onedir dependencies remain beside
it.

## Packaging Architecture

The GUI uses the Windows GUI subsystem with `console=False`. PyInstaller
maintained PySide6 hooks collect the Qt libraries and platform plugins. The
spec has no bundled data files and includes only `afde.cli` as the explicit
hidden import needed by the frozen execution boundary.

Source mode continues to invoke `python -m afde.cli`. Frozen mode invokes the
same `afde.cli.main(argv)` JSON and exit-code contract inside the existing
Desktop worker thread because the packaged executable is not a Python
interpreter. Runtime lifecycle and public CLI behavior are unchanged.
Workspace and Evidence data remain in the operator-selected external
workspace.

No official `.ico` resource exists in the repository, so this MVP uses the
default PyInstaller icon.

## Local Validation

- Local Windows build: **PASS**
- Generated EXE: 10,319,008 bytes
- Generated onedir bundle: 231 files, 145,481,600 bytes
- PE subsystem: Windows GUI
- Desktop window launch and handle: **PASS**
- Normal WM_CLOSE and exit code 0: **PASS**
- Orphan packaged processes after exit: 0
- Full pytest: 705 passed, 2 skipped
- OpenAI live calls: 0
- Compileall, pip check, and diff integrity: **PASS**
- Workspace input, Goal input, packaged Mock execution, Evidence display, and
  Open Evidence interaction: **MANUAL VALIDATION REQUIRED**
- Clean Windows PC validation: **NOT YET VERIFIED**

The build emitted an optional `tzdata` hidden-import discovery warning. No
`tzdata` entry was recorded in the generated PyInstaller warning file, and
the packaged GUI launch and normal exit validation passed.

## CI And Distribution Boundary

The `Windows Desktop Package` pull-request workflow is prepared to run focused
tests, build the onedir folder, and retain the
`AI-Factory-Desktop-Windows` artifact for seven days. Its first GitHub-hosted
run is pending PR creation.

The executable is unsigned, so Windows SmartScreen or antivirus warnings are
possible. This Sprint does not provide an installer, automatic updates, code
signing, Microsoft Store packaging, GitHub Release publication, external
deployment, onefile packaging, or macOS/Linux packages.

No `.env`, credential, API key, Runtime session, workspace, or persisted
Evidence data is intentionally bundled.
