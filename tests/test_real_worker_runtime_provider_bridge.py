import pytest
from real_worker_runtime.provider_bridge import ProviderBridge
from real_worker_runtime.errors import ProviderConfigurationError
def test_mock(tmp_path): assert ProviderBridge(tmp_path).select("mock")["mode"]=="deterministic_mock"
@pytest.mark.parametrize("name",["openai","gemini"])
def test_unconfigured_real_provider(tmp_path,monkeypatch,name):
 monkeypatch.delenv("OPENAI_API_KEY",raising=False); monkeypatch.delenv("GEMINI_API_KEY",raising=False)
 with pytest.raises(ProviderConfigurationError): ProviderBridge(tmp_path).select(name)
def test_unknown(tmp_path):
 with pytest.raises(ProviderConfigurationError): ProviderBridge(tmp_path).select("bad")
