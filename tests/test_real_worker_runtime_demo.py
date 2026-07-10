from real_worker_runtime import RealWorkerRuntime
def test_demo_completed(tmp_path):
 s=RealWorkerRuntime(tmp_path).run("demo",live=False); assert s.status=="completed" and s.progress==100
def test_demo_messages(tmp_path): assert len(RealWorkerRuntime(tmp_path).run("demo",live=False).messages)>=4
def test_demo_artifacts(tmp_path): assert len(RealWorkerRuntime(tmp_path).run("demo",live=False).artifacts)>=4
def test_demo_runner(tmp_path): assert RealWorkerRuntime(tmp_path).run("demo",live=False).runner_run_id
def test_approval_demo(tmp_path): assert RealWorkerRuntime(tmp_path).run("demo",live=False,include_approval_demo=True).status=="completed"
