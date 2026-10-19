"""Playwright 煙霧測試用的後端：重建獨立資料庫、跑 migration、啟動 API。

用法（由 web/playwright.config.ts 呼叫）：
    uv run python scripts/e2e_server.py [port]
資料庫連線取自 E2E_DATABASE_URL，預設 nutrition_e2e（需要本機 db 已啟動：docker compose up -d db）。
"""

import os
import sys

import psycopg
import uvicorn
from alembic import command
from alembic.config import Config
from psycopg import conninfo, sql

from nutrition_agent.config import to_sqlalchemy_url

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
    config = Config("alembic.ini")
    config.attributes["url"] = to_sqlalchemy_url(url)
    command.upgrade(config, "head")
    uvicorn.run("nutrition_agent.api.app:app", host="127.0.0.1", port=port)


if __name__ == "__main__":
    main()
