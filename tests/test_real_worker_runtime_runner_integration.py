from real_worker_runtime import RealWorkerRuntime
def test_runner_result_completed(tmp_path):
 s=RealWorkerRuntime(tmp_path).run("demo",live=False); import json; p=tmp_path/"data"/"sprint_runs"/f"{s.runner_run_id}.json"; assert json.loads(p.read_text())["status"]=="completed"
def test_guardian_audit_exists(tmp_path): RealWorkerRuntime(tmp_path).run("demo",live=False); assert list((tmp_path/"data"/"audit").glob("AUD-AGV2-*.json"))
