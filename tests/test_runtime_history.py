from copy import deepcopy
import csv
from io import StringIO
import json

import pytest

from afde import cli
from real_worker_runtime import RealWorkerRuntime
from real_worker_runtime.artifact_store import ArtifactStore
from real_worker_runtime.dashboard import RuntimeDashboard
from real_worker_runtime.event_stream import EventStream
from real_worker_runtime.models import RuntimeEvent
from real_worker_runtime.runtime_history import (
    RuntimeHistoryInvalid, RuntimeHistoryStore, history_csv,
)
from real_worker_runtime.web_dashboard import DashboardAPI


def _session(root, session_id):
    directory = root / 'data' / 'runtime_sessions' / session_id
    directory.mkdir(parents=True, exist_ok=True)
    (directory / 'session.json').write_text(json.dumps({
        'status': 'running', 'created_at': '2026-07-18T00:00:00Z',
        'updated_at': '2026-07-18T01:00:00Z', 'runtime_pipelines': [],
        'artifacts': [], 'pending_approval': None,
    }), encoding='utf-8')
    return directory


def test_event_model_and_append_only_safe_copy(tmp_path):
    _session(tmp_path, 'RWS-model')
    stream = EventStream(ArtifactStore(tmp_path, 'RWS-model'))
    event = stream.emit('WORKER_STARTED', 'development_worker', payload={'attempt': 1})
    path = tmp_path / 'data' / 'runtime_sessions' / 'RWS-model' / 'events.jsonl'
    before = path.read_bytes(); stream.emit('WORKER_COMPLETED', 'development_worker')
    assert isinstance(event, RuntimeEvent)
    assert event.event_id.startswith('EVT-') and event.session_id == 'RWS-model'
    assert event.event_type == 'WORKER_STARTED' and event.actor == 'development_worker'
    assert event.status == 'running' and event.metadata == {'attempt': 1}
    assert path.read_bytes().startswith(before)
    rows = RuntimeHistoryStore(tmp_path).events('RWS-model')
    rows[0]['metadata']['tampered'] = True
    assert 'tampered' not in RuntimeHistoryStore(tmp_path).events('RWS-model')[0]['metadata']


def test_store_rejects_missing_required_event_fields(tmp_path):
    with pytest.raises(RuntimeHistoryInvalid, match='required event fields'):
        RuntimeHistoryStore(tmp_path).append({'session_id': 'RWS-invalid'})


def test_major_runtime_event_types_cover_approval_qa_error_and_completion(tmp_path):
    _session(tmp_path, 'RWS-types')
    stream = EventStream(ArtifactStore(tmp_path, 'RWS-types'))
    for name in (
        'RUNTIME_CREATED', 'APPROVAL_PENDING', 'APPROVAL_CONSUMED',
        'QA_COMPLETED', 'PROVIDER_ERROR', 'RUNTIME_COMPLETED',
    ):
        stream.emit(name, 'qa_worker' if name.startswith('QA_') else '')
    rows = RuntimeHistoryStore(tmp_path).events('RWS-types')
    assert [(row['event_type'], row['status']) for row in rows] == [
        ('SESSION_STARTED', 'running'),
        ('APPROVAL_REQUESTED', 'waiting'),
        ('APPROVAL_COMPLETED', 'completed'),
        ('QA_COMPLETED', 'completed'),
        ('ERROR_OCCURRED', 'failed'),
        ('SESSION_COMPLETED', 'completed'),
    ]


def test_ordering_and_filters_are_deterministic(tmp_path):
    directory = _session(tmp_path, 'RWS-order')
    values = [
        {'event': 'SECOND', 'timestamp': '2026-07-18T10:00:00+09:00'},
        {'event': 'FIRST-A', 'timestamp': '2026-07-18T00:00:00Z'},
        {'event': 'FIRST-B', 'timestamp': '2026-07-18T00:00:00Z'},
        {'event': 'PROVIDER_ERROR', 'timestamp': 'not-a-time', 'worker_id': 'qa_worker'},
    ]
    (directory / 'events.jsonl').write_text(
        ''.join(json.dumps(row) + '\n' for row in values), encoding='utf-8',
    )
    store = RuntimeHistoryStore(tmp_path); rows = store.events('RWS-order')
    assert [row['event'] for row in rows] == ['FIRST-A', 'FIRST-B', 'SECOND', 'PROVIDER_ERROR']
    errors = store.events(
        'RWS-order', event_type='ERROR_OCCURRED', actor='qa_worker',
        status='failed', worker_id='qa_worker',
    )
    assert len(errors) == 1 and errors[0]['event'] == 'PROVIDER_ERROR'


def test_session_filter_and_legacy_normalization_do_not_rewrite(tmp_path):
    one = _session(tmp_path, 'RWS-one'); _session(tmp_path, 'RWS-two')
    path = one / 'events.jsonl'
    path.write_text(json.dumps({
        'event': 'RUNTIME_CREATED', 'timestamp': '2026-07-18T00:00:00Z',
        'payload': {'legacy': True},
    }) + '\n', encoding='utf-8')
    before = path.read_bytes(); store = RuntimeHistoryStore(tmp_path)
    first = store.events('RWS-one'); second = store.events('RWS-one')
    assert first == second and first[0]['event_id'].startswith('EVT-LEGACY-')
    assert first[0]['event_type'] == 'SESSION_STARTED'
    assert first[0]['legacy_normalized'] is True and path.read_bytes() == before
    assert store.events('RWS-two') == []


@pytest.mark.parametrize('session_id', ['../session.json', '', 'RWS/bad'])
def test_invalid_session_ids_are_rejected(tmp_path, session_id):
    with pytest.raises(RuntimeHistoryInvalid, match='session ID'):
        RuntimeHistoryStore(tmp_path).events(session_id)


def test_invalid_range_and_limit_are_rejected(tmp_path):
    _session(tmp_path, 'RWS-filter'); store = RuntimeHistoryStore(tmp_path)
    with pytest.raises(RuntimeHistoryInvalid, match='timezone-aware'):
        store.events('RWS-filter', since='2026-01-01')
    with pytest.raises(RuntimeHistoryInvalid, match='since'):
        store.events('RWS-filter', since='2026-02-01T00:00:00Z', until='2026-01-01T00:00:00Z')
    with pytest.raises(RuntimeHistoryInvalid, match='limit'):
        store.events('RWS-filter', limit=0)


def test_runtime_integration_records_major_events(tmp_path):
    session = RealWorkerRuntime(tmp_path).run('AFDE-3.9 integration', provider='mock', live=False)
    rows = RuntimeHistoryStore(tmp_path).events(session.session_id)
    types = {row['event_type'] for row in rows}
    assert session.status == 'completed'
    assert {'SESSION_STARTED', 'WORKER_STARTED', 'WORKER_COMPLETED',
            'QA_COMPLETED', 'SESSION_COMPLETED'} <= types
    assert all(row['session_id'] == session.session_id for row in rows)


def test_dashboard_and_api_project_history_and_errors(tmp_path):
    _session(tmp_path, 'RWS-dashboard')
    stream = EventStream(ArtifactStore(tmp_path, 'RWS-dashboard'))
    stream.emit('WORKER_STARTED', 'qa_worker'); stream.emit('PROVIDER_ERROR', 'qa_worker')
    snapshot = RuntimeDashboard(tmp_path).snapshot('RWS-dashboard')
    assert snapshot['history_summary']['event_count'] == 2
    assert snapshot['history_summary']['error_event_count'] == 1
    assert snapshot['error_events'][0]['event_type'] == 'ERROR_OCCURRED'
    assert snapshot['timeline'][1]['status'] == 'failed'
    assert str(tmp_path) not in json.dumps(snapshot)

    class Provider:
        def snapshot(self, session_id): return deepcopy(snapshot)
    api = DashboardAPI(Provider(), 'RWS-dashboard')
    history = api.get('/history'); errors = api.get('/error-events')
    assert len(history['event_history']) == 2 and len(errors['error_events']) == 1
    history['event_history'][0]['event_id'] = 'tampered'
    assert api.get('/history')['event_history'][0]['event_id'] != 'tampered'


def test_cli_history_events_and_exports(tmp_path, monkeypatch, capsys):
    _session(tmp_path, 'RWS-cli')
    stream = EventStream(ArtifactStore(tmp_path, 'RWS-cli'))
    stream.emit('SESSION_STARTED'); stream.emit('PROVIDER_ERROR', 'qa_worker', '=unsafe')
    monkeypatch.chdir(tmp_path)
    cli.main(['runtime-history', '--session-id', 'RWS-cli', '--json'])
    history = json.loads(capsys.readouterr().out)
    assert history['event_count'] == 2 and history['error_event_count'] == 1
    cli.main(['runtime-events', '--session-id', 'RWS-cli', '--event-type', 'ERROR_OCCURRED', '--json'])
    events = json.loads(capsys.readouterr().out)
    assert events['event_count'] == 1 and events['events'][0]['status'] == 'failed'
    cli.main(['runtime-export', '--session-id', 'RWS-cli', '--format', 'csv'])
    rows = list(csv.DictReader(StringIO(capsys.readouterr().out)))
    assert len(rows) == 2 and rows[1]['detail'] == chr(39) + '=unsafe'


def test_csv_does_not_mutate_summary():
    summary = {'events': [{
        'event_id': 'EVT-1', 'session_id': 'RWS-csv',
        'timestamp': '2026-07-18T00:00:00Z', 'event_type': 'SESSION_STARTED',
        'actor': 'runtime', 'status': 'running', 'metadata': {'key': 'value'},
    }]}
    before = deepcopy(summary)
    assert 'SESSION_STARTED' in history_csv(summary) and summary == before
