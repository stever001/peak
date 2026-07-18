"""Contracts for the Packet-Derived Review Orchestration Boundary (Phase 29).

**A review-planning boundary, not a review-approval phase and not a DB writer.** These
lightweight dataclasses describe how Peak organizes packet-derived outputs (safe references,
receipts, and metadata from prior phases) into **review-ready plans** for human reviewers —
review bundle drafts, review plan items, and review readiness assessments — **without approving
anything, executing anything, or writing to the database.**

Nothing here opens a database connection or imports SQLAlchemy / Alembic / ``peak.db``; executes
a live or mock agent/LLM; makes an AgentNet/MCP/resolver/connector/network call; creates
client-facing output; verifies financial impact; or publishes a capsule. Every "a call/write
happened" flag defaults to ``False``, and every draft stays ``draft`` / ``needs_review`` with
``approval_allowed=False`` and ``requires_human_review=True``. **"Ready for human review" never
means approved.**

This phase is analogous to Phase 26 (which planned agent task queue readiness without DB writes):
Phase 29 plans human-review readiness without DB writes. It is **DB-free**; future persistence of
review plans is deferred to a later phase. See
docs/PACKET_DERIVED_REVIEW_ORCHESTRATION_BOUNDARY.md and
docs/REVIEW_ORCHESTRATION_GOVERNANCE_POLICY.md.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import List, Optional

# The only review-orchestration action Phase 29 plans.
ALLOWED_REVIEW_ACTIONS = frozenset({"prepare_packet_review_plan"})

# Review-gate defaults carried onto every review bundle draft / plan item.
DEFAULT_OUTPUT_STATUS = "draft"
DEFAULT_REVIEW_STATUS = "needs_review"
DEFAULT_LIFECYCLE_STATUS = "draft"

# --- Review plan item types --------------------------------------------------------------
ITEM_SOURCE_INGESTION_REVIEW = "source_ingestion_review"
ITEM_EVIDENCE_REFERENCE_REVIEW = "evidence_reference_review"
ITEM_AGENT_TASK_QUEUE_REVIEW = "agent_task_queue_review"
ITEM_PACKET_PROCESSING_REVIEW = "packet_processing_review"
ITEM_CROSS_STAGE_CONSISTENCY_REVIEW = "cross_stage_consistency_review"
ITEM_MISSING_EVIDENCE_REVIEW = "missing_evidence_review"
ITEM_READINESS_EXCEPTION_REVIEW = "readiness_exception_review"

# --- Review subject types ----------------------------------------------------------------
SUBJECT_SOURCE_INGESTION = "source_ingestion_record"
SUBJECT_EVIDENCE_REFERENCE = "evidence_reference"
SUBJECT_AGENT_TASK_QUEUE = "agent_task_queue_record"
SUBJECT_PACKET_PROCESSING = "packet_processing_receipt"

# --- Review readiness states (deterministic) ---------------------------------------------
READY_FOR_HUMAN_REVIEW = "ready_for_human_review"  # ready to be reviewed — NOT approved
BLOCKED_NO_SUBJECTS = "blocked_no_subjects"
BLOCKED_INVALID_SCOPE = "blocked_invalid_scope"
BLOCKED_LIFECYCLE = "blocked_lifecycle"
BLOCKED_RAW_CONTENT = "blocked_raw_content"
BLOCKED_SECRET_LIKE_CONTENT = "blocked_secret_like_content"
BLOCKED_EXECUTION_INTENT = "blocked_execution_intent"
BLOCKED_APPROVAL_INTENT = "blocked_approval_intent"
BLOCKED_PUBLICATION_INTENT = "blocked_publication_intent"
BLOCKED_FINANCIAL_VERIFICATION_INTENT = "blocked_financial_verification_intent"

READINESS_STATES = frozenset({
    READY_FOR_HUMAN_REVIEW, BLOCKED_NO_SUBJECTS, BLOCKED_INVALID_SCOPE, BLOCKED_LIFECYCLE,
    BLOCKED_RAW_CONTENT, BLOCKED_SECRET_LIKE_CONTENT, BLOCKED_EXECUTION_INTENT,
    BLOCKED_APPROVAL_INTENT, BLOCKED_PUBLICATION_INTENT, BLOCKED_FINANCIAL_VERIFICATION_INTENT,
})
BLOCKED_STATES = frozenset(s for s in READINESS_STATES if s != READY_FOR_HUMAN_REVIEW)

# --- Orchestration-level outcomes --------------------------------------------------------
OUTCOME_DENIED = "denied"      # request-level governance denied the whole request
OUTCOME_PLANNED = "planned"    # a review bundle + plan items were produced (ready for review)
OUTCOME_BLOCKED = "blocked"    # request permitted but not review-ready (e.g. no subjects)


class StageName:
    """Deterministic stage identifiers reported on the result."""

    VALIDATE_REQUEST = "validate_request"
    BUILD_SUBJECT_REFS = "build_subject_refs"
    BUILD_REVIEW_ITEMS = "build_review_items"
    ASSESS_READINESS = "assess_readiness"


@dataclass
class ReviewSubjectReference:
    """A safe reference to one review subject (an id + type; never raw content)."""

    subject_ref_id: Optional[str] = None
    subject_type: Optional[str] = None
    owner_id: Optional[str] = None
    client_id: Optional[str] = None
    engagement_id: Optional[str] = None
    authorization_scope: Optional[str] = None


@dataclass
class PacketReviewOrchestrationRequest:
    """A request to prepare (never execute) a packet-derived human-review plan.

    Carries only ids/references and safe metadata — **never** a full ``packet_payload``, raw
    evidence/interview text, source bytes, generated agent output, arbitrary client content,
    credentials/secrets, DB URLs, raw SQL, or stack traces. ``context`` is optional safe metadata
    whose keys are scanned for prohibited terms.
    """

    owner_id: Optional[str] = None
    client_id: Optional[str] = None
    engagement_id: Optional[str] = None
    requested_by: Optional[str] = None
    requester_role: Optional[str] = None
    authorization_scope: Optional[str] = None
    idempotency_key: Optional[str] = None
    packet_processing_receipt_ref: Optional[str] = None
    source_ingestion_record_ids: List[str] = field(default_factory=list)
    evidence_reference_ids: List[str] = field(default_factory=list)
    agent_task_queue_record_ids: List[str] = field(default_factory=list)
    agent_task_queue_draft_refs: List[str] = field(default_factory=list)
    source_ingestion_receipt_refs: List[str] = field(default_factory=list)
    evidence_receipt_refs: List[str] = field(default_factory=list)
    task_queue_receipt_refs: List[str] = field(default_factory=list)
    reviewer_role: Optional[str] = None
    review_reason: Optional[str] = None
    strict_mode: bool = True
    requested_action: Optional[str] = "prepare_packet_review_plan"
    source_phase: Optional[str] = None
    lifecycle_status: Optional[str] = None
    context: Optional[dict] = None  # safe metadata only; keys scanned for prohibited terms


@dataclass
class ReviewPlanItem:
    """One review plan item grouping safe references for a human reviewer (no raw content)."""

    item_id: Optional[str] = None  # deterministic ref (e.g. "<idem>::item::<type>")
    item_type: Optional[str] = None
    subject_refs: List[str] = field(default_factory=list)  # safe ids only
    priority: int = 100
    required_reviewer_role: Optional[str] = None
    status: str = DEFAULT_REVIEW_STATUS
    reasons: List[str] = field(default_factory=list)
    warnings: List[str] = field(default_factory=list)


@dataclass
class ReviewBundleDraft:
    """A production-shaped but review-gated review bundle draft (in-memory only).

    ``review_bundle_id`` and ``created_at`` are left ``None`` — Phase 29 stores nothing; a future
    persistence phase (not this one) would assign them. Nothing here is approved or executed.
    """

    review_bundle_id: Optional[str] = None  # future persistence phase assigns; nothing stored
    owner_id: Optional[str] = None
    client_id: Optional[str] = None
    engagement_id: Optional[str] = None
    packet_processing_receipt_ref: Optional[str] = None
    source_ingestion_record_ids: List[str] = field(default_factory=list)
    evidence_reference_ids: List[str] = field(default_factory=list)
    agent_task_queue_record_ids: List[str] = field(default_factory=list)
    subject_refs: List[ReviewSubjectReference] = field(default_factory=list)
    reviewer_role: Optional[str] = None
    review_reason: Optional[str] = None
    review_scope: Optional[str] = None
    output_status: str = DEFAULT_OUTPUT_STATUS
    review_status: str = DEFAULT_REVIEW_STATUS
    lifecycle_status: str = DEFAULT_LIFECYCLE_STATUS
    authoritative: bool = False
    client_facing_approved: bool = False
    capsule_candidate_ready: bool = False
    financial_verified: bool = False
    execution_allowed: bool = False
    approval_allowed: bool = False
    publication_allowed: bool = False
    requires_human_review: bool = True
    reasons: List[str] = field(default_factory=list)
    warnings: List[str] = field(default_factory=list)
    created_at: Optional[str] = None  # reserved; Phase 29 stores nothing


@dataclass
class ReviewReadinessAssessment:
    """A deterministic review-readiness assessment (no approval, no execution)."""

    readiness_state: str = READY_FOR_HUMAN_REVIEW
    blocked: bool = False
    requires_human_review: bool = True
    approval_allowed: bool = False  # never True in Phase 29
    subject_count: int = 0
    reasons: List[str] = field(default_factory=list)
    warnings: List[str] = field(default_factory=list)


@dataclass
class PacketReviewPlan:
    """The controlled, no-side-effect review plan derived from the request."""

    permitted: bool = False
    review_bundles: List[ReviewBundleDraft] = field(default_factory=list)
    review_plan_items: List[ReviewPlanItem] = field(default_factory=list)
    readiness_assessments: List[ReviewReadinessAssessment] = field(default_factory=list)
    controlled_write_requests: List[object] = field(default_factory=list)  # Phase 29 produces none
    direct_database_write_made: bool = False
    database_connection_made: bool = False
    sql_execution_made: bool = False
    stored_record_created: bool = False
    review_approval_made: bool = False
    agent_execution_made: bool = False
    mock_agent_execution_made: bool = False
    llm_call_made: bool = False
    agentnet_call_made: bool = False
    resolver_call_made: bool = False
    network_call_made: bool = False
    client_facing_output_created: bool = False
    financial_verification_made: bool = False
    capsule_publication_made: bool = False
    reasons: List[str] = field(default_factory=list)
    warnings: List[str] = field(default_factory=list)


@dataclass
class ReviewOrchestrationValidationResult:
    """Result of the deterministic request-level validation."""

    permitted: bool = False
    identity_valid: bool = False
    scope_valid: bool = False
    has_subjects: bool = False
    contains_prohibited_content: bool = False
    reasons: List[str] = field(default_factory=list)
    warnings: List[str] = field(default_factory=list)


@dataclass
class PacketReviewOrchestrationResult:
    """The controlled result of preparing a packet-derived review plan (no side effects)."""

    outcome: str = OUTCOME_DENIED
    permitted: bool = False
    reason_code: Optional[str] = None
    status: str = "rejected"
    validation_result: Optional[ReviewOrchestrationValidationResult] = None
    plan: Optional[PacketReviewPlan] = None
    review_bundle_count: int = 0
    review_plan_item_count: int = 0
    readiness_assessment_count: int = 0
    subject_count: int = 0
    blocked_subject_count: int = 0
    controlled_write_request_count: int = 0
    stages_completed: List[str] = field(default_factory=list)
    stages_skipped: List[str] = field(default_factory=list)
    reasons: List[str] = field(default_factory=list)
    warnings: List[str] = field(default_factory=list)
    # Aggregate side-effect flags — all stay False in Phase 29.
    direct_database_write_made: bool = False
    database_connection_made: bool = False
    sql_execution_made: bool = False
    stored_record_created: bool = False
    review_approval_made: bool = False
    client_facing_output_created: bool = False
    financial_verification_made: bool = False
    capsule_publication_made: bool = False
    agent_execution_made: bool = False
    mock_agent_execution_made: bool = False
    llm_call_made: bool = False
    agentnet_call_made: bool = False
    resolver_call_made: bool = False
    network_call_made: bool = False
