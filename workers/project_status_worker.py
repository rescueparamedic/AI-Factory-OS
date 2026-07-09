from __future__ import annotations

from datetime import datetime
from typing import Dict, Any
from workers.base_worker import BaseWorker


class ProjectStatusWorker(BaseWorker):
    worker_id = "project_status_worker"
    worker_type = "document_worker"
    team = "documentation_team"
    role = "Project Status 문서 생성"
    permission_level = 2
    requires_approval = False
    log_required = True

    def execute(self, payload: Dict[str, Any]) -> Dict[str, Any]:
        path = self.base_path / "PROJECT_STATUS.md"
        completed = "\n".join(f"- {item}" for item in payload.get("completed", []))
        next_items = "\n".join(f"- {item}" for item in payload.get("next", []))
        content = f"""# AI Factory OS Project Status

작성일: {datetime.now().astimezone().isoformat(timespec='seconds')}

## 현재 상태

| 항목 | 내용 |
|---|---|
| 현재 Phase | {payload.get('phase', '')} |
| 현재 Step | {payload.get('step', '')} |
| 상태 | {payload.get('status', '')} |

## 완료된 작업

{completed}

## 다음 작업

{next_items}
"""
        path.write_text(content, encoding="utf-8")
        return {
            "created_file": str(path),
            "phase": payload.get("phase", ""),
            "step": payload.get("step", ""),
        }
