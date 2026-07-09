# Sprint 10-2 Update Package

## 목표

Product Development Pipeline MVP를 추가합니다.

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
python "C:\AIFactory\AI Factory OS\main.py" product list
python "C:\AIFactory\AI Factory OS\main.py" product run-dev --title "테스트 개발 작업" --request "Blog Growth Analyzer 개발 파이프라인 테스트"
python "C:\AIFactory\AI Factory OS\main.py" product status
```
