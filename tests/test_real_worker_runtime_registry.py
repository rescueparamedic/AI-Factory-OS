from real_worker_runtime.worker_registry import WorkerRegistry
def test_five_workers(): assert len(WorkerRegistry().list())==5
def test_worker_order(): assert [x.order for x in WorkerRegistry().list()]==[1,2,3,4,5]
def test_worker_ids_unique():
 ids=[x.worker_id for x in WorkerRegistry().list()]; assert len(ids)==len(set(ids))
