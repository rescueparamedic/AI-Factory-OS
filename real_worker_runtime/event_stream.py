from dataclasses import asdict
from datetime import datetime
from .models import RuntimeEvent
class EventStream:
    def __init__(self,store): self.store=store
    def emit(self,event,worker_id="",detail=""):
        item=RuntimeEvent(event,datetime.now().astimezone().isoformat(timespec="seconds"),worker_id,detail); self.store.append("events.jsonl",asdict(item)); return item
