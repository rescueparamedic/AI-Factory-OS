# AFDE Operator Workflow Quickstart

AFDE-3.10 provides a thin, guided CLI journey over the existing Runtime,
Provider, Approval Guardian, Controlled Execution, History, and Dashboard
components. Mock mode is deterministic and network-free. It naturally pauses
at the existing-file replacement policy boundary and never bypasses approval.

## Environment preparation

Open PowerShell in an AI Factory OS checkout. Use a feature branch or a
disposable checkout because the deterministic mock flow intentionally proposes
replacing the existing approval fixture.

```powershell
Set-Location "C:\AIFactory\AI Factory OS"
python --version
git status --short --branch
```

No new dependency is required. Operator commands accept `--workspace` when the
governed repository differs from the current directory.

## Mock preflight and first run

```powershell
python -m afde.cli operator-preflight --provider mock --workspace .
python -m afde.cli operator-run --request "Create the deterministic operator workflow proof" --provider mock --workspace .
```

Preflight is read-only. A dirty repository is reported as `WARN`, while a
missing workspace or repository, unavailable provider, missing live opt-in, an
incompatible Controlled Execution boundary, or a non-writable Runtime data path
is a blocking `FAIL`.

Mock `operator-run` uses the existing deterministic Runtime acceptance contract.
It proposes exactly one controlled replacement of
`tests/fixtures/afde_2_7_approval_target.txt` and stops at
`waiting_approval`. Copy the exact `Next:` command printed by the CLI.

## Status

```powershell
python -m afde.cli operator-status --session-id RWS-YYYYMMDD-HHMMSS-XXXXXX --workspace .
```

Add `--json` to any operator command for the stable operator result contract.

## Approval and resume

Approval and execution are deliberately separate operations. Approval records
the exact operator decision. Resume revalidates the action, Runtime context,
policy, and preimage before consuming the approval once.

```powershell
python -m afde.cli operator-approve --session-id RWS-YYYYMMDD-HHMMSS-XXXXXX --approval-id APR-XXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXX --workspace .
python -m afde.cli operator-resume --session-id RWS-YYYYMMDD-HHMMSS-XXXXXX --workspace .
```

To reject instead:

```powershell
python -m afde.cli operator-reject --session-id RWS-YYYYMMDD-HHMMSS-XXXXXX --approval-id APR-XXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXX --reason "Replacement is not approved" --workspace .
```

A rejected workflow remains blocked and does not modify the target file.

## Dashboard and history inspection

Completed and failed results print these inspection hints with the actual
session ID:

```powershell
python -m afde.cli runtime-history --session-id RWS-YYYYMMDD-HHMMSS-XXXXXX
python -m afde.cli runtime-events --session-id RWS-YYYYMMDD-HHMMSS-XXXXXX --json
python -m afde.cli runtime-dashboard --session-id RWS-YYYYMMDD-HHMMSS-XXXXXX
python -m afde.cli runtime-dashboard-web --session-id RWS-YYYYMMDD-HHMMSS-XXXXXX
```

Status, history, and Dashboard projections are read-only and do not modify
`session.json` or `events.jsonl`.

## Optional live-provider mode

Live OpenAI execution can incur charges. The API key remains environment-only,
and both provider configuration and explicit opt-in are required.

```powershell
$secret = Read-Host "OpenAI API key" -AsSecureString
$env:OPENAI_API_KEY = [System.Net.NetworkCredential]::new("", $secret).Password
python -m afde.cli operator-preflight --provider openai --allow-live-api --workspace .
python -m afde.cli operator-run --request "Prepare a small implementation" --provider openai --model gpt-4.1-mini --allow-live-api --workspace .
```

Do not paste credentials into `--request`, files, logs, or command output. Live
provider calls are never made without `--allow-live-api`.

## Common recovery cases

- Expected Runtime failures use `Status`, `Error`, `Cause`, `Next action`,
  `Evidence`, and `Session ID` where applicable. JSON commands expose the same
  meanings as lower-case keys. This is Beta hardening of existing commands, not
  a new Runtime feature or state transition.
- Exit code `0`: the command completed successfully.
- Exit code `2`: correct invalid CLI input, filters, state-dependent requests,
  or provider configuration and rerun the command.
- Exit code `3`: resolve every preflight `FAIL`; no Runtime session was started.
- Exit code `4`: the requested session or approval was not found; verify the
  exact ID and `--workspace`, then use the printed Runtime history command.
- Exit code `5`: a Runtime/Provider operation or Runtime evidence read failed;
  inspect the printed cause, evidence, Runtime history, and Dashboard.
- Exit code `7`: official Beta execution could not persist evidence; verify
  workspace write access before retrying.
- `waiting_approval`: run the exact printed `operator-approve` command, then the
  exact printed `operator-resume` command.
- `blocked` after rejection: inspect `operator-status` and history; start a new
  operator run if a new action is desired.
- Context or preimage mismatch: do not retry the consumed or invalid approval;
  inspect evidence and start a new run so policy can evaluate a new exact action.

Expected input, lookup, state, Provider, and persisted-data errors are rendered
without a Python traceback. Unexpected internal errors are deliberately not
caught at this boundary so debugging information and exception chains remain
available.
