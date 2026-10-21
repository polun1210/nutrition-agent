"""設定：正式環境缺少 session 密鑰、或 S3 金鑰仍是開發預設值時拒絕啟動。"""

import pytest

from nutrition_agent.config import (
    DEV_S3_SECRET_KEY,
    Settings,
    resolve_s3_secret_key,
    resolve_session_secret,
)


def test_production_without_session_secret_fails() -> None:
    settings = Settings(_env_file=None, app_env="production", session_secret="")
    with pytest.raises(RuntimeError, match="SESSION_SECRET"):
        resolve_session_secret(settings)


def test_production_with_session_secret_is_used() -> None:
    settings = Settings(_env_file=None, app_env="production", session_secret="x" * 32)
    assert resolve_session_secret(settings) == "x" * 32


def test_development_falls_back_to_dev_secret() -> None:
    settings = Settings(_env_file=None, app_env="development", session_secret="")
    assert resolve_session_secret(settings)


def test_production_with_dev_s3_secret_key_fails() -> None:
    settings = Settings(_env_file=None, app_env="production", s3_secret_key=DEV_S3_SECRET_KEY)
    with pytest.raises(RuntimeError, match="S3_SECRET_KEY"):
        resolve_s3_secret_key(settings)


def test_production_with_own_s3_secret_key_is_used() -> None:
    settings = Settings(_env_file=None, app_env="production", s3_secret_key="y" * 32)
    assert resolve_s3_secret_key(settings) == "y" * 32


def test_development_allows_dev_s3_secret_key() -> None:
    settings = Settings(_env_file=None, app_env="development")
    assert resolve_s3_secret_key(settings) == DEV_S3_SECRET_KEY
