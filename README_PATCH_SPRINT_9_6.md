# Sprint 9-6 PATCH 적용 안내

## 적용 위치

아래 폴더에 압축 해제해서 덮어쓰기합니다.

```text
C:\AIFactory\AI Factory OS
```

## 신규 명령어

```powershell
python "C:\AIFactory\AI Factory OS\main.py" version
python "C:\AIFactory\AI Factory OS\main.py" doctor
python "C:\AIFactory\AI Factory OS\main.py" update backup
python "C:\AIFactory\AI Factory OS\main.py" update check
```

## 권장 적용 순서

1. 패치 압축 해제
2. version 확인
3. doctor 실행
4. update check 실행
5. update backup 실행

## 주의

Sprint 9-6에서는 안전을 위해 실제 자동 patch install은 비활성화되어 있습니다.
자동 patch install은 Sprint 9-7에서 활성화 예정입니다.
