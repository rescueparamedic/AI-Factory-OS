from afde.providers import MockAIProvider, ProviderResponse


def test_mock_provider_is_deterministic_and_network_free():
    provider = MockAIProvider()

    first = provider.generate("  describe beta  ")
    second = provider.generate("describe beta")

    assert first == second
    assert isinstance(first, ProviderResponse)
    assert first.provider == "mock"
    assert first.model == "deterministic-mock-v1"
    assert first.content == "Mock response: describe beta"
    assert first.metadata["execution_mode"] == "deterministic_mock"
