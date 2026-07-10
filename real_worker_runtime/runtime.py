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

class RealWorkerRuntime:
    def __init__(self,root="."): self.root=Path(root).resolve()
    def run(self,request,provider="mock",live=True,include_approval_demo=False,max_revisions=1):
        selected=ProviderBridge(self.root); selected.select(provider)
        sid=f"RWS-{datetime.now().strftime('%Y%m%d-%H%M%S')}-{uuid4().hex[:6]}"; sprint=f"DEMO-{datetime.now().strftime('%Y%m%d-%H%M%S')}"
        workers={w.worker_id:("queued" if w.order==1 else "waiting") for w in WorkerRegistry().list()}
        session=RuntimeSession(sid,sprint,request,provider,"running",_now(),_now(),workers); store=ArtifactStore(self.root,sid); events=EventStream(store); bus=MessageBus(store,session); dash=TerminalDashboard(live)
        store.json("session.json",session.to_dict()); events.emit("RUNTIME_CREATED",detail=request); context={"request":request,"outputs":{}}
        previous="user"; revisions=0
        for index,definition in enumerate(WorkerRegistry().list()):
            for wid in workers:
                if workers[wid]=="queued": workers[wid]="waiting"
            workers[definition.worker_id]="running"; session.current_activity=f"{definition.role} is working..."; session.progress=index*20+10; dash.render(session); events.emit("WORKER_STARTED",definition.worker_id)
            result=BaseWorker(definition,selected).execute(context); session.results.append(asdict(result)); context["outputs"][definition.worker_id]=result.output
            if result.status!="completed": session.status="failed"; session.error=result.error; break
            workers[definition.worker_id]="completed"; bus.publish(previous,definition.worker_id,"TASK" if previous!="user" else "REQUEST",result.summary,result.output); previous=definition.worker_id
            if definition.worker_id=="qa_worker" and result.output.get("failed",0):
                if revisions>=max_revisions: session.status="failed"; session.error="QA failed after maximum revisions"; break
                revisions+=1; context["revision"]=revisions; events.emit("REVISION_STARTED","development_worker",f"revision {revisions}")
                for retry_id in ("development_worker","qa_worker"):
                    retry_def=next(item for item in WorkerRegistry().list() if item.worker_id==retry_id); retry=BaseWorker(retry_def,selected).execute(context); session.results.append(asdict(retry)); context["outputs"][retry_id]=retry.output; bus.publish("qa_worker" if retry_id=="development_worker" else "development_worker",retry_id,"REVISION",retry.summary,retry.output)
                if context["outputs"]["qa_worker"].get("failed",0): session.status="failed"; session.error="QA revision failed"; break
            session.progress=(index+1)*20; session.current_activity=result.summary; events.emit("WORKER_COMPLETED",definition.worker_id); dash.render(session)
        # Mandatory real Runner/Guardian path: harmless local validation.
        definition_path=store.json("runtime_sprint.json",{"sprint_id":sprint,"title":"Runtime validation","version":"1", "steps":[{"step_id":"RUNTIME-CHECK","name":"Python runtime","command":"python --version","cwd":str(self.root),"environment":"local"}]})
        runner_run=SprintAutoRunner(self.root).start(definition_path); session.runner_run_id=runner_run.run_id
        if runner_run.status!="completed": session.status=runner_run.status
        if include_approval_demo:
            from approval_guardian import ApprovalGuardian, ApprovalRequest
            for command in ("git reset --hard","git push origin develop"):
                decision=ApprovalGuardian(self.root).evaluate(ApprovalRequest(command=command,cwd=str(self.root),branch="feature/demo")); events.emit("APPROVAL_DEMO",detail=f"{command}: {decision.decision.value}")
        if session.status=="running": session.status="completed"
        session.progress=100 if session.status=="completed" else session.progress; session.updated_at=_now()
        artifacts={"plan.json":context["outputs"].get("planning_worker",{}),"implementation.json":context["outputs"].get("development_worker",{}),"qa_report.json":context["outputs"].get("qa_worker",{})}
        for name,data in artifacts.items(): session.artifacts.append({"type":name,"path":str(store.json(name,data))})
        report="# Real Worker Runtime Report\n\n"+f"Session: `{sid}`\n\nStatus: **{session.status.upper()}**\n\nRequest: {request}\n\nWorkers: 5\nMessages: {len(session.messages)}\nRunner: `{session.runner_run_id}`\n"
        session.artifacts.append({"type":"final_report","path":str(store.text("final_report.md",report))}); store.json("artifact_index.json",session.artifacts); store.json("session.json",session.to_dict()); events.emit("RUNTIME_COMPLETED",detail=session.status); dash.render(session); return session
    def status(self,sid):
        p=self.root/"data"/"runtime_sessions"/sid/"session.json"; return json.loads(p.read_text(encoding="utf-8"))
    def report(self,sid): return (self.root/"data"/"runtime_sessions"/sid/"final_report.md").read_text(encoding="utf-8")
    def cancel(self,sid):
        data=self.status(sid)
        if data["status"] in {"completed","failed","blocked","cancelled"}: raise ValueError("cannot cancel terminal session")
        data["status"]="cancelled"; ArtifactStore(self.root,sid).json("session.json",data); return data
def _now(): return datetime.now().astimezone().isoformat(timespec="seconds")
