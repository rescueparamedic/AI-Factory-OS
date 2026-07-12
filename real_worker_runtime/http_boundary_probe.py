from __future__ import annotations

import json
import os
import re
import shutil
import socket
import ssl
import subprocess
from typing import Any, Callable
from urllib.error import HTTPError, URLError
from urllib.request import Request, urlopen

from .errors import ProviderConfigurationError


HOST = "api.openai.com"
BASE_URL = f"https://{HOST}"
RESPONSES_URL = f"{BASE_URL}/v1/responses"
TRANSPORT_ENV_NAMES = (
    "HTTP_PROXY", "HTTPS_PROXY", "ALL_PROXY", "NO_PROXY",
    "SSL_CERT_FILE", "SSL_CERT_DIR", "REQUESTS_CA_BUNDLE", "CURL_CA_BUNDLE",
    "PYTHONHTTPSVERIFY", "SSLKEYLOGFILE", "OPENAI_BASE_URL",
)
_GATEWAY_HEADER_NAMES = {
    "server", "via", "cf-ray", "cf-cache-status", "x-cache", "x-cache-hits",
    "x-served-by", "x-envoy-upstream-service-time", "x-amz-cf-id", "x-amz-cf-pop",
}


class HTTPBoundaryDiagnostic:
    """Layered diagnostics with one optional, explicitly opted-in API POST."""

    def __init__(
        self,
        model: str,
        include_post: bool = False,
        include_curl_post: bool = False,
        include_curl_error_details: bool = False,
        allow_live_api: bool = False,
        timeout_seconds: float = 15.0,
        resolver: Callable[..., Any] = socket.getaddrinfo,
        urllib_transport: Callable[..., Any] = urlopen,
        tls_connector: Callable[..., Any] | None = None,
        httpx_client_factory: Callable[..., Any] | None = None,
        curl_finder: Callable[[str], str | None] = shutil.which,
        subprocess_runner: Callable[..., Any] = subprocess.run,
    ) -> None:
        self.model = model.strip()
        self.include_post = include_post
        self.include_curl_post = include_curl_post
        self.include_curl_error_details = include_curl_error_details
        self.allow_live_api = allow_live_api
        self.timeout_seconds = timeout_seconds
        self.resolver = resolver
        self.urllib_transport = urllib_transport
        self.tls_connector = tls_connector
        self.httpx_client_factory = httpx_client_factory
        self.curl_finder = curl_finder
        self.subprocess_runner = subprocess_runner

    def run(self) -> dict:
        if self.include_post and not self.allow_live_api:
            raise ProviderConfigurationError(
                "HTTP boundary POST requires --allow-live-api; no POST was made"
            )
        if self.include_curl_post and not self.allow_live_api:
            raise ProviderConfigurationError(
                "curl POST requires both --include-curl-post and --allow-live-api; no POST was made"
            )
        if self.include_curl_error_details and not self.include_curl_post:
            raise ProviderConfigurationError(
                "--include-curl-error-details requires --include-curl-post; no POST was made"
            )
        curl_path = self.curl_finder("curl.exe")
        result = {
            "diagnostic": "OPENAI_HTTP_BOUNDARY",
            "python_ssl": {
                "openssl_version": ssl.OPENSSL_VERSION,
                "default_verify_paths": _verify_path_presence(),
            },
            "transport_environment": {
                name: "SET" if os.environ.get(name) else "NOT SET"
                for name in TRANSPORT_ENV_NAMES
            },
            "dns": self._dns(),
            "tls": self._tls(),
            "urllib_head": self._urllib_head(),
            "httpx_head": self._httpx_head(),
            "api_key_shape": _api_key_shape(os.environ.get("OPENAI_API_KEY")),
            "curl": {
                "available": bool(curl_path),
                "version": self._curl_version(curl_path) if curl_path else None,
                "head": self._curl_request(curl_path, post=False) if curl_path else {"status": "unavailable"},
                "post": {"status": "not_requested"},
                "authenticated_secret_transport": "stdin_config_anonymous_pipe",
                "process_list_risk": (
                    "The API key is not in argv, but privileged process inspection or debugging "
                    "could observe parent/child memory or the anonymous stdin pipe."
                ),
            },
            "raw_post": {"status": "not_requested"},
        }
        if self.include_post:
            result["raw_post"] = self._raw_post()
        if self.include_curl_post and curl_path:
            result["curl"]["post"] = self._curl_request(
                curl_path, post=True, include_error_details=self.include_curl_error_details
            )
        return result

    def _dns(self) -> dict:
        try:
            records = self.resolver(HOST, 443, type=socket.SOCK_STREAM)
        except Exception as exc:
            return {"status": "failed", "error_type": type(exc).__name__}
        addresses = {
            item[4][0] for item in records
            if len(item) > 4 and item[4]
        }
        families = sorted({"IPv6" if item[0] == socket.AF_INET6 else "IPv4" for item in records})
        return {"status": "success", "resolved_ip_count": len(addresses), "address_families": families}

    def _tls(self) -> dict:
        try:
            if self.tls_connector is not None:
                info = self.tls_connector(HOST, 443, self.timeout_seconds)
                return {"status": "success", **info}
            context = ssl.create_default_context()
            with socket.create_connection((HOST, 443), timeout=self.timeout_seconds) as raw:
                with context.wrap_socket(raw, server_hostname=HOST) as secured:
                    cert = secured.getpeercert() or {}
                    cipher = secured.cipher() or (None, None, None)
                    return {
                        "status": "success",
                        "tls_version": secured.version(),
                        "cipher": cipher[0],
                        "certificate": _certificate_summary(cert),
                    }
        except Exception as exc:
            return {"status": "failed", "error_type": type(exc).__name__}

    def _urllib_head(self) -> dict:
        request = Request(BASE_URL, method="HEAD")
        return _perform_urllib(request, self.urllib_transport, self.timeout_seconds)

    def _httpx_head(self) -> dict:
        try:
            if self.httpx_client_factory is None:
                import httpx
                factory = httpx.Client
                version = httpx.__version__
            else:
                factory = self.httpx_client_factory
                version = "injected"
        except ImportError:
            return {"status": "unavailable"}
        try:
            with factory(timeout=self.timeout_seconds) as client:
                response = client.head(BASE_URL)
                return {"library_version": version, **_response_summary(response.status_code, response.headers)}
        except Exception as exc:
            return {"status": "failed", "library_version": version, "error_type": type(exc).__name__}

    def _raw_post(self) -> dict:
        api_key = os.environ.get("OPENAI_API_KEY", "").strip()
        if not api_key:
            raise ProviderConfigurationError("OPENAI_API_KEY is required for boundary POST")
        if not self.model:
            raise ProviderConfigurationError("A model is required for boundary POST")
        body = json.dumps(
            {"model": self.model, "input": "Reply with exactly OK"},
            separators=(",", ":"),
        ).encode("utf-8")
        request = Request(
            RESPONSES_URL,
            data=body,
            method="POST",
            headers={"Authorization": f"Bearer {api_key}", "Content-Type": "application/json"},
        )
        return _perform_urllib(request, self.urllib_transport, self.timeout_seconds)

    def _curl_version(self, curl_path: str) -> str | None:
        try:
            completed = self.subprocess_runner(
                [curl_path, "--version"], capture_output=True, timeout=self.timeout_seconds,
                check=False,
            )
            first_line = completed.stdout.decode("utf-8", "replace").splitlines()[0]
            return first_line[:255]
        except Exception:
            return None

    def _curl_request(
        self, curl_path: str, post: bool, include_error_details: bool = False
    ) -> dict:
        key = os.environ.get("OPENAI_API_KEY")
        if post:
            shape = _api_key_shape(key)
            if not shape["key_present"]:
                raise ProviderConfigurationError("OPENAI_API_KEY is required for curl POST")
            if shape["embedded_newline"]:
                raise ProviderConfigurationError("OPENAI_API_KEY contains a newline; curl POST was not made")
            if not self.model:
                raise ProviderConfigurationError("A model is required for curl POST")
        marker = "AFDE_CURL_HTTP_STATUS:"
        config = _build_curl_config(
            model=self.model, api_key=key, post=post,
            timeout_seconds=self.timeout_seconds, marker=marker,
        )
        try:
            completed = self.subprocess_runner(
                [curl_path, "--config", "-"], input=config, capture_output=True,
                timeout=self.timeout_seconds + 2, check=False,
            )
            return _curl_output_summary(
                completed.returncode, completed.stdout, marker,
                include_error_details=include_error_details, api_key=key or "",
            )
        except Exception as exc:
            return {"status": "failed", "exit_code": None, "http_status": None,
                    "error_type": type(exc).__name__}


def _perform_urllib(request: Request, transport: Callable[..., Any], timeout: float) -> dict:
    try:
        response = transport(request, timeout=timeout)
        try:
            return _response_summary(response.status, response.headers)
        finally:
            response.close()
    except HTTPError as exc:
        try:
            return _response_summary(exc.code, exc.headers)
        finally:
            exc.close()
    except (URLError, OSError) as exc:
        return {"status": "failed", "http_status": None, "error_type": type(exc).__name__}


def _response_summary(status: int, headers: Any) -> dict:
    names = sorted({str(name).lower() for name in headers.keys()})
    return {
        "status": "success",
        "http_status": int(status),
        "response_header_names": names,
        "has_openai_request_id": "x-request-id" in names,
        "gateway_header_names": sorted(set(names) & _GATEWAY_HEADER_NAMES),
    }


def _api_key_shape(key: str | None) -> dict:
    value = key or ""
    return {
        "key_present": bool(value),
        "key_length": len(value),
        "prefix_valid": value.startswith("sk-"),
        "leading_whitespace": bool(value and value[0].isspace()),
        "trailing_whitespace": bool(value and value[-1].isspace()),
        "embedded_newline": "\n" in value or "\r" in value,
    }


def _build_curl_config(
    model: str, api_key: str | None, post: bool, timeout_seconds: float, marker: str
) -> bytes:
    lines = [
        f'url = "{RESPONSES_URL if post else BASE_URL}"',
        "silent", "show-error", "include", f"max-time = {timeout_seconds}",
        f'write-out = "\\n{marker}%{{http_code}}"',
    ]
    if post:
        body = json.dumps(
            {"model": model, "input": "Reply with exactly OK"},
            ensure_ascii=False, separators=(",", ":"),
        )
        escaped_key = (api_key or "").replace("\\", "\\\\").replace('"', '\\"')
        escaped_body = body.replace("\\", "\\\\").replace('"', '\\"')
        lines.extend([
            'request = "POST"',
            'header = "Content-Type: application/json"',
            f'header = "Authorization: Bearer {escaped_key}"',
            f'data = "{escaped_body}"',
        ])
    else:
        lines.append("head")
    return ("\n".join(lines) + "\n").encode("utf-8")


def _curl_output_summary(
    exit_code: int, output: bytes, marker: str,
    include_error_details: bool = False, api_key: str = "",
) -> dict:
    marker_bytes = ("\n" + marker).encode("ascii")
    payload, separator, status_bytes = output.rpartition(marker_bytes)
    parsed_status = int(status_bytes.strip()) if separator and status_bytes.strip().isdigit() else None
    http_status = parsed_status or None
    header_end = payload.rfind(b"\r\n\r\n")
    delimiter_size = 4
    if header_end < 0:
        header_end = payload.rfind(b"\n\n")
        delimiter_size = 2
    header_blob = payload[:header_end] if header_end >= 0 else b""
    body = payload[header_end + delimiter_size:] if header_end >= 0 else payload
    # With proxy/interim responses, retain only the final HTTP header block.
    last_http = max(header_blob.rfind(b"\r\nHTTP/"), header_blob.rfind(b"\nHTTP/"))
    if last_http >= 0:
        header_blob = header_blob[last_http + (2 if header_blob[last_http:last_http + 2] == b"\r\n" else 1):]
    names = []
    request_id = None
    for line in header_blob.replace(b"\r\n", b"\n").split(b"\n")[1:]:
        if b":" in line:
            raw_name, raw_value = line.split(b":", 1)
            name = raw_name.decode("ascii", "ignore").strip().lower()
            names.append(name)
            if name == "x-request-id":
                request_id = _safe_error_scalar(raw_value.decode("utf-8", "replace").strip(), api_key)
    unique_names = sorted(set(filter(None, names)))
    sample = body[:512].lstrip().lower()
    result = {
        "status": "success" if exit_code == 0 else "failed",
        "exit_code": int(exit_code),
        "http_status": http_status,
        "response_header_names": unique_names,
        "has_openai_request_id": "x-request-id" in unique_names,
        "gateway_header_names": sorted(set(unique_names) & _GATEWAY_HEADER_NAMES),
        "response_body_byte_length": len(body),
        "body_appears_html": sample.startswith(b"<!doctype html") or sample.startswith(b"<html"),
    }
    if include_error_details and http_status is not None and not 200 <= http_status < 300:
        result["error_response"] = _safe_curl_error_response(
            http_status, body, request_id, api_key
        )
    return result


def _safe_curl_error_response(
    http_status: int | None, body: bytes, header_request_id: Any, api_key: str
) -> dict:
    classification = {
        400: "request_error", 401: "authentication_error", 403: "permission_error",
        429: "rate_limit_error",
    }.get(http_status, "server_error" if http_status and http_status >= 500 else "http_error")
    try:
        payload = json.loads(body.decode("utf-8"))
    except (UnicodeDecodeError, json.JSONDecodeError):
        payload = None
    error = payload.get("error") if isinstance(payload, dict) else None
    if not isinstance(error, dict):
        error = {}
    top_request_id = payload.get("request_id") if isinstance(payload, dict) else None
    return {
        "classification": classification,
        "error.message": _safe_error_scalar(error.get("message"), api_key, default=None),
        "error.type": _safe_error_scalar(error.get("type"), api_key),
        "error.code": _safe_error_scalar(error.get("code"), api_key),
        "error.param": _safe_error_scalar(error.get("param"), api_key),
        "request_id": _safe_error_scalar(top_request_id, api_key) or header_request_id,
    }


def _safe_error_scalar(
    value: Any, api_key: str, default: str | int | None = None
) -> str | int | None:
    if isinstance(value, int):
        return value
    if not isinstance(value, str):
        return default
    safe = value.replace("\r", " ").replace("\n", " ")
    if api_key:
        safe = safe.replace(api_key, "[REDACTED]")
    safe = re.sub(r"\bsk-[A-Za-z0-9_-]{8,}\b", "[REDACTED]", safe)
    safe = re.sub(
        r"(?i)authorization\s*:\s*bearer\s+\S+", "Authorization: [REDACTED]", safe
    )
    return safe[:500]


def _certificate_summary(cert: dict) -> dict:
    san = cert.get("subjectAltName", ())
    return {
        "subject_common_name": _name_attribute(cert.get("subject", ()), "commonName"),
        "issuer_common_name": _name_attribute(cert.get("issuer", ()), "commonName"),
        "not_before": cert.get("notBefore"),
        "not_after": cert.get("notAfter"),
        "subject_alt_name_count": len(san),
    }


def _name_attribute(groups: Any, key: str) -> str | None:
    for group in groups:
        for name, value in group:
            if name == key and isinstance(value, str):
                return value[:255]
    return None


def _verify_path_presence() -> dict:
    paths = ssl.get_default_verify_paths()
    return {
        "cafile_configured": bool(paths.cafile),
        "capath_configured": bool(paths.capath),
        "openssl_cafile_env": paths.openssl_cafile_env,
        "openssl_capath_env": paths.openssl_capath_env,
    }
