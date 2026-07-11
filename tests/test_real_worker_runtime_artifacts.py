import json
from real_worker_runtime.artifact_store import ArtifactStore
def test_json_atomic(tmp_path):
 p=ArtifactStore(tmp_path,"s").json("a.json",{"x":1}); assert json.loads(p.read_text())["x"]==1
def test_text(tmp_path): assert ArtifactStore(tmp_path,"s").text("a.md","hello").read_text()=="hello"
def test_append(tmp_path):
 s=ArtifactStore(tmp_path,"s"); s.append("e.jsonl",{"a":1}); s.append("e.jsonl",{"b":2}); assert len((s.root/"e.jsonl").read_text().splitlines())==2
