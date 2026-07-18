"""Deterministic provider for local tests and product smoke flows."""
from __future__ import annotations

from .base import AIProvider
from .models import ProviderResponse


class MockAIProvider(AIProvider):
    provider_name = "mock"
    model = "deterministic-mock-v1"

    def generate(self, request: str) -> ProviderResponse:
        value = _request(request)
        return ProviderResponse(
            provider=self.provider_name,
            model=self.model,
            content=f"Mock response: {value}",
            metadata={"execution_mode": "deterministic_mock"},
        )


def _request(value: str) -> str:
    if not isinstance(value, str) or not value.strip():
        raise ValueError("provider request must not be empty")
    return value.strip()
