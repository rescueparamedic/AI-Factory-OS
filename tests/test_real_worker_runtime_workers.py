import pytest
from real_worker_runtime.provider_bridge import ProviderBridge
from real_worker_runtime.worker_registry import WorkerRegistry
from real_worker_runtime.workers import BaseWorker
@pytest.mark.parametrize("definition",WorkerRegistry().list())
def test_worker_mock_outputs(tmp_path,definition):
 r=BaseWorker(definition,ProviderBridge(tmp_path)).execute({"request":"demo"}); assert r.status=="completed" and r.output
def test_worker_can_handle(tmp_path): assert BaseWorker(WorkerRegistry().list()[0],ProviderBridge(tmp_path)).can_handle("x")
