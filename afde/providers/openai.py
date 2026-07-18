"""Minimal opt-in OpenAI Responses API provider."""
from __future__ import annotations

import os
from typing import Any

from .base import AIProvider
from .errors import (
    LiveAPIBlockedError, ProviderConfigurationError, ProviderRequestError,
    ProviderResponseError,
)
from .models import ProviderResponse


DEFAULT_OPENAI_MODEL = "gpt-4.1-mini"


class OpenAIProvider(AIProvider):
    provider_name = "openai"

    def __init__(
        self, model: str | None = None, *, allow_live_api: bool = False,
        client: Any | None = None,
    ) -> None:
        if not allow_live_api:
            raise LiveAPIBlockedError(
                "OpenAI calls require explicit --allow-live-api opt-in; no call was made"
            )
        api_key = os.environ.get("OPENAI_API_KEY", "").strip()
        if not api_key:
            raise ProviderConfigurationError(
                "OPENAI_API_KEY is required for the openai provider"
            )
        self.model = (model or DEFAULT_OPENAI_MODEL).strip()
        if not self.model:
            raise ProviderConfigurationError("OpenAI model must not be empty")
        self._client = client if client is not None else self._create_client(api_key)

    @staticmethod
    def _create_client(api_key: str):
        try:
            from openai import OpenAI
        except ImportError as exc:
            raise ProviderConfigurationError(
                "The openai package is required for the openai provider"
            ) from exc
        return OpenAI(api_key=api_key)

    def generate(self, request: str) -> ProviderResponse:
        value = _request(request)
        try:
            response = self._client.responses.create(
                model=self.model, input=value,
            )
        except Exception as exc:
            raise ProviderRequestError(
                f"OpenAI request failed ({type(exc).__name__})"
            ) from None
        content = getattr(response, "output_text", None)
        if not isinstance(content, str) or not content.strip():
            raise ProviderResponseError("OpenAI returned an empty response")
        response_model = getattr(response, "model", None) or self.model
        metadata: dict[str, Any] = {
            "execution_mode": "live",
            "request_id": getattr(response, "_request_id", None)
            or getattr(response, "id", None),
        }
        usage = getattr(response, "usage", None)
        if usage is not None:
            metadata["usage"] = _usage(usage)
        return ProviderResponse(
            provider=self.provider_name,
            model=str(response_model),
            content=content.strip(),
            metadata=metadata,
        )


def _request(value: str) -> str:
    if not isinstance(value, str) or not value.strip():
        raise ValueError("provider request must not be empty")
    return value.strip()


def _usage(value: Any) -> dict[str, Any]:
    if hasattr(value, "model_dump"):
        return dict(value.model_dump())
    if isinstance(value, dict):
        return dict(value)
    return {
        key: item
        for key in ("input_tokens", "output_tokens", "total_tokens")
        if (item := getattr(value, key, None)) is not None
    }
