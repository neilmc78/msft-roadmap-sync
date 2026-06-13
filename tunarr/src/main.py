import json
import logging
from contextlib import asynccontextmanager
from pathlib import Path

from fastapi import FastAPI
from fastapi.staticfiles import StaticFiles
from fastapi.responses import FileResponse

from .config import settings
from .database import init_db, SessionLocal
from .models import QualityProfile
from .schemas import QUALITY_DEFINITIONS
from .download_manager import process_pending_queue
from .api import artist, album, track, command, queue, history, wanted, settings as settings_api, system, search

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger("tunarr")


@asynccontextmanager
async def lifespan(app: FastAPI):
    logger.info("Tunarr starting — initialising database")
    Path(settings.data_dir).mkdir(parents=True, exist_ok=True)
    Path(settings.downloads_dir).mkdir(parents=True, exist_ok=True)
    Path(settings.music_dir).mkdir(parents=True, exist_ok=True)

    init_db()
    _seed_default_quality_profile()

    logger.info("Resuming pending downloads")
    await process_pending_queue()

    logger.info("Tunarr ready on port %s", settings.port)
    yield
    logger.info("Tunarr shutting down")


def _seed_default_quality_profile():
    db = SessionLocal()
    try:
        if db.query(QualityProfile).count() == 0:
            qp = QualityProfile(
                name="Standard",
                upgrade_allowed=True,
                cutoff=3,
                items=json.dumps(QUALITY_DEFINITIONS),
            )
            db.add(qp)
            db.commit()
            logger.info("Created default quality profile 'Standard'")
    finally:
        db.close()


app = FastAPI(
    title="Tunarr",
    description="Individual track download manager — Sonarr for music tracks",
    version="1.0.0",
    lifespan=lifespan,
)

# API routers
for r in [
    artist.router,
    album.router,
    track.router,
    command.router,
    queue.router,
    history.router,
    wanted.router,
    settings_api.router,
    system.router,
    search.router,
]:
    app.include_router(r)

# Serve the SPA frontend
_static = Path(__file__).parent.parent / "static"
if _static.exists():
    app.mount("/assets", StaticFiles(directory=str(_static)), name="static")

    @app.get("/", include_in_schema=False)
    @app.get("/{full_path:path}", include_in_schema=False)
    async def spa_fallback(full_path: str = ""):
        if full_path.startswith("api/"):
            from fastapi import HTTPException
            raise HTTPException(404)
        index = _static / "index.html"
        return FileResponse(str(index))
