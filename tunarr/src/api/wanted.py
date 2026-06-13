from fastapi import APIRouter, Depends, Query
from sqlalchemy.orm import Session

from ..database import get_db
from ..models import Track
from ..schemas import TrackOut

router = APIRouter(prefix="/api/v3/wanted", tags=["wanted"])


@router.get("/missing", response_model=dict)
def wanted_missing(
    page: int = Query(1, ge=1),
    pageSize: int = Query(20, ge=1, le=100),
    db: Session = Depends(get_db),
):
    """All monitored tracks without a file (≈ Sonarr's Wanted > Missing episodes)."""
    q = db.query(Track).filter(Track.monitored == True, Track.has_file == False)
    total = q.count()
    items = q.order_by(Track.artist_id, Track.album_id, Track.absolute_track_number)
    items = items.offset((page - 1) * pageSize).limit(pageSize).all()
    records = [TrackOut.from_orm(t) for t in items]
    return {
        "page": page,
        "pageSize": pageSize,
        "totalRecords": total,
        "records": [r.model_dump() for r in records],
    }
