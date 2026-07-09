# Sprint 9-4 PATCH 적용 안내

이 패치는 기존 `C:\AIFactory\AI Factory OS` 폴더에 직접 압축 해제해서 덮어쓰기합니다.

## 적용 위치

```text
C:\AIFactory\AI Factory OS
```

압축 안의 `main.py`, `agents`, `teams`, `managers`, `os_core`가 위 폴더 바로 아래에 들어가야 합니다.

## 적용 후 확인 명령어

```powershell
python "C:\AIFactory\AI Factory OS\main.py"
python "C:\AIFactory\AI Factory OS\main.py" agent list
python "C:\AIFactory\AI Factory OS\main.py" agent teams
```

정상 출력에는 다음 문구가 포함됩니다.

```text
=== AI Factory OS / Sprint 9-4 ===
CEO decision     : approved_for_pm_planning
```
