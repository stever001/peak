"""Declarative base and shared mixins for the controlled engagement database.

MySQL-oriented (InnoDB / utf8mb4). Governance and audit fields are **real columns**
(never hidden inside JSON); `details_json` is only for non-governance detail. IDs are
prefixed strings, not autoincrement integers.
"""

from __future__ import annotations

from datetime import datetime

from sqlalchemy import Boolean, DateTime, JSON, String, func
from sqlalchemy.orm import DeclarativeBase, Mapped, mapped_column


# MySQL table defaults applied to every model.
MYSQL_TABLE_ARGS = {"mysql_engine": "InnoDB", "mysql_charset": "utf8mb4"}


class Base(DeclarativeBase):
    """Declarative base for all controlled-database models."""


class AuditMixin:
    """Audit columns carried by every record (see docs/DATABASE_ACCESS_AND_AUDIT.md)."""

    created_at: Mapped[datetime] = mapped_column(DateTime, server_default=func.now(), nullable=False)
    created_by: Mapped[str | None] = mapped_column(String(128))
    updated_at: Mapped[datetime] = mapped_column(
        DateTime, server_default=func.now(), onupdate=func.now(), nullable=False
    )
    updated_by: Mapped[str | None] = mapped_column(String(128))
    # Provenance of an agent/worker run that produced or edited this record, if any.
    agent_run_id: Mapped[str | None] = mapped_column(String(64), index=True)
    # Non-governance detail only. Do NOT store governance fields here.
    details_json: Mapped[dict | None] = mapped_column(JSON)


class GovernanceMixin:
    """Universal governance axes carried by every governed record.

    Values come from peak/db/enums.py, whose canonical source of truth is the Phase 9
    schemas (schemas/governance-state.schema.json and siblings). Stored as strings for
    MySQL portability and enforced app-side by the Python enums.
    """

    owner_id: Mapped[str | None] = mapped_column(String(128), index=True)
    authorization_scope: Mapped[str | None] = mapped_column(String(48), index=True)
    review_status: Mapped[str] = mapped_column(String(32), index=True, default="draft")
    lifecycle_status: Mapped[str] = mapped_column(String(32), index=True, default="draft")
