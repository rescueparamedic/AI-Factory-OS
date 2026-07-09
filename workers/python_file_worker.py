from __future__ import annotations

from typing import Dict, Any
from workers.base_worker import BaseWorker


class PythonFileWorker(BaseWorker):
    worker_id = "python_file_worker"
    worker_type = "code_worker"
    team = "development_team"
    role = "Python 파일 생성 및 수정"
    permission_level = 2
    requires_approval = False
    log_required = True

    def execute(self, payload: Dict[str, Any]) -> Dict[str, Any]:
        filename = payload.get("filename")
        content = payload.get("content", "")
        if not filename:
            raise ValueError("filename is required")

        path = self.base_path / filename
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(content, encoding="utf-8")
        return {
            "created_file": str(path),
            "bytes_written": len(content.encode("utf-8")),
        }
