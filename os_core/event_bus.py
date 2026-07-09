from __future__ import annotations

from dataclasses import dataclass, asdict
from datetime import datetime
from pathlib import Path
import json
from typing import Any, Dict


@dataclass
class Event:
    event_id: str
    timestamp: str
    event_type: str
    payload: Dict[str, Any]


class EventBus:
    def __init__(self, base_path: Path):
        self.base_path = base_path
        self.events_dir = base_path / "data" / "events"
        self.events_dir.mkdir(parents=True, exist_ok=True)

    def publish(self, event_type: str, payload: Dict[str, Any]) -> Event:
        now = datetime.now().astimezone()
        event = Event(
            event_id=f"EVT-{now.strftime('%Y%m%d-%H%M%S-%f')}",
            timestamp=now.isoformat(timespec="seconds"),
            event_type=event_type,
            payload=payload,
        )
        event_file = self.events_dir / f"{event.event_id}.json"
        event_file.write_text(
            json.dumps(asdict(event), ensure_ascii=False, indent=2),
            encoding="utf-8",
        )
        return event
