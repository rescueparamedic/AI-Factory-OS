from types import SimpleNamespace
import json

from real_worker_runtime import RealWorkerRuntime


class WorkerResponses:
    def create(self, **kwargs):
        instruction = kwargs["instructions"]
        if "QA worker" in instruction:
            body = '{"tests_run": [], "passed": 1, "failed": 0, "issues": [], "recommendation": "PASS"}'
        else:
            body = '{"result": "completed"}'
        return SimpleNamespace(output_text=body, id="resp_test", model=kwargs["model"])


def test_runtime_openai_provider_with_mocked_client(tmp_path, monkeypatch):
    monkeypatch.setenv("OPENAI_API_KEY", "test-placeholder")
    client = SimpleNamespace(responses=WorkerResponses())
    session = RealWorkerRuntime(tmp_path).run(
        "demo", provider="openai", live=False, allow_live_api=True, openai_client=client
    )
    assert session.status == "completed"
    assert len(session.results) == 5
    assert session.artifacts


def test_runtime_persists_safe_bad_request_diagnostics(tmp_path, monkeypatch):
    monkeypatch.setenv("OPENAI_API_KEY", "test-placeholder")
    error_type = type("BadRequestError", (Exception,), {})
    error = error_type("raw")
    error.status_code = 400
    error.request_id = "req_safe"
    error.response = SimpleNamespace(headers={})
    error.body = {"error": {"message": "Invalid input", "type": "invalid_request_error", "param": "input", "code": "bad_input"}}

    class FailingResponses:
        def create(self, **kwargs):
            raise error

    session = RealWorkerRuntime(tmp_path).run(
        "demo", provider="openai", live=False, allow_live_api=True,
        openai_client=SimpleNamespace(responses=FailingResponses()),
    )
    persisted = json.loads((tmp_path / "data" / "runtime_sessions" / session.session_id / "session.json").read_text())
    events = [json.loads(line) for line in (tmp_path / "data" / "runtime_sessions" / session.session_id / "events.jsonl").read_text().splitlines()]
    provider_event = next(item for item in events if item["event"] == "PROVIDER_ERROR")
    for value in (session.error, persisted["error"], provider_event["detail"]):
        assert '"http_status": 400' in value
        assert '"error_code": "bad_input"' in value
        assert '"request_id": "req_safe"' in value
        assert "test-placeholder" not in value
