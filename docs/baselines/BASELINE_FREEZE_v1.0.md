# AI Factory OS v1.0 Baseline Freeze

## Freeze 선언

이 문서는 AI Factory OS v1.0 기준점을 고정하기 위한 문서입니다.

## 기준점 의미

v1.0은 다음을 의미합니다.

- OS Core 기반 완성
- Agent / Team / Worker 구조 검증 완료
- Update Manager 기반 검증 완료
- Product Pipeline MVP 검증 완료
- Repository Mode 추가 완료

## v1.0 이후 변경 원칙

v1.0 이후 변경은 다음 원칙을 따릅니다.

1. main 브랜치는 항상 실행 가능한 안정 버전으로 유지한다.
2. 기능 개발은 develop 또는 feature 브랜치에서 진행한다.
3. 사용자 승인 전 Release 확정은 하지 않는다.
4. Update Package는 patch_manifest.json을 포함한다.
5. 모든 주요 변경은 Audit / Update History / Release Note에 남긴다.
6. 위험 작업은 Approval Gate를 거쳐야 한다.

## 되돌림 기준

문제가 발생하면 v1.0 Baseline으로 되돌릴 수 있어야 합니다.

권장 복구 순서:

```powershell
python main.py update rollback
python main.py doctor
python main.py version
```

## 다음 단계

AI Factory OS v1.0 이후의 핵심 목표는 AI 개발회사 워크플로우 구현입니다.

```text
User Request
↓
CEO Agent
↓
PM Agent
↓
Planning Agent
↓
Development Agent
↓
QA Agent
↓
Documentation Agent
↓
Approval Gate
↓
Release
```
