from __future__ import annotations

from datetime import datetime
from typing import Dict, Any
from workers.base_worker import BaseWorker


class CheckpointWorker(BaseWorker):
    worker_id = "checkpoint_worker"
    worker_type = "document_worker"
    team = "documentation_team"
    role = "Checkpoint 문서 생성"
    permission_level = 2
    requires_approval = False
    log_required = True

    def execute(self, payload: Dict[str, Any]) -> Dict[str, Any]:
        checkpoint_id = payload.get("checkpoint_id", datetime.now().strftime("CP-%Y%m%d-%H%M%S"))
        path = self.base_path / "docs" / "operations" / f"{checkpoint_id}.md"
        path.parent.mkdir(parents=True, exist_ok=True)

        content = f"""# {checkpoint_id}

## Summary

{payload.get('summary', 'Checkpoint generated.')}

## Items

"""
        for item in payload.get("items", []):
            content += f"- {item}\n"

        path.write_text(content, encoding="utf-8")
        return {
            "checkpoint_id": checkpoint_id,
            "created_file": str(path),
        }
