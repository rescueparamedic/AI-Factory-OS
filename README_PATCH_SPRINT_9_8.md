# Sprint 9-8 PATCH 적용 안내

## 적용 위치

이번 패치는 마지막 수동 적용 패치로 아래 폴더에 압축 해제해서 덮어쓰기합니다.

```text
C:\AIFactory\AI Factory OS
```

## 신규/개선 명령어

```powershell
python "C:\AIFactory\AI Factory OS\main.py" update find
python "C:\AIFactory\AI Factory OS\main.py" update install
```

## 다음 Sprint부터 적용 방식

1. 패치 ZIP을 다운로드
2. 아래 폴더에 넣기

```text
C:\AIFactory\AI Factory OS\updates
```

3. 명령어 실행

```powershell
python "C:\AIFactory\AI Factory OS\main.py" update install
```

그러면 최신 패치 자동 검색 → 백업 → 설치 → 이력 기록이 진행됩니다.
