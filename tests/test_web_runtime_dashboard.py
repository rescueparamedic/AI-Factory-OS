from copy import deepcopy
from http.client import HTTPConnection
import inspect
import json
from pathlib import Path
from threading import Thread

import pytest

from afde import cli
from real_worker_runtime.dashboard import RuntimeDashboard
from real_worker_runtime.runtime_pipeline import PipelineState, RuntimePipeline
from real_worker_runtime.web_dashboard import (
    API_ROUTES, DashboardAPI, DashboardRouteNotFound,
    RuntimeDashboardWebServer,
)


def _snapshot(task='TASK-web', status='Running'):
    return {
        'session_id': 'RWS-web',
        'runtime_status': status,
        'current_stage': 'developing',
        'current_task': task,
        'current_worker': 'development_worker',
        'progress': {'value': 25, 'source': 'lifecycle_derived'},
        'workers': [{
            'worker': 'Development', 'status': status,
            'current_task': task, 'progress': 25,
        }],
        'approval_queue': [{
            'approval_id': 'APR-web', 'action': 'FILE_WRITE report.md',
            'status': 'PENDING', 'next_action': 'exact approval required',
        }],
        'timeline': [{
            'timestamp': '2026-07-16T10:00:00+09:00',
            'event': 'START', 'worker': 'development_worker',
            'detail': 'started',
        }],
        'evidence': [{'type': 'plan', 'path': 'plan.json'}],
        'repository': {
            'current_branch': 'feature/web',
            'working_tree': 'clean',
            'latest_commit': 'abc web',
        },
        'snapshot_timestamp': '2026-07-16T10:00:00+09:00',
    }


class RecordingProvider:
    def __init__(self, snapshots=None):
        self.snapshots = list(snapshots or [_snapshot()])
        self.calls = []

    def snapshot(self, session_id):
        self.calls.append(session_id)
        index = min(len(self.calls) - 1, len(self.snapshots) - 1)
        return deepcopy(self.snapshots[index])


def _request(server, path, method='GET'):
    connection = HTTPConnection(server.host, server.port, timeout=5)
    connection.request(method, path)
    response = connection.getresponse()
    body = response.read()
    headers = dict(response.getheaders())
    status = response.status
    connection.close()
    return status, headers, body


@pytest.fixture
def web_server():
    provider = RecordingProvider()
    server = RuntimeDashboardWebServer(
        provider, 'RWS-web', port=0, poll_interval=0.25,
    )
    thread = Thread(target=server.serve_forever, daemon=True)
    thread.start()
    try:
        yield server, provider
    finally:
        server.shutdown()
        thread.join(timeout=5)
        server.close()


def test_api_routes_are_json_serializable_snapshot_views():
    provider = RecordingProvider()
    api = DashboardAPI(provider, 'RWS-web', poll_interval=0.5)

    results = {
        route: api.get(route) for route in sorted(API_ROUTES)
        if route not in {'/compare', '/operations-report'}
    }

    for result in results.values():
        assert isinstance(result, dict)
        json.dumps(result, allow_nan=False)
    assert results['/runtime']['runtime_status'] == 'Running'
    assert results['/session']['current_task'] == 'TASK-web'
    assert results['/workers']['workers'][0]['worker'] == 'Development'
    assert results['/timeline']['timeline'][0]['event'] == 'START'
    assert results['/approval-queue']['approval_queue'][0]['approval_id'] == 'APR-web'
    assert results['/evidence']['evidence'][0]['type'] == 'plan'
    assert results['/repository']['repository']['working_tree'] == 'clean'
    assert results['/config']['poll_interval_seconds'] == 0.5


def test_api_refreshes_snapshot_once_per_request():
    provider = RecordingProvider([
        _snapshot('TASK-one'), _snapshot('TASK-two', 'Completed'),
    ])
    api = DashboardAPI(provider, 'RWS-web')

    first = api.get('/runtime')
    second = api.get('/runtime')

    assert first['current_task'] == 'TASK-one'
    assert second['current_task'] == 'TASK-two'
    assert second['runtime_status'] == 'Completed'
    assert provider.calls == ['RWS-web', 'RWS-web']


def test_api_views_are_consistent_and_safely_copied():
    provider = RecordingProvider()
    api = DashboardAPI(provider, 'RWS-web')
    runtime = api.get('/runtime')
    workers = api.get('/workers')
    runtime['workers'][0]['status'] = 'tampered'
    workers['workers'][0]['status'] = 'tampered'

    fresh = api.get('/runtime')

    assert fresh['workers'][0]['status'] == 'Running'
    assert fresh['snapshot_timestamp'] == runtime['snapshot_timestamp']


def test_invalid_api_route_and_invalid_configuration_are_rejected():
    api = DashboardAPI(RecordingProvider(), 'RWS-web')
    with pytest.raises(DashboardRouteNotFound):
        api.get('/unknown')
    with pytest.raises(ValueError, match='session ID'):
        DashboardAPI(RecordingProvider(), '')
    with pytest.raises(ValueError, match='positive'):
        DashboardAPI(RecordingProvider(), 'RWS', poll_interval=0)


def test_api_controller_has_no_runtime_pipeline_dependency():
    source = inspect.getsource(DashboardAPI)

    assert 'RuntimePipeline' not in source
    assert '.transition(' not in source
    assert '.approve' not in source


@pytest.mark.parametrize(
    'route', sorted(API_ROUTES - {'/compare', '/operations-report'}),
)
def test_http_api_endpoints_return_json(web_server, route):
    server, provider = web_server

    status, headers, body = _request(server, route)
    payload = json.loads(body)

    assert status == 200
    assert headers['Content-Type'] == 'application/json; charset=utf-8'
    assert headers['Cache-Control'] == 'no-store'
    assert headers['X-Content-Type-Options'] == 'nosniff'
    assert isinstance(payload, dict)
    if route != '/config':
        assert provider.calls[-1] == 'RWS-web'


def test_http_invalid_route_is_json_404(web_server):
    server, _ = web_server

    status, headers, body = _request(server, '/not-found')

    assert status == 404
    assert headers['Content-Type'] == 'application/json; charset=utf-8'
    assert json.loads(body) == {
        'error': 'route_not_found', 'path': '/not-found',
    }


@pytest.mark.parametrize(
    'method', ['POST', 'PUT', 'PATCH', 'DELETE', 'OPTIONS'],
)
def test_http_mutation_methods_are_rejected_without_snapshot_access(
    web_server, method,
):
    server, provider = web_server

    status, headers, body = _request(server, '/runtime', method)

    assert status == 405
    assert headers['Allow'] == 'GET, HEAD'
    assert json.loads(body)['error'] == 'method_not_allowed'
    assert provider.calls == []


def test_http_head_returns_headers_without_body(web_server):
    server, provider = web_server

    status, headers, body = _request(server, '/runtime', 'HEAD')

    assert status == 200
    assert int(headers['Content-Length']) > 0
    assert body == b''
    assert provider.calls == ['RWS-web']


def test_missing_runtime_session_is_safe_json_404():
    class MissingProvider:
        def snapshot(self, session_id):
            raise FileNotFoundError(session_id)

    server = RuntimeDashboardWebServer(MissingProvider(), 'RWS-missing', port=0)
    thread = Thread(target=server.serve_forever, daemon=True)
    thread.start()
    try:
        status, _, body = _request(server, '/runtime')
    finally:
        server.shutdown()
        thread.join(timeout=5)
        server.close()

    assert status == 404
    assert json.loads(body)['error'] == 'runtime_session_not_found'


def test_non_serializable_snapshot_is_safe_json_500():
    class InvalidProvider:
        def snapshot(self, session_id):
            return {'progress': float('nan')}

    server = RuntimeDashboardWebServer(InvalidProvider(), 'RWS-invalid', port=0)
    thread = Thread(target=server.serve_forever, daemon=True)
    thread.start()
    try:
        status, _, body = _request(server, '/runtime')
    finally:
        server.shutdown()
        thread.join(timeout=5)
        server.close()

    assert status == 500
    assert json.loads(body)['error'] == 'dashboard_snapshot_unavailable'


def test_server_rejects_non_localhost_binding():
    with pytest.raises(ValueError, match='localhost'):
        RuntimeDashboardWebServer(
            RecordingProvider(), 'RWS-web', host='0.0.0.0',
        )


@pytest.mark.parametrize(
    ('path', 'content_type', 'marker'),
    [
        ('/', 'text/html; charset=utf-8', b'Operations Dashboard'),
        ('/dashboard.css', 'text/css; charset=utf-8', b'@media'),
        ('/dashboard.js', 'text/javascript; charset=utf-8', b'startDashboard'),
    ],
)
def test_browser_assets_render_with_security_headers(
    web_server, path, content_type, marker,
):
    server, _ = web_server

    status, headers, body = _request(server, path)

    assert status == 200
    assert headers['Content-Type'] == content_type
    assert marker in body
    assert headers['X-Frame-Options'] == 'DENY'
    quote = chr(39)
    assert 'default-src ' + quote + 'self' + quote in headers[
        'Content-Security-Policy'
    ]


def test_browser_skeleton_contains_all_required_cards(web_server):
    server, _ = web_server

    _, _, body = _request(server, '/')
    html = body.decode('utf-8')

    for card in (
        'runtime-summary', 'workers', 'timeline',
        'approval-queue', 'evidence', 'repository',
    ):
        assert 'id=' + chr(39) + card + chr(39) in html
    assert '<form' not in html
    assert html.count('<button') >= 1
    assert 'id=' + chr(39) + 'refresh-button' + chr(39) in html
    for control in ('Approve', 'Reject', 'Execute', 'Delete'):
        assert '>' + control + '<' not in html


def test_browser_polling_uses_get_only_and_one_runtime_endpoint():
    path = (
        Path(__file__).parents[1]
        / 'real_worker_runtime' / 'web_assets' / 'dashboard.js'
    )
    javascript = path.read_text(encoding='utf-8')

    assert 'loadJson(' + chr(39) + '/config' + chr(39) in javascript
    assert 'loadJson(runtimePath(requestedSession)' in javascript
    assert 'method: ' + chr(39) + 'GET' + chr(39) in javascript
    assert 'window.setTimeout(() => refreshRuntime(' + chr(39) + 'poll' in javascript
    assert 'state.runtimeInFlight' in javascript
    assert 'innerHTML' not in javascript
    for mutation in ('POST', 'PUT', 'PATCH', 'DELETE'):
        pattern = 'method: ' + chr(39) + mutation + chr(39)
        assert pattern not in javascript


def test_http_refresh_does_not_mutate_persisted_runtime_state(tmp_path):
    session_id = 'RWS-readonly-web'
    directory = tmp_path / 'data' / 'runtime_sessions' / session_id
    directory.mkdir(parents=True)
    pipeline = RuntimePipeline(
        'TASK-readonly', state=PipelineState.DEVELOPING,
        current_worker='development_worker',
    )
    path = directory / 'session.json'
    path.write_text(json.dumps({
        'status': 'running',
        'progress': 25,
        'runtime_pipelines': [pipeline.to_dict()],
        'pending_approval': None,
        'artifacts': [],
    }), encoding='utf-8')
    before = path.read_bytes()
    server = RuntimeDashboardWebServer(
        RuntimeDashboard(tmp_path), session_id, port=0,
    )
    thread = Thread(target=server.serve_forever, daemon=True)
    thread.start()
    try:
        status, _, _ = _request(server, '/runtime')
        second_status, _, _ = _request(server, '/approval-queue')
    finally:
        server.shutdown()
        thread.join(timeout=5)
        server.close()

    assert status == second_status == 200
    assert path.read_bytes() == before


def test_web_cli_starts_and_closes_local_server(monkeypatch, capsys):
    events = []

    class FakeServer:
        url = 'http://127.0.0.1:9999/'

        def __init__(self, provider, session_id, **settings):
            events.append(('init', session_id, settings))

        def serve_forever(self):
            events.append(('serve',))
            raise KeyboardInterrupt

        def close(self):
            events.append(('close',))

    monkeypatch.setattr(cli, 'RuntimeDashboardWebServer', FakeServer)

    assert cli.main([
        'runtime-dashboard-web', '--session-id', 'RWS-cli-web',
        '--port', '9999', '--poll-interval', '0.5',
    ]) is None

    output = capsys.readouterr().out
    assert 'Read-only localhost server' in output
    assert events[-2:] == [('serve',), ('close',)]
