import base64
import json
from pathlib import Path
import shutil
import subprocess

import pytest


ROOT = Path(__file__).resolve().parents[1]
SCRIPT = ROOT / "scripts" / "Invoke-AfdeMergeAutomation.ps1"
WINDOWS_POWERSHELL = shutil.which("powershell")


def _run_powershell(body: str) -> subprocess.CompletedProcess[str]:
    if WINDOWS_POWERSHELL is None:
        pytest.skip("Windows PowerShell is unavailable")
    source = str(SCRIPT).replace("'", "''")
    command = f". '{source}'; {body}"
    encoded = base64.b64encode(command.encode("utf-16-le")).decode("ascii")
    return subprocess.run(
        [
            WINDOWS_POWERSHELL,
            "-NoLogo",
            "-NoProfile",
            "-NonInteractive",
            "-EncodedCommand",
            encoded,
        ],
        cwd=ROOT,
        capture_output=True,
        text=True,
        check=False,
    )


def _successful_json(body: str):
    completed = _run_powershell(body)
    assert completed.returncode == 0, completed.stderr
    return json.loads(completed.stdout)


def test_windows_powershell_parser_accepts_reference_script():
    escaped_script = str(SCRIPT).replace("'", "''")
    completed = _run_powershell(
        "$tokens=$null; $errors=$null; "
        "[void][System.Management.Automation.Language.Parser]::ParseFile("
        f"'{escaped_script}', [ref]$tokens, [ref]$errors); "
        "if($errors.Count -ne 0){$errors | ForEach-Object {$_.ToString()}; exit 1}; "
        "'OK'"
    )
    assert completed.returncode == 0, completed.stderr
    assert "OK" in completed.stdout


def test_ci_normalization_handles_checkrun_statuscontext_and_missing_properties():
    result = _successful_json(
        "$checks=@("
        "[pscustomobject]@{status='COMPLETED';conclusion='SUCCESS';name='build'},"
        "[pscustomobject]@{state='SUCCESS';context='required/context'},"
        "[pscustomobject]@{conclusion='SKIPPED';workflowName='optional'},"
        "[pscustomobject]@{state='NEUTRAL'},"
        "[pscustomobject]@{status='IN_PROGRESS';name='pending'},"
        "[pscustomobject]@{conclusion='FAILURE';name='failed'});"
        "@($checks | ForEach-Object {ConvertTo-NormalizedCheck $_}) | ConvertTo-Json"
    )
    assert [item["Category"] for item in result] == [
        "SUCCESS",
        "SUCCESS",
        "SUCCESS",
        "SUCCESS",
        "PENDING",
        "FAILURE",
    ]
    assert result[1]["Name"] == "required/context"
    assert result[2]["Name"] == "optional"
    assert result[3]["Name"] == "<unnamed>"


@pytest.mark.parametrize(
    ("check", "message"),
    [
        ("[pscustomobject]@{status='IN_PROGRESS';name='build'}", "in progress"),
        ("[pscustomobject]@{conclusion='FAILURE';name='build'}", "did not succeed"),
        ("[pscustomobject]@{}", "did not succeed"),
    ],
)
def test_ci_validation_fails_closed_without_strictmode_property_errors(check, message):
    completed = _run_powershell(
        f"try {{Assert-CiChecks @({check}); exit 9}} catch {{[Console]::Out.Write($_.Exception.Message)}}"
    )
    assert completed.returncode == 0
    assert message in completed.stdout
    assert "PropertyNotFoundStrict" not in completed.stdout + completed.stderr


def test_ci_validation_allows_success_skipped_and_neutral():
    completed = _run_powershell(
        "$checks=@([pscustomobject]@{state='SUCCESS'},"
        "[pscustomobject]@{conclusion='SKIPPED'},"
        "[pscustomobject]@{conclusion='NEUTRAL'});"
        "$result=@(Assert-CiChecks $checks); [Console]::Out.Write($result.Count)"
    )
    assert completed.returncode == 0, completed.stderr
    assert completed.stdout == "3"


def test_native_command_exit_zero_accepts_stderr():
    result = _successful_json(
        "$executor={param($command,$arguments) [pscustomobject]@{"
        "ExitCode=0;StdOut='answer';StdErr='normal progress'}};"
        "Invoke-NativeCommand 'git' @('fetch') $executor | ConvertTo-Json"
    )
    assert result == {
        "ExitCode": 0,
        "StdOut": "answer",
        "StdErr": "normal progress",
    }


def test_native_command_nonzero_reports_command_exit_and_both_streams():
    completed = _run_powershell(
        "$executor={param($command,$arguments) [pscustomobject]@{"
        "ExitCode=7;StdOut='captured stdout';StdErr='captured stderr'}};"
        "try {Invoke-NativeCommand 'gh' @('pr','view','58') $executor; exit 9} "
        "catch {[Console]::Out.Write($_.Exception.Message)}"
    )
    assert completed.returncode == 0
    for expected in ("gh pr view 58", "Exit code: 7", "captured stdout", "captured stderr"):
        assert expected in completed.stdout
    assert "VariableIsUndefined" not in completed.stdout + completed.stderr


@pytest.mark.parametrize(
    ("state", "draft", "local", "remote", "synced", "expected"),
    [
        ("OPEN", "$true", "$true", "$true", "$false", [True, True, True, True, True]),
        ("OPEN", "$false", "$true", "$true", "$true", [False, True, False, True, True]),
        ("MERGED", "$false", "$false", "$false", "$true", [False, False, False, False, False]),
    ],
)
def test_recovery_plan_is_idempotent(state, draft, local, remote, synced, expected):
    result = _successful_json(
        f"Get-MergeRecoveryPlan '{state}' {draft} {local} {remote} {synced} | ConvertTo-Json"
    )
    assert list(result.values()) == expected


def test_already_merged_snapshot_skips_mergeability_and_retains_merge_commit():
    payload = json.dumps(
        _snapshot(
            state="MERGED",
            mergeable="UNKNOWN",
            mergeCommit={"oid": "d" * 40},
        ),
        separators=(",", ":"),
    ).replace("'", "''")
    result = _successful_json(
        f"$snapshot=ConvertFrom-Json '{payload}';"
        "$state=Assert-PullRequestSnapshot $snapshot 'develop' ('a'*40) "
        "'agent/feature' ('b'*40);"
        "$sha=Get-MergeCommitSha $snapshot;"
        "[pscustomobject]@{State=$state;Sha=$sha} | ConvertTo-Json"
    )
    assert result == {"State": "MERGED", "Sha": "d" * 40}


def _snapshot(**overrides):
    snapshot = {
        "state": "OPEN",
        "isDraft": False,
        "baseRefName": "develop",
        "baseRefOid": "a" * 40,
        "headRefName": "agent/feature",
        "headRefOid": "b" * 40,
        "mergeable": "MERGEABLE",
        "statusCheckRollup": [{"state": "SUCCESS", "context": "test"}],
    }
    snapshot.update(overrides)
    return snapshot


@pytest.mark.parametrize(
    ("overrides", "message"),
    [
        ({"baseRefOid": "c" * 40}, "base SHA"),
        ({"headRefOid": "c" * 40}, "head SHA"),
        ({"mergeable": "CONFLICTING"}, "not mergeable"),
        ({"statusCheckRollup": [{"state": "PENDING"}]}, "in progress"),
        ({"statusCheckRollup": [{"state": "FAILURE"}]}, "did not succeed"),
    ],
)
def test_pull_request_safety_checks_fail_closed(overrides, message):
    payload = json.dumps(_snapshot(**overrides), separators=(",", ":"))
    payload = payload.replace("'", "''")
    completed = _run_powershell(
        f"$snapshot=ConvertFrom-Json '{payload}'; try {{"
        "Assert-PullRequestSnapshot $snapshot 'develop' ('a'*40) 'agent/feature' ('b'*40); exit 9"
        "} catch {[Console]::Out.Write($_.Exception.Message)}"
    )
    assert completed.returncode == 0
    assert message.lower() in completed.stdout.lower()


def test_dirty_working_tree_stops_before_pr_lookup_or_merge():
    completed = _run_powershell(
        "$script:commands=@(); $executor={param($command,$arguments) "
        "$script:commands += (($command + ' ' + ($arguments -join ' '))); "
        "if($command -eq 'gh'){return [pscustomobject]@{ExitCode=0;StdOut='owner/repo';StdErr=''}};"
        "return [pscustomobject]@{ExitCode=0;StdOut=' M user-file.txt';StdErr=''}};"
        "try {Invoke-AfdeMergeAutomation 'owner/repo' 1 'develop' ('a'*40) "
        "'agent/feature' ('b'*40) $true $true $true $executor; exit 9} "
        "catch {[Console]::Out.Write($_.Exception.Message + '|' + ($script:commands -join ';'))}"
    )
    assert completed.returncode == 0
    assert "Working tree must be clean" in completed.stdout
    assert "gh pr merge" not in completed.stdout


def test_missing_user_approval_stops_before_any_native_command():
    completed = _run_powershell(
        "$script:called=$false;$executor={param($command,$arguments)"
        "$script:called=$true;throw 'executor must not run'};"
        "try {Invoke-AfdeMergeAutomation 'owner/repo' 1 'develop' ('a'*40) "
        "'agent/feature' ('b'*40) $true $true $false $executor;exit 9} "
        "catch {[Console]::Out.Write($_.Exception.Message+'|'+$script:called)}"
    )
    assert completed.returncode == 0
    assert "explicit user Merge approval" in completed.stdout
    assert completed.stdout.endswith("|False")


def test_reference_flow_revalidates_draft_merges_once_and_cleans_branches():
    result = _successful_json(
        "$script:state='OPEN';$script:draft=$true;$script:calls=@();"
        "$executor={param($command,$arguments) "
        "$key=$command+' '+($arguments -join ' ');$script:calls += $key;"
        "if($command -eq 'gh' -and $arguments[0] -eq 'repo'){"
        "return [pscustomobject]@{ExitCode=0;StdOut='owner/repo';StdErr=''}};"
        "if($command -eq 'gh' -and $arguments[0] -eq 'pr' -and $arguments[1] -eq 'view'){"
        "$merge=$null;if($script:state -eq 'MERGED'){$merge=[pscustomobject]@{oid=('d'*40)}};"
        "$pr=[pscustomobject]@{state=$script:state;isDraft=$script:draft;"
        "baseRefName='develop';baseRefOid=('a'*40);headRefName='agent/feature';"
        "headRefOid=('b'*40);mergeable='MERGEABLE';mergeCommit=$merge;"
        "statusCheckRollup=@([pscustomobject]@{state='SUCCESS';context='test'})};"
        "return [pscustomobject]@{ExitCode=0;StdOut=($pr|ConvertTo-Json -Depth 5);StdErr=''}};"
        "if($command -eq 'gh' -and $arguments[1] -eq 'ready'){"
        "$script:draft=$false;return [pscustomobject]@{ExitCode=0;StdOut='';StdErr=''}};"
        "if($command -eq 'gh' -and $arguments[1] -eq 'merge'){"
        "$script:state='MERGED';return [pscustomobject]@{ExitCode=0;StdOut='';StdErr=''}};"
        "if($command -eq 'git' -and $arguments[0] -eq 'status'){"
        "return [pscustomobject]@{ExitCode=0;StdOut='';StdErr=''}};"
        "if($command -eq 'git' -and $arguments[0] -eq 'rev-parse'){"
        "$sha=if($script:state -eq 'MERGED'){'d'*40}else{'a'*40};"
        "return [pscustomobject]@{ExitCode=0;StdOut=$sha;StdErr=''}};"
        "if($command -eq 'git' -and $arguments[0] -eq 'ls-remote'){"
        "return [pscustomobject]@{ExitCode=0;StdOut=(('b'*40)+' refs/heads/agent/feature');StdErr=''}};"
        "if($command -eq 'git' -and $arguments[0] -eq 'branch' -and $arguments[1] -eq '--list'){"
        "return [pscustomobject]@{ExitCode=0;StdOut='agent/feature';StdErr=''}};"
        "return [pscustomobject]@{ExitCode=0;StdOut='';StdErr=''}};"
        "$mergeResult=Invoke-AfdeMergeAutomation 'owner/repo' 8 'develop' ('a'*40) "
        "'agent/feature' ('b'*40) $true $true $true $executor | ConvertFrom-Json;"
        "[pscustomobject]@{Result=$mergeResult;Calls=$script:calls}|ConvertTo-Json -Depth 6"
    )
    assert result["Result"]["Result"] == "SUCCESS"
    assert result["Result"]["MergeMethod"] == "MERGE_COMMIT"
    assert result["Result"]["MergeCommitSha"] == "d" * 40
    assert result["Result"]["RemoteBranch"] == "DELETED"
    assert result["Result"]["LocalBranch"] == "DELETED"
    calls = result["Calls"]
    assert sum("gh pr ready" in call for call in calls) == 1
    assert sum("gh pr merge 8 --repo owner/repo --merge" in call for call in calls) == 1
    assert any("git pull --ff-only origin develop" in call for call in calls)
    assert any("git push origin --delete agent/feature" in call for call in calls)


def test_script_contract_uses_merge_commit_and_has_no_runtime_dependency():
    source = SCRIPT.read_text(encoding="utf-8")
    assert "'pr', 'merge'" in source
    assert "'--merge'" in source
    assert "--squash" not in source
    assert "--rebase" not in source
    assert "git' @('branch', '-d'" in source
    assert "branch', '-D'" not in source
    assert "afde.runtime" not in source
    assert "real_worker_runtime" not in source
    assert "UserMergeApproved" in source


def test_runtime_application_and_ci_workflows_do_not_import_or_invoke_capability():
    marker = "Invoke-AfdeMergeAutomation"
    for source_root in (ROOT / "afde", ROOT / "real_worker_runtime"):
        for path in source_root.rglob("*.py"):
            assert marker not in path.read_text(encoding="utf-8")
    workflow_root = ROOT / ".github" / "workflows"
    if workflow_root.exists():
        for path in workflow_root.iterdir():
            if path.is_file():
                assert marker not in path.read_text(encoding="utf-8")
