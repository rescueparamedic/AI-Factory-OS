from copy import deepcopy
import csv
from http.client import HTTPConnection
from io import StringIO
import json
from pathlib import Path
from threading import Thread

import pytest

from real_worker_runtime.dashboard import RuntimeDashboard
from real_worker_runtime.operations_analytics import (
    MAX_COMPARE_SESSIONS, OperationsAnalytics, export_filename, report_csv,
)
from real_worker_runtime.runtime_pipeline import PipelineState, RuntimePipeline
from real_worker_runtime.web_dashboard import (
    DashboardAPI, DashboardComparisonInvalid, DashboardSessionInvalid,
    DashboardSessionNotFound, RuntimeDashboardWebServer,
)


ASSETS = Path(__file__).parents[1] / 'real_worker_runtime' / 'web_assets'


def _snapshot(session_id='RWS-one', status='Running', *, created='2026-07-17T00:00:00Z',
              updated='2026-07-17T01:00:00Z', snapshot_time='2026-07-17T02:00:00Z'):
    return {
        'session_id': session_id, 'runtime_status': status,
        'current_stage': 'developing', 'current_task': 'TASK-one',
        'current_worker': 'development_worker',
        'created_at': created, 'updated_at': updated,
        'snapshot_timestamp': snapshot_time,
        'progress': {'value': 40, 'source': 'explicit_session'},
        'workers': [
            {'worker': 'Development', 'status': 'Completed'},
            {'worker': 'QA', 'status': 'Failed'},
        ],
        'approval_queue': [], 'timeline': [],
        'evidence': [{'identifier': 'report.json'}],
        'repository': {'current_branch': 'feature/test', 'working_tree': 'clean'},
    }


def test_projection_is_deterministic_copied_and_does_not_mutate_inputs():
    source = [_snapshot()]
    before = deepcopy(source)
    analytics = OperationsAnalytics()

    first = analytics.project(source, discovered_session_count=3)
    second = analytics.project(source, discovered_session_count=3)
    first['comparisons'][0]['runtime_status'] = 'tampered'

    assert second == analytics.project(source, discovered_session_count=3)
    assert source == before
    assert second['snapshot_derived'] is True
    assert second['read_only'] is True


def test_kpis_status_duration_workers_and_progress_denominators_are_honest():
    snapshots = [
        _snapshot('RWS-run'),
        _snapshot('RWS-done', 'Completed', updated='2026-07-17T03:00:00Z'),
        _snapshot('RWS-wait', 'Waiting', created='invalid'),
        _snapshot('RWS-unavailable', 'Unavailable', updated='invalid'),
    ]
    snapshots[1]['progress'] = {'value': 100, 'source': 'lifecycle_derived'}
    snapshots[2]['progress'] = {'value': None, 'source': 'unavailable'}
    result = OperationsAnalytics().project(snapshots, discovered_session_count=9)
    kpis = result['kpis']

    assert kpis['discovered_session_count'] == 9
    assert kpis['selected_comparison_session_count'] == 4
    assert kpis['running_session_count'] == 1
    assert kpis['waiting_session_count'] == 1
    assert kpis['completed_session_count'] == 1
    assert kpis['unavailable_session_count'] == 1
    assert kpis['average_elapsed_seconds'] == 9000
    assert kpis['median_elapsed_seconds'] == 9000
    assert kpis['elapsed_duration_denominator'] == 2
    assert kpis['total_worker_count'] == 8
    assert kpis['failed_worker_count'] == 4
    assert kpis['explicit_progress_count'] == 2
    assert kpis['lifecycle_derived_progress_count'] == 1
    assert kpis['unavailable_progress_count'] == 1


def test_missing_invalid_and_negative_elapsed_durations_are_unavailable():
    rows = [
        _snapshot('RWS-missing', created='unavailable'),
        _snapshot('RWS-invalid', created='not-a-time'),
        _snapshot('RWS-negative', created='2026-07-17T03:00:00Z'),
    ]
    result = OperationsAnalytics().project(rows)
    assert [row['elapsed_seconds'] for row in result['comparisons']] == [None, None, None]
    assert result['kpis']['average_elapsed_seconds'] is None
    assert result['kpis']['elapsed_duration_denominator'] == 0


def test_stage_duration_measured_precedes_inferred_and_active_is_safe():
    snapshot = _snapshot()
    snapshot['current_stage'] = 'qa_pending'
    snapshot['timeline'] = [
        {'timestamp': '2026-07-17T00:00:00Z', 'event': 'development_started',
         'stage': 'Development', 'duration_seconds': 120},
        {'timestamp': '2026-07-17T00:10:00Z', 'event': 'qa_started'},
    ]
    result = OperationsAnalytics().project([snapshot])
    stages = {row['stage']: row for row in result['stage_durations']['RWS-one']}

    assert stages['Development']['duration_seconds'] == 120
    assert stages['Development']['provenance'] == 'measured'
    assert stages['QA']['duration_seconds'] == 6600
    assert stages['QA']['provenance'] == 'inferred'
    assert stages['Planning']['duration_seconds'] is None
    assert stages['Planning']['provenance'] == 'unavailable'


def test_invalid_explicit_stage_duration_is_rejected():
    snapshot = _snapshot()
    snapshot['timeline'] = [{
        'timestamp': '2026-07-17T00:00:00Z', 'event': 'development',
        'duration_seconds': -1,
    }]
    stages = OperationsAnalytics().project([snapshot])['stage_durations']['RWS-one']
    development = next(row for row in stages if row['stage'] == 'Development')
    assert development['duration_seconds'] == 7200
    assert development['provenance'] == 'inferred'


def test_longest_stage_and_waiting_approval_findings_are_explainable():
    snapshot = _snapshot(status='Waiting')
    snapshot['current_stage'] = 'approval_pending'
    snapshot['timeline'] = [
        {'timestamp': '2026-07-17T00:00:00Z', 'event': 'development', 'duration_seconds': 100},
        {'timestamp': '2026-07-17T00:10:00Z', 'event': 'approval'},
    ]
    snapshot['approval_queue'] = [{
        'approval_id': 'APR-1', 'status': 'PENDING',
        'requested_at': '2026-07-17T00:00:00Z', 'actor': 'worker',
    }]
    result = OperationsAnalytics().project([snapshot])
    findings = result['findings']

    assert any(row['finding_type'] == 'longest_stage' for row in findings)
    waiting = next(row for row in findings if row['finding_type'] == 'approval_wait')
    assert waiting['evidence_fields'] == ['runtime_status', 'approval_queue.status']
    assert waiting['advisory_only'] is True
    assert any(row['finding_type'] == 'approval_delay' and row['severity'] == 'critical' for row in findings)


def test_approval_age_missing_timestamp_and_median_are_honest():
    snapshot = _snapshot(status='Waiting')
    snapshot['approval_queue'] = [
        {'approval_id': 'APR-old', 'status': 'PENDING', 'requested_at': '2026-07-17T00:00:00Z'},
        {'approval_id': 'APR-new', 'status': 'PENDING', 'requested_at': '2026-07-17T01:00:00Z'},
        {'approval_id': 'APR-missing', 'status': 'PENDING'},
    ]
    delays = OperationsAnalytics().project([snapshot])['approval_delays']['RWS-one']
    assert delays['pending_count'] == 3
    assert delays['oldest_pending_age_seconds'] == 7200
    assert delays['median_pending_age_seconds'] == 5400
    assert delays['available_age_denominator'] == 2
    assert delays['pending'][-1]['age_seconds'] is None


def test_failure_summary_bounds_text_and_repeated_categories_are_deterministic():
    snapshot = _snapshot(status='Failed')
    snapshot['timeline'] = [
        {'timestamp': '2026-07-17T00:00:00Z', 'event': 'FAILED', 'category': 'Timeout', 'detail': 'x' * 900},
        {'timestamp': '2026-07-17T01:00:00Z', 'event': 'error', 'category': 'timeout', 'detail': 'again'},
    ]
    result = OperationsAnalytics().project([snapshot])
    failures = result['failure_summaries']['RWS-one']

    assert failures['failure_event_count'] == 2
    assert failures['repeated_categories'] == [{'category': 'timeout', 'count': 2}]
    assert len(failures['most_recent_failure']['message']) <= 500
    assert 'root cause unavailable' in failures['interpretation'].lower()
    repeated = next(row for row in result['findings'] if row['finding_type'] == 'repeated_failure')
    assert repeated['confidence_provenance'] == 'heuristic'


def test_staleness_thresholds_exclude_terminal_sessions():
    active = _snapshot('RWS-active', updated='2026-07-16T23:00:00Z')
    completed = _snapshot('RWS-done', 'Completed', updated='2026-07-16T00:00:00Z')
    result = OperationsAnalytics().project([active, completed])
    by_id = {row['session_id']: row for row in result['comparisons']}
    assert by_id['RWS-active']['staleness']['state'] == 'stale'
    assert by_id['RWS-done']['staleness']['state'] == 'fresh'
    assert not any(row['finding_type'] == 'stale_session' and row['session_id'] == 'RWS-done' for row in result['findings'])


def test_json_and_csv_reports_include_provenance_and_safe_names():
    report = OperationsAnalytics().project([_snapshot('RWS-one'), _snapshot('RWS-two')])
    report['comparisons'][0]['current_task'] = '=FORMULA'
    csv_text = report_csv(report)

    assert report['findings'][0]['confidence_provenance'] in {'measured', 'inferred', 'heuristic'}
    assert csv_text.startswith('record_type,key,value,provenance,session_id')
    assert 'RWS-one' in csv_text and 'RWS-two' in csv_text
    assert 'generated_at' in csv_text and 'kpi_definition' in csv_text
    assert 'finding' in csv_text and 'snapshot_derived' in csv_text
    rows = list(csv.DictReader(StringIO(csv_text)))
    comparison = next(row for row in rows if row['record_type'] == 'comparison')
    assert comparison['current_task'] == chr(39) + '=FORMULA'
    assert export_filename(['RWS-one', '../bad'], 'json') == 'afde-operations-RWS-one-bad.json'
    json.dumps(report, allow_nan=False)


class Provider:
    def __init__(self, snapshots):
        self.snapshots = {row['session_id']: deepcopy(row) for row in snapshots}
        self.calls = []

    def sessions(self):
        return [{'session_id': key, 'runtime_status': value['runtime_status'],
                 'created_at': value.get('created_at', 'unavailable'),
                 'updated_at': value.get('updated_at', 'unavailable')}
                for key, value in sorted(self.snapshots.items())]

    def snapshot(self, session_id):
        self.calls.append(session_id)
        value = self.snapshots[session_id]
        if value.get('malformed'):
            raise json.JSONDecodeError('bad', '', 0)
        return deepcopy(value)


def test_comparison_supports_two_maximum_and_deduplicates_stably():
    snapshots = [_snapshot(f'RWS-{index}') for index in range(MAX_COMPARE_SESSIONS)]
    api = DashboardAPI(Provider(snapshots), 'RWS-0')

    two = api.get('/compare?session_id=RWS-1&session_id=RWS-0&session_id=RWS-1')
    maximum = api.get('/compare?' + '&'.join(f'session_id=RWS-{i}' for i in range(MAX_COMPARE_SESSIONS)))

    assert two['selected_session_ids'] == ['RWS-0', 'RWS-1']
    assert len(maximum['comparisons']) == MAX_COMPARE_SESSIONS


def test_comparison_rejects_too_few_too_many_unknown_and_traversal():
    snapshots = [_snapshot(f'RWS-{index}') for index in range(MAX_COMPARE_SESSIONS + 1)]
    api = DashboardAPI(Provider(snapshots), 'RWS-0')
    with pytest.raises(DashboardComparisonInvalid):
        api.get('/compare?session_id=RWS-0')
    with pytest.raises(DashboardComparisonInvalid):
        api.get('/compare?' + '&'.join(f'session_id=RWS-{i}' for i in range(MAX_COMPARE_SESSIONS + 1)))
    with pytest.raises(DashboardSessionNotFound):
        api.get('/compare?session_id=RWS-0&session_id=RWS-unknown')
    with pytest.raises(DashboardSessionInvalid):
        api.get('/compare?session_id=RWS-0&session_id=../session.json')


def test_malformed_discovered_session_degrades_to_unavailable_without_path():
    malformed = _snapshot('RWS-bad')
    malformed['malformed'] = True
    api = DashboardAPI(Provider([_snapshot(), malformed]), 'RWS-one')
    result = api.get('/compare?session_id=RWS-one&session_id=RWS-bad')
    bad = next(row for row in result['comparisons'] if row['session_id'] == 'RWS-bad')
    assert bad['runtime_status'] == 'Unavailable'
    assert bad['error'] == 'JSONDecodeError'
    assert 'path' not in json.dumps(result).lower()


def test_operations_report_is_json_with_csv_and_provenance():
    api = DashboardAPI(Provider([_snapshot(), _snapshot('RWS-two')]), 'RWS-one')
    payload = api.get('/operations-report?session_id=RWS-one&session_id=RWS-two')
    assert payload['read_only'] is True
    assert payload['report']['kpi_definitions']
    assert payload['report']['findings'][0]['confidence_provenance']
    assert payload['filenames']['csv'].endswith('.csv')
    assert 'RWS-one' in payload['csv']


def _request(server, path, method='GET'):
    connection = HTTPConnection(server.host, server.port, timeout=5)
    connection.request(method, path)
    response = connection.getresponse()
    body = response.read()
    status = response.status
    connection.close()
    return status, json.loads(body)


def test_http_comparison_validation_and_mutation_rejection_do_not_mutate_provider():
    provider = Provider([_snapshot(), _snapshot('RWS-two')])
    server = RuntimeDashboardWebServer(provider, 'RWS-one', port=0)
    thread = Thread(target=server.serve_forever, daemon=True)
    thread.start()
    try:
        assert _request(server, '/compare?session_id=RWS-one')[0] == 400
        assert _request(server, '/compare?session_id=RWS-one&session_id=RWS-unknown')[0] == 404
        assert _request(server, '/compare?session_id=..%2Fbad&session_id=RWS-one')[0] == 400
        calls = list(provider.calls)
        status, payload = _request(server, '/compare?session_id=RWS-one&session_id=RWS-two', 'POST')
        assert status == 405 and payload['error'] == 'method_not_allowed'
        assert provider.calls == calls
    finally:
        server.shutdown(); thread.join(timeout=5); server.close()


def test_persisted_session_bytes_remain_unchanged_during_comparison(tmp_path):
    paths = []
    for session_id in ('RWS-one', 'RWS-two'):
        directory = tmp_path / 'data' / 'runtime_sessions' / session_id
        directory.mkdir(parents=True)
        pipeline = RuntimePipeline('TASK', PipelineState.DEVELOPING, 'development_worker')
        path = directory / 'session.json'
        path.write_text(json.dumps({
            'status': 'running', 'created_at': '2026-07-17T00:00:00Z',
            'updated_at': '2026-07-17T01:00:00Z', 'runtime_pipelines': [pipeline.to_dict()],
            'artifacts': [], 'pending_approval': None,
        }), encoding='utf-8')
        paths.append(path)
    before = {path: path.read_bytes() for path in paths}
    DashboardAPI(RuntimeDashboard(tmp_path), 'RWS-one').get(
        '/compare?session_id=RWS-one&session_id=RWS-two',
    )
    assert {path: path.read_bytes() for path in paths} == before


def test_operations_center_markup_and_scripts_keep_read_only_accessible_boundary():
    html = (ASSETS / 'index.html').read_text(encoding='utf-8')
    javascript = (ASSETS / 'dashboard.js').read_text(encoding='utf-8')
    for identifier in (
        'operations-center', 'comparison-sessions', 'compare-button', 'clear-comparison',
        'operations-kpis', 'comparison-table', 'stage-duration-panel', 'bottleneck-findings',
        'approval-delay-panel', 'failure-summary-panel', 'operations-result-status',
        'finding-session-filter', 'finding-severity-filter', 'finding-type-filter',
        'finding-stage-filter', 'finding-text-filter', 'finding-sort', 'finding-reset',
        'export-json', 'export-csv',
    ):
        assert 'id=' + chr(39) + identifier + chr(39) in html
    assert 'aria-live=' + chr(39) + 'polite' + chr(39) in html
    assert '<table' in html and '<caption' in html
    assert 'inner' + 'HTML' not in javascript
    assert 'state.operationsInFlight' in javascript
    assert 'state.operationsGeneration' in javascript
    assert 'OPERATIONS_FINDING_LIMIT' in javascript
    assert 'Blob' in javascript
    for action in ('Approve', 'Reject', 'Execute', 'Retry', 'Cancel', 'Delete'):
        assert '>' + action + '<' not in html
