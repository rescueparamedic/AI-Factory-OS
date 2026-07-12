from __future__ import annotations

from typing import Any, Iterable

from .errors import ProviderConfigurationError
from .openai_provider import (
    OpenAIConfig,
    OpenAIProvider,
    _SYSTEM_INSTRUCTIONS,
    safe_error_diagnostics,
    structured_output_config,
)


PROBE_NAMES = ("A", "B", "C")
_MINIMAL_INPUT = "Reply with exactly OK"


class OpenAIResponsesProbe:
    """Minimal opt-in Responses API diagnostics, independent of Factory Runtime."""

    def __init__(
        self,
        model: str | None = None,
        allow_live_api: bool = False,
        client: Any | None = None,
        config: OpenAIConfig | None = None,
    ) -> None:
        self.model = model
        self.allow_live_api = allow_live_api
        self.client = client
        self.config = config

    def run(self, probe_name: str) -> dict:
        name = probe_name.upper()
        if name not in PROBE_NAMES:
            raise ProviderConfigurationError(f"Unknown OpenAI probe: {probe_name}")
        if not self.allow_live_api:
            raise ProviderConfigurationError(
                "OpenAI probe requires explicit --allow-live-api opt-in; no call was made"
            )
        config = self.config or OpenAIConfig.from_env(self.model)
        provider = OpenAIProvider(config, self.client)
        try:
            response = provider.client.responses.create(**probe_request(name, config.model))
        except Exception as exc:
            diagnostics = safe_error_diagnostics(exc, config.api_key)
            return {
                "probe": name,
                "status": "failed",
                "http_status": diagnostics["http_status"],
                "error_type": diagnostics["error_type"],
                "code": diagnostics["error_code"],
                "param": diagnostics["param"],
                "request_id": diagnostics["request_id"],
                "message": diagnostics["message"],
            }
        output_text = getattr(response, "output_text", None)
        return {
            "probe": name,
            "status": "success",
            "model": getattr(response, "model", None) or config.model,
            "response_id": getattr(response, "id", None),
            "output_text_length": len(output_text) if isinstance(output_text, str) else 0,
        }

    def run_many(self, probe_names: Iterable[str] = PROBE_NAMES) -> dict:
        results = [self.run(name) for name in probe_names]
        return {"results": results, "classification": classify_probe_results(results)}


def probe_request(probe_name: str, model: str) -> dict:
    name = probe_name.upper()
    request = {"model": model, "input": _MINIMAL_INPUT}
    if name == "B":
        request["instructions"] = "Reply briefly."
    elif name == "C":
        request.update(
            instructions=_SYSTEM_INSTRUCTIONS["pm_worker"],
            input="Create a minimal plan.",
            text=structured_output_config("pm_worker"),
        )
    elif name != "A":
        raise ProviderConfigurationError(f"Unknown OpenAI probe: {probe_name}")
    return request


def classify_probe_results(results: list[dict]) -> str:
    by_name = {item["probe"]: item for item in results}
    if by_name.get("A", {}).get("status") == "failed":
        return "api_account_model_or_transport"
    if by_name.get("A", {}).get("status") == "success" and by_name.get("B", {}).get("status") == "failed":
        return "instructions_path"
    if all(by_name.get(name, {}).get("status") == "success" for name in ("A", "B")) and by_name.get("C", {}).get("status") == "failed":
        return "structured_output_or_schema"
    if all(by_name.get(name, {}).get("status") == "success" for name in PROBE_NAMES):
        return "all_probes_successful"
    return "incomplete_probe_sequence"
