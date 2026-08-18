"""Engine/session helpers for the controlled engagement database (MySQL).

**Runtime sessions read ``PEAK_RUNTIME_DATABASE_URL`` — and only that variable.** The URL never
comes from the repo. This module holds NO credentials and NO data, and creates no engine at import
time.

Three roles, three variables, deliberately not interchangeable (Phase 49):

===============================  ==================================================================
``PEAK_RUNTIME_DATABASE_URL``    application/runtime DB sessions — this module
``PEAK_DATABASE_URL``            Alembic / migration / bootstrap only — ``alembic/env.py``
``PEAK_PRODUCTION_DB_URL``       read-only production verifier only — ``tools/production_mysql_collation_verify.py``
===============================  ==================================================================

Phase 48 established that the runtime credential holds exactly ``SELECT`` + ``INSERT`` while the
migration credential can change schema. Runtime therefore **never falls back** to
``PEAK_DATABASE_URL``: a silent fallback would hand schema-changing privileges to application code
the moment the runtime variable went missing, which is precisely the failure this split prevents.
A missing runtime variable fails closed instead.

Local harnesses do not need the runtime variable at all. Every controlled writer accepts an explicit
``session_factory=``, and :func:`create_session_factory` accepts an explicit ``url=`` — either is the
supported way to point a test at a temporary SQLite database.
"""

from __future__ import annotations

import os

# Explicit, greppable names for the three roles. Nothing here reads a value at import time.
RUNTIME_DATABASE_URL_ENV = "PEAK_RUNTIME_DATABASE_URL"
MIGRATION_DATABASE_URL_ENV = "PEAK_DATABASE_URL"
PRODUCTION_VERIFY_DATABASE_URL_ENV = "PEAK_PRODUCTION_DB_URL"

#: Deprecated alias for :data:`RUNTIME_DATABASE_URL_ENV`, kept so existing imports keep resolving.
#: It names the *runtime* variable; migration code must use :data:`MIGRATION_DATABASE_URL_ENV`.
ENV_VAR = RUNTIME_DATABASE_URL_ENV


def get_runtime_database_url() -> str:
    """Return the runtime MySQL URL from the environment, or raise if unset.

    Expected format (see .env.example):
        mysql+pymysql://user:password@host:3306/peak_dev

    Raises ``RuntimeError`` naming the missing variable. The message contains variable *names*
    only — never a value, and never any part of a connection string.
    """
    url = os.environ.get(RUNTIME_DATABASE_URL_ENV)
    if not url:
        raise RuntimeError(
            f"{RUNTIME_DATABASE_URL_ENV} is not set. Runtime database sessions read that variable "
            f"and no other. {MIGRATION_DATABASE_URL_ENV} is reserved for Alembic/migration and must "
            f"not be substituted for it — doing so would give runtime the migration credential's "
            f"schema privileges. Set {RUNTIME_DATABASE_URL_ENV} (credentials live outside the "
            f"repo), or pass an explicit url= / session_factory= in tests."
        )
    return url


def get_database_url() -> str:
    """Deprecated alias for :func:`get_runtime_database_url`.

    Retained for callers written before the Phase 49 split. It resolves the **runtime** variable;
    migration code reads ``PEAK_DATABASE_URL`` directly in ``alembic/env.py``.
    """
    return get_runtime_database_url()


def create_runtime_engine(echo: bool = False, url: str | None = None):
    """Create a SQLAlchemy engine for runtime sessions.

    ``url`` is an explicit override for local harnesses (e.g. a temporary SQLite path). When it is
    omitted the runtime environment variable is required; there is no fallback to any other
    variable.

    SQLAlchemy is imported lazily so this module has no import-time dependency on it.
    """
    from sqlalchemy import create_engine

    return create_engine(url or get_runtime_database_url(), echo=echo, pool_pre_ping=True)


def create_db_engine(echo: bool = False):
    """Deprecated alias for :func:`create_runtime_engine`."""
    return create_runtime_engine(echo=echo)


def create_session_factory(echo: bool = False, url: str | None = None):
    """Create a sessionmaker bound to the runtime engine.

    This is the seam every controlled writer falls back to when no ``session_factory=`` is injected,
    so it is the single place runtime connectivity is resolved.
    """
    from sqlalchemy.orm import sessionmaker

    return sessionmaker(bind=create_runtime_engine(echo=echo, url=url), expire_on_commit=False)
