from http.client import HTTPConnection
import json
from pathlib import Path
import shutil
import subprocess
from threading import Thread

import pytest

from real_worker_runtime.dashboard import RuntimeDashboard
from real_worker_runtime.runtime_pipeline import PipelineState, RuntimePipeline
from real_worker_runtime.web_dashboard import RuntimeDashboardWebServer


ROOT = Path(__file__).parents[1]
ASSETS = ROOT / 'real_worker_runtime' / 'web_assets'


def _javascript():
    return (ASSETS / 'dashboard.js').read_text(encoding='utf-8')


def _html():
    return (ASSETS / 'index.html').read_text(encoding='utf-8')


def _session(root, session_id='RWS-36', **updates):
    directory = root / 'data' / 'runtime_sessions' / session_id
    directory.mkdir(parents=True, exist_ok=True)
    pipeline = RuntimePipeline(
        'TASK-36', state=PipelineState.DEVELOPING,
        current_worker='development_worker',
    ).to_dict()
    data = {
        'status': 'running',
        'progress': 42,
        'runtime_pipelines': [pipeline],
        'pending_approval': None,
        'artifacts': [],
    }
    data.update(updates)
    path = directory / 'session.json'
    path.write_text(json.dumps(data), encoding='utf-8')
    return directory, path


def _request(server, path, method='GET'):
    connection = HTTPConnection(server.host, server.port, timeout=5)
    connection.request(method, path)
    response = connection.getresponse()
    body = response.read()
    status = response.status
    connection.close()
    return status, body


@pytest.mark.parametrize('status', ['Running', 'Waiting', 'Completed', 'Failed'])
def test_runtime_status_badge_supports_every_runtime_state(status):
    javascript = _javascript()

    assert status in javascript
    assert 'status-' + status.lower() in (
        'status-running status-waiting status-completed status-failed'
    )
    assert 'runtime-status' in javascript


def test_live_layout_has_operations_panels_and_accessibility():
    html = _html()
    css = (ASSETS / 'dashboard.css').read_text(encoding='utf-8')

    for identifier in (
        'runtime-summary', 'current-operation', 'workers', 'lifecycle',
        'approval-queue', 'timeline', 'evidence', 'repository',
        'connection-status', 'refresh-status', 'refresh-button',
    ):
        assert 'id=' + chr(39) + identifier + chr(39) in html
    assert 'aria-live=' + chr(39) + 'polite' + chr(39) in html
    assert 'type=' + chr(39) + 'button' + chr(39) in html
    assert ':focus-visible' in css
    assert 'prefers-reduced-motion' in css
    assert '@media (max-width: 760px)' in css


def test_progress_provenance_and_malformed_values_are_honest():
    javascript = _javascript()

    for source in (
        'explicit_pipeline', 'explicit_session',
        'lifecycle_derived', 'unavailable',
    ):
        assert source in javascript
    assert 'Progress unavailable' in javascript
    assert 'Number.isFinite(number)' in javascript
    assert 'boolean' in javascript
    assert 'lifecycle-derived estimate' in javascript


def test_approval_metadata_is_projected_without_mutation(tmp_path):
    _, path = _session(
        tmp_path,
        pending_approval={
            'approval_request_id': 'APR-36',
            'safe_action_summary': 'FILE_WRITE docs/report.md',
            'source_worker': 'documentation_worker',
            'guardian_reason': 'human confirmation required',
            'permission_level': 'ASK_USER',
            'requested_at': '2026-07-16T20:00:00+09:00',
            'status': 'PENDING',
            'next_action': 'resume requires exact approval',
        },
    )
    before = path.read_bytes()

    approval = RuntimeDashboard(tmp_path).snapshot('RWS-36')['approval_queue'][0]

    assert approval['actor'] == 'documentation_worker'
    assert approval['reason'] == 'human confirmation required'
    assert approval['risk'] == 'ASK_USER'
    assert approval['requested_at'].startswith('2026-07-16')
    assert path.read_bytes() == before


def test_timeline_order_task_summary_and_visible_limit(tmp_path):
    directory, _ = _session(tmp_path)
    events = [
        {
            'timestamp': '2026-07-16T20:01:00+09:00',
            'event': 'SECOND', 'worker_id': 'qa_worker',
            'task_id': 'TASK-36', 'detail': 'qa started',
        },
        {
            'timestamp': '2026-07-16T20:00:00+09:00',
            'event': 'FIRST', 'worker_id': 'development_worker',
            'task_id': 'TASK-36', 'detail': 'development started',
        },
    ]
    (directory / 'events.jsonl').write_text(
        '\n'.join(json.dumps(item) for item in events + [events[0]]),
        encoding='utf-8',
    )

    timeline = RuntimeDashboard(tmp_path).snapshot('RWS-36')['timeline']

    assert [item['event'] for item in timeline] == ['FIRST', 'SECOND']
    assert timeline[0]['task'] == 'TASK-36'
    assert timeline[1]['summary'] == 'qa started'
    javascript = _javascript()
    assert '.slice(-TIMELINE_LIMIT)' in javascript
    assert '.reverse()' not in javascript


def test_evidence_is_metadata_only_and_outside_paths_are_excluded(tmp_path):
    directory, _ = _session(tmp_path)
    inside = directory / 'qa.json'
    outside = tmp_path / 'secret.txt'
    inside.write_text('{}', encoding='utf-8')
    outside.write_text('not dashboard evidence', encoding='utf-8')
    _session(tmp_path, artifacts=[
        {'type': 'qa', 'path': 'qa.json'},
        {'type': 'unsafe', 'path': str(outside)},
        {'type': 'traversal', 'path': '../../../secret.txt'},
    ])

    evidence = RuntimeDashboard(tmp_path).snapshot('RWS-36')['evidence']

    assert len(evidence) == 1
    assert evidence[0]['identifier'] == 'qa.json'
    assert evidence[0]['availability'] == 'available'
    assert str(tmp_path) not in evidence[0]['path']
    assert 'Metadata only' in _html()


def test_path_traversal_and_mutations_are_json_rejections(tmp_path):
    _, path = _session(tmp_path)
    server = RuntimeDashboardWebServer(
        RuntimeDashboard(tmp_path), 'RWS-36', port=0,
    )
    thread = Thread(target=server.serve_forever, daemon=True)
    thread.start()
    try:
        traversal_status, traversal_body = _request(
            server, '/%2e%2e/session.json',
        )
        before = path.read_bytes()
        mutation_status, mutation_body = _request(server, '/runtime', 'POST')
        after = path.read_bytes()
    finally:
        server.shutdown()
        thread.join(timeout=5)
        server.close()

    assert traversal_status == 404
    assert json.loads(traversal_body)['error'] == 'route_not_found'
    assert mutation_status == 405
    assert json.loads(mutation_body)['error'] == 'method_not_allowed'
    assert after == before


def test_single_polling_loop_preserves_last_snapshot_and_recovers():
    javascript = _javascript()

    assert 'endpoint: ' + chr(39) + '/runtime' + chr(39) in javascript
    assert 'if (state.stopped || state.inFlight)' in javascript
    assert 'state.lastSnapshot = snapshot' in javascript
    assert 'displaying last valid snapshot' in javascript
    assert 'retry scheduled' in javascript
    assert 'state.controller.abort()' in javascript
    catch_block = javascript.rsplit('} catch (error) {', 1)[-1]
    assert 'renderSnapshot(' not in catch_block.split('} finally {', 1)[0]


def test_manual_refresh_is_get_only_and_has_no_action_controls():
    html = _html()
    javascript = _javascript()

    assert 'polling.refresh(' + chr(39) + 'manual' + chr(39) in javascript
    assert 'method: ' + chr(39) + 'GET' + chr(39) in javascript
    assert 'inner' + 'HTML' not in javascript
    for method in ('POST', 'PUT', 'PATCH', 'DELETE'):
        assert 'method: ' + chr(39) + method + chr(39) not in javascript
    for action in ('Approve', 'Reject', 'Execute', 'Dismiss', 'Delete'):
        assert '>' + action + '<' not in html


def test_repository_states_and_commit_fields_are_renderable():
    javascript = _javascript()

    assert 'Availability' in javascript
    assert 'Working tree' in javascript
    assert 'Commit hash' in javascript
    assert 'Commit summary' in javascript
    assert 'unavailable' in javascript


def test_javascript_syntax_smoke_when_node_is_available():
    node = shutil.which('node')
    if not node:
        pytest.skip('Node.js unavailable for browser asset syntax smoke')

    result = subprocess.run(
        [node, '--check', str(ASSETS / 'dashboard.js')],
        capture_output=True, text=True, check=False,
    )

    assert result.returncode == 0, result.stderr
