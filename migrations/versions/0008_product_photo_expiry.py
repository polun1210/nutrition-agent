"""保健食品照片的過期時間。

Revision ID: 0008
Revises: 0007
"""

from alembic import op

revision = "0008"
down_revision = "0007"
branch_labels = None
depends_on = None


def upgrade() -> None:
    # 過期的照片物件可能已刪除，GET 回 410；評估個案與報告照常顯示。
    op.execute("ALTER TABLE product_photos ADD COLUMN expired_at timestamptz")
    # 遷移前的照片都存在舊的本機 volume（不搬到物件儲存），一律視為已過期。
    op.execute("UPDATE product_photos SET expired_at = now()")


def downgrade() -> None:
    op.execute("ALTER TABLE product_photos DROP COLUMN expired_at")
