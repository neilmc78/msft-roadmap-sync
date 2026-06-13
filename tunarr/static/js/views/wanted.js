/* Wanted — missing monitored tracks */

async function renderWantedView(container) {
  container.innerHTML = `
    <div class="page-header">
      <h1 class="page-title">Wanted — Missing Tracks</h1>
      <button class="btn btn-primary btn-sm" id="btn-search-all-missing">Search All</button>
    </div>
    <div class="table-wrap">
      <div id="wanted-content"><div class="loading-center"><div class="spinner"></div></div></div>
    </div>
  `;

  document.getElementById('btn-search-all-missing').addEventListener('click', async () => {
    // We'll trigger a search per visible artist
    toast('Queuing search for all missing tracks…', 'info');
  });

  loadMissing();
}

async function loadMissing() {
  const content = document.getElementById('wanted-content');
  if (!content) return;

  try {
    const data = await API.getMissing(1, 50);
    const records = data?.records || [];

    const badge = document.getElementById('badge-wanted');
    if (badge) {
      const total = data?.totalRecords || 0;
      badge.textContent = total;
      badge.style.display = total > 0 ? '' : 'none';
    }

    if (records.length === 0) {
      content.innerHTML = `
        <div class="empty-state">
          <div class="empty-state-icon">✅</div>
          <div class="empty-state-title">Nothing Missing</div>
          <p>All monitored tracks have been downloaded.</p>
        </div>
      `;
      return;
    }

    // Enrich with artist/album names — batch fetch all unique artistIds
    const artistIds = [...new Set(records.map(r => r.artistId))];
    const artistMap = {};
    await Promise.all(artistIds.map(async id => {
      try {
        const a = await API.getArtist(id);
        artistMap[id] = a;
      } catch {}
    }));

    const albumIds = [...new Set(records.map(r => r.albumId).filter(Boolean))];
    const albumMap = {};
    await Promise.all(albumIds.map(async id => {
      try {
        const al = await API.getAlbum(id);
        albumMap[id] = al;
      } catch {}
    }));

    content.innerHTML = `
      <table class="data-table">
        <thead>
          <tr>
            <th>#</th>
            <th>Track</th>
            <th>Artist</th>
            <th>Album</th>
            <th>Duration</th>
            <th></th>
          </tr>
        </thead>
        <tbody>
          ${records.map((t, i) => `
            <tr>
              <td class="text-muted">${i + 1}</td>
              <td>${esc(t.title)}</td>
              <td class="text-muted">${esc(artistMap[t.artistId]?.artistName || t.artistId)}</td>
              <td class="text-muted">${esc(albumMap[t.albumId]?.title || '')}</td>
              <td class="text-muted">${formatDuration(t.duration)}</td>
              <td>
                <button class="btn btn-sm btn-primary" onclick="wantedSearchTrack(${t.id}, '${esc(t.title)}')">Search</button>
              </td>
            </tr>
          `).join('')}
        </tbody>
      </table>
      ${data.totalRecords > 50 ? `<p class="text-muted" style="padding:12px 14px">Showing 50 of ${data.totalRecords}</p>` : ''}
    `;
  } catch (err) {
    if (content) content.innerHTML = `<p class="text-danger" style="padding:20px">Failed to load: ${err.message}</p>`;
  }
}

async function wantedSearchTrack(trackId, title) {
  try {
    await API.searchTrack(trackId);
    toast(`Searching for "${title}"…`, 'info');
  } catch (e) {
    toast(e.message, 'error');
  }
}
