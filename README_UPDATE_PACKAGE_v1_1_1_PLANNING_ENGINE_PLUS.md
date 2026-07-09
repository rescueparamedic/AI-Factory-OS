# AI Factory OS v1.1.1 Planning Engine Plus Update Package

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
python "C:\AIFactory\AI Factory OS\main.py" plan create --request "블로그 작성기에 Gemini 검수 기능 추가"
python "C:\AIFactory\AI Factory OS\main.py" plan latest
python "C:\AIFactory\AI Factory OS\main.py" plan show
```
