from __future__ import annotations
from dataclasses import asdict
from datetime import datetime
import json
from pathlib import Path
from uuid import uuid4
from sprint_auto_runner import SprintAutoRunner
from .artifact_store import ArtifactStore
from .dashboard import TerminalDashboard
from .event_stream import EventStream
from .message_bus import MessageBus
from .models import RuntimeSession
from .provider_bridge import ProviderBridge
from .worker_registry import WorkerRegistry
from .workers import BaseWorker
from .execution_truth import apply_execution_truth_contract, claimed_qa_failures
from .controlled_execution import ControlledExecutor, ExecutionRequest

class RealWorkerRuntime:
    def __init__(self,root="."): self.root=Path(root).resolve()
    def run(self,request,provider="mock",live=True,include_approval_demo=False,max_revisions=1,model=None,allow_live_api=False,openai_client=None,enable_controlled_execution=False):
        selected=ProviderBridge(self.root,model,allow_live_api,openai_client); selected.select(provider)
        sid=f"RWS-{datetime.now().strftime('%Y%m%d-%H%M%S')}-{uuid4().hex[:6]}"; sprint=f"DEMO-{datetime.now().strftime('%Y%m%d-%H%M%S')}"
        workers={w.worker_id:("queued" if w.order==1 else "waiting") for w in WorkerRegistry().list()}
        session=RuntimeSession(sid,sprint,request,provider,"running",_now(),_now(),workers); store=ArtifactStore(self.root,sid); events=EventStream(store); bus=MessageBus(store,session); dash=TerminalDashboard(live)
        store.json("session.json",session.to_dict()); events.emit("RUNTIME_CREATED",detail=request); context={"request":request,"outputs":{}}
        previous="user"; revisions=0; controlled=ControlledExecutor(self.root) if enable_controlled_execution else None
        for index,definition in enumerate(WorkerRegistry().list()):
            for wid in workers:
                if workers[wid]=="queued": workers[wid]="waiting"
            workers[definition.worker_id]="running"; session.current_activity=f"{definition.role} is working..."; session.progress=index*20+10; dash.render(session); events.emit("WORKER_STARTED",definition.worker_id)
            result=BaseWorker(definition,selected).execute(context)
            if result.status=="completed":
                evidence=_execute_proposals(controlled,definition.worker_id,result.output)
                result.output, findings=apply_execution_truth_contract(definition.worker_id,result.output,evidence)
                session.truth_contract_findings.extend(findings)
                _merge_execution_evidence(session,evidence)
            session.results.append(asdict(result)); context["outputs"][definition.worker_id]=result.output
            if result.status!="completed": session.status="failed"; session.error=result.error; events.emit("PROVIDER_ERROR",definition.worker_id,result.error); break
            workers[definition.worker_id]="completed"; bus.publish(definition.worker_id,"runtime","WORKER_OUTPUT",result.summary,result.output); previous=definition.worker_id
            if definition.worker_id=="qa_worker" and claimed_qa_failures(result.output):
                if revisions>=max_revisions: session.status="failed"; session.error="QA failed after maximum revisions"; break
                revisions+=1; context["revision"]=revisions; events.emit("REVISION_STARTED","development_worker",f"revision {revisions}")
                for retry_id in ("development_worker","qa_worker"):
                    retry_def=next(item for item in WorkerRegistry().list() if item.worker_id==retry_id); retry=BaseWorker(retry_def,selected).execute(context)
                    if retry.status=="completed":
                        evidence=_execute_proposals(controlled,retry_id,retry.output); retry.output,findings=apply_execution_truth_contract(retry_id,retry.output,evidence); session.truth_contract_findings.extend(findings); _merge_execution_evidence(session,evidence)
                    session.results.append(asdict(retry)); context["outputs"][retry_id]=retry.output; bus.publish(retry_id,"runtime","WORKER_OUTPUT",retry.summary,retry.output)
                if claimed_qa_failures(context["outputs"]["qa_worker"]): session.status="failed"; session.error="QA revision failed"; break
            session.progress=(index+1)*20; session.current_activity=result.summary; metadata=result.output.get("_provider",{}); events.emit("WORKER_COMPLETED",definition.worker_id,json.dumps(metadata) if metadata else ""); dash.render(session)
        # Mandatory real Runner/Guardian path: harmless local validation.
        definition_path=store.json("runtime_sprint.json",{"sprint_id":sprint,"title":"Runtime validation","version":"1", "steps":[{"step_id":"RUNTIME-CHECK","name":"Python runtime","command":"python --version","cwd":str(self.root),"environment":"local"}]})
        runner_run=SprintAutoRunner(self.root).start(definition_path); session.runner_run_id=runner_run.run_id
        if runner_run.status!="completed": session.status=runner_run.status
        if include_approval_demo:
            from approval_guardian import ApprovalGuardian, ApprovalRequest
            for command in ("git reset --hard","git push origin develop"):
                decision=ApprovalGuardian(self.root).evaluate(ApprovalRequest(command=command,cwd=str(self.root),branch="feature/demo")); events.emit("APPROVAL_DEMO",detail=f"{command}: {decision.decision.value}")
        if session.status=="running": session.status="completed"
        if session.execution_verification["verified_changed_files"] and session.execution_verification["verified_test_executions"]:
            session.execution_verification["status"]="VERIFIED"
        session.execution_verification["findings"]=[item["classification"] for item in session.truth_contract_findings]
        session.progress=100 if session.status=="completed" else session.progress; session.updated_at=_now()
        artifacts={"plan.json":context["outputs"].get("planning_worker",{}),"implementation.json":context["outputs"].get("development_worker",{}),"qa_report.json":context["outputs"].get("qa_worker",{})}
        for name,data in artifacts.items(): session.artifacts.append({"type":name,"path":str(store.json(name,data))})
        report=_truthful_report(session,context)
        session.artifacts.append({"type":"final_report","path":str(store.text("final_report.md",report))}); store.json("artifact_index.json",session.artifacts); store.json("session.json",session.to_dict()); events.emit("RUNTIME_COMPLETED",detail=session.status); dash.render(session); return session
    def status(self,sid):
        p=self.root/"data"/"runtime_sessions"/sid/"session.json"; return json.loads(p.read_text(encoding="utf-8"))
    def report(self,sid): return (self.root/"data"/"runtime_sessions"/sid/"final_report.md").read_text(encoding="utf-8")
    def cancel(self,sid):
        data=self.status(sid)
        if data["status"] in {"completed","failed","blocked","cancelled"}: raise ValueError("cannot cancel terminal session")
        data["status"]="cancelled"; ArtifactStore(self.root,sid).json("session.json",data); return data
def _now(): return datetime.now().astimezone().isoformat(timespec="seconds")

def _execute_proposals(executor,worker_id,output):
    evidence={"verified_changed_files":[],"verified_test_executions":[],"execution_evidence":[]}
    if executor is None: return evidence
    if worker_id=="development_worker":
        for item in output.get("proposed_file_writes",[]):
            if not isinstance(item,dict): continue
            request=ExecutionRequest.file_write(item.get("relative_path",""),item.get("content",""),worker_id,item.get("purpose",""))
            observed=executor.execute(request); evidence["execution_evidence"].append(observed)
            if observed.get("status")=="SUCCEEDED" and observed.get("changed"): evidence["verified_changed_files"].append(observed["relative_path"])
    if worker_id=="qa_worker":
        for item in output.get("requested_test_executions",[]):
            if not isinstance(item,dict) or not isinstance(item.get("argv"),list): continue
            request=ExecutionRequest.command_run(item["argv"],worker_id,item.get("purpose",""))
            observed=executor.execute(request); evidence["execution_evidence"].append(observed)
            if observed.get("status") in {"SUCCEEDED","FAILED"}: evidence["verified_test_executions"].append(observed)
    return evidence

def _merge_execution_evidence(session,evidence):
    session.execution_verification["verified_changed_files"].extend(evidence.get("verified_changed_files",[]))
    session.execution_verification["verified_test_executions"].extend(evidence.get("verified_test_executions",[]))
    session.execution_verification.setdefault("evidence",[]).extend(evidence.get("execution_evidence",[]))

def _truthful_report(session,context):
    plan=context["outputs"].get("planning_worker",{}); implementation=context["outputs"].get("development_worker",{}); qa=context["outputs"].get("qa_worker",{}); documentation=context["outputs"].get("documentation_worker",{})
    findings=", ".join(sorted({item["classification"] for item in session.truth_contract_findings})) or "None"
    return (
      "# Real Worker Runtime Report\n\n"
      f"Session: `{session.session_id}`\n\nOrchestration status: **{session.status.upper()}**\n\n"
      f"Execution verification: **{session.execution_verification['status']}**\n\nRequest: {session.request}\n\n"
      "## Plan\n\n"+"\n".join(f"- {item}" for item in plan.get("tasks",[]))+"\n\n"
      "## Provider Development Claims\n\n"
      f"{implementation.get('implementation_summary','')}\n\nProposed files: {implementation.get('proposed_files',[])}\n\n"
      f"Runtime-verified changed files: {implementation.get('verified_changed_files',[])}\n\n"
      "## Provider QA Claims\n\n"
      f"Claimed test commands: {qa.get('claimed_test_commands',[])}\n\nClaimed results: {qa.get('claimed_test_results',{})}\n\n"
      f"Runtime-verified test executions: {qa.get('verified_test_executions',[])}\n\n"
      "## Provider Documentation Claim (Not Runtime Verification)\n\n"
      f"{documentation.get('user_summary','')}\n\n## Truth Contract Findings\n\n{findings}\n\n"
      f"Workers: {len(session.workers)}\nMessages: {len(session.messages)}\nRunner: `{session.runner_run_id}`\n"
    )
