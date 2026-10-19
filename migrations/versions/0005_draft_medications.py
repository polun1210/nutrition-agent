"""評估草稿加上用藥。

Revision ID: 0005
Revises: 0004
"""

from alembic import op

revision = "0005"
down_revision = "0004"
branch_labels = None
depends_on = None


def upgrade() -> None:
    # 只存使用者輸入的藥名原文（[{"name": ...}]）；對照結果在送出時由後端重算。
    op.execute("ALTER TABLE assessment_drafts ADD COLUMN medications jsonb NOT NULL DEFAULT '[]'")


def downgrade() -> None:
    op.execute("ALTER TABLE assessment_drafts DROP COLUMN medications")
