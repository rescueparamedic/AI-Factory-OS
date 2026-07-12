from __future__ import annotations
from afde.provider_manager import ProviderManager
from .errors import ProviderConfigurationError

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
        if self.provider != "mock": return self.provider.generate(worker_id,request,context)
        # Deterministic, visible output; never performs network access.
        templates={
          "pm_worker":{"request_summary":request,"goal":"Deliver a small validated implementation plan","constraints":["local safe mode","no external API"],"definition_of_done":["plan","implementation","QA","documentation"],"risk_notes":["mock output"]},
          "planning_worker":{"tasks":["analyze request","prepare implementation","validate result","document outcome"],"dependencies":["PM analysis"],"assigned_workers":["development_worker","qa_worker","documentation_worker"],"acceptance_criteria":["runner validation passes","artifacts saved"]},
          "development_worker":{"implementation_summary":"Prepared a deterministic implementation candidate without modifying project source.","proposed_files":["controlled_execution/hello_from_afde.py"] if "[controlled-execution-mvp]" in request else [],"proposed_test_commands":["python controlled_execution/hello_from_afde.py"] if "[controlled-execution-mvp]" in request else ["python --version"],"claimed_artifacts":["implementation.json"],"proposed_file_writes":[{"relative_path":"controlled_execution/hello_from_afde.py","content":"print(\"Hello from AFDE.\")\n","purpose":"Deterministic controlled execution proof"}] if "[controlled-execution-mvp]" in request else []},
          "qa_worker":{"claimed_test_commands":["python controlled_execution/hello_from_afde.py"] if "[controlled-execution-mvp]" in request else ["Sprint Auto Runner python version validation"],"claimed_passed":0 if "[qa-fail-once]" in request and context.get("revision",0)==0 else 1,"claimed_failed":1 if "[qa-fail-once]" in request and context.get("revision",0)==0 else 0,"issues":["mock revision requested"] if "[qa-fail-once]" in request and context.get("revision",0)==0 else [],"recommendation":"REVISE" if "[qa-fail-once]" in request and context.get("revision",0)==0 else "PASS","requested_test_executions":[{"argv":["python","controlled_execution/hello_from_afde.py"],"purpose":"Validate deterministic controlled file"}] if "[controlled-execution-mvp]" in request else []},
          "documentation_worker":{"runtime_report":"final_report.md","artifact_index":"artifact_index.json","user_summary":"Five-worker demo completed successfully."},
        }
        return templates[worker_id]
