from real_worker_runtime.dashboard import TerminalDashboard
from real_worker_runtime.models import RuntimeSession
def test_no_live_silent(capsys):
 TerminalDashboard(False).render(RuntimeSession("s","sp","r","mock","running","a","a",{})); assert capsys.readouterr().out==""
def test_live_snapshot(capsys):
 TerminalDashboard(True).render(RuntimeSession("s","sp","r","mock","running","a","a",{"pm_worker":"running"},10,"working")); assert "Progress: 10%" in capsys.readouterr().out
