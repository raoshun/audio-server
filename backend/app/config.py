from pathlib import Path

from pydantic import Field, HttpUrl, SecretStr
from pydantic_settings import BaseSettings, SettingsConfigDict

# List import removed; dwe_artist is now a simple string.


# 環境変数から設定を読み込むためのクラス
class Settings(BaseSettings):
    model_config = SettingsConfigDict(
        env_file=".env", env_file_encoding="utf-8", extra="ignore")
    navidrome_url: HttpUrl
    navidrome_user: str = Field()
    navidrome_password: SecretStr = Field()
    navidrome_timeout_seconds: int = Field(default=10, gt=0)
    dwe_music_dir: Path = Field(
        default=Path("/srv/dwe/music"),
        description="Base directory containing music files.")

    # The following paths are derived from ``dwe_music_dir``.
    # They are exposed as read‑only properties so they update automatically
    # when the base directory changes.

    @property
    def dwe_root_dir(self) -> Path:
        """Root directory for DWE operations.

        ``dwe_music_dir`` is ``<root>/music``; the root is two levels up.
        """
        return self.dwe_music_dir.parent.parent / "dwe"

    @property
    def dwe_navidrome_data_dir(self) -> Path:
        """Navidrome data directory derived from the music base.
        """
        return self.dwe_music_dir.parent / "navidrome" / "data"

    @property
    def dwe_navidrome_config_dir(self) -> Path:
        """Navidrome config directory derived from the music base.
        """
        return self.dwe_music_dir.parent / "navidrome" / "config"

    @property
    def dwe_staging_dir(self) -> Path:
        """Staging base directory derived from the music base.
        """
        return self.dwe_music_dir.parent / "staging"

    @property
    def dwe_staging_incoming_dir(self) -> Path:
        return self.dwe_staging_dir / "incoming"

    @property
    def dwe_staging_validated_dir(self) -> Path:
        return self.dwe_staging_dir / "validated"

    @property
    def dwe_staging_rejected_dir(self) -> Path:
        return self.dwe_staging_dir / "rejected"

    @property
    def dwe_sync_log_dir(self) -> Path:
        return self.dwe_music_dir.parent / "sync" / "logs"

    @property
    def dwe_sync_state_dir(self) -> Path:
        return self.dwe_music_dir.parent / "sync" / "state"
    # Single artist name for DWE operations. Previously a list; simplified
    # to a single string to reduce configuration complexity.
    dwe_artist: str = Field(
        default="Disney's World of English",
        description="The artist name to filter tracks by.")
