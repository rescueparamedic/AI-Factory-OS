import pytest
from real_worker_runtime.models import WorkerState,RuntimeState,WorkerMessage
@pytest.mark.parametrize("value",[x.value for x in WorkerState])
def test_worker_states(value): assert WorkerState(value).value==value
@pytest.mark.parametrize("value",[x.value for x in RuntimeState])
def test_runtime_states(value): assert RuntimeState(value).value==value
def test_message_ids():
 a=WorkerMessage.create("s","a","b","TASK","x"); b=WorkerMessage.create("s","a","b","TASK","x"); assert a.message_id!=b.message_id and a.correlation_id
