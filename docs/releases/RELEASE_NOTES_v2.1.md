# AI Factory OS v2.1 Release Notes

## Release Type
Real Worker Foundation MVP

## 핵심 추가 기능
- AI Provider Registry 추가
- `runtime providers` 명령 추가
- OPENAI_API_KEY / GEMINI_API_KEY 환경변수 감지
- Worker Runtime provider-aware 실행
- API Key가 없으면 local_safe_mode fallback

## 목적
실제 AI Worker 호출 전 단계로, 안전한 Provider 감지/선택 구조를 만든다.
