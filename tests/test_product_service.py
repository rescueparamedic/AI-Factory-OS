from __future__ import annotations

from pathlib import Path

import pytest

from afde.operator import (
    OperatorInputError,
    OperatorResult,
    PreflightResult,
)
from afde.product import (
    DevelopmentRunService,
    ProductOperationError,
    ProductRunView,
)


class FakeOperatorService:
    def __init__(self, workspace: str | Path) -> None:
        self.workspace = workspace
        self.calls = []
        self.result = OperatorResult(
            status="completed",
            session_id="RWS-product-service",
            request="Default goal",
            provider="mock",
            approval_id=None,
            summary="Completed by the existing Operator workflow.",
            next_action="",
            evidence=(
                {"type": "artifact", "reference": "artifacts/output.py"},
            ),
            history_hint="runtime-history --session-id RWS-product-service",
            dashboard_hint="runtime-dashboard --session-id RWS-product-service",
        )
        self.preflight_result = PreflightResult(
            status="PASS",
            blocking=False,
            provider="mock",
            workspace=str(workspace),
            checks=(),
        )

    def preflight(self, provider="mock", allow_live_api=False):
        self.calls.append(("preflight", provider, allow_live_api))
        return self.preflight_result

    def run(
        self,
        request,
        provider="mock",
        *,
        allow_live_api=False,
        model=None,
    ):
        self.calls.append(
            ("run", request, provider, allow_live_api, model)
        )
        return OperatorResult(
            **{
                **self.result.__dict__,
                "request": request,
                "provider": provider,
            }
        )

    def status(self, session_id):
        self.calls.append(("status", session_id))
        return self.result

    def approve(self, session_id, approval_id):
        self.calls.append(("approve", session_id, approval_id))
        return self.result

    def reject(self, session_id, approval_id, reason):
        self.calls.append(("reject", session_id, approval_id, reason))
        return self.result

    def resume(self, session_id):
        self.calls.append(("resume", session_id))
        return self.result


@pytest.fixture
def composed_service(tmp_path):
    operator = FakeOperatorService(tmp_path)
    workspaces = []

    def factory(workspace):
        workspaces.append(workspace)
        return operator

    return DevelopmentRunService(factory), operator, workspaces, tmp_path


def test_run_composes_operator_and_projects_product_view(composed_service):
    service, operator, workspaces, workspace = composed_service

    view = service.run(
        "Create a normal product capability",
        workspace,
        provider="mock",
        model="test-model",
        allow_live_api=True,
    )

    assert isinstance(view, ProductRunView)
    assert view.goal == "Create a normal product capability"
    assert view.evidence_references == ("artifacts/output.py",)
    assert operator.calls == [(
        "run",
        "Create a normal product capability",
        "mock",
        True,
        "test-model",
    )]
    assert workspaces == [workspace]
    assert "[" not in view.goal


def test_default_provider_is_mock_and_no_marker_is_inserted(composed_service):
    service, operator, _, workspace = composed_service

    service.run("Write clear release notes", workspace)

    assert operator.calls == [(
        "run",
        "Write clear release notes",
        "mock",
        False,
        None,
    )]


def test_preflight_and_session_operations_delegate_exactly(composed_service):
    service, operator, _, workspace = composed_service

    preflight = service.preflight(workspace, "openai", allow_live_api=True)
    status = service.status("RWS-1", workspace)
    approved = service.approve("RWS-1", "APR-1", workspace)
    rejected = service.reject("RWS-1", "APR-1", "Not approved", workspace)
    resumed = service.resume("RWS-1", workspace)

    assert preflight is operator.preflight_result
    assert all(
        isinstance(item, ProductRunView)
        for item in (status, approved, rejected, resumed)
    )
    assert operator.calls == [
        ("preflight", "openai", True),
        ("status", "RWS-1"),
        ("approve", "RWS-1", "APR-1"),
        ("reject", "RWS-1", "APR-1", "Not approved"),
        ("resume", "RWS-1"),
    ]


def test_operator_errors_are_normalized_without_hiding_meaning(tmp_path):
    class FailingOperator(FakeOperatorService):
        def run(self, *args, **kwargs):
            raise OperatorInputError("request must not be empty")

    service = DevelopmentRunService(FailingOperator)

    with pytest.raises(ProductOperationError) as captured:
        service.run(" ", tmp_path)

    error = captured.value
    assert error.operation == "run"
    assert error.operator_error_type == "OperatorInputError"
    assert error.operator_exit_code == OperatorInputError.exit_code
    assert "request must not be empty" in str(error)
    assert isinstance(error.__cause__, OperatorInputError)


def test_service_module_has_no_runtime_or_execution_capability_imports():
    source = Path("afde/product/service.py").read_text(encoding="utf-8")

    assert "real_worker_runtime" not in source
    assert "RealWorkerRuntime" not in source
    assert "ToolAction" not in source
    assert "ControlledExecutor" not in source
