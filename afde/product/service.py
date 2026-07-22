"""Application coordination over the existing OperatorService."""
from __future__ import annotations

from pathlib import Path
from typing import Callable

from afde.operator import (
    OperatorError,
    OperatorService,
    PreflightResult,
)

from .models import ProductRunView
from .presenter import project_operator_result


OperatorFactory = Callable[[str | Path], OperatorService]


class ProductOperationError(RuntimeError):
    """Stable Product Layer wrapper that preserves the Operator error meaning."""

    def __init__(self, operation: str, error: OperatorError) -> None:
        self.operation = operation
        self.operator_error_type = type(error).__name__
        self.operator_exit_code = error.exit_code
        super().__init__(f"{operation} failed: {error}")


class DevelopmentRunService:
    """Coordinate product runs exclusively through OperatorService."""

    def __init__(
        self,
        operator_factory: OperatorFactory = OperatorService,
    ) -> None:
        self._operator_factory = operator_factory

    def preflight(
        self,
        workspace: str | Path,
        provider: str,
        allow_live_api: bool = False,
    ) -> PreflightResult:
        operator = self._operator(workspace)
        return self._call(
            "preflight",
            operator.preflight,
            provider,
            allow_live_api,
        )

    def run(
        self,
        goal: str,
        workspace: str | Path,
        provider: str = "mock",
        model: str | None = None,
        allow_live_api: bool = False,
    ) -> ProductRunView:
        operator = self._operator(workspace)
        result = self._call(
            "run",
            operator.run,
            goal,
            provider,
            allow_live_api=allow_live_api,
            model=model,
        )
        return project_operator_result(result)

    def status(
        self,
        session_id: str,
        workspace: str | Path,
    ) -> ProductRunView:
        operator = self._operator(workspace)
        return project_operator_result(
            self._call("status", operator.status, session_id)
        )

    def approve(
        self,
        session_id: str,
        approval_id: str,
        workspace: str | Path,
    ) -> ProductRunView:
        operator = self._operator(workspace)
        return project_operator_result(
            self._call("approve", operator.approve, session_id, approval_id)
        )

    def reject(
        self,
        session_id: str,
        approval_id: str,
        reason: str,
        workspace: str | Path,
    ) -> ProductRunView:
        operator = self._operator(workspace)
        return project_operator_result(
            self._call(
                "reject",
                operator.reject,
                session_id,
                approval_id,
                reason,
            )
        )

    def resume(
        self,
        session_id: str,
        workspace: str | Path,
    ) -> ProductRunView:
        operator = self._operator(workspace)
        return project_operator_result(
            self._call("resume", operator.resume, session_id)
        )

    def _operator(self, workspace: str | Path) -> OperatorService:
        return self._operator_factory(workspace)

    @staticmethod
    def _call(operation: str, method, *args, **kwargs):
        try:
            return method(*args, **kwargs)
        except OperatorError as error:
            raise ProductOperationError(operation, error) from error
