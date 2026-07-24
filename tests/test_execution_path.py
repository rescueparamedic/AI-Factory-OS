from dataclasses import FrozenInstanceError, replace
from pathlib import Path

import pytest

from afde.execution_path import (
    ExecutionPathRequest,
    ExecutionPathService,
    ExecutionPathStatus,
    InvalidExecutionPathMetadataError,
    InvalidExecutionPathRequestError,
    RuntimeHandoffProjection,
)
from afde.knowledge import KnowledgeFoundationProvider
from afde.resolver import (
    CapabilityRequirement,
    CapabilityResolver,
    ResolutionStatus,
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
    ToolAdapterCandidate,
    ToolAdapterSelectionRequest,
    ToolAdapterSelectionService,
    ToolAdapterSelectionStatus,
)


ROOT = Path(__file__).resolve().parents[1]
CAPABILITY_ID = "CAP-KNOW-0001"


class CandidateSource:
    def __init__(self, candidates):
        self.candidates = candidates

    def list_candidates(self):
        return self.candidates


class CatalogSource:
    def __init__(self, descriptor):
        self.descriptor = descriptor
        self.calls = []

    def get_adapter(self, adapter_id):
        self.calls.append(adapter_id)
        return self.descriptor


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


def _resolution():
    return CapabilityResolver(
        KnowledgeFoundationProvider(ROOT)
    ).resolve(CapabilityRequirement(capability_id=CAPABILITY_ID))


def _selection(descriptor=None):
    catalog = ToolAdapterCatalog([descriptor or _descriptor()])
    return ToolAdapterSelectionService(catalog).select(
        ToolAdapterSelectionRequest(_resolution())
    )


def _path(descriptor=None, selection=None):
    descriptor = descriptor or _descriptor()
    result = ExecutionPathService(
        ToolAdapterCatalog([descriptor])
    ).build(ExecutionPathRequest(selection or _selection(descriptor)))
    return result


def test_valid_selection_constructs_deterministic_immutable_path():
    selection = _selection()
    service = ExecutionPathService(ToolAdapterCatalog([_descriptor()]))
    request = ExecutionPathRequest(selection)

    first = service.build(request)
    second = service.build(request)

    assert first == second
    assert first.status is ExecutionPathStatus.CONSTRUCTED
    assert first.path_id.startswith("EXECPATH-")
    assert first.path_constructed is True
    assert first.runtime_handoff_ready is True
    assert first.adapter_id == "adapter.local"
    assert first.capability_id == CAPABILITY_ID
    assert len(first.steps) == 1
    assert first.steps[0].sequence == 1
    assert first.runtime_allowed is False
    assert first.execution_allowed is False
    with pytest.raises(FrozenInstanceError):
        request.selection_result = None
    with pytest.raises(FrozenInstanceError):
        first.path_id = "changed"
    with pytest.raises(FrozenInstanceError):
        first.steps[0].adapter_id = "changed"


def test_path_preserves_catalog_selection_and_resolver_metadata():
    descriptor = _descriptor()
    selection = _selection(descriptor)
    result = _path(descriptor, selection)
    step = result.steps[0]

    assert step.adapter_id == selection.selected_adapter.adapter_id
    assert step.capability_id == selection.capability_id
    assert step.adapter_version == descriptor.version
    assert step.availability is descriptor.availability
    assert step.runtime_compatibility is descriptor.runtime_compatibility
    assert step.execution_contract is descriptor.execution_contract
    assert step.privacy_classification is descriptor.privacy_classification
    assert step.cost_classification is descriptor.cost_classification
    assert step.credentials_required is descriptor.credentials_required
    assert step.metadata_references == descriptor.metadata_references
    assert result.resolver_status is selection.resolver_status
    assert result.gaps == selection.gaps
    assert result.rejection_reasons == selection.rejection_reasons
    assert result.source_documents == selection.source_documents
    assert result.reference_priority == selection.reference_priority
    assert result.ordered_rationale == selection.ordered_rationale
    assert result.resolver_trace == selection.resolver_trace
    assert result.selection_rationale == selection.selection_rationale
    assert result.selection_trace == selection.selection_trace


def test_result_defensively_snapshots_all_sequence_projections():
    result = _path()

    for field_name in (
        "steps",
        "gaps",
        "rejection_reasons",
        "source_documents",
        "reference_priority",
        "ordered_rationale",
        "resolver_trace",
        "selection_rationale",
        "selection_trace",
        "blocked_reasons",
        "trace",
    ):
        assert isinstance(getattr(result, field_name), tuple)
    copied = replace(
        result,
        trace=list(result.trace),
        selection_trace=list(result.selection_trace),
    )
    assert copied.trace == result.trace
    assert copied.selection_trace == result.selection_trace
    with pytest.raises(
        InvalidExecutionPathRequestError, match="sequence of strings",
    ):
        replace(result, trace="not-a-trace")


def test_catalog_dependency_is_constructor_injected_and_used_exactly():
    descriptor = _descriptor()
    catalog = CatalogSource(descriptor)

    result = ExecutionPathService(catalog).build(
        ExecutionPathRequest(_selection(descriptor))
    )

    assert result.status is ExecutionPathStatus.CONSTRUCTED
    assert catalog.calls == ["adapter.local"]
    with pytest.raises(TypeError, match="get_adapter"):
        ExecutionPathService(object())


def test_credentials_are_represented_without_retrieval_or_authority():
    descriptor = _descriptor(credentials_required=True)
    result = _path(descriptor, _selection(descriptor))

    assert result.status is ExecutionPathStatus.PREREQUISITES_REQUIRED
    assert result.path_constructed is True
    assert result.runtime_handoff_ready is False
    assert result.steps[0].credentials_required is True
    assert result.steps[0].handoff_ready is False
    assert result.blocked_reasons == (
        "credentials are required; retrieval and authorization "
        "remain outside Execution Path",
    )
    assert result.runtime_allowed is False
    assert result.execution_allowed is False


def test_optional_catalog_references_do_not_change_readiness():
    descriptor = _descriptor(metadata_references=())
    result = _path(descriptor, _selection(descriptor))

    assert result.status is ExecutionPathStatus.CONSTRUCTED
    assert result.steps[0].metadata_references == ()


@pytest.mark.parametrize(
    ("selection_status", "expected_status"),
    [
        (
            ToolAdapterSelectionStatus.NO_SELECTION,
            ExecutionPathStatus.UNAVAILABLE,
        ),
        (
            ToolAdapterSelectionStatus.BLOCKED,
            ExecutionPathStatus.BLOCKED,
        ),
    ],
)
def test_non_selected_input_returns_structured_blocked_path(
    selection_status, expected_status,
):
    if selection_status is ToolAdapterSelectionStatus.NO_SELECTION:
        selection = ToolAdapterSelectionService(
            CandidateSource(())
        ).select(ToolAdapterSelectionRequest(_resolution()))
    else:
        selection = ToolAdapterSelectionService(CandidateSource((
            ToolAdapterCandidate("adapter.alpha", (CAPABILITY_ID,)),
            ToolAdapterCandidate("adapter.zeta", (CAPABILITY_ID,)),
        ))).select(ToolAdapterSelectionRequest(_resolution()))

    result = ExecutionPathService(
        ToolAdapterCatalog(())
    ).build(ExecutionPathRequest(selection))

    assert result.status is expected_status
    assert result.path_constructed is False
    assert result.runtime_handoff_ready is False
    assert result.adapter_id is None
    assert result.steps == ()
    assert result.blocked_reasons
    assert result.runtime_allowed is False
    assert result.execution_allowed is False


@pytest.mark.parametrize(
    ("resolver_status", "decision_required"),
    [
        (ResolutionStatus.UNRESOLVED, False),
        (ResolutionStatus.BLOCKED, False),
        (ResolutionStatus.DECISION_REQUIRED, True),
    ],
)
def test_non_resolved_upstream_state_is_never_silently_repaired(
    resolver_status, decision_required,
):
    resolution = replace(
        _resolution(),
        capability=None
        if resolver_status is ResolutionStatus.UNRESOLVED
        else _resolution().capability,
        resolution_status=resolver_status,
        eligible=False,
        decision_required=decision_required,
    )
    selection = ToolAdapterSelectionService(
        CandidateSource((ToolAdapterCandidate(
            "adapter.local", (CAPABILITY_ID,),
        ),))
    ).select(ToolAdapterSelectionRequest(resolution))

    result = ExecutionPathService(
        ToolAdapterCatalog([_descriptor()])
    ).build(ExecutionPathRequest(selection))

    assert result.status is ExecutionPathStatus.BLOCKED
    assert result.resolver_status is resolver_status
    assert result.path_constructed is False


@pytest.mark.parametrize(
    ("overrides", "expected_status", "reason"),
    [
        (
            {"availability": AdapterAvailability.UNAVAILABLE},
            ExecutionPathStatus.UNAVAILABLE,
            "unavailable",
        ),
        (
            {
                "runtime_compatibility":
                RuntimeCompatibility.INCOMPATIBLE,
            },
            ExecutionPathStatus.BLOCKED,
            "Runtime-compatible",
        ),
        (
            {
                "runtime_compatibility":
                RuntimeCompatibility.UNVERIFIED,
            },
            ExecutionPathStatus.BLOCKED,
            "Runtime-compatible",
        ),
        (
            {"execution_contract": ExecutionContract.NOT_DECLARED},
            ExecutionPathStatus.BLOCKED,
            "execution contract",
        ),
    ],
)
def test_catalog_prerequisites_fail_closed(
    overrides, expected_status, reason,
):
    descriptor = _descriptor(**overrides)
    selection = ToolAdapterSelectionService(CandidateSource((
        ToolAdapterCandidate("adapter.local", (CAPABILITY_ID,)),
    ))).select(ToolAdapterSelectionRequest(_resolution()))

    result = ExecutionPathService(
        ToolAdapterCatalog([descriptor])
    ).build(ExecutionPathRequest(selection))

    assert result.status is expected_status
    assert result.path_constructed is False
    assert reason in result.blocked_reasons[0]


def test_missing_catalog_adapter_returns_unavailable_path():
    result = ExecutionPathService(ToolAdapterCatalog(())).build(
        ExecutionPathRequest(_selection())
    )

    assert result.status is ExecutionPathStatus.UNAVAILABLE
    assert result.path_constructed is False
    assert "not available in the Catalog" in result.blocked_reasons[0]


@pytest.mark.parametrize(
    "descriptor",
    [
        _descriptor(adapter_id="adapter.other"),
        _descriptor(
            supported_capability_ids=("CAP-RESOLVER-0001",),
        ),
        _descriptor(
            supported_capability_ids=(
                CAPABILITY_ID,
                "CAP-RESOLVER-0001",
            ),
        ),
    ],
)
def test_catalog_and_selection_metadata_conflicts_block(descriptor):
    result = ExecutionPathService(CatalogSource(descriptor)).build(
        ExecutionPathRequest(_selection())
    )

    assert result.status is ExecutionPathStatus.BLOCKED
    assert result.path_constructed is False
    assert "conflict" in result.blocked_reasons[0].lower() or (
        "does not support" in result.blocked_reasons[0]
    )


def test_malformed_catalog_metadata_fails_closed():
    result_source = CatalogSource(object())
    with pytest.raises(
        InvalidExecutionPathMetadataError, match="invalid adapter metadata",
    ):
        ExecutionPathService(result_source).build(
            ExecutionPathRequest(_selection())
        )


def test_missing_or_invalid_selected_identity_fails_closed():
    missing_adapter = _selection()
    object.__setattr__(missing_adapter, "selected_adapter", None)
    with pytest.raises(
        InvalidExecutionPathMetadataError, match="identity is missing",
    ):
        ExecutionPathService(ToolAdapterCatalog([_descriptor()])).build(
            ExecutionPathRequest(missing_adapter)
        )

    missing_capability = _selection()
    object.__setattr__(missing_capability, "capability_id", "")
    with pytest.raises(
        InvalidExecutionPathMetadataError, match="identity is invalid",
    ):
        ExecutionPathService(ToolAdapterCatalog([_descriptor()])).build(
            ExecutionPathRequest(missing_capability)
        )


def test_invalid_request_path_state_and_authority_fail_closed():
    with pytest.raises(
        InvalidExecutionPathRequestError, match="selection_result",
    ):
        ExecutionPathRequest(object())
    service = ExecutionPathService(ToolAdapterCatalog(()))
    with pytest.raises(
        InvalidExecutionPathRequestError, match="request must",
    ):
        service.build(object())

    result = _path()
    with pytest.raises(
        InvalidExecutionPathRequestError, match="construction fields",
    ):
        replace(result, path_constructed=False)
    with pytest.raises(
        InvalidExecutionPathRequestError, match="cannot allow Runtime",
    ):
        replace(result, runtime_allowed=True)
    with pytest.raises(
        InvalidExecutionPathRequestError, match="cannot allow execution",
    ):
        replace(result, execution_allowed=True)


def test_handoff_projection_rejects_invalid_identity_and_metadata():
    step = _path().steps[0]
    with pytest.raises(FrozenInstanceError):
        step.sequence = 2
    with pytest.raises(
        InvalidExecutionPathMetadataError, match="identity is invalid",
    ):
        replace(step, adapter_id=" ")
    with pytest.raises(
        InvalidExecutionPathMetadataError, match="identity is invalid",
    ):
        replace(step, capability_id="invalid")
    with pytest.raises(
        InvalidExecutionPathMetadataError, match="invalid adapter_version",
    ):
        replace(step, adapter_version="v1")
    with pytest.raises(
        InvalidExecutionPathMetadataError, match="invalid execution_contract",
    ):
        replace(step, execution_contract="controlled_runtime")
    with pytest.raises(
        InvalidExecutionPathMetadataError,
        match="invalid runtime_compatibility",
    ):
        replace(step, runtime_compatibility="compatible")
    with pytest.raises(
        InvalidExecutionPathMetadataError, match="conflicts",
    ):
        replace(step, handoff_ready=False)
