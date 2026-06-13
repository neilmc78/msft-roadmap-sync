/* Download queue view */

let _queueInterval = null;

async function renderQueueView(container) {
  container.innerHTML = `
    <div class="page-header">
      <h1 class="page-title">Download Queue</h1>
      <button class="btn btn-secondary btn-sm" id="btn-clear-completed">Clear Completed</button>
    </div>
    <div class="table-wrap">
      <div id="queue-content"><div class="loading-center"><div class="spinner"></div></div></div>
    </div>
  `;

  document.getElementById('btn-clear-completed').addEventListener('click', async () => {
    await API.clearCompleted().catch(e => toast(e.message, 'error'));
    loadQueue();
  });

  loadQueue();
  _queueInterval = setInterval(loadQueue, 3000);
}

function teardownQueueView() {
  if (_queueInterval) { clearInterval(_queueInterval); _queueInterval = null; }
}

async function loadQueue() {
  const content = document.getElementById('queue-content');
  if (!content) { teardownQueueView(); return; }

  try {
    const data = await API.getQueue();
    const records = (data?.records || []);

    // Update sidebar badge
    const active = records.filter(r => r.status !== 'completed').length;
    const badge = document.getElementById('badge-queue');
    if (badge) {
      badge.textContent = active;
      badge.style.display = active > 0 ? '' : 'none';
    }

    if (records.length === 0) {
      content.innerHTML = `
        <div class="empty-state">
          <div class="empty-state-icon">⬇️</div>
          <div class="empty-state-title">Queue is Empty</div>
          <p>Downloads appear here when you search for tracks.</p>
        </div>
      `;
      return;
    }

    content.innerHTML = `
      <table class="data-table">
        <thead>
          <tr>
            <th>Track</th>
            <th>Artist</th>
            <th>Album</th>
            <th>Source</th>
            <th>Status</th>
            <th>Progress</th>
            <th></th>
          </tr>
        </thead>
        <tbody>
          ${records.map(r => `
            <tr>
              <td>${esc(r.trackTitle || r.title)}</td>
              <td class="text-muted">${esc(r.artistName)}</td>
              <td class="text-muted">${esc(r.albumTitle)}</td>
              <td class="text-muted">${esc(r.protocol)}</td>
              <td>${statusBadgeForQueue(r.status)}</td>
              <td>
                ${r.status === 'downloading'
                  ? `<div class="progress-bar-container"><div class="progress-bar-fill" style="width:${r.progress}%"></div></div>`
                  : `<span class="text-muted">${Math.round(r.progress)}%</span>`}
              </td>
              <td>
                <button class="btn btn-sm btn-danger" onclick="removeFromQueue(${r.id})">✕</button>
              </td>
            </tr>
          `).join('')}
        </tbody>
      </table>
    `;
  } catch (err) {
    if (document.getElementById('queue-content')) {
      content.innerHTML = `<p class="text-danger" style="padding:20px">Failed to load queue: ${err.message}</p>`;
    }
  }
}

async function removeFromQueue(id) {
  await API.removeQueue(id).catch(e => toast(e.message, 'error'));
  loadQueue();
}

function statusBadgeForQueue(status) {
  const map = {
    queued:      'status-monitored',
    downloading: 'status-monitored',
    importing:   'status-queued',
    completed:   'status-downloaded',
    failed:      'status-missing',
  };
  return `<span class="status-badge ${map[status] || ''}">${status}</span>`;
}
