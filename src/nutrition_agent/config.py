"""設定：全部從環境變數（或 .env）讀取，模型 ID 不寫死在程式裡。"""

from functools import lru_cache

from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_file=".env", extra="ignore")

    database_url: str = "postgresql://nutrition:nutrition@127.0.0.1:55432/nutrition"
    # 簽 session cookie 用；正式環境務必以環境變數換掉並開啟 https_only。
    session_secret: str = "dev-only-insecure-session-secret"
    session_https_only: bool = False
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
