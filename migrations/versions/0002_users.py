"""使用者帳號與個人資料。

Revision ID: 0002
Revises: 0001
"""

from alembic import op

revision = "0002"
down_revision = "0001"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.execute(
        "CREATE TABLE users ("
        "id serial PRIMARY KEY, "
        "email text NOT NULL, "
        "password_hash text NOT NULL, "
        "birth_year integer NOT NULL CHECK (birth_year BETWEEN 1900 AND 2200), "
        "birth_month integer NOT NULL CHECK (birth_month BETWEEN 1 AND 12), "
        "sex text NOT NULL CHECK (sex IN ('male', 'female')), "
        "conditions text[] NOT NULL CHECK (cardinality(conditions) > 0), "
        "created_at timestamptz NOT NULL DEFAULT now())"
    )
    op.execute("CREATE UNIQUE INDEX users_email_lower_key ON users (lower(email))")


def downgrade() -> None:
    op.execute("DROP TABLE users")
