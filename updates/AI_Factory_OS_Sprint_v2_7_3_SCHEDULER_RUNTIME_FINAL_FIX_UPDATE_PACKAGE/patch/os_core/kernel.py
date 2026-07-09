from __future__ import annotations

from pathlib import Path

from os_core.decision_engine import DecisionEngine
from os_core.event_bus import EventBus
from os_core.task_engine import TaskEngine
from os_core.workflow_engine import WorkflowEngine
from os_core.worker_manager import WorkerManager
from runtime.product_loader import ProductLoader
from managers.agent_manager import AgentManager
from managers.team_manager import TeamManager
from update.update_manager import UpdateManager
from doctor.project_doctor import ProjectDoctor
from product_pipeline.product_pipeline import ProductDevelopmentPipeline
from repo.repository_manager import RepositoryManager
from planning_engine.planning_engine import PlanningEngine
from development_engine.development_engine import DevelopmentEngine
from package_builder.package_builder import PackageBuilder
from qa_engine.qa_engine import QAEngine
from documentation_engine.documentation_engine import DocumentationEngine
from approval_gate.approval_gate import ApprovalGate
from pipeline_orchestrator.pipeline_orchestrator import PipelineOrchestrator
from release_engine.release_engine import ReleaseEngine
from deployment_engine.deployment_engine import DeploymentEngine
from worker_runtime.worker_runtime_engine import WorkerRuntimeEngine
from conversation_engine.conversation_engine import AgentConversationEngine
from dashboard_engine.dashboard_engine import DashboardEngine
from dashboard_engine.live_dashboard import LiveDashboardEngine
from worker_runtime.real_ai_worker import RealAIWorker
from scheduler_engine.task_scheduler import TaskScheduler


class AIFactoryKernel:
    def __init__(self):
        self.base_path = Path(__file__).resolve().parent.parent
        self.event_bus = EventBus(self.base_path)
        self.decision_engine = DecisionEngine()
        self.task_engine = TaskEngine(self.base_path)
        self.workflow_engine = WorkflowEngine()
        self.worker_manager = WorkerManager(self.base_path)
        self.agent_manager = AgentManager()
        self.team_manager = TeamManager(self.worker_manager)
        self.product_loader = ProductLoader(self.base_path)
        self.update_manager = UpdateManager(self.base_path)
        self.project_doctor = ProjectDoctor(self.base_path)
        self.product_pipeline = ProductDevelopmentPipeline(self.base_path, self.product_loader, self.task_engine, self.workflow_engine, self.agent_manager, self.team_manager, self.worker_manager, self.event_bus)
        self.repository_manager = RepositoryManager(self.base_path)
        self.planning_engine = PlanningEngine(self.base_path, self.worker_manager, self.event_bus)
        self.development_engine = DevelopmentEngine(self.base_path, self.planning_engine, self.worker_manager, self.event_bus)
        self.package_builder = PackageBuilder(self.base_path)
        self.qa_engine = QAEngine(self.base_path, self.development_engine, self.worker_manager, self.event_bus)
        self.documentation_engine = DocumentationEngine(self.base_path, self.qa_engine, self.worker_manager, self.event_bus)
        self.approval_gate = ApprovalGate(self.base_path, self.documentation_engine, self.worker_manager, self.event_bus)
        self.pipeline_orchestrator = PipelineOrchestrator(self.base_path, self.planning_engine, self.development_engine, self.qa_engine, self.documentation_engine, self.approval_gate, self.worker_manager, self.event_bus)
        self.release_engine = ReleaseEngine(self.base_path, self.approval_gate, self.update_manager, self.worker_manager, self.event_bus)
        self.deployment_engine = DeploymentEngine(self.base_path, self.release_engine, self.worker_manager, self.event_bus)
        self.worker_runtime_engine = WorkerRuntimeEngine(self.base_path, self.worker_manager, self.event_bus)
        self.real_ai_worker = RealAIWorker(self.base_path, self.event_bus, self.worker_manager)
        self.task_scheduler = TaskScheduler(self.base_path, self.worker_manager, self.event_bus)
        self.conversation_engine = AgentConversationEngine(self.base_path, self.planning_engine, self.worker_runtime_engine, self.worker_manager, self.event_bus)
        self.dashboard_engine = DashboardEngine(self.base_path, self.update_manager, self.agent_manager, self.team_manager, self.worker_runtime_engine, self.conversation_engine, self.event_bus)
        self.live_dashboard_engine = LiveDashboardEngine(self.base_path, self.update_manager, self.agent_manager, self.team_manager, self.worker_runtime_engine, self.conversation_engine, self.event_bus)

    def boot(self):
        self.update_manager.version_manager.set_version("2.5.0", "v2.5-real-ai-worker", "mvp")
        return {"status": "success", "product_name": "Blog Growth Analyzer", "task_id": "LIVE-DASHBOARD", "workflow_status": "done", "ceo_decision": "approved", "pm_plan": "Live Dashboard added", "team_assigned": "documentation_team", "worker_result_path": "", "audit_log_path": "", "project_status_path": ""}


    def list_real_ai_providers(self): return self.real_ai_worker.list_providers()
    def run_real_ai_worker(self, prompt: str, provider_id: str = "mock", system: str = "", product_id: str = "blog_growth_analyzer"): return self.real_ai_worker.run(prompt=prompt, provider_id=provider_id, system=system, product_id=product_id)
    def get_latest_real_ai_run(self): return self.real_ai_worker.latest()
    def list_real_ai_runs(self, limit: int = 10): return self.real_ai_worker.list_runs(limit=limit)

    def scheduler_enqueue(self, title: str, worker_id: str, payload: dict | None = None, priority: str = "medium", product_id: str = "blog_growth_analyzer", max_retries: int = 2):
        return self.task_scheduler.enqueue(title=title, worker_id=worker_id, payload=payload or {}, priority=priority, product_id=product_id, max_retries=max_retries)
    def scheduler_status(self): return self.task_scheduler.status()
    def scheduler_list(self, status: str = "all", limit: int = 20): return self.task_scheduler.list_jobs(status=status, limit=limit)
    def scheduler_next(self): return self.task_scheduler.peek_next()
    def scheduler_run_next(self): return self.task_scheduler.run_next()
    def scheduler_run_all(self, limit: int = 10): return self.task_scheduler.run_all(limit=limit)
    def scheduler_run_job(self, job_id: str): return self.task_scheduler.run_job(job_id)
    def build_dashboard(self): return self.dashboard_engine.build()
    def open_dashboard(self): return self.dashboard_engine.open_dashboard()
    def get_latest_dashboard(self): return self.dashboard_engine.latest()
    def build_live_dashboard(self, refresh_seconds: int = 10): return self.live_dashboard_engine.build(refresh_seconds=refresh_seconds)
    def open_live_dashboard(self, refresh_seconds: int = 10): return self.live_dashboard_engine.open(refresh_seconds=refresh_seconds)
    def get_live_dashboard_status(self): return self.live_dashboard_engine.status()

    def run_agent_conversation(self, request: str, product_id: str = "blog_growth_analyzer"): return self.conversation_engine.run(request=request, product_id=product_id)
    def get_latest_agent_conversation(self): return self.conversation_engine.latest()
    def list_agent_conversations(self, limit: int = 10): return self.conversation_engine.list_conversations(limit=limit)
    def list_ai_providers(self): return self.worker_runtime_engine.list_providers()
    def list_runtime_workers(self): return self.worker_runtime_engine.list_workers()
    def run_runtime_worker(self, worker_id: str, task: str, product_id: str = "blog_growth_analyzer"): return self.worker_runtime_engine.run(worker_id=worker_id, task=task, product_id=product_id)
    def get_latest_runtime_run(self): return self.worker_runtime_engine.latest()
    def list_runtime_runs(self, limit: int = 10): return self.worker_runtime_engine.list_runs(limit=limit)
    def create_deployment(self, release_id: str | None = None, environment: str = "staging", apply: bool = False): return self.deployment_engine.create(release_id=release_id, environment=environment, apply=apply)
    def get_latest_deployment(self): return self.deployment_engine.latest()
    def list_deployments(self, limit: int = 10): return self.deployment_engine.list_deployments(limit=limit)
    def get_deployment_rollback(self, deploy_id: str | None = None): return self.deployment_engine.rollback_point(deploy_id=deploy_id)
    def create_release(self, approval_id: str | None = None, release_type: str = "patch"): return self.release_engine.create(approval_id=approval_id, release_type=release_type)
    def get_latest_release(self): return self.release_engine.latest()
    def list_releases(self, limit: int = 10): return self.release_engine.list_releases(limit=limit)
    def run_pipeline(self, request: str, product_id: str = "blog_growth_analyzer"): return self.pipeline_orchestrator.run(request=request, product_id=product_id)
    def get_latest_pipeline_result(self): return self.pipeline_orchestrator.latest()
    def list_pipeline_results(self, limit: int = 10): return self.pipeline_orchestrator.list_results(limit=limit)
    def create_approval_request(self, doc_id: str | None = None): return self.approval_gate.create(doc_id=doc_id)
    def get_approval(self, approval_id: str | None = None): return self.approval_gate.get(approval_id)
    def get_latest_approval(self): return self.approval_gate.latest()
    def approve_request(self, approval_id: str | None = None, by: str = "Owner"): return self.approval_gate.approve(approval_id, by=by)
    def reject_request(self, approval_id: str | None = None, reason: str = "수정 필요", by: str = "Owner"): return self.approval_gate.reject(approval_id, reason=reason, by=by)
    def list_approval_history(self, limit: int = 20): return self.approval_gate.history(limit=limit)
    def run_documentation_engine(self, qa_id: str | None = None): return self.documentation_engine.run(qa_id=qa_id)
    def list_documentation_results(self, limit: int = 10): return self.documentation_engine.list_results(limit=limit)
    def get_latest_documentation_result(self): return self.documentation_engine.latest_result()
    def run_qa_engine(self, dev_run_id: str | None = None): return self.qa_engine.run(dev_run_id=dev_run_id)
    def list_qa_results(self, limit: int = 10): return self.qa_engine.list_results(limit=limit)
    def get_latest_qa_result(self): return self.qa_engine.latest_result()
    def validate_patch_package(self, zip_path: str): return self.package_builder.validate_zip(zip_path)
    def run_development_engine(self, plan_id: str | None = None, apply_changes: bool = False): return self.development_engine.run(plan_id=plan_id, apply_changes=apply_changes)
    def list_development_runs(self, limit: int = 10): return self.development_engine.list_runs(limit=limit)
    def get_latest_development_run(self): return self.development_engine.latest_run()
    def create_development_plan(self, request: str, product_id: str = "blog_growth_analyzer"): return self.planning_engine.create_plan(request=request, product_id=product_id)
    def list_development_plans(self, limit: int = 10): return self.planning_engine.list_plans(limit=limit)
    def get_development_plan(self, plan_id: str | None = None): return self.planning_engine.get_plan(plan_id)
    def get_latest_development_plan(self): return self.planning_engine.get_latest_plan()
    def get_repository_status(self): return self.repository_manager.status()
    def create_repository_guide(self): return self.repository_manager.create_guide()
    def create_repository_snapshot(self): return self.repository_manager.create_snapshot()
    def list_products(self): return self.product_loader.list_products()
    def run_product_development(self, product_id: str, title: str, request: str): return self.product_pipeline.run(product_id, title, request)
    def get_product_pipeline_status(self): return self.product_pipeline.status()
    def get_version(self): return self.update_manager.get_version()
    def run_doctor(self): return self.project_doctor.run()
    def create_backup(self): return self.update_manager.create_backup()
    def check_update_readiness(self): return self.update_manager.check_readiness()
    def find_latest_patch(self): return self.update_manager.find_latest_patch()
    def preview_patch(self, patch_path: str | None = None): return self.update_manager.preview_patch(patch_path)
    def install_patch(self, patch_path: str | None = None): return self.update_manager.install_patch(patch_path)
    def rollback_update(self): return self.update_manager.rollback_latest()
    def get_update_history(self): return self.update_manager.get_history()
    def create_manual_task(self, title: str, description: str, product_id: str, assigned_worker: str):
        self.product_loader.load(product_id)
        task = self.task_engine.create_task(title, description, product_id, assigned_worker)
        self.event_bus.publish("TASK_CREATED_FROM_CLI", {"task_id": task["task_id"]})
        self._audit("TASK_CREATED_FROM_CLI", task["task_id"], "Manual task creation", "success", {"title": title, "product_id": product_id, "assigned_worker": assigned_worker})
        return task
    def list_tasks(self, limit: int = 20): return self.task_engine.list_tasks(limit=limit)
    def get_task(self, task_id: str): return self.task_engine.load_task(task_id)
    def update_task_status(self, task_id: str, status: str):
        task = self.task_engine.update_status(task_id, status)
        self.event_bus.publish("TASK_STATUS_UPDATED", {"task_id": task_id, "status": status})
        self._audit("TASK_STATUS_UPDATED", task_id, "Manual task status update", "success", {"status": status})
        return task
    def run_task_next(self, task_id: str):
        task = self.task_engine.load_task(task_id)
        task = self.workflow_engine.move_next(task)
        self.task_engine.save_task(task)
        self.event_bus.publish("TASK_WORKFLOW_NEXT", {"task_id": task_id, "status": task["status"]})
        self._audit("TASK_WORKFLOW_NEXT", task_id, "Workflow next transition", "success", {"status": task["status"]})
        return task
    def list_agents(self): return self.agent_manager.list_agents()
    def list_teams(self): return self.team_manager.list_teams()
    def list_workers(self): return self.worker_manager.list_workers()
    def run_worker_standard_test(self): return self.worker_manager.run("markdown_worker", {"filename": "docs/operations/v2_4_worker_test.md", "title": "AI Factory v2.4 Worker Standard Test", "body": ["Worker 표준 결과 테스트 문서입니다.", "v2.4에서도 WorkerResult 표준이 유지됩니다."]})
    def _audit(self, action: str, target: str, reason: str, result: str, metadata: dict):
        return self.worker_manager.run("audit_log_worker", {"actor": "AIFactoryKernel", "action": action, "target": target, "reason": reason, "result": result, "metadata": metadata})
