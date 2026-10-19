from alembic import context
from sqlalchemy import create_engine

from nutrition_agent.config import get_settings, to_sqlalchemy_url

url = context.config.attributes.get("url") or to_sqlalchemy_url(get_settings().database_url)
engine = create_engine(url)
with engine.begin() as connection:
    context.configure(connection=connection, target_metadata=None)
    with context.begin_transaction():
        context.run_migrations()
