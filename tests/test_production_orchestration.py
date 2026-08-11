from dataclasses import replace
from pathlib import Path
from types import SimpleNamespace
from uuid import uuid4

import pytest

from afde.codex_automation_bridge_production_adapter import (
    CodexAutomationBridgeProductionFactory,
    CodexAutomationBridgeProductionInvocationTarget,
)
from afde.knowledge import KnowledgeFoundationProvider
from afde.production_adapter_creation import (
    ProductionAdapterConfigurationKey,
    ProductionAdapterConfigurationMetadata,
)
from afde.production_adapter_credential_readiness import (
    CredentialReadinessEvidence,
    CredentialReadinessEvidenceSource,
)
from afde.production_adapter_runtime_execution import (
    ProductionAdapterRuntimeExecutionAuthority,
)
from afde.production_adapter_runtime_startup_integration import (
    ProductionAdapterRuntimeStartupPrerequisiteError,
    build_production_adapter_runtime_startup_composition,
)
from afde.production_orchestration import (
    InvalidProductionOrchestrationRequestError,
    ProductionOrchestrationRequest,
    ProductionOrchestrationStatus,
    ProductionPlannerRuntimeOrchestrator,
)
from afde.runtime_integration import RuntimeIntegrationPolicy
from afde.tool_catalog import ExecutionContract, RuntimeCompatibility
from real_worker_runtime.controlled_execution import (
    ControlledExecutor,
    RuntimeApprovalContext,
)
from real_worker_runtime.tool_actions import ToolAction, ToolActionType


ROOT = Path(__file__).resolve().parents[1]
ADAPTER_ID = "adapter.codex_automation_bridge"
CAPABILITY_ID = "CAP-TOOLADAPTER-CONTRACT-0001"


class EmptyDiscoverySource:
    def entry_points(self, group):
        return ()


class BindingAuthorityProvider:
    def __init__(self, *, mismatch=False, fixed_reference=None):
        self.mismatch = mismatch
        self.fixed_reference = fixed_reference
        self.bindings = []

    def get_authority(self, binding):
        self.bindings.append(binding)
        return ProductionAdapterRuntimeExecutionAuthority(
            authority_reference=self.fixed_reference or (
                "RUNTIME-EXECUTION-AUTHORITY-" + uuid4().hex.upper()
            ),
            adapter_id=binding.adapter_id,
            projection_id=binding.projection_id,
            path_id=binding.path_id,
            capability_id=binding.capability_id,
            binding_id=(
                "ADAPTERBIND-FFFFFFFFFFFFFFFF"
                if self.mismatch else binding.binding_id
            ),
        )


def _request(**changes):
    request = ProductionOrchestrationRequest(
        goal="Verify the production Codex adapter boundary",
        capability_id=CAPABILITY_ID,
        invocation_metadata_references=(
            "INVOCATION-REFERENCE-AFDE-6.19-001",
        ),
    )
    return replace(request, **changes)


def _action(tmp_path, **changes):
    action = ToolAction(
        action_id="AFDE-6.19-" + uuid4().hex,
        action_type=ToolActionType.COMMAND_RUN,
        source_worker="afde-6.19-test",
        purpose="Reach controlled execution through production orchestration",
        target="python",
        arguments={"argv": ["python", "--version"]},
        cwd=str(tmp_path),
        repository=str(tmp_path),
        branch="agent/afde-6-19-test",
        runtime_task_id="task-afde-6-19",
        runtime_session_id="session-afde-6-19",
        stage="qa",
        revision=1,
        preconditions={},
        expected_result={},
        metadata={},
    )
    return replace(action, **changes)


def _startup(tmp_path, *, action=None, evidence=True, runner=None):
    executor = (
        ControlledExecutor(tmp_path)
        if runner is None
        else ControlledExecutor(tmp_path, runner=runner)
    )
    factory = CodexAutomationBridgeProductionFactory(
        tmp_path, executor=executor,
    )
    action = action or _action(tmp_path)
    context = RuntimeApprovalContext(
        cwd=str(tmp_path),
        repository=str(tmp_path),
        branch="agent/afde-6-19-test",
        environment="test",
        runtime_task_id="task-afde-6-19",
        runtime_session_id="session-afde-6-19",
        stage="qa",
        actor="afde-6.19-test",
        metadata={"revision": 1},
    )
    target = CodexAutomationBridgeProductionInvocationTarget(
        factory, action=action, approval_context=context,
    )
    readiness = None if evidence is None else CredentialReadinessEvidence(
        adapter_id=ADAPTER_ID,
        ready=evidence,
        evidence_reference="CRED-EVIDENCE-AFDE-6.19-001",
        source=CredentialReadinessEvidenceSource.GOVERNED_RECORD_REFERENCE,
    )
    startup = build_production_adapter_runtime_startup_composition(
        knowledge_provider=KnowledgeFoundationProvider(ROOT),
        runtime_policy=RuntimeIntegrationPolicy(
            projection_version="1.0.0",
            required_runtime_compatibility=RuntimeCompatibility.COMPATIBLE,
            required_execution_contract=ExecutionContract.CONTROLLED_RUNTIME,
        ),
        adapter_id=ADAPTER_ID,
        discovery_source=EmptyDiscoverySource(),
        factory=factory,
        credential_readiness_evidence=readiness,
        configuration_metadata=(
            ProductionAdapterConfigurationMetadata(
                key=ProductionAdapterConfigurationKey.PROFILE_REFERENCE,
                reference="CONFIG-REFERENCE-CODEX-CONTROLLED-RUNTIME",
            ),
        ),
        invocation_target=target,
    )
    return startup, target


def test_principal_request_runs_actual_planner_to_concrete_runtime_execution(
    tmp_path,
):
    calls = []

    def runner(argv, **kwargs):
        calls.append((argv, kwargs))
        return SimpleNamespace(returncode=0, stdout="Python test", stderr="")

    startup, target = _startup(tmp_path, runner=runner)
    authority = BindingAuthorityProvider()
    service = ProductionPlannerRuntimeOrchestrator(
        startup_composition=startup,
        authority_provider=authority,
    )

    result = service.orchestrate(_request())

    assert result.status is ProductionOrchestrationStatus.COMPLETED
    assert result.capability_id == CAPABILITY_ID
    assert result.adapter_id == ADAPTER_ID
    assert result.path_id.startswith("EXECPATH-")
    assert result.projection_id.startswith("RUNTIMEPROJ-")
    assert result.binding_id.startswith("ADAPTERBIND-")
    assert result.runtime_execution_result is not None
    assert result.runtime_allowed is False
    assert result.execution_allowed is False
    assert not hasattr(result, "authority")
    assert [item.split(".", 1)[0] for item in result.trace] == [
        "01", "02", "03", "04", "05", "06", "07", "08", "09",
    ]
    assert authority.bindings[0].binding_id == result.binding_id
    assert calls and calls[0][0][1:] == ["--version"]
    assert target.last_execution_result.status == "SUCCEEDED"


def test_invalid_planner_input_and_unresolved_capability_fail_closed(tmp_path):
    with pytest.raises(InvalidProductionOrchestrationRequestError):
        ProductionOrchestrationRequest(goal="", capability_id=CAPABILITY_ID)

    startup, _ = _startup(tmp_path)
    authority = BindingAuthorityProvider()
    result = ProductionPlannerRuntimeOrchestrator(
        startup_composition=startup,
        authority_provider=authority,
    ).orchestrate(_request(capability_id="CAP-NOTREGISTERED-0001"))

    assert result.status in {
        ProductionOrchestrationStatus.BLOCKED,
        ProductionOrchestrationStatus.REJECTED,
    }
    assert result.runtime_execution_result is None
    assert authority.bindings == []
    assert all(not item.startswith("03.") for item in result.trace)


def test_missing_and_mismatched_authority_stop_before_execution(tmp_path):
    startup, target = _startup(tmp_path)
    missing = ProductionPlannerRuntimeOrchestrator(
        startup_composition=startup,
        authority_provider=None,
    ).orchestrate(_request())
    assert missing.status is ProductionOrchestrationStatus.BLOCKED
    assert missing.binding_id is not None
    assert missing.trace[-1] == "08.runtime_authority.missing"
    assert target.last_execution_result is None


def test_authority_reuse_is_rejected_without_second_invocation(tmp_path):
    reference = "RUNTIME-EXECUTION-AUTHORITY-AFDE-6.19-REUSE"
    startup, first_target = _startup(tmp_path)
    first = ProductionPlannerRuntimeOrchestrator(
        startup_composition=startup,
        authority_provider=BindingAuthorityProvider(fixed_reference=reference),
    ).orchestrate(_request())
    assert first.status is ProductionOrchestrationStatus.COMPLETED
    assert first_target.last_execution_result is not None

    startup, second_target = _startup(tmp_path)
    second = ProductionPlannerRuntimeOrchestrator(
        startup_composition=startup,
        authority_provider=BindingAuthorityProvider(fixed_reference=reference),
    ).orchestrate(_request())
    assert second.status is ProductionOrchestrationStatus.REJECTED
    assert second.trace[-1] == "09.runtime_execution.failed"
    assert second_target.last_execution_result is None

    startup, target = _startup(tmp_path)
    mismatched = ProductionPlannerRuntimeOrchestrator(
        startup_composition=startup,
        authority_provider=BindingAuthorityProvider(mismatch=True),
    ).orchestrate(_request())
    assert mismatched.status is ProductionOrchestrationStatus.REJECTED
    assert mismatched.trace[-1] == "08.runtime_authority.rejected"
    assert target.last_execution_result is None


@pytest.mark.parametrize("target_path", [r"C:\outside.py", "../outside.py"])
def test_controlled_execution_denies_workspace_escape_through_orchestrator(
    tmp_path, target_path,
):
    action = _action(
        tmp_path,
        action_type=ToolActionType.FILE_WRITE,
        purpose="Prove controlled path denial",
        target=target_path,
        arguments={"content": "print('blocked')"},
    )
    startup, target = _startup(tmp_path, action=action)
    result = ProductionPlannerRuntimeOrchestrator(
        startup_composition=startup,
        authority_provider=BindingAuthorityProvider(),
    ).orchestrate(_request())

    assert result.status is ProductionOrchestrationStatus.REJECTED
    assert result.runtime_execution_result is None
    assert target.last_execution_result.status == "DENIED"


def test_waiting_approval_fails_closed_through_orchestrator(tmp_path):
    target_path = tmp_path / "existing.py"
    target_path.write_text("print('existing')", encoding="utf-8")
    action = _action(
        tmp_path,
        action_type=ToolActionType.FILE_WRITE,
        purpose="Prove governed approval remains pending",
        target=target_path.name,
        arguments={"content": "print('replacement')"},
    )
    startup, target = _startup(tmp_path, action=action)

    result = ProductionPlannerRuntimeOrchestrator(
        startup_composition=startup,
        authority_provider=BindingAuthorityProvider(),
    ).orchestrate(_request())

    assert result.status is ProductionOrchestrationStatus.REJECTED
    assert result.runtime_execution_result is None
    assert target.last_execution_result.status == "WAITING_APPROVAL"


def test_failed_controlled_execution_fails_closed_through_orchestrator(
    tmp_path,
):
    def runner(argv, **kwargs):
        return SimpleNamespace(returncode=1, stdout="", stderr="safe failure")

    startup, target = _startup(tmp_path, runner=runner)
    result = ProductionPlannerRuntimeOrchestrator(
        startup_composition=startup,
        authority_provider=BindingAuthorityProvider(),
    ).orchestrate(_request())

    assert result.status is ProductionOrchestrationStatus.REJECTED
    assert result.runtime_execution_result is None
    assert target.last_execution_result.status == "FAILED"


def test_duplicate_controlled_action_fails_closed_through_orchestrator(
    tmp_path,
):
    action = _action(tmp_path)
    claim = tmp_path / "data" / "tool_action_evidence" / f"{action.action_id}.claim"
    claim.parent.mkdir(parents=True)
    claim.write_text(action.fingerprint, encoding="utf-8")
    startup, target = _startup(tmp_path, action=action)

    result = ProductionPlannerRuntimeOrchestrator(
        startup_composition=startup,
        authority_provider=BindingAuthorityProvider(),
    ).orchestrate(_request())

    assert result.status is ProductionOrchestrationStatus.REJECTED
    assert result.runtime_execution_result is None
    assert target.last_execution_result.status == "DUPLICATE"


@pytest.mark.parametrize("evidence", [None, False])
def test_startup_rejects_missing_or_not_ready_credential_evidence(
    tmp_path, evidence,
):
    with pytest.raises(ProductionAdapterRuntimeStartupPrerequisiteError):
        _startup(tmp_path, evidence=evidence)
