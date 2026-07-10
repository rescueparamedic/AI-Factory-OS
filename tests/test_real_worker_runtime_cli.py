import json
from afde.cli import main
def test_factory_demo_json(tmp_path,monkeypatch,capsys):
 monkeypatch.chdir(tmp_path); main(["factory-demo","--request","demo","--provider","mock","--no-live","--json"]); assert json.loads(capsys.readouterr().out)["status"]=="completed"
def test_factory_demo_human(tmp_path,monkeypatch,capsys):
 monkeypatch.chdir(tmp_path); main(["factory-demo","--request","demo","--no-live"]); assert "Demo Complete" in capsys.readouterr().out
def test_status_and_report(tmp_path,monkeypatch,capsys):
 monkeypatch.chdir(tmp_path); main(["factory-demo","--request","demo","--no-live","--json"]); sid=json.loads(capsys.readouterr().out)["session_id"]; main(["runtime-status","--session-id",sid]); assert json.loads(capsys.readouterr().out)["session_id"]==sid; main(["runtime-report","--session-id",sid]); assert "Runtime Report" in capsys.readouterr().out
