"""過期照片清理：超過保存天數的照片從物件儲存刪除，資料庫對應的列標記為過期。

只刪物件，資料列與辨識結果保留。重新評估會複製照片列，多列共用同一個 object key，
所以過期從該 key 最早一筆的建立時間起算，共用的列（保健食品與藥包兩張表）一起標記。
冪等：已標記的列跳過；物件已不存在也算成功（S3 刪除本來就冪等）。
每個 key 刪除成功就各自 commit 標記；某個 key 刪除失敗只跳過它（下次重跑），不影響其他 key。

用法：`uv run python -m nutrition_agent.photo_cleanup [--days N] [--dry-run]`
"""

import argparse
import logging
import sys
from dataclasses import dataclass
from datetime import UTC, datetime, timedelta

import psycopg

from nutrition_agent.config import get_settings
from nutrition_agent.photos import PhotoStorageError, PhotoStore

PHOTO_TABLES = ("product_photos", "medication_photos")

_ALL_PHOTOS = " UNION ALL ".join(
    f"SELECT stored_name, created_at, expired_at FROM {table}" for table in PHOTO_TABLES
)
# 只挑還有未標記列的 key：全部標記過的 key 物件早已刪除，不用再處理。
_DUE_KEYS = (
    f"SELECT stored_name, count(*) FILTER (WHERE expired_at IS NULL) FROM ({_ALL_PHOTOS}) AS p "
    "GROUP BY stored_name "
    "HAVING min(created_at) <= %s AND bool_or(expired_at IS NULL) "
    "ORDER BY stored_name"
)


log = logging.getLogger(__name__)


@dataclass(frozen=True)
class CleanupResult:
    deleted_objects: int
    marked_rows: int
    failed_objects: int = 0


def expire_photos(
    conn: psycopg.Connection,
    store: PhotoStore,
    now: datetime,
    retention_days: int,
    *,
    dry_run: bool = False,
) -> CleanupResult:
    """刪除滿保存天數的照片物件並標記資料列；dry_run 只計算會處理的數量，不改任何東西。"""
    cutoff = now - timedelta(days=retention_days)
    due = conn.execute(_DUE_KEYS, (cutoff,)).fetchall()
    if dry_run:
        return CleanupResult(len(due), sum(count for _, count in due))
    deleted = marked = failed = 0
    for key, _ in due:
        try:
            store.delete(key)  # 先刪物件再標記：刪除失敗時列不標記，下次重跑
        except (PhotoStorageError, ValueError):  # ValueError：資料庫裡的 key 格式不符
            log.exception("刪除過期照片物件失敗：%s", key)
            failed += 1
            continue
        # autocommit 連線上每個 key 各自 commit；已在交易中（測試）則是 savepoint。
        with conn.transaction():
            marked += _mark_expired(conn, key, now)
        deleted += 1
    return CleanupResult(deleted, marked, failed)


def _mark_expired(conn: psycopg.Connection, key: str, now: datetime) -> int:
    marked = 0
    for table in PHOTO_TABLES:
        cursor = conn.execute(
            f"UPDATE {table} SET expired_at = %s WHERE stored_name = %s AND expired_at IS NULL",
            (now, key),
        )
        marked += cursor.rowcount
    return marked


def run(argv: list[str], conn: psycopg.Connection, store: PhotoStore, now: datetime) -> int:
    """執行清理並印出結果；有物件刪除失敗時回傳非零的結束狀態。"""
    parser = argparse.ArgumentParser(description="刪除超過保存天數的照片物件並標記資料列")
    parser.add_argument(
        "--days", type=int, default=None, help="保存天數（預設取 PHOTO_RETENTION_DAYS，30 天）"
    )
    parser.add_argument("--dry-run", action="store_true", help="只列出數量，不刪物件也不改資料庫")
    args = parser.parse_args(argv)
    if args.days is not None and args.days < 0:
        parser.error("--days 不可為負數")
    days = get_settings().photo_retention_days if args.days is None else args.days
    result = expire_photos(conn, store, now, days, dry_run=args.dry_run)
    prefix = "[dry-run] 將" if args.dry_run else "已"
    print(f"{prefix}刪除物件 {result.deleted_objects} 個，標記 {result.marked_rows} 列")
    if result.failed_objects:
        print(f"刪除失敗 {result.failed_objects} 個，下次執行會重試", file=sys.stderr)
        return 1
    return 0


def main(argv: list[str] | None = None) -> int:
    settings = get_settings()
    store = PhotoStore.from_settings(settings)
    # autocommit：每個 key 的標記各自 commit，中途失敗不會把已處理的一起 rollback。
    with psycopg.connect(settings.database_url, autocommit=True) as conn:
        return run(sys.argv[1:] if argv is None else argv, conn, store, datetime.now(UTC))


if __name__ == "__main__":
    sys.exit(main())
