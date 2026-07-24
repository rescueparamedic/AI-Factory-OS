from dataclasses import FrozenInstanceError, replace
from pathlib import Path

import pytest

from afde.knowledge import KnowledgeFoundationProvider
from afde.planner_resolution import (
    PlannerCapabilityResolutionRequest,
    PlannerResolutionService,
)
from afde.resolver import (
    CapabilityRequirement,
    CapabilityResolver,
    ResolutionStatus,
)
from afde.tool_selection import (
    InvalidAdapterCandidateError,
    InvalidToolAdapterSelectionRequestError,
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
        self.calls = 0

    def list_candidates(self):
        self.calls += 1
        return self.candidates


def _resolved():
    return CapabilityResolver(
        KnowledgeFoundationProvider(ROOT)
    ).resolve(CapabilityRequirement(capability_id=CAPABILITY_ID))


def _candidate(adapter_id="ADP-LOCAL-0001", *capability_ids):
    return ToolAdapterCandidate(
        adapter_id=adapter_id,
        capability_ids=capability_ids or (CAPABILITY_ID,),
    )


def _select(resolution=None, candidates=None):
    source = CandidateSource(
        [_candidate()] if candidates is None else candidates
    )
    result = ToolAdapterSelectionService(source).select(
        ToolAdapterSelectionRequest(resolution or _resolved())
    )
    return result, source


def test_exact_capability_match_preserves_identity_and_resolver_projection():
    resolution = _resolved()
    result, source = _select(resolution)

    assert source.calls == 1
    assert result.selection_status is ToolAdapterSelectionStatus.SELECTED
    assert result.selected_adapter == _candidate()
    assert result.selected_adapter.adapter_id == "ADP-LOCAL-0001"
    assert result.capability_id == CAPABILITY_ID
    assert result.resolver_status is resolution.resolution_status
    assert result.gaps == resolution.gaps
    assert result.rejection_reasons == resolution.rejection_reasons
    assert result.source_documents == resolution.source_documents
    assert result.reference_priority == resolution.reference_priority
    assert result.ordered_rationale == resolution.trace
    assert result.resolver_trace == resolution.trace
    assert result.runtime_allowed is False
    assert result.execution_allowed is False


def test_planner_resolution_result_is_accepted_and_preserved():
    resolver = CapabilityResolver(KnowledgeFoundationProvider(ROOT))
    planner_result = PlannerResolutionService(resolver).resolve(
        PlannerCapabilityResolutionRequest(
            planning_result={"goal": "select a local adapter"},
            capability_id=CAPABILITY_ID,
        )
    )
    result, _ = _select(planner_result)

    assert result.resolver_status.value == planner_result.integration_status.value
    assert result.gaps == planner_result.gaps
    assert result.ordered_rationale == planner_result.ordered_rationale
    assert result.resolver_trace == (
        planner_result.capability_resolution_result.trace
    )


def test_selection_is_deterministic_and_does_not_mutate_source_order():
    candidates = [
        _candidate("ADP-ZETA-0001", "CAP-RESOLVER-0001"),
        _candidate("ADP-LOCAL-0001"),
        _candidate("ADP-ALPHA-0001", "CAP-PLANRES-0001"),
    ]
    original = list(candidates)
    source = CandidateSource(candidates)
    service = ToolAdapterSelectionService(source)
    request = ToolAdapterSelectionRequest(_resolved())

    first = service.select(request)
    second = service.select(request)

    assert first == second
    assert first.selection_trace == second.selection_trace
    assert candidates == original
    assert source.calls == 2


def test_request_candidate_and_result_are_immutable():
    request = ToolAdapterSelectionRequest(_resolved())
    candidate = _candidate()
    result, _ = _select(request.resolution_result, [candidate])

    with pytest.raises(FrozenInstanceError):
        request.resolution_result = None
    with pytest.raises(FrozenInstanceError):
        candidate.adapter_id = "ADP-OTHER-0002"
    with pytest.raises(FrozenInstanceError):
        result.execution_allowed = True
    with pytest.raises(
        InvalidToolAdapterSelectionRequestError, match="cannot allow Runtime",
    ):
        replace(result, runtime_allowed=True)
    with pytest.raises(
        InvalidToolAdapterSelectionRequestError, match="cannot allow execution",
    ):
        replace(result, execution_allowed=True)
    with pytest.raises(
        InvalidToolAdapterSelectionRequestError, match="selected_adapter",
    ):
        replace(result, selected_adapter=None)


def test_result_defensively_snapshots_sequence_fields():
    result, _ = _select()

    assert isinstance(result.gaps, tuple)
    assert isinstance(result.source_documents, tuple)
    assert isinstance(result.reference_priority, tuple)
    assert isinstance(result.ordered_rationale, tuple)
    assert isinstance(result.resolver_trace, tuple)
    assert isinstance(result.selection_rationale, tuple)
    assert isinstance(result.selection_trace, tuple)


def test_no_compatible_adapter_fails_closed_without_fuzzy_matching():
    result, _ = _select(
        candidates=[
            _candidate("ADP-OTHER-0001", "CAP-RESOLVER-0001"),
        ]
    )

    assert result.selection_status is ToolAdapterSelectionStatus.NO_SELECTION
    assert result.selected_adapter is None
    assert result.selection_rationale == (
        f"no adapter supports exact capability {CAPABILITY_ID}",
    )
    assert result.selection_trace[-1] == "04.selection.none"


@pytest.mark.parametrize(
    ("status", "decision_required"),
    [
        (ResolutionStatus.UNRESOLVED, False),
        (ResolutionStatus.BLOCKED, False),
        (ResolutionStatus.DECISION_REQUIRED, True),
    ],
)
def test_non_selectable_resolver_status_blocks_without_reading_candidates(
    status, decision_required,
):
    resolution = replace(
        _resolved(),
        capability=None if status is ResolutionStatus.UNRESOLVED else (
            _resolved().capability
        ),
        resolution_status=status,
        eligible=False,
        decision_required=decision_required,
    )
    source = CandidateSource([_candidate()])

    result = ToolAdapterSelectionService(source).select(
        ToolAdapterSelectionRequest(resolution)
    )

    assert result.selection_status is ToolAdapterSelectionStatus.BLOCKED
    assert result.selected_adapter is None
    assert result.resolver_status is status
    assert source.calls == 0
    assert result.runtime_allowed is False
    assert result.execution_allowed is False


def test_duplicate_exact_matches_are_ambiguous_in_stable_identity_order():
    result, _ = _select(candidates=[
        _candidate("ADP-ZETA-0001"),
        _candidate("ADP-ALPHA-0001"),
    ])

    assert result.selection_status is ToolAdapterSelectionStatus.BLOCKED
    assert result.selected_adapter is None
    assert result.selection_rationale == (
        "multiple authoritative adapters support exact capability "
        f"{CAPABILITY_ID}: ADP-ALPHA-0001,ADP-ZETA-0001",
    )
    assert result.selection_trace[-1] == "04.selection.ambiguous"


def test_duplicate_adapter_id_and_invalid_candidate_metadata_fail_closed():
    duplicate = _candidate()
    with pytest.raises(InvalidAdapterCandidateError, match="duplicate"):
        _select(candidates=[duplicate, duplicate])
    with pytest.raises(InvalidAdapterCandidateError, match="invalid"):
        ToolAdapterCandidate(" ", (CAPABILITY_ID,))
    with pytest.raises(InvalidAdapterCandidateError, match="non-empty tuple"):
        ToolAdapterCandidate("ADP-LOCAL-0001", ())
    with pytest.raises(InvalidAdapterCandidateError, match="invalid"):
        _select(candidates=[object()])


def test_invalid_request_and_inconsistent_resolver_result_fail_closed():
    service = ToolAdapterSelectionService(CandidateSource([_candidate()]))
    with pytest.raises(
        InvalidToolAdapterSelectionRequestError, match="request must",
    ):
        service.select(object())
    with pytest.raises(
        InvalidToolAdapterSelectionRequestError, match="resolution_result",
    ):
        ToolAdapterSelectionRequest(object())

    inconsistent = replace(
        _resolved(),
        resolution_status=ResolutionStatus.BLOCKED,
        eligible=True,
    )
    with pytest.raises(
        InvalidToolAdapterSelectionRequestError, match="inconsistent",
    ):
        service.select(ToolAdapterSelectionRequest(inconsistent))


def test_constructor_requires_injected_candidate_source():
    with pytest.raises(TypeError, match="list_candidates"):
        ToolAdapterSelectionService(object())
