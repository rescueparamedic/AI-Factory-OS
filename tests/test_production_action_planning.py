from __future__ import annotations

from dataclasses import FrozenInstanceError, fields
import json
from pathlib import Path
import subprocess

import pytest

from afde.production_action_planning import (
    CAPABILITY_ID,
    EXECUTION_MODE,
    RUNTIME_MODEL,
    RUNTIME_PROVIDER,
    WORKER_ID,
    InvalidProductionActionPlanningRequestError,
    InvalidProductionActionProposalError,
    ProductionActionPlanner,
    ProductionActionPlanningGitContextError,
    ProductionActionPlanningProviderConfigurationError,
    ProductionActionPlanningProviderRequestError,
    ProductionActionPlanningRequest,
    ProductionToolActionValidationError,
    UnsafeProductionFileReadTargetError,
    UnsupportedProductionActionTypeError,
    build_openai_production_action_planner,
)
from afde.knowledge import KnowledgeFoundationProvider
from afde.providers import (
    AIProvider,
    ProviderRequestError,
    ProviderResponse,
)
from real_worker_runtime.tool_actions import ToolAction, ToolActionType


ROOT = Path(__file__).resolve().parents[1]


class FakeProvider(AIProvider):
    def __init__(self, content: str, *, error: Exception | None = None) -> None:
        self.content = content
        self.error = error
        self.calls: list[str] = []

    def generate(self, request: str) -> ProviderResponse:
        self.calls.append(request)
        if self.error is not None:
            raise self.error
        return ProviderResponse(
            provider="fake-planning-provider",
            model="deterministic-test-model",
            content=self.content,
        )


def _git_workspace(tmp_path: Path) -> Path:
    workspace = tmp_path / "workspace"
    workspace.mkdir()
    subprocess.run(
        ["git", "init", "-b", "planning-test", str(workspace)],
        check=True,
        capture_output=True,
        text=True,
    )
    (workspace / "README.md").write_text("safe project documentation\n")
    subprocess.run(
        ["git", "-C", str(workspace), "add", "README.md"],
        check=True,
        capture_output=True,
        text=True,
    )
    subprocess.run(
        [
            "git", "-C", str(workspace), "-c", "user.name=Planning Test",
            "-c", "user.email=planning@example.invalid", "commit", "-m", "fixture",
        ],
        check=True,
        capture_output=True,
        text=True,
    )
    return workspace.resolve()


def _proposal(action_type="FILE_READ", target="README.md") -> str:
    return json.dumps({
        "action_type": action_type,
        "purpose": "Inspect the requested project documentation",
        "target": target,
    })


def _planner(provider: AIProvider) -> ProductionActionPlanner:
    return ProductionActionPlanner(
        provider,
        task_id_factory=lambda: "TASK-PRODACTION-test",
        action_id_factory=lambda: "PROD-ACTION-test",
        session_id_factory=lambda: "production-action-test",
    )


def test_safe_file_read_produces_one_system_owned_inert_tool_action(tmp_path):
    workspace = _git_workspace(tmp_path)
    provider = FakeProvider(_proposal())
    before = {
        path.relative_to(workspace).as_posix(): path.read_bytes()
        for path in workspace.rglob("*") if path.is_file()
    }

    plan = _planner(provider).plan(ProductionActionPlanningRequest(
        workspace, "  README.md 내용을 확인해줘  ",
    ))

    after = {
        path.relative_to(workspace).as_posix(): path.read_bytes()
        for path in workspace.rglob("*") if path.is_file()
    }
    assert len(provider.calls) == 1
    assert "Return exactly one JSON object and nothing else" in provider.calls[0]
    assert "FILE_WRITE" in provider.calls[0] and "shell syntax" in provider.calls[0]
    assert plan.capability_id == CAPABILITY_ID
    assert plan.worker_id == WORKER_ID
    assert plan.task_id == "TASK-PRODACTION-test"
    assert plan.runtime_session_id == "production-action-test"
    assert (plan.runtime_provider, plan.runtime_model, plan.execution_mode) == (
        RUNTIME_PROVIDER, RUNTIME_MODEL, EXECUTION_MODE,
    )
    assert (plan.planning_provider, plan.planning_model) == (
        "fake-planning-provider", "deterministic-test-model",
    )
    assert plan.runtime_allowed is False and plan.execution_allowed is False
    assert type(plan.tool_action) is ToolAction
    assert plan.tool_action.action_type is ToolActionType.FILE_READ
    assert plan.tool_action.target == "README.md"
    assert plan.tool_action.arguments == {}
    assert plan.tool_action.cwd == str(workspace)
    assert plan.tool_action.repository == str(workspace)
    assert plan.tool_action.branch == "planning-test"
    assert plan.tool_action.source_worker == WORKER_ID
    assert plan.tool_action.runtime_task_id == plan.task_id
    assert plan.tool_action.runtime_session_id == plan.runtime_session_id
    assert plan.tool_action.stage == "production_action_planning"
    assert plan.tool_action.revision == 1
    assert plan.tool_action.metadata == {
        "capability_id": CAPABILITY_ID,
        "planning_provider": "fake-planning-provider",
        "planning_model": "deterministic-test-model",
    }
    assert before == after
    with pytest.raises(FrozenInstanceError):
        plan.task_id = "caller-controlled"


@pytest.mark.parametrize("action_type", ["GIT_STATUS", "GIT_DIFF"])
def test_git_actions_have_empty_trusted_target_and_no_arguments(tmp_path, action_type):
    workspace = _git_workspace(tmp_path)
    provider = FakeProvider(_proposal(action_type, ""))
    head_before = subprocess.run(
        ["git", "-C", str(workspace), "rev-parse", "HEAD"],
        check=True, capture_output=True, text=True,
    ).stdout

    plan = _planner(provider).plan(
        ProductionActionPlanningRequest(workspace, "Inspect repository state")
    )

    head_after = subprocess.run(
        ["git", "-C", str(workspace), "rev-parse", "HEAD"],
        check=True, capture_output=True, text=True,
    ).stdout
    assert len(provider.calls) == 1
    assert plan.tool_action.action_type is ToolActionType(action_type)
    assert plan.tool_action.target == ""
    assert plan.tool_action.arguments == {}
    assert plan.tool_action.branch == "planning-test"
    assert plan.tool_action.cwd == plan.tool_action.repository == str(workspace)
    assert head_before == head_after
    assert plan.runtime_allowed is plan.execution_allowed is False


@pytest.mark.parametrize("action_type", [
    "FILE_WRITE", "COMMAND_RUN", "TEST_RUN", "GIT_ADD", "GIT_COMMIT",
    "GIT_PUSH_FEATURE",
])
def test_prohibited_actions_fail_closed_after_one_call(tmp_path, action_type):
    workspace = _git_workspace(tmp_path)
    provider = FakeProvider(_proposal(action_type, ""))
    with pytest.raises(UnsupportedProductionActionTypeError):
        _planner(provider).plan(
            ProductionActionPlanningRequest(workspace, "Perform unsafe action")
        )
    assert len(provider.calls) == 1


@pytest.mark.parametrize("content", [
    "not-json",
    "```json\n{\"action_type\":\"GIT_STATUS\",\"purpose\":\"x\",\"target\":\"\"}\n```",
    "[]",
    "{}",
    '{"action_type":"GIT_STATUS","purpose":"x","target":"","extra":1}',
    '{"action_type":"GIT_STATUS","purpose":"x"}',
    '{"actions":[{"action_type":"GIT_STATUS"},{"action_type":"GIT_DIFF"}]}',
    '{"action_type":"UNKNOWN","purpose":"x","target":""}',
    '{"action_type":"GIT_STATUS","purpose":false,"target":""}',
    '{"action_type":"GIT_STATUS","purpose":"x","target":"README.md"}',
])
def test_malformed_provider_output_has_no_repair_or_retry(tmp_path, content):
    workspace = _git_workspace(tmp_path)
    provider = FakeProvider(content)
    with pytest.raises(InvalidProductionActionProposalError):
        _planner(provider).plan(
            ProductionActionPlanningRequest(workspace, "Inspect safely")
        )
    assert len(provider.calls) == 1


@pytest.mark.parametrize("target", [
    "../outside.txt", "/absolute.txt", r"C:\absolute.txt", ".git/config",
    ".env", "credentials.json", "private.pem", "private.key", "private.pfx",
    "private.p12", "missing.txt",
])
def test_unsafe_file_targets_fail_closed_without_content_leak(tmp_path, target):
    workspace = _git_workspace(tmp_path)
    for name in (".env", "credentials.json", "private.pem", "private.key", "private.pfx", "private.p12"):
        (workspace / name).write_text("TOP-SECRET-CONTENT")
    provider = FakeProvider(_proposal(target=target))
    with pytest.raises(UnsafeProductionFileReadTargetError) as caught:
        _planner(provider).plan(
            ProductionActionPlanningRequest(workspace, "Read requested file")
        )
    assert len(provider.calls) == 1
    assert "TOP-SECRET-CONTENT" not in str(caught.value)


def test_oversized_file_fails_closed(tmp_path):
    workspace = _git_workspace(tmp_path)
    (workspace / "large.txt").write_bytes(b"x" * 65537)
    provider = FakeProvider(_proposal(target="large.txt"))
    with pytest.raises(UnsafeProductionFileReadTargetError, match="64 KiB"):
        _planner(provider).plan(
            ProductionActionPlanningRequest(workspace, "Read large file")
        )
    assert len(provider.calls) == 1


@pytest.mark.parametrize("user_input", ["", "   ", "x" * 1001, None])
def test_invalid_user_request_fails_before_provider(tmp_path, user_input):
    workspace = _git_workspace(tmp_path)
    provider = FakeProvider(_proposal())
    with pytest.raises(InvalidProductionActionPlanningRequestError):
        planning_request = ProductionActionPlanningRequest(workspace, user_input)
        _planner(provider).plan(planning_request)
    assert provider.calls == []


def test_request_trims_only_outer_whitespace_and_resolves_workspace(tmp_path):
    workspace = _git_workspace(tmp_path)
    request = ProductionActionPlanningRequest(
        workspace / ".", "  inspect\nthis request  ",
    )
    assert request.workspace == workspace
    assert request.request == "inspect\nthis request"


def test_missing_and_non_directory_workspace_fail_during_request_validation(tmp_path):
    provider = FakeProvider(_proposal())
    missing = tmp_path / "missing"
    file_path = tmp_path / "file.txt"
    file_path.write_text("x")
    for workspace in (missing, file_path):
        with pytest.raises(InvalidProductionActionPlanningRequestError):
            planning_request = ProductionActionPlanningRequest(workspace, "inspect")
            _planner(provider).plan(planning_request)
    assert provider.calls == []


def test_non_git_workspace_fails_before_provider(tmp_path):
    workspace = tmp_path / "not-git"
    workspace.mkdir()
    provider = FakeProvider(_proposal())
    with pytest.raises(ProductionActionPlanningGitContextError, match="Git worktree"):
        _planner(provider).plan(
            ProductionActionPlanningRequest(workspace, "inspect")
        )
    assert provider.calls == []


def test_detached_head_fails_before_provider(tmp_path):
    workspace = _git_workspace(tmp_path)
    subprocess.run(
        ["git", "-C", str(workspace), "checkout", "--detach"],
        check=True, capture_output=True, text=True,
    )
    provider = FakeProvider(_proposal())
    with pytest.raises(ProductionActionPlanningGitContextError, match="non-detached"):
        _planner(provider).plan(
            ProductionActionPlanningRequest(workspace, "inspect")
        )
    assert provider.calls == []


def test_provider_failure_is_safely_typed_and_not_retried(tmp_path):
    workspace = _git_workspace(tmp_path)
    provider = FakeProvider(
        _proposal(),
        error=ProviderRequestError("unsafe upstream detail"),
    )
    with pytest.raises(ProductionActionPlanningProviderRequestError) as caught:
        _planner(provider).plan(
            ProductionActionPlanningRequest(workspace, "inspect")
        )
    assert len(provider.calls) == 1
    assert "unsafe upstream detail" not in str(caught.value)


def test_canonical_tool_action_validation_failure_is_typed(tmp_path):
    workspace = _git_workspace(tmp_path)
    provider = FakeProvider(_proposal())
    planner = ProductionActionPlanner(
        provider,
        task_id_factory=lambda: "invalid identity with spaces",
        action_id_factory=lambda: "invalid action with spaces",
        session_id_factory=lambda: "invalid session with spaces",
    )
    with pytest.raises(ProductionToolActionValidationError):
        planner.plan(ProductionActionPlanningRequest(workspace, "inspect"))
    assert len(provider.calls) == 1


def test_openai_builder_preserves_explicit_live_opt_in(monkeypatch):
    monkeypatch.setenv("OPENAI_API_KEY", "test-placeholder")
    with pytest.raises(ProductionActionPlanningProviderConfigurationError):
        build_openai_production_action_planner()


def test_contracts_have_no_credentials_or_execution_dependencies(tmp_path):
    request_fields = {item.name for item in fields(ProductionActionPlanningRequest)}
    plan_fields = {item.name for item in fields(
        __import__(
            "afde.production_action_planning", fromlist=["ProductionActionPlan"]
        ).ProductionActionPlan
    )}
    tool_action_fields = {item.name for item in fields(ToolAction)}
    forbidden = {
        "api_key", "credential", "approval_secret", "provider_client",
        "executor", "runtime_authority",
    }
    assert request_fields == {"workspace", "request"}
    assert not forbidden.intersection(request_fields | plan_fields | tool_action_fields)


def test_architecture_boundary_contains_no_runtime_execution_or_file_mutation():
    source = "\n".join(
        path.read_text(encoding="utf-8")
        for path in (ROOT / "afde" / "production_action_planning").glob("*.py")
    )
    for forbidden in (
        "ControlledExecutor", "CodexAutomationBridge", ".execute(", ".dispatch(",
        ".finalize(", "write_text(", "write_bytes(", "open(",
    ):
        assert forbidden not in source


def test_capability_policy_reuses_existing_registered_capability():
    capability = KnowledgeFoundationProvider(ROOT).get_capability(CAPABILITY_ID)
    assert capability is not None
    assert capability.capability_id == "CAP-TOOLADAPTER-CONTRACT-0001"
    assert capability.status == "implemented"
    assert capability.implementation_status == "implemented"
