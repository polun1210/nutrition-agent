"""過期照片清理：超過保存天數的照片從物件儲存刪除，資料庫對應的列標記為過期。

只刪物件，資料列與辨識結果保留。重新評估會複製照片列，多列共用同一個 object key，
所以過期從該 key 最早一筆的建立時間起算，共用的列（保健食品與藥包兩張表）一起標記。
冪等：已標記的列跳過；物件已不存在也算成功（S3 刪除本來就冪等）。

用法：`uv run python -m nutrition_agent.photo_cleanup [--days N] [--dry-run]`
"""

import argparse
import sys
from dataclasses import dataclass
from datetime import UTC, datetime, timedelta

import psycopg

from nutrition_agent.config import get_settings
from nutrition_agent.photos import PhotoStore

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


@dataclass(frozen=True)
class CleanupResult:
    deleted_objects: int
    marked_rows: int


def expire_photos(
    conn: psycopg.Connection,
    store: PhotoStore,
    now: datetime,
    retention_days: int | None = None,
    *,
    dry_run: bool = False,
) -> CleanupResult:
    """刪除滿保存天數的照片物件並標記資料列；dry_run 只計算會處理的數量，不改任何東西。"""
    if retention_days is None:
        retention_days = get_settings().photo_retention_days
    cutoff = now - timedelta(days=retention_days)
    due = conn.execute(_DUE_KEYS, (cutoff,)).fetchall()
    if dry_run:
        return CleanupResult(len(due), sum(count for _, count in due))
    marked = 0
    for key, _ in due:
        store.delete(key)  # 先刪物件再標記：刪除失敗時列不標記，下次重跑
        marked += _mark_expired(conn, key, now)
    return CleanupResult(len(due), marked)


def _mark_expired(conn: psycopg.Connection, key: str, now: datetime) -> int:
    marked = 0
    for table in PHOTO_TABLES:
        cursor = conn.execute(
            f"UPDATE {table} SET expired_at = %s WHERE stored_name = %s AND expired_at IS NULL",
            (now, key),
        )
        marked += cursor.rowcount
    return marked


def run(
    argv: list[str], conn: psycopg.Connection, store: PhotoStore, now: datetime
) -> CleanupResult:
    parser = argparse.ArgumentParser(description="刪除超過保存天數的照片物件並標記資料列")
    parser.add_argument(
        "--days", type=int, default=None, help="保存天數（預設取 PHOTO_RETENTION_DAYS，30 天）"
    )
    parser.add_argument("--dry-run", action="store_true", help="只列出數量，不刪物件也不改資料庫")
    args = parser.parse_args(argv)
    if args.days is not None and args.days < 0:
        parser.error("--days 不可為負數")
    result = expire_photos(conn, store, now, args.days, dry_run=args.dry_run)
    prefix = "[dry-run] 將" if args.dry_run else "已"
    print(f"{prefix}刪除物件 {result.deleted_objects} 個，標記 {result.marked_rows} 列")
    return result


def main(argv: list[str] | None = None) -> int:
    settings = get_settings()
    store = PhotoStore.from_settings(settings)
    with psycopg.connect(settings.database_url) as conn:  # 離開 with 時 commit
        run(sys.argv[1:] if argv is None else argv, conn, store, datetime.now(UTC))
    return 0


if __name__ == "__main__":
    sys.exit(main())
