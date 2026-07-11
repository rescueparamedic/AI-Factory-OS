from __future__ import annotations
from afde.provider_manager import ProviderManager
from .errors import ProviderConfigurationError

class ProviderBridge:
    def __init__(self, root): self.manager=ProviderManager(root)
    def select(self, provider="mock"):
        provider=provider.lower()
        statuses={x["provider"]:x for x in self.manager.as_dicts()}
        if provider not in {"mock","openai","gemini"}: raise ProviderConfigurationError(f"Unknown provider: {provider}")
        if provider=="mock": return {"provider":"mock","mode":"deterministic_mock"}
        if not statuses[provider]["configured"]: raise ProviderConfigurationError(f"{provider} is not configured; use --provider mock or configure its API key")
        raise ProviderConfigurationError(f"{provider} is configured but external execution is not enabled in this MVP; no paid call was made")
    def generate(self, worker_id, request, context):
        # Deterministic, visible output; never performs network access.
        templates={
          "pm_worker":{"request_summary":request,"goal":"Deliver a small validated implementation plan","constraints":["local safe mode","no external API"],"definition_of_done":["plan","implementation","QA","documentation"],"risk_notes":["mock output"]},
          "planning_worker":{"tasks":["analyze request","prepare implementation","validate result","document outcome"],"dependencies":["PM analysis"],"assigned_workers":["development_worker","qa_worker","documentation_worker"],"acceptance_criteria":["runner validation passes","artifacts saved"]},
          "development_worker":{"implementation_summary":"Prepared a deterministic implementation candidate without modifying project source.","changed_files":[],"commands_requested":["python --version"],"artifacts":["implementation.json"]},
          "qa_worker":{"tests_run":["Sprint Auto Runner python version validation"],"passed":0 if "[qa-fail-once]" in request and context.get("revision",0)==0 else 1,"failed":1 if "[qa-fail-once]" in request and context.get("revision",0)==0 else 0,"issues":["mock revision requested"] if "[qa-fail-once]" in request and context.get("revision",0)==0 else [],"recommendation":"REVISE" if "[qa-fail-once]" in request and context.get("revision",0)==0 else "PASS"},
          "documentation_worker":{"runtime_report":"final_report.md","artifact_index":"artifact_index.json","user_summary":"Five-worker demo completed successfully."},
        }
        return templates[worker_id]
