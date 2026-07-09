from __future__ import annotations

from datetime import datetime
from pathlib import Path
from typing import Dict, Any
import html
import json
import webbrowser
from worker_runtime.real_ai_worker import ProviderRegistry


class LiveDashboardEngine:
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

    def build(self, refresh_seconds: int = 10) -> Dict[str, Any]:
        now = datetime.now().astimezone()
        live_id = f"LIVE-{now.strftime('%Y%m%d-%H%M%S')}"
        snapshot = self._snapshot(live_id, now, refresh_seconds)
        html_path = self.dashboard_dir / "AI_FACTORY_LIVE_DASHBOARD.html"
        json_path = self.data_dir / f"{live_id}.json"
        html_path.write_text(self._render(snapshot), encoding="utf-8")
        json_path.write_text(json.dumps(snapshot, ensure_ascii=False, indent=2), encoding="utf-8")
        self.event_bus.publish("LIVE_DASHBOARD_BUILT", {"live_id": live_id, "html_path": str(html_path), "json_path": str(json_path)})
        return {"status": "completed", "live_id": live_id, "html_path": str(html_path), "json_path": str(json_path), "refresh_seconds": refresh_seconds, "created_at": now.isoformat(timespec="seconds"), "next_stage": "live_dashboard_review"}

    def open(self, refresh_seconds: int = 10) -> Dict[str, Any]:
        result = self.build(refresh_seconds=refresh_seconds)
        webbrowser.open(Path(result["html_path"]).resolve().as_uri())
        result["opened"] = True
        return result

    def status(self) -> Dict[str, Any]:
        html_path = self.dashboard_dir / "AI_FACTORY_LIVE_DASHBOARD.html"
        snapshots = sorted(self.data_dir.glob("LIVE-*.json"), reverse=True)
        latest = {}
        if snapshots:
            try:
                latest = json.loads(snapshots[0].read_text(encoding="utf-8"))
            except Exception:
                latest = {}
        return {"status": "available" if html_path.exists() else "not_built", "html_path": str(html_path), "latest_live_id": latest.get("live_id", ""), "latest_created_at": latest.get("created_at", ""), "snapshot_count": len(snapshots)}

    def _snapshot(self, live_id: str, now: datetime, refresh_seconds: int) -> Dict[str, Any]:
        version = self._safe(self.update_manager.get_version, {})
        agents = self._safe(self.agent_manager.list_agents, [])
        teams = self._safe(self.team_manager.list_teams, [])
        workers = self._safe(self.worker_runtime_engine.list_workers, [])
        providers = self._safe(self.worker_runtime_engine.list_providers, [])
        real_ai_providers = self._safe(ProviderRegistry().list_providers, [])
        conversation = self._latest(self.conversation_engine.latest)
        runtime = self._latest(self.worker_runtime_engine.latest)
        latest_ai = self._latest_files(self.base_path / "data" / "ai_runs", "AI-*.json", 1)
        latest_session = self._latest_files(self.base_path / "data" / "agent_sessions", "SESSION-*_result.json", 1)
        session_messages = []
        if latest_session:
            sid = latest_session[0].get("session_id", "")
            bus_path = self.base_path / "data" / "message_bus" / f"{sid}.jsonl"
            if bus_path.exists():
                for line in bus_path.read_text(encoding="utf-8").splitlines()[:10]:
                    try:
                        session_messages.append(json.loads(line))
                    except Exception:
                        pass
        events = self._latest_files(self.base_path / "data" / "events", "*.json", 8)
        tasks = self._latest_files(self.base_path / "data" / "tasks", "*.json", 8)
        scheduler_jobs = self._scheduler_jobs(limit=12)
        audits = self._latest_files(self.base_path / "data" / "audit", "*.json", 5)
        done = sum(1 for t in tasks if str(t.get("status", "")).lower() in ["done", "completed"])
        scheduler_counts = {}
        for job in scheduler_jobs:
            st = str(job.get("status", "queued"))
            scheduler_counts[st] = scheduler_counts.get(st, 0) + 1
        return {
            "live_id": live_id,
            "created_at": now.isoformat(timespec="seconds"),
            "refresh_seconds": refresh_seconds,
            "version": version,
            "agents": agents,
            "teams": teams,
            "workers": workers,
            "providers": providers,
            "real_ai_providers": real_ai_providers,
            "latest_ai": latest_ai[0] if latest_ai else None,
            "latest_agent_session": latest_session[0] if latest_session else None,
            "session_messages": session_messages,
            "latest_conversation": conversation,
            "latest_runtime": runtime,
            "events": events,
            "tasks": tasks,
            "scheduler_jobs": scheduler_jobs,
            "scheduler_counts": scheduler_counts,
            "audits": audits,
            "metrics": {"agents": len(agents), "teams": len(teams), "workers": len(workers), "providers": len(providers), "real_ai_providers": len(real_ai_providers), "agent_sessions": 1 if latest_session else 0, "session_messages": len(session_messages), "recent_tasks": len(tasks), "completed_tasks": done, "queued_jobs": scheduler_counts.get("queued", 0), "running_jobs": scheduler_counts.get("running", 0), "completed_jobs": scheduler_counts.get("completed", 0), "failed_jobs": scheduler_counts.get("failed", 0), "events": len(events), "audits": len(audits)},
        }

    def _scheduler_jobs(self, limit: int = 12):
        path = self.base_path / "data" / "scheduler" / "worker_queue.json"
        if not path.exists():
            return []
        try:
            data = json.loads(path.read_text(encoding="utf-8"))
            if not isinstance(data, list):
                return []
            return sorted(data, key=lambda j: j.get("updated_at", ""), reverse=True)[:limit]
        except Exception:
            return []

    def _safe(self, fn, default):
        try:
            return fn()
        except Exception:
            return default

    def _latest(self, fn):
        try:
            return fn()
        except Exception:
            return None

    def _latest_files(self, folder: Path, pattern: str, limit: int):
        out = []
        try:
            for path in sorted(folder.glob(pattern), reverse=True)[:limit]:
                try:
                    data = json.loads(path.read_text(encoding="utf-8"))
                    if isinstance(data, dict):
                        data["_file"] = str(path)
                        out.append(data)
                except Exception:
                    continue
        except Exception:
            return []
        return out

    def _esc(self, value):
        return html.escape(str(value if value is not None else ""))

    def _card(self, title, body, wide=False):
        return '<section class="' + ("card wide" if wide else "card") + '"><h2>' + self._esc(title) + '</h2>' + body + '</section>'

    def _metrics(self, metrics):
        return '<div class="mini-grid">' + ''.join(['<div class="mini"><div class="mini-value">' + self._esc(v) + '</div><div class="mini-label">' + self._esc(k) + '</div></div>' for k, v in metrics.items()]) + '</div>'

    def _kv(self, mapping):
        return '<div class="kv">' + ''.join(['<b>' + self._esc(k) + '</b><span>' + self._esc(v) + '</span>' for k, v in mapping.items()]) + '</div>'

    def _table(self, items, columns):
        if not items:
            return '<p class="muted">No data</p>'
        head = ''.join(['<th>' + self._esc(c) + '</th>' for c in columns])
        body = []
        for item in items:
            body.append('<tr>' + ''.join(['<td>' + self._esc(item.get(c, "")) + '</td>' for c in columns]) + '</tr>')
        return '<table><thead><tr>' + head + '</tr></thead><tbody>' + ''.join(body) + '</tbody></table>'

    def _messages(self, conversation):
        messages = (conversation or {}).get("messages") or []
        if not messages:
            return '<p class="muted">No conversation yet</p>'
        return ''.join(['<div class="message"><b>' + self._esc(m.get("agent")) + '</b> <span>' + self._esc(m.get("role")) + '</span><p>' + self._esc(m.get("message")) + '</p></div>' for m in messages[:10]])

    def _render(self, snap: Dict[str, Any]) -> str:
        version = snap.get("version") or {}
        runtime = snap.get("latest_runtime") or {}
        latest_ai = snap.get("latest_ai") or {}
        conversation = snap.get("latest_conversation") or {}
        agent_session = snap.get("latest_agent_session") or {}
        cards = [
            self._card("Live Metrics", self._metrics(snap.get("metrics") or {}), True),
            self._card("OS", self._kv({"version": version.get("version", ""), "sprint": version.get("sprint", ""), "status": version.get("status", "")})),
            self._card("Latest Runtime", self._kv({"run": runtime.get("run_id", ""), "worker": runtime.get("worker_id", ""), "mode": runtime.get("mode", "")})),
            self._card("Providers", self._table(snap.get("providers") or [], ["provider_id", "name", "status", "mode"])),
            self._card("Real AI Providers", self._table(snap.get("real_ai_providers") or [], ["provider_id", "name", "status", "mode"])),
            self._card("Latest Real AI", self._kv({"run": latest_ai.get("run_id", ""), "status": latest_ai.get("status", ""), "mode": latest_ai.get("mode", ""), "next": latest_ai.get("next_stage", "")})),
            self._card("Workers", self._table(snap.get("workers") or [], ["worker_id", "name", "status", "capability"])),
            self._card("Latest Conversation", self._kv({"conversation": conversation.get("conversation_id", ""), "plan": conversation.get("plan_id", ""), "request": conversation.get("request", "")})),
            self._card("Latest Agent Session", self._kv({"session": agent_session.get("session_id", ""), "status": agent_session.get("status", ""), "plan": agent_session.get("plan_id", ""), "messages": agent_session.get("message_count", ""), "next": agent_session.get("next_stage", "")})),
            self._card("Session Message Bus", self._table(snap.get("session_messages") or [], ["message_type", "sender", "recipient", "status"]), True),
            self._card("Worker Queue", self._table(snap.get("scheduler_jobs") or [], ["job_id", "priority", "status", "worker_id", "attempts", "title"]), True),
            self._card("Recent Tasks", self._table(snap.get("tasks") or [], ["task_id", "title", "status", "assigned_worker"]), True),
            self._card("Recent Events", self._table(snap.get("events") or [], ["event_type", "created_at", "source"]), True),
            self._card("Conversation Stream", self._messages(conversation), True),
        ]
        css = "body{margin:0;background:#07111f;color:#e5e7eb;font-family:Segoe UI,Arial,sans-serif}header{padding:24px 34px;background:#0f172a;border-bottom:1px solid #334155;position:sticky;top:0}h1{margin:0;font-size:28px}.sub{color:#94a3b8;margin-top:6px}main{padding:24px 34px;display:grid;grid-template-columns:repeat(12,1fr);gap:16px}.card{grid-column:span 6;background:#111827;border:1px solid #334155;border-radius:16px;padding:18px;box-shadow:0 10px 30px rgba(0,0,0,.25)}.wide{grid-column:span 12}h2{margin:0 0 14px;color:#f8fafc}.mini-grid{display:grid;grid-template-columns:repeat(4,1fr);gap:12px}.mini{background:#1f2937;border:1px solid #334155;border-radius:12px;padding:14px}.mini-value{font-size:24px;font-weight:800;color:#38bdf8}.mini-label{color:#94a3b8;font-size:12px;margin-top:6px}.kv{display:grid;grid-template-columns:130px 1fr;gap:8px}.kv b{color:#94a3b8}.kv span{word-break:break-all}table{width:100%;border-collapse:collapse;font-size:13px}th,td{border-bottom:1px solid #334155;padding:8px;text-align:left;vertical-align:top}th{color:#38bdf8}.message{background:#1f2937;border:1px solid #334155;border-radius:12px;padding:12px;margin-bottom:10px}.message b{color:#38bdf8}.message span{color:#94a3b8}.message p{margin:8px 0 0}.muted{color:#94a3b8}"
        refresh = str(int(snap.get("refresh_seconds") or 10))
        return '<!doctype html><html lang="ko"><head><meta charset="utf-8"><meta http-equiv="refresh" content="' + refresh + '"><title>AI Factory Live Dashboard</title><style>' + css + '</style></head><body><header><h1>AI Factory Live Dashboard</h1><div class="sub">Auto refresh ' + refresh + 's · ' + self._esc(snap.get("created_at")) + '</div></header><main>' + ''.join(cards) + '</main></body></html>'
