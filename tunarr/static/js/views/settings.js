/* Settings view */

async function renderSettingsView(container) {
  container.innerHTML = `
    <div class="page-header">
      <h1 class="page-title">Settings</h1>
    </div>
    <div id="settings-body"><div class="loading-center"><div class="spinner"></div></div></div>
  `;

  try {
    const [folders, profiles, status] = await Promise.all([
      API.getRootFolders(),
      API.getQProfiles(),
      API.getStatus(),
    ]);
    renderSettingsBody(document.getElementById('settings-body'), folders, profiles, status);
  } catch (err) {
    document.getElementById('settings-body').innerHTML = `<p class="text-danger">Failed to load settings: ${err.message}</p>`;
  }
}

function renderSettingsBody(body, folders, profiles, status) {
  body.innerHTML = `
    <!-- Root Folders -->
    <div class="settings-section">
      <h3>Music Library Folders</h3>
      <ul class="root-folder-list" id="root-folder-list">
        ${folders.length === 0 ? '<li class="text-muted">No folders configured.</li>' : ''}
        ${folders.map(f => `
          <li class="root-folder-item">
            <span class="root-folder-path">${esc(f.path)}</span>
            <span class="text-muted" style="font-size:12px">${fmtBytes(f.freeSpace)} free</span>
            <button class="btn btn-sm btn-danger" onclick="deleteRootFolder(${f.id})">Remove</button>
          </li>
        `).join('')}
      </ul>
      <div class="flex gap-2">
        <input type="text" class="form-input" id="new-folder-path" placeholder="/music/library" style="max-width:320px" />
        <button class="btn btn-primary btn-sm" id="btn-add-folder">Add Folder</button>
      </div>
    </div>

    <!-- Quality Profiles -->
    <div class="settings-section">
      <h3>Quality Profiles</h3>
      ${profiles.length === 0 ? '<p class="text-muted">No profiles configured.</p>' : ''}
      ${profiles.map(p => `
        <div style="display:flex;align-items:center;gap:12px;padding:8px 0;border-bottom:1px solid var(--border)">
          <span style="font-weight:600">${esc(p.name)}</span>
          <span class="text-muted">Cutoff: ${esc(String(p.cutoff))}</span>
          <span class="text-muted">${p.upgradeAllowed ? 'Upgrades allowed' : 'No upgrades'}</span>
        </div>
      `).join('')}
    </div>

    <!-- System Info -->
    <div class="settings-section">
      <h3>System</h3>
      <div style="display:grid;grid-template-columns:auto 1fr;gap:8px 16px;font-size:13px">
        <span class="text-muted">Version</span><span>${esc(status.version || '—')}</span>
        <span class="text-muted">yt-dlp</span><span>${esc(status.ytdlpVersion || '—')}</span>
        <span class="text-muted">OS</span><span>${esc(status.osName || '')} ${esc(status.osVersion || '')}</span>
        <span class="text-muted">Started</span><span>${fmtDateLocal(status.startedAt)}</span>
      </div>
    </div>
  `;

  document.getElementById('btn-add-folder').addEventListener('click', addRootFolder);
  document.getElementById('new-folder-path').addEventListener('keydown', e => {
    if (e.key === 'Enter') addRootFolder();
  });
}

async function addRootFolder() {
  const input = document.getElementById('new-folder-path');
  const path = input.value.trim();
  if (!path) return;
  try {
    await API.addRootFolder(path);
    toast('Root folder added', 'success');
    input.value = '';
    renderSettingsView(document.getElementById('view-container'));
  } catch (e) { toast(e.message, 'error'); }
}

async function deleteRootFolder(id) {
  if (!confirm('Remove this folder from Tunarr? (Files will NOT be deleted.)')) return;
  try {
    await API.deleteRootFolder(id);
    toast('Folder removed', 'success');
    renderSettingsView(document.getElementById('view-container'));
  } catch (e) { toast(e.message, 'error'); }
}

function fmtBytes(bytes) {
  if (!bytes) return '?';
  if (bytes >= 1e12) return (bytes/1e12).toFixed(1) + ' TB';
  if (bytes >= 1e9)  return (bytes/1e9).toFixed(1) + ' GB';
  if (bytes >= 1e6)  return (bytes/1e6).toFixed(1) + ' MB';
  return bytes + ' B';
}

function fmtDateLocal(iso) {
  if (!iso) return '—';
  try { return new Date(iso).toLocaleString(); } catch { return iso; }
}
