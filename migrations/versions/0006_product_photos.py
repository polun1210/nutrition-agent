"""保健食品照片與每張照片的辨識結果。

Revision ID: 0006
Revises: 0005
"""

from alembic import op

revision = "0006"
down_revision = "0005"
branch_labels = None
depends_on = None


def upgrade() -> None:
    # 照片檔存在本機 volume（stored_name 為檔名），資料庫只記歸屬與辨識結果。
    op.execute(
        "CREATE TABLE product_photos ("
        "id serial PRIMARY KEY, "
        "user_id integer NOT NULL REFERENCES users (id), "
        "draft_id integer NOT NULL REFERENCES assessment_drafts (id), "
        "stored_name text NOT NULL, "
        "mime_type text NOT NULL, "
        "reading jsonb NOT NULL, "
        "created_at timestamptz NOT NULL DEFAULT now())"
    )
    op.execute("CREATE INDEX product_photos_user_idx ON product_photos (user_id, id)")


def downgrade() -> None:
    op.execute("DROP TABLE product_photos")
