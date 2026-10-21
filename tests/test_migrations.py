"""遷移本身的行為：在獨立的資料庫上從舊版本升級，不動共用的測試資料庫。"""

from collections.abc import Iterator

import psycopg
import pytest
from alembic import command
from alembic.config import Config
from psycopg import conninfo

from nutrition_agent.config import to_sqlalchemy_url
from tests.conftest import TEST_DATABASE_URL, _recreate_database


@pytest.fixture
def migration_db() -> Iterator[tuple[str, Config]]:
    name = conninfo.conninfo_to_dict(TEST_DATABASE_URL)["dbname"]
    url = TEST_DATABASE_URL.rsplit("/", 1)[0] + f"/{name}_migration"
    _recreate_database(url)
    config = Config("alembic.ini")
    config.attributes["url"] = to_sqlalchemy_url(url)
    yield url, config


def insert_legacy_photo(conn: psycopg.Connection) -> int:
    user_id = conn.execute(
        "INSERT INTO users (email, password_hash, birth_year, birth_month, sex, conditions) "
        "VALUES ('old@example.com', 'x', 1950, 6, 'female', ARRAY['hypertension']) RETURNING id"
    ).fetchone()[0]
    draft_id = conn.execute(
        "INSERT INTO assessment_drafts (user_id) VALUES (%s) RETURNING id", (user_id,)
    ).fetchone()[0]
    return conn.execute(
        "INSERT INTO product_photos (user_id, draft_id, stored_name, mime_type, reading) "
        "VALUES (%s, %s, 'abc.jpg', 'image/jpeg', '{}') RETURNING id",
        (user_id, draft_id),
    ).fetchone()[0]


def test_遷移時既有的保健食品照片全部標記為過期(migration_db):
    url, config = migration_db
    command.upgrade(config, "0007")
    with psycopg.connect(url) as conn:
        photo_id = insert_legacy_photo(conn)

    command.upgrade(config, "head")

    with psycopg.connect(url) as conn:
        expired_at = conn.execute(
            "SELECT expired_at FROM product_photos WHERE id = %s", (photo_id,)
        ).fetchone()[0]
        assert expired_at is not None
        # 新照片預設不過期
        conn.execute(
            "INSERT INTO product_photos (user_id, draft_id, stored_name, mime_type, reading) "
            "SELECT user_id, draft_id, 'product/x.jpg', 'image/jpeg', '{}' FROM product_photos"
        )
        fresh = conn.execute(
            "SELECT expired_at FROM product_photos WHERE stored_name = 'product/x.jpg'"
        ).fetchone()[0]
        assert fresh is None
