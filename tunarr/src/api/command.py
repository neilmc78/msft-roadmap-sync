"""
Command endpoint — mirrors Sonarr's /api/v3/command.

Supported commands:
  TrackSearch   {trackIds: [int, ...]}   — search + grab individual tracks
  AlbumSearch   {albumId: int}           — search all missing tracks in an album
  ArtistSearch  {artistId: int}          — search all missing monitored tracks for artist
  RefreshArtist {artistId: int}          — re-fetch MusicBrainz metadata for artist/albums/tracks
"""

import asyncio
import uuid
from datetime import datetime, timezone
from fastapi import APIRouter, BackgroundTasks, Depends, HTTPException
from sqlalchemy.orm import Session

from ..database import get_db, SessionLocal
from ..models import Artist, Album, Track
from ..schemas import CommandIn, CommandOut
from ..services.downloader import search_youtube_music
from ..download_manager import enqueue_track_download

router = APIRouter(prefix="/api/v3/command", tags=["command"])

_command_store: dict[int, dict] = {}
_cmd_counter = 0


def _new_command(name: str) -> dict:
    global _cmd_counter
    _cmd_counter += 1
    cmd = {
        "id": _cmd_counter,
        "name": name,
        "status": "queued",
        "queued": datetime.now(timezone.utc).isoformat(),
        "started": None,
        "ended": None,
        "message": "",
    }
    _command_store[_cmd_counter] = cmd
    return cmd


async def _search_and_grab_track(track_id: int):
    db: Session = SessionLocal()
    try:
        track = db.get(Track, track_id)
        if not track or track.has_file:
            return
        album = db.get(Album, track.album_id)
        artist = db.get(Artist, track.artist_id)
        if not artist:
            return

        query = f"{artist.name} {track.title}"
        if album:
            query = f"{artist.name} - {track.title} {album.title}"

        results = await search_youtube_music(query, limit=3)
        if not results:
            return

        # Pick the best result: prefer duration within ±15s of expected
        best = results[0]
        expected_ms = track.duration or 0
        if expected_ms > 0:
            for r in results:
                diff = abs((r.get("duration") or 0) - expected_ms)
                best_diff = abs((best.get("duration") or 0) - expected_ms)
                if diff < best_diff:
                    best = r

        source_title = f"{artist.name} - {track.title}"
        await enqueue_track_download(
            db=db,
            track_id=track_id,
            source_url=best["url"],
            source_title=source_title,
            protocol="ytdlp",
        )
    finally:
        db.close()


async def _run_command(cmd: dict, body: CommandIn):
    cmd["status"] = "started"
    cmd["started"] = datetime.now(timezone.utc).isoformat()

    try:
        name = body.name

        if name == "TrackSearch":
            tasks = [_search_and_grab_track(tid) for tid in body.trackIds]
            await asyncio.gather(*tasks, return_exceptions=True)

        elif name == "AlbumSearch":
            if not body.albumId:
                raise ValueError("albumId required for AlbumSearch")
            db: Session = SessionLocal()
            try:
                tracks = db.query(Track).filter(
                    Track.album_id == body.albumId,
                    Track.monitored == True,
                    Track.has_file == False,
                ).all()
                track_ids = [t.id for t in tracks]
            finally:
                db.close()
            tasks = [_search_and_grab_track(tid) for tid in track_ids]
            await asyncio.gather(*tasks, return_exceptions=True)

        elif name == "ArtistSearch":
            if not body.artistId:
                raise ValueError("artistId required for ArtistSearch")
            db: Session = SessionLocal()
            try:
                tracks = db.query(Track).filter(
                    Track.artist_id == body.artistId,
                    Track.monitored == True,
                    Track.has_file == False,
                ).all()
                track_ids = [t.id for t in tracks]
            finally:
                db.close()
            tasks = [_search_and_grab_track(tid) for tid in track_ids]
            await asyncio.gather(*tasks, return_exceptions=True)

        elif name == "RefreshArtist":
            if not body.artistId:
                raise ValueError("artistId required for RefreshArtist")
            from ..services import musicbrainz as mb
            from ..api.album import refresh_album_tracks
            import json

            db: Session = SessionLocal()
            try:
                artist = db.get(Artist, body.artistId)
                if not artist:
                    raise ValueError(f"Artist {body.artistId} not found")

                mb_data = await mb.get_artist(artist.musicbrainz_id)
                artist.name = mb_data.get("artistName", artist.name)
                artist.sort_name = mb_data.get("sortName", artist.sort_name)
                artist.status = mb_data.get("status", artist.status)
                artist.overview = mb_data.get("overview", artist.overview)
                artist.images = json.dumps(mb_data.get("images", []))
                artist.links = json.dumps(mb_data.get("links", []))
                artist.genres = json.dumps(mb_data.get("genres", []))

                existing_album_mbids = {al.musicbrainz_id for al in artist.albums}
                for rg in mb_data.get("releaseGroups", []):
                    if rg["musicBrainzId"] not in existing_album_mbids:
                        new_album = Album(
                            musicbrainz_id=rg["musicBrainzId"],
                            artist_id=artist.id,
                            title=rg["title"],
                            album_type=rg.get("albumType", "Album"),
                            secondary_types=json.dumps(rg.get("secondaryTypes", [])),
                            release_date=rg.get("releaseDate", ""),
                            monitored=artist.monitored,
                            images=json.dumps([]),
                            links=json.dumps([]),
                            genres=json.dumps([]),
                            labels=json.dumps([]),
                        )
                        db.add(new_album)

                db.commit()
                cmd["message"] = f"Refreshed {artist.name}"
            finally:
                db.close()

        else:
            cmd["message"] = f"Unknown command: {name}"

        cmd["status"] = "completed"
    except Exception as exc:
        cmd["status"] = "failed"
        cmd["message"] = str(exc)
    finally:
        cmd["ended"] = datetime.now(timezone.utc).isoformat()


@router.post("", response_model=CommandOut, status_code=201)
async def send_command(body: CommandIn, background_tasks: BackgroundTasks):
    cmd = _new_command(body.name)
    background_tasks.add_task(_run_command, cmd, body)
    return CommandOut(**cmd)


@router.get("/{command_id}", response_model=CommandOut)
def get_command(command_id: int):
    cmd = _command_store.get(command_id)
    if not cmd:
        raise HTTPException(404, "Command not found")
    return CommandOut(**cmd)


@router.get("", response_model=list[CommandOut])
def list_commands():
    return [CommandOut(**c) for c in _command_store.values()]
