# AFDE-2.2 Update Package

## 적용 방법

1. 이 ZIP을 `C:\AIFactory\AI Factory OS` 폴더에 압축 해제합니다.
2. 생성된 `AFDE_2_2_UPDATE_PACKAGE` 폴더를 엽니다.
3. `APPLY_UPDATE.ps1`을 마우스 오른쪽 버튼으로 PowerShell에서 실행합니다.
4. 프로젝트 루트 PowerShell에서 아래 명령을 실행합니다.

```powershell
python -m pytest -q
python -m afde.cli providers
python -m afde.cli env-check
python -m afde.cli bootstrap-worker
python -m afde.cli run-mock --title "AFDE-2.2 validation" --request "CLI runtime regression test"
```

## 수정 파일

- `afde/task_runner.py`
- `afde/cli.py`
- `tests/test_afde_cli_runtime.py`
