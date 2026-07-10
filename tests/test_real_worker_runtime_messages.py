from real_worker_runtime.message_bus import MessageBus
from real_worker_runtime.models import RuntimeSession
from real_worker_runtime.artifact_store import ArtifactStore
def session(): return RuntimeSession("s","sp","r","mock","running","a","a",{})
def test_publish(tmp_path):
 s=session(); m=MessageBus(ArtifactStore(tmp_path,"s"),s).publish("a","b","TASK","hello"); assert m.summary=="hello" and len(s.messages)==1
def test_jsonl(tmp_path):
 s=session(); store=ArtifactStore(tmp_path,"s"); MessageBus(store,s).publish("a","b","TASK","hello"); assert (store.root/"messages.jsonl").exists()
