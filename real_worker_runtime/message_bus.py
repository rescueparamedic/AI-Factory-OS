from dataclasses import asdict
from .models import WorkerMessage
class MessageBus:
    def __init__(self, store, session): self.store=store; self.session=session
    def publish(self,source,target,kind,summary,payload=None):
        msg=WorkerMessage.create(self.session.session_id,source,target,kind,summary,payload); data=asdict(msg); self.session.messages.append(data); self.store.append("messages.jsonl",data); return msg
