"""
Async download manager — processes the DownloadQueue table.

Artist  ≡ Series
Album   ≡ Season
Track   ≡ Episode   ← the unit we actually download individually
"""

import asyncio
import json
import logging
import uuid
from pathlib import Path

from sqlalchemy.orm import Session

from .config import settings
from .database import SessionLocal
from .models import DownloadQueue, History, Track, Album, Artist
from .services.downloader import download_track, build_output_template
from .services.importer import import_downloaded_file

logger = logging.getLogger("tunarr.downloader")

_active_downloads: dict[int, asyncio.Task] = {}
_semaphore: asyncio.Semaphore | None = None


def _get_semaphore() -> asyncio.Semaphore:
    global _semaphore
    if _semaphore is None:
        _semaphore = asyncio.Semaphore(settings.max_concurrent_downloads)
    return _semaphore


async def _update_queue(queue_id: int, progress: float, status: str, size: int, size_left: int):
    db: Session = SessionLocal()
    try:
        item = db.get(DownloadQueue, queue_id)
        if item:
            item.progress = progress
            item.status = status
            item.size = size
            item.size_left = size_left
            db.commit()
    finally:
        db.close()


async def _run_download(queue_id: int):
    sem = _get_semaphore()
    async with sem:
        db: Session = SessionLocal()
        try:
            item = db.get(DownloadQueue, queue_id)
            if not item or item.status not in ("queued", "downloading"):
                return

            track = db.get(Track, item.track_id) if item.track_id else None
            album = db.get(Album, item.album_id) if item.album_id else None
            artist = db.get(Artist, item.artist_id)

            if not artist:
                item.status = "failed"
                item.error_message = "Artist not found"
                db.commit()
                return

            item.status = "downloading"
            db.commit()

            root = artist.root_folder_path or settings.music_dir
            year = (album.release_date or "")[:4] if album else ""
            track_number = track.track_number if track else "01"
            track_title = track.title if track else item.title
            album_title = album.title if album else "Unknown Album"

            output_template = build_output_template(
                root_folder=str(Path(settings.downloads_dir)),
                artist_name=artist.name,
                album_title=album_title,
                year=year,
                track_number=track_number,
                track_title=track_title,
            )

            db.close()

            result = await download_track(
                url=item.source_url,
                output_template=output_template,
                quality_id=3,
                progress_callback=_update_queue,
                queue_id=queue_id,
            )

            db = SessionLocal()
            item = db.get(DownloadQueue, queue_id)
            if not item:
                return

            downloaded_path = result.get("path", "")
            if downloaded_path and Path(downloaded_path).exists():
                item.status = "importing"
                db.commit()
                import_downloaded_file(db, item, downloaded_path)
                item = db.get(DownloadQueue, queue_id)
                if item:
                    item.status = "completed"
                    item.progress = 100.0
                    db.commit()
            else:
                item.status = "failed"
                item.error_message = "Downloaded file not found after completion"
                _add_history_failed(db, item)
                db.commit()

        except Exception as exc:
            logger.exception("Download failed for queue id %s", queue_id)
            db2: Session = SessionLocal()
            try:
                item2 = db2.get(DownloadQueue, queue_id)
                if item2:
                    item2.status = "failed"
                    item2.error_message = str(exc)
                    _add_history_failed(db2, item2)
                    db2.commit()
            finally:
                db2.close()
        finally:
            _active_downloads.pop(queue_id, None)
            try:
                db.close()
            except Exception:
                pass


def _add_history_failed(db: Session, item: DownloadQueue):
    history = History(
        track_id=item.track_id,
        album_id=item.album_id,
        artist_id=item.artist_id,
        source_title=item.title,
        quality=json.dumps({"quality": {"id": 0, "name": "Unknown"}}),
        event_type="downloadFailed",
        data=json.dumps({"message": item.error_message or "Unknown error"}),
    )
    db.add(history)


async def enqueue_track_download(
    db: Session,
    track_id: int,
    source_url: str,
    source_title: str,
    protocol: str = "ytdlp",
) -> DownloadQueue:
    track = db.get(Track, track_id)
    if not track:
        raise ValueError(f"Track {track_id} not found")

    item = DownloadQueue(
        track_id=track_id,
        album_id=track.album_id,
        artist_id=track.artist_id,
        download_id=str(uuid.uuid4()),
        title=source_title,
        status="queued",
        protocol=protocol,
        source_url=source_url,
    )
    db.add(item)
    db.commit()
    db.refresh(item)

    history = History(
        track_id=track_id,
        album_id=track.album_id,
        artist_id=track.artist_id,
        source_title=source_title,
        quality=json.dumps({"quality": {"id": 0, "name": "Unknown"}}),
        event_type="grabbed",
        data=json.dumps({"protocol": protocol, "url": source_url}),
    )
    db.add(history)
    db.commit()

    task = asyncio.create_task(_run_download(item.id))
    _active_downloads[item.id] = task

    return item


async def process_pending_queue():
    """Called at startup to resume any queued-but-not-started downloads."""
    db: Session = SessionLocal()
    try:
        pending = db.query(DownloadQueue).filter(
            DownloadQueue.status.in_(["queued", "downloading"])
        ).all()
        for item in pending:
            if item.id not in _active_downloads and item.source_url:
                item.status = "queued"
                db.commit()
                task = asyncio.create_task(_run_download(item.id))
                _active_downloads[item.id] = task
    finally:
        db.close()
