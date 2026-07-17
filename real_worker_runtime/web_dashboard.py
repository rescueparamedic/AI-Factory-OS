from __future__ import annotations

from copy import deepcopy
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
import json
from pathlib import Path
import re
from typing import Any, Mapping
from urllib.parse import parse_qs, urlsplit

from .live_dashboard import SnapshotProvider, validate_refresh_interval
from .operations_analytics import (
    MAX_COMPARE_SESSIONS, MIN_COMPARE_SESSIONS, OperationsAnalytics,
    export_filename, report_csv,
)


API_ROUTES = frozenset({
    '/runtime', '/session', '/workers', '/timeline',
    '/approval-queue', '/evidence', '/repository', '/config', '/sessions',
    '/operations', '/compare', '/operations-report',
})
LOCAL_HOSTS = frozenset({'127.0.0.1', 'localhost'})
SESSION_ID_PATTERN = re.compile(r'^[A-Za-z0-9][A-Za-z0-9_-]{0,127}$')


class DashboardRouteNotFound(LookupError):
    pass


class DashboardSessionInvalid(ValueError):
    pass


class DashboardSessionNotFound(LookupError):
    pass


class DashboardComparisonInvalid(ValueError):
    pass


class DashboardAPI:
    '''Read-only JSON views over one reusable dashboard snapshot provider.'''

    def __init__(
        self, provider: SnapshotProvider, session_id: str,
        poll_interval: float = 1.0,
    ):
        if not isinstance(session_id, str) or not session_id.strip():
            raise ValueError('session ID is required')
        self.provider = provider
        self.session_id = session_id
        self.poll_interval = validate_refresh_interval(poll_interval)
        self.analytics = OperationsAnalytics()

    def get(self, route: str) -> dict[str, Any]:
        parsed = urlsplit(route)
        path = parsed.path.rstrip('/') or '/'
        if path not in API_ROUTES:
            raise DashboardRouteNotFound(path)
        if path == '/sessions':
            return {
                'sessions': deepcopy(self._sessions()),
                'read_only': True,
            }
        if path in {'/operations', '/compare', '/operations-report'}:
            return self._operations(path, parsed.query)
        selected_session = self._selected_session(parsed.query)
        if path == '/config':
            return {
                'session_id': selected_session,
                'poll_interval_seconds': self.poll_interval,
                'runtime_endpoint': '/runtime',
                'sessions_endpoint': '/sessions',
                'transport': 'http-polling',
                'read_only': True,
            }
        snapshot = self.provider.snapshot(selected_session)
        if not isinstance(snapshot, Mapping):
            raise TypeError('dashboard snapshot must be a mapping')
        return deepcopy(self._view(path, snapshot))

    def _operations(self, path: str, query: str) -> dict[str, Any]:
        minimum = MIN_COMPARE_SESSIONS if path in {'/compare', '/operations-report'} else 1
        summaries = self._sessions()
        session_ids = self._comparison_ids(query, minimum, summaries)
        by_id = {
            str(item.get('session_id')): item for item in summaries
            if isinstance(item.get('session_id'), str)
        }
        snapshots = []
        for session_id in session_ids:
            try:
                snapshot = self.provider.snapshot(session_id)
                if not isinstance(snapshot, Mapping):
                    raise TypeError('dashboard snapshot must be a mapping')
                snapshots.append(dict(snapshot))
            except (FileNotFoundError, OSError, TypeError, ValueError, json.JSONDecodeError) as exc:
                summary = by_id.get(session_id, {})
                snapshots.append({
                    'session_id': session_id,
                    'runtime_status': 'Unavailable',
                    'created_at': summary.get('created_at', 'unavailable'),
                    'updated_at': summary.get('updated_at', 'unavailable'),
                    'snapshot_timestamp': 'unavailable',
                    'error': type(exc).__name__,
                })
        projection = self.analytics.project(
            snapshots, discovered_session_count=len(summaries),
        )
        if path != '/operations-report':
            return projection
        return {
            'report': projection,
            'csv': report_csv(projection),
            'filenames': {
                'json': export_filename(session_ids, 'json'),
                'csv': export_filename(session_ids, 'csv'),
            },
            'read_only': True,
        }

    def _comparison_ids(
        self, query: str, minimum: int,
        summaries: list[Mapping[str, Any]],
    ) -> list[str]:
        values = parse_qs(query, keep_blank_values=True).get('session_id', [])
        if not values and minimum == 1:
            values = [self.session_id]
        if any(not SESSION_ID_PATTERN.fullmatch(value) for value in values):
            raise DashboardSessionInvalid('invalid session ID')
        unique = list(dict.fromkeys(values))
        if len(unique) < minimum:
            raise DashboardComparisonInvalid(
                f'select between {minimum} and {MAX_COMPARE_SESSIONS} sessions',
            )
        if len(unique) > MAX_COMPARE_SESSIONS:
            raise DashboardComparisonInvalid(
                f'at most {MAX_COMPARE_SESSIONS} sessions may be compared',
            )
        discovered = {
            item.get('session_id') for item in summaries
            if isinstance(item, Mapping)
        }
        unknown = next((item for item in unique if item not in discovered), None)
        if unknown is not None:
            raise DashboardSessionNotFound(unknown)
        return unique

    def _selected_session(self, query: str) -> str:
        if not query:
            return self.session_id
        values = parse_qs(query, keep_blank_values=True).get('session_id', [])
        if len(values) != 1 or not SESSION_ID_PATTERN.fullmatch(values[0]):
            raise DashboardSessionInvalid('invalid session ID')
        selected = values[0]
        if selected not in {
            item.get('session_id') for item in self._sessions()
            if isinstance(item, Mapping)
        }:
            raise DashboardSessionNotFound(selected)
        return selected

    def _sessions(self) -> list[dict[str, Any]]:
        discover = getattr(self.provider, 'sessions', None)
        if callable(discover):
            values = discover()
            if not isinstance(values, list):
                raise TypeError('dashboard sessions must be a list')
            return [dict(item) for item in values if isinstance(item, Mapping)]
        snapshot = self.provider.snapshot(self.session_id)
        if not isinstance(snapshot, Mapping):
            raise TypeError('dashboard snapshot must be a mapping')
        progress = snapshot.get('progress', {})
        if not isinstance(progress, Mapping):
            progress = {}
        return [{
            'session_id': snapshot.get('session_id', self.session_id),
            'runtime_status': snapshot.get('runtime_status', 'Unavailable'),
            'created_at': snapshot.get('created_at', 'unavailable'),
            'updated_at': snapshot.get('updated_at', 'unavailable'),
            'current_task': snapshot.get('current_task', 'unavailable'),
            'current_worker': snapshot.get('current_worker', 'unavailable'),
            'progress': progress.get('value'),
            'progress_source': progress.get('source', 'unavailable'),
            'approval_count': len(snapshot.get('approval_queue', [])),
            'evidence_count': len(snapshot.get('evidence', [])),
        }]

    @staticmethod
    def _view(path: str, snapshot: Mapping[str, Any]) -> dict[str, Any]:
        timestamp = snapshot.get('snapshot_timestamp', 'unavailable')
        if path == '/runtime':
            return dict(snapshot)
        if path == '/session':
            return {
                'session_id': snapshot.get('session_id', 'unavailable'),
                'runtime_status': snapshot.get('runtime_status', 'Unavailable'),
                'current_stage': snapshot.get('current_stage', 'unavailable'),
                'current_task': snapshot.get('current_task', 'unavailable'),
                'current_worker': snapshot.get('current_worker', 'unavailable'),
                'progress': snapshot.get(
                    'progress', {'value': None, 'source': 'unavailable'},
                ),
                'snapshot_timestamp': timestamp,
            }
        field = {
            '/workers': 'workers',
            '/timeline': 'timeline',
            '/approval-queue': 'approval_queue',
            '/evidence': 'evidence',
            '/repository': 'repository',
        }[path]
        value = deepcopy(snapshot.get(field, [] if field != 'repository' else {}))
        return {
            'session_id': snapshot.get('session_id', 'unavailable'),
            field: value,
            'snapshot_timestamp': timestamp,
        }


def build_dashboard_handler(
    api: DashboardAPI, asset_root: str | Path | None = None,
) -> type[BaseHTTPRequestHandler]:
    root = Path(asset_root) if asset_root else Path(__file__).with_name('web_assets')
    assets = {
        '/': ('index.html', 'text/html; charset=utf-8'),
        '/index.html': ('index.html', 'text/html; charset=utf-8'),
        '/dashboard.css': ('dashboard.css', 'text/css; charset=utf-8'),
        '/dashboard.js': ('dashboard.js', 'text/javascript; charset=utf-8'),
    }

    class DashboardRequestHandler(BaseHTTPRequestHandler):
        server_version = 'AFDE-Dashboard/3.8'

        def do_GET(self) -> None:
            self._read(head_only=False)

        def do_HEAD(self) -> None:
            self._read(head_only=True)

        def do_POST(self) -> None:
            self._method_not_allowed()

        def do_PUT(self) -> None:
            self._method_not_allowed()

        def do_PATCH(self) -> None:
            self._method_not_allowed()

        def do_DELETE(self) -> None:
            self._method_not_allowed()

        def do_OPTIONS(self) -> None:
            self._method_not_allowed()

        def _read(self, head_only: bool) -> None:
            path = urlsplit(self.path).path
            if path in assets:
                name, content_type = assets[path]
                try:
                    body = (root / name).read_bytes()
                except OSError:
                    self._json(
                        500, {'error': 'dashboard_asset_unavailable'},
                        head_only=head_only,
                    )
                    return
                self._response(200, content_type, body, head_only)
                return
            try:
                payload = api.get(self.path)
                body = _json_bytes(payload)
            except DashboardRouteNotFound:
                self._json(
                    404, {'error': 'route_not_found', 'path': path},
                    head_only=head_only,
                )
                return
            except DashboardSessionInvalid:
                self._json(
                    400, {'error': 'invalid_session_id'},
                    head_only=head_only,
                )
                return
            except DashboardComparisonInvalid as exc:
                self._json(
                    400, {'error': 'invalid_comparison', 'detail': str(exc)},
                    head_only=head_only,
                )
                return
            except DashboardSessionNotFound:
                self._json(
                    404, {'error': 'runtime_session_not_found'},
                    head_only=head_only,
                )
                return
            except FileNotFoundError:
                self._json(
                    404, {
                        'error': 'runtime_session_not_found',
                        'session_id': api.session_id,
                    },
                    head_only=head_only,
                )
                return
            except (OSError, TypeError, ValueError, json.JSONDecodeError):
                self._json(
                    500, {'error': 'dashboard_snapshot_unavailable'},
                    head_only=head_only,
                )
                return
            self._response(
                200, 'application/json; charset=utf-8', body, head_only,
            )

        def _method_not_allowed(self) -> None:
            body = _json_bytes({'error': 'method_not_allowed'})
            self.send_response(405)
            self.send_header('Allow', 'GET, HEAD')
            self._security_headers()
            self.send_header('Content-Type', 'application/json; charset=utf-8')
            self.send_header('Content-Length', str(len(body)))
            self.end_headers()
            self.wfile.write(body)

        def _json(
            self, status: int, payload: Mapping[str, Any],
            head_only: bool = False,
        ) -> None:
            self._response(
                status, 'application/json; charset=utf-8',
                _json_bytes(payload), head_only,
            )

        def _response(
            self, status: int, content_type: str, body: bytes,
            head_only: bool,
        ) -> None:
            self.send_response(status)
            self._security_headers()
            self.send_header('Content-Type', content_type)
            self.send_header('Content-Length', str(len(body)))
            self.send_header('Cache-Control', 'no-store')
            self.end_headers()
            if not head_only:
                self.wfile.write(body)

        def _security_headers(self) -> None:
            quote = chr(39)
            policy = (
                f'default-src {quote}self{quote}; '
                f'script-src {quote}self{quote}; '
                f'style-src {quote}self{quote}; '
                f'connect-src {quote}self{quote}; '
                f'img-src {quote}self{quote} data:; '
                f'object-src {quote}none{quote}; '
                f'base-uri {quote}none{quote}; '
                f'form-action {quote}none{quote}; '
                f'frame-ancestors {quote}none{quote}'
            )
            self.send_header('X-Content-Type-Options', 'nosniff')
            self.send_header('X-Frame-Options', 'DENY')
            self.send_header('Referrer-Policy', 'no-referrer')
            self.send_header('Content-Security-Policy', policy)

        def log_message(self, format: str, *args: Any) -> None:
            return

    return DashboardRequestHandler


class RuntimeDashboardWebServer:
    '''Localhost-only HTTP transport for the read-only Dashboard API.'''

    def __init__(
        self, provider: SnapshotProvider, session_id: str,
        host: str = '127.0.0.1', port: int = 8765,
        poll_interval: float = 1.0,
        asset_root: str | Path | None = None,
    ):
        normalized_host = str(host).lower()
        if normalized_host not in LOCAL_HOSTS:
            raise ValueError('web dashboard host must be localhost')
        if isinstance(port, bool) or not isinstance(port, (int, str)):
            raise ValueError('port must be between 0 and 65535')
        if isinstance(port, str) and not port.isdecimal():
            raise ValueError('port must be between 0 and 65535')
        try:
            normalized_port = int(port)
        except (TypeError, ValueError) as exc:
            raise ValueError('port must be between 0 and 65535') from exc
        if not 0 <= normalized_port <= 65535:
            raise ValueError('port must be between 0 and 65535')
        self.api = DashboardAPI(provider, session_id, poll_interval)
        handler = build_dashboard_handler(self.api, asset_root)
        self.httpd = ThreadingHTTPServer(
            (normalized_host, normalized_port), handler,
        )
        self.httpd.daemon_threads = True

    @property
    def host(self) -> str:
        return str(self.httpd.server_address[0])

    @property
    def port(self) -> int:
        return int(self.httpd.server_address[1])

    @property
    def url(self) -> str:
        return 'http://{}:{}/'.format(self.host, self.port)

    def serve_forever(self) -> None:
        self.httpd.serve_forever(poll_interval=0.2)

    def shutdown(self) -> None:
        self.httpd.shutdown()

    def close(self) -> None:
        self.httpd.server_close()

    def __enter__(self) -> RuntimeDashboardWebServer:
        return self

    def __exit__(self, *args: Any) -> None:
        self.close()


def _json_bytes(payload: Mapping[str, Any]) -> bytes:
    return json.dumps(
        payload, ensure_ascii=False, allow_nan=False, separators=(',', ':'),
    ).encode('utf-8')
