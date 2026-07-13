import pytest
from real_worker_runtime.provider_bridge import ProviderBridge
from real_worker_runtime.errors import ProviderConfigurationError, ProviderResponseError
def test_mock(tmp_path): assert ProviderBridge(tmp_path).select("mock")["mode"]=="deterministic_mock"
@pytest.mark.parametrize("name",["openai","gemini"])
def test_unconfigured_real_provider(tmp_path,monkeypatch,name):
 monkeypatch.delenv("OPENAI_API_KEY",raising=False); monkeypatch.delenv("GEMINI_API_KEY",raising=False)
 with pytest.raises(ProviderConfigurationError): ProviderBridge(tmp_path).select(name)
def test_unknown(tmp_path):
 with pytest.raises(ProviderConfigurationError): ProviderBridge(tmp_path).select("bad")


def _development_output(proposal):
 return {
  "implementation_summary":"structured proposal", "proposed_files":[],
  "proposed_test_commands":[], "claimed_artifacts":[],
  "proposed_file_writes":[proposal],
 }


def _openai_bridge(tmp_path, monkeypatch, output):
 monkeypatch.setenv("OPENAI_API_KEY", "test-placeholder")
 class Provider:
  def generate(self, worker_id, request, context): return output
 bridge=ProviderBridge(tmp_path)
 bridge.provider=Provider()
 return bridge


def test_exact_multiline_utf8_lf_content_survives_provider_boundary(tmp_path, monkeypatch):
 content="첫째 줄\nsecond line\n"
 proposal={"action_type":"FILE_WRITE","relative_path":"controlled_execution/note.txt","content":content,"purpose":"write exact text"}
 output=_development_output(proposal)
 observed=_openai_bridge(tmp_path,monkeypatch,output).generate("development_worker","demo",{"outputs":{}})
 assert observed["proposed_file_writes"][0]["content"] == content
 assert observed is output


@pytest.mark.parametrize("content",[
 "(Original content with the exact line 'old' replaced by 'new', preserving LF)",
 "<content>", "content goes here", "...",
])
def test_descriptive_or_placeholder_content_fails_closed(tmp_path, monkeypatch, content):
 proposal={"action_type":"FILE_WRITE","relative_path":"controlled_execution/note.txt","content":content,"purpose":"write"}
 bridge=_openai_bridge(tmp_path,monkeypatch,_development_output(proposal))
 with pytest.raises(ProviderResponseError,match="placeholder"):
  bridge.generate("development_worker","demo",{"outputs":{}})


@pytest.mark.parametrize("proposal",[
 {"action_type":"FILE_WRITE","relative_path":"controlled_execution/note.txt","purpose":"missing content"},
 {"action_type":"FILE_WRITE","relative_path":"controlled_execution/note.txt","content":"ok\n"},
 {"action_type":"COMMAND_RUN","relative_path":"controlled_execution/note.txt","content":"ok\n","purpose":"wrong action"},
 ["not","an","object"],
])
def test_malformed_file_write_structure_fails_closed(tmp_path, monkeypatch, proposal):
 bridge=_openai_bridge(tmp_path,monkeypatch,_development_output(proposal))
 with pytest.raises(ProviderResponseError):
  bridge.generate("development_worker","demo",{"outputs":{}})


def test_incorrect_literal_payload_is_never_repaired(tmp_path, monkeypatch):
 proposal={"action_type":"FILE_WRITE","relative_path":"controlled_execution/note.txt","content":"wrong literal bytes\n","purpose":"write"}
 output=_development_output(proposal)
 observed=_openai_bridge(tmp_path,monkeypatch,output).generate("development_worker","expected content",{"outputs":{}})
 assert observed["proposed_file_writes"][0]["content"] == "wrong literal bytes\n"
