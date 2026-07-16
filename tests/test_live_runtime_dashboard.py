import io
import json

import pytest

from afde.cli import main
from real_worker_runtime.dashboard import RuntimeDashboard
from real_worker_runtime.live_dashboard import (
    LiveDashboardController, TerminalLiveDashboardRenderer,
)
from real_worker_runtime.runtime_pipeline import PipelineState, RuntimePipeline


MISSING = object()


def _write_session(
    root, session_id, pipeline=None, status='running',
    progress=MISSING, approval=None, artifacts=None,
):
    directory = root / 'data' / 'runtime_sessions' / session_id
    directory.mkdir(parents=True, exist_ok=True)
    data = {
        'status': status,
        'runtime_pipelines': [pipeline] if pipeline else [],
        'pending_approval': approval,
        'artifacts': artifacts or [],
    }
    if progress is not MISSING:
        data['progress'] = progress
    (directory / 'session.json').write_text(
        json.dumps(data), encoding='utf-8',
    )
    return directory


def _pipeline(task, state, worker='development_worker', progress=MISSING):
    data = RuntimePipeline(
        task, state=state, current_worker=worker,
    ).to_dict()
    if progress is not MISSING:
        data['progress'] = progress
    return data


class SequenceProvider:
    def __init__(self, values):
        self.values = iter(values)
        self.calls = 0

    def snapshot(self, session_id):
        self.calls += 1
        value = next(self.values)
        if isinstance(value, Exception):
            raise value
        return value


class CaptureRenderer:
    def __init__(self):
        self.calls = []

    def render(self, snapshot, refresh_count, refresh_interval, error=None):
        self.calls.append((snapshot, refresh_count, refresh_interval, error))


def test_snapshot_refresh_tracks_pipeline_task_worker_and_status(tmp_path):
    first = _pipeline('TASK-1', PipelineState.DEVELOPING)
    _write_session(tmp_path, 'RWS-live', first, progress=30)
    dashboard = RuntimeDashboard(tmp_path)

    before = dashboard.snapshot('RWS-live')
    second = _pipeline('TASK-2', PipelineState.QA_PENDING, 'qa_worker')
    _write_session(tmp_path, 'RWS-live', second, progress=55)
    after = dashboard.snapshot('RWS-live')

    assert before['current_task'] == 'TASK-1'
    assert before['current_worker'] == 'development_worker'
    assert after['current_task'] == 'TASK-2'
    assert after['current_worker'] == 'qa_worker'
    assert after['current_stage'] == 'qa_pending'
    assert after['workers'][1]['status'] == 'Running'
    assert after['workers'][1]['progress'] == 55


def test_snapshot_refreshes_approval_without_mutation(tmp_path):
    approval = {
        'approval_request_id': 'APR-live',
        'safe_action_summary': 'FILE_WRITE report.md',
        'status': 'PENDING',
        'next_action': 'resume requires exact approval',
    }
    pipeline = _pipeline(
        'TASK-A', PipelineState.APPROVAL_PENDING, 'approval_guardian',
    )
    directory = _write_session(
        tmp_path, 'RWS-approval', pipeline,
        status='waiting_approval', progress=60, approval=approval,
    )
    path = directory / 'session.json'
    before = path.read_bytes()

    result = RuntimeDashboard(tmp_path).snapshot('RWS-approval')

    assert result['runtime_status'] == 'Waiting'
    assert result['approval_queue'][0]['approval_id'] == 'APR-live'
    assert path.read_bytes() == before


def test_timeline_refresh_orders_and_deduplicates_polling_source(tmp_path):
    pipeline = _pipeline('TASK-T', PipelineState.DEVELOPING)
    directory = _write_session(tmp_path, 'RWS-time', pipeline, progress=25)
    event = {'timestamp': '2026-07-16T10:00:00+09:00', 'event': 'START', 'detail': 'one'}
    path = directory / 'events.jsonl'
    path.write_text(
        json.dumps(event) + '\n' + json.dumps(event) + '\n',
        encoding='utf-8',
    )
    dashboard = RuntimeDashboard(tmp_path)

    assert len(dashboard.snapshot('RWS-time')['timeline']) == 1
    later = {'timestamp': '2026-07-16T10:01:00+09:00', 'event': 'NEXT', 'detail': 'two'}
    path.write_text(
        json.dumps(later) + '\n' + json.dumps(event) + '\n',
        encoding='utf-8',
    )
    events = dashboard.snapshot('RWS-time')['timeline']

    assert [item['event'] for item in events] == ['START', 'NEXT']


def test_evidence_refresh_includes_only_new_available_artifacts(tmp_path):
    pipeline = _pipeline('TASK-E', PipelineState.QA_PENDING, 'qa_worker')
    directory = _write_session(tmp_path, 'RWS-evidence', pipeline, progress=50)
    dashboard = RuntimeDashboard(tmp_path)
    assert dashboard.snapshot('RWS-evidence')['evidence'] == []

    artifact = directory / 'qa.json'
    artifact.write_text('{}', encoding='utf-8')
    _write_session(
        tmp_path, 'RWS-evidence', pipeline, progress=50,
        artifacts=[
            {'type': 'qa', 'path': 'qa.json'},
            {'type': 'missing', 'path': 'missing.json'},
        ],
    )

    assert [item['type'] for item in dashboard.snapshot('RWS-evidence')['evidence']] == ['qa']


@pytest.mark.parametrize(
    ('session_status', 'pipeline_state', 'approval', 'expected'),
    [
        ('running', PipelineState.DEVELOPING, None, 'Running'),
        (
            'waiting_approval', PipelineState.APPROVAL_PENDING,
            {'approval_request_id': 'APR-x', 'status': 'PENDING'}, 'Waiting',
        ),
        ('completed', PipelineState.DONE, None, 'Completed'),
        ('failed', PipelineState.QA_PENDING, None, 'Failed'),
    ],
)
def test_runtime_status_transitions(
    tmp_path, session_status, pipeline_state, approval, expected,
):
    pipeline = _pipeline('TASK-S', pipeline_state)
    _write_session(
        tmp_path, 'RWS-status', pipeline,
        status=session_status, approval=approval,
    )

    assert RuntimeDashboard(tmp_path).snapshot('RWS-status')['runtime_status'] == expected


def test_completed_session_does_not_hide_incomplete_pipeline(tmp_path):
    pipeline = _pipeline('TASK-I', PipelineState.DOCUMENTING)
    _write_session(tmp_path, 'RWS-incomplete', pipeline, status='completed')

    result = RuntimeDashboard(tmp_path).snapshot('RWS-incomplete')

    assert result['runtime_status'] == 'Running'


def test_explicit_pipeline_progress_precedes_session_progress(tmp_path):
    pipeline = _pipeline(
        'TASK-P', PipelineState.DEVELOPING, progress=42.5,
    )
    _write_session(tmp_path, 'RWS-progress', pipeline, progress=90)

    progress = RuntimeDashboard(tmp_path).snapshot('RWS-progress')['progress']

    assert progress == {'value': 42.5, 'source': 'explicit_pipeline'}


@pytest.mark.parametrize(
    ('state', 'expected'),
    [
        (PipelineState.PLANNED, 0),
        (PipelineState.ASSIGNED, 10),
        (PipelineState.DEVELOPING, 25),
        (PipelineState.QA_PENDING, 50),
        (PipelineState.DOCUMENTING, 75),
        (PipelineState.DONE, 100),
    ],
)
def test_lifecycle_progress_is_deterministic(tmp_path, state, expected):
    pipeline = _pipeline('TASK-D', state)
    _write_session(tmp_path, 'RWS-derived', pipeline)

    progress = RuntimeDashboard(tmp_path).snapshot('RWS-derived')['progress']

    assert progress == {'value': expected, 'source': 'lifecycle_derived'}


def test_missing_progress_and_pipeline_are_unavailable_and_safe(tmp_path):
    _write_session(tmp_path, 'RWS-missing')
    dashboard = RuntimeDashboard(tmp_path)

    result = dashboard.snapshot('RWS-missing')

    assert result['progress'] == {'value': None, 'source': 'unavailable'}
    assert 'progress=unavailable' in dashboard.render('RWS-missing')


def test_snapshot_is_safely_copied_between_callers(tmp_path):
    pipeline = _pipeline('TASK-C', PipelineState.DEVELOPING)
    _write_session(tmp_path, 'RWS-copy', pipeline, progress=25)
    dashboard = RuntimeDashboard(tmp_path)
    first = dashboard.snapshot('RWS-copy')
    first['workers'][0]['status'] = 'tampered'

    second = dashboard.snapshot('RWS-copy')

    assert second['workers'][0]['status'] == 'Running'


def test_bounded_controller_refreshes_and_exits_without_busy_loop():
    snapshots = [
        {'session_id': 'RWS', 'current_task': 'one'},
        {'session_id': 'RWS', 'current_task': 'two'},
    ]
    provider = SequenceProvider(snapshots)
    renderer = CaptureRenderer()
    sleeps = []
    controller = LiveDashboardController(
        provider, renderer, refresh_interval=0.25,
        max_refreshes=2, sleeper=sleeps.append,
    )

    result = controller.run('RWS')

    assert result.refreshes == 2
    assert result.interrupted is False
    assert [call[0]['current_task'] for call in renderer.calls] == ['one', 'two']
    assert sleeps == [0.25]


def test_failed_refresh_preserves_previous_valid_snapshot():
    valid = {'session_id': 'RWS', 'current_task': 'safe'}
    provider = SequenceProvider([valid, OSError('read failed')])
    renderer = CaptureRenderer()
    controller = LiveDashboardController(
        provider, renderer, max_refreshes=2, sleeper=lambda delay: None,
    )

    result = controller.run('RWS')

    assert renderer.calls[1][0]['current_task'] == 'safe'
    assert renderer.calls[1][3] == 'Refresh failed (OSError)'
    assert result.last_snapshot == valid


@pytest.mark.parametrize(
    'interval', [0, -1, 'invalid', float('inf'), float('nan')],
)
def test_invalid_refresh_interval_is_rejected(interval):
    with pytest.raises(ValueError, match='positive number'):
        LiveDashboardController(
            SequenceProvider([]), CaptureRenderer(),
            refresh_interval=interval,
        )


def test_maximum_duration_bounds_refresh():
    clocks = iter([0.0, 0.2, 0.2])
    controller = LiveDashboardController(
        SequenceProvider([{'session_id': 'RWS'}]), CaptureRenderer(),
        max_duration=0.1, clock=lambda: next(clocks),
    )

    result = controller.run('RWS')

    assert result.refreshes == 1


def test_keyboard_interrupt_exits_cleanly():
    def interrupt(delay):
        raise KeyboardInterrupt

    controller = LiveDashboardController(
        SequenceProvider([{'session_id': 'RWS'}]), CaptureRenderer(),
        sleeper=interrupt,
    )

    result = controller.run('RWS')

    assert result.refreshes == 1
    assert result.interrupted is True


def test_controller_refresh_is_read_only(tmp_path):
    pipeline = _pipeline('TASK-R', PipelineState.DEVELOPING)
    directory = _write_session(tmp_path, 'RWS-readonly', pipeline, progress=25)
    path = directory / 'session.json'
    before = path.read_bytes()
    controller = LiveDashboardController(
        RuntimeDashboard(tmp_path), CaptureRenderer(), max_refreshes=1,
    )

    controller.run('RWS-readonly')

    assert path.read_bytes() == before


def _render_snapshot():
    return {
        'session_id': 'RWS-render',
        'runtime_status': 'Running',
        'current_stage': 'developing',
        'current_task': 'TASK-render',
        'current_worker': 'development_worker',
        'progress': {'value': 25, 'source': 'lifecycle_derived'},
        'workers': [{
            'worker': 'Development', 'status': 'Running',
            'current_task': 'TASK-render', 'progress': 25,
        }],
        'approval_queue': [],
        'timeline': [{
            'timestamp': '2026-07-16T10:00:00+09:00',
            'event': 'EVENT', 'worker': 'development_worker',
            'detail': 'detail',
        }],
        'evidence': [{'type': 'plan', 'path': 'plan.json'}],
        'repository': {
            'current_branch': 'feature/test',
            'working_tree': 'clean',
            'latest_commit': 'abc test',
        },
        'snapshot_timestamp': '2026-07-16T10:00:00+09:00',
    }


def test_terminal_clear_and_no_clear_behavior():
    cleared = io.StringIO()
    TerminalLiveDashboardRenderer(
        cleared, clear_supported=True,
    ).render(_render_snapshot(), 1, 1.0)
    plain = io.StringIO()
    TerminalLiveDashboardRenderer(
        plain, no_clear=True, clear_supported=True,
    ).render(_render_snapshot(), 1, 1.0)

    assert cleared.getvalue().startswith(TerminalLiveDashboardRenderer.CLEAR)
    assert TerminalLiveDashboardRenderer.CLEAR not in plain.getvalue()


def test_non_tty_output_falls_back_without_ansi_clear():
    stream = io.StringIO()

    TerminalLiveDashboardRenderer(stream).render(
        _render_snapshot(), 1, 1.0,
    )

    assert TerminalLiveDashboardRenderer.CLEAR not in stream.getvalue()
    assert 'Press Ctrl+C to exit' in stream.getvalue()


def test_no_clear_polling_does_not_repeat_timeline_events():
    stream = io.StringIO()
    renderer = TerminalLiveDashboardRenderer(stream, no_clear=True)
    snapshot = _render_snapshot()

    renderer.render(snapshot, 1, 1.0)
    renderer.render(snapshot, 2, 1.0)

    assert stream.getvalue().count('| EVENT | detail') == 1


def test_bounded_live_cli_and_json_non_live_smoke(
    tmp_path, monkeypatch, capsys,
):
    pipeline = _pipeline('TASK-cli', PipelineState.DEVELOPING)
    _write_session(tmp_path, 'RWS-cli', pipeline, progress=25)
    monkeypatch.chdir(tmp_path)

    assert main([
        'runtime-dashboard', '--session-id', 'RWS-cli', '--live',
        '--max-refreshes', '1', '--no-clear',
    ]) is None
    live = capsys.readouterr().out
    assert 'Live Runtime Dashboard' in live
    assert 'TASK-cli' in live

    assert main([
        'runtime-dashboard', '--session-id', 'RWS-cli', '--json',
    ]) is None
    data = json.loads(capsys.readouterr().out)
    assert data['runtime_status'] == 'Running'
    assert data['progress']['source'] == 'explicit_session'


def test_live_and_json_conflict_is_explicit(tmp_path, monkeypatch):
    monkeypatch.chdir(tmp_path)
    with pytest.raises(SystemExit) as exc:
        main([
            'runtime-dashboard', '--session-id', 'RWS',
            '--live', '--json',
        ])
    assert exc.value.code == 2
