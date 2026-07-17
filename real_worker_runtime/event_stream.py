from datetime import datetime
from uuid import uuid4

from .models import RuntimeEvent
from .runtime_history import (
    RuntimeHistoryStore, canonical_event_status, canonical_event_type,
)


class EventStream:
    def __init__(self, store):
        self.store = store

    def emit(
        self, event, worker_id='', detail='', task_id='', state='', payload=None,
    ):
        metadata = dict(payload) if isinstance(payload, dict) else {}
        item = RuntimeEvent(
            event=event,
            timestamp=datetime.now().astimezone().isoformat(timespec='seconds'),
            worker_id=worker_id,
            detail=detail,
            task_id=task_id,
            state=state,
            payload=metadata,
            event_id=f'EVT-{uuid4().hex}',
            session_id=self.store.session_id,
            event_type=canonical_event_type(event),
            actor=worker_id or 'runtime',
            status=canonical_event_status(event, state),
            metadata=metadata,
        )
        RuntimeHistoryStore(self.store.repository_root).append(item)
        return item
