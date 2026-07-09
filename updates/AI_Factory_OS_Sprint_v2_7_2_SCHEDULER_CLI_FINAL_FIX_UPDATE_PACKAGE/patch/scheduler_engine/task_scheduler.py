from __future__ import annotations

from datetime import datetime
from pathlib import Path
from typing import Any, Dict, List, Optional
import json

PRIORITY_WEIGHT = {"critical": 0, "high": 1, "medium": 2, "low": 3}
QUEUE_STATUSES = {"queued", "running", "completed", "failed", "retrying", "blocked"}

class TaskScheduler:
    """AI Factory OS Sprint v2.7 Task Scheduler & Worker Queue.

    Phase-appropriate implementation: JSON based, single-process, additive.
    It does not delete existing tasks and only executes registered local workers.
    """
    def __init__(self, base_path: Path, worker_manager, event_bus=None):
        self.base_path = Path(base_path)
        self.worker_manager = worker_manager
        self.event_bus = event_bus
        self.queue_dir = self.base_path / "data" / "scheduler"
        self.queue_dir.mkdir(parents=True, exist_ok=True)
        self.queue_file = self.queue_dir / "worker_queue.json"
        self.runs_dir = self.queue_dir / "runs"
        self.runs_dir.mkdir(parents=True, exist_ok=True)
        if not self.queue_file.exists():
            self._save_queue([])

    def enqueue(self, title: str, worker_id: str, payload: Optional[Dict[str, Any]] = None,
                priority: str = "medium", product_id: str = "blog_growth_analyzer",
                max_retries: int = 2) -> Dict[str, Any]:
        priority = self._normalize_priority(priority)
        now = self._now()
        queue = self._load_queue()
        job_id = self._make_id("JOB")
        job = {
            "job_id": job_id,
            "title": title,
            "product_id": product_id,
            "worker_id": worker_id,
            "payload": payload or {},
            "priority": priority,
            "priority_weight": PRIORITY_WEIGHT[priority],
            "status": "queued",
            "attempts": 0,
            "max_retries": int(max_retries),
            "created_at": now,
            "updated_at": now,
            "started_at": "",
            "finished_at": "",
            "last_error": "",
            "result_path": "",
            "history": [{"status": "queued", "timestamp": now, "note": "Job queued"}],
        }
        queue.append(job)
        self._save_queue(queue)
        self._publish("SCHEDULER_JOB_QUEUED", {"job_id": job_id, "worker_id": worker_id, "priority": priority})
        return job

    def list_jobs(self, status: str = "all", limit: int = 20) -> List[Dict[str, Any]]:
        jobs = self._load_queue()
        if status != "all":
            jobs = [j for j in jobs if j.get("status") == status]
        jobs = sorted(jobs, key=lambda j: (PRIORITY_WEIGHT.get(j.get("priority", "medium"), 2), j.get("created_at", "")))
        return jobs[:int(limit)]

    def latest(self) -> Optional[Dict[str, Any]]:
        jobs = self._load_queue()
        if not jobs:
            return None
        return sorted(jobs, key=lambda j: j.get("updated_at", ""), reverse=True)[0]

    def status(self) -> Dict[str, Any]:
        jobs = self._load_queue()
        counts = {s: 0 for s in sorted(QUEUE_STATUSES)}
        for job in jobs:
            counts[job.get("status", "queued")] = counts.get(job.get("status", "queued"), 0) + 1
        return {
            "status": "available",
            "queue_file": str(self.queue_file),
            "total_jobs": len(jobs),
            "counts": counts,
            "latest_job": self.latest(),
            "next_job": self.peek_next(),
        }

    def peek_next(self) -> Optional[Dict[str, Any]]:
        queued = [j for j in self._load_queue() if j.get("status") in {"queued", "retrying"}]
        if not queued:
            return None
        return sorted(queued, key=lambda j: (PRIORITY_WEIGHT.get(j.get("priority", "medium"), 2), j.get("created_at", "")))[0]

    def run_next(self) -> Dict[str, Any]:
        next_job = self.peek_next()
        if not next_job:
            return {"status": "empty", "message": "No queued scheduler jobs"}
        return self.run_job(next_job["job_id"])

    def run_all(self, limit: int = 10) -> Dict[str, Any]:
        results = []
        for _ in range(int(limit)):
            nxt = self.peek_next()
            if not nxt:
                break
            results.append(self.run_job(nxt["job_id"]))
        return {"status": "completed", "run_count": len(results), "results": results, "queue": self.status()}

    def run_job(self, job_id: str) -> Dict[str, Any]:
        queue = self._load_queue()
        idx = next((i for i, j in enumerate(queue) if j.get("job_id") == job_id), None)
        if idx is None:
            raise FileNotFoundError(f"Scheduler job not found: {job_id}")
        job = queue[idx]
        if job.get("status") not in {"queued", "retrying", "failed"}:
            return {"status": "skipped", "reason": f"Job status is {job.get('status')}", "job": job}

        now = self._now()
        job["status"] = "running"
        job["attempts"] = int(job.get("attempts", 0)) + 1
        job["started_at"] = job.get("started_at") or now
        job["updated_at"] = now
        job.setdefault("history", []).append({"status": "running", "timestamp": now, "note": f"Attempt {job['attempts']} started"})
        queue[idx] = job
        self._save_queue(queue)
        self._publish("SCHEDULER_JOB_STARTED", {"job_id": job_id, "worker_id": job.get("worker_id"), "attempts": job.get("attempts")})

        try:
            result = self.worker_manager.run(job["worker_id"], job.get("payload") or {})
            finished = self._now()
            job["finished_at"] = finished
            job["updated_at"] = finished
            job["result_path"] = result.get("saved_path", "")
            if result.get("status") == "completed":
                job["status"] = "completed"
                job["last_error"] = ""
                note = "Worker completed"
                event = "SCHEDULER_JOB_COMPLETED"
            else:
                raise RuntimeError(json.dumps(result.get("error") or {"message": "Worker failed"}, ensure_ascii=False))
            job.setdefault("history", []).append({"status": job["status"], "timestamp": finished, "note": note})
            run_record = {"job": job, "worker_result": result}
            run_path = self._save_run_record(job_id, run_record)
            job["run_record_path"] = str(run_path)
            queue[idx] = job
            self._save_queue(queue)
            self._publish(event, {"job_id": job_id, "worker_id": job.get("worker_id"), "result_path": job.get("result_path")})
            return {"status": job["status"], "job": job, "worker_result": result, "run_record_path": str(run_path)}
        except Exception as exc:
            failed = self._now()
            job["finished_at"] = failed
            job["updated_at"] = failed
            job["last_error"] = str(exc)
            if int(job.get("attempts", 0)) <= int(job.get("max_retries", 0)):
                job["status"] = "retrying"
                note = "Worker failed; job queued for retry"
                event = "SCHEDULER_JOB_RETRYING"
            else:
                job["status"] = "failed"
                note = "Worker failed; retry limit exceeded"
                event = "SCHEDULER_JOB_FAILED"
            job.setdefault("history", []).append({"status": job["status"], "timestamp": failed, "note": note, "error": str(exc)})
            run_path = self._save_run_record(job_id, {"job": job, "error": str(exc)})
            job["run_record_path"] = str(run_path)
            queue[idx] = job
            self._save_queue(queue)
            self._publish(event, {"job_id": job_id, "worker_id": job.get("worker_id"), "error": str(exc)})
            return {"status": job["status"], "job": job, "error": str(exc), "run_record_path": str(run_path)}

    def _load_queue(self) -> List[Dict[str, Any]]:
        try:
            data = json.loads(self.queue_file.read_text(encoding="utf-8"))
            return data if isinstance(data, list) else []
        except Exception:
            return []

    def _save_queue(self, queue: List[Dict[str, Any]]) -> None:
        self.queue_file.write_text(json.dumps(queue, ensure_ascii=False, indent=2), encoding="utf-8")

    def _save_run_record(self, job_id: str, record: Dict[str, Any]) -> Path:
        path = self.runs_dir / f"{job_id}_{datetime.now().strftime('%Y%m%d-%H%M%S-%f')}.json"
        path.write_text(json.dumps(record, ensure_ascii=False, indent=2), encoding="utf-8")
        return path

    def _normalize_priority(self, priority: str) -> str:
        p = str(priority or "medium").lower().strip()
        if p not in PRIORITY_WEIGHT:
            raise ValueError("priority must be one of: critical, high, medium, low")
        return p

    def _make_id(self, prefix: str) -> str:
        return f"{prefix}-{datetime.now().strftime('%Y%m%d-%H%M%S-%f')}"

    def _now(self) -> str:
        return datetime.now().astimezone().isoformat(timespec="seconds")

    def _publish(self, event_type: str, payload: Dict[str, Any]) -> None:
        if self.event_bus is not None:
            try:
                self.event_bus.publish(event_type, payload)
            except Exception:
                pass
