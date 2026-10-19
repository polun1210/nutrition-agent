"""Playwright 煙霧測試用的後端：重建獨立資料庫、跑 migration、啟動 API。

用法（由 web/playwright.config.ts 呼叫）：
    uv run python scripts/e2e_server.py [port]
資料庫連線取自 E2E_DATABASE_URL，預設 nutrition_e2e（需要本機 db 已啟動：docker compose up -d db）。
"""

import os
import sys
import tempfile
from pathlib import Path

import psycopg
import uvicorn
from alembic import command
from alembic.config import Config
from psycopg import conninfo, sql

from nutrition_agent.api.app import create_app
from nutrition_agent.config import get_settings, to_sqlalchemy_url
from nutrition_agent.extraction import medication_pack
from nutrition_agent.photos import PhotoStore

MEDICATION_PACK_REPLY = '{"readable": true, "names": ["Amlodipine", "Zantac"]}'
RECORDED_VLM = Path(__file__).resolve().parents[1] / "evals" / "vlm" / "recorded" / "vlm"


class RecordedVlmGateway:
    """煙霧測試用的假模型閘道：標示照片回錄製的 p01 辨識結果，藥包照片回固定的兩個藥名，不打外部 API。"""

    def vision(self, prompt: str, image: bytes, mime_type: str) -> str:
        if prompt == medication_pack.PROMPT:  # 藥包照片：固定回兩個藥名
            return MEDICATION_PACK_REPLY
        return (RECORDED_VLM / "p01-img01.json").read_text(encoding="utf-8")

    def complete(self, prompt: str, system: str | None = None) -> str:
        return "fake-completion"

    def embed(self, texts: list[str]) -> list[list[float]]:
        return [[0.0] * 4 for _ in texts]

DEFAULT_URL = "postgresql://nutrition:nutrition@127.0.0.1:55432/nutrition_e2e"


def recreate_database(url: str) -> None:
    name = conninfo.conninfo_to_dict(url)["dbname"]
    admin = conninfo.make_conninfo(url, dbname="postgres")
    with psycopg.connect(admin, autocommit=True) as conn:
        conn.execute(
            sql.SQL("DROP DATABASE IF EXISTS {} WITH (FORCE)").format(sql.Identifier(name))
        )
        conn.execute(sql.SQL("CREATE DATABASE {}").format(sql.Identifier(name)))


def main() -> None:
    port = int(sys.argv[1]) if len(sys.argv) > 1 else 8001
    url = os.environ.get("E2E_DATABASE_URL", DEFAULT_URL)
    recreate_database(url)
    os.environ["DATABASE_URL"] = url
    get_settings.cache_clear()  # import app 時已用預設連線建立過設定
    config = Config("alembic.ini")
    config.attributes["url"] = to_sqlalchemy_url(url)
    command.upgrade(config, "head")
    app = create_app(
        gateway=RecordedVlmGateway(),
        photo_store=PhotoStore(Path(tempfile.mkdtemp(prefix="nutrition-e2e-photos-"))),
    )
    uvicorn.run(app, host="127.0.0.1", port=port)


if __name__ == "__main__":
    main()
