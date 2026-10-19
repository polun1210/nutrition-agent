"""設定：正式環境缺少 session 密鑰時拒絕啟動。"""

import pytest

from nutrition_agent.config import Settings, resolve_session_secret


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
