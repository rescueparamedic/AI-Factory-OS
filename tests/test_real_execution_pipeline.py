from afde.execution import RealExecutionPipeline, SingleWorkerExecutionAdapter
from afde.providers import AIProvider, ProviderResponse


class RecordingProvider(AIProvider):
    def __init__(self):
        self.requests = []

    def generate(self, request: str) -> ProviderResponse:
        self.requests.append(request)
        return ProviderResponse(
            provider="mock", model="pipeline-test-model",
            content=f"Execute: {request}",
            metadata={"execution_mode": "deterministic_mock"},
        )


def test_pipeline_connects_planner_provider_and_one_sequential_worker():
    provider = RecordingProvider()
    worker_calls = []

    def worker(value):
        worker_calls.append((value.task_id, value.worker_id, value.instruction))
        return {"accepted": True, "instruction": value.instruction}

    adapter = SingleWorkerExecutionAdapter(
        "development_worker", executor=worker,
    )
    pipeline = RealExecutionPipeline(
        provider, worker_id="development_worker", adapter=adapter,
    )

    results = pipeline.run("Prepare AFDE-4.0 Beta")

    assert len(results) == 3
    assert len(provider.requests) == 3
    assert [item[0] for item in worker_calls] == [result.task_id for result in results]
    assert {result.worker_id for result in results} == {"development_worker"}
    assert all(result.execution_status == "completed" for result in results)
    assert all(result.output["accepted"] is True for result in results)
    assert pipeline.last_evidence == {
        "provider": "mock", "model": "pipeline-test-model",
        "execution_mode": "deterministic_mock",
        "plan_id": results[-1].plan_id,
        "worker_id": "development_worker", "execution_status": "completed",
    }
