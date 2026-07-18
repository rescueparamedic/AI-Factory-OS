"""AFDE real execution pipeline foundation."""

from real_worker_runtime.execution_adapter import SingleWorkerExecutionAdapter
from real_worker_runtime.models import ExecutionInput, WorkerExecutionResult

from .bridge import ProviderRuntimeBridge
from .pipeline import RealExecutionPipeline

__all__ = [
    "ExecutionInput",
    "ProviderRuntimeBridge",
    "RealExecutionPipeline",
    "SingleWorkerExecutionAdapter",
    "WorkerExecutionResult",
]
