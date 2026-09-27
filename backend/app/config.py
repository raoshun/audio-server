from pathlib import Path

from pydantic import Field, HttpUrl, SecretStr
from pydantic_settings import BaseSettings, SettingsConfigDict

# List のインポートは削除されました。dwe_artist はシンプルな文字列になりました。


# 環境変数から設定を読み込むクラスです
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

    # 以下のパスは ``dwe_music_dir`` から派生します。
    # 読み取り専用プロパティとして公開され、ベースディレクトリが変更されたときに自動的に更新されます。

    @property
    def dwe_root_dir(self) -> Path:
        """DWE 操作のルートディレクトリ。

        ``dwe_music_dir`` は ``<root>/music`` で、ルートは2階層上にあります。
        """
        return self.dwe_music_dir.parent.parent / "dwe"

    @property
    def dwe_navidrome_data_dir(self) -> Path:
        """音楽ベースから導出された Navidrome データディレクトリ。
        """
        return self.dwe_music_dir.parent / "navidrome" / "data"

    @property
    def dwe_navidrome_config_dir(self) -> Path:
        """音楽ベースから導出された Navidrome 設定ディレクトリ。
        """
        return self.dwe_music_dir.parent / "navidrome" / "config"

    @property
    def dwe_staging_dir(self) -> Path:
        """音楽ベースから導出されたステージングのベースディレクトリ。
        """
        return self.dwe_music_dir.parent / "staging"

    @property
    def dwe_staging_incoming_dir(self) -> Path:
        return self.dwe_staging_dir / "incoming"  # 受信ディレクトリ

    @property
    def dwe_staging_validated_dir(self) -> Path:
        return self.dwe_staging_dir / "validated"  # 検証済みディレクトリ

    @property
    def dwe_staging_rejected_dir(self) -> Path:
        return self.dwe_staging_dir / "rejected"  # 却下ディレクトリ

    @property
    def dwe_sync_log_dir(self) -> Path:
        return self.dwe_music_dir.parent / "sync" / "logs"  # 同期ログディレクトリ

    @property
    def dwe_sync_state_dir(self) -> Path:
        return self.dwe_music_dir.parent / "sync" / "state"  # 同期状態ディレクトリ
    # DWE 操作用のシングルアーティスト名です。以前はリストでしたが、設定の複雑さを減らすため文字列に簡素化しました。
    dwe_artist: str = Field(
        default="Disney's World of English",
        description="トラックをフィルタリングするアーティスト名。")
