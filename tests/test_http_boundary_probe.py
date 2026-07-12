import json
import socket
import ssl
from types import SimpleNamespace

import pytest

from afde.cli import main
from real_worker_runtime.errors import ProviderConfigurationError
from real_worker_runtime.http_boundary_probe import (
    HTTPBoundaryDiagnostic, _build_curl_config, _curl_output_summary,
)


class FakeResponse:
    def __init__(self, status=200, headers=None):
        self.status = status
        self.headers = headers or {}
        self.closed = False

    def close(self):
        self.closed = True


class QueueTransport:
    def __init__(self, *responses):
        self.responses = iter(responses)
        self.requests = []

    def __call__(self, request, timeout):
        self.requests.append(request)
        return next(self.responses)


class FakeHTTPXClient:
    def __init__(self, response, timeout=None):
        self.response = response

    def __enter__(self):
        return self

    def __exit__(self, *args):
        return None

    def head(self, url):
        return self.response


def resolver(host, port, type):
    return [
        (socket.AF_INET, socket.SOCK_STREAM, 6, "", ("192.0.2.1", port)),
        (socket.AF_INET, socket.SOCK_STREAM, 6, "", ("192.0.2.1", port)),
        (socket.AF_INET6, socket.SOCK_STREAM, 6, "", ("2001:db8::1", port, 0, 0)),
    ]


def tls_connector(host, port, timeout):
    return {
        "tls_version": "TLSv1.3",
        "cipher": "TLS_TEST_CIPHER",
        "certificate": {
            "subject_common_name": "api.openai.com",
            "issuer_common_name": "Test CA",
            "not_before": "safe-start",
            "not_after": "safe-end",
            "subject_alt_name_count": 2,
        },
    }


def make_diagnostic(transport, httpx_response, **kwargs):
    return HTTPBoundaryDiagnostic(
        model="test-model",
        resolver=resolver,
        tls_connector=tls_connector,
        urllib_transport=transport,
        httpx_client_factory=lambda timeout: FakeHTTPXClient(httpx_response, timeout),
        curl_finder=lambda name: None,
        **kwargs,
    )


def test_read_only_boundary_diagnostic_has_safe_layer_summaries(monkeypatch):
    monkeypatch.setenv("SSL_CERT_FILE", "sensitive-path-must-not-appear")
    secret_value = "secret-header-value"
    head = FakeResponse(403, {"Server": secret_value, "X-Request-ID": secret_value, "Set-Cookie": secret_value})
    httpx_response = SimpleNamespace(status_code=404, headers={"via": secret_value})
    result = make_diagnostic(QueueTransport(head), httpx_response).run()

    assert result["dns"] == {
        "status": "success", "resolved_ip_count": 2,
        "address_families": ["IPv4", "IPv6"],
    }
    assert result["tls"]["tls_version"] == "TLSv1.3"
    assert result["urllib_head"] == {
        "status": "success",
        "http_status": 403,
        "response_header_names": ["server", "set-cookie", "x-request-id"],
        "has_openai_request_id": True,
        "gateway_header_names": ["server"],
    }
    assert result["httpx_head"]["gateway_header_names"] == ["via"]
    assert result["transport_environment"]["SSL_CERT_FILE"] == "SET"
    assert result["raw_post"] == {"status": "not_requested"}
    rendered = json.dumps(result)
    assert secret_value not in rendered
    assert "sensitive-path-must-not-appear" not in rendered
    assert "192.0.2.1" not in rendered


def test_post_requires_opt_in_before_any_diagnostic():
    transport = QueueTransport()
    with pytest.raises(ProviderConfigurationError, match="allow-live-api"):
        make_diagnostic(transport, SimpleNamespace(status_code=200, headers={}), include_post=True).run()
    assert transport.requests == []


def test_one_opted_in_post_records_only_boundary_metadata(monkeypatch):
    monkeypatch.setenv("OPENAI_API_KEY", "test-placeholder")
    head = FakeResponse(200, {"server": "hidden-head-value"})
    post = FakeResponse(400, {"server": "hidden-post-value", "x-request-id": "hidden-id-value"})
    transport = QueueTransport(head, post)
    result = make_diagnostic(
        transport,
        SimpleNamespace(status_code=200, headers={}),
        include_post=True,
        allow_live_api=True,
    ).run()
    assert len(transport.requests) == 2
    post_request = transport.requests[1]
    assert json.loads(post_request.data) == {
        "model": "test-model", "input": "Reply with exactly OK"
    }
    assert result["raw_post"] == {
        "status": "success",
        "http_status": 400,
        "response_header_names": ["server", "x-request-id"],
        "has_openai_request_id": True,
        "gateway_header_names": ["server"],
    }
    rendered = json.dumps(result)
    assert "hidden-head-value" not in rendered
    assert "hidden-post-value" not in rendered
    assert "hidden-id-value" not in rendered
    assert "test-placeholder" not in rendered


def test_dns_tls_and_http_failures_are_type_only():
    def bad_resolver(*args, **kwargs):
        raise socket.gaierror("sensitive dns details")

    def bad_tls(*args):
        raise ssl.SSLError("sensitive tls details")

    def bad_transport(*args, **kwargs):
        raise OSError("sensitive transport details")

    class BadClient:
        def __init__(self, timeout): pass
        def __enter__(self): raise RuntimeError("sensitive httpx details")
        def __exit__(self, *args): pass

    result = HTTPBoundaryDiagnostic(
        "test-model", resolver=bad_resolver, tls_connector=bad_tls,
        urllib_transport=bad_transport, httpx_client_factory=BadClient,
    ).run()
    assert result["dns"] == {"status": "failed", "error_type": "gaierror"}
    assert result["tls"] == {"status": "failed", "error_type": "SSLError"}
    assert result["urllib_head"]["error_type"] == "OSError"
    assert result["httpx_head"]["error_type"] == "RuntimeError"
    assert "sensitive" not in json.dumps(result)


def test_boundary_cli_routes_without_network(monkeypatch, capsys):
    monkeypatch.setattr(
        HTTPBoundaryDiagnostic, "run",
        lambda self: {"diagnostic": "OPENAI_HTTP_BOUNDARY", "raw_post": {"status": "not_requested"}},
    )
    main(["openai-http-boundary", "--model", "test-model"])
    output = capsys.readouterr().out
    assert "OPENAI_HTTP_BOUNDARY" in output
    assert "OPENAI_API_KEY" not in output


class FakeCurlRunner:
    def __init__(self, secret):
        self.secret = secret
        self.calls = []

    def __call__(self, args, **kwargs):
        self.calls.append((args, kwargs))
        if args[-1] == "--version":
            return SimpleNamespace(returncode=0, stdout=b"curl 8.10.1 test\n", stderr=b"")
        assert self.secret not in " ".join(args)
        if b'Authorization: Bearer ' in kwargs["input"]:
            output = (b"HTTP/1.1 400 Bad Request\r\nCF-Ray: hidden\r\n"
                      b"Content-Type: text/html\r\n\r\n<html>bad</html>"
                      b"\nAFDE_CURL_HTTP_STATUS:400")
        else:
            output = (b"HTTP/1.1 421 Misdirected Request\r\nServer: hidden\r\n\r\n"
                      b"\nAFDE_CURL_HTTP_STATUS:421")
        return SimpleNamespace(returncode=0, stdout=output, stderr=b"")


def test_curl_head_and_opted_in_post_keep_secret_out_of_argv_and_result(monkeypatch):
    secret = "sk-" + "test-super-secret-value"
    monkeypatch.setenv("OPENAI_API_KEY", secret)
    runner = FakeCurlRunner(secret)
    result = HTTPBoundaryDiagnostic(
        "test-model", resolver=resolver, tls_connector=tls_connector,
        urllib_transport=QueueTransport(FakeResponse()),
        httpx_client_factory=lambda timeout: FakeHTTPXClient(SimpleNamespace(status_code=200, headers={}), timeout),
        curl_finder=lambda name: r"C:\\Windows\\System32\\curl.exe",
        subprocess_runner=runner, include_curl_post=True, allow_live_api=True,
    ).run()
    assert result["curl"]["version"] == "curl 8.10.1 test"
    assert result["curl"]["head"]["http_status"] == 421
    assert result["curl"]["post"] == {
        "status": "success", "exit_code": 0, "http_status": 400,
        "response_header_names": ["cf-ray", "content-type"],
        "has_openai_request_id": False, "gateway_header_names": ["cf-ray"],
        "response_body_byte_length": 16, "body_appears_html": True,
    }
    assert result["api_key_shape"] == {
        "key_present": True, "key_length": len(secret), "prefix_valid": True,
        "leading_whitespace": False, "trailing_whitespace": False,
        "embedded_newline": False,
    }
    assert secret not in json.dumps(result)
    for args, kwargs in runner.calls:
        assert secret not in json.dumps(args)
        assert kwargs.get("shell") is not True


def test_curl_post_requires_both_flags_before_subprocess(monkeypatch):
    monkeypatch.setenv("OPENAI_API_KEY", "sk-test-secret")
    runner = FakeCurlRunner("sk-test-secret")
    diagnostic = HTTPBoundaryDiagnostic(
        "test-model", include_curl_post=True, curl_finder=lambda name: "curl.exe",
        subprocess_runner=runner,
    )
    with pytest.raises(ProviderConfigurationError, match="both"):
        diagnostic.run()
    assert runner.calls == []


def test_api_key_shape_does_not_normalize_or_disclose_key(monkeypatch):
    secret = " sk-test-secret\r\n"
    monkeypatch.setenv("OPENAI_API_KEY", secret)
    result = make_diagnostic(QueueTransport(FakeResponse()), SimpleNamespace(status_code=200, headers={})).run()
    assert result["api_key_shape"] == {
        "key_present": True, "key_length": len(secret), "prefix_valid": False,
        "leading_whitespace": True, "trailing_whitespace": True,
        "embedded_newline": True,
    }
    assert secret not in json.dumps(result)


def test_windows_curl_stdin_config_has_exact_minimal_responses_body():
    secret = "sk-" + "config-test-value"
    config = _build_curl_config(
        "gpt-4.1-mini", secret, True, 15.0, "AFDE_CURL_HTTP_STATUS:"
    ).decode("utf-8")
    assert config.startswith('url = "https://api.openai.com/v1/responses"\n')
    assert 'request = "POST"\n' in config
    assert 'header = "Content-Type: application/json"\n' in config
    assert 'header = "Authorization: Bearer ' + secret + '"\n' in config
    assert ('data = "{\\"model\\":\\"gpt-4.1-mini\\",'
            '\\"input\\":\\"Reply with exactly OK\\"}"\n') in config
    assert "transfer-encoding" not in config.lower()
    assert "content-length" not in config.lower()


@pytest.mark.parametrize(
    ("status", "expected"),
    [(400, "request_error"), (401, "authentication_error"), (500, "server_error")],
)
def test_curl_json_error_allowlist_and_http_classification(status, expected):
    secret = "sk-" + "never-render-this-value"
    body = json.dumps({
        "error": {
            "message": "Rejected " + secret + " Authorization" + ": Bearer hidden-token",
            "type": "server_error" if status == 500 else "invalid_request_error",
            "code": "internal_error" if status == 500 else "invalid_api_key",
            "param": None,
            "cookie": "must-not-appear",
        },
        "request_id": "req_body_safe",
        "extra": "must-not-appear",
    }).encode()
    output = (
        f"HTTP/1.1 {status} Error\r\nX-Request-ID: req_header_safe\r\n"
        "Set-Cookie: private-cookie\r\nContent-Type: application/json\r\n\r\n"
    ).encode() + body + f"\nAFDE_CURL_HTTP_STATUS:{status}".encode()
    result = _curl_output_summary(
        0, output, "AFDE_CURL_HTTP_STATUS:",
        include_error_details=True, api_key=secret,
    )
    assert result["http_status"] == status
    assert result["error_response"] == {
        "classification": expected,
        "error.message": "Rejected [REDACTED] Authorization: [REDACTED]",
        "error.type": "server_error" if status == 500 else "invalid_request_error",
        "error.code": "internal_error" if status == 500 else "invalid_api_key",
        "error.param": None,
        "request_id": "req_body_safe",
    }
    rendered = json.dumps(result)
    assert secret not in rendered
    assert "private-cookie" not in rendered
    assert "must-not-appear" not in rendered
    assert "hidden-token" not in rendered


def test_curl_error_details_requires_curl_post_before_network():
    diagnostic = HTTPBoundaryDiagnostic(
        "test-model", include_curl_error_details=True,
        curl_finder=lambda name: "curl.exe",
    )
    with pytest.raises(ProviderConfigurationError, match="include-curl-post"):
        diagnostic.run()


def test_default_400_and_401_summaries_do_not_add_error_body_fields():
    for status in (400, 401):
        output = (f"HTTP/1.1 {status} Error\r\nContent-Type: application/json\r\n\r\n"
                  '{"error":{"message":"not exposed by default"}}'
                  f"\nAFDE_CURL_HTTP_STATUS:{status}").encode()
        result = _curl_output_summary(0, output, "AFDE_CURL_HTTP_STATUS:")
        assert result["http_status"] == status
        assert "error_response" not in result
        assert "not exposed by default" not in json.dumps(result)


def test_curl_200_with_error_details_is_success_without_error_classification():
    output = (
        b"HTTP/1.1 200 OK\r\nX-Request-ID: req_success_safe\r\n"
        b"Content-Type: application/json\r\n\r\n"
        b'{"id":"resp_safe","output":[],"error":{"message":"must not classify"}}'
        b"\nAFDE_CURL_HTTP_STATUS:200"
    )
    result = _curl_output_summary(
        0, output, "AFDE_CURL_HTTP_STATUS:", include_error_details=True,
        api_key="sk-" + "not-rendered-success-key",
    )
    assert result["status"] == "success"
    assert result["http_status"] == 200
    assert result["has_openai_request_id"] is True
    assert "error_response" not in result
    assert "http_error" not in json.dumps(result)
    assert "must not classify" not in json.dumps(result)
    assert "req_success_safe" not in json.dumps(result)


def test_non_2xx_error_request_id_falls_back_safely_to_header():
    secret = "sk-" + "header-fallback-secret"
    output = (
        b"HTTP/1.1 500 Error\r\nX-Request-ID: req_header_only\r\n\r\n"
        b'{"error":{"message":"server failed","type":"server_error"}}'
        b"\nAFDE_CURL_HTTP_STATUS:500"
    )
    result = _curl_output_summary(
        0, output, "AFDE_CURL_HTTP_STATUS:",
        include_error_details=True, api_key=secret,
    )
    assert result["error_response"]["classification"] == "server_error"
    assert result["error_response"]["request_id"] == "req_header_only"
    assert secret not in json.dumps(result)
