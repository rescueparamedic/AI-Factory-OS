from __future__ import annotations

import json
from copy import deepcopy
from datetime import datetime
from pathlib import Path
import subprocess
from typing import Any, Mapping

from .runtime_pipeline import PipelineState, RuntimePipeline

WORKERS = ('Development', 'QA', 'Documentation', 'Approval', 'Release')
STAGES = {
    PipelineState.PLANNED: 0, PipelineState.ASSIGNED: 0,
    PipelineState.DEVELOPING: 0, PipelineState.QA_PENDING: 1,
    PipelineState.DOCUMENTING: 2, PipelineState.APPROVAL_PENDING: 3,
    PipelineState.DONE: 4,
}


class RuntimeDashboard:
    '''Read-only projection over persisted RuntimePipeline state.'''

    def __init__(self, root: str | Path = '.'):
        self.root = Path(root).resolve()

    def snapshot(self, session_id: str) -> dict[str, Any]:
        directory = self.root / 'data' / 'runtime_sessions' / session_id
        path = directory / 'session.json'
        session = json.loads(path.read_text(encoding='utf-8'))
        values = session.get('runtime_pipelines', [])
        pipelines = []
        for item in values if isinstance(values, list) else []:
            try:
                pipeline = RuntimePipeline.from_value(item)
            except (KeyError, TypeError, ValueError):
                continue
            if pipeline is not None:
                pipelines.append(pipeline)
        pipeline = pipelines[-1] if pipelines else None
        raw_pipeline = (
            values[-1]
            if isinstance(values, list) and values
            and isinstance(values[-1], Mapping)
            else {}
        )
        progress = _progress(session, pipeline, raw_pipeline)
        workers = _workers(session, pipeline, progress)
        repository = self.repository_status()
        result = {
            'session_id': session_id,
            'runtime_status': _runtime_status(session, pipeline),
            'current_stage': pipeline.state.value if pipeline else 'unavailable',
            'current_task': pipeline.task_id if pipeline else 'unavailable',
            'current_worker': pipeline.current_worker if pipeline else 'unavailable',
            'progress': progress,
            'workers': workers,
            'worker_status': deepcopy(workers),
            'development_status': workers[0]['status'],
            'qa_status': workers[1]['status'],
            'documentation_status': workers[2]['status'],
            'approval_status': workers[3]['status'],
            'release_status': workers[4]['status'],
            'approval_queue': _approvals(session),
            'timeline': _timeline(directory, pipeline),
            'evidence': _evidence(session, directory),
            'repository': repository,
            'repository_branch': repository['current_branch'],
            'repository_working_tree': repository['working_tree'],
            'latest_commit': repository['latest_commit'],
            'snapshot_timestamp': _now(),
        }
        return deepcopy(result)

    def repository_status(self) -> dict[str, str]:
        branch = self._git('branch', '--show-current')
        tree = self._git('status', '--porcelain')
        commit = self._git('log', '-1', '--format=%H %s')
        available = None not in (branch, tree, commit)
        return {
            'current_branch': branch or 'unavailable',
            'working_tree': (
                'dirty' if tree else 'clean'
            ) if available else 'unavailable',
            'latest_commit': commit or 'unavailable',
        }

    def render(self, session_id: str) -> str:
        data = self.snapshot(session_id)
        lines = [
            'AI Factory OS - Runtime Dashboard',
            f'Session: {session_id}',
            'Runtime Status: {}'.format(data['runtime_status']),
            '', 'Worker Status',
        ]
        for row in data['workers']:
            value = row['progress']
            progress = f'{value}%' if value is not None else 'unavailable'
            lines.append(
                '- {worker}: {status} | task={current_task} | progress={progress_display}'.format(
                    progress_display=progress, **row,
                )
            )
        lines += ['', 'Approval Queue']
        lines += [
            '- {approval_id} | {action} | {status} | {next_action}'.format(**row)
            for row in data['approval_queue']
        ] or ['- No pending approvals']
        lines += ['', 'Runtime Timeline']
        lines += [
            '- {timestamp} | {event} | {detail}'.format(**row)
            for row in data['timeline']
        ] or ['- No execution events']
        lines += ['', 'Evidence Viewer']
        lines += [
            '- {type}: {path}'.format(**row) for row in data['evidence']
        ] or ['- No evidence artifacts']
        repo = data['repository']
        lines += [
            '', 'Repository Status',
            '- Current branch: {}'.format(repo['current_branch']),
            '- Working tree: {}'.format(repo['working_tree']),
            '- Latest commit: {}'.format(repo['latest_commit']),
        ]
        return '\n'.join(lines)

    def _git(self, *args: str) -> str | None:
        try:
            result = subprocess.run(
                ['git', *args], cwd=self.root, capture_output=True, text=True,
                encoding='utf-8', errors='replace', check=False,
            )
        except OSError:
            return None
        return result.stdout.strip() if result.returncode == 0 else None


class TerminalDashboard:
    '''Existing in-run view retained for backward compatibility.'''

    def __init__(self, live=True):
        self.live = live

    def render(self, session):
        if not self.live:
            return
        print('\nAI Factory OS - Real Worker Runtime')
        print(
            f'Session: {session.session_id} | Sprint: {session.sprint_id} | '
            f'Status: {session.status.upper()}'
        )
        for worker, state in session.workers.items():
            label = worker.replace('_', ' ').title()
            print(f'[{label:24}] {state.upper()}')
        print(f'Current activity: {session.current_activity}\nProgress: {session.progress}%')


def _runtime_status(session: Mapping[str, Any], pipeline: RuntimePipeline | None) -> str:
    status = str(session.get('status', '')).lower()
    pending = _approvals(session)
    if status in {'failed', 'cancelled'}:
        return 'Failed'
    if status in {'waiting', 'waiting_approval'} or status == 'blocked' and pending:
        return 'Waiting'
    if status == 'blocked':
        return 'Failed'
    if pipeline and pipeline.state is PipelineState.DONE:
        return 'Completed'
    if pipeline and pipeline.state is PipelineState.APPROVAL_PENDING:
        return 'Waiting'
    if pipeline is None and status == 'completed':
        return 'Completed'
    return 'Running'


def _now() -> str:
    return datetime.now().astimezone().isoformat(timespec='seconds')


def _progress(
    session: Mapping[str, Any],
    pipeline: RuntimePipeline | None,
    raw_pipeline: Mapping[str, Any],
) -> dict[str, Any]:
    explicit = _progress_value(raw_pipeline.get('progress'))
    if explicit is not None:
        return {'value': explicit, 'source': 'explicit_pipeline'}
    explicit = _progress_value(session.get('progress')) if 'progress' in session else None
    if explicit is not None:
        return {'value': explicit, 'source': 'explicit_session'}
    if pipeline is None:
        return {'value': None, 'source': 'unavailable'}
    values = {
        PipelineState.PLANNED: 0,
        PipelineState.ASSIGNED: 10,
        PipelineState.DEVELOPING: 25,
        PipelineState.QA_PENDING: 50,
        PipelineState.DOCUMENTING: 75,
        PipelineState.DONE: 100,
    }
    if pipeline.state is PipelineState.APPROVAL_PENDING:
        previous = pipeline.history[-1].get('from') if pipeline.history else None
        derived = 90 if previous == 'documenting' else 35
    else:
        derived = values[pipeline.state]
    return {'value': derived, 'source': 'lifecycle_derived'}


def _progress_value(value: Any) -> int | float | None:
    if isinstance(value, bool) or not isinstance(value, (int, float)):
        return None
    if not 0 <= value <= 100:
        return None
    return int(value) if float(value).is_integer() else float(value)


def _workers(
    session: Mapping[str, Any],
    pipeline: RuntimePipeline | None,
    progress_state: Mapping[str, Any],
) -> list[dict[str, Any]]:
    stage = STAGES.get(pipeline.state, 0) if pipeline else 0
    session_status = str(session.get('status', '')).lower()
    failed = session_status in {
        'failed', 'blocked', 'cancelled',
    }
    active_progress = progress_state.get('value')
    rows = []
    for index, worker in enumerate(WORKERS):
        if (
            index < stage
            or pipeline and pipeline.state is PipelineState.DONE
            or pipeline is None and session_status == 'completed'
        ):
            status, progress = 'Completed', 100
        elif index > stage:
            status, progress = 'Waiting', 0
        elif failed:
            status, progress = 'Failed', active_progress
        elif pipeline and pipeline.state is PipelineState.APPROVAL_PENDING:
            status, progress = 'Waiting', active_progress
        else:
            status, progress = 'Running', active_progress
        rows.append({
            'worker': worker, 'status': status,
            'current_task': pipeline.task_id if pipeline and index == stage else '-',
            'progress': progress,
        })
    return rows


def _approvals(session: Mapping[str, Any]) -> list[dict[str, str]]:
    item = session.get('pending_approval')
    pending = isinstance(item, Mapping) and (
        str(item.get('status', 'PENDING')).upper() == 'PENDING'
    )
    if not pending:
        return []
    return [{
        'approval_id': str(item.get('approval_request_id', '')),
        'action': str(
            item.get('safe_action_summary')
            or item.get('action_type')
            or item.get('target', '')
        ),
        'status': 'PENDING',
        'next_action': str(
            item.get('next_action', 'resume requires exact approval')
        ),
    }]


def _timeline(directory: Path, pipeline: RuntimePipeline | None) -> list[dict[str, str]]:
    path = directory / 'events.jsonl'
    if path.is_file():
        source = []
        for line in path.read_text(encoding='utf-8').splitlines():
            try:
                item = json.loads(line)
            except json.JSONDecodeError:
                continue
            if isinstance(item, Mapping):
                source.append(item)
        rows = [{
            'timestamp': str(item.get('timestamp', '')),
            'event': str(item.get('event', '')),
            'worker': str(item.get('worker_id', '')),
            'detail': str(item.get('detail', '')),
        } for item in source]
    else:
        rows = [{
            'timestamp': str(item.get('timestamp', '')),
            'event': 'PipelineTransition',
            'worker': str(item.get('worker', '')),
            'detail': str(item.get('reason', '')),
        } for item in (pipeline.history if pipeline else [])]
    unique = {}
    for item in rows:
        key = (
            item['timestamp'], item['event'], item['worker'], item['detail'],
        )
        unique.setdefault(key, item)
    return sorted(unique.values(), key=lambda item: item['timestamp'])


def _evidence(session: Mapping[str, Any], directory: Path) -> list[dict[str, str]]:
    rows: list[dict[str, str]] = []
    seen: set[Path] = set()
    for item in session.get('artifacts', []):
        if not isinstance(item, Mapping):
            continue
        raw = Path(str(item.get('path', '')))
        path = (raw if raw.is_absolute() else directory / raw).resolve()
        if path.is_file() and path not in seen:
            rows.append({
                'type': str(item.get('type', item.get('artifact_type', 'artifact'))),
                'path': str(path),
            })
            seen.add(path)
    return rows
