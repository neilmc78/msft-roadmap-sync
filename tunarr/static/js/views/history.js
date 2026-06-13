/* History view */

async function renderHistoryView(container) {
  container.innerHTML = `
    <div class="page-header">
      <h1 class="page-title">History</h1>
    </div>
    <div class="table-wrap">
      <div id="history-content"><div class="loading-center"><div class="spinner"></div></div></div>
    </div>
  `;
  loadHistory(1);
}

async function loadHistory(page = 1) {
  const content = document.getElementById('history-content');
  if (!content) return;

  try {
    const data = await API.getHistory(page, 30);
    const records = data?.records || [];

    if (records.length === 0) {
      content.innerHTML = `
        <div class="empty-state">
          <div class="empty-state-icon">📋</div>
          <div class="empty-state-title">No History</div>
          <p>Download events will appear here.</p>
        </div>
      `;
      return;
    }

    const eventIcon = {
      grabbed:            '⬇️',
      trackFileImported:  '✅',
      downloadFailed:     '❌',
      trackFileDeleted:   '🗑️',
      trackFileRenamed:   '✏️',
    };

    content.innerHTML = `
      <table class="data-table">
        <thead>
          <tr>
            <th>Event</th>
            <th>Track</th>
            <th>Artist</th>
            <th>Source</th>
            <th>Quality</th>
            <th>Date</th>
          </tr>
        </thead>
        <tbody>
          ${records.map(h => `
            <tr>
              <td>${eventIcon[h.eventType] || '•'} <span class="status-badge ${h.eventType === 'downloadFailed' ? 'status-missing' : h.eventType === 'trackFileImported' ? 'status-downloaded' : 'status-monitored'}">${h.eventType}</span></td>
              <td>${esc(h.trackTitle || '—')}</td>
              <td class="text-muted">${esc(h.artistName)}</td>
              <td class="text-muted" style="max-width:200px;overflow:hidden;text-overflow:ellipsis;white-space:nowrap" title="${esc(h.sourceTitle)}">${esc(h.sourceTitle)}</td>
              <td class="text-muted">${esc(h.quality?.quality?.name || '')}</td>
              <td class="text-muted" style="white-space:nowrap">${fmtDate(h.date)}</td>
            </tr>
          `).join('')}
        </tbody>
      </table>
      ${data.totalRecords > 30 ? `
        <div style="padding:12px 14px;display:flex;justify-content:space-between;align-items:center">
          <span class="text-muted">Page ${page} of ${Math.ceil(data.totalRecords/30)}</span>
          <div style="display:flex;gap:8px">
            ${page > 1 ? `<button class="btn btn-secondary btn-sm" onclick="loadHistory(${page-1})">← Prev</button>` : ''}
            ${page < Math.ceil(data.totalRecords/30) ? `<button class="btn btn-secondary btn-sm" onclick="loadHistory(${page+1})">Next →</button>` : ''}
          </div>
        </div>
      ` : ''}
    `;
  } catch (err) {
    if (content) content.innerHTML = `<p class="text-danger" style="padding:20px">Failed to load history: ${err.message}</p>`;
  }
}

function fmtDate(iso) {
  if (!iso) return '—';
  try {
    const d = new Date(iso);
    return d.toLocaleString(undefined, { dateStyle: 'short', timeStyle: 'short' });
  } catch { return iso; }
}
