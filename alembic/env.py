"""Alembic migration environment for Peak's controlled engagement database (MySQL).

The database URL is read from the ``PEAK_DATABASE_URL`` environment variable — never
from the repo. No credentials are stored here. Target metadata is the SQLAlchemy Base
from peak.db (schema only; no data).
"""

from __future__ import annotations

import os
import sys
from logging.config import fileConfig

from alembic import context

# Ensure the repo root is importable so `peak` resolves when Alembic runs.
REPO_ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
if REPO_ROOT not in sys.path:
    sys.path.insert(0, REPO_ROOT)

from peak.db.base import Base  # noqa: E402
import peak.db.models  # noqa: F401,E402  (registers models on Base.metadata)

config = context.config
if config.config_file_name is not None:
    fileConfig(config.config_file_name)

target_metadata = Base.metadata


def _get_url() -> str:
    url = os.environ.get("PEAK_DATABASE_URL")
    if not url:
        raise RuntimeError(
            "PEAK_DATABASE_URL is not set. Copy .env.example to .env and set the MySQL "
            "URL (credentials live outside the repo)."
        )
    return url


def run_migrations_offline() -> None:
    context.configure(
        url=_get_url(),
        target_metadata=target_metadata,
        literal_binds=True,
        dialect_opts={"paramstyle": "named"},
    )
    with context.begin_transaction():
        context.run_migrations()


def run_migrations_online() -> None:
    from sqlalchemy import create_engine

    connectable = create_engine(_get_url(), pool_pre_ping=True)
    with connectable.connect() as connection:
        context.configure(connection=connection, target_metadata=target_metadata)
        with context.begin_transaction():
            context.run_migrations()


if context.is_offline_mode():
    run_migrations_offline()
else:
    run_migrations_online()
