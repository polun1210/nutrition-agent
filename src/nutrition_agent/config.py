"""設定：全部從環境變數（或 .env）讀取，模型 ID 不寫死在程式裡。"""

from functools import lru_cache

from pydantic_settings import BaseSettings, SettingsConfigDict

DEV_SESSION_SECRET = "dev-only-insecure-session-secret"


class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_file=".env", extra="ignore")

    database_url: str = "postgresql://nutrition:nutrition@127.0.0.1:55432/nutrition"
    # "production"（預設）缺 SESSION_SECRET 會啟動失敗；本機開發／測試設 APP_ENV=development。
    app_env: str = "production"
    # 簽 session cookie 用；正式環境務必以環境變數提供並開啟 https_only。
    session_secret: str = ""
    session_https_only: bool = False
    # 保健食品照片存放的本機資料夾（compose 以 volume 掛載）。
    photo_dir: str = "data/photos"
    openrouter_api_key: str = ""
    openrouter_base_url: str = "https://openrouter.ai/api/v1"
    openrouter_provider: str = ""
    vlm_model: str = ""
    llm_model: str = ""
    embedding_model: str = ""


@lru_cache
def get_settings() -> Settings:
    return Settings()


def to_sqlalchemy_url(url: str) -> str:
    """alembic 走 SQLAlchemy，需指定 psycopg (v3) 驅動。"""
    return url.replace("postgresql://", "postgresql+psycopg://", 1)


def resolve_session_secret(settings: Settings) -> str:
    """啟動 API 時取得 session 密鑰；正式環境缺值就拒絕啟動，只有明確的開發環境才用內建值。"""
    if settings.session_secret:
        return settings.session_secret
    if settings.app_env != "development":
        raise RuntimeError("正式環境必須設定 SESSION_SECRET（本機開發請設 APP_ENV=development）")
    return DEV_SESSION_SECRET
