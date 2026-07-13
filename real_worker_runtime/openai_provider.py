from __future__ import annotations

from dataclasses import dataclass, field
import json
import os
import re
from typing import Any

from .errors import (
    ProviderAuthenticationError,
    ProviderBadRequestError,
    ProviderConfigurationError,
    ProviderRateLimitError,
    ProviderResponseError,
    ProviderTimeoutError,
)


DEFAULT_MODEL = "gpt-4.1-mini"


@dataclass(frozen=True)
class OpenAIConfig:
    api_key: str = field(repr=False)
    model: str = DEFAULT_MODEL
    timeout_seconds: float = 60.0
    max_retries: int = 2

    @classmethod
    def from_env(cls, model: str | None = None) -> "OpenAIConfig":
        api_key = os.environ.get("OPENAI_API_KEY", "").strip()
        if not api_key:
            raise ProviderConfigurationError(
                "OPENAI_API_KEY is required for the openai provider"
            )
        try:
            timeout = float(os.environ.get("AI_FACTORY_OPENAI_TIMEOUT_SECONDS", "60"))
            retries = int(os.environ.get("AI_FACTORY_OPENAI_MAX_RETRIES", "2"))
        except ValueError as exc:
            raise ProviderConfigurationError(
                "OpenAI timeout must be a number and max retries must be an integer"
            ) from exc
        if timeout <= 0 or retries < 0:
            raise ProviderConfigurationError(
                "OpenAI timeout must be positive and max retries cannot be negative"
            )
        return cls(
            api_key=api_key,
            model=(model or os.environ.get("AI_FACTORY_OPENAI_MODEL") or DEFAULT_MODEL).strip(),
            timeout_seconds=timeout,
            max_retries=retries,
        )


class OpenAIProvider:
    """OpenAI Responses API adapter with a stable dictionary result contract."""

    def __init__(self, config: OpenAIConfig, client: Any | None = None) -> None:
        self.config = config
        self.client = client if client is not None else self._create_client()

    def _create_client(self):
        try:
            from openai import OpenAI
        except ImportError as exc:
            raise ProviderConfigurationError(
                "The openai package is required for the openai provider; install project requirements"
            ) from exc
        return OpenAI(
            api_key=self.config.api_key,
            timeout=self.config.timeout_seconds,
            max_retries=self.config.max_retries,
        )

    def generate(self, worker_id: str, request: str, context: dict) -> dict:
        request_args = build_worker_request(worker_id, request, context, self.config.model)
        try:
            response = self.client.responses.create(**request_args)
        except Exception as exc:
            raise _translate_error(exc, self.config.api_key) from None
        return self._normalize(response)

    def _normalize(self, response: Any) -> dict:
        text = getattr(response, "output_text", None)
        request_id = getattr(response, "_request_id", None) or getattr(response, "id", None)
        if not isinstance(text, str) or not text.strip():
            raise ProviderResponseError("OpenAI returned an empty or malformed response")
        try:
            content = json.loads(text)
        except json.JSONDecodeError as exc:
            raise ProviderResponseError("OpenAI response was not valid JSON") from exc
        if not isinstance(content, dict):
            raise ProviderResponseError("OpenAI response JSON must be an object")
        metadata = {
            "provider": "openai",
            "model": getattr(response, "model", None) or self.config.model,
            "request_id": request_id,
        }
        usage = getattr(response, "usage", None)
        if usage is not None:
            metadata["usage"] = _usage_dict(usage)
        content["_provider"] = metadata
        return content


def _usage_dict(usage: Any) -> dict:
    if hasattr(usage, "model_dump"):
        return usage.model_dump()
    if isinstance(usage, dict):
        return dict(usage)
    return {
        key: value
        for key in ("input_tokens", "output_tokens", "total_tokens")
        if (value := getattr(usage, key, None)) is not None
    }


def _translate_error(exc: Exception, api_key: str = "") -> Exception:
    name = type(exc).__name__.lower()
    message = str(exc).lower()
    if "badrequest" in name or getattr(exc, "status_code", None) == 400:
        return ProviderBadRequestError(_safe_diagnostics(exc, api_key))
    if "authentication" in name or "permission" in name or "api key" in message:
        return ProviderAuthenticationError("OpenAI authentication failed; verify OPENAI_API_KEY")
    if "ratelimit" in name or "rate limit" in message or "429" in message:
        return ProviderRateLimitError("OpenAI rate limit exceeded; retry later")
    if "timeout" in name or "timed out" in message:
        return ProviderTimeoutError("OpenAI request timed out")
    return ProviderResponseError(f"OpenAI request failed ({type(exc).__name__})")


def safe_error_diagnostics(exc: Exception, api_key: str = "") -> dict:
    error = _error_fields(getattr(exc, "body", None))
    response = getattr(exc, "response", None)
    headers = getattr(response, "headers", {}) or {}
    raw_message = (
        error.get("message")
        or getattr(exc, "message", None)
        or "OpenAI rejected the request"
    )
    return {
        "provider": "openai",
        "category": "bad_request",
        "http_status": getattr(exc, "status_code", None),
        "error_code": _safe_scalar(getattr(exc, "code", None) or error.get("code")),
        "error_type": _safe_scalar(getattr(exc, "type", None) or error.get("type")) or type(exc).__name__,
        "param": _safe_scalar(getattr(exc, "param", None) or error.get("param")),
        "request_id": _safe_scalar(
            getattr(exc, "request_id", None)
            or headers.get("x-request-id")
            or headers.get("request-id")
        ),
        "message": _sanitize_message(raw_message, api_key),
    }


def _safe_diagnostics(exc: Exception, api_key: str = "") -> dict:
    """Backward-compatible internal alias."""
    return safe_error_diagnostics(exc, api_key)


def _error_fields(body: Any) -> dict:
    """Return only the server error allowlist, never the complete response body."""
    if isinstance(body, str):
        try:
            body = json.loads(body)
        except (json.JSONDecodeError, TypeError):
            return {}
    if not isinstance(body, dict):
        return {}
    candidate = body.get("error", body)
    if not isinstance(candidate, dict):
        return {}
    return {
        key: candidate.get(key)
        for key in ("message", "code", "type", "param")
    }


def _safe_scalar(value: Any) -> str | int | None:
    return value if isinstance(value, (str, int)) else None


def _sanitize_message(value: Any, api_key: str) -> str:
    message = value if isinstance(value, str) else "OpenAI rejected the request"
    if api_key:
        message = message.replace(api_key, "[REDACTED]")
    message = re.sub(r"(?i)authorization\s*:\s*bearer\s+\S+", "Authorization: [REDACTED]", message)
    message = re.sub(r"\bsk-[A-Za-z0-9_-]{8,}\b", "[REDACTED]", message)
    return message.replace("\r", " ").replace("\n", " ")[:500]


_SYSTEM_INSTRUCTIONS = {
    "pm_worker": "Act as the PM. Return only a JSON object with request_summary, goal, constraints, definition_of_done, and risk_notes.",
    "planning_worker": "Act as the planning worker. Use previous outputs. Return only a JSON object with tasks, dependencies, assigned_workers, and acceptance_criteria.",
    "development_worker": "Act as the development worker. Propose an implementation, but do not claim files were actually changed or commands executed. Every proposed_file_writes item must use action_type FILE_WRITE and content must be the complete literal intended file content exactly as it should be encoded as UTF-8; never put a description, transformation instruction, placeholder, summary, or prose about the content in the content field. Return only the requested JSON object.",
    "qa_worker": "Act as the QA worker. Report proposed tests and claimed assessment only; Runtime evidence determines whether tests executed. When runtime-observed development output lists tests/fixtures/afde_2_7_approval_target.txt in verified_changed_files, request the bounded deterministic command with argv [\"python\",\"-m\",\"pytest\",\"tests/test_afde_2_7_fixture.py\",\"-q\"]. Return only the requested JSON object.",
    "documentation_worker": "Act as the documentation worker. Summarize provider claims separately from Runtime-verified evidence; never describe proposed files or claimed tests as verified. Return only a JSON object with runtime_report, artifact_index, and user_summary.",
}


def _object_schema(properties: dict, required: list[str]) -> dict:
    return {
        "type": "object",
        "properties": properties,
        "required": required,
        "additionalProperties": False,
    }


_STRINGS = {"type": "array", "items": {"type": "string"}}
_FILE_WRITE_PROPOSALS = {"type":"array","items":_object_schema({"action_type":{"type":"string","enum":["FILE_WRITE"]},"relative_path":{"type":"string"},"content":{"type":"string"},"purpose":{"type":"string"}},["action_type","relative_path","content","purpose"])}
_COMMAND_PROPOSALS = {"type":"array","items":_object_schema({"argv":_STRINGS,"purpose":{"type":"string"}},["argv","purpose"])}
_OUTPUT_SCHEMAS = {
    "pm_worker": _object_schema(
        {
            "request_summary": {"type": "string"}, "goal": {"type": "string"},
            "constraints": _STRINGS, "definition_of_done": _STRINGS, "risk_notes": _STRINGS,
        },
        ["request_summary", "goal", "constraints", "definition_of_done", "risk_notes"],
    ),
    "planning_worker": _object_schema(
        {"tasks": _STRINGS, "dependencies": _STRINGS, "assigned_workers": _STRINGS, "acceptance_criteria": _STRINGS},
        ["tasks", "dependencies", "assigned_workers", "acceptance_criteria"],
    ),
    "development_worker": _object_schema(
        {"implementation_summary": {"type": "string"}, "proposed_files": _STRINGS, "proposed_test_commands": _STRINGS, "claimed_artifacts": _STRINGS, "proposed_file_writes": _FILE_WRITE_PROPOSALS},
        ["implementation_summary", "proposed_files", "proposed_test_commands", "claimed_artifacts", "proposed_file_writes"],
    ),
    "qa_worker": _object_schema(
        {"claimed_test_commands": _STRINGS, "claimed_passed": {"type": "integer"}, "claimed_failed": {"type": "integer"}, "issues": _STRINGS, "recommendation": {"type": "string", "enum": ["PASS", "REVISE"]}, "requested_test_executions": _COMMAND_PROPOSALS},
        ["claimed_test_commands", "claimed_passed", "claimed_failed", "issues", "recommendation", "requested_test_executions"],
    ),
    "documentation_worker": _object_schema(
        {"runtime_report": {"type": "string"}, "artifact_index": {"type": "string"}, "user_summary": {"type": "string"}},
        ["runtime_report", "artifact_index", "user_summary"],
    ),
}


def structured_output_config(worker_id: str) -> dict:
    if worker_id not in _OUTPUT_SCHEMAS:
        raise ProviderConfigurationError(f"Unknown worker: {worker_id}")
    return {
        "format": {
            "type": "json_schema",
            "name": f"{worker_id}_result",
            "schema": _OUTPUT_SCHEMAS[worker_id],
            "strict": True,
        }
    }


def build_worker_request(worker_id: str, request: str, context: dict, model: str) -> dict:
    instructions = _SYSTEM_INSTRUCTIONS.get(worker_id)
    if instructions is None:
        raise ProviderConfigurationError(f"Unknown worker: {worker_id}")
    payload = {
        "request": request,
        "previous_worker_outputs": context.get("outputs", {}),
        "revision": context.get("revision", 0),
    }
    return {
        "model": model,
        "instructions": instructions,
        "input": json.dumps(payload, ensure_ascii=False),
        "text": structured_output_config(worker_id),
    }
