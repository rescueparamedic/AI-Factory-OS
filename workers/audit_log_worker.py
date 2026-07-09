from __future__ import annotations

from datetime import datetime
from typing import Dict, Any
from workers.base_worker import BaseWorker
import json


class AuditLogWorker(BaseWorker):
    worker_id = "audit_log_worker"
    worker_type = "audit_worker"
    team = "documentation_team"
    role = "Audit Log 기록"
    permission_level = 1
    requires_approval = False
    log_required = True

    def execute(self, payload: Dict[str, Any]) -> Dict[str, Any]:
        audit_dir = self.base_path / "data" / "audit"
        audit_dir.mkdir(parents=True, exist_ok=True)

        now = datetime.now().astimezone()
        audit = {
            "audit_id": f"AUD-{now.strftime('%Y%m%d-%H%M%S-%f')}",
            "timestamp": now.isoformat(timespec="seconds"),
            "actor": payload.get("actor", "unknown"),
            "action": payload.get("action", "UNKNOWN_ACTION"),
            "target": payload.get("target", ""),
            "reason": payload.get("reason", ""),
            "result": payload.get("result", "unknown"),
            "metadata": payload.get("metadata", {}),
        }
        path = audit_dir / f"{audit['audit_id']}.json"
        path.write_text(json.dumps(audit, ensure_ascii=False, indent=2), encoding="utf-8")
        return {
            "audit_id": audit["audit_id"],
            "created_file": str(path),
        }
