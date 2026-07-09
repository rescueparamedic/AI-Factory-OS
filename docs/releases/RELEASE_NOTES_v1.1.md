# AI Factory OS v1.1 Release Notes

## Release Type

Planning Engine MVP

## 핵심 추가 기능

- Planning Engine 추가
- 사용자 자연어 요청 → 구조화된 개발 계획 JSON 생성
- 요구사항 추출
- Task 자동 분해
- 리스크 분석
- 승인 필요 여부 판단
- Agent 배정
- Planning Report Markdown 생성
- Audit Log 기록

## 신규 명령어

```powershell
python main.py plan create --request "요청 내용"
python main.py plan list
python main.py plan show PLAN-ID
```

## 다음 단계

v1.2 Development Engine에서 Planning 결과를 기반으로 실제 코드 생성/수정 작업으로 연결합니다.
