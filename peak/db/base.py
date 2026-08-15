"""Declarative base and shared mixins for the controlled engagement database.

MySQL-oriented (InnoDB / utf8mb4). Governance and audit fields are **real columns**
(never hidden inside JSON); `details_json` is only for non-governance detail. IDs are
prefixed strings, not autoincrement integers.
"""

from __future__ import annotations

from datetime import datetime
from typing import Optional

from sqlalchemy import Boolean, DateTime, JSON, String, func
from sqlalchemy.dialects import mysql
from sqlalchemy.orm import DeclarativeBase, Mapped, mapped_column


# MySQL table defaults applied to every model.
MYSQL_TABLE_ARGS = {"mysql_engine": "InnoDB", "mysql_charset": "utf8mb4"}

#: The deterministic collation pinned on governed string columns (Phase 44).
#:
#: MySQL's server default for ``utf8mb4`` is case- and accent-INSENSITIVE, so a governed column
#: that inherits it compares ``idem-key-1`` equal to ``idem-KEY-1`` — which would merge two
#: intentionally distinct idempotency keys. ``utf8mb4_bin`` compares byte-exactly. Governed values
#: are ASCII by construction (refs match ``[A-Za-z0-9_.:/-]``, fingerprints are sha256 hex), so a
#: Unicode-aware collation buys nothing here and byte comparison is the strictest guarantee.
#: ``utf8mb4_0900_as_cs`` remains a documented alternative; it is MySQL 8.0+ only.
#: See docs/GOVERNED_MYSQL_COLLATION_POLICY.md.
GOVERNED_COLLATION = "utf8mb4_bin"


def GovernedString(length: int):  # noqa: N802 - reads as a type constructor at the call site
    """A governed string column type: deterministic collation on MySQL, plain VARCHAR elsewhere.

    Use this for any column whose comparison decides identity, authorization, uniqueness, or
    integrity. Ordinary prose and JSON/detail text must **not** use it — see the policy doc.

    The collation is attached through ``with_variant`` rather than ``String(collation=...)`` on
    purpose. A bare ``collation=`` renders ``COLLATE utf8mb4_bin`` on *every* dialect, and SQLite —
    which backs the fast local structural-smoke harnesses — rejects it outright with
    ``no such collation sequence: utf8mb4_bin``. The variant emits identical MySQL DDL while
    leaving SQLite untouched, so local validation stays green without pretending SQLite proves
    anything about MySQL collation.
    """
    return String(length).with_variant(
        mysql.VARCHAR(length, collation=GOVERNED_COLLATION), "mysql", "mariadb")


class Base(DeclarativeBase):
    """Declarative base for all controlled-database models."""


class AuditMixin:
    """Audit columns carried by every record (see docs/DATABASE_ACCESS_AND_AUDIT.md)."""

    created_at: Mapped[datetime] = mapped_column(DateTime, server_default=func.now(), nullable=False)
    created_by: Mapped[Optional[str]] = mapped_column(GovernedString(128))
    updated_at: Mapped[datetime] = mapped_column(
        DateTime, server_default=func.now(), onupdate=func.now(), nullable=False
    )
    updated_by: Mapped[Optional[str]] = mapped_column(GovernedString(128))
    # Provenance of an agent/worker run that produced or edited this record, if any.
    agent_run_id: Mapped[Optional[str]] = mapped_column(GovernedString(64), index=True)
    # Non-governance detail only. Do NOT store governance fields here.
    details_json: Mapped[Optional[dict]] = mapped_column(JSON)


class GovernanceMixin:
    """Universal governance axes carried by every governed record.

    Values come from peak/db/enums.py, whose canonical source of truth is the Phase 9
    schemas (schemas/governance-state.schema.json and siblings). Stored as strings for
    MySQL portability and enforced app-side by the Python enums.
    """

    owner_id: Mapped[Optional[str]] = mapped_column(GovernedString(128), index=True)
    authorization_scope: Mapped[Optional[str]] = mapped_column(GovernedString(48), index=True)
    review_status: Mapped[str] = mapped_column(String(32), index=True, default="draft")
    lifecycle_status: Mapped[str] = mapped_column(String(32), index=True, default="draft")
