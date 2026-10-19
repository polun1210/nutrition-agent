"""評估個案與評估草稿。

Revision ID: 0003
Revises: 0002
"""

from alembic import op

revision = "0003"
down_revision = "0002"
branch_labels = None
depends_on = None


def upgrade() -> None:
    # 評估個案：送出後的不可變快照（程式不提供任何 UPDATE 路徑）。
    op.execute(
        "CREATE TABLE assessment_cases ("
        "id serial PRIMARY KEY, "
        "user_id integer NOT NULL REFERENCES users (id), "
        "snapshot jsonb NOT NULL, "
        "assessment jsonb NOT NULL, "
        "report jsonb NOT NULL, "
        "reference_versions jsonb NOT NULL, "
        "created_at timestamptz NOT NULL DEFAULT now())"
    )
    op.execute("CREATE INDEX assessment_cases_user_idx ON assessment_cases (user_id, id DESC)")
    # 草稿：逐步儲存；case_id 非空代表已送出，不能再改。
    op.execute(
        "CREATE TABLE assessment_drafts ("
        "id serial PRIMARY KEY, "
        "user_id integer NOT NULL REFERENCES users (id), "
        "products jsonb NOT NULL DEFAULT '[]', "
        "case_id integer REFERENCES assessment_cases (id), "
        "updated_at timestamptz NOT NULL DEFAULT now())"
    )


def downgrade() -> None:
    op.execute("DROP TABLE assessment_drafts")
    op.execute("DROP TABLE assessment_cases")
