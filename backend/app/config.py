from pydantic_settings import BaseSettings, SettingsConfigDict
from pydantic import SecretStr, Field, HttpUrl


# 環境変数から設定を読み込むためのクラス
class Settings(BaseSettings):
    model_config = SettingsConfigDict(
        env_file=".env", env_file_encoding="utf-8", extra="ignore")
    navidrome_url: HttpUrl
    navidrome_user: str = Field()
    navidrome_password: SecretStr = Field()
    navidrome_timeout_seconds: int = Field(default=10, gt=0)
    dwe_artist: str = Field(
        default="Disney's World of English",
        description="The artist name to filter tracks by."
    )
