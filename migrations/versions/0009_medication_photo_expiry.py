"""藥包照片的過期時間。

Revision ID: 0009
Revises: 0008
"""

from alembic import op

revision = "0009"
down_revision = "0008"
branch_labels = None
depends_on = None


def upgrade() -> None:
    # 過期清理刪掉物件後標記；既有藥包照片一開始就存在物件儲存，不標記。
    op.execute("ALTER TABLE medication_photos ADD COLUMN expired_at timestamptz")


def downgrade() -> None:
    op.execute("ALTER TABLE medication_photos DROP COLUMN expired_at")
