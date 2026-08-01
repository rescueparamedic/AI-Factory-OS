# PowerShell Merge Automation Standard v1

## Status and Scope

This standard defines `CAP-POWERSHELLMERGEAUTOMATIONSTANDARD-0001`, the
repository-local reference boundary for a user-approved GitHub pull-request
Merge Commit, `develop` synchronization, and completed feature-branch cleanup.
It adds no merge authority. Cross-project reusability is `NOT_VERIFIED`.

## Preconditions and Approval Gate

Execution is permitted only after all of the following are true:

1. the implementation Work Audit is `PASS`;
2. Chat Merge review is `PASS`;
3. the user explicitly approves this exact merge;
4. the repository, pull request, base/head branches, and full base/head SHAs
   are known;
5. the working tree is clean; and
6. Git and an authenticated GitHub CLI are available.

The reference script requires `-WorkAuditPassed`, `-ChatMergePassed`, and
`-UserMergeApproved`. These switches record caller assertions; they do not
perform, infer, or replace any approval. The script must not be invoked by CI,
a background service, Runtime, Application, Provider, or automatic approval.

## Input Contract

`scripts/Invoke-AfdeMergeAutomation.ps1` accepts:

| Input | Contract |
| --- | --- |
| `Repository` | Exact GitHub `owner/name` repository identity |
| `PullRequestNumber` | Positive pull-request number |
| `BaseBranch` | Expected target branch, normally `develop` |
| `ExpectedBaseSha` | Full 40-character pre-merge base SHA recorded by the approval |
| `HeadBranch` | Exact approved feature branch |
| `ExpectedHeadSha` | Full 40-character approved PR head SHA |
| Approval switches | Work PASS, Chat Merge PASS, and explicit user approval assertions |

Base and head must be distinct. A mismatch is never corrected or inferred.

## Validation and Merge Sequence

The implementation performs this fail-closed sequence:

1. validate the input and all three approval assertions;
2. validate the current GitHub repository and clean working tree;
3. fetch `origin/<BaseBranch>` and query the PR again;
4. validate PR state, base/head branch names, base/head SHAs, mergeability, and
   normalized CI checks;
5. for an open PR, require `origin/<BaseBranch>` to equal `ExpectedBaseSha`;
6. if Draft, run `gh pr ready`, query again, and repeat validation;
7. run `gh pr merge --merge` and query again;
8. obtain and validate the Merge Commit SHA;
9. fetch, check out the base branch, and pull with `--ff-only`;
10. require local and origin base SHAs to match and the Merge Commit to be an
    ancestor;
11. delete the remote feature branch only when it still exists, then delete
    the local branch with non-forcing `git branch -d` only when it still
    exists; and
12. revalidate a clean working tree and exact local/origin base equality.

Squash and rebase merge are prohibited. Direct pushes to the base branch,
force deletion, force push, CI bypass, and automatic merge approval are
prohibited.

## CI JSON Normalization

Every `statusCheckRollup` item is read through property discovery rather than
direct missing-property access. The normalizer accepts CheckRun and
StatusContext shapes containing any available subset of `status`,
`conclusion`, `state`, `name`, `context`, and `workflowName`.

`SUCCESS`, `SKIPPED`, and `NEUTRAL` are accepted terminal outcomes. Expected,
pending, queued, requested, in-progress, and waiting outcomes stop execution.
Failure, cancellation, timeout, action-required, unknown, missing, or any
unrecognized outcome fails closed. An empty check rollup also fails closed.

## Native Command Boundary

Native Git and GitHub CLI processes are launched through one capture boundary.
Standard output and standard error are collected separately. Standard error
does not determine success: exit code zero succeeds even when standard error
contains normal progress output. Any non-zero exit code throws immediately and
reports the rendered command, exit code, stdout, and stderr.

## Partial Execution and Re-entry

Every run fetches and queries current state instead of trusting state retained
from an earlier attempt.

- An already-Ready PR skips the Ready transition.
- An already-Merged PR may continue only when its recorded base/head identity,
  expected SHAs, CI results, and Merge Commit are valid.
- An already-synchronized base branch converges through an idempotent
  `--ff-only` pull and equality validation.
- An absent remote or local feature branch is reported as `ALREADY_ABSENT`.
- A conflicting Merge Commit, identity, SHA, CI, mergeability, repository, or
  working-tree state stops execution.

The expected base SHA remains the approved pre-merge PR base. On re-entry after
merge, it is validated against the PR record; the current origin base must
contain the validated Merge Commit rather than equal the old pre-merge SHA.

## Error and Output Contract

Errors terminate the script because `$ErrorActionPreference = "Stop"` and
`Set-StrictMode -Version Latest` are mandatory. No later step may consume a
value whose creation failed. Error messages identify the failed invariant or
native command without converting a failed operation into success.

Success emits one JSON object containing `Result: SUCCESS`, repository and PR
identity, `MERGED` state, `MERGE_COMMIT` method, Merge Commit SHA, synchronized
base SHA, branch cleanup outcomes, re-entry indicators, and final clean-tree
evidence.

## PowerShell Compatibility

The reference implementation uses syntax and .NET APIs shared by Windows
PowerShell 5.1 and PowerShell 7. It does not depend on `$PSNativeCommandUseErrorActionPreference`,
null-coalescing operators, ternary syntax, or unconditional property access.
Parser and unit validation should run in both hosts when available. An
unavailable host must be reported as `NOT_VERIFIED`, never inferred as passing.

## Prohibited Extensions

This capability does not modify Runtime or Application packages, authorize
merges, infer approvals, schedule execution, run as a service, change Release
Policy, weaken checks, use squash/rebase, or claim compatibility with another
repository. Such work requires a separately approved scope.
