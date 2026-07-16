'use strict';

const byId = (id) => document.getElementById(id);

function replaceChildren(node) {
  while (node.firstChild) {
    node.removeChild(node.firstChild);
  }
}

function metric(container, label, value) {
  const term = document.createElement('dt');
  const detail = document.createElement('dd');
  term.textContent = label;
  detail.textContent = value == null ? 'unavailable' : String(value);
  container.append(term, detail);
}

function renderRuntime(snapshot) {
  const summary = byId('runtime-summary');
  replaceChildren(summary);
  metric(summary, 'Status', snapshot.runtime_status);
  metric(summary, 'Session', snapshot.session_id);
  metric(summary, 'Stage', snapshot.current_stage);
  metric(summary, 'Task', snapshot.current_task);
  metric(summary, 'Worker', snapshot.current_worker);

  const progress = snapshot.progress || {};
  const value = Number(progress.value);
  const valid = Number.isFinite(value) && value >= 0 && value <= 100;
  byId('runtime-progress').style.width = valid ? String(value) + '%' : '0';
  byId('progress-source').textContent = valid
    ? String(value) + '% · ' + String(progress.source || 'unavailable')
    : 'Progress unavailable · ' + String(progress.source || 'unavailable');
}

function renderWorkers(workers) {
  const target = byId('workers');
  replaceChildren(target);
  if (!Array.isArray(workers) || workers.length === 0) {
    target.append(emptyState('Worker status unavailable'));
    return;
  }
  const table = document.createElement('table');
  const head = document.createElement('thead');
  const headRow = document.createElement('tr');
  ['Worker', 'Status', 'Task', 'Progress'].forEach((label) => {
    const cell = document.createElement('th');
    cell.textContent = label;
    headRow.appendChild(cell);
  });
  head.appendChild(headRow);
  table.appendChild(head);
  const body = document.createElement('tbody');
  workers.forEach((worker) => {
    const row = document.createElement('tr');
    const progress = worker.progress == null
      ? 'unavailable' : String(worker.progress) + '%';
    [worker.worker, worker.status, worker.current_task, progress].forEach((value) => {
      const cell = document.createElement('td');
      cell.textContent = value == null ? 'unavailable' : String(value);
      row.appendChild(cell);
    });
    body.appendChild(row);
  });
  table.appendChild(body);
  target.appendChild(table);
}

function emptyState(message) {
  const item = document.createElement('div');
  item.className = 'empty-state';
  item.textContent = message;
  return item;
}

function renderTimeline(timeline) {
  const target = byId('timeline');
  replaceChildren(target);
  if (!Array.isArray(timeline) || timeline.length === 0) {
    target.appendChild(emptyState('No execution events'));
    return;
  }
  timeline.slice(-12).reverse().forEach((event) => {
    const item = document.createElement('li');
    const title = document.createElement('div');
    const meta = document.createElement('div');
    title.className = 'item-title';
    meta.className = 'item-meta';
    title.textContent = String(event.event || 'Runtime event');
    meta.textContent = [
      event.timestamp || 'time unavailable',
      event.worker || 'runtime',
      event.detail || '',
    ].filter(Boolean).join(' · ');
    item.append(title, meta);
    target.appendChild(item);
  });
}

function renderCards(targetId, rows, emptyMessage, titleField, metaFields) {
  const target = byId(targetId);
  replaceChildren(target);
  if (!Array.isArray(rows) || rows.length === 0) {
    target.appendChild(emptyState(emptyMessage));
    return;
  }
  rows.forEach((row) => {
    const item = document.createElement('div');
    const title = document.createElement('div');
    const meta = document.createElement('div');
    item.className = 'stack-item';
    title.className = 'item-title';
    meta.className = 'item-meta';
    title.textContent = String(row[titleField] || 'unavailable');
    meta.textContent = metaFields
      .map((field) => row[field])
      .filter(Boolean)
      .map(String)
      .join(' · ');
    item.append(title, meta);
    target.appendChild(item);
  });
}

function renderRepository(repository) {
  const target = byId('repository');
  replaceChildren(target);
  const repo = repository || {};
  metric(target, 'Branch', repo.current_branch);
  metric(target, 'Working tree', repo.working_tree);
  metric(target, 'Latest commit', repo.latest_commit);
}

function renderSnapshot(snapshot) {
  renderRuntime(snapshot);
  renderWorkers(snapshot.workers);
  renderTimeline(snapshot.timeline);
  renderCards(
    'approval-queue', snapshot.approval_queue,
    'No pending approvals', 'approval_id',
    ['action', 'status', 'next_action'],
  );
  renderCards(
    'evidence', snapshot.evidence,
    'No evidence available', 'type', ['path'],
  );
  renderRepository(snapshot.repository);
  byId('refresh-time').textContent =
    'Snapshot ' + String(snapshot.snapshot_timestamp || 'unavailable');
}

function setConnection(label, className) {
  const badge = byId('connection-status');
  badge.textContent = label;
  badge.className = 'status-badge ' + className;
}

async function loadJson(path) {
  const response = await fetch(path, {
    method: 'GET',
    cache: 'no-store',
    headers: {'Accept': 'application/json'},
  });
  if (!response.ok) {
    throw new Error('HTTP ' + String(response.status));
  }
  return response.json();
}

async function startDashboard() {
  let interval = 1000;
  let endpoint = '/runtime';
  try {
    const config = await loadJson('/config');
    const seconds = Number(config.poll_interval_seconds);
    if (Number.isFinite(seconds) && seconds > 0) {
      interval = seconds * 1000;
    }
    endpoint = String(config.runtime_endpoint || endpoint);
  } catch (error) {
    setConnection('Configuration unavailable', 'error');
  }

  async function refresh() {
    try {
      const snapshot = await loadJson(endpoint);
      renderSnapshot(snapshot);
      setConnection('Connected · read-only', 'connected');
    } catch (error) {
      setConnection('Refresh failed · retrying', 'error');
    } finally {
      window.setTimeout(refresh, interval);
    }
  }

  refresh();
}

window.addEventListener('DOMContentLoaded', startDashboard);
