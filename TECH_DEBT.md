# Technical Debt

## AFDE-2.7 Approval Resume

- Atomic local JSON does not yet provide multi-process approval locking.
- Approval pause inside the optional QA revision sub-loop is out of scope.
- Approved writes have no automatic rollback; evidence supports manual Git
  restoration after forensic preservation.
- Remote approval UI and identity attestation remain future work.

## Approval Guardian v2

- Command classification is text-based. Shell syntax differs between Windows,
  POSIX shells, and tool-specific parsers; structured tool permissions should
  eventually replace text inference at execution boundaries.
- Existing subprocess and worker execution paths are not yet centrally routed
  through Guardian. Sprint AFDE-2.3 provides the stable policy API, CLI path,
  and adapter, but executor-by-executor enforcement remains future work.
- Symlink and junction containment depends on host filesystem resolution and
  should receive platform-specific integration coverage.
- Protected branches currently default to `main` and `master`; repository-host
  branch protection discovery is intentionally not fetched automatically.
- Audit files are local JSON records without locking, rotation, or a tamper-
  evident append-only store.

## Sprint Auto Runner

- Central interception for every legacy executor remains future work; the new
  Runner path is mandatory-Guardian but does not replace all existing engines.
- JSON state should migrate to SQLite with transaction and schema migration
  support before concurrent production use.
- Concurrent Runner locking and duplicate-run prevention are not implemented.
- JSONL audit needs a tamper-evident hash chain, rotation, and retention policy.
- Cross-platform shell parsing needs a structured-command replacement.
- GitHub PR creation is not yet a first-class structured adapter.
- Approval UI/dashboard integration remains future work.

## Real AI Worker Runtime

- Real LLM evaluation, parallel workers, centralized interception, SQLite,
  web/WebSocket UI, locks, cost tracking, sandboxing, and multi-step revision
  remain future work.
