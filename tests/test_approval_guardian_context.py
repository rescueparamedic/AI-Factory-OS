from approval_guardian import ApprovalDecision, ApprovalGuardian, ApprovalRequest


def test_write_outside_repository_requires_user(tmp_path):
    root = tmp_path / "repo"
    root.mkdir()
    outside = tmp_path / "outside"
    outside.mkdir()
    result = ApprovalGuardian(root, audit=False).evaluate(
        ApprovalRequest(command="git add file.txt", cwd=str(outside), branch="feature/test")
    )
    assert result.decision is ApprovalDecision.ASK_USER


def test_production_mutation_requires_user(tmp_path):
    result = ApprovalGuardian(tmp_path, audit=False).evaluate(
        ApprovalRequest(
            command="git commit -m test",
            cwd=str(tmp_path),
            branch="feature/test",
            environment="prod",
        )
    )
    assert result.decision is ApprovalDecision.ASK_USER


def test_production_read_only_command_remains_safe(tmp_path):
    result = ApprovalGuardian(tmp_path, audit=False).evaluate(
        ApprovalRequest(command="git status", cwd=str(tmp_path), environment="prod")
    )
    assert result.decision is ApprovalDecision.AUTO_APPROVE


def test_feature_push_without_branch_context_requires_user(tmp_path):
    result = ApprovalGuardian(tmp_path, audit=False).evaluate(
        ApprovalRequest(command="git push origin feature/test", cwd=str(tmp_path), branch="")
    )
    assert result.decision is ApprovalDecision.ASK_USER
