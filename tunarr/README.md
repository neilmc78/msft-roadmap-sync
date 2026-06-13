# Tunarr

**Individual music track download manager** — Sonarr for music tracks.

Lidarr manages music but deliberately only supports whole-album downloads.
Tunarr solves this by applying Sonarr's episode-level model to music:

| Sonarr | Tunarr |
|--------|--------|
| Series | Artist |
| Season | Album  |
| Episode | **Track** |

You can monitor individual tracks, search YouTube Music for them,
and download them as standalone files — just like grabbing a single
TV episode in Sonarr.

## Features

- **Artist management** — add artists via MusicBrainz search
- **Album + track browser** — view full discographies with track-level status
- **Per-track monitoring** — monitor specific tracks, not whole albums
- **Automatic search** — finds best YouTube Music match for duration
- **Manual grab** — search YouTube Music and pick the exact version you want
- **Download queue** — real-time progress for active downloads
- **File import** — automatic rename, tag writing (ID3/FLAC), library organisation
- **History** — full audit trail of every download event
- **Wanted** — list of all monitored-but-missing tracks
- **Quality profiles** — MP3-128 through FLAC 24bit
- **Sonarr-compatible API** — `/api/v3/` endpoint structure

## Quick Start

### Docker Compose

```yaml
version: "3.8"
services:
  tunarr:
    build: .
    ports:
      - "8686:8686"
    volumes:
      - ./config:/config
      - /path/to/music:/music
    environment:
      - TUNARR_MUSIC_DIR=/music
    restart: unless-stopped
```

```bash
docker compose up -d
# Open http://localhost:8686
```

### Local (Python 3.11+)

```bash
pip install -r requirements.txt
# ffmpeg must be in PATH
uvicorn src.main:app --port 8686 --reload
```

## First Steps

1. **Settings → Add Root Folder** — set your music library path
2. **Artists → Add Artist** — search MusicBrainz, click Add
3. **Artist page → click an album** — expands the track list
4. **Toggle the monitor switch** per track (or per album)
5. Click **⬇** on any track to search YouTube Music and grab it
6. Watch **Queue** for download progress
7. **Wanted** shows everything monitored but not yet downloaded

## File Naming

```
{root_folder}/{Artist Name}/{Album Title (Year)}/{NN} - {Track Title}.mp3
```

## Architecture

```
MusicBrainz API  →  Artist/Album/Track metadata
YouTube Music    →  Audio source (via yt-dlp)
yt-dlp           →  Download + audio extraction + tag embedding
ffmpeg           →  Audio conversion (required by yt-dlp)
SQLite           →  Local database (in /config)
FastAPI          →  REST API + SPA frontend
```

## Environment Variables

| Variable | Default | Description |
|----------|---------|-------------|
| `TUNARR_DATA_DIR` | `./config` | Database + temp downloads |
| `TUNARR_MUSIC_DIR` | `./music` | Final music library location |
| `TUNARR_MAX_CONCURRENT_DOWNLOADS` | `3` | Parallel downloads |
| `TUNARR_PORT` | `8686` | HTTP port |

## API

The API mirrors Sonarr's v3 structure:

```
GET  /api/v3/artist              list artists
POST /api/v3/artist              add artist
GET  /api/v3/album?artistId=N    list albums for artist
GET  /api/v3/track?albumId=N     list tracks for album
PUT  /api/v3/track/{id}          update track (monitored)
PUT  /api/v3/track/monitor       bulk monitor/unmonitor tracks
POST /api/v3/command             send command (TrackSearch, AlbumSearch, etc.)
GET  /api/v3/queue               download queue
GET  /api/v3/wanted/missing      missing monitored tracks
GET  /api/v3/history             download history
GET  /api/v3/search/track?query= search YouTube Music
POST /api/v3/queue/grab          manually grab a track by URL
```

Full OpenAPI docs at `http://localhost:8686/docs`.
