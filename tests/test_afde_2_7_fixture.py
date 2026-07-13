from pathlib import Path


def test_approval_fixture_has_a_known_safe_state():
    value = (Path(__file__).parent / "fixtures" / "afde_2_7_approval_target.txt").read_text(encoding="utf-8")
    assert value in {"approval_state=baseline\n", "approval_state=approved\n"}
