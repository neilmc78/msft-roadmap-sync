import platform
import sys
from datetime import datetime, timezone
from fastapi import APIRouter

router = APIRouter(prefix="/api/v3/system", tags=["system"])

_start_time = datetime.now(timezone.utc)


@router.get("/status")
def system_status():
    import yt_dlp
    return {
        "appName": "Tunarr",
        "version": "1.0.0",
        "buildTime": "2024-01-01T00:00:00Z",
        "startupPath": ".",
        "appData": "./config",
        "osName": platform.system(),
        "osVersion": platform.release(),
        "runtimeVersion": sys.version,
        "ytdlpVersion": yt_dlp.version.__version__,
        "isDocker": False,
        "isNetCore": False,
        "startedAt": _start_time.isoformat(),
    }


@router.get("/task")
def list_tasks():
    return [
        {"id": 1, "name": "RefreshArtist", "taskName": "Refresh Artist", "interval": 1440, "lastExecution": "", "nextExecution": ""},
        {"id": 2, "name": "CheckForMissingTracks", "taskName": "Check for Missing Tracks", "interval": 60, "lastExecution": "", "nextExecution": ""},
    ]


@router.get("/backup")
def list_backups():
    return []
