"""Concrete factory and invocation target for CodexAutomationBridge."""
from __future__ import annotations

from hashlib import sha256
from pathlib import Path
from threading import Lock

from afde.production_adapter_creation import (
    ProductionAdapterCreationContext,
    ProductionAdapterInstance,
)
from afde.production_adapter_invocation import (
    InvocationRequest,
    InvocationTargetResult,
)
from real_worker_runtime.automation_bridge import CodexAutomationBridge
from real_worker_runtime.controlled_execution import (
    ControlledExecutor,
    RuntimeApprovalContext,
)
from real_worker_runtime.tool_actions import ToolAction, ToolExecutionResult


CODEX_AUTOMATION_BRIDGE_ADAPTER_ID = "adapter.codex_automation_bridge"


class CodexAutomationBridgeProductionFactory:
    """Create the existing bridge at the authorized creation boundary."""

    adapter_id = CODEX_AUTOMATION_BRIDGE_ADAPTER_ID

    def __init__(
        self,
        workspace_root: str | Path,
        *,
        executor: ControlledExecutor | None = None,
    ) -> None:
        self._workspace_root = Path(workspace_root).resolve()
        if not self._workspace_root.is_dir():
            raise ValueError("workspace_root must be an existing directory")
        if executor is not None and (
            type(executor) is not ControlledExecutor
            or executor.root != self._workspace_root
        ):
            raise ValueError(
                "executor must be a ControlledExecutor for the exact workspace"
            )
        self._executor = executor
        self._lock = Lock()
        self._bridges: dict[str, tuple[CodexAutomationBridge, str]] = {}

    def create(
        self, context: ProductionAdapterCreationContext,
    ) -> ProductionAdapterInstance:
        if type(context) is not ProductionAdapterCreationContext:
            raise TypeError(
                "context must be exactly one ProductionAdapterCreationContext"
            )
        if (
            context.adapter_id != self.adapter_id
            or context.descriptor.adapter_id != self.adapter_id
            or context.binding is None
            or context.binding.adapter_id != self.adapter_id
        ):
            raise ValueError(
                "Codex production factory identity chain is incomplete"
            )
        configuration = tuple(
            f"{item.key.value}:{item.reference}"
            for item in context.configuration_metadata
        )
        digest = sha256(
            "\x1f".join((
                str(self._workspace_root),
                context.binding.binding_id,
                *configuration,
            )).encode("utf-8")
        ).hexdigest()[:16].upper()
        creation_reference = f"CREATION-REFERENCE-CODEX-{digest}"
        bridge = CodexAutomationBridge(
            self._workspace_root,
            executor=self._executor,
        )
        with self._lock:
            if context.binding.binding_id in self._bridges:
                raise ValueError(
                    "a Codex bridge already exists for this binding identity"
                )
            self._bridges[context.binding.binding_id] = (
                bridge,
                creation_reference,
            )
        return ProductionAdapterInstance(
            adapter_id=self.adapter_id,
            creation_metadata_references=(creation_reference,),
            runtime_allowed=False,
            execution_allowed=False,
        )

    def claim_bridge(
        self,
        binding_id: str,
        creation_reference: str,
    ) -> CodexAutomationBridge:
        """Consume the bridge created for one exact binding identity."""

        with self._lock:
            try:
                bridge, expected_reference = self._bridges.pop(binding_id)
            except KeyError as exc:
                raise ValueError(
                    "no created Codex bridge matches the binding identity"
                ) from exc
        if creation_reference != expected_reference:
            raise ValueError(
                "Codex bridge creation reference does not match the instance"
            )
        return bridge


class CodexAutomationBridgeProductionInvocationTarget:
    """Invoke one structured ToolAction with its Runtime approval context."""

    adapter_id = CODEX_AUTOMATION_BRIDGE_ADAPTER_ID

    def __init__(
        self,
        factory: CodexAutomationBridgeProductionFactory,
        *,
        action: ToolAction,
        approval_context: RuntimeApprovalContext,
    ) -> None:
        if type(factory) is not CodexAutomationBridgeProductionFactory:
            raise TypeError("factory must be the concrete Codex production factory")
        if type(action) is not ToolAction:
            raise TypeError("action must be exactly one structured ToolAction")
        if type(approval_context) is not RuntimeApprovalContext:
            raise TypeError(
                "approval_context must be exactly one RuntimeApprovalContext"
            )
        self._factory = factory
        self._action = action
        self._approval_context = approval_context
        self._last_execution_result: ToolExecutionResult | None = None

    @property
    def last_execution_result(self) -> ToolExecutionResult | None:
        """Expose controlled-execution evidence for the composing caller."""

        return self._last_execution_result

    def invoke(self, request: InvocationRequest) -> InvocationTargetResult:
        if type(request) is not InvocationRequest:
            raise TypeError("request must be exactly one InvocationRequest")
        if request.adapter_id != self.adapter_id:
            raise ValueError("Codex invocation request adapter identity mismatches")
        references = request.instance.creation_metadata_references
        if len(references) != 1:
            raise ValueError("Codex instance must have one creation reference")
        bridge = self._factory.claim_bridge(
            request.binding.binding_id,
            references[0],
        )
        result = bridge.execute(self._action, self._approval_context)
        self._last_execution_result = result
        result_reference = (
            "INVOCATION-RESULT-REFERENCE-CODEX-"
            f"{result.action_fingerprint[:16].upper()}"
        )
        return InvocationTargetResult(
            adapter_id=self.adapter_id,
            result_metadata_references=(result_reference,),
            runtime_allowed=False,
            execution_allowed=False,
        )
