import json

from afde.cli import main
from real_worker_runtime.dashboard import RuntimeDashboard, TerminalDashboard
from real_worker_runtime.models import RuntimeSession
from real_worker_runtime.runtime_pipeline import PipelineState, RuntimePipeline


def _persist(root, session_id, status, pipeline, **updates):
    directory = root / 'data' / 'runtime_sessions' / session_id
    directory.mkdir(parents=True)
    session = {
        'status': status,
        'progress': 65,
        'runtime_pipelines': [pipeline.to_dict()],
        'artifacts': [],
        'pending_approval': None,
    }
    session.update(updates)
    (directory / 'session.json').write_text(
        json.dumps(session), encoding='utf-8',
    )
    return directory


def test_no_live_silent(capsys):
    session = RuntimeSession('s', 'sp', 'r', 'mock', 'running', 'a', 'a', {})
    TerminalDashboard(False).render(session)
    assert capsys.readouterr().out == ''


def test_live_snapshot(capsys):
    session = RuntimeSession(
        's', 'sp', 'r', 'mock', 'running', 'a', 'a',
        {'pm_worker': 'running'}, 10, 'working',
    )
    TerminalDashboard(True).render(session)
    assert 'Progress: 10%' in capsys.readouterr().out


def test_completed_dashboard_reads_pipeline_events_evidence_and_repository(
    tmp_path, monkeypatch,
):
    pipeline = RuntimePipeline('TASK-33', state=PipelineState.DONE)
    directory = _persist(tmp_path, 'RWS-complete', 'completed', pipeline)
    evidence = directory / 'qa-report.json'
    evidence.write_text('{}', encoding='utf-8')
    session = json.loads((directory / 'session.json').read_text(encoding='utf-8'))
    session['artifacts'] = [
        {'type': 'qa', 'path': 'qa-report.json'},
        {'type': 'missing', 'path': 'missing.json'},
    ]
    (directory / 'session.json').write_text(json.dumps(session), encoding='utf-8')
    events = [
        {'timestamp': '2026-07-16T10:01:00+09:00', 'event': 'second', 'detail': 'b'},
        {'timestamp': '2026-07-16T10:00:00+09:00', 'event': 'first', 'detail': 'a'},
    ]
    (directory / 'events.jsonl').write_text(
        '\n'.join(json.dumps(item) for item in events), encoding='utf-8',
    )
    monkeypatch.setattr(
        RuntimeDashboard, 'repository_status',
        lambda self: {
            'current_branch': 'feature/afde-3.3-runtime-dashboard',
            'working_tree': 'dirty', 'latest_commit': 'abc dashboard',
        },
    )

    result = RuntimeDashboard(tmp_path).snapshot('RWS-complete')

    assert result['runtime_status'] == 'Completed'
    assert [row['worker'] for row in result['workers']] == [
        'Development', 'QA', 'Documentation', 'Approval', 'Release',
    ]
    assert {row['status'] for row in result['workers']} == {'Completed'}
    assert result['workers'][-1]['current_task'] == 'TASK-33'
    assert [item['event'] for item in result['timeline']] == ['first', 'second']
    assert [item['type'] for item in result['evidence']] == ['qa']
    assert result['repository']['working_tree'] == 'dirty'


def test_waiting_dashboard_exposes_pending_approval_and_pipeline_stage(tmp_path):
    pipeline = RuntimePipeline(
        'TASK-approval', state=PipelineState.APPROVAL_PENDING,
        current_worker='approval_guardian',
    )
    _persist(
        tmp_path, 'RWS-waiting', 'waiting_approval', pipeline,
        pending_approval={
            'approval_request_id': 'APR-33',
            'safe_action_summary': 'FILE_WRITE docs/report.md',
            'status': 'PENDING',
            'next_action': 'resume requires exact approval',
        },
    )
    dashboard = RuntimeDashboard(tmp_path)
    result = dashboard.snapshot('RWS-waiting')
    approval = result['approval_queue'][0]

    assert result['runtime_status'] == 'Waiting'
    assert result['workers'][3] == {
        'worker': 'Approval', 'status': 'Waiting',
        'current_task': 'TASK-approval', 'progress': 65,
    }
    assert approval['approval_id'] == 'APR-33'
    assert approval['action'] == 'FILE_WRITE docs/report.md'
    rendered = dashboard.render('RWS-waiting')
    assert 'Approval Queue' in rendered
    assert 'Runtime Timeline' in rendered
    assert 'Evidence Viewer' in rendered
    assert 'Repository Status' in rendered


def test_failed_dashboard_marks_current_pipeline_worker_failed(tmp_path):
    pipeline = RuntimePipeline('TASK-failed', state=PipelineState.QA_PENDING)
    _persist(tmp_path, 'RWS-failed', 'failed', pipeline, progress=40)

    result = RuntimeDashboard(tmp_path).snapshot('RWS-failed')

    assert result['runtime_status'] == 'Failed'
    assert result['workers'][0]['status'] == 'Completed'
    assert result['workers'][1]['status'] == 'Failed'
    assert result['workers'][1]['progress'] == 40


def test_runtime_dashboard_cli_emits_json(tmp_path, monkeypatch, capsys):
    pipeline = RuntimePipeline('TASK-cli', state=PipelineState.DEVELOPING)
    _persist(tmp_path, 'RWS-cli', 'running', pipeline, progress=25)
    monkeypatch.chdir(tmp_path)

    assert main([
        'runtime-dashboard', '--session-id', 'RWS-cli', '--json',
    ]) is None
    result = json.loads(capsys.readouterr().out)

    assert result['runtime_status'] == 'Running'
    assert result['workers'][0]['current_task'] == 'TASK-cli'
