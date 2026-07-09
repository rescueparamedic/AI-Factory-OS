# Sprint 9-7 PATCH 적용 안내

## 적용 위치

이번 패치는 아직 수동으로 아래 폴더에 압축 해제해서 덮어쓰기합니다.

```text
C:\AIFactory\AI Factory OS
```

## 신규 명령어

```powershell
python "C:\AIFactory\AI Factory OS\main.py" update install "패치ZIP경로"
python "C:\AIFactory\AI Factory OS\main.py" update rollback
python "C:\AIFactory\AI Factory OS\main.py" update history
```

## Sprint 9-7 이후 변경점

다음 Sprint부터는 패치 ZIP을 수동 압축해제하지 않고 아래 명령으로 적용할 수 있습니다.

```powershell
python "C:\AIFactory\AI Factory OS\main.py" update install "C:\다운로드경로\AI_Factory_OS_Sprint_9_8_PATCH.zip"
```

## 주의

rollback은 가장 최근 백업을 기준으로 복원합니다.
중요한 작업 전에는 반드시 `update backup`을 먼저 실행하는 것을 권장합니다.
