from types import SimpleNamespace

import pytest

from afde.providers import (
    LiveAPIBlockedError, MockAIProvider, OpenAIProvider,
    ProviderConfigurationError, create_provider,
)


def test_factory_selects_mock_without_external_configuration():
    assert isinstance(create_provider("mock"), MockAIProvider)


def test_factory_blocks_openai_without_explicit_live_opt_in(monkeypatch):
    monkeypatch.setenv("OPENAI_API_KEY", "test-placeholder")

    with pytest.raises(LiveAPIBlockedError, match="allow-live-api"):
        create_provider("openai", allow_live_api=False)


def test_factory_selects_openai_with_model_and_opt_in(monkeypatch):
    monkeypatch.setenv("OPENAI_API_KEY", "test-placeholder")
    client = SimpleNamespace(responses=SimpleNamespace())

    provider = create_provider(
        "openai", model="test-model", allow_live_api=True, client=client,
    )

    assert isinstance(provider, OpenAIProvider)
    assert provider.model == "test-model"


def test_factory_rejects_unknown_provider():
    with pytest.raises(ProviderConfigurationError, match="Unknown provider"):
        create_provider("unknown")
