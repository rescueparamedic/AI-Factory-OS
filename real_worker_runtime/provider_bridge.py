from __future__ import annotations
import re
from afde.provider_manager import ProviderManager
from .errors import ProviderConfigurationError, ProviderResponseError

class ProviderBridge:
    def __init__(self, root, model=None, allow_live_api=False, openai_client=None):
        self.manager=ProviderManager(root); self.model=model; self.allow_live_api=allow_live_api; self.openai_client=openai_client; self.provider="mock"
    def select(self, provider="mock"):
        provider=provider.lower()
        statuses={x["provider"]:x for x in self.manager.as_dicts()}
        if provider not in {"mock","openai","gemini"}: raise ProviderConfigurationError(f"Unknown provider: {provider}")
        if provider=="mock": self.provider="mock"; return {"provider":"mock","mode":"deterministic_mock"}
        if not statuses[provider]["configured"]: raise ProviderConfigurationError(f"{provider} is not configured; use --provider mock or configure its API key")
        if provider!="openai": raise ProviderConfigurationError(f"{provider} is configured but external execution is not supported; no paid call was made")
        if not self.allow_live_api: raise ProviderConfigurationError("OpenAI calls require explicit --allow-live-api opt-in; no paid call was made")
        from .openai_provider import OpenAIConfig, OpenAIProvider
        config=OpenAIConfig.from_env(self.model); self.provider=OpenAIProvider(config,self.openai_client)
        return {"provider":"openai","mode":"live","model":config.model}
    def generate(self, worker_id, request, context):
        if self.provider != "mock":
            output = self.provider.generate(worker_id, request, context)
            return _validate_provider_output(worker_id, _apply_bounded_qa_contract(worker_id, output, context))
        # Deterministic, visible output; never performs network access.
        templates={
          "pm_worker":{"request_summary":request,"goal":"Deliver a small validated implementation plan","constraints":["local safe mode","no external API"],"definition_of_done":["plan","implementation","QA","documentation"],"risk_notes":["mock output"]},
          "planning_worker":{"tasks":["analyze request","prepare implementation","validate result","document outcome"],"dependencies":["PM analysis"],"assigned_workers":["development_worker","qa_worker","documentation_worker"],"acceptance_criteria":["runner validation passes","artifacts saved"]},
          "development_worker":{"implementation_summary":"Prepared a deterministic implementation candidate without modifying project source.","proposed_files":["tests/fixtures/afde_2_7_approval_target.txt"] if "[approval-resume-mvp]" in request else (["controlled_execution/hello_from_afde.py"] if "[controlled-execution-mvp]" in request else []),"proposed_test_commands":(["python -m pytest tests/test_afde_2_7_fixture.py -q"] if "[approval-resume-mvp]" in request else (["python controlled_execution/hello_from_afde.py"] if "[controlled-execution-mvp]" in request else ["python --version"])),"claimed_artifacts":["implementation.json"],"proposed_file_writes":[{"action_type":"FILE_WRITE","relative_path":"tests/fixtures/afde_2_7_approval_target.txt","content":"approval_state=approved\n","purpose":"Deterministic existing-file approval resume proof"}] if "[approval-resume-mvp]" in request else ([{"action_type":"FILE_WRITE","relative_path":"controlled_execution/hello_from_afde.py","content":"print(\"Hello from AFDE.\")\n","purpose":"Deterministic controlled execution proof"}] if "[controlled-execution-mvp]" in request else [])},
          "qa_worker":{"claimed_test_commands":["python -m pytest tests/test_afde_2_7_fixture.py -q"] if "[approval-resume-mvp]" in request else (["python controlled_execution/hello_from_afde.py"] if "[controlled-execution-mvp]" in request else ["Sprint Auto Runner python version validation"]),"claimed_passed":0 if "[qa-fail-once]" in request and context.get("revision",0)==0 else 1,"claimed_failed":1 if "[qa-fail-once]" in request and context.get("revision",0)==0 else 0,"issues":["mock revision requested"] if "[qa-fail-once]" in request and context.get("revision",0)==0 else [],"recommendation":"REVISE" if "[qa-fail-once]" in request and context.get("revision",0)==0 else "PASS","requested_test_executions":[{"argv":["python","-m","pytest","tests/test_afde_2_7_fixture.py","-q"],"purpose":"Validate approved fixture state"}] if "[approval-resume-mvp]" in request else ([{"argv":["python","controlled_execution/hello_from_afde.py"],"purpose":"Validate deterministic controlled file"}] if "[controlled-execution-mvp]" in request else [])},
          "documentation_worker":{"runtime_report":"final_report.md","artifact_index":"artifact_index.json","user_summary":"Five-worker demo completed successfully."},
        }
        return _validate_provider_output(
            worker_id, _apply_bounded_qa_contract(worker_id, templates[worker_id], context)
        )


_APPROVAL_FIXTURE = "tests/fixtures/afde_2_7_approval_target.txt"
_APPROVAL_FIXTURE_QA_ARGV = [
    "python", "-m", "pytest", "tests/test_afde_2_7_fixture.py", "-q",
]


def _apply_bounded_qa_contract(worker_id, output, context):
    if worker_id != "qa_worker" or not isinstance(output, dict):
        return output
    development = context.get("outputs", {}).get("development_worker", {})
    verified = development.get("verified_changed_files", [])
    if _APPROVAL_FIXTURE not in verified:
        return output
    requested = output.get("requested_test_executions")
    if not isinstance(requested, list):
        requested = []
        output["requested_test_executions"] = requested
    if not any(isinstance(item, dict) and item.get("argv") == _APPROVAL_FIXTURE_QA_ARGV for item in requested):
        requested.append({
            "argv": list(_APPROVAL_FIXTURE_QA_ARGV),
            "purpose": "Verify the exact approved AFDE-2.7 fixture state after the controlled write",
        })
    return output


def _validate_provider_output(worker_id, output):
    if worker_id != "development_worker":
        return output
    if not isinstance(output, dict):
        raise ProviderResponseError("Development Worker response must be a structured object")
    proposals = output.get("proposed_file_writes")
    if not isinstance(proposals, list):
        raise ProviderResponseError("Development Worker proposed_file_writes must be an array")
    for proposal in proposals:
        if not isinstance(proposal, dict):
            raise ProviderResponseError("FILE_WRITE proposal must be a structured object")
        required = ("action_type", "relative_path", "content", "purpose")
        if any(key not in proposal for key in required):
            raise ProviderResponseError("FILE_WRITE proposal is missing a required structured field")
        if proposal["action_type"] != "FILE_WRITE":
            raise ProviderResponseError("FILE_WRITE proposal action_type is invalid")
        if not isinstance(proposal["relative_path"], str) or not proposal["relative_path"].strip():
            raise ProviderResponseError("FILE_WRITE proposal relative_path is invalid")
        if not isinstance(proposal["content"], str) or not proposal["content"]:
            raise ProviderResponseError("FILE_WRITE proposal content must be complete literal file content")
        if not isinstance(proposal["purpose"], str):
            raise ProviderResponseError("FILE_WRITE proposal purpose is invalid")
        if _is_explicit_placeholder(proposal["content"]):
            raise ProviderResponseError("FILE_WRITE proposal content is descriptive or placeholder text")
    return output


def _is_explicit_placeholder(content):
    stripped = content.strip()
    lowered = stripped.lower()
    if lowered in {"...", "todo", "tbd", "<content>", "[content]", "content goes here", "insert content here"}:
        return True
    if re.fullmatch(r"[<(\[].*(?:placeholder|content goes here|insert .* here).*[>)\]]", lowered, re.DOTALL):
        return True
    return bool(
        stripped.startswith("(") and stripped.endswith(")")
        and "original content" in lowered
        and ("replace" in lowered or "replaced" in lowered)
    )
