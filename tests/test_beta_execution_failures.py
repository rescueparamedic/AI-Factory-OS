import json

import pytest

from afde import cli
from afde.execution import (
    BetaExecutionService, RealExecutionPipeline, SingleWorkerExecutionAdapter,
)
from afde.execution.bridge import ProviderRuntimeBridge
from afde.providers import (
    AIProvider, MockAIProvider, ProviderRequestError, ProviderResponseError,
)
from real_worker_runtime.artifact_store import ArtifactStore


class FailingProvider(AIProvider):
    def __init__(self, error, model=None):
        self.error = error
        self.model = model

    def generate(self, request):
        raise self.error


class CountingProvider(AIProvider):
    def __init__(self):
        self.calls = 0

    def generate(self, request):
        self.calls += 1
        return MockAIProvider().generate(request)


def _factory(provider):
    return lambda *args, **kwargs: provider


def _evidence(tmp_path, result):
    return json.loads(
        (tmp_path / result.evidence_path).read_text(encoding="utf-8")
    )


@pytest.mark.parametrize(
    ("error", "category", "retryable"),
    [
        (ProviderRequestError("OpenAI request failed (TimeoutError)"),
         "provider_timeout", True),
        (ProviderRequestError("OpenAI request failed (AuthenticationError)"),
         "provider_authentication", False),
        (ProviderRequestError("OpenAI request failed (ConnectionError)"),
         "provider_request", True),
        (ProviderResponseError("OpenAI returned an empty response"),
         "provider_response", False),
    ],
)
def test_provider_failures_are_normalized_sanitized_and_persisted(
    tmp_path, error, category, retryable,
):
    result = BetaExecutionService(
        tmp_path, provider_factory=_factory(FailingProvider(error)),
    ).execute("bounded request")

    assert result.status == "failed"
    assert result.exit_code == 5
    assert result.error["category"] == category
    assert result.error["stage"] == "provider"
    assert result.error["retryable"] is retryable
    assert result.error["sanitized"] is True
    assert _evidence(tmp_path, result)["error"] == result.error


def test_provider_error_never_leaks_environment_key(tmp_path, monkeypatch):
    secret = "sk-beta-provider-secret"
    monkeypatch.setenv("OPENAI_API_KEY", secret)
    provider = FailingProvider(ProviderRequestError(f"transport failed: {secret}"))

    result = BetaExecutionService(
        tmp_path, provider_factory=_factory(provider),
    ).execute("bounded request")

    serialized = json.dumps(result.to_dict()) + json.dumps(_evidence(tmp_path, result))
    assert secret not in serialized
    assert "[REDACTED]" in serialized


def test_bridge_failure_is_normalized_and_persisted(tmp_path, monkeypatch):
    def fail(*args, **kwargs):
        raise RuntimeError("conversion failed")

    monkeypatch.setattr(ProviderRuntimeBridge, "convert", fail)
    result = BetaExecutionService(tmp_path).execute("bounded request")

    assert result.exit_code == 5
    assert result.error["category"] == "bridge_conversion"
    assert result.error["stage"] == "bridge"
    assert _evidence(tmp_path, result)["stage"] == "bridge"


def test_worker_failure_is_structured_and_persisted(tmp_path):
    def pipeline_factory(provider, worker_id):
        def fail_worker(value):
            raise RuntimeError("worker failed")

        adapter = SingleWorkerExecutionAdapter(
            worker_id, executor=fail_worker,
        )
        return RealExecutionPipeline(
            provider, worker_id=worker_id, adapter=adapter,
        )

    result = BetaExecutionService(
        tmp_path, pipeline_factory=pipeline_factory,
    ).execute("bounded request")

    assert result.exit_code == 5
    assert result.error["category"] == "worker_execution"
    assert result.error["stage"] == "worker"
    assert len(result.results) == 1
    assert result.results[0]["execution_status"] == "failed"
    assert _evidence(tmp_path, result)["execution_status"] == "failed"


def test_evidence_persistence_failure_has_dedicated_exit_code(
    tmp_path, monkeypatch,
):
    def fail_write(*args, **kwargs):
        raise OSError("evidence path unavailable")

    monkeypatch.setattr(ArtifactStore, "json", fail_write)
    result = BetaExecutionService(tmp_path).execute("bounded request")

    assert result.status == "failed"
    assert result.stage == "evidence"
    assert result.exit_code == 7
    assert result.evidence_path == ""
    assert result.error["category"] == "evidence_persistence"


def test_cli_configuration_failures_return_two_and_write_failure_evidence(
    tmp_path, monkeypatch, capsys,
):
    monkeypatch.delenv("OPENAI_API_KEY", raising=False)
    monkeypatch.setenv("AI_FACTORY_RUN_LIVE_OPENAI_TESTS", "1")
    exit_code = cli.main([
        "execute", "--request", "bounded request", "--provider", "openai",
        "--allow-live-api", "--workspace", str(tmp_path), "--json",
    ])
    missing_key = json.loads(capsys.readouterr().out)
    unsupported_code = cli.main([
        "execute", "--request", "bounded request", "--provider", "unknown",
        "--workspace", str(tmp_path), "--json",
    ])
    unsupported = json.loads(capsys.readouterr().out)

    assert exit_code == missing_key["exit_code"] == 2
    assert missing_key["error"]["category"] == "provider_configuration"
    assert unsupported_code == unsupported["exit_code"] == 2
    assert unsupported["error"]["category"] == "invalid_input"
    assert (tmp_path / missing_key["evidence_path"]).is_file()
    assert (tmp_path / unsupported["evidence_path"]).is_file()


@pytest.mark.parametrize(
    ("allow_live_api", "live_environment"),
    [(False, "1"), (True, "0")],
)
def test_openai_requires_all_explicit_live_opt_ins(
    tmp_path, monkeypatch, allow_live_api, live_environment,
):
    monkeypatch.setenv("OPENAI_API_KEY", "test-placeholder")
    monkeypatch.setenv("AI_FACTORY_RUN_LIVE_OPENAI_TESTS", live_environment)

    result = BetaExecutionService(tmp_path).execute(
        "bounded request", provider="openai", allow_live_api=allow_live_api,
    )

    assert result.exit_code == 2
    assert result.error["category"] == "provider_configuration"


def test_model_priority_is_cli_then_environment_then_provider_default(
    tmp_path, monkeypatch,
):
    observed = []

    def factory(provider, **kwargs):
        observed.append(kwargs["model"])
        return MockAIProvider()

    service = BetaExecutionService(tmp_path, provider_factory=factory)
    monkeypatch.setenv("AI_FACTORY_OPENAI_MODEL", "environment-model")

    assert service.execute("first", model="cli-model").exit_code == 0
    assert service.execute("second").exit_code == 0
    monkeypatch.delenv("AI_FACTORY_OPENAI_MODEL")
    assert service.execute("third").exit_code == 0
    assert observed == ["cli-model", "environment-model", None]


def test_official_beta_service_calls_provider_exactly_once(tmp_path):
    provider = CountingProvider()

    result = BetaExecutionService(
        tmp_path, provider_factory=_factory(provider),
    ).execute("bounded request")

    assert result.exit_code == 0
    assert provider.calls == 1
    assert len(result.results) == 1


def test_failed_live_provider_records_resolved_model_and_safe_diagnostics(
    tmp_path, monkeypatch,
):
    monkeypatch.setenv("OPENAI_API_KEY", "test-placeholder")
    monkeypatch.setenv("AI_FACTORY_RUN_LIVE_OPENAI_TESTS", "1")
    error = ProviderRequestError(
        "OpenAI request failed (InternalServerError)",
        category="provider_server", status_code=500,
        request_id="req_safe_identifier", retryable=True,
    )
    provider = FailingProvider(error, model="gpt-4.1-mini")

    result = BetaExecutionService(
        tmp_path, provider_factory=_factory(provider),
    ).execute("bounded request", provider="openai", allow_live_api=True)

    assert result.model == "gpt-4.1-mini"
    assert result.execution_mode == "live"
    assert result.error["code"] == "BETA_PROVIDER_SERVER"
    assert result.error["http_status"] == 500
    assert result.error["provider_request_id"] == "req_safe_identifier"
    evidence = _evidence(tmp_path, result)
    assert evidence["provider"]["model"] == "gpt-4.1-mini"
    assert evidence["provider"]["execution_mode"] == "live"
