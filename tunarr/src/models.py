import json
from datetime import datetime
from sqlalchemy import (
    Boolean, Column, DateTime, Float, ForeignKey,
    Integer, String, Text, func,
)
from sqlalchemy.orm import relationship
from .database import Base


class _JsonColumn(Text):
    """Stores Python list/dict as JSON text."""


def _json_get(obj, attr):
    raw = object.__getattribute__(obj, attr)
    if isinstance(raw, str):
        try:
            return json.loads(raw)
        except (json.JSONDecodeError, TypeError):
            return raw
    return raw


class Artist(Base):
    __tablename__ = "artists"

    id = Column(Integer, primary_key=True, index=True)
    musicbrainz_id = Column(String, unique=True, index=True, nullable=False)
    name = Column(String, nullable=False)
    sort_name = Column(String)
    disambiguation = Column(String, default="")
    overview = Column(Text, default="")
    status = Column(String, default="active")  # active, ended
    artist_type = Column(String, default="")   # Person, Group, Orchestra
    monitored = Column(Boolean, default=True)
    album_folder = Column(Boolean, default=True)
    root_folder_path = Column(String, default="")
    quality_profile_id = Column(Integer, ForeignKey("quality_profiles.id"), nullable=True)
    added = Column(DateTime, default=func.now())
    images = Column(_JsonColumn, default="[]")
    links = Column(_JsonColumn, default="[]")
    genres = Column(_JsonColumn, default="[]")
    tags = Column(_JsonColumn, default="[]")

    albums = relationship("Album", back_populates="artist", cascade="all, delete-orphan")
    quality_profile = relationship("QualityProfile", foreign_keys=[quality_profile_id])


class Album(Base):
    __tablename__ = "albums"

    id = Column(Integer, primary_key=True, index=True)
    musicbrainz_id = Column(String, unique=True, index=True, nullable=False)
    artist_id = Column(Integer, ForeignKey("artists.id"), nullable=False)
    title = Column(String, nullable=False)
    overview = Column(Text, default="")
    release_date = Column(String, default="")
    album_type = Column(String, default="Album")  # Album, Single, EP, Broadcast
    secondary_types = Column(_JsonColumn, default="[]")
    monitored = Column(Boolean, default=True)
    images = Column(_JsonColumn, default="[]")
    links = Column(_JsonColumn, default="[]")
    genres = Column(_JsonColumn, default="[]")
    labels = Column(_JsonColumn, default="[]")
    ratings = Column(_JsonColumn, default='{"count": 0, "value": 0}')

    artist = relationship("Artist", back_populates="albums")
    tracks = relationship("Track", back_populates="album", cascade="all, delete-orphan")

    @property
    def track_count(self) -> int:
        return len(self.tracks)

    @property
    def any_tracks_missing(self) -> bool:
        return any(t.monitored and not t.has_file for t in self.tracks)


class Track(Base):
    __tablename__ = "tracks"

    id = Column(Integer, primary_key=True, index=True)
    musicbrainz_id = Column(String, index=True)
    album_id = Column(Integer, ForeignKey("albums.id"), nullable=False)
    artist_id = Column(Integer, ForeignKey("artists.id"), nullable=False)
    track_number = Column(String, default="")
    absolute_track_number = Column(Integer, default=0)
    disc_number = Column(Integer, default=1)
    title = Column(String, nullable=False)
    duration = Column(Integer, default=0)  # milliseconds
    explicit = Column(Boolean, default=False)
    monitored = Column(Boolean, default=True)
    has_file = Column(Boolean, default=False)
    track_file_id = Column(Integer, ForeignKey("track_files.id"), nullable=True)
    ratings = Column(_JsonColumn, default='{"count": 0, "value": 0}')

    album = relationship("Album", back_populates="tracks")
    artist = relationship("Artist", foreign_keys=[artist_id])
    track_file = relationship("TrackFile", foreign_keys=[track_file_id])


class TrackFile(Base):
    __tablename__ = "track_files"

    id = Column(Integer, primary_key=True, index=True)
    track_id = Column(Integer, ForeignKey("tracks.id"), nullable=True)
    artist_id = Column(Integer, ForeignKey("artists.id"), nullable=False)
    album_id = Column(Integer, ForeignKey("albums.id"), nullable=False)
    relative_path = Column(String, nullable=False)
    path = Column(String, nullable=False)
    size = Column(Integer, default=0)
    date_added = Column(DateTime, default=func.now())
    quality = Column(_JsonColumn, default='{"quality": {"id": 0, "name": "Unknown"}}')
    media_info = Column(_JsonColumn, default="{}")


class DownloadQueue(Base):
    __tablename__ = "download_queue"

    id = Column(Integer, primary_key=True, index=True)
    track_id = Column(Integer, ForeignKey("tracks.id"), nullable=True)
    album_id = Column(Integer, ForeignKey("albums.id"), nullable=True)
    artist_id = Column(Integer, ForeignKey("artists.id"), nullable=False)
    download_id = Column(String, index=True)
    title = Column(String, nullable=False)
    size = Column(Integer, default=0)
    size_left = Column(Integer, default=0)
    status = Column(String, default="queued")  # queued, downloading, completed, failed, importing
    protocol = Column(String, default="ytdlp")  # ytdlp, torrent, usenet
    indexer = Column(String, default="")
    source_url = Column(String, default="")
    output_path = Column(String, default="")
    added = Column(DateTime, default=func.now())
    error_message = Column(String, default="")
    progress = Column(Float, default=0.0)

    track = relationship("Track", foreign_keys=[track_id])
    album = relationship("Album", foreign_keys=[album_id])
    artist = relationship("Artist", foreign_keys=[artist_id])


class History(Base):
    __tablename__ = "history"

    id = Column(Integer, primary_key=True, index=True)
    track_id = Column(Integer, ForeignKey("tracks.id"), nullable=True)
    album_id = Column(Integer, ForeignKey("albums.id"), nullable=True)
    artist_id = Column(Integer, ForeignKey("artists.id"), nullable=False)
    source_title = Column(String, default="")
    quality = Column(_JsonColumn, default='{"quality": {"id": 0, "name": "Unknown"}}')
    event_type = Column(String, nullable=False)  # grabbed, trackFileImported, downloadFailed, etc.
    date = Column(DateTime, default=func.now())
    data = Column(_JsonColumn, default="{}")

    track = relationship("Track", foreign_keys=[track_id])
    album = relationship("Album", foreign_keys=[album_id])
    artist = relationship("Artist", foreign_keys=[artist_id])


class RootFolder(Base):
    __tablename__ = "root_folders"

    id = Column(Integer, primary_key=True, index=True)
    path = Column(String, unique=True, nullable=False)


class QualityProfile(Base):
    __tablename__ = "quality_profiles"

    id = Column(Integer, primary_key=True, index=True)
    name = Column(String, nullable=False)
    upgrade_allowed = Column(Boolean, default=True)
    cutoff = Column(Integer, default=3)  # quality id at which to stop upgrading
    items = Column(_JsonColumn, default="[]")


class AppConfig(Base):
    __tablename__ = "app_config"

    id = Column(Integer, primary_key=True, index=True)
    key = Column(String, unique=True, nullable=False)
    value = Column(Text, default="")
