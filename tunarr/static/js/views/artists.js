/* Artists list view */

function renderArtistsView(container) {
  container.innerHTML = `
    <div class="page-header">
      <h1 class="page-title">Artists</h1>
      <button class="btn btn-primary" id="btn-add-artist">+ Add Artist</button>
    </div>
    <div id="artist-grid-wrap">
      <div class="loading-center"><div class="spinner"></div></div>
    </div>
  `;

  document.getElementById('btn-add-artist').addEventListener('click', openAddArtistModal);
  loadArtists();
}

async function loadArtists() {
  const wrap = document.getElementById('artist-grid-wrap');
  if (!wrap) return;

  try {
    const artists = await API.getArtists();
    if (!artists || artists.length === 0) {
      wrap.innerHTML = `
        <div class="empty-state">
          <div class="empty-state-icon">🎤</div>
          <div class="empty-state-title">No Artists Yet</div>
          <p>Click "Add Artist" to start building your music library.</p>
        </div>
      `;
      return;
    }

    const grid = document.createElement('div');
    grid.className = 'artist-grid';
    artists.forEach(a => grid.appendChild(buildArtistCard(a)));
    wrap.innerHTML = '';
    wrap.appendChild(grid);
  } catch (err) {
    wrap.innerHTML = `<p class="text-danger">Failed to load artists: ${err.message}</p>`;
  }
}

function buildArtistCard(artist) {
  const card = document.createElement('div');
  card.className = 'artist-card';
  const stats = artist.statistics || {};
  const pct = Math.round(stats.percentOfTracks || 0);
  const imgUrl = (artist.images || []).find(i => i.coverType === 'poster' || i.coverType === 'cover')?.remoteUrl;

  card.innerHTML = `
    <div class="artist-card-art">
      ${imgUrl ? `<img src="${imgUrl}" alt="${esc(artist.artistName)}" loading="lazy" onerror="this.style.display='none'" />` : '🎤'}
    </div>
    <div class="artist-card-info">
      <div class="artist-card-name" title="${esc(artist.artistName)}">${esc(artist.artistName)}</div>
      <div class="artist-card-meta">${stats.albumCount || 0} albums · ${stats.trackFileCount || 0}/${stats.totalTrackCount || 0} tracks</div>
      <div class="progress-wrap"><div class="progress-bar" style="width:${pct}%"></div></div>
    </div>
  `;
  card.addEventListener('click', () => navigate(`/artist/${artist.id}`));
  return card;
}

/* ── Add Artist Modal ───────────────────────────────────────────────── */

function openAddArtistModal() {
  document.getElementById('modal-overlay').classList.remove('hidden');
  document.getElementById('artist-search-input').value = '';
  document.getElementById('artist-search-results').innerHTML = '';
  setTimeout(() => document.getElementById('artist-search-input').focus(), 50);
}

function closeAddArtistModal() {
  document.getElementById('modal-overlay').classList.add('hidden');
}

function initAddArtistModal() {
  document.getElementById('modal-close').addEventListener('click', closeAddArtistModal);
  document.getElementById('modal-overlay').addEventListener('click', e => {
    if (e.target === document.getElementById('modal-overlay')) closeAddArtistModal();
  });

  const input = document.getElementById('artist-search-input');
  const btn   = document.getElementById('artist-search-btn');

  btn.addEventListener('click', doArtistSearch);
  input.addEventListener('keydown', e => { if (e.key === 'Enter') doArtistSearch(); });
}

async function doArtistSearch() {
  const input = document.getElementById('artist-search-input');
  const results = document.getElementById('artist-search-results');
  const term = input.value.trim();
  if (!term) return;

  results.innerHTML = '<div class="loading-center"><div class="spinner"></div></div>';

  try {
    const data = await API.searchArtists(term);
    if (!data || data.length === 0) {
      results.innerHTML = '<p class="text-muted" style="text-align:center;padding:20px">No results found.</p>';
      return;
    }

    results.innerHTML = '';
    data.forEach(a => {
      const item = document.createElement('div');
      item.className = 'search-result-item';
      item.innerHTML = `
        <div class="search-result-thumb">🎤</div>
        <div class="search-result-info">
          <div class="search-result-name">${esc(a.artistName)}</div>
          <div class="search-result-sub">${esc(a.artistType || '')} ${a.disambiguation ? '· ' + esc(a.disambiguation) : ''}</div>
        </div>
        <div class="search-result-actions">
          <button class="btn btn-primary btn-sm">Add</button>
        </div>
      `;
      item.querySelector('button').addEventListener('click', () => addArtist(a));
      results.appendChild(item);
    });
  } catch (err) {
    results.innerHTML = `<p class="text-danger">Search failed: ${err.message}</p>`;
  }
}

async function addArtist(a) {
  const folders = await API.getRootFolders().catch(() => []);
  const rootPath = folders[0]?.path || '';

  try {
    await API.addArtist({
      musicBrainzId: a.musicBrainzId,
      artistName: a.artistName,
      monitored: true,
      albumFolder: true,
      rootFolderPath: rootPath,
      addOptions: { addType: 'manual' },
    });
    toast('Artist added: ' + a.artistName, 'success');
    closeAddArtistModal();
    loadArtists();
  } catch (err) {
    toast('Failed to add artist: ' + err.message, 'error');
  }
}
