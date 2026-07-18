from dataclasses import FrozenInstanceError

import pytest

from afde.providers import ProviderResponse


def test_provider_response_is_typed_immutable_and_serializable():
    response = ProviderResponse(
        provider="openai", model="test-model", content="result",
        metadata={"execution_mode": "live", "usage": {"total_tokens": 3}},
    )

    with pytest.raises(FrozenInstanceError):
        response.content = "changed"
    with pytest.raises(TypeError):
        response.metadata["execution_mode"] = "changed"
    with pytest.raises(TypeError):
        response.metadata["usage"]["total_tokens"] = 4

    assert response.to_dict() == {
        "provider": "openai", "model": "test-model", "content": "result",
        "metadata": {"execution_mode": "live", "usage": {"total_tokens": 3}},
    }
