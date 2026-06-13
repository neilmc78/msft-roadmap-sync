"""
yt-dlp based downloader.

Concept: a Track (≈ Sonarr Episode) maps to a single audio file download.
Search uses YouTube Music; future: Prowlarr for NZB/torrent sources.
"""

import asyncio
import os
import uuid
from pathlib import Path
from typing import Any
import yt_dlp

from ..config import settings


QUALITY_TO_BITRATE = {
    1: "128",
    2: "256",
    3: "320",
    4: "256",  # AAC-256 – ffmpeg picks aac
    5: "320",  # AAC-320
    6: "0",    # FLAC (best)
    7: "0",    # FLAC 24bit
}

QUALITY_TO_FORMAT = {
    1: "mp3", 2: "mp3", 3: "mp3",
    4: "aac", 5: "aac",
    6: "flac", 7: "flac",
}


async def search_youtube_music(query: str, limit: int = 5) -> list[dict]:
    """Search YouTube Music for a track query and return candidate results."""
    search_query = f"ytmsearch{limit}:{query}"
    ydl_opts = {
        "quiet": True,
        "no_warnings": True,
        "extract_flat": True,
        "skip_download": True,
    }

    def _search():
        with yt_dlp.YoutubeDL(ydl_opts) as ydl:
            info = ydl.extract_info(search_query, download=False)
            entries = info.get("entries", []) if info else []
            results = []
            for e in entries:
                if not e:
                    continue
                duration_s = e.get("duration") or 0
                results.append({
                    "url": e.get("webpage_url") or e.get("url", ""),
                    "title": e.get("title", ""),
                    "channel": e.get("channel") or e.get("uploader", ""),
                    "duration": int(duration_s * 1000),  # to ms
                    "viewCount": e.get("view_count", 0),
                    "thumbnailUrl": (e.get("thumbnails") or [{}])[-1].get("url", ""),
                    "videoId": e.get("id", ""),
                })
            return results

    return await asyncio.get_event_loop().run_in_executor(None, _search)


class ProgressHook:
    def __init__(self, queue_id: int, progress_callback):
        self.queue_id = queue_id
        self.callback = progress_callback

    def __call__(self, d: dict):
        if d["status"] == "downloading":
            total = d.get("total_bytes") or d.get("total_bytes_estimate") or 0
            downloaded = d.get("downloaded_bytes", 0)
            progress = (downloaded / total * 100) if total else 0
            if self.callback:
                asyncio.run_coroutine_threadsafe(
                    self.callback(self.queue_id, progress, "downloading", total, downloaded),
                    asyncio.get_event_loop(),
                )
        elif d["status"] == "finished":
            if self.callback:
                asyncio.run_coroutine_threadsafe(
                    self.callback(self.queue_id, 100.0, "finished", 0, 0),
                    asyncio.get_event_loop(),
                )


async def download_track(
    url: str,
    output_template: str,
    quality_id: int = 3,
    progress_callback=None,
    queue_id: int = 0,
) -> dict[str, Any]:
    """
    Download audio from url, return {'path': ..., 'size': ...}.
    quality_id maps to QUALITY_DEFINITIONS in schemas.py.
    """
    audio_format = QUALITY_TO_FORMAT.get(quality_id, "mp3")
    audio_quality = QUALITY_TO_BITRATE.get(quality_id, "320")

    postprocessors = [{
        "key": "FFmpegExtractAudio",
        "preferredcodec": audio_format,
        "preferredquality": audio_quality,
    }, {
        "key": "EmbedThumbnail",
    }, {
        "key": "FFmpegMetadata",
        "add_metadata": True,
    }]

    hooks = []
    if progress_callback:
        hooks.append(ProgressHook(queue_id, progress_callback))

    ydl_opts = {
        "format": "bestaudio/best",
        "outtmpl": output_template,
        "postprocessors": postprocessors,
        "quiet": True,
        "no_warnings": True,
        "writethumbnail": True,
        "progress_hooks": hooks,
        "noplaylist": True,
    }

    result: dict[str, Any] = {}

    def _download():
        with yt_dlp.YoutubeDL(ydl_opts) as ydl:
            info = ydl.extract_info(url, download=True)
            if info:
                # yt-dlp changes the extension after post-processing
                expected_ext = audio_format
                base = output_template.replace("%(ext)s", expected_ext)
                # Try to resolve actual output path
                for ext in [audio_format, "mp3", "flac", "aac", "m4a", "opus"]:
                    candidate = output_template.replace("%(ext)s", ext)
                    if os.path.exists(candidate):
                        result["path"] = candidate
                        result["size"] = os.path.getsize(candidate)
                        break
                if "path" not in result:
                    result["path"] = base
                    result["size"] = 0
                result["title"] = info.get("title", "")
                result["duration"] = int((info.get("duration") or 0) * 1000)

    await asyncio.get_event_loop().run_in_executor(None, _download)
    return result


def build_output_template(
    root_folder: str,
    artist_name: str,
    album_title: str,
    year: str,
    track_number: str,
    track_title: str,
) -> str:
    """Build a filesystem output path following standard naming convention."""
    safe = lambda s: "".join(c for c in s if c not in r'\/:*?"<>|').strip()
    folder = Path(root_folder) / safe(artist_name) / f"{safe(album_title)} ({year[:4] if year else 'Unknown'})"
    folder.mkdir(parents=True, exist_ok=True)
    filename = f"{str(track_number).zfill(2)} - {safe(track_title)}.%(ext)s"
    return str(folder / filename)
