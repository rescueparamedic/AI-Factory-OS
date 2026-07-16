'use strict';

const byId = (id) => document.getElementById(id);
const STATUS_VALUES = new Set(['Running', 'Waiting', 'Completed', 'Failed']);
const LIFECYCLE_NAMES = ['Development', 'QA', 'Documentation', 'Approval', 'Release'];
const TIMELINE_LIMIT = 50;
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
    fieldMatches(row, 'event', event) && containsText([row.worker, row.actor], actor)
    && containsText([row.task, row.task_id], task) && fieldMatches(row, 'status', status)
    && containsText(row, text) && containsText(row, globalQuery)
  ));
  rows = stableSort(rows, (row) => row.timestamp || '', byId('timeline-sort').value);
  rows = rows.slice(0, TIMELINE_LIMIT);
  if (!rows.length) { target.appendChild(emptyState('No timeline events match the active filters')); return 0; }
  rows.forEach((row) => {
    const item = document.createElement('li'); const title = document.createElement('h3');
    title.textContent = safeText(row.event || row.type, 'Runtime event'); item.appendChild(title);
    appendMeta(item, 'Time', row.timestamp); appendMeta(item, 'Actor', row.worker || row.actor);
    appendMeta(item, 'Task', row.task || row.task_id); appendMeta(item, 'Status', row.status);
    appendMeta(item, 'Summary', row.summary || row.detail);
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
    runtimeInFlight: false, sessionsInFlight: false, stopped: false,
    runtimeController: null, sessionsController: null, snapshot: null,
    sessions: [], sessionId: '', lastSuccess: 'unavailable',
    pendingSessionRefresh: false,
  };

  function runtimePath(sessionId = state.sessionId) {
    return '/runtime?session_id=' + encodeURIComponent(sessionId);
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
    window.history.replaceState(null, '', '?session_id=' + encodeURIComponent(sessionId));
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
  }

  return {configure, refreshRuntime, refreshSessions, selectSession, state, stop};
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
  collectText, containsText, createDashboardController, normalizeProgress,
  normalizedStatus, progressSourceLabel, renderSnapshot, stableSort, statusClass,
});
window.addEventListener('DOMContentLoaded', startDashboard);
