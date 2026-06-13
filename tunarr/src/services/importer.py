"""
Post-download file importer.

After yt-dlp completes, this module:
1. Reads audio metadata with mutagen
2. Writes tags (artist, album, track number, title)
3. Registers the TrackFile in the database
4. Updates Track.has_file = True
5. Creates a History record
"""

import json
import os
import shutil
from pathlib import Path

from mutagen import File as MutagenFile
from mutagen.id3 import ID3, TIT2, TPE1, TALB, TRCK, TPOS, TDRC
from mutagen.flac import FLAC
from sqlalchemy.orm import Session

from ..models import Track, TrackFile, History, DownloadQueue
from ..config import settings


def _write_mp3_tags(path: str, track, album, artist):
    try:
        audio = ID3(path)
    except Exception:
        from mutagen.id3 import ID3NoHeaderError
        audio = ID3()
    audio["TIT2"] = TIT2(encoding=3, text=track.title)
    audio["TPE1"] = TPE1(encoding=3, text=artist.name)
    audio["TALB"] = TALB(encoding=3, text=album.title)
    audio["TRCK"] = TRCK(encoding=3, text=f"{track.track_number}/{len(album.tracks)}")
    audio["TPOS"] = TPOS(encoding=3, text=str(track.disc_number or 1))
    if album.release_date:
        audio["TDRC"] = TDRC(encoding=3, text=album.release_date[:4])
    audio.save(path)


def _write_flac_tags(path: str, track, album, artist):
    audio = FLAC(path)
    audio["title"] = track.title
    audio["artist"] = artist.name
    audio["album"] = album.title
    audio["tracknumber"] = str(track.track_number)
    audio["discnumber"] = str(track.disc_number or 1)
    if album.release_date:
        audio["date"] = album.release_date[:4]
    audio.save()


def _get_file_size(path: str) -> int:
    try:
        return os.path.getsize(path)
    except OSError:
        return 0


def _detect_quality(path: str) -> dict:
    try:
        f = MutagenFile(path)
        if f is None:
            return {"quality": {"id": 0, "name": "Unknown"}}
        bitrate = getattr(f.info, "bitrate", 0) or 0
        codec = type(f).__name__.lower()
        if "flac" in codec:
            qid, qname = 6, "FLAC"
        elif bitrate >= 300:
            qid, qname = 3, "MP3-320"
        elif bitrate >= 240:
            qid, qname = 2, "MP3-256"
        else:
            qid, qname = 1, "MP3-128"
        return {
            "quality": {"id": qid, "name": qname},
            "revision": {"version": 1, "real": 0},
        }
    except Exception:
        return {"quality": {"id": 0, "name": "Unknown"}}


def _get_media_info(path: str) -> dict:
    try:
        f = MutagenFile(path)
        if f is None:
            return {}
        info = f.info
        return {
            "audioBitrate": getattr(info, "bitrate", 0) or 0,
            "audioChannels": getattr(info, "channels", 0) or 0,
            "audioSampleRate": getattr(info, "sample_rate", 0) or 0,
            "audioCodec": type(f).__name__,
        }
    except Exception:
        return {}


def import_downloaded_file(
    db: Session,
    queue_item: DownloadQueue,
    downloaded_path: str,
) -> TrackFile | None:
    """Move/rename the file and register it in the database."""
    track = db.get(Track, queue_item.track_id) if queue_item.track_id else None
    album = db.get(__import__("src.models", fromlist=["Album"]).Album, queue_item.album_id) if queue_item.album_id else None
    artist = db.get(__import__("src.models", fromlist=["Artist"]).Artist, queue_item.artist_id)

    if not os.path.exists(downloaded_path):
        return None

    root = artist.root_folder_path or settings.music_dir
    ext = Path(downloaded_path).suffix

    safe = lambda s: "".join(c for c in (s or "") if c not in r'\/:*?"<>|').strip()

    if artist and album and track:
        year = (album.release_date or "")[:4] or "Unknown"
        folder = Path(root) / safe(artist.name) / f"{safe(album.title)} ({year})"
        folder.mkdir(parents=True, exist_ok=True)
        filename = f"{str(track.track_number).zfill(2)} - {safe(track.title)}{ext}"
        dest_path = folder / filename
    elif artist and album:
        year = (album.release_date or "")[:4] or "Unknown"
        folder = Path(root) / safe(artist.name) / f"{safe(album.title)} ({year})"
        folder.mkdir(parents=True, exist_ok=True)
        filename = Path(downloaded_path).name
        dest_path = folder / filename
    else:
        dest_path = Path(root) / Path(downloaded_path).name

    if str(dest_path) != downloaded_path:
        shutil.move(downloaded_path, str(dest_path))

    # Write tags
    if track and album and artist:
        if ext.lower() == ".mp3":
            _write_mp3_tags(str(dest_path), track, album, artist)
        elif ext.lower() == ".flac":
            _write_flac_tags(str(dest_path), track, album, artist)

    quality = _detect_quality(str(dest_path))
    media_info = _get_media_info(str(dest_path))

    track_file = TrackFile(
        track_id=queue_item.track_id,
        artist_id=queue_item.artist_id,
        album_id=queue_item.album_id or (track.album_id if track else 0),
        relative_path=str(dest_path.relative_to(root)) if root else str(dest_path),
        path=str(dest_path),
        size=_get_file_size(str(dest_path)),
        quality=json.dumps(quality),
        media_info=json.dumps(media_info),
    )
    db.add(track_file)
    db.flush()

    if track:
        track.has_file = True
        track.track_file_id = track_file.id

    history = History(
        track_id=queue_item.track_id,
        album_id=queue_item.album_id,
        artist_id=queue_item.artist_id,
        source_title=queue_item.title,
        quality=json.dumps(quality),
        event_type="trackFileImported",
        data=json.dumps({"downloadId": queue_item.download_id or ""}),
    )
    db.add(history)
    db.commit()

    return track_file
