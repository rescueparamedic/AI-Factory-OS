# AI Factory OS v1.1.1 Release Notes

## Release Type

Planning Engine Plus

## 개선 내용

- `plan latest` 명령 추가
- `plan show`에서 PLAN-ID 생략 시 최신 계획 표시
- 예상 수정 파일 목록 생성
- 예상 개발 시간 및 난이도 추정
- Regression 필요 여부 판단
- Development Engine용 Handoff JSON 생성

## 확인 명령

```powershell
python main.py plan create --request "블로그 작성기에 Gemini 검수 기능 추가"
python main.py plan latest
python main.py plan show
```
