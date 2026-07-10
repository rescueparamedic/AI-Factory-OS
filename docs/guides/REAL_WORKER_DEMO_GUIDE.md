# Real Worker Demo Guide

```powershell
python -m afde.cli factory-demo --request "Analyze a small feature and produce a plan and test result" --provider mock
```

Use `--no-live` for compact output or `--json` for automation. Mock mode needs no API key and performs no network call. Results are under `data/runtime_sessions/<session_id>/`.

```powershell
python -m afde.cli factory-demo --request "Show Guardian decisions" --provider mock --include-approval-demo --no-live
```

Real providers never fall back silently; unsupported providers fail before any paid call.
