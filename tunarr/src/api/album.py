import json
from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy.orm import Session

from ..database import get_db
from ..models import Album, Artist, Track
from ..schemas import AlbumOut, AlbumUpdate
from ..services import musicbrainz as mb

router = APIRouter(prefix="/api/v3/album", tags=["album"])


@router.get("", response_model=list[AlbumOut])
def list_albums(
    artistId: int | None = Query(None),
    db: Session = Depends(get_db),
):
    q = db.query(Album)
    if artistId is not None:
        q = q.filter(Album.artist_id == artistId)
    albums = q.all()
    return [AlbumOut.from_orm_album(al) for al in albums]


@router.get("/{album_id}", response_model=AlbumOut)
def get_album(album_id: int, db: Session = Depends(get_db)):
    al = db.get(Album, album_id)
    if not al:
        raise HTTPException(404, "Album not found")
    return AlbumOut.from_orm_album(al)


@router.put("/{album_id}", response_model=AlbumOut)
def update_album(album_id: int, body: AlbumUpdate, db: Session = Depends(get_db)):
    al = db.get(Album, album_id)
    if not al:
        raise HTTPException(404, "Album not found")
    if body.monitored is not None:
        al.monitored = body.monitored
        # cascade to tracks
        for t in al.tracks:
            t.monitored = body.monitored
    db.commit()
    db.refresh(al)
    return AlbumOut.from_orm_album(al)


@router.post("/{album_id}/tracks/refresh")
async def refresh_album_tracks(album_id: int, db: Session = Depends(get_db)):
    """Fetch full track listing from MusicBrainz and populate the Track table."""
    al = db.get(Album, album_id)
    if not al:
        raise HTTPException(404, "Album not found")

    try:
        mb_data = await mb.get_release_group_with_tracks(al.musicbrainz_id)
    except Exception as e:
        raise HTTPException(502, f"MusicBrainz lookup failed: {e}")

    # Update album metadata
    al.overview = mb_data.get("overview", al.overview)
    al.images = json.dumps(mb_data.get("images", []))
    al.links = json.dumps(mb_data.get("links", []))
    al.genres = json.dumps(mb_data.get("genres", []))
    if mb_data.get("releaseDate"):
        al.release_date = mb_data["releaseDate"]

    existing_mbids = {t.musicbrainz_id for t in al.tracks if t.musicbrainz_id}

    for t_data in mb_data.get("tracks", []):
        if t_data["musicBrainzId"] in existing_mbids:
            continue
        track = Track(
            musicbrainz_id=t_data["musicBrainzId"],
            album_id=al.id,
            artist_id=al.artist_id,
            title=t_data["title"],
            track_number=t_data["trackNumber"],
            absolute_track_number=t_data["absoluteTrackNumber"],
            disc_number=t_data["discNumber"],
            duration=t_data.get("duration", 0),
            explicit=t_data.get("explicit", False),
            monitored=al.monitored,
        )
        db.add(track)

    db.commit()
    db.refresh(al)
    return AlbumOut.from_orm_album(al)
