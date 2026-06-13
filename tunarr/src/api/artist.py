import json
from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session

from ..database import get_db
from ..models import Artist, Album, Track, QualityProfile
from ..schemas import ArtistOut, ArtistIn, ArtistUpdate, ArtistLookup
from ..services import musicbrainz as mb

router = APIRouter(prefix="/api/v3/artist", tags=["artist"])


@router.get("", response_model=list[ArtistOut])
def list_artists(db: Session = Depends(get_db)):
    artists = db.query(Artist).all()
    return [ArtistOut.from_orm_artist(a) for a in artists]


@router.get("/{artist_id}", response_model=ArtistOut)
def get_artist(artist_id: int, db: Session = Depends(get_db)):
    a = db.get(Artist, artist_id)
    if not a:
        raise HTTPException(404, "Artist not found")
    return ArtistOut.from_orm_artist(a)


@router.post("", response_model=ArtistOut, status_code=201)
async def add_artist(body: ArtistIn, db: Session = Depends(get_db)):
    existing = db.query(Artist).filter(Artist.musicbrainz_id == body.musicBrainzId).first()
    if existing:
        raise HTTPException(400, "Artist already added")

    # Fetch full metadata from MusicBrainz
    try:
        mb_data = await mb.get_artist(body.musicBrainzId)
    except Exception as e:
        raise HTTPException(502, f"MusicBrainz lookup failed: {e}")

    # Ensure quality profile exists (use first if not specified)
    qp_id = body.qualityProfileId
    if not qp_id:
        qp = db.query(QualityProfile).first()
        qp_id = qp.id if qp else None

    artist = Artist(
        musicbrainz_id=body.musicBrainzId,
        name=mb_data.get("artistName") or body.artistName,
        sort_name=mb_data.get("sortName") or body.artistName,
        disambiguation=mb_data.get("disambiguation", ""),
        overview=mb_data.get("overview", ""),
        status=mb_data.get("status", "active"),
        artist_type=mb_data.get("artistType", ""),
        monitored=body.monitored,
        album_folder=body.albumFolder,
        root_folder_path=body.rootFolderPath,
        quality_profile_id=qp_id,
        images=json.dumps(mb_data.get("images", [])),
        links=json.dumps(mb_data.get("links", [])),
        genres=json.dumps(mb_data.get("genres", [])),
        tags=json.dumps([]),
    )
    db.add(artist)
    db.flush()

    # Create albums + tracks from release groups
    add_all_albums = body.addOptions.get("addType", "manual") == "automatic"
    for rg in mb_data.get("releaseGroups", []):
        album = Album(
            musicbrainz_id=rg["musicBrainzId"],
            artist_id=artist.id,
            title=rg["title"],
            album_type=rg.get("albumType", "Album"),
            secondary_types=json.dumps(rg.get("secondaryTypes", [])),
            release_date=rg.get("releaseDate", ""),
            monitored=body.monitored and add_all_albums,
            images=json.dumps([]),
            links=json.dumps([]),
            genres=json.dumps([]),
            labels=json.dumps([]),
        )
        db.add(album)

    db.commit()
    db.refresh(artist)
    return ArtistOut.from_orm_artist(artist)


@router.put("/{artist_id}", response_model=ArtistOut)
def update_artist(artist_id: int, body: ArtistUpdate, db: Session = Depends(get_db)):
    a = db.get(Artist, artist_id)
    if not a:
        raise HTTPException(404, "Artist not found")
    if body.monitored is not None:
        a.monitored = body.monitored
    if body.albumFolder is not None:
        a.album_folder = body.albumFolder
    if body.rootFolderPath is not None:
        a.root_folder_path = body.rootFolderPath
    if body.qualityProfileId is not None:
        a.quality_profile_id = body.qualityProfileId
    db.commit()
    db.refresh(a)
    return ArtistOut.from_orm_artist(a)


@router.delete("/{artist_id}", status_code=200)
def delete_artist(artist_id: int, deleteFiles: bool = False, db: Session = Depends(get_db)):
    a = db.get(Artist, artist_id)
    if not a:
        raise HTTPException(404, "Artist not found")
    if deleteFiles:
        import os
        for album in a.albums:
            for track in album.tracks:
                if track.track_file:
                    try:
                        os.remove(track.track_file.path)
                    except OSError:
                        pass
    db.delete(a)
    db.commit()
    return {}


@router.get("/lookup/search", response_model=list[ArtistLookup])
async def lookup_artist(term: str, db: Session = Depends(get_db)):
    try:
        results = await mb.search_artists(term)
    except Exception as e:
        raise HTTPException(502, f"MusicBrainz search failed: {e}")
    return [ArtistLookup(**r) for r in results]
