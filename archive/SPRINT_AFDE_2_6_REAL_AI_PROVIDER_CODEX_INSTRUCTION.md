# SPRINT AFDE-2.6 REAL AI PROVIDER — CODEX INSTRUCTION

## 0. 작업 목적

AFDE-2.5에서 구현된 Real AI Worker Runtime을 유지하면서 실제 OpenAI Provider를 추가한다.

최종 목표:

```text
User Request
→ Factory Runtime
→ OpenAI Provider
→ 실제 GPT API 호출
→ Planning Worker
→ Development Worker
→ QA Worker
→ Documentation Worker
→ 결과 및 Artifact 생성
```

Mock Provider는 반드시 유지한다.

---

## 1. 현재 기준

- Repository: `AI-Factory-OS`
- Base branch: `develop`
- Working branch: `feature/afde-2.6-real-ai-provider`
- AFDE-2.4 Sprint Auto Runner 완료
- AFDE-2.5 Real AI Worker Runtime 완료
- AFDE-2.5 기준 전체 테스트: `217 passed`
- AFDE-2.5 Runtime 집중 테스트: `53 passed`
- `compileall` PASS
- secret scan PASS
- PR #5가 `develop`에 병합된 상태를 기준으로 한다.

---

## 2. 절대 원칙

1. 기존 AFDE-2.5 구현을 불필요하게 재작성하지 않는다.
2. Mock Provider를 삭제하거나 기본 테스트 경로에서 깨뜨리지 않는다.
3. OpenAI Provider는 기존 Provider Bridge / Registry 구조에 맞춰 확장한다.
4. 실제 API Key를 코드, 테스트, 로그, 문서, fixture, snapshot에 저장하지 않는다.
5. API Key는 환경변수로만 읽는다.
6. main/master/develop에 직접 push하지 않는다.
7. 강제 push, reset --hard, 대량 삭제, 보안 완화, 실제 배포를 하지 않는다.
8. `AFDE_2_2_UPDATE_PACKAGE/` 폴더는 작업 대상에서 제외한다.
9. 외부 API 호출 테스트는 명시적으로 opt-in 된 경우에만 수행한다.
10. 네트워크/API Key가 없어도 전체 테스트가 통과해야 한다.

---

## 3. 구현 범위

### 3.1 OpenAI Provider

기존 Provider 인터페이스와 호환되는 OpenAI Provider를 추가한다.

필수 요구사항:

- 환경변수 기반 인증
- 명시적인 model 설정
- timeout 설정
- retry 가능한 오류와 retry 불가능 오류 구분
- API 응답을 내부 표준 응답 형식으로 정규화
- usage 정보가 있으면 기록
- provider/model/request_id 메타데이터 기록
- 비밀값 마스킹
- 외부 호출 실패 시 구조화된 예외 반환
- 기존 Runtime revision loop와 호환

권장 환경변수:

```text
OPENAI_API_KEY
AI_FACTORY_OPENAI_MODEL
AI_FACTORY_OPENAI_TIMEOUT_SECONDS
AI_FACTORY_OPENAI_MAX_RETRIES
```

기본 모델은 프로젝트 현재 의존성과 공식 SDK가 지원하는 범위에서 비용과 속도가 합리적인 모델로 설정하되, 환경변수로 변경 가능하게 한다.

### 3.2 Provider Registry / Factory 연동

- `mock` provider 유지
- `openai` provider 등록
- 문자열 또는 config로 provider 선택 가능
- 미지원 provider는 명확한 오류
- API Key가 없을 때 import 단계에서 실패하지 않음
- OpenAI SDK가 설치되지 않은 환경에서도 Mock 경로는 정상 동작

### 3.3 Runtime 연동

기존 Real AI Worker Runtime의 다음 흐름을 재사용한다.

```text
PM
→ Planning
→ Development
→ QA
→ Documentation
```

각 Worker가 OpenAI Provider를 사용할 수 있어야 한다.

필수:

- Worker별 system instruction 유지
- 이전 Worker output을 다음 Worker context로 전달
- message/event stream 유지
- artifact 저장 유지
- revision loop 유지
- terminal dashboard 유지
- provider 메타데이터와 오류 이벤트 기록

### 3.4 설정 및 CLI

기존 CLI 스타일을 재사용한다.

필요 기능:

- provider 선택: mock/openai
- model 선택
- 실제 API 호출을 명시적으로 허용하는 플래그 또는 설정
- API Key 누락 시 친절한 오류
- Mock demo 기존 동작 유지
- OpenAI demo 실행 경로 추가

예시 형태:

```powershell
python -m <existing_cli_module> run `
  --provider openai `
  --model <model-name> `
  --request "Create a small Python utility"
```

실제 모듈명과 옵션명은 현재 코드 구조를 확인한 뒤 기존 패턴과 일관되게 결정한다.

---

## 4. 보안 요구사항

다음을 반드시 검증한다.

- API Key를 출력하지 않는다.
- 예외 메시지에 Authorization header가 포함되지 않는다.
- request dump에 secret이 포함되지 않는다.
- `.env`는 commit하지 않는다.
- `.env.example`에는 placeholder만 둔다.
- 로그에는 masked 형태만 허용한다.
- secret scan 테스트를 추가하거나 기존 scan 범위를 확장한다.
- 사용자 prompt와 결과 artifact 저장 위치는 기존 정책을 따른다.

---

## 5. 테스트 요구사항

네트워크 없이 실행 가능한 단위 테스트를 우선한다.

### 필수 테스트

1. OpenAI Provider config 로딩
2. API Key 누락 오류
3. Provider Registry에서 `openai` 선택
4. Mock Provider 회귀 테스트
5. SDK client mock을 사용한 정상 응답 정규화
6. timeout 오류 처리
7. rate limit 오류 처리
8. authentication 오류 처리
9. malformed response 처리
10. usage metadata 처리
11. secret masking
12. Runtime + OpenAI Provider 통합 테스트
13. Worker lifecycle 유지
14. revision loop 유지
15. artifact 생성 유지
16. CLI provider 선택
17. 실제 API 호출 opt-in 보호
18. OpenAI SDK 미설치 시 Mock 경로 정상 동작

실제 API 통합 테스트는 다음 조건을 모두 만족할 때만 실행한다.

```text
OPENAI_API_KEY 존재
AND
명시적 live-test 환경변수 또는 CLI 플래그 존재
```

예:

```text
AI_FACTORY_RUN_LIVE_OPENAI_TESTS=1
```

기본 `pytest`에서는 실제 API를 호출하지 않는다.

---

## 6. 문서 요구사항

다음을 현재 프로젝트 문서 구조에 맞춰 업데이트한다.

- OpenAI Provider 설정 방법
- 환경변수 목록
- Mock Provider 실행법
- OpenAI Provider 실행법
- 비용 발생 경고
- 실제 API 테스트 opt-in 방법
- 오류 해결 방법
- 보안 주의사항
- AFDE-2.6 Sprint 결과

기존 문서를 중복 생성하지 말고 적절한 README/CHANGELOG/Sprint 문서를 수정한다.

---

## 7. 구현 순서

1. 프로젝트 기준 문서와 AFDE-2.5 코드 구조 확인
2. Provider 인터페이스/Registry/Bridge 확인
3. 변경 설계 요약
4. OpenAI Provider 최소 구현
5. Registry 및 Runtime 연결
6. CLI/config 연결
7. 단위 테스트 작성
8. 통합 테스트 작성
9. 문서 업데이트
10. 전체 테스트
11. compileall
12. secret scan
13. git diff 검토
14. 완료 보고

안전한 파일 읽기, 코드 수정, 테스트, compileall, diff 확인은 중단 없이 진행한다.

다음 상황만 사용자에게 질문한다.

- 기존 핵심 아키텍처를 변경해야 하는 경우
- develop/main 직접 변경이 필요한 경우
- 실제 API Key가 필요한 live test
- 유료 API 호출
- 위험한 삭제
- 강제 push
- 보안 정책 완화
- BLOCKED / ASK_USER / DENY 판정

---

## 8. 완료 기준

아래 조건을 모두 충족해야 완료다.

- Mock Provider 기존 동작 유지
- OpenAI Provider 구현 완료
- Provider Registry 연결 완료
- Runtime Worker lifecycle 연결 완료
- 기본 테스트에서 외부 API 호출 없음
- 전체 pytest PASS
- compileall PASS
- secret scan PASS
- 실제 API Key 미포함
- 문서 업데이트 완료
- 변경사항이 feature branch에만 존재
- 실제 OpenAI Demo 실행 직전 상태까지 준비

---

## 9. 완료 보고 형식

작업 완료 후 아래 형식으로만 명확히 보고한다.

```text
[완료된 작업]
- ...

[수정/생성 파일]
- ...

[테스트 결과]
- 전체 pytest:
- 집중 테스트:
- compileall:
- secret scan:

[현재 상태]
- ...

[실제 OpenAI 테스트 전 사용자 행동]
1. ...
2. ...

[위험/승인 필요 항목]
- 없음 / 상세 내용

[다음 단계]
- ...
```

커밋, push, PR 생성은 사용자가 명시적으로 요청하기 전까지 수행하지 않는다.
