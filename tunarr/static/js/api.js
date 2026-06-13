/* Tunarr API client — thin wrapper around fetch */

const API = (() => {
  const base = '';

  async function request(method, path, body) {
    const opts = {
      method,
      headers: { 'Content-Type': 'application/json' },
    };
    if (body !== undefined) opts.body = JSON.stringify(body);
    const resp = await fetch(base + path, opts);
    if (!resp.ok) {
      const text = await resp.text();
      throw new Error(`${resp.status}: ${text}`);
    }
    if (resp.status === 204 || resp.headers.get('content-length') === '0') return null;
    try { return await resp.json(); } catch { return null; }
  }

  return {
    get:    (path)        => request('GET',    path),
    post:   (path, body)  => request('POST',   path, body),
    put:    (path, body)  => request('PUT',    path, body),
    delete: (path)        => request('DELETE', path),

    // ─── Artists ────────────────────────────────────────────────────────
    getArtists:      ()       => API.get('/api/v3/artist'),
    getArtist:       (id)     => API.get(`/api/v3/artist/${id}`),
    searchArtists:   (term)   => API.get(`/api/v3/artist/lookup/search?term=${encodeURIComponent(term)}`),
    addArtist:       (body)   => API.post('/api/v3/artist', body),
    updateArtist:    (id, b)  => API.put(`/api/v3/artist/${id}`, b),
    deleteArtist:    (id, df) => API.delete(`/api/v3/artist/${id}?deleteFiles=${!!df}`),

    // ─── Albums ──────────────────────────────────────────────────────────
    getAlbums:       (artistId) => API.get(`/api/v3/album?artistId=${artistId}`),
    getAlbum:        (id)       => API.get(`/api/v3/album/${id}`),
    updateAlbum:     (id, b)    => API.put(`/api/v3/album/${id}`, b),
    refreshAlbum:    (id)       => API.post(`/api/v3/album/${id}/tracks/refresh`, {}),

    // ─── Tracks ──────────────────────────────────────────────────────────
    getTracks:       (albumId)  => API.get(`/api/v3/track?albumId=${albumId}`),
    getTrack:        (id)       => API.get(`/api/v3/track/${id}`),
    updateTrack:     (id, b)    => API.put(`/api/v3/track/${id}`, b),
    monitorTracks:   (ids, m)   => API.put('/api/v3/track/monitor', { trackIds: ids, monitored: m }),

    // ─── Commands ─────────────────────────────────────────────────────────
    sendCommand:     (body)     => API.post('/api/v3/command', body),
    searchTrack:     (trackId)  => API.post('/api/v3/command', { name: 'TrackSearch', trackIds: [trackId] }),
    searchAlbum:     (albumId)  => API.post('/api/v3/command', { name: 'AlbumSearch', albumId }),
    searchArtistMissing: (aid)  => API.post('/api/v3/command', { name: 'ArtistSearch', artistId: aid }),
    refreshArtist:   (aid)      => API.post('/api/v3/command', { name: 'RefreshArtist', artistId: aid }),

    // ─── Queue ────────────────────────────────────────────────────────────
    getQueue:        ()         => API.get('/api/v3/queue'),
    removeQueue:     (id)       => API.delete(`/api/v3/queue/${id}`),
    clearCompleted:  ()         => API.delete('/api/v3/queue'),

    // ─── History ──────────────────────────────────────────────────────────
    getHistory:      (p=1, ps=20) => API.get(`/api/v3/history?page=${p}&pageSize=${ps}`),

    // ─── Wanted ───────────────────────────────────────────────────────────
    getMissing:      (p=1, ps=20) => API.get(`/api/v3/wanted/missing?page=${p}&pageSize=${ps}`),

    // ─── Track search (YouTube) ───────────────────────────────────────────
    searchYT:        (query)    => API.get(`/api/v3/search/track?query=${encodeURIComponent(query)}`),

    // ─── Download (manual grab) ───────────────────────────────────────────
    grabTrack:       (trackId, url, title) => API.post('/api/v3/command', {
      name: 'TrackSearch', trackIds: [trackId],
    }),

    // ─── Settings ─────────────────────────────────────────────────────────
    getRootFolders:  ()         => API.get('/api/v3/rootfolder'),
    addRootFolder:   (path)     => API.post('/api/v3/rootfolder', { path }),
    deleteRootFolder:(id)       => API.delete(`/api/v3/rootfolder/${id}`),
    getQProfiles:    ()         => API.get('/api/v3/qualityprofile'),

    // ─── System ───────────────────────────────────────────────────────────
    getStatus:       ()         => API.get('/api/v3/system/status'),
  };
})();
