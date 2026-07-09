from __future__ import annotations

from typing import Dict, Any, List
from workers.base_worker import BaseWorker


class MarkdownWorker(BaseWorker):
    worker_id = "markdown_worker"
    worker_type = "document_worker"
    team = "documentation_team"
    role = "Markdown 문서 생성"
    permission_level = 2
    requires_approval = False
    log_required = True

    def execute(self, payload: Dict[str, Any]) -> Dict[str, Any]:
        path = self.base_path / payload.get("filename", "docs/operations/generated.md")
        title = payload.get("title", "Generated Document")
        body: List[str] = payload.get("body", [])
        path.parent.mkdir(parents=True, exist_ok=True)
        content = f"# {title}\n\n" + "\n\n".join(str(x) for x in body) + "\n"
        path.write_text(content, encoding="utf-8")
        return {
            "created_file": str(path),
            "title": title,
            "line_count": len(content.splitlines()),
        }
