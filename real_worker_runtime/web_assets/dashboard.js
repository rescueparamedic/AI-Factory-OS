'use strict';

const byId = (id) => document.getElementById(id);
const STATUS_VALUES = new Set(['Running', 'Waiting', 'Completed', 'Failed']);
const LIFECYCLE_NAMES = ['Development', 'QA', 'Documentation', 'Approval', 'Release'];
const TIMELINE_LIMIT = 20;

function safeText(value, fallback = 'unavailable') {
  if (value === null || value === undefined || value === '') {
    return fallback;
  }
  if (typeof value === 'object') {
    return fallback;
  }
  return String(value);
}

function safeRows(value) {
  return Array.isArray(value)
    ? value.filter((item) => item && typeof item === 'object' && !Array.isArray(item))
    : [];
}

function replaceChildren(node) {
  while (node.firstChild) {
    node.removeChild(node.firstChild);
  }
}

function metric(container, label, value) {
  const term = document.createElement('dt');
  const detail = document.createElement('dd');
  term.textContent = label;
  detail.textContent = safeText(value);
  container.append(term, detail);
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
  if (typeof value === 'boolean') {
    return null;
  }
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

function renderRuntime(snapshot, lastSuccess) {
  const status = normalizedStatus(snapshot.runtime_status);
  applyStatusBadge(byId('runtime-status'), status);

  const summary = byId('runtime-summary');
  replaceChildren(summary);
  metric(summary, 'Session ID', snapshot.session_id);
  metric(summary, 'Runtime status', status);
  metric(summary, 'Current stage', snapshot.current_stage);
  metric(summary, 'Snapshot time', snapshot.snapshot_timestamp);
  metric(summary, 'Last browser refresh', lastSuccess);

  const current = byId('current-operation');
  replaceChildren(current);
  metric(current, 'Current task', snapshot.current_task);
  metric(current, 'Current worker', snapshot.current_worker);
  metric(current, 'Current stage', snapshot.current_stage);

  const progress = snapshot.progress && typeof snapshot.progress === 'object'
    ? snapshot.progress : {};
  byId('progress-source').textContent = updateProgress(
    byId('runtime-progress-track'), byId('runtime-progress'),
    progress.value, safeText(progress.source, 'unavailable'),
  );
}

function emptyState(message) {
  const item = document.createElement('div');
  item.className = 'empty-state';
  item.textContent = message;
  return item;
}

function renderWorkers(workers, runtimeProgress) {
  const target = byId('workers');
  replaceChildren(target);
  const rows = safeRows(workers);
  if (rows.length === 0) {
    target.appendChild(emptyState('Worker status unavailable'));
    return;
  }
  rows.forEach((worker) => {
    const item = document.createElement('article');
    const heading = document.createElement('div');
    const name = document.createElement('h3');
    const badge = document.createElement('span');
    const task = document.createElement('p');
    const track = document.createElement('div');
    const bar = document.createElement('div');
    const note = document.createElement('p');
    item.className = 'worker-item';
    heading.className = 'worker-heading';
    name.textContent = safeText(worker.worker, 'Unknown worker');
    applyStatusBadge(badge, worker.status);
    task.className = 'item-meta';
    task.textContent = 'Role: ' + safeText(worker.role || worker.worker)
      + ' · Task: ' + safeText(worker.current_task, 'none');
    track.className = 'progress-track compact';
    track.setAttribute('role', 'progressbar');
    track.setAttribute('aria-label', name.textContent + ' progress');
    track.setAttribute('aria-valuemin', '0');
    track.setAttribute('aria-valuemax', '100');
    bar.className = 'progress-value';
    note.className = 'card-note';
    const source = worker.progress_source || (
      worker.current_task && worker.current_task !== '-'
        ? runtimeProgress.source : 'lifecycle_derived'
    );
    note.textContent = updateProgress(track, bar, worker.progress, source);
    heading.append(name, badge);
    track.appendChild(bar);
    item.append(heading, task, track, note);
    target.appendChild(item);
  });
}

function renderLifecycle(snapshot) {
  const target = byId('lifecycle');
  replaceChildren(target);
  const workers = safeRows(snapshot.workers);
  LIFECYCLE_NAMES.forEach((name, index) => {
    const item = document.createElement('li');
    const label = document.createElement('span');
    const badge = document.createElement('span');
    const field = name.toLowerCase() + '_status';
    const fallback = workers[index] ? workers[index].status : 'Waiting';
    label.textContent = name;
    applyStatusBadge(badge, snapshot[field] || fallback);
    item.append(label, badge);
    target.appendChild(item);
  });
}

function appendMeta(container, label, value) {
  if (value === null || value === undefined || value === '') {
    return;
  }
  const line = document.createElement('p');
  line.className = 'item-meta';
  line.textContent = label + ': ' + safeText(value);
  container.appendChild(line);
}

function renderApprovals(value) {
  const target = byId('approval-queue');
  replaceChildren(target);
  const rows = safeRows(value);
  if (rows.length === 0) {
    target.appendChild(emptyState('No pending approvals'));
    return;
  }
  rows.forEach((row) => {
    const item = document.createElement('article');
    const heading = document.createElement('div');
    const title = document.createElement('h3');
    const badge = document.createElement('span');
    item.className = 'stack-item approval-pending';
    heading.className = 'worker-heading';
    title.textContent = safeText(row.approval_id, 'Approval ID unavailable');
    applyStatusBadge(badge, row.status === 'PENDING' ? 'Waiting' : row.status);
    heading.append(title, badge);
    item.appendChild(heading);
    appendMeta(item, 'Action', row.action);
    appendMeta(item, 'Actor / worker', row.actor || row.worker);
    appendMeta(item, 'Reason', row.reason);
    appendMeta(item, 'Risk / permission', row.risk || row.permission_level);
    appendMeta(item, 'Requested', row.requested_at);
    appendMeta(item, 'Approval status', row.status);
    appendMeta(item, 'Next action', row.next_action);
    target.appendChild(item);
  });
}

function renderTimeline(value) {
  const target = byId('timeline');
  replaceChildren(target);
  const rows = safeRows(value).slice(-TIMELINE_LIMIT);
  if (rows.length === 0) {
    target.appendChild(emptyState('No execution events'));
    return;
  }
  rows.forEach((event) => {
    const item = document.createElement('li');
    const title = document.createElement('h3');
    title.textContent = safeText(event.event || event.type, 'Runtime event');
    item.appendChild(title);
    appendMeta(item, 'Time', event.timestamp);
    appendMeta(item, 'Actor', event.worker || event.actor);
    appendMeta(item, 'Task', event.task || event.task_id);
    appendMeta(item, 'Summary', event.summary || event.detail);
    target.appendChild(item);
  });
}

function renderEvidence(value) {
  const target = byId('evidence');
  replaceChildren(target);
  const rows = safeRows(value);
  if (rows.length === 0) {
    target.appendChild(emptyState('No available evidence metadata'));
    return;
  }
  rows.forEach((row) => {
    const item = document.createElement('article');
    const title = document.createElement('h3');
    item.className = 'stack-item';
    title.textContent = safeText(row.name || row.label || row.type, 'Evidence artifact');
    item.appendChild(title);
    appendMeta(item, 'Type', row.type);
    appendMeta(item, 'Identifier', row.identifier || row.path);
    appendMeta(item, 'Timestamp', row.timestamp);
    appendMeta(item, 'Availability', row.availability || 'available');
    target.appendChild(item);
  });
}

function renderRepository(value) {
  const target = byId('repository');
  replaceChildren(target);
  const repository = value && typeof value === 'object' ? value : {};
  const latest = safeText(repository.latest_commit);
  const pieces = latest === 'unavailable' ? [] : latest.split(' ');
  metric(target, 'Availability', repository.availability || (
    repository.current_branch ? 'available' : 'unavailable'
  ));
  metric(target, 'Branch', repository.current_branch);
  metric(target, 'Working tree', repository.working_tree);
  metric(target, 'Commit hash', repository.latest_commit_hash || pieces[0]);
  metric(target, 'Commit summary', repository.latest_commit_summary || pieces.slice(1).join(' '));
  if (repository.error) {
    metric(target, 'Error', repository.error);
  }
}

function renderSnapshot(snapshot, lastSuccess) {
  const safeSnapshot = snapshot && typeof snapshot === 'object' ? snapshot : {};
  const progress = safeSnapshot.progress && typeof safeSnapshot.progress === 'object'
    ? safeSnapshot.progress : {};
  renderRuntime(safeSnapshot, lastSuccess);
  renderWorkers(safeSnapshot.workers, progress);
  renderLifecycle(safeSnapshot);
  renderApprovals(safeSnapshot.approval_queue);
  renderTimeline(safeSnapshot.timeline);
  renderEvidence(safeSnapshot.evidence);
  renderRepository(safeSnapshot.repository);
}

function setConnection(label, stateClass, detail) {
  const badge = byId('connection-status');
  badge.textContent = label;
  badge.className = 'status-badge ' + stateClass;
  byId('refresh-status').textContent = detail;
}

async function loadJson(path, signal) {
  const response = await fetch(path, {
    method: 'GET',
    cache: 'no-store',
    headers: {'Accept': 'application/json'},
    signal: signal,
  });
  if (!response.ok) {
    throw new Error('HTTP ' + String(response.status));
  }
  return response.json();
}

function createPollingController() {
  const state = {
    interval: 1000,
    endpoint: '/runtime',
    timer: null,
    inFlight: false,
    stopped: false,
    lastSnapshot: null,
    controller: null,
  };

  function schedule() {
    if (state.stopped) {
      return;
    }
    window.clearTimeout(state.timer);
    state.timer = window.setTimeout(() => refresh('poll'), state.interval);
  }

  async function refresh(source = 'manual') {
    if (state.stopped || state.inFlight) {
      return false;
    }
    window.clearTimeout(state.timer);
    state.inFlight = true;
    state.controller = new AbortController();
    byId('refresh-button').disabled = true;
    if (source === 'manual') {
      byId('refresh-status').textContent = 'Manual read-only refresh in progress';
    }
    try {
      const snapshot = await loadJson(state.endpoint, state.controller.signal);
      if (!snapshot || typeof snapshot !== 'object' || Array.isArray(snapshot)) {
        throw new Error('Invalid snapshot');
      }
      const successfulAt = new Date().toLocaleString();
      state.lastSnapshot = snapshot;
      renderSnapshot(snapshot, successfulAt);
      setConnection(
        'Connected · read only', 'connection-ok',
        'Last successful refresh: ' + successfulAt,
      );
      return true;
    } catch (error) {
      const preserved = state.lastSnapshot
        ? ' · displaying last valid snapshot' : ' · no snapshot available';
      setConnection(
        'Disconnected', 'connection-error',
        'Refresh failed; retry scheduled' + preserved,
      );
      return false;
    } finally {
      state.inFlight = false;
      state.controller = null;
      byId('refresh-button').disabled = false;
      schedule();
    }
  }

  function configure(config) {
    const seconds = Number(config.poll_interval_seconds);
    if (Number.isFinite(seconds) && seconds > 0) {
      state.interval = seconds * 1000;
    }
    if (typeof config.runtime_endpoint === 'string' && config.runtime_endpoint === '/runtime') {
      state.endpoint = config.runtime_endpoint;
    }
    byId('polling-status').textContent = 'Polling every '
      + String(state.interval / 1000) + 's · one ' + state.endpoint + ' request';
  }

  function stop() {
    state.stopped = true;
    window.clearTimeout(state.timer);
    if (state.controller) {
      state.controller.abort();
    }
  }

  return {refresh, configure, stop, state};
}

async function startDashboard() {
  const polling = createPollingController();
  byId('refresh-button').addEventListener('click', () => polling.refresh('manual'));
  window.addEventListener('beforeunload', polling.stop, {once: true});
  try {
    const configController = new AbortController();
    const config = await loadJson('/config', configController.signal);
    polling.configure(config);
  } catch (error) {
    byId('polling-status').textContent = 'Polling every 1s · fallback configuration';
    setConnection('Configuration unavailable', 'connection-error', 'Using safe local defaults');
  }
  await polling.refresh('initial');
}

window.AFDEDashboard = Object.freeze({
  normalizeProgress,
  normalizedStatus,
  progressSourceLabel,
  renderSnapshot,
  statusClass,
});
window.addEventListener('DOMContentLoaded', startDashboard);
