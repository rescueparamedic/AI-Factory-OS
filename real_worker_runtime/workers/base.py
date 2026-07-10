from __future__ import annotations
from datetime import datetime
from ..models import WorkerResult
class BaseWorker:
    def __init__(self,definition,provider): self.definition=definition; self.provider=provider
    def can_handle(self,task): return bool(task)
    def execute(self,context):
        start=datetime.now().astimezone().isoformat(timespec="seconds")
        try:
            output=self.provider.generate(self.definition.worker_id,context["request"],context); return WorkerResult(self.definition.worker_id,"completed",start,datetime.now().astimezone().isoformat(timespec="seconds"),f"{self.definition.role} completed",output)
        except Exception as exc: return WorkerResult(self.definition.worker_id,"failed",start,datetime.now().astimezone().isoformat(timespec="seconds"),"worker failed",{},str(exc))
