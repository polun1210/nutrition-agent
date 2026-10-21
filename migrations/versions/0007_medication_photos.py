"""藥包照片與每張照片讀出的藥名。

Revision ID: 0007
Revises: 0006
"""

from alembic import op

revision = "0007"
down_revision = "0006"
branch_labels = None
depends_on = None


def upgrade() -> None:
    # 照片存在物件儲存（stored_name 為 object key，medication/ 前綴），留著方便回頭查 VLM 讀了什麼。
    op.execute(
        "CREATE TABLE medication_photos ("
        "id serial PRIMARY KEY, "
        "user_id integer NOT NULL REFERENCES users (id), "
        "draft_id integer NOT NULL REFERENCES assessment_drafts (id), "
        "stored_name text NOT NULL, "
        "mime_type text NOT NULL, "
        "names text[] NOT NULL, "
        "created_at timestamptz NOT NULL DEFAULT now())"
    )
    op.execute("CREATE INDEX medication_photos_user_idx ON medication_photos (user_id, id)")


def downgrade() -> None:
    op.execute("DROP TABLE medication_photos")
