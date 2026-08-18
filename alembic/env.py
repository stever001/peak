"""Alembic migration environment for Peak's controlled engagement database (MySQL).

The database URL is read from the ``PEAK_DATABASE_URL`` environment variable — never
from the repo. No credentials are stored here. Target metadata is the SQLAlchemy Base
from peak.db (schema only; no data).

Phase 47 adds a version-table preflight: before any migration runs, the Alembic bookkeeping
column ``alembic_version.version_num`` is created or widened to hold this repository's revision
identifiers, several of which exceed Alembic's default ``VARCHAR(32)``. See
``alembic/version_table_hardening.py`` for the reasoning and the exact, fixed statements. The
preflight is Alembic bookkeeping only: it never touches an application table.
"""

from __future__ import annotations

import importlib.util
import os
import sys
from logging.config import fileConfig

from alembic import context

# Ensure the repo root is importable so `peak` resolves when Alembic runs.
REPO_ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
if REPO_ROOT not in sys.path:
    sys.path.insert(0, REPO_ROOT)

ALEMBIC_DIR = os.path.dirname(os.path.abspath(__file__))
VERSIONS_DIR = os.path.join(ALEMBIC_DIR, "versions")


def _load_hardening():
    """Load the sibling hardening module by path.

    ``alembic/`` is not an importable package, and putting it on ``sys.path`` risks shadowing
    unrelated modules, so the module is loaded explicitly from its own file.
    """
    spec = importlib.util.spec_from_file_location(
        "peak_alembic_version_table_hardening",
        os.path.join(ALEMBIC_DIR, "version_table_hardening.py"),
    )
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


hardening = _load_hardening()

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
    # Source-only guard: no connection is opened in offline mode, but a revision identifier that
    # could never be recorded is a source defect worth failing on either way.
    hardening.assert_revision_ids_fit(VERSIONS_DIR)
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

    hardening.assert_revision_ids_fit(VERSIONS_DIR)
    connectable = create_engine(_get_url(), pool_pre_ping=True)
    # Preflight on its own short transaction, before the migration connection is opened, so the
    # version table can hold long revision identifiers by the time Alembic writes one. A no-op on
    # SQLite and on any already-wide column.
    with connectable.begin() as preflight:
        hardening.harden_version_table(preflight)
    with connectable.connect() as connection:
        context.configure(connection=connection, target_metadata=target_metadata)
        with context.begin_transaction():
            context.run_migrations()


if context.is_offline_mode():
    run_migrations_offline()
else:
    run_migrations_online()
