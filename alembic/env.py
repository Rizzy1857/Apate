from __future__ import annotations

import asyncio
import os
import sys
from logging.config import fileConfig
from sqlalchemy import pool
from sqlalchemy.engine import Connection
from sqlalchemy.ext.asyncio import async_engine_from_config
from alembic import context

# this is the Alembic Config object, which provides
# access to the values within the .ini file in use.
config = context.config

# Interpret the config file for Python logging.
# This line sets up loggers basically.
if config.config_file_name is not None:
    fileConfig(config.config_file_name)

# Ensure project root on sys.path
ROOT = os.path.dirname(os.path.abspath(__file__))
PROJ_ROOT = os.path.dirname(ROOT)
sys.path.insert(0, PROJ_ROOT)

# Import metadata from db_manager
try:
    from backend.app.db_manager import Base  # type: ignore
except Exception as e:
    Base = None  # type: ignore

target_metadata = Base.metadata if Base is not None else None

# Use APATE_DB_URL if provided
fallback_url = "sqlite+aiosqlite:///./apate.db"
db_url = os.getenv("APATE_DB_URL") or config.get_main_option("sqlalchemy.url") or fallback_url
config.set_main_option("sqlalchemy.url", db_url)

def run_migrations_offline() -> None:
    url = config.get_main_option("sqlalchemy.url")
    context.configure(url=url, target_metadata=target_metadata, literal_binds=True)

    with context.begin_transaction():
        context.run_migrations()

def do_run_migrations(connection: Connection) -> None:
    context.configure(connection=connection, target_metadata=target_metadata)

    with context.begin_transaction():
        context.run_migrations()

async def run_migrations_online() -> None:
    section = config.get_section(config.config_ini_section) or {}
    connectable = async_engine_from_config(
        section,
        prefix="sqlalchemy.",
        poolclass=pool.NullPool,
    )

    async with connectable.connect() as connection:
        await connection.run_sync(do_run_migrations)

    await connectable.dispose()

if context.is_offline_mode():
    run_migrations_offline()
else:
    asyncio.run(run_migrations_online())