# AFDE-2.3 Test Report

## Baseline

- Full pytest before implementation: 14 passed
- AFDE env-check: PASS
- AFDE providers: PASS
- AFDE run-mock: success

## Guardian validation

- Policy, chain, context, audit, and integration tests: 86 focused cases
- Parameterized policy cases: more than 50
- Required safe, prompt, deny, wrapper, chained-command, external-path, and
  production-context cases are covered.

## Security checks

- Destructive Git commands remain denied.
- Root, home, and repository-wide recursive deletion is denied.
- Protected branch deletion and force push are denied.
- Plaintext credential-file reads and credential transfer are denied.
- Audit output redacts sensitive commands and retains only a fingerprint.
- Unknown or malformed commands are never auto-approved.

## Final regression

- Full pytest after implementation: 100 passed
- AFDE env-check: PASS
- AFDE providers: PASS
- AFDE run-mock: success
- Guardian CLI: AUTO_APPROVE, ASK_USER, and DENY paths verified
