from __future__ import annotations

import json
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
        pipelines = [
            pipeline for item in values
            if (pipeline := RuntimePipeline.from_value(item)) is not None
        ]
        pipeline = pipelines[-1] if pipelines else None
        return {
            'session_id': session_id,
            'runtime_status': _runtime_status(session, pipeline),
            'workers': _workers(session, pipeline),
            'approval_queue': _approvals(session),
            'timeline': _timeline(directory, pipeline),
            'evidence': _evidence(session, directory),
            'repository': self.repository_status(),
        }

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
        lines += [
            '- {worker}: {status} | task={current_task} | progress={progress}%'.format(**row)
            for row in data['workers']
        ]
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
    if status in {'failed', 'blocked', 'cancelled'}:
        return 'Failed'
    if status in {'waiting', 'waiting_approval'}:
        return 'Waiting'
    if status == 'completed' or pipeline and pipeline.state is PipelineState.DONE:
        return 'Completed'
    if pipeline and pipeline.state is PipelineState.APPROVAL_PENDING:
        return 'Waiting'
    return 'Running'


def _workers(session: Mapping[str, Any], pipeline: RuntimePipeline | None) -> list[dict[str, Any]]:
    stage = STAGES.get(pipeline.state, 0) if pipeline else 0
    session_status = str(session.get('status', '')).lower()
    failed = session_status in {
        'failed', 'blocked', 'cancelled',
    }
    try:
        active_progress = max(0, min(99, int(session.get('progress', 0))))
    except (TypeError, ValueError):
        active_progress = 0
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
        source = [
            json.loads(line)
            for line in path.read_text(encoding='utf-8').splitlines()
            if line
        ]
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
    return sorted(rows, key=lambda item: item['timestamp'])


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
