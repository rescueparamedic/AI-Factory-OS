# Codex Safe Approval Policy v1

## Purpose

This project policy reduces approval prompts for clearly read-only repository
inspection and focused validation while retaining user review for state-changing,
remote-writing, and approval-sensitive commands.

The policy keeps these safety settings:

- `approval_policy = "on-request"`
- `approvals_reviewer = "user"`
- `sandbox_mode = "workspace-write"`
- `allow_login_shell = false`
- `auto_review` is not enabled

## Activation

Project-local `.codex` configuration and rules load only when AI Factory OS is
opened as a trusted project. Restart Codex after adding or changing these files
so the project policy is reloaded.

The `.codex` directory is protected by the sandbox. Creating or modifying its
configuration may therefore require explicit user approval even inside this
workspace. The workspace-write sandbox remains enabled and is not broadened by
this policy.

## Automatically allowed

The rules automatically allow these narrow command prefixes:

- `git status`, `git diff`, `git log`, `git branch`, `git rev-parse`, and
  `git remote`
- `python -m pytest`
- `python -m afde.cli`
- `rg`, `Get-ChildItem`, and `Get-Content`

The policy does not broadly allow `git`, `python`, PowerShell, `cmd`, or other
shell wrappers. A command that hides an allowed command behind a wrapper does
not inherit the allowance.

## Manual approval remains required

Codex must ask the user before running:

- `git fetch`, `git switch`, `git checkout`, `git add`, `git commit`,
  `git push`, `git pull`, `git merge`, and `git rebase`
- `gh pr create` and `gh pr merge`
- `Remove-Item`

These prompts cover local Git mutations, remote communication or writes, pull
request changes, and filesystem deletion.

## Forbidden operations

The policy blocks these destructive commands:

- `git reset --hard`
- `git clean`
- `git push --force` and `git push -f`
- `git checkout -- .`
- `git restore .`

Specific forbidden rules intentionally overlap broader prompt rules. Codex
selects the most restrictive matching decision, so a force push remains blocked
even though ordinary `git push` requires a prompt.

## Validation

Use `codex execpolicy check --rules .codex/rules/ai-factory.rules --pretty --
<command>` to inspect the decision for a representative tokenized command.
Policy checks validate command matching only; they do not execute the command.
