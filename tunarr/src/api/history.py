from fastapi import APIRouter, Depends, Query
from sqlalchemy.orm import Session

from ..database import get_db
from ..models import History
from ..schemas import HistoryOut

router = APIRouter(prefix="/api/v3/history", tags=["history"])


@router.get("", response_model=dict)
def get_history(
    page: int = Query(1, ge=1),
    pageSize: int = Query(20, ge=1, le=100),
    artistId: int | None = Query(None),
    albumId: int | None = Query(None),
    db: Session = Depends(get_db),
):
    q = db.query(History)
    if artistId:
        q = q.filter(History.artist_id == artistId)
    if albumId:
        q = q.filter(History.album_id == albumId)
    total = q.count()
    items = q.order_by(History.date.desc()).offset((page - 1) * pageSize).limit(pageSize).all()
    records = [HistoryOut.from_orm(h) for h in items]
    return {
        "page": page,
        "pageSize": pageSize,
        "totalRecords": total,
        "records": [r.model_dump() for r in records],
    }
