# AI Factory OS v1.6 Release Notes

## Release Type

Pipeline Orchestrator MVP

## 핵심 추가 기능

- Pipeline Orchestrator 추가
- `pipeline run` 명령 추가
- `pipeline latest` 명령 추가
- `pipeline list` 명령 추가
- 사용자 요청 하나로 Planning → Development → QA → Documentation → Approval Queue 자동 실행
- Pipeline Report 생성
- Pipeline Run JSON 저장

## 확인 명령

```powershell
python main.py pipeline run --request "블로그 작성기에 Gemini 검수 기능 추가"
python main.py pipeline latest
python main.py approve latest
```
