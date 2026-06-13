"""
MusicBrainz API client.

Concept mapping:
  MusicBrainz artist  → Tunarr Artist  (≈ Sonarr Series)
  MusicBrainz release-group → Tunarr Album (≈ Sonarr Season)
  MusicBrainz recording → Tunarr Track (≈ Sonarr Episode)
"""

import asyncio
import time
import httpx

MB_BASE = "https://musicbrainz.org/ws/2"
USER_AGENT = "Tunarr/1.0 (https://github.com/tunarr/tunarr)"

_last_request = 0.0
_RATE_LIMIT = 1.1  # seconds between requests (MB requires ≥1s)


async def _get(path: str, params: dict | None = None) -> dict:
    global _last_request
    now = time.monotonic()
    gap = _RATE_LIMIT - (now - _last_request)
    if gap > 0:
        await asyncio.sleep(gap)
    _last_request = time.monotonic()

    async with httpx.AsyncClient(headers={"User-Agent": USER_AGENT}) as client:
        resp = await client.get(f"{MB_BASE}/{path}", params={**(params or {}), "fmt": "json"}, timeout=15)
        resp.raise_for_status()
        return resp.json()


async def search_artists(query: str, limit: int = 10) -> list[dict]:
    data = await _get("artist", {"query": query, "limit": limit})
    results = []
    for a in data.get("artists", []):
        results.append({
            "musicBrainzId": a.get("id", ""),
            "artistName": a.get("name", ""),
            "sortName": a.get("sort-name", ""),
            "disambiguation": a.get("disambiguation", ""),
            "artistType": a.get("type", ""),
            "status": a.get("life-span", {}).get("ended") and "ended" or "active",
            "overview": "",
            "images": [],
            "links": [],
            "genres": [g["name"] for g in a.get("genres", [])],
        })
    return results


async def get_artist(mbid: str) -> dict:
    data = await _get(f"artist/{mbid}", {"inc": "release-groups+genres+url-rels"})
    release_groups = []
    for rg in data.get("release-groups", []):
        release_groups.append({
            "musicBrainzId": rg.get("id", ""),
            "title": rg.get("title", ""),
            "albumType": rg.get("primary-type", "Album"),
            "secondaryTypes": rg.get("secondary-types", []),
            "releaseDate": rg.get("first-release-date", ""),
        })

    links = []
    for rel in data.get("relations", []):
        url = rel.get("url", {}).get("resource", "")
        if url:
            links.append({"url": url, "name": rel.get("type", "")})

    return {
        "musicBrainzId": data.get("id", ""),
        "artistName": data.get("name", ""),
        "sortName": data.get("sort-name", ""),
        "disambiguation": data.get("disambiguation", ""),
        "artistType": data.get("type", ""),
        "status": "ended" if data.get("life-span", {}).get("ended") else "active",
        "overview": "",
        "images": [],
        "links": links,
        "genres": [g["name"] for g in data.get("genres", [])],
        "releaseGroups": release_groups,
    }


async def get_release_group_with_tracks(rg_mbid: str) -> dict:
    """Fetch a release-group and its canonical release's track list."""
    rg_data = await _get(f"release-group/{rg_mbid}", {
        "inc": "releases+genres+url-rels",
    })

    # Pick the earliest official release
    releases = rg_data.get("releases", [])
    releases_sorted = sorted(
        [r for r in releases if r.get("status", "").lower() == "official" or not r.get("status")],
        key=lambda r: r.get("date", "9999"),
    )
    release_mbid = releases_sorted[0]["id"] if releases_sorted else None
    if not release_mbid and releases:
        release_mbid = releases[0]["id"]

    tracks = []
    if release_mbid:
        release_data = await _get(f"release/{release_mbid}", {"inc": "recordings"})
        disc_num = 0
        abs_num = 0
        for medium in release_data.get("media", []):
            disc_num += 1
            for track in medium.get("tracks", []):
                abs_num += 1
                rec = track.get("recording", {})
                tracks.append({
                    "musicBrainzId": rec.get("id", ""),
                    "title": track.get("title") or rec.get("title", "Unknown"),
                    "trackNumber": track.get("number", str(abs_num)),
                    "absoluteTrackNumber": abs_num,
                    "discNumber": disc_num,
                    "duration": rec.get("length") or 0,
                    "explicit": False,
                })

    images = []
    # CAA (Cover Art Archive)
    images.append({
        "coverType": "cover",
        "remoteUrl": f"https://coverartarchive.org/release-group/{rg_mbid}/front-250",
    })

    links = []
    for rel in rg_data.get("relations", []):
        url = rel.get("url", {}).get("resource", "")
        if url:
            links.append({"url": url, "name": rel.get("type", "")})

    return {
        "musicBrainzId": rg_mbid,
        "title": rg_data.get("title", ""),
        "albumType": rg_data.get("primary-type", "Album"),
        "secondaryTypes": rg_data.get("secondary-types", []),
        "releaseDate": rg_data.get("first-release-date", ""),
        "genres": [g["name"] for g in rg_data.get("genres", [])],
        "images": images,
        "links": links,
        "tracks": tracks,
    }
