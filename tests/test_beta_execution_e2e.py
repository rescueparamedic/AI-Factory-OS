import json
from pathlib import Path

from afde.cli import main


def _run(tmp_path, capsys, request="Prepare the AFDE-4.0 Beta"):
    exit_code = main([
        "execute", "--request", request, "--provider", "mock",
        "--workspace", str(tmp_path), "--json",
    ])
    result = json.loads(capsys.readouterr().out)
    evidence = json.loads(
        (tmp_path / result["evidence_path"]).read_text(encoding="utf-8")
    )
    return exit_code, result, evidence


def test_official_beta_mock_cli_runs_the_complete_supported_path(
    tmp_path, capsys, monkeypatch,
):
    secret = "sk-beta-test-secret-value"
    monkeypatch.setenv("OPENAI_API_KEY", secret)

    exit_code, result, evidence = _run(
        tmp_path, capsys,
        "Prepare a bounded Beta task; Authorization: Bearer test-token-value",
    )

    assert exit_code == result["exit_code"] == 0
    assert result["status"] == "completed"
    assert result["stage"] == "completed"
    assert result["provider"] == "mock"
    assert result["model"] == "deterministic-mock-v1"
    assert result["execution_mode"] == "deterministic_mock"
    assert result["worker_id"] == "development_worker"
    assert len(result["results"]) == 1
    assert all(item["execution_status"] == "completed" for item in result["results"])

    assert evidence["schema_version"] == "1.0"
    assert evidence["execution_id"] == result["execution_id"]
    assert evidence["session_id"] == result["session_id"]
    assert evidence["request_id"] == result["request_id"]
    assert evidence["execution_status"] == "completed"
    assert evidence["planner"]["task_count"] == 3
    assert evidence["provider"] == {
        "name": "mock",
        "model": "deterministic-mock-v1",
        "execution_mode": "deterministic_mock",
    }
    assert evidence["worker"]["mode"] == "single_worker"
    assert evidence["worker"]["execution_order"] == "sequential"
    assert len(evidence["provider_response_summary"]) == 1
    assert len(evidence["worker_result_summary"]) == 1
    assert evidence["runtime_evidence"]["plan_id"] == result["plan_id"]
    assert evidence["runtime_evidence"]["worker_id"] == "development_worker"
    assert evidence["runtime_evidence"]["execution_status"] == "completed"
    assert evidence["security"]["credentials_persisted"] is False

    serialized = json.dumps(evidence, ensure_ascii=False)
    assert secret not in serialized
    assert "test-token-value" not in serialized
    assert "Mock response:" not in serialized
    assert "authorization" not in evidence["request"]["summary"].lower()
    assert "bearer" not in evidence["request"]["summary"].lower()


def test_mock_e2e_is_repeatable_three_times_without_cross_run_contamination(
    tmp_path, capsys,
):
    runs = [_run(tmp_path, capsys) for _ in range(3)]
    results = [item[1] for item in runs]
    evidence = [item[2] for item in runs]

    assert [item[0] for item in runs] == [0, 0, 0]
    assert len({item["execution_id"] for item in results}) == 3
    assert len({item["session_id"] for item in results}) == 3
    assert len({item["request_id"] for item in results}) == 3
    assert len({item["evidence_path"] for item in results}) == 3
    assert len({item["plan_id"] for item in results}) == 1
    assert all(item["execution_status"] == "completed" for item in evidence)
    assert all(
        Path(tmp_path, item["evidence_path"]).is_file() for item in results
    )
    assert len(list((tmp_path / "data" / "runtime_sessions").iterdir())) == 3
