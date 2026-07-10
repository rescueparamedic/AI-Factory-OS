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
