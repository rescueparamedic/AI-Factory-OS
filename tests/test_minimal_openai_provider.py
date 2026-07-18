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
