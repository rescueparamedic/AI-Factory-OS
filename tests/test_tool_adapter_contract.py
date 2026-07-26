from dataclasses import FrozenInstanceError, replace
from pathlib import Path

import pytest

from afde.execution_path import ExecutionPathRequest, ExecutionPathService
from afde.knowledge import KnowledgeFoundationProvider
from afde.resolver import CapabilityRequirement, CapabilityResolver
from afde.runtime_integration import (
    RuntimeIntegrationPolicy,
    RuntimeIntegrationRequest,
    RuntimeIntegrationService,
)
from afde.tool_adapter_contract import (
    InvalidToolAdapterRequestError,
    InvalidToolAdapterResultError,
    ToolAdapterContractService,
    ToolAdapterContractStatus,
    ToolAdapterErrorCode,
    ToolAdapterRequest,
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


class Lookup:
    def __init__(self, adapters):
        self.adapters = adapters

    def list_adapters(self):
        return self.adapters


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


def _projection(descriptor=None):
    descriptor = descriptor or _descriptor()
    catalog = ToolAdapterCatalog([descriptor])
    resolution = CapabilityResolver(
        KnowledgeFoundationProvider(ROOT)
    ).resolve(CapabilityRequirement(capability_id=CAPABILITY_ID))
    selection = ToolAdapterSelectionService(catalog).select(
        ToolAdapterSelectionRequest(resolution)
    )
    path = ExecutionPathService(catalog).build(
        ExecutionPathRequest(selection)
    )
    policy = RuntimeIntegrationPolicy(
        projection_version="1.0.0",
        required_runtime_compatibility=RuntimeCompatibility.COMPATIBLE,
        required_execution_contract=ExecutionContract.CONTROLLED_RUNTIME,
    )
    return RuntimeIntegrationService(policy).project(
        RuntimeIntegrationRequest(path)
    ).projection


def _bind(adapters=None, projection=None):
    projection = projection or _projection()
    adapters = [_descriptor()] if adapters is None else adapters
    return ToolAdapterContractService(Lookup(adapters)).bind(
        ToolAdapterRequest(projection)
    )


def test_exact_binding_is_immutable_deterministic_and_preserves_identity():
    projection = _projection()
    request = ToolAdapterRequest(projection)
    catalog = ToolAdapterCatalog([_descriptor()])
    service = ToolAdapterContractService(catalog)

    first = service.bind(request)
    second = service.bind(request)

    assert first == second
    assert first.status is ToolAdapterContractStatus.VALIDATED
    assert first.binding.binding_id.startswith("ADAPTERBIND-")
    for name in ("projection_id", "path_id", "capability_id", "adapter_id"):
        assert getattr(request, name) == getattr(projection, name)
        assert getattr(first, name) == getattr(projection, name)
        assert getattr(first.binding, name) == getattr(projection, name)
    assert first.runtime_allowed is False
    assert first.execution_allowed is False
    assert first.binding.runtime_allowed is False
    assert first.binding.execution_allowed is False
    with pytest.raises(FrozenInstanceError):
        request.adapter_id = "adapter.changed"
    with pytest.raises(FrozenInstanceError):
        first.binding = None


def test_lookup_order_does_not_change_binding_or_trace():
    target = _descriptor()
    other = _descriptor(
        adapter_id="adapter.other",
        supported_capability_ids=("CAP-RESOLVER-0001",),
    )

    assert _bind([target, other]) == _bind([other, target])


@pytest.mark.parametrize(
    "adapters, code, trace_fragment",
    [
        ([object()], ToolAdapterErrorCode.MALFORMED, "malformed"),
        (
            [_descriptor(), _descriptor()],
            ToolAdapterErrorCode.DUPLICATE,
            "duplicate",
        ),
        ([], ToolAdapterErrorCode.UNREGISTERED, "unregistered"),
        (
            [_descriptor(version="1.2.4")],
            ToolAdapterErrorCode.MISMATCH,
            "mismatch",
        ),
        (
            [_descriptor(
                supported_capability_ids=("CAP-RESOLVER-0001",),
            )],
            ToolAdapterErrorCode.MISMATCH,
            "mismatch",
        ),
    ],
)
def test_invalid_lookup_and_binding_fail_closed(
    adapters, code, trace_fragment,
):
    result = _bind(adapters)

    assert result.status is ToolAdapterContractStatus.REJECTED
    assert result.binding is None
    assert tuple(error.code for error in result.errors) == (code,)
    assert any(trace_fragment in item for item in result.trace)
    assert result.runtime_allowed is False
    assert result.execution_allowed is False
    error = result.errors[0]
    assert error.projection_id == result.projection_id
    assert error.path_id == result.path_id
    assert error.capability_id == result.capability_id
    assert error.adapter_id == result.adapter_id
    assert error.runtime_allowed is False
    assert error.execution_allowed is False


def test_lookup_exception_and_non_iterable_are_malformed():
    class RaisingLookup:
        def list_adapters(self):
            raise RuntimeError("lookup unavailable")

    for lookup in (RaisingLookup(), Lookup(None), Lookup("adapter.local")):
        projection = _projection()
        result = ToolAdapterContractService(lookup).bind(
            ToolAdapterRequest(projection)
        )
        assert result.errors[0].code is ToolAdapterErrorCode.MALFORMED


def test_forcibly_corrupted_descriptor_is_malformed():
    descriptor = _descriptor()
    object.__setattr__(descriptor, "adapter_id", None)

    result = _bind([descriptor])

    assert result.status is ToolAdapterContractStatus.REJECTED
    assert result.errors[0].code is ToolAdapterErrorCode.MALFORMED


def test_request_lookup_result_and_authority_validation_fail_closed():
    with pytest.raises(
        InvalidToolAdapterRequestError, match="projection",
    ):
        ToolAdapterRequest(object())
    with pytest.raises(TypeError, match="lookup"):
        ToolAdapterContractService(object())
    with pytest.raises(
        InvalidToolAdapterRequestError, match="request must",
    ):
        ToolAdapterContractService(Lookup(())).bind(object())

    request = ToolAdapterRequest(_projection())
    with pytest.raises(
        InvalidToolAdapterRequestError, match="cannot allow Runtime",
    ):
        replace(request, runtime_allowed=True)
    result = _bind()
    with pytest.raises(
        InvalidToolAdapterResultError, match="cannot allow execution",
    ):
        replace(result, execution_allowed=True)
    with pytest.raises(
        InvalidToolAdapterResultError, match="inconsistent",
    ):
        replace(result, binding=None)


def test_corrupted_projection_authority_is_rejected_before_lookup():
    projection = _projection()
    object.__setattr__(projection, "execution_allowed", True)
    request = ToolAdapterRequest.__new__(ToolAdapterRequest)
    object.__setattr__(request, "projection", projection)
    object.__setattr__(request, "projection_id", projection.projection_id)
    object.__setattr__(request, "path_id", projection.path_id)
    object.__setattr__(request, "capability_id", projection.capability_id)
    object.__setattr__(request, "adapter_id", projection.adapter_id)
    object.__setattr__(request, "runtime_allowed", False)
    object.__setattr__(request, "execution_allowed", False)

    with pytest.raises(
        InvalidToolAdapterRequestError,
        match="cannot grant execution authority",
    ):
        ToolAdapterContractService(Lookup(())).bind(request)
