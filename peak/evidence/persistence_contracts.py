"""Contracts for the Evidence Persistence Mapping (Phase 18).

**DB-aware but not DB-writing.** These dataclasses describe how a Phase 14 normalized
evidence output is mapped into a *future* controlled write plan for the `evidence_references`
table — the persistence draft, the request, the decision, and the mapping result — **without
connecting to a database, importing a live SQLAlchemy session, executing SQL, persisting
records, or reading records.**

This package (``peak.evidence``) is domain-specific evidence persistence mapping. It is
deliberately kept out of ``peak.db`` and imports no SQLAlchemy, no Alembic, and no
``peak.db`` session/model modules. It *does* bridge two existing boundaries — the Phase 14
worker contracts (``peak.workers``) and the Phase 17 controlled-write contracts
(``peak.persistence``) — because Phase 18 connects them.

**Source contracts only — no stored records.** Nothing here opens a database connection,
runs SQL, writes a file, calls an LLM/AgentNet/MCP/resolver, touches the network, produces
client-facing output, or publishes a capsule. See docs/EVIDENCE_PERSISTENCE_MAPPING.md and
docs/EVIDENCE_WRITE_PLAN_POLICY.md.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import List, Optional

# The only persistence action Phase 18 plans, and the table/action it maps to.
ALLOWED_PERSISTENCE_ACTION = "prepare_evidence_reference_write_plan"
TARGET_TABLE = "evidence_references"
TARGET_ACTION = "create_draft"

# Review-gated posture defaults carried onto every evidence persistence draft.
DEFAULT_OUTPUT_STATUS = "draft"
DEFAULT_REVIEW_STATUS = "needs_review"
DEFAULT_LIFECYCLE_STATUS = "active"


@dataclass
class EvidencePersistenceSubjectSnapshot:
    """The stored parent/source/engagement subject that authorizes the evidence write.

    Because the normalized evidence itself may have **no stored DB record yet**, this
    snapshot is the scope anchor for the future write: ``stored_authorization_scope`` is the
    parent record's own persisted scope — the value a future controlled writer must compare
    the request scope against. In Phase 18 the caller supplies it in memory; a future
    controlled-DB reader would load it.
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
class EvidencePersistenceRequest:
    """A request to map a normalized evidence output into a controlled write plan."""

    owner_id: Optional[str] = None
    client_id: Optional[str] = None
    engagement_id: Optional[str] = None
    requested_by: Optional[str] = None
    requester_role: Optional[str] = None
    authorization_scope: Optional[str] = None
    normalization_result: Optional[object] = None  # a Phase 14 EvidenceNormalizationResult
    normalized_record: Optional[object] = None  # a Phase 14 NormalizedEvidenceRecord
    subject_snapshot: Optional[EvidencePersistenceSubjectSnapshot] = None
    requested_persistence_action: Optional[str] = None
    source_phase: Optional[str] = None
    idempotency_key: Optional[str] = None
    lifecycle_status: Optional[str] = None


@dataclass
class EvidencePersistenceDraft:
    """A production-shaped but review-gated evidence draft (in-memory only; never stored).

    ``evidence_record_id`` and ``created_at`` are left ``None`` — a future controlled DB
    writer assigns them. The review-gate posture is preserved: ``draft`` / ``needs_review``,
    non-authoritative, not client-facing, not a capsule candidate.
    """

    evidence_record_id: Optional[str] = None  # assigned by a future controlled-DB writer
    owner_id: Optional[str] = None
    client_id: Optional[str] = None
    engagement_id: Optional[str] = None
    source_reference_id: Optional[str] = None
    evidence_type: Optional[str] = None
    normalized_title: Optional[str] = None
    normalized_summary: Optional[str] = None
    observed_condition: Optional[str] = None
    operational_area: Optional[str] = None
    inventory_process_area: Optional[str] = None
    source_type: Optional[str] = None
    source_location: Optional[str] = None
    confidence_level: str = "low"
    output_status: str = DEFAULT_OUTPUT_STATUS
    review_status: str = DEFAULT_REVIEW_STATUS
    lifecycle_status: str = DEFAULT_LIFECYCLE_STATUS
    authoritative: bool = False
    client_facing_approved: bool = False
    capsule_candidate_ready: bool = False
    reasons: List[str] = field(default_factory=list)
    warnings: List[str] = field(default_factory=list)
    created_at: Optional[str] = None  # reserved for future controlled-DB assignment


@dataclass
class EvidencePersistenceDecision:
    """Result of the pre-mapping governance checks (no side effects)."""

    permitted: bool = False
    persistence_action: Optional[str] = None
    target_table: Optional[str] = None
    requested_action: Optional[str] = None
    reasons: List[str] = field(default_factory=list)
    warnings: List[str] = field(default_factory=list)


@dataclass
class EvidencePersistenceMappingResult:
    """The controlled result of mapping evidence into a write plan (no side effects)."""

    permitted: bool = False
    status: str = "rejected"
    evidence_persistence_draft: Optional[EvidencePersistenceDraft] = None
    controlled_write_request: Optional[object] = None  # a Phase 17 ControlledWriteRequest
    controlled_write_result: Optional[object] = None  # a Phase 17 ControlledWriteResult
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
