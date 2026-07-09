# Sprint 9-9 Update Package

## 적용 방식

이번부터는 압축을 풀지 않습니다.

1. 이 ZIP 파일을 아래 폴더에 넣습니다.

```text
C:\AIFactory\AI Factory OS\updates
```

2. PowerShell에서 실행합니다.

```powershell
python "C:\AIFactory\AI Factory OS\main.py" update preview
python "C:\AIFactory\AI Factory OS\main.py" update install
```

3. 설치 여부 질문이 나오면 `Y`를 입력합니다.

자동 승인하려면:

```powershell
python "C:\AIFactory\AI Factory OS\main.py" update install --yes
```

## 설치 후 확인

```powershell
python "C:\AIFactory\AI Factory OS\main.py"
python "C:\AIFactory\AI Factory OS\main.py" version
python "C:\AIFactory\AI Factory OS\main.py" update history
```
