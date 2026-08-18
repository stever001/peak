"""Alembic version-table hardening for Peak (Phase 47).

**Root cause (Phase 46).** Alembic builds its bookkeeping table with
``Column("version_num", String(32))`` — see ``alembic.ddl.impl.DefaultImpl.version_table_impl``.
Five of this repository's revision identifiers are longer than 32 characters, the longest being
``012_internal_report_review_packet_decisions`` at 43. On MySQL/MariaDB the bookkeeping write of
such an identifier is rejected with "Data too long for column 'version_num'", which is what halted
the Phase 46 production bootstrap midway: migration ``008``'s DDL had already committed, but Alembic
could not record it.

**Why a preflight and not a configure() option.** Alembic exposes no width parameter on
``context.configure()`` — only ``version_table``, ``version_table_schema``, and ``version_table_pk``.
It does expose ``DefaultImpl.version_table_impl`` (added in Alembic 1.14) as an override hook, but
that hook is documented for third-party *dialect* authors and only governs the shape Alembic would
``CREATE``; it does nothing for a database whose ``alembic_version`` already exists at
``VARCHAR(32)``. A preflight covers all three states — absent, too narrow, already wide — with one
deterministic mechanism, so that is what this module implements.

**Scope.** This module touches exactly one table, ``alembic_version``, and exactly one column,
``version_num``. It issues two fixed statements and never composes SQL from caller input. It never
touches an application table, never reads or writes application rows, and never drops or deletes
anything. It is Alembic bookkeeping only.

Nothing here reads credentials, environment values, or ``.env``; the caller supplies an already-open
connection and no connection detail is read, logged, or raised.
"""

from __future__ import annotations

import ast
import os
from typing import Optional

# The width the version column must have. 255 leaves generous headroom over the longest revision
# identifier in the repository (43) without approaching any MySQL row/index limit.
ALEMBIC_VERSION_NUM_LENGTH = 255

VERSION_TABLE_NAME = "alembic_version"
VERSION_COLUMN_NAME = "version_num"

# Dialects whose DDL this module is written for. Every other dialect is deliberately left alone:
# SQLite ignores VARCHAR lengths entirely, so local smoke runs need no hardening and must not be
# perturbed by it.
SUPPORTED_DIALECTS = frozenset({"mysql", "mariadb"})

# Both statements are fixed literals, not templates. They are written out in full so a reviewer can
# see the entire surface this module can execute. The shape mirrors Alembic's own version table,
# including its ``<table>_pkc`` primary-key constraint name.
CREATE_VERSION_TABLE_SQL = (
    "CREATE TABLE alembic_version ("
    "version_num VARCHAR(255) NOT NULL, "
    "CONSTRAINT alembic_version_pkc PRIMARY KEY (version_num)"
    ")"
)
WIDEN_VERSION_COLUMN_SQL = (
    "ALTER TABLE alembic_version MODIFY COLUMN version_num VARCHAR(255) NOT NULL"
)

# Planner outcomes.
ACTION_CREATE = "create"
ACTION_WIDEN = "widen"
ACTION_NOOP = "noop"
ACTION_SKIP_DIALECT = "skip_unsupported_dialect"


def plan_version_table_action(dialect_name: str, existing_length: Optional[int]) -> str:
    """Decide what the version table needs, as a pure function.

    ``existing_length`` is the current ``version_num`` width, or ``None`` when the table is absent.
    Kept free of any database handle so the decision can be exercised exhaustively in tests without
    a server of any kind.
    """
    if (dialect_name or "").lower() not in SUPPORTED_DIALECTS:
        return ACTION_SKIP_DIALECT
    if existing_length is None:
        return ACTION_CREATE
    if existing_length < ALEMBIC_VERSION_NUM_LENGTH:
        return ACTION_WIDEN
    return ACTION_NOOP


def sql_for_action(action: str) -> Optional[str]:
    """Map a planner outcome to the one fixed statement it authorises, or ``None``."""
    if action == ACTION_CREATE:
        return CREATE_VERSION_TABLE_SQL
    if action == ACTION_WIDEN:
        return WIDEN_VERSION_COLUMN_SQL
    return None


def revision_ids(versions_dir: str) -> dict:
    """Return ``{filename: revision_id}`` parsed statically from the migration files.

    Parsed with :mod:`ast` rather than imported: this works on an interpreter without Alembic
    installed and cannot execute migration code as a side effect of measuring it.
    """
    found = {}
    for name in sorted(os.listdir(versions_dir)):
        if not name.endswith(".py"):
            continue
        with open(os.path.join(versions_dir, name), "r", encoding="utf-8") as fh:
            tree = ast.parse(fh.read())
        for node in tree.body:
            if not isinstance(node, ast.Assign):
                continue
            if not any(isinstance(t, ast.Name) and t.id == "revision" for t in node.targets):
                continue
            value = node.value
            if isinstance(value, ast.Constant) and isinstance(value.value, str):
                found[name] = value.value
    return found


def max_revision_id_length(versions_dir: str) -> int:
    """Longest revision identifier in the repository, or 0 when there are none."""
    ids = revision_ids(versions_dir)
    return max((len(r) for r in ids.values()), default=0)


def assert_revision_ids_fit(versions_dir: str) -> None:
    """Fail loudly in source terms if a revision id could not be recorded.

    This is the guard that would have caught Phase 46 before it reached production. It compares the
    repository against its own configured width and names the offenders; it reports no connection,
    credential, or environment detail.
    """
    offenders = sorted(
        (name, rev) for name, rev in revision_ids(versions_dir).items()
        if len(rev) > ALEMBIC_VERSION_NUM_LENGTH
    )
    if offenders:
        listed = ", ".join(f"{rev} ({len(rev)} chars, {name})" for name, rev in offenders)
        raise RuntimeError(
            f"Revision identifier(s) exceed the configured alembic_version.version_num width of "
            f"{ALEMBIC_VERSION_NUM_LENGTH}: {listed}. Shorten the identifier(s) or raise "
            f"ALEMBIC_VERSION_NUM_LENGTH before migrating."
        )


def current_version_num_length(connection) -> Optional[int]:
    """Current ``version_num`` width, or ``None`` when ``alembic_version`` does not exist.

    Returns ``None`` too when the column exists without a declared length, which is how SQLite
    reports an unconstrained ``VARCHAR``; callers only act on this value for MySQL/MariaDB.
    """
    from sqlalchemy import inspect as sa_inspect

    inspector = sa_inspect(connection)
    if not inspector.has_table(VERSION_TABLE_NAME):
        return None
    for column in inspector.get_columns(VERSION_TABLE_NAME):
        if column.get("name") == VERSION_COLUMN_NAME:
            return getattr(column.get("type"), "length", None)
    return None


def harden_version_table(connection) -> str:
    """Ensure ``alembic_version.version_num`` can hold this repository's revision identifiers.

    Creates the table at the configured width when absent, widens it when too narrow, and does
    nothing when it is already wide enough or the dialect is not MySQL/MariaDB. Returns the action
    taken so the caller can report it. The connection is supplied by the caller; this function opens
    none and reads no configuration.
    """
    dialect_name = connection.dialect.name
    if dialect_name.lower() not in SUPPORTED_DIALECTS:
        return ACTION_SKIP_DIALECT

    action = plan_version_table_action(dialect_name, current_version_num_length(connection))
    statement = sql_for_action(action)
    if statement is not None:
        # Imported only on the branch that actually emits DDL, so the skip and no-op paths stay
        # usable on an interpreter without SQLAlchemy installed (the offline validation tier).
        from sqlalchemy import text

        connection.execute(text(statement))
    return action
