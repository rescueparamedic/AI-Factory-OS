from http.client import HTTPConnection
import json
from pathlib import Path
import shutil
import subprocess
from threading import Thread

import pytest

from real_worker_runtime.dashboard import RuntimeDashboard
from real_worker_runtime.runtime_pipeline import PipelineState, RuntimePipeline
from real_worker_runtime.web_dashboard import (
    DashboardAPI, DashboardSessionInvalid, DashboardSessionNotFound,
    RuntimeDashboardWebServer,
)


ROOT = Path(__file__).parents[1]
ASSETS = ROOT / 'real_worker_runtime' / 'web_assets'


def _session(root, session_id, task, updated_at, malformed=False):
    directory = root / 'data' / 'runtime_sessions' / session_id
    directory.mkdir(parents=True, exist_ok=True)
    path = directory / 'session.json'
    if malformed:
        path.write_text('{broken', encoding='utf-8')
        return path
    pipeline = RuntimePipeline(
        task, state=PipelineState.DEVELOPING,
        current_worker='development_worker',
    )
    path.write_text(json.dumps({
        'status': 'running',
        'created_at': '2026-07-16T10:00:00+09:00',
        'updated_at': updated_at,
        'progress': 35,
        'runtime_pipelines': [pipeline.to_dict()],
        'pending_approval': None,
        'artifacts': [],
    }), encoding='utf-8')
    return path


def _request(server, path, method='GET'):
    connection = HTTPConnection(server.host, server.port, timeout=5)
    connection.request(method, path)
    response = connection.getresponse()
    body = response.read()
    status = response.status
    connection.close()
    return status, body


def test_session_discovery_returns_safe_sorted_summaries(tmp_path):
    _session(tmp_path, 'RWS-old', 'TASK-old', '2026-07-16T11:00:00+09:00')
    _session(tmp_path, 'RWS-new', 'TASK-new', '2026-07-16T12:00:00+09:00')
    _session(tmp_path, 'RWS-malformed', 'unused', 'unused', malformed=True)

    summaries = RuntimeDashboard(tmp_path).sessions()

    assert [item['session_id'] for item in summaries] == [
        'RWS-new', 'RWS-old', 'RWS-malformed',
    ]
    assert summaries[0]['current_task'] == 'TASK-new'
    assert summaries[0]['progress'] == 35
    assert summaries[0]['progress_source'] == 'explicit_session'
    assert summaries[-1]['runtime_status'] == 'Unavailable'
    assert str(tmp_path) not in json.dumps(summaries)
    for item in summaries:
        assert set(item) == {
            'session_id', 'runtime_status', 'created_at', 'updated_at',
            'current_task', 'current_worker', 'progress', 'progress_source',
            'approval_count', 'evidence_count',
        }


def test_api_sessions_and_validated_session_switching(tmp_path):
    _session(tmp_path, 'RWS-one', 'TASK-one', '2026-07-16T11:00:00+09:00')
    _session(tmp_path, 'RWS-two', 'TASK-two', '2026-07-16T12:00:00+09:00')
    api = DashboardAPI(RuntimeDashboard(tmp_path), 'RWS-one')

    discovered = api.get('/sessions')
    selected = api.get('/runtime?session_id=RWS-two')

    assert discovered['read_only'] is True
    assert len(discovered['sessions']) == 2
    assert selected['session_id'] == 'RWS-two'
    assert selected['current_task'] == 'TASK-two'
    with pytest.raises(DashboardSessionInvalid):
        api.get('/runtime?session_id=../session.json')
    with pytest.raises(DashboardSessionInvalid):
        api.get('/runtime?session_id=')
    with pytest.raises(DashboardSessionNotFound):
        api.get('/runtime?session_id=RWS-unknown')


def test_http_session_switching_errors_and_bytes_are_read_only(tmp_path):
    one = _session(tmp_path, 'RWS-one', 'TASK-one', '2026-07-16T11:00:00+09:00')
    two = _session(tmp_path, 'RWS-two', 'TASK-two', '2026-07-16T12:00:00+09:00')
    before = {one: one.read_bytes(), two: two.read_bytes()}
    server = RuntimeDashboardWebServer(
        RuntimeDashboard(tmp_path), 'RWS-one', port=0,
    )
    thread = Thread(target=server.serve_forever, daemon=True)
    thread.start()
    try:
        sessions_status, sessions_body = _request(server, '/sessions')
        selected_status, selected_body = _request(
            server, '/runtime?session_id=RWS-two',
        )
        invalid_status, invalid_body = _request(
            server, '/runtime?session_id=..%2Fsession.json',
        )
        unknown_status, unknown_body = _request(
            server, '/runtime?session_id=RWS-unknown',
        )
        mutation_status, _ = _request(
            server, '/sessions?session_id=RWS-one', 'POST',
        )
    finally:
        server.shutdown()
        thread.join(timeout=5)
        server.close()

    assert sessions_status == selected_status == 200
    assert json.loads(sessions_body)['read_only'] is True
    assert json.loads(selected_body)['current_task'] == 'TASK-two'
    assert invalid_status == 400
    assert json.loads(invalid_body)['error'] == 'invalid_session_id'
    assert unknown_status == 404
    assert json.loads(unknown_body)['error'] == 'runtime_session_not_found'
    assert mutation_status == 405
    assert {path: path.read_bytes() for path in before} == before


def test_interactive_controls_cover_search_filters_sort_and_navigation():
    html = (ASSETS / 'index.html').read_text(encoding='utf-8')

    for identifier in (
        'session-selector', 'global-search', 'search-reset',
        'worker-status-filter', 'worker-source-filter', 'worker-text-filter',
        'approval-status-filter', 'timeline-event-filter',
        'timeline-actor-filter', 'timeline-task-filter',
        'timeline-status-filter', 'timeline-text-filter',
        'evidence-type-filter', 'evidence-availability-filter',
        'evidence-text-filter', 'detail-dialog', 'runtime-statistics',
    ):
        assert 'id=' + chr(39) + identifier + chr(39) in html
    assert 'section-nav' in html
    assert 'Return to top' in html
    assert 'aria-live=' + chr(39) + 'polite' + chr(39) in html
    assert '<form' not in html


def test_browser_logic_is_safe_stable_bounded_and_non_overlapping():
    javascript = (ASSETS / 'dashboard.js').read_text(encoding='utf-8')

    assert 'inner' + 'HTML' not in javascript
    assert 'stableSort(rows' in javascript
    assert 'syncApprovalStatuses(snapshot.approval_queue)' in javascript
    assert 'TIMELINE_LIMIT = 50' in javascript
    assert 'rows.slice(0, TIMELINE_LIMIT)' in javascript
    assert 'state.runtimeInFlight' in javascript
    assert 'state.sessionsInFlight' in javascript
    assert 'SESSION_REFRESH_INTERVAL = 30000' in javascript
    assert 'window.clearTimeout(state.runtimeTimer)' in javascript
    assert 'window.clearTimeout(state.sessionTimer)' in javascript
    assert 'state.runtimeController.abort()' in javascript
    assert 'state.sessionsController.abort()' in javascript
    assert 'safeRows(snapshot.workers)' in javascript
    for method in ('POST', 'PUT', 'PATCH', 'DELETE'):
        assert 'method: ' + chr(39) + method + chr(39) not in javascript


def test_detail_dialog_has_focus_escape_and_safe_text_behavior():
    javascript = (ASSETS / 'dashboard.js').read_text(encoding='utf-8')
    html = (ASSETS / 'index.html').read_text(encoding='utf-8')

    assert 'textContent' in javascript
    assert 'dialog.showModal()' in javascript
    assert 'dialog.addEventListener(' + chr(39) + 'cancel' in javascript
    assert 'detailInvoker.focus()' in javascript
    assert 'event.key !== ' + chr(39) + 'Tab' in javascript
    assert 'Inspection only' in html
    for action in ('Approve', 'Reject', 'Execute', 'Dismiss', 'Delete', 'Download'):
        assert '>' + action + '<' not in html


def test_statistics_are_derived_from_current_snapshot_only():
    javascript = (ASSETS / 'dashboard.js').read_text(encoding='utf-8')

    for label in (
        'Total workers', 'Running workers', 'Completed workers',
        'Failed workers', 'Pending approvals', 'Timeline events',
        'Evidence items', 'Explicit progress', 'Derived progress',
        'Unavailable progress',
    ):
        assert label in javascript
    assert 'localStorage' not in javascript
    assert 'sessionStorage' not in javascript


def test_search_and_stable_sort_helpers_execute_when_node_is_available():
    node = shutil.which('node')
    if not node:
        pytest.skip('Node.js unavailable for JavaScript helper smoke')
    path = str(ASSETS / 'dashboard.js').replace('\\', '/')
    quote = chr(39)
    script = (
        'global.window={addEventListener:function(){}};'
        'global.document={};require(' + quote + path + quote + ');'
        'const api=window.AFDEDashboard;'
        'if(!api.containsText({worker:' + quote + 'QA Worker' + quote + '},'
        + quote + 'qa' + quote + '))process.exit(2);'
        'const rows=[{n:2,id:' + quote + 'a' + quote + '},{n:null,id:'
        + quote + 'missing' + quote + '},{n:2,id:' + quote + 'b' + quote + '}];'
        'const sorted=api.stableSort(rows,r=>r.n,' + quote + 'asc' + quote + ');'
        'if(sorted.map(r=>r.id).join(' + quote + ',' + quote + ')!=='
        + quote + 'a,b,missing' + quote + ')process.exit(3);'
    )

    result = subprocess.run(
        [node, '-e', script], capture_output=True, text=True, check=False,
    )

    assert result.returncode == 0, result.stderr
