import json

from afde.cli import main


def test_plan_create_and_show_json(tmp_path, capsys):
    create_code = main([
        "plan", "create", "--goal", "Ship planner MVP",
        "--workspace", str(tmp_path), "--json",
    ])
    created = json.loads(capsys.readouterr().out)

    show_code = main([
        "plan", "show", "--plan-id", created["plan_id"],
        "--workspace", str(tmp_path), "--json",
    ])
    shown = json.loads(capsys.readouterr().out)

    assert create_code == 0
    assert show_code == 0
    assert shown == created
    assert len(shown["tasks"]) == 3


def test_plan_create_and_show_human_output(tmp_path, capsys):
    assert main([
        "plan", "create", "--goal", "Human plan",
        "--workspace", str(tmp_path),
    ]) == 0
    output = capsys.readouterr().out

    assert "AI Factory OS - Execution Plan" in output
    assert "Prepare execution" in output
    plan_id = next(
        line.split(": ", 1)[1] for line in output.splitlines()
        if line.startswith("Plan ID:")
    )
    assert main([
        "plan", "show", "--plan-id", plan_id,
        "--workspace", str(tmp_path),
    ]) == 0
    assert plan_id in capsys.readouterr().out


def test_plan_cli_invalid_goal_and_unknown_plan_exit_codes(tmp_path, capsys):
    assert main([
        "plan", "create", "--goal", "   ",
        "--workspace", str(tmp_path), "--json",
    ]) == 2
    assert json.loads(capsys.readouterr().out)["status"] == "invalid"

    assert main([
        "plan", "show", "--plan-id", "PLAN-0000000000000000",
        "--workspace", str(tmp_path), "--json",
    ]) == 4
    assert json.loads(capsys.readouterr().out)["status"] == "not_found"
