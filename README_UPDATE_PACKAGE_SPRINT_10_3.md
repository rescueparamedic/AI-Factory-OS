# Sprint 10-3 Update Package

## 목표

AI Factory OS를 정식 GitHub 저장소로 운영하기 위한 Repository Mode를 추가합니다.

## 적용 방식

ZIP을 풀지 말고 아래 폴더에 넣습니다.

```text
C:\AIFactory\AI Factory OS\updates
```

그다음 실행합니다.

```powershell
python "C:\AIFactory\AI Factory OS\main.py" update preview
python "C:\AIFactory\AI Factory OS\main.py" update install
```

또는 자동 승인:

```powershell
python "C:\AIFactory\AI Factory OS\main.py" update install --yes
```

## 설치 후 확인

```powershell
python "C:\AIFactory\AI Factory OS\main.py"
python "C:\AIFactory\AI Factory OS\main.py" repo status
python "C:\AIFactory\AI Factory OS\main.py" repo guide
python "C:\AIFactory\AI Factory OS\main.py" repo snapshot
```
