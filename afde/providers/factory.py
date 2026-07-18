"""Explicit provider selection without routing or fallback behavior."""
from __future__ import annotations

from typing import Any

from .base import AIProvider
from .errors import ProviderConfigurationError
from .mock import MockAIProvider
from .openai import OpenAIProvider


class AIProviderFactory:
    @staticmethod
    def create(
        provider: str = "mock", *, model: str | None = None,
        allow_live_api: bool = False, client: Any | None = None,
    ) -> AIProvider:
        name = str(provider or "mock").strip().lower()
        if name == "mock":
            return MockAIProvider()
        if name == "openai":
            return OpenAIProvider(
                model=model, allow_live_api=allow_live_api, client=client,
            )
        raise ProviderConfigurationError(f"Unknown provider: {name}")


def create_provider(
    provider: str = "mock", *, model: str | None = None,
    allow_live_api: bool = False, client: Any | None = None,
) -> AIProvider:
    return AIProviderFactory.create(
        provider, model=model, allow_live_api=allow_live_api, client=client,
    )
