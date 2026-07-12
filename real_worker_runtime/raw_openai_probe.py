from __future__ import annotations

import hashlib
import json
import os
import re
from typing import Any, Callable
from urllib.error import HTTPError, URLError
from urllib.request import Request, urlopen

from .errors import ProviderConfigurationError
from .openai_provider import _error_fields, _safe_scalar, _sanitize_message


RESPONSES_URL = "https://api.openai.com/v1/responses"
RAW_INPUT = "Reply with exactly OK"


class RawOpenAIResponsesProbe:
    """Minimal stdlib HTTPS probe that does not import or use the OpenAI SDK."""

    def __init__(
        self,
        model: str,
        allow_live_api: bool = False,
        timeout_seconds: float = 60.0,
        transport: Callable[..., Any] | None = None,
    ) -> None:
        self.model = model.strip()
        self.allow_live_api = allow_live_api
        self.timeout_seconds = timeout_seconds
        self.transport = transport or urlopen

    def run(self) -> dict:
        if not self.allow_live_api:
            raise ProviderConfigurationError(
                "RAW OpenAI probe requires explicit --allow-live-api opt-in; no call was made"
            )
        api_key = os.environ.get("OPENAI_API_KEY", "").strip()
        if not api_key:
            raise ProviderConfigurationError("OPENAI_API_KEY is required for the RAW OpenAI probe")
        if not self.model:
            raise ProviderConfigurationError("A model is required for the RAW OpenAI probe")

        body = json.dumps(
            {"model": self.model, "input": RAW_INPUT},
            ensure_ascii=False,
            separators=(",", ":"),
        ).encode("utf-8")
        request = Request(
            RESPONSES_URL,
            data=body,
            method="POST",
            headers={
                "Authorization": f"Bearer {api_key}",
                "Content-Type": "application/json",
            },
        )
        try:
            response = self.transport(request, timeout=self.timeout_seconds)
            return self._read_response(response, api_key)
        except HTTPError as exc:
            return self._read_response(exc, api_key)
        except (URLError, OSError) as exc:
            return {
                "probe": "RAW",
                "status": "failed",
                "http_status": None,
                "content_type": None,
                "message": _sanitize_message(str(getattr(exc, "reason", exc)), api_key),
                "error_type": type(exc).__name__,
                "code": None,
                "param": None,
                "request_id": None,
            }

    def _read_response(self, response: Any, api_key: str) -> dict:
        status = getattr(response, "status", None) or getattr(response, "code", None)
        headers = getattr(response, "headers", {}) or {}
        content_type = _safe_content_type(headers.get("Content-Type"))
        request_id = _safe_scalar(headers.get("x-request-id"))
        raw = response.read()
        if not isinstance(raw, bytes):
            raw = bytes(raw or b"")
        parsed = _parse_json(raw, content_type)

        if status is not None and 200 <= int(status) < 300:
            if isinstance(parsed, dict):
                return {
                    "probe": "RAW",
                    "status": "success",
                    "http_status": int(status),
                    "response_id": _safe_scalar(parsed.get("id")),
                    "output_text_length": _output_text_length(parsed),
                }
            return _non_json_result(status, content_type, raw, request_id)

        if isinstance(parsed, dict):
            error = _error_fields(parsed)
            return {
                "probe": "RAW",
                "status": "failed",
                "http_status": int(status) if status is not None else None,
                "content_type": content_type,
                "message": _sanitize_message(error.get("message"), api_key),
                "error_type": _safe_scalar(error.get("type")),
                "code": _safe_scalar(error.get("code")),
                "param": _safe_scalar(error.get("param")),
                "request_id": request_id,
            }
        return _non_json_result(status, content_type, raw, request_id)


def _parse_json(raw: bytes, content_type: str | None) -> Any:
    if "json" not in (content_type or "").lower():
        return None
    try:
        return json.loads(raw.decode("utf-8"))
    except (UnicodeDecodeError, json.JSONDecodeError):
        return None


def _safe_content_type(value: Any) -> str | None:
    if not isinstance(value, str):
        return None
    return re.sub(r"[\r\n]", "", value)[:120]


def _non_json_result(status: Any, content_type: str | None, raw: bytes, request_id: Any) -> dict:
    prefix = raw.lstrip()[:32].lower()
    return {
        "probe": "RAW",
        "status": "failed",
        "http_status": int(status) if status is not None else None,
        "content_type": content_type,
        "body_byte_length": len(raw),
        "body_sha256_12": hashlib.sha256(raw).hexdigest()[:12],
        "html": prefix.startswith(b"<!doctype html") or prefix.startswith(b"<html"),
        "request_id": _safe_scalar(request_id),
    }


def _output_text_length(payload: dict) -> int:
    total = 0
    for output in payload.get("output", []):
        if not isinstance(output, dict):
            continue
        for content in output.get("content", []):
            if isinstance(content, dict) and content.get("type") == "output_text":
                text = content.get("text")
                if isinstance(text, str):
                    total += len(text)
    return total
