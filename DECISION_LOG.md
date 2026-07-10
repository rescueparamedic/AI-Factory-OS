# Decision Log

## 2026-07-11 — Approval Guardian v2

- Adopted three decisions: `AUTO_APPROVE`, `ASK_USER`, and `DENY`.
- Adopted fail-closed classification with deny-overrides precedence.
- Allowed verified low-risk actions only within feature-branch workflows.
- Kept the existing release `ApprovalGate` unchanged and added Guardian as a
  command-policy layer.
- Reused the existing JSON audit directory with command redaction and
  fingerprinting.
- Kept Safe Approval Policy v1 compatibility behind `ExecPolicyAdapter`; the
  v1 policy itself is not duplicated because it is not yet on `develop`.

## 2026-07-11 — Sprint Auto Runner

- Adopted a persisted Sprint state machine with mandatory Guardian evaluation
  before every process execution.
- Limited automatic progress to AUTO_APPROVE decisions in verified feature
  workflows; ASK_USER persists and stops, while DENY permanently blocks.
- Explicitly denied direct push to `main`, `master`, and `develop` in the Runner.
- Kept merge as a user-approved operation and excluded automatic merge.
- Chose additive integration instead of replacing all legacy executors.

## 2026-07-11 — Real AI Worker Runtime MVP

- Prioritized an executable deterministic mock Demo.
- Reused Runner/Guardian and prohibited silent real-provider fallback.
