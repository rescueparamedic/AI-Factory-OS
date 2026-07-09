# AI Factory OS v1.4 Documentation Engine Update Package

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

## 설치 후 확인

```powershell
python "C:\AIFactory\AI Factory OS\main.py" version
python "C:\AIFactory\AI Factory OS\main.py" docs run
python "C:\AIFactory\AI Factory OS\main.py" docs latest
python "C:\AIFactory\AI Factory OS\main.py" docs list
```
