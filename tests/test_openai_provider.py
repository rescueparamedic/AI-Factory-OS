from types import SimpleNamespace

import httpx
import json
import pytest
from openai import BadRequestError

from real_worker_runtime.errors import (
    ProviderAuthenticationError,
    ProviderBadRequestError,
    ProviderConfigurationError,
    ProviderRateLimitError,
    ProviderResponseError,
    ProviderTimeoutError,
)
from real_worker_runtime.openai_provider import OpenAIConfig, OpenAIProvider
from real_worker_runtime.provider_bridge import ProviderBridge


class FakeResponses:
    def __init__(self, response=None, error=None):
        self.response = response
        self.error = error
        self.calls = []

    def create(self, **kwargs):
        self.calls.append(kwargs)
        if self.error:
            raise self.error
        return self.response


def fake_client(response=None, error=None):
    return SimpleNamespace(responses=FakeResponses(response, error))


def test_config_from_environment(monkeypatch):
    monkeypatch.setenv("OPENAI_API_KEY", "test-placeholder")
    monkeypatch.setenv("AI_FACTORY_OPENAI_MODEL", "test-model")
    monkeypatch.setenv("AI_FACTORY_OPENAI_TIMEOUT_SECONDS", "12.5")
    monkeypatch.setenv("AI_FACTORY_OPENAI_MAX_RETRIES", "4")
    config = OpenAIConfig.from_env()
    assert (config.model, config.timeout_seconds, config.max_retries) == ("test-model", 12.5, 4)
    assert "test-placeholder" not in repr(config)


def test_missing_api_key(monkeypatch):
    monkeypatch.delenv("OPENAI_API_KEY", raising=False)
    with pytest.raises(ProviderConfigurationError, match="OPENAI_API_KEY"):
        OpenAIConfig.from_env()


def test_bridge_selects_openai_only_with_opt_in(monkeypatch, tmp_path):
    monkeypatch.setenv("OPENAI_API_KEY", "test-placeholder")
    with pytest.raises(ProviderConfigurationError, match="opt-in"):
        ProviderBridge(tmp_path).select("openai")
    bridge = ProviderBridge(tmp_path, model="test-model", allow_live_api=True, openai_client=fake_client())
    assert bridge.select("openai") == {"provider": "openai", "mode": "live", "model": "test-model"}


def test_normalizes_response_and_usage():
    response = SimpleNamespace(
        output_text='{"passed": 1, "failed": 0, "recommendation": "PASS"}',
        id="resp_test",
        model="test-model",
        usage=SimpleNamespace(input_tokens=10, output_tokens=5, total_tokens=15),
    )
    provider = OpenAIProvider(OpenAIConfig("test-placeholder", "test-model"), fake_client(response))
    result = provider.generate("qa_worker", "test", {"outputs": {}})
    assert result["recommendation"] == "PASS"
    assert result["_provider"] == {
        "provider": "openai",
        "model": "test-model",
        "request_id": "resp_test",
        "usage": {"input_tokens": 10, "output_tokens": 5, "total_tokens": 15},
    }


def test_request_uses_responses_structured_output():
    response = SimpleNamespace(
        output_text='{"request_summary":"x","goal":"y","constraints":[],"definition_of_done":[],"risk_notes":[]}',
        id="resp_test",
        model="test-model",
    )
    client = fake_client(response)
    OpenAIProvider(OpenAIConfig("test-placeholder", "test-model"), client).generate(
        "pm_worker", "safe request", {"outputs": {}}
    )
    call = client.responses.calls[0]
    assert set(call) == {"model", "instructions", "input", "text"}
    assert call["text"]["format"]["type"] == "json_schema"
    assert call["text"]["format"]["strict"] is True
    assert call["text"]["format"]["schema"]["additionalProperties"] is False
    assert "OPENAI_API_KEY" not in str(call)


@pytest.mark.parametrize(
    ("error", "expected"),
    [
        (TimeoutError("timed out"), ProviderTimeoutError),
        (type("RateLimitError", (Exception,), {})("429"), ProviderRateLimitError),
        (type("AuthenticationError", (Exception,), {})("bad key"), ProviderAuthenticationError),
    ],
)
def test_structured_errors(error, expected):
    provider = OpenAIProvider(OpenAIConfig("test-placeholder"), fake_client(error=error))
    with pytest.raises(expected) as caught:
        provider.generate("pm_worker", "test", {"outputs": {}})
    assert "test-placeholder" not in str(caught.value)


def test_malformed_response():
    response = SimpleNamespace(output_text="not-json", id="resp_test", model="test-model")
    provider = OpenAIProvider(OpenAIConfig("test-placeholder"), fake_client(response))
    with pytest.raises(ProviderResponseError, match="valid JSON"):
        provider.generate("pm_worker", "test", {"outputs": {}})


def test_bad_request_preserves_only_safe_diagnostics():
    error_type = type("BadRequestError", (Exception,), {})
    error = error_type("unsafe raw exception")
    error.status_code = 400
    error.request_id = "req_safe"
    error.response = SimpleNamespace(headers={"authorization": "Bearer secret"})
    error.body = {
        "error": {
            "message": "Invalid schema; Authorization" + ": Bearer hidden " + "sk-" + "sensitive123456",
            "type": "invalid_request_error",
            "param": "text.format.schema",
            "code": "invalid_json_schema",
        },
        "request": {"input": "must not be preserved"},
    }
    provider = OpenAIProvider(OpenAIConfig("test-placeholder"), fake_client(error=error))
    with pytest.raises(ProviderBadRequestError) as caught:
        provider.generate("pm_worker", "private body", {"outputs": {}})
    diagnostics = caught.value.diagnostics
    assert diagnostics == {
        "provider": "openai",
        "category": "bad_request",
        "http_status": 400,
        "error_code": "invalid_json_schema",
        "error_type": "invalid_request_error",
        "param": "text.format.schema",
        "request_id": "req_safe",
        "message": "Invalid schema; Authorization: [REDACTED] [REDACTED]",
    }
    serialized = str(caught.value)
    assert "must not be preserved" not in serialized
    assert "hidden" not in serialized
    assert "sensitive123456" not in serialized


def test_sdk_2_41_bad_request_shape_is_preserved():
    request = httpx.Request("POST", "https://api.openai.com/v1/responses")
    response = httpx.Response(
        400, headers={"x-request-id": "req_sdk_shape"}, request=request
    )
    error = BadRequestError(
        "Error code: 400",
        response=response,
        body={
            "message": "Invalid schema for response_format",
            "type": "invalid_request_error",
            "param": "text.format.schema",
            "code": "invalid_json_schema",
        },
    )
    provider = OpenAIProvider(OpenAIConfig("test-placeholder"), fake_client(error=error))
    with pytest.raises(ProviderBadRequestError) as caught:
        provider.generate("pm_worker", "test", {"outputs": {}})
    assert caught.value.diagnostics == {
        "provider": "openai",
        "category": "bad_request",
        "http_status": 400,
        "error_code": "invalid_json_schema",
        "error_type": "invalid_request_error",
        "param": "text.format.schema",
        "request_id": "req_sdk_shape",
        "message": "Invalid schema for response_format",
    }


def test_string_json_body_and_sdk_message_fallback_are_safe():
    error_type = type("BadRequestError", (Exception,), {})
    error = error_type("unused")
    error.status_code = 400
    error.request_id = None
    error.response = SimpleNamespace(headers={"request-id": "req_fallback"})
    error.body = json.dumps({
        "error": {
            "message": "Bad value " + "sk-" + "maskedvalue123",
            "type": "invalid_request_error",
            "param": "input",
            "code": "bad_value",
        },
        "unsafe_extra": "not retained",
    })
    error.message = "fallback should not replace server message"
    provider = OpenAIProvider(OpenAIConfig("test-placeholder"), fake_client(error=error))
    with pytest.raises(ProviderBadRequestError) as caught:
        provider.generate("pm_worker", "private request", {"outputs": {}})
    diagnostics = caught.value.diagnostics
    assert diagnostics["message"] == "Bad value [REDACTED]"
    assert diagnostics["request_id"] == "req_fallback"
    assert diagnostics["error_code"] == "bad_value"
    assert "unsafe_extra" not in str(caught.value)


def test_non_json_body_uses_sanitized_sdk_message():
    error_type = type("BadRequestError", (Exception,), {})
    error = error_type("unused")
    error.status_code = 400
    error.request_id = None
    error.response = SimpleNamespace(headers={})
    error.body = "upstream returned non-json"
    error.message = "Server rejected Authorization" + ": Bearer hidden-token"
    provider = OpenAIProvider(OpenAIConfig("test-placeholder"), fake_client(error=error))
    with pytest.raises(ProviderBadRequestError) as caught:
        provider.generate("pm_worker", "private request", {"outputs": {}})
    assert caught.value.diagnostics["message"] == "Server rejected Authorization: [REDACTED]"
