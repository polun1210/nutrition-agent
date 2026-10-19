"""啟用 pgvector 並建立 ping 表（骨架用的資料庫往返）。

Revision ID: 0001
Revises:
"""

from alembic import op

revision = "0001"
down_revision = None
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.execute("CREATE EXTENSION IF NOT EXISTS vector")
    op.execute(
        "CREATE TABLE ping ("
        "id serial PRIMARY KEY, "
        "created_at timestamptz NOT NULL DEFAULT now())"
    )


def downgrade() -> None:
    op.execute("DROP TABLE ping")
