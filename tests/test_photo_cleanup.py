"""過期照片清理（Seam：清理函式＋CLI，真的測試 DB＋moto）：只刪物件，資料列與辨識結果保留。"""

from collections.abc import Iterator
from datetime import UTC, datetime, timedelta

import psycopg
import pytest

from nutrition_agent.config import get_settings
from nutrition_agent.photo_cleanup import expire_photos, run
from tests.conftest import bucket_keys, fail_storage

NOW = datetime(2026, 10, 21, 3, 0, tzinfo=UTC)
JPEG = b"\xff\xd8\xff\xe0" + b"\x00" * 32


@pytest.fixture
def draft(db: psycopg.Connection) -> tuple[int, int]:
    user_id = db.execute(
        "INSERT INTO users (email, password_hash, birth_year, birth_month, sex, conditions) "
        "VALUES ('cleanup@example.com', 'x', 1950, 6, 'female', ARRAY['hypertension']) "
        "RETURNING id"
    ).fetchone()[0]
    draft_id = db.execute(
        "INSERT INTO assessment_drafts (user_id) VALUES (%s) RETURNING id", (user_id,)
    ).fetchone()[0]
    return user_id, draft_id


def product_photo(db, draft, key: str, created_at: datetime) -> int:
    return db.execute(
        "INSERT INTO product_photos (user_id, draft_id, stored_name, mime_type, reading, created_at) "
        "VALUES (%s, %s, %s, 'image/jpeg', '{\"brand\": \"x\"}', %s) RETURNING id",
        (*draft, key, created_at),
    ).fetchone()[0]


def expired_at(db, photo_id: int, table: str = "product_photos") -> datetime | None:
    return db.execute(
        f"SELECT expired_at FROM {table} WHERE id = %s", (photo_id,)
    ).fetchone()[0]


def test_滿保存天數的照片刪除物件並標記過期(db, draft, photo_store, s3):
    key = photo_store.save(JPEG, ".jpg", "image/jpeg")
    photo_id = product_photo(db, draft, key, NOW - timedelta(days=30))

    result = expire_photos(db, photo_store, NOW, retention_days=30)

    assert (result.deleted_objects, result.marked_rows) == (1, 1)
    assert bucket_keys(s3) == []
    assert expired_at(db, photo_id) == NOW
    reading = db.execute(
        "SELECT reading FROM product_photos WHERE id = %s", (photo_id,)
    ).fetchone()[0]
    assert reading == {"brand": "x"}  # 資料列與辨識結果保留


def medication_photo(db, draft, key: str, created_at: datetime) -> int:
    return db.execute(
        "INSERT INTO medication_photos (user_id, draft_id, stored_name, mime_type, names, created_at) "
        "VALUES (%s, %s, %s, 'image/jpeg', ARRAY['Amlodipine'], %s) RETURNING id",
        (*draft, key, created_at),
    ).fetchone()[0]


def test_未滿保存天數的照片不動(db, draft, photo_store, s3):
    key = photo_store.save(JPEG, ".jpg", "image/jpeg")
    photo_id = product_photo(db, draft, key, NOW - timedelta(days=29, hours=23))

    result = expire_photos(db, photo_store, NOW, retention_days=30)

    assert (result.deleted_objects, result.marked_rows) == (0, 0)
    assert bucket_keys(s3) == [key]
    assert expired_at(db, photo_id) is None


def test_共用key的列從最早一筆起算並全部標記(db, draft, photo_store, s3):
    key = photo_store.save(JPEG, ".jpg", "image/jpeg")
    original = product_photo(db, draft, key, NOW - timedelta(days=31))
    copied = product_photo(db, draft, key, NOW - timedelta(days=1))  # 重新評估複製的列

    result = expire_photos(db, photo_store, NOW, retention_days=30)

    assert (result.deleted_objects, result.marked_rows) == (1, 2)
    assert bucket_keys(s3) == []
    assert expired_at(db, original) == expired_at(db, copied) == NOW


def test_重複執行時已標記的列跳過(db, draft, photo_store, s3):
    key = photo_store.save(JPEG, ".jpg", "image/jpeg")
    photo_id = product_photo(db, draft, key, NOW - timedelta(days=40))
    expire_photos(db, photo_store, NOW, retention_days=30)

    later = NOW + timedelta(days=1)
    result = expire_photos(db, photo_store, later, retention_days=30)

    assert (result.deleted_objects, result.marked_rows) == (0, 0)
    assert expired_at(db, photo_id) == NOW


def test_物件已不存在也視為成功並標記(db, draft, photo_store, s3):
    photo_id = product_photo(db, draft, "product/" + "a" * 32 + ".jpg", NOW - timedelta(days=30))

    result = expire_photos(db, photo_store, NOW, retention_days=30)

    assert (result.deleted_objects, result.marked_rows) == (1, 1)
    assert expired_at(db, photo_id) == NOW


def test_dry_run只回報數量不改任何東西(db, draft, photo_store, s3):
    key = photo_store.save(JPEG, ".jpg", "image/jpeg")
    photo_id = product_photo(db, draft, key, NOW - timedelta(days=30))

    result = expire_photos(db, photo_store, NOW, retention_days=30, dry_run=True)

    assert (result.deleted_objects, result.marked_rows) == (1, 1)
    assert bucket_keys(s3) == [key]
    assert expired_at(db, photo_id) is None


def test_保健食品與藥包照片都會處理(db, draft, photo_store, s3):
    product_key = photo_store.save(JPEG, ".jpg", "image/jpeg")
    medication_key = photo_store.save(JPEG, ".jpg", "image/jpeg", prefix="medication")
    fresh_key = photo_store.save(JPEG, ".jpg", "image/jpeg", prefix="medication")
    product_id = product_photo(db, draft, product_key, NOW - timedelta(days=30))
    medication_id = medication_photo(db, draft, medication_key, NOW - timedelta(days=45))
    fresh_id = medication_photo(db, draft, fresh_key, NOW - timedelta(days=2))

    result = expire_photos(db, photo_store, NOW, retention_days=30)

    assert (result.deleted_objects, result.marked_rows) == (2, 2)
    assert bucket_keys(s3) == [fresh_key]
    assert expired_at(db, product_id) == NOW
    assert expired_at(db, medication_id, "medication_photos") == NOW
    assert expired_at(db, fresh_id, "medication_photos") is None


def test_CLI沒給天數時保存天數取自設定(db, draft, photo_store, s3, monkeypatch, capsys):
    monkeypatch.setenv("PHOTO_RETENTION_DAYS", "7")
    get_settings.cache_clear()
    try:
        key = photo_store.save(JPEG, ".jpg", "image/jpeg")
        product_photo(db, draft, key, NOW - timedelta(days=8))

        run([], db, photo_store, NOW)
    finally:
        monkeypatch.delenv("PHOTO_RETENTION_DAYS")
        get_settings.cache_clear()

    assert "刪除物件 1 個" in capsys.readouterr().out
    assert bucket_keys(s3) == []


def test_CLI_dry_run以自訂天數印出數量且不改任何東西(db, draft, photo_store, s3, capsys):
    key = photo_store.save(JPEG, ".jpg", "image/jpeg")
    photo_id = product_photo(db, draft, key, NOW - timedelta(days=8))

    run(["--days", "7", "--dry-run"], db, photo_store, NOW)

    out = capsys.readouterr().out
    assert "dry-run" in out
    assert "刪除物件 1 個" in out and "標記 1 列" in out
    assert bucket_keys(s3) == [key]
    assert expired_at(db, photo_id) is None


def test_CLI執行後印出刪除物件數與標記列數(db, draft, photo_store, s3, capsys):
    key = photo_store.save(JPEG, ".jpg", "image/jpeg")
    product_photo(db, draft, key, NOW - timedelta(days=8))

    run(["--days", "7"], db, photo_store, NOW)

    assert "刪除物件 1 個，標記 1 列" in capsys.readouterr().out
    assert bucket_keys(s3) == []


@pytest.fixture
def committed(database_url: str) -> Iterator[psycopg.Connection]:
    """autocommit 連線（同 CLI）：寫入會真的 commit，用另一條連線才看得出哪些標記留下來。"""
    with psycopg.connect(database_url, autocommit=True) as conn:
        user_id = conn.execute(
            "INSERT INTO users (email, password_hash, birth_year, birth_month, sex, conditions) "
            "VALUES ('committed@example.com', 'x', 1950, 6, 'female', ARRAY['hypertension']) "
            "RETURNING id"
        ).fetchone()[0]
        try:
            yield conn
        finally:
            conn.execute("DELETE FROM product_photos WHERE user_id = %s", (user_id,))
            conn.execute("DELETE FROM assessment_drafts WHERE user_id = %s", (user_id,))
            conn.execute("DELETE FROM users WHERE id = %s", (user_id,))


def committed_draft(conn: psycopg.Connection) -> tuple[int, int]:
    user_id = conn.execute(
        "SELECT id FROM users WHERE email = 'committed@example.com'"
    ).fetchone()[0]
    draft_id = conn.execute(
        "INSERT INTO assessment_drafts (user_id) VALUES (%s) RETURNING id", (user_id,)
    ).fetchone()[0]
    return user_id, draft_id


def test_CLI中途刪除失敗時已處理的標記保留並以非零狀態結束(
    committed, database_url, photo_store, s3, capsys
):
    draft = committed_draft(committed)
    keys = sorted(photo_store.save(JPEG, ".jpg", "image/jpeg") for _ in range(2))
    done, failed = (product_photo(committed, draft, key, NOW - timedelta(days=8)) for key in keys)
    fail_storage(s3, "DeleteObject", after=1)  # 依 key 排序處理：第一個刪掉、第二個失敗

    status = run(["--days", "7"], committed, photo_store, NOW)

    assert status != 0
    assert "失敗 1 個" in capsys.readouterr().err
    assert bucket_keys(s3) == [keys[1]]
    with psycopg.connect(database_url) as other:
        assert expired_at(other, done) == NOW
        assert expired_at(other, failed) is None


def test_格式不符的key算刪除失敗且不標記(db, draft, photo_store, s3):
    photo_id = product_photo(db, draft, "../outside.jpg", NOW - timedelta(days=30))

    result = expire_photos(db, photo_store, NOW, retention_days=30)

    assert (result.deleted_objects, result.failed_objects) == (0, 1)
    assert expired_at(db, photo_id) is None
