from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy.orm import Session

from ..database import get_db
from ..models import Track
from ..schemas import TrackOut, TrackUpdate, TrackMonitorBulk

router = APIRouter(prefix="/api/v3/track", tags=["track"])


@router.get("", response_model=list[TrackOut])
def list_tracks(
    albumId: int | None = Query(None),
    artistId: int | None = Query(None),
    db: Session = Depends(get_db),
):
    q = db.query(Track)
    if albumId is not None:
        q = q.filter(Track.album_id == albumId)
    if artistId is not None:
        q = q.filter(Track.artist_id == artistId)
    tracks = q.order_by(Track.disc_number, Track.absolute_track_number).all()
    return [TrackOut.from_orm(t) for t in tracks]


@router.get("/{track_id}", response_model=TrackOut)
def get_track(track_id: int, db: Session = Depends(get_db)):
    t = db.get(Track, track_id)
    if not t:
        raise HTTPException(404, "Track not found")
    return TrackOut.from_orm(t)


@router.put("/{track_id}", response_model=TrackOut)
def update_track(track_id: int, body: TrackUpdate, db: Session = Depends(get_db)):
    t = db.get(Track, track_id)
    if not t:
        raise HTTPException(404, "Track not found")
    if body.monitored is not None:
        t.monitored = body.monitored
    db.commit()
    db.refresh(t)
    return TrackOut.from_orm(t)


@router.put("/monitor", response_model=list[TrackOut])
def monitor_tracks(body: TrackMonitorBulk, db: Session = Depends(get_db)):
    """Bulk-set monitored status on a list of track IDs."""
    updated = []
    for tid in body.trackIds:
        t = db.get(Track, tid)
        if t:
            t.monitored = body.monitored
            updated.append(t)
    db.commit()
    return [TrackOut.from_orm(t) for t in updated]
