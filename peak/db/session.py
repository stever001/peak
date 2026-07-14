"""Engine/session helpers for the controlled engagement database (MySQL).

Reads the connection URL from the environment variable ``PEAK_DATABASE_URL`` — never
from the repo. See .env.example for the placeholder format. No engine is created at
import time, and this module holds NO credentials and NO data.
"""

from __future__ import annotations

import os

ENV_VAR = "PEAK_DATABASE_URL"


def get_database_url() -> str:
    """Return the MySQL connection URL from the environment, or raise if unset.

    Expected format (see .env.example):
        mysql+pymysql://user:password@host:3306/peak_dev
    """
    url = os.environ.get(ENV_VAR)
    if not url:
        raise RuntimeError(
            f"{ENV_VAR} is not set. Copy .env.example to .env and set the MySQL URL "
            f"(credentials live outside the repo)."
        )
    return url


def create_db_engine(echo: bool = False):
    """Create a SQLAlchemy engine from the environment URL.

    Imported lazily so this module has no hard import-time dependency on SQLAlchemy.
    """
    from sqlalchemy import create_engine

    return create_engine(get_database_url(), echo=echo, pool_pre_ping=True)


def create_session_factory(echo: bool = False):
    """Create a sessionmaker bound to the engine."""
    from sqlalchemy.orm import sessionmaker

    return sessionmaker(bind=create_db_engine(echo=echo), expire_on_commit=False)
