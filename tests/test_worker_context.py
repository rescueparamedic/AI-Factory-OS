from copy import deepcopy

from real_worker_runtime import RealWorkerRuntime, WorkerContext
from real_worker_runtime.provider_bridge import ProviderBridge


def test_worker_context_creation_uses_independent_structured_fields():
    first = WorkerContext(
        request="implement worker context",
        planner_output={"tasks": ["implement"]},
        task_metadata={"task_id": "AFDE-2.8-PR-1"},
        runtime_evidence={"status": "NOT_VERIFIED"},
        prior_worker_artifacts={"pm_worker": {"goal": "deliver"}},
    )
    second = WorkerContext(request="another task")

    first.outputs["planning_worker"] = {"tasks": ["validate"]}

    assert first["request"] == "implement worker context"
    assert first.get("planner_output") == {"tasks": ["implement"]}
    assert first.task_metadata == {"task_id": "AFDE-2.8-PR-1"}
    assert first.runtime_evidence == {"status": "NOT_VERIFIED"}
    assert first.prior_worker_artifacts == {"pm_worker": {"goal": "deliver"}}
    assert second.outputs == {}
    assert second.prior_worker_artifacts == {}


def test_worker_context_records_planner_output_and_round_trips_for_resume():
    context = WorkerContext(
        request="implement worker context",
        task_metadata={"session_id": "RWS-test"},
        runtime_evidence={"status": "NOT_VERIFIED"},
    )
    planner_output = {"tasks": ["implement", "validate"]}
    context.record_worker_output("planning_worker", planner_output)

    serialized = context.to_dict()
    restored = WorkerContext.from_value(serialized)
    planner_output["tasks"].append("mutated after capture")

    assert restored.planner_output == {"tasks": ["implement", "validate"]}
    assert restored.prior_worker_artifacts["planning_worker"] == restored.planner_output
    assert restored.outputs["planning_worker"] == restored.planner_output
    assert restored.task_metadata == {"session_id": "RWS-test"}
    assert restored.runtime_evidence == {"status": "NOT_VERIFIED"}


def test_runtime_passes_planner_populated_worker_context_to_developer(tmp_path, monkeypatch):
    original_generate = ProviderBridge.generate
    observations = {}

    def capture_generate(provider, worker_id, request, context):
        if worker_id in {"planning_worker", "development_worker"}:
            observations[worker_id] = {
                "identity": id(context),
                "type": type(context),
                "planner_output": deepcopy(context.planner_output),
                "task_metadata": deepcopy(context.task_metadata),
                "runtime_evidence": deepcopy(context.runtime_evidence),
                "prior_worker_artifacts": deepcopy(context.prior_worker_artifacts),
            }
        return original_generate(provider, worker_id, request, context)

    monkeypatch.setattr(ProviderBridge, "generate", capture_generate)

    session = RealWorkerRuntime(tmp_path).run("implement worker context", live=False)
    planning = observations["planning_worker"]
    development = observations["development_worker"]

    assert session.status == "completed"
    assert planning["type"] is WorkerContext
    assert development["type"] is WorkerContext
    assert planning["identity"] == development["identity"]
    assert planning["planner_output"] == {}
    assert development["planner_output"]["tasks"]
    assert development["prior_worker_artifacts"]["planning_worker"] == development["planner_output"]
    assert "pm_worker" in development["prior_worker_artifacts"]
    assert development["task_metadata"] == {
        "session_id": session.session_id,
        "sprint_id": session.sprint_id,
        "provider": "mock",
        "current_worker_id": "development_worker",
    }
    assert development["runtime_evidence"]["status"] == "NOT_VERIFIED"


def test_worker_context_restores_legacy_runtime_mapping():
    restored = WorkerContext.from_value({
        "request": "legacy request",
        "outputs": {"planning_worker": {"tasks": ["existing"]}},
        "revision": 1,
    })

    assert restored.request == "legacy request"
    assert restored.outputs == {"planning_worker": {"tasks": ["existing"]}}
    assert restored.revision == 1
    assert restored.planner_output == {}
