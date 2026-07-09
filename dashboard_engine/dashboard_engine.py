from __future__ import annotations

from datetime import datetime
from pathlib import Path
from typing import Dict, Any
import html
import json
import webbrowser


class DashboardEngine:
    def __init__(self, base_path: Path, update_manager, agent_manager, team_manager, worker_runtime_engine, conversation_engine, event_bus):
        self.base_path = base_path
        self.update_manager = update_manager
        self.agent_manager = agent_manager
        self.team_manager = team_manager
        self.worker_runtime_engine = worker_runtime_engine
        self.conversation_engine = conversation_engine
        self.event_bus = event_bus
        self.dashboard_dir = base_path / "docs" / "dashboard"
        self.data_dir = base_path / "data" / "dashboard"
        self.dashboard_dir.mkdir(parents=True, exist_ok=True)
        self.data_dir.mkdir(parents=True, exist_ok=True)

    def build(self) -> Dict[str, Any]:
        now = datetime.now().astimezone()
        dashboard_id = f"DASH-{now.strftime('%Y%m%d-%H%M%S')}"
        snapshot = self._collect_snapshot(dashboard_id, now)
        html_path = self.dashboard_dir / "AI_FACTORY_DASHBOARD.html"
        json_path = self.data_dir / f"{dashboard_id}.json"
        html_path.write_text(self._render_html(snapshot), encoding="utf-8")
        json_path.write_text(json.dumps(snapshot, ensure_ascii=False, indent=2), encoding="utf-8")
        self.event_bus.publish("DASHBOARD_BUILT", {"dashboard_id": dashboard_id, "html_path": str(html_path), "json_path": str(json_path)})
        return {"dashboard_id": dashboard_id, "status": "completed", "html_path": str(html_path), "json_path": str(json_path), "created_at": now.isoformat(timespec="seconds"), "next_stage": "dashboard_review"}

    def latest(self) -> Dict[str, Any]:
        items = sorted(self.data_dir.glob("DASH-*.json"), reverse=True)
        if not items:
            raise FileNotFoundError("No dashboard found.")
        return json.loads(items[0].read_text(encoding="utf-8"))

    def open_dashboard(self) -> Dict[str, Any]:
        result = self.build()
        webbrowser.open(Path(result["html_path"]).resolve().as_uri())
        result["opened"] = True
        return result

    def _collect_snapshot(self, dashboard_id: str, now: datetime) -> Dict[str, Any]:
        return {
            "dashboard_id": dashboard_id,
            "created_at": now.isoformat(timespec="seconds"),
            "version": self._safe_call(self.update_manager.get_version, {}),
            "agents": self._safe_call(self.agent_manager.list_agents, []),
            "teams": self._safe_call(self.team_manager.list_teams, []),
            "runtime_workers": self._safe_call(self.worker_runtime_engine.list_workers, []),
            "providers": self._safe_call(self.worker_runtime_engine.list_providers, []),
            "latest_conversation": self._safe_latest(self.conversation_engine.latest),
            "latest_runtime": self._safe_latest(self.worker_runtime_engine.latest),
            "latest_pipeline": self._load_latest_json(self.base_path / "data" / "pipeline_runs", "PIPELINE-*.json"),
            "latest_release": self._load_latest_json(self.base_path / "data" / "release_history", "REL-*.json"),
            "latest_deployment": self._load_latest_json(self.base_path / "data" / "deployment_history", "DEPLOY-*.json"),
        }

    def _safe_call(self, fn, default):
        try:
            return fn()
        except Exception:
            return default

    def _safe_latest(self, fn):
        try:
            return fn()
        except Exception:
            return None

    def _load_latest_json(self, folder: Path, pattern: str):
        try:
            items = sorted(folder.glob(pattern), reverse=True)
            if not items:
                return None
            return json.loads(items[0].read_text(encoding="utf-8"))
        except Exception:
            return None

    def _esc(self, value):
        return html.escape(str(value if value is not None else ""))

    def _table(self, items, columns):
        if not items:
            return '<p class="muted">No data</p>'
        head = ''.join(['<th>' + self._esc(c) + '</th>' for c in columns])
        body = []
        for item in items:
            row = ''.join(['<td>' + self._esc(item.get(c, '')) + '</td>' for c in columns])
            body.append('<tr>' + row + '</tr>')
        return '<table><thead><tr>' + head + '</tr></thead><tbody>' + ''.join(body) + '</tbody></table>'

    def _metric(self, mapping):
        out = []
        for key, value in mapping.items():
            out.append('<div class="label">' + self._esc(key) + '</div><div class="value">' + self._esc(value) + '</div>')
        return '<div class="metric">' + ''.join(out) + '</div>'

    def _card(self, title, body, wide=False):
        cls = "card wide" if wide else "card"
        return '<section class="' + cls + '"><h2>' + self._esc(title) + '</h2>' + body + '</section>'

    def _messages_html(self, conversation):
        messages = (conversation or {}).get("messages") or []
        if not messages:
            return '<p class="muted">No conversation yet</p>'
        blocks = []
        for item in messages[:12]:
            block = '<div class="message"><div class="agent">' + self._esc(item.get("agent")) + ' <span>' + self._esc(item.get("role")) + '</span></div><div>' + self._esc(item.get("message")) + '</div></div>'
            blocks.append(block)
        return ''.join(blocks)

    def _render_html(self, snapshot: Dict[str, Any]) -> str:
        version = snapshot.get("version") or {}
        agents = snapshot.get("agents") or []
        teams = snapshot.get("teams") or []
        workers = snapshot.get("runtime_workers") or []
        providers = snapshot.get("providers") or []
        conversation = snapshot.get("latest_conversation") or {}
        runtime = snapshot.get("latest_runtime") or {}
        pipeline = snapshot.get("latest_pipeline") or {}
        release = snapshot.get("latest_release") or {}
        deployment = snapshot.get("latest_deployment") or {}

        cards = []
        cards.append(self._card("OS Version", self._metric({"version": version.get("version", ""), "sprint": version.get("sprint", ""), "build": version.get("build", ""), "status": version.get("status", "")})))
        cards.append(self._card("Latest Runtime", self._metric({"run_id": runtime.get("run_id", ""), "worker": runtime.get("worker_id", ""), "mode": runtime.get("mode", ""), "task": runtime.get("task", "")})))
        cards.append(self._card("AI Providers", self._table(providers, ["provider_id", "name", "status", "mode", "env_key"])))
        cards.append(self._card("Runtime Workers", self._table(workers, ["worker_id", "name", "status", "capability"])))
        cards.append(self._card("Agents", self._table(agents, ["agent_id", "name", "status"])))
        cards.append(self._card("Teams", self._table(teams, ["team_id", "name", "status"])))
        cards.append(self._card("Pipeline / Release / Deployment", self._metric({"pipeline": pipeline.get("pipeline_id", "No data") if pipeline else "No data", "release": release.get("release_id", "No data") if release else "No data", "deployment": deployment.get("deploy_id", "No data") if deployment else "No data"})))
        cards.append(self._card("Latest Conversation", self._metric({"conversation_id": conversation.get("conversation_id", ""), "plan_id": conversation.get("plan_id", ""), "message_count": conversation.get("message_count", ""), "request": conversation.get("request", "")})))
        cards.append(self._card("Conversation Messages", self._messages_html(conversation), wide=True))

        css = ":root{--bg:#0f172a;--panel:#111827;--text:#e5e7eb;--muted:#9ca3af;--accent:#38bdf8;--line:#334155}body{margin:0;font-family:'Segoe UI',Arial,sans-serif;background:linear-gradient(135deg,#020617,#111827);color:var(--text)}header{padding:28px 36px;border-bottom:1px solid var(--line);background:rgba(15,23,42,.94);position:sticky;top:0;z-index:10}h1{margin:0;font-size:28px}.subtitle{margin-top:8px;color:var(--muted)}main{padding:28px 36px 48px;display:grid;grid-template-columns:repeat(12,1fr);gap:18px}.card{grid-column:span 6;background:rgba(17,24,39,.92);border:1px solid var(--line);border-radius:16px;padding:20px;box-shadow:0 14px 35px rgba(0,0,0,.22)}.wide{grid-column:span 12}h2{margin:0 0 14px;font-size:18px;color:#f8fafc}.metric{display:grid;grid-template-columns:160px 1fr;gap:8px;line-height:1.8}.label{color:var(--muted)}.value{font-weight:600;word-break:break-all}table{width:100%;border-collapse:collapse;font-size:13px}th,td{border-bottom:1px solid var(--line);padding:9px 8px;text-align:left;vertical-align:top}th{color:var(--accent)}.muted{color:var(--muted)}.message{background:rgba(31,41,55,.75);border:1px solid var(--line);border-radius:12px;padding:12px 14px;margin-bottom:10px;line-height:1.55}.agent{font-weight:700;color:var(--accent);margin-bottom:6px}.agent span{color:var(--muted);font-weight:500;margin-left:6px}@media(max-width:1000px){main{grid-template-columns:1fr}.card,.wide{grid-column:span 1}}"
        return '<!doctype html><html lang="ko"><head><meta charset="utf-8"><title>AI Factory Dashboard</title><style>' + css + '</style></head><body><header><h1>AI Factory Dashboard</h1><div class="subtitle">AI가 개발하고 사람은 결정한다 · Snapshot ' + self._esc(snapshot.get("created_at")) + '</div></header><main>' + ''.join(cards) + '</main></body></html>'
