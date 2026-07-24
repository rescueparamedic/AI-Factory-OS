from dataclasses import FrozenInstanceError, replace
from pathlib import Path

import pytest

from afde.execution_path import ExecutionPathRequest, ExecutionPathService
from afde.knowledge import KnowledgeFoundationProvider
from afde.resolver import CapabilityRequirement, CapabilityResolver
from afde.runtime_integration import (
    InvalidRuntimeIntegrationRequestError,
    InvalidRuntimeProjectionError,
    RuntimeIntegrationPolicy,
    RuntimeIntegrationRequest,
    RuntimeIntegrationService,
    RuntimeIntegrationStatus,
)
from afde.tool_catalog import (
    AdapterAvailability,
    CostClassification,
    ExecutionContract,
    PrivacyClassification,
    RuntimeCompatibility,
    ToolAdapterCatalog,
    ToolAdapterDescriptor,
)
from afde.tool_selection import (
    ToolAdapterSelectionRequest,
    ToolAdapterSelectionService,
)


ROOT = Path(__file__).resolve().parents[1]
CAPABILITY_ID = "CAP-KNOW-0001"


def _descriptor(**overrides):
    values = {
        "adapter_id": "adapter.local",
        "display_name": "Local Adapter",
        "version": "1.2.3",
        "supported_capability_ids": (CAPABILITY_ID,),
        "availability": AdapterAvailability.AVAILABLE,
        "runtime_compatibility": RuntimeCompatibility.COMPATIBLE,
        "execution_contract": ExecutionContract.CONTROLLED_RUNTIME,
        "privacy_classification": PrivacyClassification.LOCAL,
        "cost_classification": CostClassification.NO_COST,
        "credentials_required": False,
        "description": "Test-only adapter metadata.",
        "metadata_references": ("DOC-TCAT-0001",),
    }
    values.update(overrides)
    return ToolAdapterDescriptor(**values)


def _path(**descriptor_overrides):
    descriptor = _descriptor(**descriptor_overrides)
    resolution = CapabilityResolver(
        KnowledgeFoundationProvider(ROOT)
    ).resolve(CapabilityRequirement(capability_id=CAPABILITY_ID))
    selection = ToolAdapterSelectionService(
        ToolAdapterCatalog([descriptor])
    ).select(ToolAdapterSelectionRequest(resolution))
    return ExecutionPathService(
        ToolAdapterCatalog([descriptor])
    ).build(ExecutionPathRequest(selection))


def _policy(**overrides):
    values = {
        "projection_version": "1.0.0",
        "required_runtime_compatibility": RuntimeCompatibility.COMPATIBLE,
        "required_execution_contract": ExecutionContract.CONTROLLED_RUNTIME,
    }
    values.update(overrides)
    return RuntimeIntegrationPolicy(**values)


def _result(path=None, policy=None):
    return RuntimeIntegrationService(policy or _policy()).project(
        RuntimeIntegrationRequest(path or _path())
    )


def test_ready_path_creates_deterministic_immutable_runtime_projection():
    path = _path()
    request = RuntimeIntegrationRequest(path)
    service = RuntimeIntegrationService(_policy())

    first = service.project(request)
    second = service.project(request)

    assert first == second
    assert first.status is RuntimeIntegrationStatus.READY
    assert first.runtime_ready is True
    assert first.runtime_allowed is False
    assert first.execution_allowed is False
    assert first.path_id == path.path_id
    assert first.adapter_id == path.adapter_id
    assert first.capability_id == path.capability_id
    assert first.path_trace == path.trace
    assert first.projection.projection_id.startswith("RUNTIMEPROJ-")
    assert first.projection.runtime_ready is True
    assert first.projection.runtime_allowed is False
    assert first.projection.execution_allowed is False
    with pytest.raises(FrozenInstanceError):
        request.execution_path = None
    with pytest.raises(FrozenInstanceError):
        first.runtime_ready = False
    with pytest.raises(FrozenInstanceError):
        first.projection.adapter_id = "changed"


def test_projection_preserves_all_handoff_metadata_exactly():
    path = _path()
    step = path.steps[0]
    projection = _result(path).projection

    assert projection.path_id == path.path_id
    assert projection.sequence == step.sequence
    assert projection.adapter_id == step.adapter_id
    assert projection.capability_id == step.capability_id
    assert projection.adapter_version == step.adapter_version
    assert projection.availability is step.availability
    assert projection.runtime_compatibility is step.runtime_compatibility
    assert projection.execution_contract is step.execution_contract
    assert projection.privacy_classification is step.privacy_classification
    assert projection.cost_classification is step.cost_classification
    assert projection.credentials_required is step.credentials_required
    assert projection.metadata_references == step.metadata_references


def test_runtime_result_defensively_snapshots_sequence_fields():
    result = _result()
    path_trace = list(result.path_trace)
    trace = list(result.trace)
    copied = replace(result, path_trace=path_trace, trace=trace)

    path_trace.append("mutated")
    trace.append("mutated")

    assert copied.path_trace == result.path_trace
    assert copied.trace == result.trace


def test_policy_is_constructor_injected_and_changes_identity():
    first = _result(policy=_policy(projection_version="1.0.0"))
    second = _result(policy=_policy(projection_version="1.0.1"))

    assert first.projection.projection_id != second.projection.projection_id
    with pytest.raises(TypeError, match="policy"):
        RuntimeIntegrationService(object())


@pytest.mark.parametrize(
    "path, reason",
    [
        (
            lambda: _path(credentials_required=True),
            "prerequisites",
        ),
    ],
)
def test_non_ready_execution_path_is_blocked(path, reason):
    result = _result(path())

    assert result.status is RuntimeIntegrationStatus.BLOCKED
    assert result.runtime_ready is False
    assert result.projection is None
    assert result.path_id is None
    assert result.adapter_id is None
    assert any(reason in item for item in result.blocked_reasons)
    assert result.runtime_allowed is False
    assert result.execution_allowed is False


def test_policy_mismatch_fails_closed_without_runtime_behavior():
    result = _result(
        policy=_policy(
            required_runtime_compatibility=RuntimeCompatibility.UNVERIFIED,
            required_execution_contract=ExecutionContract.NOT_DECLARED,
        )
    )

    assert result.status is RuntimeIntegrationStatus.BLOCKED
    assert result.runtime_ready is False
    assert result.projection is None
    assert len(result.blocked_reasons) == 2


def test_invalid_request_policy_and_authority_fail_closed():
    with pytest.raises(
        InvalidRuntimeIntegrationRequestError, match="execution_path",
    ):
        RuntimeIntegrationRequest(object())
    with pytest.raises(
        InvalidRuntimeIntegrationRequestError, match="projection_version",
    ):
        _policy(projection_version="latest")
    with pytest.raises(
        InvalidRuntimeIntegrationRequestError, match="request must",
    ):
        RuntimeIntegrationService(_policy()).project(object())
    result = _result()
    with pytest.raises(
        InvalidRuntimeIntegrationRequestError, match="cannot allow Runtime",
    ):
        replace(result, runtime_allowed=True)
    with pytest.raises(
        InvalidRuntimeIntegrationRequestError, match="cannot allow execution",
    ):
        replace(result, execution_allowed=True)


def test_projection_and_result_reject_inconsistent_state():
    result = _result()
    projection = result.projection
    with pytest.raises(InvalidRuntimeProjectionError, match="projection_id"):
        replace(projection, projection_id="random")
    with pytest.raises(InvalidRuntimeProjectionError, match="path_id"):
        replace(projection, path_id="invalid")
    with pytest.raises(InvalidRuntimeProjectionError, match="sequence"):
        replace(projection, sequence=2)
    with pytest.raises(InvalidRuntimeProjectionError, match="metadata"):
        replace(projection, credentials_required=True)
    with pytest.raises(
        InvalidRuntimeIntegrationRequestError, match="conflicts",
    ):
        replace(result, runtime_ready=False)
    with pytest.raises(
        InvalidRuntimeIntegrationRequestError, match="inconsistent",
    ):
        replace(result, blocked_reasons=("blocked",))


def test_corrupted_upstream_authority_is_rejected():
    path = _path()
    object.__setattr__(path, "runtime_allowed", True)
    with pytest.raises(
        InvalidRuntimeIntegrationRequestError,
        match="cannot grant execution authority",
    ):
        _result(path)
