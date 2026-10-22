"""移除 ping 表（骨架用的資料庫往返，端點已移除）。

Revision ID: 0010
Revises: 0009
"""

from alembic import op

revision = "0010"
down_revision = "0009"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.execute("DROP TABLE ping")


def downgrade() -> None:
    # 與 0001 建立時相同，0001 的 downgrade 才能照常刪除。
    op.execute(
        "CREATE TABLE ping ("
        "id serial PRIMARY KEY, "
        "created_at timestamptz NOT NULL DEFAULT now())"
    )
