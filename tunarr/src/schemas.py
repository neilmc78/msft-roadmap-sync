from __future__ import annotations
import json
from datetime import datetime
from typing import Any
from pydantic import BaseModel, field_validator


def _parse_json_field(v):
    if isinstance(v, str):
        try:
            return json.loads(v)
        except Exception:
            return v
    return v


# ─── Quality ───────────────────────────────────────────────────────────────────

class QualityItem(BaseModel):
    id: int
    name: str

class Quality(BaseModel):
    quality: QualityItem
    revision: dict = {"version": 1, "real": 0}


# ─── Root Folder ───────────────────────────────────────────────────────────────

class RootFolderOut(BaseModel):
    id: int
    path: str
    freeSpace: int = 0
    totalSpace: int = 0

    model_config = {"from_attributes": True}


class RootFolderIn(BaseModel):
    path: str


# ─── Quality Profile ───────────────────────────────────────────────────────────

QUALITY_DEFINITIONS = [
    {"id": 0, "name": "Unknown"},
    {"id": 1, "name": "MP3-128"},
    {"id": 2, "name": "MP3-256"},
    {"id": 3, "name": "MP3-320"},
    {"id": 4, "name": "AAC-256"},
    {"id": 5, "name": "AAC-320"},
    {"id": 6, "name": "FLAC"},
    {"id": 7, "name": "FLAC 24bit"},
]

class QualityProfileOut(BaseModel):
    id: int
    name: str
    upgradeAllowed: bool
    cutoff: int
    items: list[dict]

    model_config = {"from_attributes": True}

    @field_validator("items", mode="before")
    @classmethod
    def parse_items(cls, v):
        return _parse_json_field(v)


class QualityProfileIn(BaseModel):
    name: str
    upgradeAllowed: bool = True
    cutoff: int = 3
    items: list[dict] = []


# ─── Artist ────────────────────────────────────────────────────────────────────

class ArtistOut(BaseModel):
    id: int
    musicBrainzId: str
    artistName: str
    sortName: str
    disambiguation: str
    overview: str
    status: str
    artistType: str
    monitored: bool
    albumFolder: bool
    rootFolderPath: str
    qualityProfileId: int | None
    added: str
    images: list[dict]
    links: list[dict]
    genres: list[str]
    tags: list[int]
    statistics: dict

    model_config = {"from_attributes": True}

    @classmethod
    def from_orm_artist(cls, a) -> "ArtistOut":
        total = len(a.albums)
        monitored_albums = sum(1 for al in a.albums if al.monitored)
        total_tracks = sum(len(al.tracks) for al in a.albums)
        file_count = sum(1 for al in a.albums for t in al.tracks if t.has_file)
        missing = sum(1 for al in a.albums for t in al.tracks if t.monitored and not t.has_file)
        return cls(
            id=a.id,
            musicBrainzId=a.musicbrainz_id,
            artistName=a.name,
            sortName=a.sort_name or a.name,
            disambiguation=a.disambiguation or "",
            overview=a.overview or "",
            status=a.status or "active",
            artistType=a.artist_type or "",
            monitored=a.monitored,
            albumFolder=a.album_folder,
            rootFolderPath=a.root_folder_path or "",
            qualityProfileId=a.quality_profile_id,
            added=a.added.isoformat() if a.added else "",
            images=_parse_json_field(a.images) or [],
            links=_parse_json_field(a.links) or [],
            genres=_parse_json_field(a.genres) or [],
            tags=_parse_json_field(a.tags) or [],
            statistics={
                "albumCount": total,
                "monitoredAlbumCount": monitored_albums,
                "trackCount": total_tracks,
                "trackFileCount": file_count,
                "totalTrackCount": total_tracks,
                "percentOfTracks": (file_count / total_tracks * 100) if total_tracks else 0,
                "sizeOnDisk": 0,
                "missingTrackCount": missing,
            },
        )


class ArtistIn(BaseModel):
    musicBrainzId: str
    artistName: str
    monitored: bool = True
    albumFolder: bool = True
    rootFolderPath: str = ""
    qualityProfileId: int | None = None
    addOptions: dict = {}


class ArtistUpdate(BaseModel):
    monitored: bool | None = None
    albumFolder: bool | None = None
    rootFolderPath: str | None = None
    qualityProfileId: int | None = None


# ─── Album ─────────────────────────────────────────────────────────────────────

class AlbumOut(BaseModel):
    id: int
    musicBrainzId: str
    artistId: int
    title: str
    overview: str
    releaseDate: str
    albumType: str
    secondaryTypes: list[str]
    monitored: bool
    anyTracksMissing: bool
    images: list[dict]
    links: list[dict]
    genres: list[str]
    labels: list[dict]
    ratings: dict
    statistics: dict

    model_config = {"from_attributes": True}

    @classmethod
    def from_orm_album(cls, al) -> "AlbumOut":
        total_tracks = len(al.tracks)
        file_count = sum(1 for t in al.tracks if t.has_file)
        return cls(
            id=al.id,
            musicBrainzId=al.musicbrainz_id,
            artistId=al.artist_id,
            title=al.title,
            overview=al.overview or "",
            releaseDate=al.release_date or "",
            albumType=al.album_type or "Album",
            secondaryTypes=_parse_json_field(al.secondary_types) or [],
            monitored=al.monitored,
            anyTracksMissing=al.any_tracks_missing,
            images=_parse_json_field(al.images) or [],
            links=_parse_json_field(al.links) or [],
            genres=_parse_json_field(al.genres) or [],
            labels=_parse_json_field(al.labels) or [],
            ratings=_parse_json_field(al.ratings) or {"count": 0, "value": 0},
            statistics={
                "trackCount": total_tracks,
                "trackFileCount": file_count,
                "totalTrackCount": total_tracks,
                "percentOfTracks": (file_count / total_tracks * 100) if total_tracks else 0,
                "sizeOnDisk": 0,
            },
        )


class AlbumUpdate(BaseModel):
    monitored: bool | None = None


# ─── Track ─────────────────────────────────────────────────────────────────────

class TrackOut(BaseModel):
    id: int
    musicBrainzId: str
    albumId: int
    artistId: int
    trackNumber: str
    absoluteTrackNumber: int
    discNumber: int
    title: str
    duration: int
    explicit: bool
    monitored: bool
    hasFile: bool
    trackFileId: int | None
    ratings: dict

    model_config = {"from_attributes": True}

    @classmethod
    def from_orm(cls, t) -> "TrackOut":
        return cls(
            id=t.id,
            musicBrainzId=t.musicbrainz_id or "",
            albumId=t.album_id,
            artistId=t.artist_id,
            trackNumber=t.track_number or "",
            absoluteTrackNumber=t.absolute_track_number or 0,
            discNumber=t.disc_number or 1,
            title=t.title,
            duration=t.duration or 0,
            explicit=t.explicit or False,
            monitored=t.monitored,
            hasFile=t.has_file,
            trackFileId=t.track_file_id,
            ratings=_parse_json_field(t.ratings) or {"count": 0, "value": 0},
        )


class TrackUpdate(BaseModel):
    monitored: bool | None = None


class TrackMonitorBulk(BaseModel):
    trackIds: list[int]
    monitored: bool


# ─── Track File ────────────────────────────────────────────────────────────────

class TrackFileOut(BaseModel):
    id: int
    trackId: int | None
    artistId: int
    albumId: int
    relativePath: str
    path: str
    size: int
    dateAdded: str
    quality: dict
    mediaInfo: dict

    model_config = {"from_attributes": True}

    @classmethod
    def from_orm(cls, f) -> "TrackFileOut":
        return cls(
            id=f.id,
            trackId=f.track_id,
            artistId=f.artist_id,
            albumId=f.album_id,
            relativePath=f.relative_path,
            path=f.path,
            size=f.size or 0,
            dateAdded=f.date_added.isoformat() if f.date_added else "",
            quality=_parse_json_field(f.quality) or {},
            mediaInfo=_parse_json_field(f.media_info) or {},
        )


# ─── Download Queue ─────────────────────────────────────────────────────────────

class QueueOut(BaseModel):
    id: int
    trackId: int | None
    albumId: int | None
    artistId: int
    title: str
    size: int
    sizeleft: int
    status: str
    protocol: str
    indexer: str
    downloadId: str
    added: str
    progress: float
    errorMessage: str
    artistName: str = ""
    trackTitle: str = ""
    albumTitle: str = ""

    model_config = {"from_attributes": True}

    @classmethod
    def from_orm(cls, q) -> "QueueOut":
        return cls(
            id=q.id,
            trackId=q.track_id,
            albumId=q.album_id,
            artistId=q.artist_id,
            title=q.title,
            size=q.size or 0,
            sizeleft=q.size_left or 0,
            status=q.status,
            protocol=q.protocol,
            indexer=q.indexer or "",
            downloadId=q.download_id or "",
            added=q.added.isoformat() if q.added else "",
            progress=q.progress or 0.0,
            errorMessage=q.error_message or "",
            artistName=q.artist.name if q.artist else "",
            trackTitle=q.track.title if q.track else "",
            albumTitle=q.album.title if q.album else "",
        )


# ─── History ───────────────────────────────────────────────────────────────────

class HistoryOut(BaseModel):
    id: int
    trackId: int | None
    albumId: int | None
    artistId: int
    sourceTitle: str
    quality: dict
    eventType: str
    date: str
    data: dict
    artistName: str = ""
    trackTitle: str = ""
    albumTitle: str = ""

    model_config = {"from_attributes": True}

    @classmethod
    def from_orm(cls, h) -> "HistoryOut":
        return cls(
            id=h.id,
            trackId=h.track_id,
            albumId=h.album_id,
            artistId=h.artist_id,
            sourceTitle=h.source_title or "",
            quality=_parse_json_field(h.quality) or {},
            eventType=h.event_type,
            date=h.date.isoformat() if h.date else "",
            data=_parse_json_field(h.data) or {},
            artistName=h.artist.name if h.artist else "",
            trackTitle=h.track.title if h.track else "",
            albumTitle=h.album.title if h.album else "",
        )


# ─── Command ───────────────────────────────────────────────────────────────────

class CommandIn(BaseModel):
    name: str
    trackIds: list[int] = []
    albumId: int | None = None
    artistId: int | None = None


class CommandOut(BaseModel):
    id: int
    name: str
    status: str
    queued: str
    started: str | None = None
    ended: str | None = None
    message: str = ""


# ─── MusicBrainz search result (lookup) ────────────────────────────────────────

class ArtistLookup(BaseModel):
    musicBrainzId: str
    artistName: str
    sortName: str
    disambiguation: str = ""
    overview: str = ""
    status: str = ""
    artistType: str = ""
    images: list[dict] = []
    links: list[dict] = []
    genres: list[str] = []
