from dataclasses import FrozenInstanceError, replace
from pathlib import Path
from types import SimpleNamespace
from uuid import uuid4

import pytest

from afde.codex_automation_bridge_production_adapter import (
    CODEX_AUTOMATION_BRIDGE_ADAPTER_ID,
    CodexAutomationBridgeProductionFactory,
    CodexAutomationBridgeProductionInvocationTarget,
)
from afde.execution_path import (
    ExecutionPathRequest,
    ExecutionPathStatus,
)
from afde.knowledge import KnowledgeFoundationProvider
from afde.production_adapter_creation import (
    ProductionAdapterConfigurationKey,
    ProductionAdapterConfigurationMetadata,
)
from afde.production_adapter_credential_readiness import (
    CredentialReadinessEvidence,
    CredentialReadinessEvidenceSource,
    CredentialReadinessStatus,
    ProductionAdapterCredentialReadinessService,
)
from afde.production_adapter_discovery import (
    build_discovered_production_adapter_registry,
)
from afde.production_adapter_registration import (
    build_production_adapter_registry,
)
from afde.production_adapter_runtime_execution import (
    ProductionAdapterRuntimeExecutionAuthority,
    ProductionAdapterRuntimeExecutionAuthorityReuseError,
    ProductionAdapterRuntimeExecutionRequest,
    ProductionAdapterRuntimeExecutionService,
)
from afde.production_adapter_runtime_startup_integration import (
    ProductionAdapterRuntimeStartupPrerequisiteError,
    adapt_credential_readiness_to_runtime_prerequisite_satisfaction,
    build_production_adapter_runtime_startup_composition,
)
from afde.resolver import CapabilityRequirement
from afde.runtime_integration import (
    InvalidRuntimeIntegrationRequestError,
    RuntimeIntegrationPolicy,
    RuntimeIntegrationPrerequisiteRequest,
    RuntimeIntegrationRequest,
    RuntimeIntegrationStatus,
)
from afde.tool_adapter_contract import (
    ToolAdapterContractStatus,
    ToolAdapterRequest,
)
from afde.tool_catalog import ExecutionContract, RuntimeCompatibility
from afde.tool_selection import ToolAdapterSelectionRequest
from real_worker_runtime.automation_bridge import CodexAutomationBridge
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


def _descriptor():
    return build_production_adapter_registry().project_catalog().get_adapter(
        ADAPTER_ID
    )


def _policy():
    return RuntimeIntegrationPolicy(
        projection_version="1.0.0",
        required_runtime_compatibility=RuntimeCompatibility.COMPATIBLE,
        required_execution_contract=ExecutionContract.CONTROLLED_RUNTIME,
    )


def _evidence(*, ready=True, adapter_id=ADAPTER_ID):
    return CredentialReadinessEvidence(
        adapter_id=adapter_id,
        ready=ready,
        evidence_reference="CRED-EVIDENCE-AFDE-6.18-001",
        source=CredentialReadinessEvidenceSource.GOVERNED_RECORD_REFERENCE,
    )


def _configuration():
    return (
        ProductionAdapterConfigurationMetadata(
            key=ProductionAdapterConfigurationKey.PROFILE_REFERENCE,
            reference="CONFIG-REFERENCE-CODEX-CONTROLLED-RUNTIME",
        ),
    )


def _path(composition):
    resolution = composition.capability_resolver.resolve(
        CapabilityRequirement(capability_id=CAPABILITY_ID)
    )
    selection = composition.tool_adapter_selection.select(
        ToolAdapterSelectionRequest(resolution)
    )
    return composition.execution_path.build(ExecutionPathRequest(selection))


def _startup(tmp_path, *, action=None, context=None, executor=None):
    factory = CodexAutomationBridgeProductionFactory(
        tmp_path,
        executor=executor,
    )
    action = action or _tool_action(tmp_path)
    context = context or _approval_context(tmp_path)
    target = CodexAutomationBridgeProductionInvocationTarget(
        factory,
        action=action,
        approval_context=context,
    )
    startup = build_production_adapter_runtime_startup_composition(
        knowledge_provider=KnowledgeFoundationProvider(ROOT),
        runtime_policy=_policy(),
        adapter_id=ADAPTER_ID,
        discovery_source=EmptyDiscoverySource(),
        factory=factory,
        credential_readiness_evidence=_evidence(),
        configuration_metadata=_configuration(),
        invocation_target=target,
    )
    return startup, factory, target


def _approval_context(root):
    return RuntimeApprovalContext(
        cwd=str(root),
        repository=str(root),
        branch="agent/afde-6-18-test",
        environment="test",
        runtime_task_id="task-afde-6-18",
        runtime_session_id="session-afde-6-18",
        stage="qa",
        actor="afde-test-worker",
        metadata={"revision": 1},
    )


def _tool_action(root):
    return ToolAction(
        action_id=f"AFDE-6.18-{uuid4().hex}",
        action_type=ToolActionType.COMMAND_RUN,
        source_worker="afde-test-worker",
        purpose="Prove the controlled Codex production invocation boundary",
        target="python",
        arguments={"argv": ["python", "--version"]},
        cwd=str(root),
        repository=str(root),
        branch="agent/afde-6-18-test",
        runtime_task_id="task-afde-6-18",
        runtime_session_id="session-afde-6-18",
        stage="qa",
        revision=1,
        preconditions={},
        expected_result={},
        metadata={},
    )


def test_canonical_registration_is_discoverable_with_exact_identity():
    discovered = build_discovered_production_adapter_registry(
        source=EmptyDiscoverySource()
    ).project_catalog().get_adapter(ADAPTER_ID)

    assert discovered.adapter_id == CODEX_AUTOMATION_BRIDGE_ADAPTER_ID
    assert discovered.version == "1.0.0"
    assert discovered.credentials_required is True
    assert discovered.supported_capability_ids == (CAPABILITY_ID,)


def test_additive_projection_preserves_legacy_credential_semantics(tmp_path):
    startup, _, _ = _startup(tmp_path)
    path = _path(startup.production_composition)

    assert path.status is ExecutionPathStatus.PREREQUISITES_REQUIRED
    assert path.runtime_handoff_ready is False
    assert path.steps[0].handoff_ready is False
    legacy = startup.production_composition.runtime_integration.project(
        RuntimeIntegrationRequest(path)
    )
    assert legacy.status is RuntimeIntegrationStatus.BLOCKED
    assert legacy.projection is None

    satisfaction = (
        adapt_credential_readiness_to_runtime_prerequisite_satisfaction(
            execution_path=path,
            credential_readiness=startup.credential_readiness,
        )
    )
    projected = (
        startup.production_composition.runtime_integration
        .project_with_prerequisite_satisfaction(
            RuntimeIntegrationPrerequisiteRequest(path, satisfaction)
        )
    )

    assert projected.status is RuntimeIntegrationStatus.READY
    assert projected.projection is not None
    assert projected.projection.runtime_ready is True
    assert projected.projection.runtime_allowed is False
    assert projected.projection.execution_allowed is False
    assert projected.projection.prerequisite_satisfaction is satisfaction
    assert path.status is ExecutionPathStatus.PREREQUISITES_REQUIRED
    assert path.runtime_handoff_ready is False
    with pytest.raises(FrozenInstanceError):
        satisfaction.satisfied = False


def test_credential_satisfaction_fails_closed_for_missing_not_ready_and_identity(
    tmp_path,
):
    startup, _, _ = _startup(tmp_path)
    path = _path(startup.production_composition)
    service = startup.production_composition.runtime_integration
    missing = service.project_with_prerequisite_satisfaction(
        RuntimeIntegrationPrerequisiteRequest(path, None)
    )
    assert missing.status is RuntimeIntegrationStatus.BLOCKED
    assert missing.projection is None

    not_ready = ProductionAdapterCredentialReadinessService().assess(
        startup.descriptor,
        _evidence(ready=False),
    )
    assert not_ready.status is CredentialReadinessStatus.NOT_READY
    with pytest.raises(ProductionAdapterRuntimeStartupPrerequisiteError):
        adapt_credential_readiness_to_runtime_prerequisite_satisfaction(
            execution_path=path,
            credential_readiness=not_ready,
        )

    valid = adapt_credential_readiness_to_runtime_prerequisite_satisfaction(
        execution_path=path,
        credential_readiness=startup.credential_readiness,
    )
    for changed in (
        replace(valid, path_id="EXECPATH-FFFFFFFFFFFFFFFF"),
        replace(valid, adapter_id="adapter.other"),
        replace(valid, capability_id="CAP-OTHER-0001"),
    ):
        result = service.project_with_prerequisite_satisfaction(
            RuntimeIntegrationPrerequisiteRequest(path, changed)
        )
        assert result.status is RuntimeIntegrationStatus.BLOCKED
        assert result.projection is None

    with pytest.raises(InvalidRuntimeIntegrationRequestError):
        replace(valid, evidence_reference="api_key=secret")


def test_real_codex_factory_target_and_runtime_execution_chain(tmp_path):
    calls = []

    def runner(argv, **kwargs):
        calls.append((argv, kwargs))
        return SimpleNamespace(returncode=0, stdout="Python test", stderr="")

    executor = ControlledExecutor(tmp_path, runner=runner)
    startup, factory, target = _startup(tmp_path, executor=executor)
    assert factory._bridges == {}
    path = _path(startup.production_composition)
    satisfaction = (
        adapt_credential_readiness_to_runtime_prerequisite_satisfaction(
            execution_path=path,
            credential_readiness=startup.credential_readiness,
        )
    )
    runtime = (
        startup.production_composition.runtime_integration
        .project_with_prerequisite_satisfaction(
            RuntimeIntegrationPrerequisiteRequest(path, satisfaction)
        )
    )
    assert runtime.projection is not None
    tool_request = ToolAdapterRequest(runtime.projection)
    adapter_result = startup.production_composition.tool_adapter_contract.bind(
        tool_request
    )
    assert adapter_result.status is ToolAdapterContractStatus.VALIDATED
    binding = adapter_result.binding
    assert binding is not None
    authority = ProductionAdapterRuntimeExecutionAuthority(
        authority_reference=(
            "RUNTIME-EXECUTION-AUTHORITY-" + uuid4().hex.upper()
        ),
        adapter_id=binding.adapter_id,
        projection_id=binding.projection_id,
        path_id=binding.path_id,
        capability_id=binding.capability_id,
        binding_id=binding.binding_id,
    )
    request = ProductionAdapterRuntimeExecutionRequest(
        startup_composition=startup,
        tool_adapter_request=tool_request,
        binding=binding,
        authority=authority,
        invocation_metadata_references=(
            "INVOCATION-REFERENCE-CODEX-AFDE-6.18",
        ),
    )

    result = ProductionAdapterRuntimeExecutionService().execute(request)

    assert result.adapter_id == ADAPTER_ID
    assert result.projection_id == runtime.projection.projection_id
    assert result.path_id == path.path_id
    assert result.capability_id == CAPABILITY_ID
    assert result.binding_id == binding.binding_id
    assert calls and calls[0][0][1:] == ["--version"]
    assert target.last_execution_result is not None
    assert target.last_execution_result.status == "SUCCEEDED"
    assert factory._bridges == {}
    with pytest.raises(ProductionAdapterRuntimeExecutionAuthorityReuseError):
        ProductionAdapterRuntimeExecutionService().execute(request)


def test_controlled_execution_rejects_windows_absolute_and_workspace_escape(
    tmp_path,
):
    executor = ControlledExecutor(tmp_path)
    action = _tool_action(tmp_path)
    context = _approval_context(tmp_path)
    for target_path in (r"C:\outside.py", "../outside.py"):
        unsafe = replace(
            action,
            action_id=f"AFDE-6.18-{uuid4().hex}",
            action_type=ToolActionType.FILE_WRITE,
            target=target_path,
            arguments={"content": "print('blocked')"},
        )
        bridge = CodexAutomationBridge(tmp_path, executor=executor)
        result = bridge.execute(unsafe, context)
        assert result.status == "DENIED"
