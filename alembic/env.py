import sys
import os
from pathlib import Path
import asyncio
from logging.config import fileConfig

from alembic import context
from sqlalchemy.ext.asyncio import create_async_engine

BASE_DIR = Path(__file__).resolve().parents[1]
sys.path.append(str(BASE_DIR))

from core.config import get_settings
from models.db import Base   # imports all models so Alembic sees them

config = context.config
fileConfig(config.config_file_name)

target_metadata = Base.metadata
settings = get_settings()


def run_migrations_offline():
      # Generates SQL without a live DB connection — useful for reviewing changes
      context.configure(
          url=settings.database_url,
          target_metadata=target_metadata,
          literal_binds=True,
      )
      with context.begin_transaction():
          context.run_migrations()


def do_run_migrations(connection):
      context.configure(connection=connection, target_metadata=target_metadata)
      with context.begin_transaction():
          context.run_migrations()


async def run_migrations_online():
      # create_async_engine here, not the shared engine from database.py,
      # because Alembic manages its own connection lifecycle
      connectable = create_async_engine(settings.database_url)
      async with connectable.connect() as connection:
          await connection.run_sync(do_run_migrations)
      await connectable.dispose()


if context.is_offline_mode():
      run_migrations_offline()
else:
      asyncio.run(run_migrations_online())
