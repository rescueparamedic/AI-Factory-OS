# AFDE-4.0.1 Beta Runtime Hardening Release Evidence

## Release Identity

- Project: AI Factory OS
- Sprint: AFDE-4.0.1 Beta Runtime Hardening
- Baseline branch: develop
- Baseline SHA: 1de822af27701e74313981bbed1837d6ab09649c
- Feature branch: feature/afde-4.0.1-beta-runtime-hardening
- Release stage: pull request candidate
- Commit SHA: PENDING FINAL COMMIT
- Pull request: PENDING CREATION
- Merge status: NOT MERGED

## Sprint Objective

Harden existing Runtime and CLI behavior for Beta operators by making expected
failures, causes, recovery actions, evidence locations, identifiers, and exit
codes explicit without adding product functionality or changing Runtime state
transitions and public APIs.

## Implemented Scope

- Added a bounded CLI error boundary for existing Runtime status, report,
  cancel, history, events, export, Dashboard, and approval commands.
- Added structured human and JSON failure fields: Status, Error, Cause, Next
  action, Evidence, and Session ID where applicable.
- Added actionable recovery commands that already exist in `afde.cli`.
- Added additive `--workspace` support to runtime status, report, and cancel;
  the current-directory default remains unchanged.
- Preserved official Beta execution codes and added Cause/Next action guidance
  to failed `execute` output.
- Added focused network-free regression tests for exit codes and message fields.

## Exit Code Contract

| Code | Meaning and scope |
| --- | --- |
| 0 | Successful Runtime, Operator, or official Beta operation |
| 2 | Invalid input/configuration or invalid state-dependent request |
| 3 | Existing Operator preflight block |
| 4 | Existing session/approval not-found outcome |
| 5 | Runtime/Provider execution or persisted Runtime-data failure |
| 7 | Existing official Beta evidence-persistence failure |

## Changed Files

- `afde/cli.py`: expected Runtime error rendering, guidance, exit results, and
  additive workspace arguments.
- `tests/test_runtime_cli_hardening.py`: focused success and failure contracts.
- `CHANGELOG.md`: AFDE-4.0.1 hardening entry.
- `docs/operations/AFDE_OPERATOR_QUICKSTART.md`: operator-visible fields,
  recovery guidance, and exit codes.
- `docs/releases/AFDE_4_0_1_RELEASE_EVIDENCE.md`: this release evidence.

## Validation Evidence

| Validation | Result |
| --- | --- |
| Targeted Runtime/CLI regression | PASS: 42 passed |
| Dashboard compatibility regression | PASS: 47 passed |
| Full `python -m pytest` | PASS: 654 passed, 2 skipped |
| `python -m compileall -q .` | PASS: exit 0 |
| `git diff --check` | PASS: exit 0 |
| Network-free CLI smoke | PASS: Mock execute 0, missing session 4, invalid request 2 |

All automated tests use local Mock/fake/fixture paths. No paid Provider or
external network call is required or authorized by this sprint.

The full compileall command reported that it could not list existing
access-restricted cache and historical temporary directories, including
`.pytest_cache`, `.test-tmp`, and prior `sprint2-*.tmp` paths. It returned exit
code 0 and reported no Python source compilation failure.

## Compatibility and Non-Goals

- Existing Runtime state transitions, provider execution, approval policy,
  persistence formats, and public Runtime APIs are unchanged.
- Existing command names and successful output payloads remain available.
- `--workspace` is additive and defaults to the previous current directory.
- No new product feature, provider, abstraction framework, UI, dependency,
  autonomous behavior, deployment, release, or approval bypass was added.
- Expected exceptions are caught narrowly; unexpected internal exceptions and
  their traceback remain available for debugging.

## Known Limitations

- Legacy `main.py runtime` remains a separate older CLI surface; AFDE-4.0 Beta
  hardening targets the supported `python -m afde.cli` Runtime/operator path.
- Human and JSON success payloads retain their command-specific historical
  formats; the standardized fields are guaranteed on expected failure paths.
- Web Dashboard startup errors are bounded, but failures occurring inside the
  long-running HTTP serving loop retain the server's existing behavior.

## Pull Request and Rollback

- Base / head: `develop` / `feature/afde-4.0.1-beta-runtime-hardening`
- Pull request status: PENDING CREATION
- Merge status: NOT MERGED
- Rollback: revert the feature-branch commit; no data migration or dependency
  rollback is required.
