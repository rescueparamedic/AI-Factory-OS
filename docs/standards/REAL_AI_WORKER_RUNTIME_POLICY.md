# Real AI Worker Runtime Policy

- Mock is deterministic, default, and network-free.
- Real providers require explicit selection and configuration; no silent fallback.
- Five workers persist redacted messages, events, and results.
- Runtime validation reuses Sprint Auto Runner and Approval Guardian.
- QA revisions default to one and are capped at three.
- Generated sessions stay under ignored `data/runtime_sessions/`.
