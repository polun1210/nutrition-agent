"""證據段落表：ingest 後的語料切塊與 embedding。

Revision ID: 0002
Revises: 0001
"""

from alembic import op

revision = "0002"
down_revision = "0001"
branch_labels = None
depends_on = None


def upgrade() -> None:
    # embedding 不固定維度：維度由模型閘道設定的 embedding 模型決定。
    op.execute(
        "CREATE TABLE evidence_chunk ("
        "id text PRIMARY KEY, "
        "source_type text NOT NULL, "
        "document_name text NOT NULL, "
        "document_path text NOT NULL, "
        "ingredients text[] NOT NULL DEFAULT '{}', "
        "section text NOT NULL, "
        "start_char integer NOT NULL, "
        "end_char integer NOT NULL, "
        "start_line integer NOT NULL, "
        "end_line integer NOT NULL, "
        "text text NOT NULL, "
        "embedding vector NOT NULL)"
    )
    op.execute(
        "CREATE INDEX evidence_chunk_ingredients_idx "
        "ON evidence_chunk USING gin (ingredients)"
    )
    op.execute("CREATE INDEX evidence_chunk_document_idx ON evidence_chunk (document_path)")


def downgrade() -> None:
    op.execute("DROP TABLE evidence_chunk")
