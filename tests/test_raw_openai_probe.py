from email.message import Message
import hashlib
import json

import pytest

from afde.cli import main
from real_worker_runtime.errors import ProviderConfigurationError
from real_worker_runtime.raw_openai_probe import RawOpenAIResponsesProbe


class FakeResponse:
    def __init__(self, status, body, content_type="application/json", request_id=None):
        self.status = status
        self._body = body if isinstance(body, bytes) else body.encode("utf-8")
        self.headers = Message()
        if content_type is not None:
            self.headers["Content-Type"] = content_type
        if request_id is not None:
            self.headers["x-request-id"] = request_id

    def read(self):
        return self._body


class CapturingTransport:
    def __init__(self, response):
        self.response = response
        self.request = None
        self.timeout = None

    def __call__(self, request, timeout):
        self.request = request
        self.timeout = timeout
        return self.response


def run_probe(monkeypatch, response):
    monkeypatch.setenv("OPENAI_API_KEY", "test-placeholder")
    transport = CapturingTransport(response)
    result = RawOpenAIResponsesProbe(
        "test-model", allow_live_api=True, transport=transport
    ).run()
    return result, transport


def test_raw_probe_requires_opt_in_before_key_lookup(monkeypatch):
    monkeypatch.delenv("OPENAI_API_KEY", raising=False)
    with pytest.raises(ProviderConfigurationError, match="opt-in"):
        RawOpenAIResponsesProbe("test-model").run()


def test_raw_probe_success_and_exact_minimal_payload(monkeypatch):
    payload = {
        "id": "resp_safe",
        "output": [{"content": [{"type": "output_text", "text": "OK"}]}],
    }
    result, transport = run_probe(
        monkeypatch, FakeResponse(200, json.dumps(payload), request_id="req_unused")
    )
    assert result == {
        "probe": "RAW",
        "status": "success",
        "http_status": 200,
        "response_id": "resp_safe",
        "output_text_length": 2,
    }
    assert json.loads(transport.request.data) == {
        "model": "test-model",
        "input": "Reply with exactly OK",
    }
    assert set(json.loads(transport.request.data)) == {"model", "input"}
    assert transport.request.full_url == "https://api.openai.com/v1/responses"
    assert transport.request.get_method() == "POST"
    assert transport.request.get_header("Authorization").startswith("Bearer ")


def test_raw_probe_openai_json_error_allowlist(monkeypatch):
    body = json.dumps({
        "error": {
            "message": "Model request rejected",
            "type": "invalid_request_error",
            "code": "bad_model",
            "param": "model",
            "extra": "must not be retained",
        },
        "top_level_extra": "must not be retained",
    })
    result, _ = run_probe(
        monkeypatch, FakeResponse(400, body, request_id="req_safe")
    )
    assert result == {
        "probe": "RAW",
        "status": "failed",
        "http_status": 400,
        "content_type": "application/json",
        "message": "Model request rejected",
        "error_type": "invalid_request_error",
        "code": "bad_model",
        "param": "model",
        "request_id": "req_safe",
    }
    assert "extra" not in str(result)


def test_raw_probe_non_json_400_records_fingerprint_only(monkeypatch):
    raw = b"opaque gateway rejection"
    result, _ = run_probe(
        monkeypatch, FakeResponse(400, raw, content_type="text/plain")
    )
    assert result == {
        "probe": "RAW",
        "status": "failed",
        "http_status": 400,
        "content_type": "text/plain",
        "body_byte_length": len(raw),
        "body_sha256_12": hashlib.sha256(raw).hexdigest()[:12],
        "html": False,
        "request_id": None,
    }
    assert raw.decode() not in str(result)


def test_raw_probe_html_400_does_not_return_body(monkeypatch):
    raw = b"<!DOCTYPE html><html><body>gateway details</body></html>"
    result, _ = run_probe(
        monkeypatch, FakeResponse(400, raw, content_type="text/html; charset=utf-8")
    )
    assert result["html"] is True
    assert result["body_byte_length"] == len(raw)
    assert "gateway details" not in str(result)


def test_raw_probe_masks_key_bearer_and_key_pattern(monkeypatch):
    key = "test-placeholder"
    unsafe = key + " Authorization" + ": Bearer hidden " + "sk-" + "sensitivevalue123"
    body = json.dumps({"error": {"message": unsafe, "type": "bad_request"}})
    result, _ = run_probe(monkeypatch, FakeResponse(400, body))
    rendered = json.dumps(result)
    assert key not in rendered
    assert "hidden" not in rendered
    assert "sensitivevalue123" not in rendered
    assert rendered.count("[REDACTED]") == 3


def test_raw_probe_cli_routes_without_network(monkeypatch, capsys):
    monkeypatch.setattr(
        RawOpenAIResponsesProbe,
        "run",
        lambda self: {"probe": "RAW", "status": "success", "http_status": 200, "response_id": None, "output_text_length": 2},
    )
    main(["openai-raw-probe", "--model", "test-model", "--allow-live-api"])
    output = capsys.readouterr().out
    assert '"probe": "RAW"' in output
    assert "OPENAI_API_KEY" not in output
