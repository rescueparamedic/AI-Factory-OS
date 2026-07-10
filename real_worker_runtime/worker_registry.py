from .models import WorkerDefinition

WORKERS=(
 WorkerDefinition("pm_worker","PM Worker",1), WorkerDefinition("planning_worker","Planning Worker",2),
 WorkerDefinition("development_worker","Development Worker",3), WorkerDefinition("qa_worker","QA Worker",4),
 WorkerDefinition("documentation_worker","Documentation Worker",5),
)
class WorkerRegistry:
    def list(self): return WORKERS
