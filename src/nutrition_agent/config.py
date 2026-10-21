"""設定：全部從環境變數（或 .env）讀取，模型 ID 不寫死在程式裡。"""

from functools import lru_cache

from pydantic_settings import BaseSettings, SettingsConfigDict

DEV_SESSION_SECRET = "dev-only-insecure-session-secret"
DEV_S3_SECRET_KEY = "nutrition-dev-secret"  # 與 compose 的 SeaweedFS 預設金鑰相同


class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_file=".env", extra="ignore")

    database_url: str = "postgresql://nutrition:nutrition@127.0.0.1:55432/nutrition"
    # "production"（預設）缺 SESSION_SECRET 會啟動失敗；本機開發／測試設 APP_ENV=development。
    app_env: str = "production"
    # 簽 session cookie 用；正式環境務必以環境變數提供並開啟 https_only。
    session_secret: str = ""
    session_https_only: bool = False
    # 照片物件儲存（S3 API）。預設對應 compose 的 SeaweedFS；換 AWS S3 或 R2 只改這幾項。
    # 讀寫走 internal；presigned URL 用 public 簽，必須是瀏覽器實際連的網址（host 不同就 403）。
    s3_internal_endpoint: str = "http://127.0.0.1:8333"
    s3_public_endpoint: str = "http://localhost:8333"
    s3_access_key: str = "nutrition"
    # 正式環境（APP_ENV 不是 development）仍用開發預設金鑰會拒絕啟動。
    s3_secret_key: str = DEV_S3_SECRET_KEY
    s3_bucket: str = "photos"
    s3_region: str = "us-east-1"
    photo_url_ttl_seconds: int = 900
    # 每個 S3 請求最多嘗試幾次（含第一次）；連不上時早點放棄，請求才不會卡住。
    s3_max_attempts: int = 2
    # 照片在物件儲存保留的天數；過期清理指令的預設值。
    photo_retention_days: int = 30
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


def resolve_s3_secret_key(settings: Settings) -> str:
    """建立 S3 client 時取得金鑰；正式環境仍是開發預設值就拒絕啟動。"""
    if settings.app_env != "development" and settings.s3_secret_key == DEV_S3_SECRET_KEY:
        raise RuntimeError("正式環境必須設定 S3_SECRET_KEY（本機開發請設 APP_ENV=development）")
    return settings.s3_secret_key
