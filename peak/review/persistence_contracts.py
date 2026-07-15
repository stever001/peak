"""Contracts for the Review Persistence Boundary (Phase 16).

**DB-aware but not DB-writing.** These dataclasses describe how a *future* controlled-DB
writer will persist a permitted Phase 15 review outcome as a `ReviewRecord` — the record
shape, the write plan, and the readiness decision — **without connecting to, reading from,
or writing to any database.**

A critical scope rule lives here: a DB-backed review must compare the request's
``authorization_scope`` against the subject record's **stored** ``authorization_scope``
(``StoredReviewSubjectSnapshot.stored_authorization_scope``), not rely only on the request
scope. Owner/client/engagement matching is necessary but not sufficient.

**Source contracts only — no stored review records.** Nothing here opens a database
session, imports SQLAlchemy or ``peak.db``, calls an LLM/AgentNet/MCP/resolver, touches the
network, writes a file, produces client-facing output, or publishes a capsule. See
docs/REVIEW_PERSISTENCE_BOUNDARY.md and docs/DB_BACKED_REVIEW_SCOPE_POLICY.md.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import List, Optional

# Persistence actions a Phase 16 request may ask for (both are no-op plans).
ALLOWED_PERSISTENCE_ACTIONS = frozenset(
    {
        "create_review_record_draft",
        "prepare_review_write_plan",
    }
)

# The table a future controlled-DB writer would target (see DATABASE_RECORD_MODEL.md).
REVIEW_RECORDS_TABLE = "review_records"

# Effects a persistence plan may never execute in Phase 16 (documented on every plan).
PROHIBITED_EFFECTS = (
    "database_write",
    "database_connection",
    "client_facing_approval",
    "financial_impact_verification",
    "capsule_publication",
    "live_llm_call",
    "agentnet_call",
    "network_call",
)

DEFAULT_LIFECYCLE_STATUS = "active"


@dataclass
class StoredReviewSubjectSnapshot:
    """An in-memory snapshot of a subject record **as it is stored** (no DB read happens).

    ``stored_authorization_scope`` is the subject record's own persisted scope — the value a
    future DB-backed review must compare the request scope against. In Phase 16 the caller
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
    stored_authoritative: bool = False
    stored_client_facing_approved: bool = False
    stored_capsule_candidate_ready: bool = False
    source_reference_id: Optional[str] = None


@dataclass
class ReviewPersistenceRequest:
    """A request to prepare (never execute) persistence of a permitted review outcome."""

    owner_id: Optional[str] = None
    client_id: Optional[str] = None
    engagement_id: Optional[str] = None
    requested_by: Optional[str] = None
    reviewer_role: Optional[str] = None
    authorization_scope: Optional[str] = None
    review_gate_result: Optional[object] = None  # a Phase 15 ReviewGateResult
    subject_snapshot: Optional[StoredReviewSubjectSnapshot] = None
    requested_persistence_action: Optional[str] = None
    lifecycle_status: Optional[str] = None


@dataclass
class ReviewRecordDraft:
    """A production-shaped `ReviewRecord` draft (in-memory only; never persisted here).

    ``review_record_id`` and ``created_at`` are left ``None`` — a future controlled-DB
    writer assigns them at write time. Nothing here is stored.
    """

    review_record_id: Optional[str] = None  # assigned by a future controlled-DB writer
    subject_record_id: Optional[str] = None
    subject_record_type: Optional[str] = None
    owner_id: Optional[str] = None
    client_id: Optional[str] = None
    engagement_id: Optional[str] = None
    reviewer_role: Optional[str] = None
    requested_by: Optional[str] = None
    decision: Optional[str] = None
    next_output_status: Optional[str] = None
    next_review_status: Optional[str] = None
    next_lifecycle_status: Optional[str] = None
    authoritative: bool = False
    client_facing_approved: bool = False
    capsule_candidate_ready: bool = False
    reasons: List[str] = field(default_factory=list)
    warnings: List[str] = field(default_factory=list)
    source_reference_id: Optional[str] = None
    created_at: Optional[str] = None  # reserved for future controlled-DB assignment


@dataclass
class ReviewPersistenceDecision:
    """Result of the pre-persistence governance checks (no side effects)."""

    permitted: bool = False
    persistence_action: Optional[str] = None
    reasons: List[str] = field(default_factory=list)
    warnings: List[str] = field(default_factory=list)


@dataclass
class ReviewWritePlan:
    """A no-op write plan a future controlled-DB writer would execute (not executed here)."""

    permitted: bool = False
    action: Optional[str] = None
    review_record_draft: Optional[ReviewRecordDraft] = None
    target_table: str = REVIEW_RECORDS_TABLE
    database_write_made: bool = False
    database_connection_made: bool = False
    requires_controlled_db_writer: bool = True
    prohibited_effects: List[str] = field(default_factory=lambda: list(PROHIBITED_EFFECTS))
    reasons: List[str] = field(default_factory=list)
    warnings: List[str] = field(default_factory=list)


@dataclass
class ReviewPersistenceResult:
    """The controlled result of preparing review persistence (no side effects)."""

    permitted: bool = False
    status: str = "rejected"
    write_plan: Optional[ReviewWritePlan] = None
    database_write_made: bool = False
    database_connection_made: bool = False
    llm_call_made: bool = False
    agentnet_call_made: bool = False
    network_call_made: bool = False
    capsule_publication_made: bool = False
    client_facing_output_created: bool = False
    stored_review_record_created: bool = False
    reasons: List[str] = field(default_factory=list)
    warnings: List[str] = field(default_factory=list)
