# Sprint AFDE-2 Test Guide

## Apply

Copy everything inside `patch/` into:

```text
C:\AIFactory\AI Factory OS\
```

Overwrite files when asked.

## Test

```powershell
cd "C:\AIFactory\AI Factory OS"
git branch --show-current
python -m afde.cli env-check
python -m afde.cli bootstrap-worker
python -m pytest tests/test_afde.py tests/test_afde_environment.py
```

## Expected

- Branch should be `develop`
- `env-check` should return JSON checks
- `bootstrap-worker` should create config/report paths
- pytest should pass

## Commit

```powershell
git add .
git commit -m "Sprint-AFDE-2 environment checker and worker bootstrap"
git push
```
