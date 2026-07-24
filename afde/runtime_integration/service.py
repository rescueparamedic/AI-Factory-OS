"""Deterministic non-executable Runtime readiness projection."""
from __future__ import annotations

from hashlib import sha256

from afde.execution_path import ExecutionPathStatus

from .errors import InvalidRuntimeIntegrationRequestError
from .models import (
    RuntimeIntegrationPolicy,
    RuntimeIntegrationRequest,
    RuntimeIntegrationResult,
    RuntimeIntegrationStatus,
    RuntimeProjection,
)


class RuntimeIntegrationService:
    """Project one Execution Path into Runtime-ready structural metadata."""

    def __init__(self, policy: RuntimeIntegrationPolicy) -> None:
        if not isinstance(policy, RuntimeIntegrationPolicy):
            raise TypeError("policy must be a RuntimeIntegrationPolicy")
        self._policy = policy

    def project(
        self, request: RuntimeIntegrationRequest,
    ) -> RuntimeIntegrationResult:
        if not isinstance(request, RuntimeIntegrationRequest):
            raise InvalidRuntimeIntegrationRequestError(
                "request must be a RuntimeIntegrationRequest"
            )
        path = request.execution_path
        if path.runtime_allowed or path.execution_allowed:
            raise InvalidRuntimeIntegrationRequestError(
                "Execution Path cannot grant execution authority"
            )
        reasons = self._blocked_reasons(path)
        if reasons:
            return RuntimeIntegrationResult(
                status=RuntimeIntegrationStatus.BLOCKED,
                runtime_ready=False,
                projection=None,
                path_id=None,
                capability_id=path.capability_id,
                adapter_id=None,
                blocked_reasons=reasons,
                path_trace=path.trace,
                trace=(
                    "01.execution_path.rejected",
                    "02.runtime_projection.blocked",
                ),
                runtime_allowed=False,
                execution_allowed=False,
            )

        step = path.steps[0]
        projection_id = self._projection_id(path.path_id, step)
        projection = RuntimeProjection(
            projection_id=projection_id,
            projection_version=self._policy.projection_version,
            path_id=path.path_id,
            sequence=step.sequence,
            adapter_id=step.adapter_id,
            capability_id=step.capability_id,
            adapter_version=step.adapter_version,
            availability=step.availability,
            runtime_compatibility=step.runtime_compatibility,
            execution_contract=step.execution_contract,
            privacy_classification=step.privacy_classification,
            cost_classification=step.cost_classification,
            credentials_required=step.credentials_required,
            metadata_references=step.metadata_references,
            runtime_ready=True,
            runtime_allowed=False,
            execution_allowed=False,
        )
        return RuntimeIntegrationResult(
            status=RuntimeIntegrationStatus.READY,
            runtime_ready=True,
            projection=projection,
            path_id=path.path_id,
            capability_id=path.capability_id,
            adapter_id=path.adapter_id,
            blocked_reasons=(),
            path_trace=path.trace,
            trace=(
                "01.execution_path.accepted",
                f"02.runtime_projection.ready:{projection_id}",
            ),
            runtime_allowed=False,
            execution_allowed=False,
        )

    def _blocked_reasons(self, path) -> tuple[str, ...]:
        reasons: list[str] = []
        if path.status is not ExecutionPathStatus.CONSTRUCTED:
            reasons.append(
                f"Execution Path status is not constructed: {path.status.value}"
            )
        if not path.path_constructed:
            reasons.append("Execution Path is not structurally constructed")
        if not path.runtime_handoff_ready:
            reasons.append("Execution Path handoff prerequisites are incomplete")
        if path.path_id is None or path.adapter_id is None or len(path.steps) != 1:
            reasons.append("Execution Path identity or handoff step is incomplete")
        if path.steps:
            step = path.steps[0]
            if (
                step.runtime_compatibility
                is not self._policy.required_runtime_compatibility
            ):
                reasons.append(
                    "Runtime compatibility is unsupported by integration policy"
                )
            if (
                step.execution_contract
                is not self._policy.required_execution_contract
            ):
                reasons.append(
                    "Execution contract is unsupported by integration policy"
                )
            if not step.handoff_ready:
                reasons.append("Runtime handoff projection is not ready")
            if step.runtime_allowed or step.execution_allowed:
                raise InvalidRuntimeIntegrationRequestError(
                    "handoff projection cannot grant execution authority"
                )
        return tuple(reasons)

    def _projection_id(self, path_id, step) -> str:
        parts = (
            self._policy.projection_version,
            path_id,
            step.adapter_id,
            step.capability_id,
            step.adapter_version,
            step.runtime_compatibility.value,
            step.execution_contract.value,
            step.privacy_classification.value,
            step.cost_classification.value,
            str(step.credentials_required).lower(),
            *step.metadata_references,
        )
        digest = sha256("\x1f".join(parts).encode("utf-8")).hexdigest()
        return f"RUNTIMEPROJ-{digest[:16].upper()}"
