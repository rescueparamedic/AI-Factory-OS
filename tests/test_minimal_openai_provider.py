from types import SimpleNamespace

import pytest

from afde.providers import (
    LiveAPIBlockedError, OpenAIProvider, ProviderConfigurationError,
    ProviderRequestError, ProviderResponseError,
)


class RecordingResponses:
    def __init__(self, response=None, error=None):
        self.response = response
        self.error = error
        self.calls = []

    def create(self, **values):
        self.calls.append(values)
        if self.error:
            raise self.error
        return self.response


def test_openai_provider_calls_responses_api_and_normalizes(monkeypatch):
    monkeypatch.setenv("OPENAI_API_KEY", "test-placeholder")
    responses = RecordingResponses(SimpleNamespace(
        output_text="  provider result  ", id="resp_test", model="served-model",
        usage=SimpleNamespace(input_tokens=2, output_tokens=3, total_tokens=5),
    ))
    provider = OpenAIProvider(
        "requested-model", allow_live_api=True,
        client=SimpleNamespace(responses=responses),
    )

    result = provider.generate("Generate one response")

    assert responses.calls == [{
        "model": "requested-model", "input": "Generate one response",
    }]
    assert result.provider == "openai"
    assert result.model == "served-model"
    assert result.content == "provider result"
    assert result.metadata["execution_mode"] == "live"
    assert result.metadata["request_id"] == "resp_test"
    assert result.metadata["usage"]["total_tokens"] == 5


def test_openai_provider_requires_opt_in_before_configuration(monkeypatch):
    monkeypatch.delenv("OPENAI_API_KEY", raising=False)

    with pytest.raises(LiveAPIBlockedError):
        OpenAIProvider(allow_live_api=False)
    with pytest.raises(ProviderConfigurationError, match="OPENAI_API_KEY"):
        OpenAIProvider(allow_live_api=True)


def test_openai_provider_rejects_empty_response(monkeypatch):
    monkeypatch.setenv("OPENAI_API_KEY", "test-placeholder")
    provider = OpenAIProvider(
        allow_live_api=True,
        client=SimpleNamespace(responses=RecordingResponses(SimpleNamespace(
            output_text="", id="resp_empty", model="test-model",
        ))),
    )

    with pytest.raises(ProviderResponseError, match="empty"):
        provider.generate("request")


def test_openai_provider_redacts_key_from_request_failure(monkeypatch):
    secret = "test-secret-value"
    monkeypatch.setenv("OPENAI_API_KEY", secret)
    provider = OpenAIProvider(
        allow_live_api=True,
        client=SimpleNamespace(responses=RecordingResponses(
            error=RuntimeError(f"failed with {secret}"),
        )),
    )

    with pytest.raises(ProviderRequestError) as caught:
        provider.generate("request")
    assert secret not in str(caught.value)


def test_openai_client_disables_retries_and_sets_bounded_timeout(monkeypatch):
    monkeypatch.setenv("OPENAI_API_KEY", "test-placeholder")
    monkeypatch.setenv("AI_FACTORY_OPENAI_TIMEOUT_SECONDS", "12.5")
    observed = {}

    class OpenAI:
        def __init__(self, **kwargs):
            observed.update(kwargs)

    monkeypatch.setitem(
        __import__("sys").modules, "openai", SimpleNamespace(OpenAI=OpenAI),
    )

    OpenAIProvider(allow_live_api=True)

    assert observed["max_retries"] == 0
    assert observed["timeout"] == 12.5
    assert "api_key" in observed


def test_openai_server_error_keeps_only_safe_diagnostics(monkeypatch):
    secret = "test-secret-value"
    monkeypatch.setenv("OPENAI_API_KEY", secret)

    class FakeInternalServerError(RuntimeError):
        status_code = 500
        request_id = "req_safe_identifier"

    provider = OpenAIProvider(
        allow_live_api=True,
        client=SimpleNamespace(responses=RecordingResponses(
            error=FakeInternalServerError(f"raw body with {secret}"),
        )),
    )

    with pytest.raises(ProviderRequestError) as caught:
        provider.generate("request")

    error = caught.value
    assert error.category == "provider_server"
    assert error.status_code == 500
    assert error.request_id == "req_safe_identifier"
    assert error.retryable is True
    assert secret not in str(error)
    assert "raw body" not in str(error)
