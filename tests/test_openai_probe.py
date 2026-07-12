from types import SimpleNamespace

import pytest

from afde.cli import main
from real_worker_runtime.errors import ProviderConfigurationError
from real_worker_runtime.openai_probe import (
    OpenAIResponsesProbe,
    classify_probe_results,
    probe_request,
)
from real_worker_runtime.openai_provider import OpenAIConfig


class FakeResponses:
    def __init__(self, outcomes):
        self.outcomes = iter(outcomes)
        self.calls = []

    def create(self, **kwargs):
        self.calls.append(kwargs)
        outcome = next(self.outcomes)
        if isinstance(outcome, Exception):
            raise outcome
        return outcome


def client_with(*outcomes):
    return SimpleNamespace(responses=FakeResponses(outcomes))


def success(name="A"):
    return SimpleNamespace(output_text="OK", id=f"resp_{name}", model="test-model")


def bad_request(message="Rejected"):
    error_type = type("BadRequestError", (Exception,), {})
    error = error_type("unused")
    error.status_code = 400
    error.code = "bad_value"
    error.type = "invalid_request_error"
    error.param = "input"
    error.request_id = "req_safe"
    error.response = SimpleNamespace(headers={})
    error.body = {"message": message, "unsafe": "not retained"}
    error.message = "unused"
    return error


def test_probe_payloads_are_isolated():
    a = probe_request("A", "test-model")
    b = probe_request("B", "test-model")
    c = probe_request("C", "test-model")
    assert a == {"model": "test-model", "input": "Reply with exactly OK"}
    assert b == {"model": "test-model", "input": "Reply with exactly OK", "instructions": "Reply briefly."}
    assert set(c) == {"model", "instructions", "input", "text"}
    assert c["input"] == "Create a minimal plan."
    assert c["text"]["format"]["type"] == "json_schema"
    assert c["text"]["format"]["strict"] is True


def test_probe_requires_explicit_opt_in(monkeypatch):
    monkeypatch.delenv("OPENAI_API_KEY", raising=False)
    with pytest.raises(ProviderConfigurationError, match="opt-in"):
        OpenAIResponsesProbe(client=client_with()).run("A")


@pytest.mark.parametrize("name", ["A", "B", "C"])
def test_each_probe_success_returns_allowlisted_summary(name):
    client = client_with(success(name))
    result = OpenAIResponsesProbe(
        allow_live_api=True,
        client=client,
        config=OpenAIConfig("test-placeholder", "test-model"),
    ).run(name)
    assert result == {
        "probe": name,
        "status": "success",
        "model": "test-model",
        "response_id": f"resp_{name}",
        "output_text_length": 2,
    }
    assert "output_text" not in result


@pytest.mark.parametrize("name", ["A", "B", "C"])
def test_each_probe_failure_returns_safe_diagnostics(name):
    result = OpenAIResponsesProbe(
        allow_live_api=True,
        client=client_with(bad_request()),
        config=OpenAIConfig("test-placeholder", "test-model"),
    ).run(name)
    assert result == {
        "probe": name,
        "status": "failed",
        "http_status": 400,
        "error_type": "invalid_request_error",
        "code": "bad_value",
        "param": "input",
        "request_id": "req_safe",
        "message": "Rejected",
    }
    assert "unsafe" not in str(result)


def test_probe_failure_masks_secrets_and_limits_message():
    unsafe = "Authorization" + ": Bearer hidden " + "sk-" + "sensitivevalue123 " + ("x" * 600)
    result = OpenAIResponsesProbe(
        allow_live_api=True,
        client=client_with(bad_request(unsafe)),
        config=OpenAIConfig("test-placeholder", "test-model"),
    ).run("A")
    assert "hidden" not in result["message"]
    assert "sensitivevalue123" not in result["message"]
    assert len(result["message"]) == 500


@pytest.mark.parametrize(
    ("statuses", "classification"),
    [
        (("failed", "success", "success"), "api_account_model_or_transport"),
        (("success", "failed", "success"), "instructions_path"),
        (("success", "success", "failed"), "structured_output_or_schema"),
        (("success", "success", "success"), "all_probes_successful"),
    ],
)
def test_probe_classification(statuses, classification):
    results = [{"probe": name, "status": status} for name, status in zip(("A", "B", "C"), statuses)]
    assert classify_probe_results(results) == classification


def test_probe_cli_routes_without_network(monkeypatch, capsys):
    monkeypatch.setattr(OpenAIResponsesProbe, "run", lambda self, name: {"probe": name, "status": "success", "model": "test-model", "response_id": None, "output_text_length": 2})
    main(["openai-probe", "--probe", "A", "--model", "test-model", "--allow-live-api"])
    output = capsys.readouterr().out
    assert '"probe": "A"' in output
    assert "OPENAI_API_KEY" not in output
