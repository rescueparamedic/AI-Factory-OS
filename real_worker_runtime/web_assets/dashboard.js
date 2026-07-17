'use strict';

const byId = (id) => document.getElementById(id);
const STATUS_VALUES = new Set(['Running', 'Waiting', 'Completed', 'Failed']);
const LIFECYCLE_NAMES = ['Development', 'QA', 'Documentation', 'Approval', 'Release'];
const TIMELINE_LIMIT = 50;
const OPERATIONS_FINDING_LIMIT = 100;
const SESSION_REFRESH_INTERVAL = 30000;

function safeText(value, fallback = 'unavailable') {
  if (value === null || value === undefined || value === '') return fallback;
  if (typeof value === 'object') return fallback;
  return String(value);
}

function detailText(value) {
  if (value === null || value === undefined || value === '') return 'unavailable';
  if (typeof value === 'object') {
    try { return JSON.stringify(value); } catch (error) { return 'unavailable'; }
  }
  return String(value);
}

function safeRows(value) {
  return Array.isArray(value)
    ? value.filter((item) => item && typeof item === 'object' && !Array.isArray(item)).slice()
    : [];
}

function replaceChildren(node) {
  while (node.firstChild) node.removeChild(node.firstChild);
}

function metric(container, label, value) {
  const term = document.createElement('dt');
  const detail = document.createElement('dd');
  term.textContent = label;
  detail.textContent = safeText(value);
  container.append(term, detail);
}

function emptyState(message) {
  const item = document.createElement('div');
  item.className = 'empty-state';
  item.textContent = message;
  return item;
}

function normalizedStatus(value) {
  const status = safeText(value, 'Waiting');
  return STATUS_VALUES.has(status) ? status : 'Waiting';
}

function statusClass(value) {
  return 'status-' + normalizedStatus(value).toLowerCase();
}

function applyStatusBadge(node, value) {
  const status = normalizedStatus(value);
  node.textContent = status;
  node.className = 'status-badge ' + statusClass(status);
}

function normalizeProgress(value) {
  if (typeof value === 'boolean') return null;
  const number = Number(value);
  return Number.isFinite(number) && number >= 0 && number <= 100 ? number : null;
}

function progressSourceLabel(source) {
  const labels = {
    explicit_pipeline: 'explicit pipeline value',
    explicit_session: 'explicit session value',
    lifecycle_derived: 'lifecycle-derived estimate',
    unavailable: 'unavailable',
  };
  return labels[source] || 'unavailable';
}

function workerSource(worker, runtimeProgress) {
  if (worker.progress_source) return safeText(worker.progress_source, 'unavailable');
  if (worker.current_task && worker.current_task !== '-') {
    return safeText(runtimeProgress.source, 'unavailable');
  }
  return normalizeProgress(worker.progress) === null ? 'unavailable' : 'lifecycle_derived';
}

function updateProgress(track, bar, value, source) {
  const progress = normalizeProgress(value);
  const sourceLabel = progressSourceLabel(source);
  bar.style.width = progress === null ? '0%' : String(progress) + '%';
  if (progress === null) {
    track.removeAttribute('aria-valuenow');
    track.setAttribute('aria-valuetext', 'Progress unavailable');
    return 'Progress unavailable · source: ' + sourceLabel;
  }
  track.setAttribute('aria-valuenow', String(progress));
  track.setAttribute('aria-valuetext', String(progress) + ' percent · ' + sourceLabel);
  return String(progress) + '% · source: ' + sourceLabel;
}

function collectText(value, output = []) {
  if (value === null || value === undefined) return output;
  if (Array.isArray(value)) {
    value.forEach((item) => collectText(item, output));
  } else if (typeof value === 'object') {
    Object.values(value).forEach((item) => collectText(item, output));
  } else {
    output.push(String(value));
  }
  return output;
}

function containsText(value, query) {
  if (!query) return true;
  return collectText(value).join(' ').toLocaleLowerCase().includes(query.toLocaleLowerCase());
}

function inputValue(id) {
  return safeText(byId(id).value, '').trim().toLocaleLowerCase();
}

function stableSort(rows, valueOf, direction = 'asc') {
  return rows.map((row, index) => ({row, index})).sort((left, right) => {
    const a = valueOf(left.row);
    const b = valueOf(right.row);
    const missingA = a === null || a === undefined || a === '';
    const missingB = b === null || b === undefined || b === '';
    if (missingA !== missingB) return missingA ? 1 : -1;
    if (missingA && missingB) return left.index - right.index;
    const comparison = typeof a === 'number' && typeof b === 'number'
      ? a - b : String(a).localeCompare(String(b));
    return comparison === 0 ? left.index - right.index
      : comparison * (direction === 'desc' ? -1 : 1);
  }).map((item) => item.row);
}

function appendMeta(container, label, value) {
  if (value === null || value === undefined || value === '') return;
  const line = document.createElement('p');
  line.className = 'item-meta';
  line.textContent = label + ': ' + safeText(value);
  container.appendChild(line);
}

let detailInvoker = null;

function openDetail(title, value, invoker) {
  const dialog = byId('detail-dialog');
  const content = byId('detail-content');
  detailInvoker = invoker || document.activeElement;
  byId('detail-title').textContent = title;
  replaceChildren(content);
  const source = value && typeof value === 'object' ? value : {value};
  Object.keys(source).sort().forEach((key) => metric(content, key.replaceAll('_', ' '), detailText(source[key])));
  dialog.showModal();
  byId('detail-close').focus();
}

function inspectButton(title, value) {
  const button = document.createElement('button');
  button.type = 'button';
  button.className = 'inspect-button';
  button.textContent = 'Inspect details';
  button.addEventListener('click', () => openDetail(title, value, button));
  return button;
}

function renderRuntime(snapshot, lastSuccess) {
  applyStatusBadge(byId('runtime-status'), snapshot.runtime_status);
  const summary = byId('runtime-summary');
  replaceChildren(summary);
  metric(summary, 'Session ID', snapshot.session_id);
  metric(summary, 'Runtime status', normalizedStatus(snapshot.runtime_status));
  metric(summary, 'Current stage', snapshot.current_stage);
  metric(summary, 'Created', snapshot.created_at);
  metric(summary, 'Updated', snapshot.updated_at);
  metric(summary, 'Snapshot time', snapshot.snapshot_timestamp);
  metric(summary, 'Last browser refresh', lastSuccess);
  const current = byId('current-operation');
  replaceChildren(current);
  metric(current, 'Current task', snapshot.current_task);
  metric(current, 'Current worker', snapshot.current_worker);
  metric(current, 'Current stage', snapshot.current_stage);
  const progress = snapshot.progress && typeof snapshot.progress === 'object' ? snapshot.progress : {};
  byId('progress-source').textContent = updateProgress(
    byId('runtime-progress-track'), byId('runtime-progress'), progress.value,
    safeText(progress.source, 'unavailable'),
  );
}

function renderStatistics(snapshot) {
  const target = byId('runtime-statistics');
  replaceChildren(target);
  const workers = safeRows(snapshot.workers);
  const approvals = safeRows(snapshot.approval_queue);
  const progress = snapshot.progress && typeof snapshot.progress === 'object' ? snapshot.progress : {};
  const sources = workers.map((worker) => workerSource(worker, progress));
  const statistics = {
    'Total workers': workers.length,
    'Running workers': workers.filter((row) => row.status === 'Running').length,
    'Completed workers': workers.filter((row) => row.status === 'Completed').length,
    'Failed workers': workers.filter((row) => row.status === 'Failed').length,
    'Pending approvals': approvals.filter((row) => safeText(row.status, '').toLowerCase() === 'pending').length,
    'Timeline events': safeRows(snapshot.timeline).length,
    'History events': safeRows(snapshot.event_history).length,
    'Error events': safeRows(snapshot.error_events).length,
    'Evidence items': safeRows(snapshot.evidence).length,
    'Explicit progress': sources.filter((source) => source.startsWith('explicit_')).length,
    'Derived progress': sources.filter((source) => source === 'lifecycle_derived').length,
    'Unavailable progress': sources.filter((source) => source === 'unavailable').length,
  };
  Object.entries(statistics).forEach(([label, value]) => metric(target, label, value));
}

function renderWorkers(snapshot, globalQuery) {
  const target = byId('workers');
  replaceChildren(target);
  const progress = snapshot.progress && typeof snapshot.progress === 'object' ? snapshot.progress : {};
  const status = inputValue('worker-status-filter');
  const source = inputValue('worker-source-filter');
  const text = inputValue('worker-text-filter');
  let rows = safeRows(snapshot.workers).filter((worker) => {
    const actualSource = workerSource(worker, progress).toLowerCase();
    return (!status || safeText(worker.status, '').toLowerCase() === status)
      && (!source || actualSource === source)
      && (!text || containsText([worker.worker, worker.role], text))
      && containsText(worker, globalQuery);
  });
  const sort = byId('worker-sort').value;
  if (sort === 'name') rows = stableSort(rows, (row) => safeText(row.worker, ''));
  if (sort === 'progress_desc') rows = stableSort(rows, (row) => normalizeProgress(row.progress), 'desc');
  if (sort === 'progress_asc') rows = stableSort(rows, (row) => normalizeProgress(row.progress));
  if (!rows.length) { target.appendChild(emptyState('No workers match the active filters')); return 0; }
  rows.forEach((worker) => {
    const item = document.createElement('article');
    const heading = document.createElement('div');
    const name = document.createElement('h3');
    const badge = document.createElement('span');
    const task = document.createElement('p');
    const track = document.createElement('div');
    const bar = document.createElement('div');
    const note = document.createElement('p');
    item.className = 'worker-item'; heading.className = 'worker-heading';
    name.textContent = safeText(worker.worker, 'Unknown worker');
    applyStatusBadge(badge, worker.status);
    task.className = 'item-meta';
    task.textContent = 'Role: ' + safeText(worker.role || worker.worker) + ' · Task: ' + safeText(worker.current_task, 'none');
    track.className = 'progress-track compact'; track.setAttribute('role', 'progressbar');
    track.setAttribute('aria-label', name.textContent + ' progress');
    track.setAttribute('aria-valuemin', '0'); track.setAttribute('aria-valuemax', '100');
    bar.className = 'progress-value'; note.className = 'card-note';
    note.textContent = updateProgress(track, bar, worker.progress, workerSource(worker, progress));
    heading.append(name, badge); track.appendChild(bar);
    item.append(heading, task, track, note, inspectButton('Worker detail', worker));
    target.appendChild(item);
  });
  return rows.length;
}

function renderLifecycle(snapshot) {
  const target = byId('lifecycle'); replaceChildren(target);
  const workers = safeRows(snapshot.workers);
  LIFECYCLE_NAMES.forEach((name, index) => {
    const item = document.createElement('li'); const label = document.createElement('span');
    const badge = document.createElement('span'); const field = name.toLowerCase() + '_status';
    label.textContent = name; applyStatusBadge(badge, snapshot[field] || (workers[index] && workers[index].status));
    item.append(label, badge); target.appendChild(item);
  });
}

function syncApprovalStatuses(rows) {
  const selector = byId('approval-status-filter');
  const selected = selector.value || 'all';
  const statuses = Array.from(new Set(
    safeRows(rows).map((row) => safeText(row.status, '').toLowerCase()).filter(Boolean),
  )).sort();
  replaceChildren(selector);
  const all = document.createElement('option');
  all.value = 'all'; all.textContent = 'All present statuses'; selector.appendChild(all);
  statuses.forEach((status) => {
    const option = document.createElement('option'); option.value = status;
    option.textContent = status.charAt(0).toUpperCase() + status.slice(1);
    selector.appendChild(option);
  });
  selector.value = statuses.includes(selected) ? selected : 'all';
}

function renderApprovals(snapshot, globalQuery) {
  const target = byId('approval-queue'); replaceChildren(target);
  syncApprovalStatuses(snapshot.approval_queue);
  const status = inputValue('approval-status-filter');
  let rows = safeRows(snapshot.approval_queue).filter((row) => (
    (status === 'all' || safeText(row.status, '').toLowerCase() === status)
    && containsText(row, globalQuery)
  ));
  if (byId('approval-sort').value === 'risk') rows = stableSort(rows, (row) => row.risk || row.permission_level || '');
  if (!rows.length) { target.appendChild(emptyState('No approvals match the active filters')); return 0; }
  rows.forEach((row) => {
    const item = document.createElement('article'); const heading = document.createElement('div');
    const title = document.createElement('h3'); const badge = document.createElement('span');
    item.className = 'stack-item approval-pending'; heading.className = 'worker-heading';
    title.textContent = safeText(row.approval_id, 'Approval ID unavailable');
    applyStatusBadge(badge, row.status === 'PENDING' ? 'Waiting' : row.status);
    heading.append(title, badge); item.appendChild(heading);
    appendMeta(item, 'Action', row.action); appendMeta(item, 'Actor / worker', row.actor || row.worker);
    appendMeta(item, 'Reason', row.reason); appendMeta(item, 'Risk / permission', row.risk || row.permission_level);
    appendMeta(item, 'Requested', row.requested_at); appendMeta(item, 'Approval status', row.status);
    item.appendChild(inspectButton('Approval detail', row)); target.appendChild(item);
  });
  return rows.length;
}

function fieldMatches(row, field, query) {
  return !query || containsText(row[field], query);
}

function renderTimeline(snapshot, globalQuery) {
  const target = byId('timeline'); replaceChildren(target);
  const event = inputValue('timeline-event-filter'); const actor = inputValue('timeline-actor-filter');
  const task = inputValue('timeline-task-filter'); const status = inputValue('timeline-status-filter');
  const text = inputValue('timeline-text-filter');
  let rows = safeRows(snapshot.timeline).filter((row) => (
    containsText([row.event, row.event_type], event) && containsText([row.worker, row.actor], actor)
    && containsText([row.task, row.task_id], task) && fieldMatches(row, 'status', status)
    && containsText(row, text) && containsText(row, globalQuery)
  ));
  rows = stableSort(rows, (row) => row.timestamp || '', byId('timeline-sort').value);
  rows = rows.slice(0, TIMELINE_LIMIT);
  if (!rows.length) { target.appendChild(emptyState('No timeline events match the active filters')); return 0; }
  rows.forEach((row) => {
    const item = document.createElement('li'); const title = document.createElement('h3');
    if (safeText(row.event_type, '') === 'ERROR_OCCURRED') item.className = 'severity-critical';
    title.textContent = safeText(row.event_type || row.event || row.type, 'Runtime event'); item.appendChild(title);
    appendMeta(item, 'Event ID', row.event_id);
    appendMeta(item, 'Source event', row.event);
    appendMeta(item, 'Time', row.timestamp); appendMeta(item, 'Actor', row.worker || row.actor);
    appendMeta(item, 'Task', row.task || row.task_id); appendMeta(item, 'Status', row.status);
    appendMeta(item, 'Summary', row.summary || row.detail);
    appendMeta(item, 'Metadata', detailText(row.metadata));
    item.appendChild(inspectButton('Timeline event detail', row)); target.appendChild(item);
  });
  return rows.length;
}

function renderEvidence(snapshot, globalQuery) {
  const target = byId('evidence'); replaceChildren(target);
  const type = inputValue('evidence-type-filter'); const availability = inputValue('evidence-availability-filter');
  const text = inputValue('evidence-text-filter');
  let rows = safeRows(snapshot.evidence).filter((row) => (
    fieldMatches(row, 'type', type)
    && (!availability || safeText(row.availability, 'available').toLowerCase() === availability)
    && containsText([row.name, row.label, row.identifier, row.path], text)
    && containsText(row, globalQuery)
  ));
  const sort = byId('evidence-sort').value;
  if (sort.startsWith('timestamp_')) rows = stableSort(rows, (row) => row.timestamp || '', sort.endsWith('desc') ? 'desc' : 'asc');
  if (!rows.length) { target.appendChild(emptyState('No evidence metadata matches the active filters')); return 0; }
  rows.forEach((row) => {
    const item = document.createElement('article'); const title = document.createElement('h3');
    item.className = 'stack-item'; title.textContent = safeText(row.name || row.label || row.type, 'Evidence artifact');
    item.appendChild(title); appendMeta(item, 'Type', row.type); appendMeta(item, 'Identifier', row.identifier || row.path);
    appendMeta(item, 'Timestamp', row.timestamp); appendMeta(item, 'Availability', row.availability || 'available');
    item.appendChild(inspectButton('Evidence metadata detail', row)); target.appendChild(item);
  });
  return rows.length;
}

function renderRepository(snapshot, globalQuery) {
  const target = byId('repository'); replaceChildren(target);
  const repository = snapshot.repository && typeof snapshot.repository === 'object' ? snapshot.repository : {};
  if (!containsText(repository, globalQuery)) { target.appendChild(emptyState('Repository metadata does not match search')); return 0; }
  const latest = safeText(repository.latest_commit); const pieces = latest === 'unavailable' ? [] : latest.split(' ');
  metric(target, 'Availability', repository.availability || (repository.current_branch ? 'available' : 'unavailable'));
  metric(target, 'Branch', repository.current_branch); metric(target, 'Working tree', repository.working_tree);
  metric(target, 'Commit hash', repository.latest_commit_hash || pieces[0]);
  metric(target, 'Commit summary', repository.latest_commit_summary || pieces.slice(1).join(' '));
  if (repository.error) metric(target, 'Error', repository.error);
  return 1;
}

function renderSnapshot(snapshot, lastSuccess) {
  const safeSnapshot = snapshot && typeof snapshot === 'object' ? snapshot : {};
  const query = inputValue('global-search');
  renderRuntime(safeSnapshot, lastSuccess); renderStatistics(safeSnapshot); renderLifecycle(safeSnapshot);
  const count = renderWorkers(safeSnapshot, query) + renderApprovals(safeSnapshot, query)
    + renderTimeline(safeSnapshot, query) + renderEvidence(safeSnapshot, query)
    + renderRepository(safeSnapshot, query);
  byId('result-status').textContent = count
    ? String(count) + ' matching inspection items shown'
    : 'No results match the active search and filters';
}

function formatDuration(value) {
  const seconds = Number(value);
  if (!Number.isFinite(seconds) || seconds < 0) return 'unavailable';
  if (seconds < 60) return String(Math.round(seconds)) + ' seconds';
  if (seconds < 3600) return String(Math.round(seconds / 60)) + ' minutes';
  return String(Math.round((seconds / 3600) * 10) / 10) + ' hours';
}

function tableCell(row, value) {
  const cell = document.createElement('td');
  cell.textContent = safeText(value);
  row.appendChild(cell);
}

function syncFindingOptions(id, values) {
  const selector = byId(id); const previous = selector.value;
  replaceChildren(selector);
  const all = document.createElement('option'); all.value = ''; all.textContent = 'All'; selector.appendChild(all);
  Array.from(new Set(values.filter(Boolean))).sort().forEach((value) => {
    const option = document.createElement('option'); option.value = value; option.textContent = value;
    selector.appendChild(option);
  });
  selector.value = Array.from(selector.options).some((option) => option.value === previous) ? previous : '';
}

function renderFindings(operations) {
  const source = safeRows(operations.findings);
  syncFindingOptions('finding-session-filter', source.map((row) => safeText(row.session_id, '')));
  syncFindingOptions('finding-type-filter', source.map((row) => safeText(row.finding_type, '')));
  syncFindingOptions('finding-stage-filter', source.map((row) => safeText(row.stage, '')));
  const session = inputValue('finding-session-filter'); const severity = inputValue('finding-severity-filter');
  const type = inputValue('finding-type-filter'); const stage = inputValue('finding-stage-filter');
  const query = inputValue('finding-text-filter'); const sort = byId('finding-sort').value;
  let rows = source.filter((row) => (
    (!session || safeText(row.session_id, '').toLowerCase() === session)
    && (!severity || safeText(row.severity, '').toLowerCase() === severity)
    && (!type || safeText(row.finding_type, '').toLowerCase() === type)
    && (!stage || safeText(row.stage, '').toLowerCase() === stage)
    && containsText(row, query)
  ));
  const severityRank = {critical: 3, warning: 2, info: 1};
  if (sort === 'duration') rows = stableSort(rows, (row) => Number(row.duration_seconds), 'desc');
  else if (sort === 'timestamp') rows = stableSort(rows, (row) => row.timestamp || '', 'desc');
  else rows = stableSort(rows, (row) => severityRank[safeText(row.severity, '').toLowerCase()] || 0, 'desc');
  rows = rows.slice(0, OPERATIONS_FINDING_LIMIT);
  const target = byId('bottleneck-findings'); replaceChildren(target);
  if (!rows.length) { target.appendChild(emptyState('No findings match the active filters')); return 0; }
  rows.forEach((finding) => {
    const item = document.createElement('article'); const title = document.createElement('h4');
    const severityValue = safeText(finding.severity, 'info').toLowerCase();
    item.className = 'stack-item severity-' + severityValue;
    title.textContent = safeText(finding.finding_type, 'Finding') + ' · ' + severityValue;
    item.appendChild(title); appendMeta(item, 'Session', finding.session_id); appendMeta(item, 'Stage', finding.stage);
    appendMeta(item, 'Duration', formatDuration(finding.duration_seconds)); appendMeta(item, 'Reason', finding.reason);
    appendMeta(item, 'Provenance', finding.confidence_provenance);
    appendMeta(item, 'Evidence fields', Array.isArray(finding.evidence_fields) ? finding.evidence_fields.join(', ') : 'unavailable');
    item.appendChild(inspectButton('Operations finding detail', finding)); target.appendChild(item);
  });
  return rows.length;
}

function renderOperations(operations) {
  const safe = operations && typeof operations === 'object' ? operations : {};
  const kpis = safe.kpis && typeof safe.kpis === 'object' ? safe.kpis : {};
  const kpiTarget = byId('operations-kpis'); replaceChildren(kpiTarget);
  [
    ['Discovered sessions', kpis.discovered_session_count], ['Selected sessions', kpis.selected_comparison_session_count],
    ['Running', kpis.running_session_count], ['Waiting', kpis.waiting_session_count],
    ['Completed', kpis.completed_session_count], ['Failed', kpis.failed_session_count],
    ['Average elapsed', formatDuration(kpis.average_elapsed_seconds)], ['Median elapsed', formatDuration(kpis.median_elapsed_seconds)],
    ['Duration denominator', kpis.elapsed_duration_denominator], ['Total workers', kpis.total_worker_count],
    ['Failed workers', kpis.failed_worker_count], ['Pending approvals', kpis.pending_approval_count],
    ['Evidence metadata', kpis.total_evidence_count], ['Explicit progress', kpis.explicit_progress_count],
    ['Lifecycle-derived progress', kpis.lifecycle_derived_progress_count], ['Unavailable progress', kpis.unavailable_progress_count],
  ].forEach((item) => metric(kpiTarget, item[0], item[1]));

  const body = byId('comparison-table').querySelector('tbody'); replaceChildren(body);
  safeRows(safe.comparisons).forEach((item) => {
    const row = document.createElement('tr');
    [item.session_id, item.runtime_status, item.current_stage, item.current_task, item.current_worker,
      formatDuration(item.elapsed_seconds), item.worker_count, item.failed_worker_count,
      item.pending_approval_count, item.evidence_count,
      item.overall_progress === null ? 'unavailable' : safeText(item.overall_progress) + '%',
      item.progress_source, item.repository_branch, item.repository_working_tree,
      item.staleness && item.staleness.state].forEach((value) => tableCell(row, value));
    body.appendChild(row);
  });
  if (!body.firstChild) {
    const row = document.createElement('tr'); const cell = document.createElement('td');
    cell.colSpan = 15; cell.textContent = 'No comparison data available'; row.appendChild(cell); body.appendChild(row);
  }

  const stageTarget = byId('stage-duration-panel'); replaceChildren(stageTarget);
  const stages = safe.stage_durations && typeof safe.stage_durations === 'object' ? safe.stage_durations : {};
  Object.keys(stages).sort().forEach((sessionId) => {
    safeRows(stages[sessionId]).forEach((stage) => {
      if (stage.duration_seconds === null && stage.provenance === 'unavailable') return;
      const item = document.createElement('article'); item.className = 'stack-item';
      const title = document.createElement('h4'); title.textContent = sessionId + ' · ' + safeText(stage.stage);
      item.appendChild(title); appendMeta(item, 'Duration', formatDuration(stage.duration_seconds));
      appendMeta(item, 'Provenance', stage.provenance); stageTarget.appendChild(item);
    });
  });
  if (!stageTarget.firstChild) stageTarget.appendChild(emptyState('Stage durations unavailable'));

  const approvalTarget = byId('approval-delay-panel'); replaceChildren(approvalTarget);
  const approvals = safe.approval_delays && typeof safe.approval_delays === 'object' ? safe.approval_delays : {};
  Object.keys(approvals).sort().forEach((sessionId) => {
    const value = approvals[sessionId]; if (!value || !value.pending_count) return;
    const item = document.createElement('article'); item.className = 'stack-item approval-pending';
    const title = document.createElement('h4'); title.textContent = sessionId + ' · pending approvals'; item.appendChild(title);
    appendMeta(item, 'Pending', value.pending_count); appendMeta(item, 'Oldest age', formatDuration(value.oldest_pending_age_seconds));
    appendMeta(item, 'Median age', formatDuration(value.median_pending_age_seconds));
    appendMeta(item, 'Age denominator', value.available_age_denominator); approvalTarget.appendChild(item);
  });
  if (!approvalTarget.firstChild) approvalTarget.appendChild(emptyState('No pending approvals in selected sessions'));

  const failureTarget = byId('failure-summary-panel'); replaceChildren(failureTarget);
  const failures = safe.failure_summaries && typeof safe.failure_summaries === 'object' ? safe.failure_summaries : {};
  Object.keys(failures).sort().forEach((sessionId) => {
    const value = failures[sessionId]; if (!value || (!value.failed_worker_count && !value.failure_event_count)) return;
    const item = document.createElement('article'); item.className = 'stack-item severity-critical';
    const title = document.createElement('h4'); title.textContent = sessionId + ' · reported failure signals'; item.appendChild(title);
    appendMeta(item, 'Failed workers', value.failed_worker_count); appendMeta(item, 'Failure events', value.failure_event_count);
    appendMeta(item, 'Most recent', detailText(value.most_recent_failure)); appendMeta(item, 'Limitation', value.interpretation);
    failureTarget.appendChild(item);
  });
  if (!failureTarget.firstChild) failureTarget.appendChild(emptyState('No reported failure signals in selected sessions'));

  const count = renderFindings(safe);
  byId('operations-result-status').textContent = String(safeRows(safe.comparisons).length)
    + ' sessions compared · ' + String(count) + ' visible findings · snapshot-derived';
  byId('export-json').disabled = false; byId('export-csv').disabled = false;
}

function reportFilename(operations, extension) {
  const ids = Array.isArray(operations.selected_session_ids) ? operations.selected_session_ids : [];
  const safeIds = ids.map((value) => safeText(value, '').replace(/[^A-Za-z0-9_-]+/g, '-').slice(0, 40)).filter(Boolean);
  return ('afde-operations-' + safeIds.join('-')).slice(0, 180).replace(/-+$/g, '') + '.' + extension;
}

function csvCell(value) {
  let text = value === null || value === undefined ? '' : String(value);
  if (/^[=+\-@]/.test(text)) text = String.fromCharCode(39) + text;
  return String.fromCharCode(34) + text.replaceAll(String.fromCharCode(34), String.fromCharCode(34) + String.fromCharCode(34)) + String.fromCharCode(34);
}

function comparisonCsv(operations) {
  const fields = ['record_type', 'key', 'value', 'provenance', 'session_id',
    'runtime_status', 'current_stage', 'current_task', 'current_worker', 'created_at',
    'updated_at', 'elapsed_seconds', 'worker_count', 'failed_worker_count', 'pending_approval_count',
    'evidence_count', 'overall_progress', 'progress_source', 'repository_branch', 'repository_working_tree'];
  const lines = [fields.map(csvCell).join(',')];
  const append = (row) => lines.push(fields.map((field) => csvCell(row[field])).join(','));
  append({record_type: 'metadata', key: 'generated_at', value: operations.generated_at});
  append({record_type: 'metadata', key: 'selected_session_ids', value: JSON.stringify(operations.selected_session_ids || [])});
  append({record_type: 'metadata', key: 'known_unavailable_fields', value: JSON.stringify(operations.known_unavailable_fields || [])});
  const definitions = operations.kpi_definitions && typeof operations.kpi_definitions === 'object'
    ? operations.kpi_definitions : {};
  Object.keys(definitions).sort().forEach((key) => append({
    record_type: 'kpi_definition', key, value: definitions[key], provenance: 'snapshot_derived',
  }));
  safeRows(operations.comparisons).forEach((row) => append({record_type: 'comparison', ...row}));
  safeRows(operations.findings).forEach((row) => append({
    record_type: 'finding', key: row.finding_type, value: row.reason,
    provenance: row.confidence_provenance, session_id: row.session_id,
  }));
  return lines.join('\r\n') + '\r\n';
}

function downloadReport(operations, format) {
  if (!operations) return;
  const json = format === 'json'; const content = json ? JSON.stringify(operations, null, 2) : comparisonCsv(operations);
  const blob = new Blob([content], {type: json ? 'application/json' : 'text/csv'});
  const link = document.createElement('a'); const url = URL.createObjectURL(blob);
  link.href = url; link.download = reportFilename(operations, format); link.click();
  window.setTimeout(() => URL.revokeObjectURL(url), 0);
}

function setConnection(label, stateClass, detail) {
  const badge = byId('connection-status'); badge.textContent = label;
  badge.className = 'status-badge ' + stateClass; byId('refresh-status').textContent = detail;
}

async function loadJson(path, signal) {
  const response = await fetch(path, {method: 'GET', cache: 'no-store', headers: {'Accept': 'application/json'}, signal});
  if (!response.ok) throw new Error('HTTP ' + String(response.status));
  return response.json();
}

function createDashboardController() {
  const state = {
    interval: 1000, runtimeTimer: null, sessionTimer: null,
    runtimeInFlight: false, sessionsInFlight: false, operationsInFlight: false, stopped: false,
    runtimeController: null, sessionsController: null, operationsController: null, snapshot: null,
    sessions: [], sessionId: '', lastSuccess: 'unavailable',
    pendingSessionRefresh: false, pendingOperationsRefresh: false,
    comparisonIds: [], operations: null, operationsGeneration: 0,
  };

  function runtimePath(sessionId = state.sessionId) {
    return '/runtime?session_id=' + encodeURIComponent(sessionId);
  }

  function comparisonPath() {
    return '/compare?' + state.comparisonIds.map((id) => 'session_id=' + encodeURIComponent(id)).join('&');
  }

  function updateUrl() {
    const query = new URLSearchParams();
    if (state.sessionId) query.set('session_id', state.sessionId);
    state.comparisonIds.forEach((id) => query.append('compare', id));
    window.history.replaceState(null, '', '?' + query.toString());
  }

  function scheduleRuntime() {
    if (state.stopped) return;
    window.clearTimeout(state.runtimeTimer);
    state.runtimeTimer = window.setTimeout(() => refreshRuntime('poll'), state.interval);
  }

  async function refreshRuntime(source = 'manual') {
    if (state.stopped || state.runtimeInFlight || !state.sessionId) return false;
    window.clearTimeout(state.runtimeTimer); state.runtimeInFlight = true;
    state.runtimeController = new AbortController(); byId('refresh-button').disabled = true;
    const requestedSession = state.sessionId;
    if (source === 'manual') byId('refresh-status').textContent = 'Manual read-only refresh in progress';
    try {
      const snapshot = await loadJson(runtimePath(requestedSession), state.runtimeController.signal);
      if (!snapshot || typeof snapshot !== 'object' || Array.isArray(snapshot)) throw new Error('Invalid snapshot');
      if (requestedSession !== state.sessionId) return false;
      state.snapshot = snapshot; state.lastSuccess = new Date().toLocaleString();
      renderSnapshot(snapshot, state.lastSuccess);
      setConnection('Connected · read only', 'connection-ok', 'Last successful refresh: ' + state.lastSuccess);
      if (state.comparisonIds.length >= 2) void refreshOperations('runtime-poll');
      return true;
    } catch (error) {
      if (!state.pendingSessionRefresh) {
        setConnection('Disconnected', 'connection-error', 'Refresh failed; retry scheduled'
          + (state.snapshot ? ' · displaying last valid snapshot' : ' · no snapshot available'));
      }
      return false;
    } finally {
      state.runtimeInFlight = false; state.runtimeController = null;
      byId('refresh-button').disabled = false;
      if (state.pendingSessionRefresh) {
        state.pendingSessionRefresh = false;
        window.setTimeout(() => refreshRuntime('session-change'), 0);
      } else {
        scheduleRuntime();
      }
    }
  }

  function renderSessions() {
    const selector = byId('session-selector'); const previous = state.sessionId;
    replaceChildren(selector);
    state.sessions.forEach((session) => {
      const option = document.createElement('option'); option.value = safeText(session.session_id, '');
      option.textContent = option.value + ' · ' + safeText(session.runtime_status, 'Unavailable')
        + ' · ' + safeText(session.updated_at, 'time unavailable'); selector.appendChild(option);
    });
    const requested = new URLSearchParams(window.location.search).get('session_id');
    const available = new Set(state.sessions.map((item) => item.session_id));
    state.sessionId = available.has(requested) ? requested
      : available.has(previous) ? previous
      : available.has(state.sessionId) ? state.sessionId
      : state.sessions.length ? safeText(state.sessions[0].session_id, '') : '';
    selector.value = state.sessionId;
    selector.disabled = state.sessions.length === 0;
    renderComparisonSessions();
  }

  function renderComparisonSessions() {
    const selector = byId('comparison-sessions');
    const available = new Set(state.sessions.map((item) => item.session_id));
    if (!state.comparisonIds.length) state.comparisonIds = new URLSearchParams(window.location.search).getAll('compare');
    const removed = state.comparisonIds.filter((id) => !available.has(id));
    state.comparisonIds = Array.from(new Set(state.comparisonIds.filter((id) => available.has(id)))).slice(0, 5);
    replaceChildren(selector);
    state.sessions.forEach((session) => {
      const option = document.createElement('option'); option.value = safeText(session.session_id, '');
      option.textContent = option.value + ' · ' + safeText(session.runtime_status, 'Unavailable');
      option.selected = state.comparisonIds.includes(option.value); selector.appendChild(option);
    });
    selector.disabled = state.sessions.length < 2;
    if (removed.length) {
      state.operationsGeneration += 1;
      state.operations = null;
      if (state.operationsController) {
        state.pendingOperationsRefresh = state.comparisonIds.length >= 2;
        state.operationsController.abort();
      } else if (state.comparisonIds.length >= 2) {
        void refreshOperations('discovery-change');
      } else {
        byId('export-json').disabled = true; byId('export-csv').disabled = true;
      }
      byId('operations-result-status').textContent = 'Removed inaccessible sessions: ' + removed.join(', ');
      updateUrl();
    }
  }

  async function refreshOperations(source = 'manual') {
    if (state.stopped || state.operationsInFlight || state.comparisonIds.length < 2) return false;
    state.operationsInFlight = true; state.operationsController = new AbortController();
    const generation = state.operationsGeneration; byId('compare-button').disabled = true;
    if (source === 'manual') byId('operations-result-status').textContent = 'Loading read-only comparison';
    try {
      const operations = await loadJson(comparisonPath(), state.operationsController.signal);
      if (generation !== state.operationsGeneration) return false;
      state.operations = operations; renderOperations(operations); return true;
    } catch (error) {
      if (!state.pendingOperationsRefresh && generation === state.operationsGeneration) {
        byId('operations-result-status').textContent = 'Comparison unavailable; previous valid result preserved';
      }
      return false;
    } finally {
      state.operationsInFlight = false; state.operationsController = null; byId('compare-button').disabled = false;
      if (state.pendingOperationsRefresh) {
        state.pendingOperationsRefresh = false;
        window.setTimeout(() => refreshOperations('selection-change'), 0);
      }
    }
  }

  function setComparison(sessionIds) {
    const available = new Set(state.sessions.map((item) => item.session_id));
    const selected = Array.from(new Set(sessionIds.filter((id) => available.has(id))));
    if (selected.length < 2 || selected.length > 5) {
      byId('operations-result-status').textContent = 'Select between 2 and 5 discovered sessions'; return false;
    }
    state.comparisonIds = selected; state.operationsGeneration += 1; updateUrl();
    if (state.operationsInFlight) {
      state.pendingOperationsRefresh = true;
      if (state.operationsController) state.operationsController.abort();
      return true;
    }
    void refreshOperations('manual'); return true;
  }

  function clearComparison() {
    state.comparisonIds = []; state.operations = null; state.operationsGeneration += 1;
    state.pendingOperationsRefresh = false;
    if (state.operationsController) state.operationsController.abort();
    Array.from(byId('comparison-sessions').options).forEach((option) => { option.selected = false; });
    updateUrl(); byId('operations-result-status').textContent = 'Comparison cleared; select 2 to 5 sessions';
    byId('export-json').disabled = true; byId('export-csv').disabled = true;
  }

  async function refreshSessions() {
    if (state.stopped || state.sessionsInFlight) return false;
    state.sessionsInFlight = true; state.sessionsController = new AbortController();
    try {
      const payload = await loadJson('/sessions', state.sessionsController.signal);
      state.sessions = safeRows(payload.sessions);
      renderSessions();
      return true;
    } catch (error) {
      byId('result-status').textContent = 'Session discovery unavailable; current selection preserved';
      return false;
    } finally {
      state.sessionsInFlight = false; state.sessionsController = null;
      if (!state.stopped) {
        window.clearTimeout(state.sessionTimer);
        state.sessionTimer = window.setTimeout(refreshSessions, SESSION_REFRESH_INTERVAL);
      }
    }
  }

  async function selectSession(sessionId) {
    if (!state.sessions.some((item) => item.session_id === sessionId)) {
      byId('result-status').textContent = 'Unknown session selection rejected'; return false;
    }
    state.sessionId = sessionId; state.snapshot = null;
    updateUrl();
    byId('result-status').textContent = 'Session changed to ' + sessionId + '; loading snapshot';
    if (state.runtimeInFlight) {
      state.pendingSessionRefresh = true;
      if (state.runtimeController) state.runtimeController.abort();
      return true;
    }
    return refreshRuntime('session-change');
  }

  function configure(config) {
    const seconds = Number(config.poll_interval_seconds);
    if (Number.isFinite(seconds) && seconds > 0) state.interval = seconds * 1000;
    state.sessionId = safeText(config.session_id, '');
    byId('polling-status').textContent = 'Runtime every ' + String(state.interval / 1000)
      + 's · sessions every ' + String(SESSION_REFRESH_INTERVAL / 1000) + 's';
  }

  function stop() {
    state.stopped = true; window.clearTimeout(state.runtimeTimer); window.clearTimeout(state.sessionTimer);
    if (state.runtimeController) state.runtimeController.abort();
    if (state.sessionsController) state.sessionsController.abort();
    if (state.operationsController) state.operationsController.abort();
  }

  return {
    clearComparison, configure, refreshOperations, refreshRuntime, refreshSessions,
    selectSession, setComparison, state, stop,
  };
}

function setupDialog() {
  const dialog = byId('detail-dialog');
  function close() { dialog.close(); if (detailInvoker) detailInvoker.focus(); }
  byId('detail-close').addEventListener('click', close);
  dialog.addEventListener('cancel', (event) => { event.preventDefault(); close(); });
  dialog.addEventListener('keydown', (event) => {
    if (event.key !== 'Tab') return;
    const focusable = Array.from(dialog.querySelectorAll('button, [href], input, select, [tabindex]'))
      .filter((item) => !item.disabled);
    if (!focusable.length) return;
    const first = focusable[0]; const last = focusable[focusable.length - 1];
    if (event.shiftKey && document.activeElement === first) { event.preventDefault(); last.focus(); }
    if (!event.shiftKey && document.activeElement === last) { event.preventDefault(); first.focus(); }
  });
}

function setupPresentationControls(controller) {
  const filterIds = [
    'global-search', 'worker-status-filter', 'worker-source-filter', 'worker-text-filter', 'worker-sort',
    'approval-status-filter', 'approval-sort', 'timeline-event-filter', 'timeline-actor-filter',
    'timeline-task-filter', 'timeline-status-filter', 'timeline-text-filter', 'timeline-sort',
    'evidence-type-filter', 'evidence-availability-filter', 'evidence-text-filter', 'evidence-sort',
  ];
  filterIds.forEach((id) => {
    const control = byId(id);
    const eventName = control.tagName === 'SELECT' ? 'change' : 'input';
    control.addEventListener(eventName, () => {
      if (controller.state.snapshot) renderSnapshot(controller.state.snapshot, controller.state.lastSuccess);
    });
  });
  byId('search-reset').addEventListener('click', () => {
    byId('global-search').value = '';
    if (controller.state.snapshot) renderSnapshot(controller.state.snapshot, controller.state.lastSuccess);
    byId('global-search').focus();
  });
  byId('refresh-button').addEventListener('click', () => controller.refreshRuntime('manual'));
  byId('session-selector').addEventListener('change', (event) => controller.selectSession(event.target.value));
  byId('compare-button').addEventListener('click', () => {
    const selected = Array.from(byId('comparison-sessions').selectedOptions).map((option) => option.value);
    controller.setComparison(selected);
  });
  byId('clear-comparison').addEventListener('click', controller.clearComparison);
  byId('export-json').addEventListener('click', () => downloadReport(controller.state.operations, 'json'));
  byId('export-csv').addEventListener('click', () => downloadReport(controller.state.operations, 'csv'));
  const findingFilters = [
    'finding-session-filter', 'finding-severity-filter', 'finding-type-filter',
    'finding-stage-filter', 'finding-text-filter', 'finding-sort',
  ];
  findingFilters.forEach((id) => {
    const control = byId(id); const eventName = control.tagName === 'SELECT' ? 'change' : 'input';
    control.addEventListener(eventName, () => {
      if (controller.state.operations) renderFindings(controller.state.operations);
    });
  });
  byId('finding-reset').addEventListener('click', () => {
    findingFilters.forEach((id) => { byId(id).value = ''; }); byId('finding-sort').value = 'severity';
    if (controller.state.operations) renderFindings(controller.state.operations);
    byId('finding-text-filter').focus();
  });
  document.querySelector('[data-detail-kind=' + String.fromCharCode(39) + 'session' + String.fromCharCode(39) + ']')
    .addEventListener('click', (event) => {
      const summary = controller.state.sessions.find((item) => item.session_id === controller.state.sessionId)
        || controller.state.snapshot || {};
      openDetail('Session summary', summary, event.currentTarget);
    });
}

async function startDashboard() {
  const controller = createDashboardController(); setupDialog(); setupPresentationControls(controller);
  window.addEventListener('beforeunload', controller.stop, {once: true});
  try {
    const config = await loadJson('/config', new AbortController().signal); controller.configure(config);
  } catch (error) {
    controller.configure({session_id: '', poll_interval_seconds: 1});
    setConnection('Configuration unavailable', 'connection-error', 'Using safe local defaults');
  }
  await controller.refreshSessions();
  if (controller.state.sessionId) await controller.refreshRuntime('initial');
  else byId('result-status').textContent = 'No runtime sessions discovered';
}

window.AFDEDashboard = Object.freeze({
  collectText, comparisonCsv, containsText, createDashboardController, normalizeProgress,
  normalizedStatus, progressSourceLabel, renderFindings, renderOperations,
  renderSnapshot, stableSort, statusClass,
});
window.addEventListener('DOMContentLoaded', startDashboard);
