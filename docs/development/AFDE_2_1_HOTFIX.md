# AFDE-2.1 Hotfix

## Purpose
Fix AFDE-2 package mismatch by adding the missing CLI commands and tests.

## Added Commands

```powershell
python -m afde.cli env-check
python -m afde.cli bootstrap-worker
```

## Validation

```powershell
python -m pytest tests/test_afde.py tests/test_afde_environment.py
```
