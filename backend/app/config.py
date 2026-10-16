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

    # LLM（Ollama）接続設定（Issue #12）。
    # Ollama は家庭内ネットワーク上のローカルサービスであり認証情報を持たない
    # ため、API キーは持たない。接続先・モデル・タイムアウトは環境変数のみから
    # 取得する（平文の秘密情報はコードへ置かない）。
    # コンテナ内からホストの Ollama へ到達するため、既定値は
    # `host.docker.internal`（docker-compose の extra_hosts で解決）とする。
    ollama_url: HttpUrl = Field(
        default="http://host.docker.internal:11434",
        description="Ollama API のベース URL。")
    ollama_model: str = Field(
        default="gemma4:e2b",
        description="プレイリスト生成に使う軽量モデル名。")
    ollama_timeout_seconds: int = Field(default=120, gt=0)
    ollama_num_predict: int = Field(
        default=2048,
        gt=0,
        description="LLM 応答の最大トークン数（構造化出力の切り詰め防止）。",
    )

    # プレイリスト生成の上限（Issue #12）。LLM へ渡すカタログはこの件数で切る。
    playlist_catalog_limit: int = Field(
        default=200,
        gt=0,
        description="LLM へ渡す Navidrome カタログの最大トラック数。")
    playlist_default_size: int = Field(
        default=10,
        gt=0,
        description="指示で曲数が指定されていない場合の既定のプレイリスト長。")
    playlist_max_size: int = Field(
        default=50,
        gt=0,
        description="プレイリストの最大曲数。")

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
