"""Contracts for the Controlled DB Writer Boundary (Phase 17).

**DB-aware but not DB-writing.** These dataclasses describe what a *future* controlled DB
writer may write — the write subject, the request, the allow/deny decision, the no-op write
plan, and an in-memory audit draft — **without connecting to a database, importing a live
SQLAlchemy session, executing SQL, persisting records, or reading records.**

This package is deliberately kept out of ``peak.db``: it must stay **stdlib-only** and
**no-live-DB**. It imports no SQLAlchemy, no Alembic, and no ``peak.db`` session/model
modules. A future live writer may bridge these contracts to ``peak.db`` models, but Phase 17
only defines the safe boundary.

**Source contracts only — no stored records.** Nothing here opens a database connection,
runs SQL, writes a file, calls an LLM/AgentNet/MCP/resolver, touches the network, produces
client-facing output, or publishes a capsule. See docs/CONTROLLED_DB_WRITER_BOUNDARY.md and
docs/CONTROLLED_WRITE_ALLOWLIST.md.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import List, Optional

# Effects a controlled write plan may never execute in Phase 17 (documented on every plan).
PROHIBITED_EFFECTS = (
    "database_write",
    "database_connection",
    "sql_execution",
    "migration",
    "record_delete",
    "credential_storage",
    "client_facing_approval",
    "financial_impact_verification",
    "capsule_publication",
    "live_llm_call",
    "agentnet_call",
    "network_call",
)


@dataclass
class ControlledWriteSubject:
    """An in-memory snapshot of the record a write would target (no DB read happens).

    ``stored_authorization_scope`` is the subject record's own persisted scope — the value a
    future controlled writer must compare the request scope against. In Phase 17 the caller
    supplies this snapshot in memory; a future controlled-DB reader would load it.
    """

    subject_record_id: Optional[str] = None
    subject_record_type: Optional[str] = None
    owner_id: Optional[str] = None
    client_id: Optional[str] = None
    engagement_id: Optional[str] = None
    stored_authorization_scope: Optional[str] = None
    stored_output_status: Optional[str] = None
    stored_review_status: Optional[str] = None
    stored_lifecycle_status: Optional[str] = None
    source_reference_id: Optional[str] = None


@dataclass
class ControlledWriteRequest:
    """A request to prepare (never execute) a controlled write of a record draft."""

    owner_id: Optional[str] = None
    client_id: Optional[str] = None
    engagement_id: Optional[str] = None
    requested_by: Optional[str] = None
    requester_role: Optional[str] = None
    authorization_scope: Optional[str] = None
    target_table: Optional[str] = None
    requested_action: Optional[str] = None
    subject: Optional[ControlledWriteSubject] = None
    record_draft: Optional[object] = None  # an upstream draft (e.g. a Phase 16 ReviewRecordDraft)
    source_phase: Optional[str] = None
    lifecycle_status: Optional[str] = None
    idempotency_key: Optional[str] = None


@dataclass
class ControlledWriteDecision:
    """Result of the pre-write governance checks (no side effects)."""

    permitted: bool = False
    target_table: Optional[str] = None
    requested_action: Optional[str] = None
    reasons: List[str] = field(default_factory=list)
    warnings: List[str] = field(default_factory=list)


@dataclass
class ControlledWritePlan:
    """A no-op write plan a future controlled DB writer would execute (not executed here)."""

    permitted: bool = False
    target_table: Optional[str] = None
    requested_action: Optional[str] = None
    record_draft: Optional[object] = None
    requires_controlled_db_writer: bool = True
    database_write_made: bool = False
    database_connection_made: bool = False
    sql_execution_made: bool = False
    stored_record_created: bool = False
    prohibited_effects: List[str] = field(default_factory=lambda: list(PROHIBITED_EFFECTS))
    reasons: List[str] = field(default_factory=list)
    warnings: List[str] = field(default_factory=list)


@dataclass
class ControlledWriteResult:
    """The controlled result of preparing a controlled write (no side effects)."""

    permitted: bool = False
    status: str = "rejected"
    write_plan: Optional[ControlledWritePlan] = None
    database_write_made: bool = False
    database_connection_made: bool = False
    sql_execution_made: bool = False
    stored_record_created: bool = False
    llm_call_made: bool = False
    agentnet_call_made: bool = False
    network_call_made: bool = False
    capsule_publication_made: bool = False
    client_facing_output_created: bool = False
    reasons: List[str] = field(default_factory=list)
    warnings: List[str] = field(default_factory=list)


@dataclass
class ControlledWriteAuditDraft:
    """An in-memory audit draft of the write attempt (never persisted here).

    ``audit_record_id`` and ``created_at`` are left ``None`` — a future controlled DB writer
    assigns them at write time. Nothing here is stored.
    """

    audit_record_id: Optional[str] = None  # assigned by a future controlled-DB writer
    owner_id: Optional[str] = None
    client_id: Optional[str] = None
    engagement_id: Optional[str] = None
    target_table: Optional[str] = None
    requested_action: Optional[str] = None
    requested_by: Optional[str] = None
    requester_role: Optional[str] = None
    source_phase: Optional[str] = None
    idempotency_key: Optional[str] = None
    decision: Optional[str] = None
    reasons: List[str] = field(default_factory=list)
    warnings: List[str] = field(default_factory=list)
    created_at: Optional[str] = None  # reserved for future controlled-DB assignment
