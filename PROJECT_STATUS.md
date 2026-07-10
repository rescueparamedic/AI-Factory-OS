# AI Factory OS Project Status

## AFDE-2.4

- Sprint Auto Runner implemented on a feature branch.
- Every Runner command is evaluated by Approval Guardian v2.
- ASK_USER state is resumable only with matching definition and context.
- Direct pushes to protected branches remain forbidden and merge remains a
  user-controlled operation.

## AFDE-2.3

- Approval Guardian v2 implemented on a feature branch.
- Command decisions use `AUTO_APPROVE`, `ASK_USER`, and `DENY` with fail-closed
  and deny-overrides behavior.
- Existing release approval workflows remain backward compatible.
- Central enforcement across every worker executor remains planned work.

## 현재 상태

| 항목 | 내용 |
|---|---|
| Version | v1.0.0 |
| 상태 | Baseline Frozen |
| 목적 | AI 개발회사 워크플로우 구현 전 안정 기준점 |
| 기준 | OS Core / Agent / Team / Worker / Update / Repository 기반 완료 |

## 완료

- OS Core MVP
- Task Engine
- Workflow Engine
- Agent / Team Architecture
- Worker Standard
- Update Manager
- Project Doctor
- CLI Modularization
- Product Development Pipeline MVP
- Repository Mode

## 다음 목표

AI Factory v1.1 Planning Agent 실작동 구현
