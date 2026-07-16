from __future__ import annotations

from copy import deepcopy
from dataclasses import dataclass
import math
import os
import sys
import time
from typing import Any, Callable, Mapping, Protocol, TextIO


class SnapshotProvider(Protocol):
    def snapshot(self, session_id: str) -> dict[str, Any]:
        ...


class LiveRenderer(Protocol):
    def render(
        self, snapshot: Mapping[str, Any], refresh_count: int,
        refresh_interval: float, error: str | None = None,
    ) -> None:
        ...


@dataclass(frozen=True)
class LiveRefreshResult:
    refreshes: int
    interrupted: bool
    last_snapshot: dict[str, Any] | None
    last_error: str | None
    duration_seconds: float


class LiveDashboardController:
    '''Reusable read-only polling controller for dashboard snapshots.'''

    def __init__(
        self, provider: SnapshotProvider, renderer: LiveRenderer,
        refresh_interval: float = 1.0, max_refreshes: int | None = None,
        max_duration: float | None = None,
        sleeper: Callable[[float], None] = time.sleep,
        clock: Callable[[], float] = time.monotonic,
    ):
        self.provider = provider
        self.renderer = renderer
        self.refresh_interval = validate_refresh_interval(refresh_interval)
        self.max_refreshes = _positive_int(max_refreshes, 'max refreshes')
        self.max_duration = (
            _positive_float(max_duration, 'maximum duration')
            if max_duration is not None else None
        )
        self.sleeper = sleeper
        self.clock = clock

    def run(self, session_id: str) -> LiveRefreshResult:
        started = self.clock()
        refreshes = 0
        interrupted = False
        previous = None
        last_error = None
        try:
            while True:
                try:
                    current = self.provider.snapshot(session_id)
                    previous = deepcopy(current)
                    last_error = None
                except Exception as exc:
                    last_error = 'Refresh failed ({})'.format(type(exc).__name__)
                    current = deepcopy(previous) if previous else _empty_snapshot(session_id)
                self.renderer.render(
                    current, refreshes + 1, self.refresh_interval, last_error,
                )
                refreshes += 1
                if self.max_refreshes and refreshes >= self.max_refreshes:
                    break
                elapsed = self.clock() - started
                if self.max_duration is not None and elapsed >= self.max_duration:
                    break
                delay = self.refresh_interval
                if self.max_duration is not None:
                    delay = min(delay, self.max_duration - elapsed)
                if delay <= 0:
                    break
                self.sleeper(delay)
        except KeyboardInterrupt:
            interrupted = True
        return LiveRefreshResult(
            refreshes=refreshes,
            interrupted=interrupted,
            last_snapshot=deepcopy(previous),
            last_error=last_error,
            duration_seconds=max(0.0, self.clock() - started),
        )


class TerminalLiveDashboardRenderer:
    '''Presentation-only terminal renderer for reusable dashboard snapshots.'''

    CLEAR = '\x1b[2J\x1b[H'

    def __init__(
        self, stream: TextIO | None = None, no_clear: bool = False,
        timeline_limit: int = 5, clear_supported: bool | None = None,
    ):
        self.stream = stream or sys.stdout
        self.no_clear = no_clear
        self.timeline_limit = max(1, int(timeline_limit))
        self.clear_supported = clear_supported
        self._seen_timeline: set[tuple[str, ...]] = set()

    def render(
        self, snapshot: Mapping[str, Any], refresh_count: int,
        refresh_interval: float, error: str | None = None,
    ) -> None:
        clear = self._can_clear()
        if clear:
            self.stream.write(self.CLEAR)
        elif refresh_count > 1:
            self.stream.write('\n' + '-' * 72 + '\n')
        status = snapshot.get('runtime_status', 'Unavailable')
        self.stream.write('AI Factory OS - Live Runtime Dashboard\n')
        self.stream.write(
            'Session: {} | Status: {}\n'.format(
                snapshot.get('session_id', 'unavailable'), status,
            )
        )
        self.stream.write(
            'Stage: {} | Task: {} | Worker: {}\n'.format(
                snapshot.get('current_stage', 'unavailable'),
                snapshot.get('current_task', 'unavailable'),
                snapshot.get('current_worker', 'unavailable'),
            )
        )
        progress = snapshot.get('progress', {})
        value = progress.get('value') if isinstance(progress, Mapping) else None
        source = progress.get('source', 'unavailable') if isinstance(progress, Mapping) else 'unavailable'
        display = '{}%'.format(value) if value is not None else 'unavailable'
        self.stream.write('Progress: {} ({})\n'.format(display, source))
        if error:
            self.stream.write('Refresh warning: {}\n'.format(error))
        self._workers(snapshot)
        self._approvals(snapshot)
        self._timeline(snapshot, clear)
        self._evidence(snapshot)
        self._repository(snapshot)
        self.stream.write(
            '\nLast refresh: {} | Interval: {}s | Refresh: {}\n'.format(
                snapshot.get('snapshot_timestamp', 'unavailable'),
                _number(refresh_interval), refresh_count,
            )
        )
        self.stream.write('Press Ctrl+C to exit. Dashboard is read-only.\n')
        self.stream.flush()

    def _workers(self, snapshot: Mapping[str, Any]) -> None:
        self.stream.write('\nLifecycle / Team Status\n')
        workers = snapshot.get('workers', [])
        if not isinstance(workers, list) or not workers:
            self.stream.write('- Worker status unavailable\n')
            return
        for row in workers:
            if not isinstance(row, Mapping):
                continue
            value = row.get('progress')
            progress = '{}%'.format(value) if value is not None else 'unavailable'
            self.stream.write(
                '- {worker}: {status} | task={current_task} | progress={progress}\n'.format(
                    worker=row.get('worker', 'Unknown'),
                    status=row.get('status', 'Unavailable'),
                    current_task=row.get('current_task', '-'),
                    progress=progress,
                )
            )

    def _approvals(self, snapshot: Mapping[str, Any]) -> None:
        queue = snapshot.get('approval_queue', [])
        queue = queue if isinstance(queue, list) else []
        self.stream.write('\nApproval Queue: {} pending\n'.format(len(queue)))
        for item in queue[:3]:
            if isinstance(item, Mapping):
                self.stream.write(
                    '- {} | {} | {} | {}\n'.format(
                        item.get('approval_id', 'unavailable'),
                        item.get('action', 'unavailable'),
                        item.get('status', 'unavailable'),
                        item.get('next_action', 'unavailable'),
                    )
                )

    def _timeline(self, snapshot: Mapping[str, Any], clear: bool) -> None:
        rows = snapshot.get('timeline', [])
        rows = rows if isinstance(rows, list) else []
        valid = [item for item in rows if isinstance(item, Mapping)]
        if clear:
            visible = valid[-self.timeline_limit:]
        else:
            visible = []
            for item in valid:
                key = _event_key(item)
                if key not in self._seen_timeline:
                    visible.append(item)
            visible = visible[-self.timeline_limit:]
        self._seen_timeline.update(_event_key(item) for item in valid)
        label = 'Latest Timeline' if clear or not self._seen_timeline else 'New Timeline Events'
        self.stream.write('\n{}\n'.format(label))
        if not visible:
            self.stream.write('- No new execution events\n')
        for item in visible:
            self.stream.write(
                '- {} | {} | {}\n'.format(
                    item.get('timestamp', ''),
                    item.get('event', ''),
                    item.get('detail', ''),
                )
            )

    def _evidence(self, snapshot: Mapping[str, Any]) -> None:
        rows = snapshot.get('evidence', [])
        rows = rows if isinstance(rows, list) else []
        self.stream.write('\nEvidence: {} available\n'.format(len(rows)))
        for item in rows[-3:]:
            if isinstance(item, Mapping):
                self.stream.write(
                    '- {}: {}\n'.format(
                        item.get('type', 'artifact'),
                        item.get('path', 'unavailable'),
                    )
                )

    def _repository(self, snapshot: Mapping[str, Any]) -> None:
        repo = snapshot.get('repository', {})
        repo = repo if isinstance(repo, Mapping) else {}
        self.stream.write('\nRepository Status\n')
        self.stream.write(
            '- Branch: {} | Tree: {}\n'.format(
                repo.get('current_branch', 'unavailable'),
                repo.get('working_tree', 'unavailable'),
            )
        )
        self.stream.write(
            '- Latest commit: {}\n'.format(
                repo.get('latest_commit', 'unavailable'),
            )
        )

    def _can_clear(self) -> bool:
        if self.no_clear:
            return False
        if self.clear_supported is not None:
            return self.clear_supported
        try:
            tty = self.stream.isatty()
        except (AttributeError, OSError):
            return False
        windows_ansi = any(
            os.environ.get(name)
            for name in ('WT_SESSION', 'ANSICON', 'TERM_PROGRAM')
        )
        return bool(tty and (os.name != 'nt' or windows_ansi))


def _event_key(item: Mapping[str, Any]) -> tuple[str, ...]:
    return tuple(
        str(item.get(name, ''))
        for name in ('timestamp', 'event', 'worker', 'detail')
    )


def _empty_snapshot(session_id: str) -> dict[str, Any]:
    return {
        'session_id': session_id,
        'runtime_status': 'Unavailable',
        'current_stage': 'unavailable',
        'current_task': 'unavailable',
        'current_worker': 'unavailable',
        'progress': {'value': None, 'source': 'unavailable'},
        'workers': [],
        'approval_queue': [],
        'timeline': [],
        'evidence': [],
        'repository': {},
        'snapshot_timestamp': 'unavailable',
    }


def _positive_float(value: Any, label: str) -> float:
    try:
        number = float(value)
    except (TypeError, ValueError) as exc:
        raise ValueError('{} must be a positive number'.format(label)) from exc
    if number <= 0 or not math.isfinite(number):
        raise ValueError('{} must be a positive number'.format(label))
    return number


def validate_refresh_interval(value: Any) -> float:
    '''Shared positive finite polling interval validation.'''
    return _positive_float(value, 'refresh interval')


def _positive_int(value: Any, label: str) -> int | None:
    if value is None:
        return None
    if isinstance(value, bool):
        raise ValueError('{} must be a positive integer'.format(label))
    try:
        number = int(value)
    except (OverflowError, TypeError, ValueError) as exc:
        raise ValueError('{} must be a positive integer'.format(label)) from exc
    if number <= 0 or str(value).strip() not in {str(number), '{}.0'.format(number)}:
        raise ValueError('{} must be a positive integer'.format(label))
    return number


def _number(value: float) -> str:
    return str(int(value)) if float(value).is_integer() else str(value)
