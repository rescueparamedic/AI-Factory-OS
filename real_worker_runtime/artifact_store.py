from __future__ import annotations

import json
from pathlib import Path

from approval_guardian.audit import redact_command


class ArtifactStore:
    def __init__(self, root, session_id):
        self.repository_root = Path(root)
        self.session_id = str(session_id)
        self.root = self.repository_root / 'data' / 'runtime_sessions' / self.session_id
        self.root.mkdir(parents=True, exist_ok=True)

    def json(self, name, data):
        path = self.root / name
        temporary = path.with_suffix(path.suffix + '.tmp')
        temporary.write_text(
            json.dumps(data, ensure_ascii=False, indent=2), encoding='utf-8',
        )
        temporary.replace(path)
        return path

    def text(self, name, text):
        path = self.root / name
        temporary = path.with_suffix(path.suffix + '.tmp')
        temporary.write_text(redact_command(text), encoding='utf-8')
        temporary.replace(path)
        return path

    def append(self, name, data):
        path = self.root / name
        with path.open('a', encoding='utf-8') as stream:
            stream.write(json.dumps(data, ensure_ascii=False) + '\n')
        return path
