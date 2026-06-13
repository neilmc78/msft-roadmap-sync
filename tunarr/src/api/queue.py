from pydantic import BaseModel
from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session

from ..database import get_db
from ..models import DownloadQueue
from ..schemas import QueueOut
from ..download_manager import enqueue_track_download

router = APIRouter(prefix="/api/v3/queue", tags=["queue"])


class GrabRequest(BaseModel):
    trackId: int
    albumId: int | None = None
    artistId: int
    sourceUrl: str
    title: str
    protocol: str = "ytdlp"


@router.post("/grab", status_code=201)
async def grab_track(body: GrabRequest, db: Session = Depends(get_db)):
    """Directly enqueue a track download with a known source URL."""
    item = await enqueue_track_download(
        db=db,
        track_id=body.trackId,
        source_url=body.sourceUrl,
        source_title=body.title,
        protocol=body.protocol,
    )
    return QueueOut.from_orm(item).model_dump()


@router.get("", response_model=dict)
def get_queue(db: Session = Depends(get_db)):
    items = db.query(DownloadQueue).filter(
        DownloadQueue.status.notin_(["completed"])
    ).order_by(DownloadQueue.added.desc()).all()
    records = [QueueOut.from_orm(i) for i in items]
    return {
        "page": 1,
        "pageSize": len(records),
        "totalRecords": len(records),
        "records": [r.model_dump() for r in records],
    }


@router.delete("/{queue_id}", status_code=200)
def remove_from_queue(queue_id: int, blacklist: bool = False, db: Session = Depends(get_db)):
    item = db.get(DownloadQueue, queue_id)
    if not item:
        raise HTTPException(404, "Queue item not found")
    db.delete(item)
    db.commit()
    return {}


@router.delete("", status_code=200)
def clear_completed_queue(db: Session = Depends(get_db)):
    db.query(DownloadQueue).filter(DownloadQueue.status == "completed").delete()
    db.commit()
    return {}
