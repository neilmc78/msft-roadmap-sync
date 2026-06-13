import os
from pathlib import Path
from pydantic_settings import BaseSettings


class Settings(BaseSettings):
    app_name: str = "Tunarr"
    data_dir: str = os.environ.get("TUNARR_DATA_DIR", "./config")
    music_dir: str = os.environ.get("TUNARR_MUSIC_DIR", "./music")
    port: int = 8686
    log_level: str = "info"

    # MusicBrainz
    mb_user_agent: str = "Tunarr/1.0 (https://github.com/tunarr/tunarr)"
    mb_rate_limit: float = 1.0  # seconds between requests

    # Download concurrency
    max_concurrent_downloads: int = 3

    class Config:
        env_prefix = "TUNARR_"

    @property
    def db_path(self) -> str:
        return str(Path(self.data_dir) / "tunarr.db")

    @property
    def downloads_dir(self) -> str:
        return str(Path(self.data_dir) / "downloads")


settings = Settings()
