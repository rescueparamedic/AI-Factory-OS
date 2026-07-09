# AI Factory OS v1.2.1 Release Notes

## Release Type

Development Engine + Package Builder Validation MVP

## 핵심 추가 기능

- Development Engine 추가
- Planning Engine의 handoff 기반 개발 산출물 생성
- `dev run`, `dev latest`, `dev list` 명령 추가
- 개발 산출물 draft 생성
- diff plan JSON 생성
- Development Report 생성
- 기본 dry_run 안전 모드 적용
- Package Builder validation 추가
- `package validate --path ZIP경로` 명령 추가

## 안전 정책

v1.2.1 MVP에서는 기존 프로젝트 파일을 직접 수정하지 않습니다.

실제 파일 반영은 향후 Approval Gate 이후에만 허용합니다.
