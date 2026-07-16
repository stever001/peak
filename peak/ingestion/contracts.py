"""Contracts for the Engagement Packet Ingestion Boundary (Phase 23).

**An ingestion boundary, not a direct importer and not a DB writer.** These lightweight
dataclasses describe how Peak accepts an external ``EngagementPacket``, validates its
contract/shape, and derives **production-shaped but review-gated** ingestion plans — a
``SourceIngestionDraft``, derived Phase 14 evidence normalization requests, derived Phase 13
agent task requests, and (optionally) no-op Phase 17 controlled write requests — **without
writing anything to the database.** Packet contents are not stored in this phase; ingestion
plans are not writes.

Nothing here opens a database connection or imports SQLAlchemy / Alembic / ``peak.db``; makes
no LLM, AgentNet, MCP, resolver, network, or file call; creates no client-facing output; and
publishes no capsule. Every "a call/write happened" flag defaults to ``False``, and every
derived record stays ``draft`` / ``needs_review``. See
docs/ENGAGEMENT_PACKET_INGESTION_BOUNDARY.md and docs/PACKET_TO_CONTROLLED_WORKFLOW_POLICY.md.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import List, Optional

# The only ingestion action Phase 23 plans.
ALLOWED_INGESTION_ACTIONS = frozenset({"prepare_packet_ingestion_plan"})

# The future controlled-write target for a source ingestion record (Phase 17 allowlist).
SOURCE_INGESTION_TABLE = "source_ingestion_records"
SOURCE_INGESTION_ACTION = "create_source_ingestion_record"

# Review-gate defaults carried onto every packet-derived draft.
DEFAULT_OUTPUT_STATUS = "draft"
DEFAULT_REVIEW_STATUS = "needs_review"
DEFAULT_LIFECYCLE_STATUS = "active"

# Deterministic packet sections the mapper understands.
EVIDENCE_LIKE_SECTIONS = (
    "evidence_items",
    "source_references",
    "interview_notes",
    "walkaround_observations",
    "inventory_observations",
)
AGENT_TASK_SECTION = "requested_agent_tasks"


@dataclass
class EngagementPacketReference:
    """A pointer to an external EngagementPacket (metadata only; no packet contents)."""

    packet_reference_id: Optional[str] = None
    owner_id: Optional[str] = None
    client_id: Optional[str] = None
    engagement_id: Optional[str] = None
    packet_schema_name: Optional[str] = None
    packet_schema_version: Optional[str] = None
    packet_source_type: Optional[str] = None
    packet_location_reference: Optional[str] = None  # a reference/pointer, never a live path read
    packet_hash: Optional[str] = None
    captured_by: Optional[str] = None
    captured_at: Optional[str] = None
    authorization_scope: Optional[str] = None
    lifecycle_status: Optional[str] = None


@dataclass
class PacketIngestionRequest:
    """A request to prepare (never execute) an ingestion plan from an engagement packet."""

    owner_id: Optional[str] = None
    client_id: Optional[str] = None
    engagement_id: Optional[str] = None
    requested_by: Optional[str] = None
    requester_role: Optional[str] = None
    authorization_scope: Optional[str] = None
    packet_reference: Optional[EngagementPacketReference] = None
    packet_payload: Optional[object] = None  # a dict-like structure; never persisted here
    requested_ingestion_action: Optional[str] = None
    source_phase: Optional[str] = None
    idempotency_key: Optional[str] = None
    lifecycle_status: Optional[str] = None


@dataclass
class PacketValidationResult:
    """Result of the deterministic packet contract/shape validation."""

    permitted: bool = False
    schema_valid: bool = False
    identity_valid: bool = False
    scope_valid: bool = False
    contains_client_data: bool = False
    allowed_for_ingestion: bool = False
    reasons: List[str] = field(default_factory=list)
    warnings: List[str] = field(default_factory=list)
    missing_items: List[str] = field(default_factory=list)


@dataclass
class SourceIngestionDraft:
    """A production-shaped but review-gated source ingestion draft (in-memory only).

    ``source_ingestion_record_id`` and ``created_at`` are left ``None`` — a *future* narrow
    controlled DB writer (not this phase) assigns them. Nothing here is persisted.
    """

    source_ingestion_record_id: Optional[str] = None  # future controlled-DB writer assigns
    owner_id: Optional[str] = None
    client_id: Optional[str] = None
    engagement_id: Optional[str] = None
    packet_reference_id: Optional[str] = None
    packet_schema_name: Optional[str] = None
    packet_schema_version: Optional[str] = None
    packet_source_type: Optional[str] = None
    packet_location_reference: Optional[str] = None
    packet_hash: Optional[str] = None
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
class PacketDerivedEvidencePlan:
    """Phase 14 evidence normalization requests derived from packet sections (not persisted)."""

    permitted: bool = False
    evidence_request_count: int = 0
    evidence_requests: List[object] = field(default_factory=list)  # Phase 14 EvidenceNormalizationRequest
    reasons: List[str] = field(default_factory=list)
    warnings: List[str] = field(default_factory=list)


@dataclass
class PacketDerivedAgentTaskPlan:
    """Phase 13 agent task requests derived from packet requests (never executed)."""

    permitted: bool = False
    agent_task_request_count: int = 0
    agent_task_requests: List[object] = field(default_factory=list)  # Phase 13 AgentTaskRequest
    reasons: List[str] = field(default_factory=list)
    warnings: List[str] = field(default_factory=list)


@dataclass
class PacketIngestionPlan:
    """The controlled, no-side-effect ingestion plan derived from a packet."""

    permitted: bool = False
    source_ingestion_draft: Optional[SourceIngestionDraft] = None
    evidence_plan: Optional[PacketDerivedEvidencePlan] = None
    agent_task_plan: Optional[PacketDerivedAgentTaskPlan] = None
    controlled_write_requests: List[object] = field(default_factory=list)  # Phase 17 CWRs (plans only)
    direct_database_write_made: bool = False
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
class PacketIngestionResult:
    """The controlled result of preparing packet ingestion (no side effects)."""

    permitted: bool = False
    status: str = "rejected"
    validation_result: Optional[PacketValidationResult] = None
    ingestion_plan: Optional[PacketIngestionPlan] = None
    direct_database_write_made: bool = False
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
