from __future__ import annotations

import csv
from copy import deepcopy
from datetime import datetime, timezone
from hashlib import sha256
from io import StringIO
import json
from pathlib import Path
import re
from typing import Any, Iterable, Mapping

from .models import RuntimeEvent


SESSION_ID_PATTERN = re.compile(r'^[A-Za-z0-9][A-Za-z0-9_-]{0,127}$')
MAX_HISTORY_LIMIT = 10_000


class RuntimeHistoryInvalid(ValueError):
    pass


class RuntimeHistoryStore:
    '''Append-only history over each existing runtime session events.jsonl.'''

    def __init__(self, root: str | Path = '.'):
        self.root = Path(root).resolve()

    def append(self, event: RuntimeEvent | Mapping[str, Any]) -> dict[str, Any]:
        value = event.to_dict() if isinstance(event, RuntimeEvent) else dict(event)
        session_id = _session_id(value.get('session_id'))
        required = (
            'event_id', 'timestamp', 'event_type', 'actor', 'status',
        )
        missing = [name for name in required if not str(value.get(name) or '').strip()]
        if missing:
            raise RuntimeHistoryInvalid(
                'missing required event fields: ' + ', '.join(missing),
            )
        if _parse_time(value.get('timestamp')) is None:
            raise RuntimeHistoryInvalid(
                'timestamp must be a timezone-aware ISO timestamp',
            )
        normalized = _normalize(value, session_id, 0, legacy=False)
        directory = self.root / 'data' / 'runtime_sessions' / session_id
        directory.mkdir(parents=True, exist_ok=True)
        with (directory / 'events.jsonl').open('a', encoding='utf-8') as stream:
            stream.write(json.dumps(normalized, ensure_ascii=False) + '\n')
        return deepcopy(normalized)

    def events(
        self, session_id: str, *,
        event_type: str | Iterable[str] | None = None,
        actor: str | None = None,
        status: str | None = None,
        worker_id: str | None = None,
        since: str | None = None,
        until: str | None = None,
        limit: int | None = None,
    ) -> list[dict[str, Any]]:
        session_id = _session_id(session_id)
        start = _filter_time(since, 'since')
        end = _filter_time(until, 'until')
        if start and end and start > end:
            raise RuntimeHistoryInvalid('since must not be after until')
        if limit is not None and (
            isinstance(limit, bool) or not isinstance(limit, int)
            or not 1 <= limit <= MAX_HISTORY_LIMIT
        ):
            raise RuntimeHistoryInvalid(
                f'limit must be between 1 and {MAX_HISTORY_LIMIT}',
            )
        directory = self.root / 'data' / 'runtime_sessions' / session_id
        path = directory / 'events.jsonl'
        if not path.is_file():
            if not (directory / 'session.json').is_file():
                raise FileNotFoundError(session_id)
            return []
        requested_types = _event_types(event_type)
        rows = []
        for index, line in enumerate(path.read_text(encoding='utf-8').splitlines()):
            try:
                value = json.loads(line)
            except json.JSONDecodeError:
                continue
            if not isinstance(value, Mapping):
                continue
            row = _normalize(value, session_id, index, legacy=True)
            timestamp = _parse_time(row['timestamp'])
            if requested_types and row['event_type'] not in requested_types:
                continue
            if actor and row['actor'] != actor:
                continue
            if status and row['status'] != status:
                continue
            if worker_id and row.get('worker_id') != worker_id:
                continue
            if start and (timestamp is None or timestamp < start):
                continue
            if end and (timestamp is None or timestamp > end):
                continue
            rows.append((timestamp, index, row))
        maximum = datetime.max.replace(tzinfo=timezone.utc)
        rows.sort(key=lambda item: (item[0] is None, item[0] or maximum, item[1]))
        result = [item[2] for item in rows]
        if limit is not None:
            result = result[:limit]
        return deepcopy(result)

    def summary(self, session_id: str, **filters: Any) -> dict[str, Any]:
        rows = self.events(session_id, **filters)
        errors = [row for row in rows if row['event_type'] == 'ERROR_OCCURRED']
        return {
            'session_id': _session_id(session_id),
            'event_count': len(rows),
            'error_event_count': len(errors),
            'first_event_at': rows[0]['timestamp'] if rows else 'unavailable',
            'last_event_at': rows[-1]['timestamp'] if rows else 'unavailable',
            'events': rows,
            'read_only': True,
        }


def canonical_event_type(value: Any) -> str:
    name = re.sub(r'[^A-Za-z0-9]+', '_', str(value or '')).strip('_').upper()
    if name == 'RUNTIME_CREATED':
        return 'SESSION_STARTED'
    if name == 'RUNTIME_COMPLETED':
        return 'SESSION_COMPLETED'
    if name == 'RUNTIME_CANCELLED':
        return 'SESSION_CANCELLED'
    if name in {'APPROVAL_PENDING', 'RUNTIME_WAITING_APPROVAL'}:
        return 'APPROVAL_REQUESTED'
    if name in {'APPROVAL_GRANTED', 'APPROVAL_CONSUMED', 'APPROVAL_REJECTED'}:
        return 'APPROVAL_COMPLETED'
    if name in {'QA_COMPLETED', 'QA_ACCEPTED'}:
        return 'QA_COMPLETED'
    if any(token in name for token in ('FAILED', 'ERROR', 'EXCEPTION')):
        return 'ERROR_OCCURRED'
    return name or 'RUNTIME_EVENT'


def canonical_event_status(event: Any, state: Any = '') -> str:
    name = str(event or '').upper()
    if 'CANCEL' in name:
        return 'cancelled'
    if 'REJECT' in name:
        return 'rejected'
    if any(token in name for token in ('FAILED', 'ERROR', 'EXCEPTION')):
        return 'failed'
    if any(token in name for token in ('PENDING', 'WAITING')):
        return 'waiting'
    if any(token in name for token in ('COMPLETED', 'ACCEPTED', 'CONSUMED', 'GRANTED')):
        return 'completed'
    if any(token in name for token in ('STARTED', 'CREATED', 'RESUMED')):
        return 'running'
    return str(state or 'recorded').lower()


def history_csv(summary: Mapping[str, Any]) -> str:
    output = StringIO(newline='')
    fields = [
        'event_id', 'session_id', 'timestamp', 'event_type', 'actor',
        'status', 'worker_id', 'event', 'detail', 'task_id', 'state',
        'metadata',
    ]
    writer = csv.DictWriter(output, fieldnames=fields, extrasaction='ignore')
    writer.writeheader()
    for row in summary.get('events', []):
        if not isinstance(row, Mapping):
            continue
        value = dict(row)
        value['metadata'] = json.dumps(
            value.get('metadata', {}), ensure_ascii=False, sort_keys=True,
        )
        writer.writerow({key: _csv_safe(item) for key, item in value.items()})
    return output.getvalue()


def _normalize(
    value: Mapping[str, Any], session_id: str, index: int, legacy: bool,
) -> dict[str, Any]:
    event = str(value.get('event') or value.get('event_type') or 'RUNTIME_EVENT')
    timestamp = str(value.get('timestamp') or 'unavailable')
    worker_id = str(value.get('worker_id') or '')
    payload = value.get('payload') if isinstance(value.get('payload'), Mapping) else {}
    metadata = value.get('metadata') if isinstance(value.get('metadata'), Mapping) else payload
    event_id = str(value.get('event_id') or '')
    if not event_id:
        identity = json.dumps(
            dict(value), ensure_ascii=False, sort_keys=True, default=str,
        )
        digest = sha256(
            f'{session_id}:{index}:{identity}'.encode('utf-8'),
        ).hexdigest()[:24]
        event_id = 'EVT-LEGACY-' + digest
    return {
        'event_id': event_id,
        'session_id': session_id,
        'timestamp': timestamp,
        'event_type': str(value.get('event_type') or canonical_event_type(event)),
        'actor': str(value.get('actor') or worker_id or 'runtime'),
        'status': str(
            value.get('status')
            or canonical_event_status(event, value.get('state'))
        ),
        'worker_id': worker_id or None,
        'metadata': deepcopy(dict(metadata)),
        'event': event,
        'detail': str(value.get('detail') or ''),
        'task_id': str(value.get('task_id') or ''),
        'state': str(value.get('state') or ''),
        'payload': deepcopy(dict(payload)),
        'legacy_normalized': legacy and not bool(value.get('event_id')),
    }


def _session_id(value: Any) -> str:
    if not isinstance(value, str) or not SESSION_ID_PATTERN.fullmatch(value):
        raise RuntimeHistoryInvalid('invalid session ID')
    return value


def _event_types(value: str | Iterable[str] | None) -> set[str]:
    if value is None:
        return set()
    values = [value] if isinstance(value, str) else list(value)
    return {canonical_event_type(item) for item in values}


def _filter_time(value: str | None, label: str) -> datetime | None:
    if value is None:
        return None
    parsed = _parse_time(value)
    if parsed is None:
        raise RuntimeHistoryInvalid(
            f'{label} must be a timezone-aware ISO timestamp',
        )
    return parsed


def _parse_time(value: Any) -> datetime | None:
    if not isinstance(value, str):
        return None
    try:
        parsed = datetime.fromisoformat(value.replace('Z', '+00:00'))
    except ValueError:
        return None
    if parsed.tzinfo is None:
        return None
    return parsed.astimezone(timezone.utc)


def _csv_safe(value: Any) -> Any:
    if isinstance(value, str) and value.startswith(('=', '+', '-', '@')):
        return chr(39) + value
    return value
