from __future__ import annotations
import json
from pathlib import Path
from approval_guardian.audit import redact_command

class ArtifactStore:
    def __init__(self, root, session_id): self.root=Path(root)/"data"/"runtime_sessions"/session_id; self.root.mkdir(parents=True,exist_ok=True)
    def json(self,name,data):
        p=self.root/name; t=p.with_suffix(p.suffix+".tmp"); t.write_text(json.dumps(data,ensure_ascii=False,indent=2),encoding="utf-8"); t.replace(p); return p
    def text(self,name,text):
        p=self.root/name; t=p.with_suffix(p.suffix+".tmp"); t.write_text(redact_command(text),encoding="utf-8"); t.replace(p); return p
    def append(self,name,data):
        p=self.root/name
        with p.open("a",encoding="utf-8") as f: f.write(json.dumps(data,ensure_ascii=False)+"\n")
        return p
