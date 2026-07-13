import json
from types import SimpleNamespace

from real_worker_runtime import RealWorkerRuntime

from tests.test_approval_resume import APPROVED, BASELINE, prepare_root


class LiveShapeResponses:
    def __init__(self, empty_qa=False):
        self.calls = []
        self.empty_qa = empty_qa

    def create(self, **kwargs):
        self.calls.append(kwargs)
        instructions = kwargs["instructions"]
        if "PM." in instructions:
            body = {"request_summary":"edit fixture","goal":"validate approval","constraints":[],"definition_of_done":[],"risk_notes":[]}
        elif "planning worker" in instructions:
            body = {"tasks":["edit fixture"],"dependencies":[],"assigned_workers":["development_worker","qa_worker"],"acceptance_criteria":["approval required"]}
        elif "development worker" in instructions:
            body = {
                "implementation_summary":"Propose exact fixture edit",
                "proposed_files":["tests/fixtures/afde_2_7_approval_target.txt"],
                "proposed_test_commands":["python -m pytest tests/test_afde_2_7_fixture.py -q"],
                "claimed_artifacts":[],
                "proposed_file_writes":[{
                    "action_type":"FILE_WRITE",
                    "relative_path":"tests/fixtures/afde_2_7_approval_target.txt",
                    "content":APPROVED,
                    "purpose":"mocked OpenAI approval lifecycle",
                }],
            }
        elif "QA worker" in instructions:
            body = {
                "claimed_test_commands":[] if self.empty_qa else ["python -m pytest tests/test_afde_2_7_fixture.py -q"],
                "claimed_passed":0 if self.empty_qa else 1,"claimed_failed":0,"issues":[],"recommendation":"PASS",
                "requested_test_executions":[] if self.empty_qa else [{
                    "argv":["python","-m","pytest","tests/test_afde_2_7_fixture.py","-q"],
                    "purpose":"validate approved fixture",
                }],
            }
        else:
            body = {"runtime_report":"verified evidence only","artifact_index":"session artifacts","user_summary":"approval resumed safely"}
        return SimpleNamespace(
            output_text=json.dumps(body), id=f"resp_{len(self.calls)}", model=kwargs["model"]
        )


def test_mocked_openai_full_pause_resume_lifecycle(tmp_path, monkeypatch):
    fixture = prepare_root(tmp_path)
    monkeypatch.setenv("OPENAI_API_KEY", "test-placeholder")
    responses = LiveShapeResponses()
    client = SimpleNamespace(responses=responses)
    runtime = RealWorkerRuntime(tmp_path)
    paused = runtime.run(
        "edit fixture", provider="openai", live=False, max_revisions=0,
        model="test-model", allow_live_api=True, openai_client=client,
        enable_controlled_execution=True,
    )
    assert paused.status == "waiting_approval"
    assert fixture.read_text() == BASELINE
    resumed = RealWorkerRuntime(tmp_path).approval_approve(
        paused.pending_approval["approval_request_id"], openai_client=client
    )
    assert resumed.status == "completed"
    assert resumed.execution_verification["status"] == "VERIFIED"
    assert fixture.read_text() == APPROVED
    assert len(responses.calls) == 5


def test_live_provider_empty_qa_request_gets_bounded_fixture_validation(tmp_path, monkeypatch):
    fixture = prepare_root(tmp_path)
    monkeypatch.setenv("OPENAI_API_KEY", "test-placeholder")
    responses = LiveShapeResponses(empty_qa=True)
    client = SimpleNamespace(responses=responses)
    paused = RealWorkerRuntime(tmp_path).run(
        "edit fixture", provider="openai", live=False, max_revisions=0,
        model="test-model", allow_live_api=True, openai_client=client,
        enable_controlled_execution=True,
    )
    resumed = RealWorkerRuntime(tmp_path).approval_approve(
        paused.pending_approval["approval_request_id"], openai_client=client
    )
    executions = resumed.execution_verification["verified_test_executions"]
    assert fixture.read_bytes() == APPROVED.encode("utf-8")
    assert len(executions) == 1
    assert executions[0]["status"] == "SUCCEEDED"
    assert executions[0]["argv"] == [
        "python", "-m", "pytest", "tests/test_afde_2_7_fixture.py", "-q",
    ]
    assert resumed.execution_verification["status"] == "VERIFIED"
