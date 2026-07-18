"""Paid AFDE Beta E2E; skipped unless all live opt-ins are present."""

import json
import os

import pytest

from afde.cli import main


pytestmark = pytest.mark.skipif(
    not (
        os.environ.get("OPENAI_API_KEY")
        and os.environ.get("AI_FACTORY_RUN_LIVE_OPENAI_TESTS") == "1"
    ),
    reason="requires OPENAI_API_KEY and AI_FACTORY_RUN_LIVE_OPENAI_TESTS=1",
)


def test_official_beta_openai_e2e_is_explicit_and_persists_evidence(
    tmp_path, capsys,
):
    exit_code = main([
        "execute",
        "--request", "Return one concise bounded implementation instruction.",
        "--provider", "openai",
        "--allow-live-api",
        "--workspace", str(tmp_path),
        "--json",
    ])
    result = json.loads(capsys.readouterr().out)
    evidence = json.loads(
        (tmp_path / result["evidence_path"]).read_text(encoding="utf-8")
    )

    assert exit_code == result["exit_code"] == 0
    assert result["status"] == "completed"
    assert result["provider"] == "openai"
    assert result["execution_mode"] == "live"
    assert evidence["execution_status"] == "completed"
    assert evidence["provider"]["name"] == "openai"
    assert evidence["runtime_evidence"]["execution_status"] == "completed"
