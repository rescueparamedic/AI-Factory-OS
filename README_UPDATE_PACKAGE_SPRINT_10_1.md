# Sprint 10-1 Update Package

## 목표

main.py 비대화 방지를 위해 CLI 명령을 `cli/` 패키지로 분리합니다.

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
python "C:\AIFactory\AI Factory OS\main.py" version
python "C:\AIFactory\AI Factory OS\main.py" task list
python "C:\AIFactory\AI Factory OS\main.py" update history
```
