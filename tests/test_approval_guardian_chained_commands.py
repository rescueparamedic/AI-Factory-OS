from approval_guardian import ApprovalDecision, ApprovalGuardian, ApprovalRequest


def evaluate(tmp_path, command):
    return ApprovalGuardian(tmp_path, audit=False).evaluate(
        ApprovalRequest(command=command, cwd=str(tmp_path), branch="feature/test")
    )


def test_deny_overrides_safe_command(tmp_path):
    assert evaluate(tmp_path, "pytest && git reset --hard").decision is ApprovalDecision.DENY


def test_prompt_overrides_safe_command(tmp_path):
    assert evaluate(tmp_path, "pytest; git push origin main").decision is ApprovalDecision.ASK_USER


def test_all_safe_chain_is_auto_approved(tmp_path):
    assert evaluate(tmp_path, "git status && python -m pytest -q").decision is ApprovalDecision.AUTO_APPROVE


def test_bash_wrapper_is_unwrapped(tmp_path):
    assert evaluate(tmp_path, "bash -c 'git reset --hard'").decision is ApprovalDecision.DENY


def test_cmd_wrapper_is_unwrapped(tmp_path):
    assert evaluate(tmp_path, 'cmd /c "git push origin main"').decision is ApprovalDecision.ASK_USER


def test_quoted_separator_is_not_executed(tmp_path):
    result = evaluate(tmp_path, "rg 'pytest && harmless' .")
    assert result.decision is ApprovalDecision.AUTO_APPROVE


def test_unclosed_quote_fails_closed(tmp_path):
    result = evaluate(tmp_path, "pytest 'unterminated")
    assert result.decision is ApprovalDecision.ASK_USER
    assert result.rule_id == "AGV2-A999"
