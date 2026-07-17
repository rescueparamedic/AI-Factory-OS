from __future__ import annotations

import csv
from copy import deepcopy
from datetime import datetime, timezone
from io import StringIO
import json
import re
from statistics import median
from typing import Any, Iterable, Mapping


MIN_COMPARE_SESSIONS = 2
MAX_COMPARE_SESSIONS = 5
ERROR_TEXT_LIMIT = 500
REPEATED_FAILURE_COUNT = 2
APPROVAL_WARNING_SECONDS = 30 * 60
APPROVAL_CRITICAL_SECONDS = 2 * 60 * 60
AGING_SECONDS = 30 * 60
STALE_SECONDS = 2 * 60 * 60
LONG_EVENT_GAP_SECONDS = 60 * 60

STAGES = ('Planning', 'Development', 'QA', 'Documentation', 'Approval', 'Release')
STAGE_ALIASES = {
    'plan': 'Planning', 'planned': 'Planning', 'planning': 'Planning',
    'assign': 'Planning', 'assigned': 'Planning',
    'develop': 'Development', 'developing': 'Development',
    'development': 'Development', 'qa': 'QA', 'qa_pending': 'QA',
    'test': 'QA', 'testing': 'QA', 'document': 'Documentation',
    'documenting': 'Documentation', 'documentation': 'Documentation',
    'approval': 'Approval', 'approval_pending': 'Approval',
    'approve': 'Approval', 'release': 'Release', 'done': 'Release',
    'completed': 'Release',
}

KPI_DEFINITIONS = {
    'discovered_session_count': 'All validated session IDs returned by discovery.',
    'selected_comparison_session_count': 'Unique validated sessions selected for this projection.',
    'status_counts': 'Selected sessions grouped by Running, Waiting, Completed, Failed, or Unavailable.',
    'average_elapsed_seconds': 'Mean of non-negative elapsed durations with valid created and end timestamps.',
    'median_elapsed_seconds': 'Median of the same available elapsed-duration denominator.',
    'worker_counts': 'Workers present in selected snapshots; failed workers have status Failed.',
    'pending_approval_count': 'Approval records whose status is PENDING in selected snapshots.',
    'total_evidence_count': 'Evidence metadata rows exposed by selected snapshots.',
    'progress_source_counts': 'Selected sessions grouped as explicit, lifecycle-derived, or unavailable progress.',
}


class OperationsAnalytics:
    '''Pure read-only analytics projection over RuntimeDashboard snapshots.'''

    def project(
        self, snapshots: Iterable[Mapping[str, Any]], *,
        discovered_session_count: int | None = None,
    ) -> dict[str, Any]:
        copied = [deepcopy(dict(item)) for item in snapshots]
        copied.sort(key=lambda item: str(item.get('session_id', '')))
        as_of = _projection_time(copied)
        comparisons = [self._comparison(item, as_of) for item in copied]
        stage_durations = {
            item['session_id']: _stage_durations(snapshot, as_of)
            for item, snapshot in zip(comparisons, copied)
        }
        approvals = {
            item['session_id']: _approval_analysis(snapshot, as_of)
            for item, snapshot in zip(comparisons, copied)
        }
        failures = {
            item['session_id']: _failure_analysis(snapshot)
            for item, snapshot in zip(comparisons, copied)
        }
        findings = []
        for comparison in comparisons:
            session_id = comparison['session_id']
            findings.extend(_findings(
                comparison, stage_durations[session_id],
                approvals[session_id], failures[session_id],
            ))
        findings.sort(key=_finding_key)
        unavailable = sorted({
            field
            for item in comparisons
            for field, value in item.items()
            if value is None or value == 'unavailable'
        })
        result = {
            'generated_at': _format_time(as_of),
            'snapshot_derived': True,
            'read_only': True,
            'selected_session_ids': [item['session_id'] for item in comparisons],
            'comparison_limits': {
                'minimum': MIN_COMPARE_SESSIONS, 'maximum': MAX_COMPARE_SESSIONS,
            },
            'kpis': _kpis(
                comparisons,
                len(copied) if discovered_session_count is None else discovered_session_count,
            ),
            'kpi_definitions': deepcopy(KPI_DEFINITIONS),
            'comparisons': comparisons,
            'stage_durations': stage_durations,
            'approval_delays': approvals,
            'failure_summaries': failures,
            'findings': findings,
            'known_unavailable_fields': unavailable,
            'thresholds': {
                'approval_warning_seconds': APPROVAL_WARNING_SECONDS,
                'approval_critical_seconds': APPROVAL_CRITICAL_SECONDS,
                'aging_seconds': AGING_SECONDS,
                'stale_seconds': STALE_SECONDS,
                'long_event_gap_seconds': LONG_EVENT_GAP_SECONDS,
                'repeated_failure_count': REPEATED_FAILURE_COUNT,
            },
        }
        return deepcopy(result)

    @staticmethod
    def _comparison(snapshot: Mapping[str, Any], as_of: datetime | None) -> dict[str, Any]:
        workers = _rows(snapshot.get('workers'))
        approvals = [row for row in _rows(snapshot.get('approval_queue')) if _pending(row)]
        timeline = _rows(snapshot.get('timeline'))
        evidence = _rows(snapshot.get('evidence'))
        progress = snapshot.get('progress') if isinstance(snapshot.get('progress'), Mapping) else {}
        status = _status(snapshot.get('runtime_status'))
        created = _parse_time(snapshot.get('created_at'))
        updated = _parse_time(snapshot.get('updated_at'))
        end = (
            updated if status in {'Completed', 'Failed'}
            else as_of if status in {'Running', 'Waiting'}
            else None
        )
        elapsed = _duration(created, end)
        repository = snapshot.get('repository') if isinstance(snapshot.get('repository'), Mapping) else {}
        return {
            'session_id': _text(snapshot.get('session_id'), 'unavailable', 128),
            'runtime_status': status,
            'current_stage': _text(snapshot.get('current_stage')),
            'current_task': _text(snapshot.get('current_task')),
            'current_worker': _text(snapshot.get('current_worker')),
            'created_at': _time_or_unavailable(created),
            'updated_at': _time_or_unavailable(updated),
            'elapsed_seconds': elapsed,
            'worker_count': len(workers),
            'completed_worker_count': sum(_status(row.get('status')) == 'Completed' for row in workers),
            'failed_worker_count': sum(_status(row.get('status')) == 'Failed' for row in workers),
            'pending_approval_count': len(approvals),
            'timeline_event_count': len(timeline),
            'evidence_count': len(evidence),
            'overall_progress': _number(progress.get('value'), 0, 100),
            'progress_source': _progress_source(progress.get('source')),
            'repository_branch': _text(repository.get('current_branch')),
            'repository_working_tree': _text(repository.get('working_tree')),
            'staleness': _staleness(status, updated, as_of),
            'error': _text(snapshot.get('error')) if status == 'Unavailable' else '',
        }


def report_csv(report: Mapping[str, Any]) -> str:
    '''Return a safely escaped CSV representation of exposed comparison data.'''
    output = StringIO(newline='')
    fields = [
        'record_type', 'key', 'value', 'provenance', 'session_id',
        'runtime_status', 'current_stage', 'current_task',
        'current_worker', 'created_at', 'updated_at', 'elapsed_seconds',
        'worker_count', 'completed_worker_count', 'failed_worker_count',
        'pending_approval_count', 'timeline_event_count', 'evidence_count',
        'overall_progress', 'progress_source', 'repository_branch',
        'repository_working_tree', 'staleness', 'error',
    ]
    writer = csv.DictWriter(output, fieldnames=fields, extrasaction='ignore')
    writer.writeheader()
    metadata = {
        'generated_at': report.get('generated_at', 'unavailable'),
        'selected_session_ids': json.dumps(report.get('selected_session_ids', []), ensure_ascii=False),
        'known_unavailable_fields': json.dumps(report.get('known_unavailable_fields', []), ensure_ascii=False),
    }
    for key, value in metadata.items():
        writer.writerow(_csv_safe({'record_type': 'metadata', 'key': key, 'value': value}))
    definitions = report.get('kpi_definitions', {})
    if isinstance(definitions, Mapping):
        for key in sorted(definitions):
            writer.writerow(_csv_safe({
                'record_type': 'kpi_definition', 'key': key,
                'value': definitions[key], 'provenance': 'snapshot_derived',
            }))
    for row in _rows(report.get('comparisons')):
        safe = {'record_type': 'comparison', **dict(row)}
        if isinstance(safe.get('staleness'), Mapping):
            safe['staleness'] = safe['staleness'].get('state', 'unavailable')
        writer.writerow(_csv_safe(safe))
    for finding in _rows(report.get('findings')):
        writer.writerow(_csv_safe({
            'record_type': 'finding', 'key': finding.get('finding_type'),
            'value': finding.get('reason'),
            'provenance': finding.get('confidence_provenance'),
            'session_id': finding.get('session_id'),
        }))
    return output.getvalue()


def _csv_safe(row: Mapping[str, Any]) -> dict[str, Any]:
    result = {}
    for key, value in row.items():
        if isinstance(value, str) and value.startswith(('=', '+', '-', '@')):
            value = chr(39) + value
        result[key] = value
    return result


def export_filename(session_ids: Iterable[str], extension: str) -> str:
    safe_ids = [re.sub(r'[^A-Za-z0-9_-]+', '-', str(item)).strip('-_')[:40] for item in session_ids]
    stem = 'afde-operations-' + '-'.join(item for item in safe_ids if item)
    return (stem[:180].rstrip('-') or 'afde-operations') + '.' + ('csv' if extension == 'csv' else 'json')


def _kpis(comparisons: list[Mapping[str, Any]], discovered: int) -> dict[str, Any]:
    elapsed = [item['elapsed_seconds'] for item in comparisons if item.get('elapsed_seconds') is not None]
    statuses = {name: 0 for name in ('Running', 'Waiting', 'Completed', 'Failed', 'Unavailable')}
    for item in comparisons:
        statuses[_status(item.get('runtime_status'))] += 1
    sources = {'explicit': 0, 'lifecycle_derived': 0, 'unavailable': 0}
    for item in comparisons:
        sources[item.get('progress_source', 'unavailable')] += 1
    return {
        'discovered_session_count': discovered,
        'selected_comparison_session_count': len(comparisons),
        'running_session_count': statuses['Running'],
        'waiting_session_count': statuses['Waiting'],
        'completed_session_count': statuses['Completed'],
        'failed_session_count': statuses['Failed'],
        'unavailable_session_count': statuses['Unavailable'],
        'average_elapsed_seconds': sum(elapsed) / len(elapsed) if elapsed else None,
        'median_elapsed_seconds': median(elapsed) if elapsed else None,
        'elapsed_duration_denominator': len(elapsed),
        'total_worker_count': sum(int(item.get('worker_count', 0)) for item in comparisons),
        'failed_worker_count': sum(int(item.get('failed_worker_count', 0)) for item in comparisons),
        'pending_approval_count': sum(int(item.get('pending_approval_count', 0)) for item in comparisons),
        'total_evidence_count': sum(int(item.get('evidence_count', 0)) for item in comparisons),
        'explicit_progress_count': sources['explicit'],
        'lifecycle_derived_progress_count': sources['lifecycle_derived'],
        'unavailable_progress_count': sources['unavailable'],
    }


def _stage_durations(snapshot: Mapping[str, Any], as_of: datetime | None) -> list[dict[str, Any]]:
    events = []
    measured: dict[str, tuple[float, list[str]]] = {}
    for index, row in enumerate(_rows(snapshot.get('timeline'))):
        timestamp = _parse_time(row.get('timestamp'))
        stage = _normalize_stage(row.get('stage') or row.get('event') or row.get('detail'))
        duration = _number(row.get('duration_seconds'), 0)
        if stage and duration is not None:
            measured[stage] = (duration, ['timeline.duration_seconds', f'timeline[{index}].stage'])
        if timestamp and stage:
            events.append((timestamp, stage, index))
    events.sort(key=lambda item: (item[0], item[2]))
    starts: dict[str, datetime] = {}
    inferred: dict[str, tuple[float, list[str]]] = {}
    for timestamp, stage, index in events:
        if stage not in starts:
            starts[stage] = timestamp
        for open_stage, started in list(starts.items()):
            if open_stage != stage and open_stage not in inferred:
                duration = _duration(started, timestamp)
                if duration is not None:
                    inferred[open_stage] = (duration, [f'timeline[{index}].timestamp', 'stage transition'])
                    starts.pop(open_stage, None)
    active = _normalize_stage(snapshot.get('current_stage'))
    status = _status(snapshot.get('runtime_status'))
    if active and active in starts and status in {'Running', 'Waiting'}:
        duration = _duration(starts[active], as_of)
        if duration is not None:
            inferred[active] = (duration, ['active stage start', 'snapshot_timestamp'])
    result = []
    for stage in STAGES:
        if stage in measured:
            duration, evidence = measured[stage]
            provenance = 'measured'
        elif stage in inferred:
            duration, evidence = inferred[stage]
            provenance = 'inferred'
        else:
            duration, evidence, provenance = None, [], 'unavailable'
        result.append({'stage': stage, 'duration_seconds': duration, 'provenance': provenance, 'evidence_fields': evidence})
    return result


def _approval_analysis(snapshot: Mapping[str, Any], as_of: datetime | None) -> dict[str, Any]:
    pending = [row for row in _rows(snapshot.get('approval_queue')) if _pending(row)]
    rows = []
    ages = []
    for row in pending:
        requested = _parse_time(row.get('requested_at') or row.get('created_at'))
        age = _duration(requested, as_of)
        if age is not None:
            ages.append(age)
        rows.append({
            'approval_id': _text(row.get('approval_id')),
            'age_seconds': age,
            'requested_at': _time_or_unavailable(requested),
            'actor': _text(row.get('actor') or row.get('worker')),
            'risk': _text(row.get('risk') or row.get('permission_level')),
            'action': _text(row.get('action')),
        })
    return {
        'pending_count': len(pending),
        'oldest_pending_age_seconds': max(ages) if ages else None,
        'median_pending_age_seconds': median(ages) if ages else None,
        'available_age_denominator': len(ages),
        'pending': rows,
    }


def _failure_analysis(snapshot: Mapping[str, Any]) -> dict[str, Any]:
    workers = [row for row in _rows(snapshot.get('workers')) if _status(row.get('status')) == 'Failed']
    events = []
    categories: dict[str, int] = {}
    evidence_ids = [_text(row.get('identifier') or row.get('path')) for row in _rows(snapshot.get('evidence'))]
    for row in _rows(snapshot.get('timeline')):
        combined = ' '.join(_text(row.get(field), '') for field in ('event', 'status', 'category', 'error', 'message', 'detail'))
        if not re.search(r'\b(fail(?:ed|ure)?|error|exception|blocked|cancelled)\b', combined, re.I):
            continue
        category = _failure_category(row, combined)
        categories[category] = categories.get(category, 0) + 1
        events.append({
            'timestamp': _text(row.get('timestamp')),
            'worker': _text(row.get('worker') or row.get('actor')),
            'task': _text(row.get('task') or row.get('task_id')),
            'stage': _text(row.get('stage')),
            'code': _text(row.get('error_code') or row.get('code')),
            'category': category,
            'message': _text(row.get('message') or row.get('error') or row.get('detail') or row.get('summary'), '', ERROR_TEXT_LIMIT),
            'provenance': 'reported error',
        })
    events.sort(key=lambda item: item['timestamp'])
    repeated = [{'category': key, 'count': value} for key, value in sorted(categories.items()) if value >= REPEATED_FAILURE_COUNT]
    return {
        'failed_worker_count': len(workers),
        'failure_event_count': len(events),
        'most_recent_failure': events[-1] if events else None,
        'repeated_categories': repeated,
        'related_evidence_identifiers': [item for item in evidence_ids if item != 'unavailable'],
        'interpretation': 'Reported errors and correlated metadata only; root cause unavailable.',
    }


def _findings(comparison, stages, approvals, failures) -> list[dict[str, Any]]:
    session_id = comparison['session_id']
    findings = []
    available = [row for row in stages if row['duration_seconds'] is not None]
    if available:
        longest = sorted(available, key=lambda row: (-row['duration_seconds'], STAGES.index(row['stage'])))[0]
        findings.append(_finding(
            'longest_stage', 'info', session_id,
            f"{longest['stage']} is the longest available stage duration ({_approx(longest['duration_seconds'])}).",
            longest['provenance'], longest['evidence_fields'], stage=longest['stage'], duration=longest['duration_seconds'],
        ))
    if comparison['runtime_status'] == 'Waiting' and approvals['pending_count']:
        findings.append(_finding(
            'approval_wait', 'warning', session_id,
            'Runtime is Waiting with one or more pending approvals.', 'measured',
            ['runtime_status', 'approval_queue.status'], stage='Approval',
        ))
    oldest = approvals['oldest_pending_age_seconds']
    if oldest is not None and oldest >= APPROVAL_WARNING_SECONDS:
        severity = 'critical' if oldest >= APPROVAL_CRITICAL_SECONDS else 'warning'
        findings.append(_finding(
            'approval_delay', severity, session_id,
            f'Oldest pending approval age is approximately {_approx(oldest)}.', 'measured',
            ['approval_queue.requested_at', 'snapshot_timestamp'], stage='Approval', duration=oldest,
        ))
    if failures['failed_worker_count']:
        findings.append(_finding(
            'failed_workers', 'critical', session_id,
            f"{failures['failed_worker_count']} worker(s) report Failed status; root cause is unavailable.",
            'measured', ['workers.status'],
        ))
    for repeated in failures['repeated_categories']:
        findings.append(_finding(
            'repeated_failure', 'warning', session_id,
            f"Failure category {repeated['category']} appears {repeated['count']} times; this is a repeated signal, not a root-cause claim.",
            'heuristic', ['timeline error/category/message'],
        ))
    stale = comparison['staleness']
    if stale['state'] in {'aging', 'stale'}:
        findings.append(_finding(
            'stale_session', 'warning' if stale['state'] == 'aging' else 'critical', session_id,
            stale['reason'], 'heuristic', ['runtime_status', 'updated_at', 'snapshot_timestamp'],
            duration=stale['age_seconds'],
        ))
    return findings


def _finding(kind, severity, session_id, reason, provenance, evidence, *, stage=None, duration=None):
    return {
        'finding_type': kind, 'severity': severity, 'session_id': session_id,
        'stage': stage, 'worker': None, 'approval_id': None,
        'duration_seconds': duration, 'timestamp': None,
        'evidence_fields': list(evidence), 'reason': reason,
        'confidence_provenance': provenance, 'advisory_only': True,
    }


def _finding_key(item):
    rank = {'critical': 0, 'warning': 1, 'info': 2}
    return (rank.get(item['severity'], 3), item['session_id'], item['finding_type'], item.get('stage') or '')


def _staleness(status, updated, as_of):
    if status in {'Completed', 'Failed'}:
        return {'state': 'fresh', 'age_seconds': None, 'reason': 'Terminal sessions are excluded from active staleness warnings.'}
    age = _duration(updated, as_of)
    if age is None:
        return {'state': 'unavailable', 'age_seconds': None, 'reason': 'A valid updated timestamp is unavailable.'}
    state = 'stale' if age >= STALE_SECONDS else 'aging' if age >= AGING_SECONDS else 'fresh'
    return {'state': state, 'age_seconds': age, 'reason': f'Active session update age is approximately {_approx(age)}; aging begins at {_approx(AGING_SECONDS)} and stale at {_approx(STALE_SECONDS)}.'}


def _projection_time(snapshots):
    values = [_parse_time(item.get('snapshot_timestamp')) for item in snapshots]
    available = [item for item in values if item is not None]
    return max(available) if available else None


def _parse_time(value):
    if not isinstance(value, str) or not value.strip() or value.lower() == 'unavailable':
        return None
    normalized = value.strip().replace('Z', '+00:00')
    try:
        parsed = datetime.fromisoformat(normalized)
    except ValueError:
        return None
    if parsed.tzinfo is None:
        return None
    return parsed.astimezone(timezone.utc)


def _duration(start, end):
    if start is None or end is None:
        return None
    value = (end - start).total_seconds()
    return value if value >= 0 else None


def _normalize_stage(value):
    text = re.sub(r'[^a-z0-9]+', '_', _text(value, '').lower()).strip('_')
    for alias in sorted(STAGE_ALIASES, key=len, reverse=True):
        if alias in text:
            return STAGE_ALIASES[alias]
    return None


def _failure_category(row, combined):
    explicit = _text(row.get('category') or row.get('error_code') or row.get('code'), '').lower()
    if explicit:
        return re.sub(r'[^a-z0-9]+', '_', explicit).strip('_')[:80] or 'reported_failure'
    match = re.search(r'\b(exception|timeout|permission|validation|network|failed?|error|blocked|cancelled)\b', combined, re.I)
    return match.group(1).lower() if match else 'reported_failure'


def _status(value):
    text = _text(value, 'Unavailable').lower()
    return {'running': 'Running', 'waiting': 'Waiting', 'completed': 'Completed', 'failed': 'Failed'}.get(text, 'Unavailable')


def _progress_source(value):
    text = _text(value, 'unavailable').lower()
    if text.startswith('explicit'):
        return 'explicit'
    return 'lifecycle_derived' if text == 'lifecycle_derived' else 'unavailable'


def _pending(row):
    return _text(row.get('status'), 'PENDING').upper() == 'PENDING'


def _rows(value):
    if not isinstance(value, list):
        return []
    return [dict(item) for item in value if isinstance(item, Mapping)]


def _number(value, minimum=None, maximum=None):
    if isinstance(value, bool) or not isinstance(value, (int, float)):
        return None
    result = float(value)
    if minimum is not None and result < minimum or maximum is not None and result > maximum:
        return None
    return int(result) if result.is_integer() else result


def _text(value, default='unavailable', limit=ERROR_TEXT_LIMIT):
    if value is None:
        return default
    text = re.sub(r'[\x00-\x08\x0b\x0c\x0e-\x1f\x7f]', ' ', str(value)).strip()
    return text[:limit] if text else default


def _time_or_unavailable(value):
    return _format_time(value) if value else 'unavailable'


def _format_time(value):
    return value.isoformat().replace('+00:00', 'Z') if value else 'unavailable'


def _approx(seconds):
    if seconds < 60:
        return f'{round(seconds)} seconds'
    if seconds < 3600:
        return f'{round(seconds / 60)} minutes'
    return f'{round(seconds / 3600, 1)} hours'
