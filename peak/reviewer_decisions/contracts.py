"""Contracts for the Internal Reviewer Decision Boundary (Phase 32).

**A decision-planning boundary, not a review-approval phase and not a persistence phase.** These
lightweight dataclasses describe how Peak represents a **structured internal reviewer decision**
against a review bundle / review plan items — as a review-gated decision *draft*, a
decision-readiness assessment, and a deterministic **routing recommendation** — **without
persisting anything, approving anything, or touching the database.**

Nothing here opens a database connection or imports SQLAlchemy / Alembic / ``peak.db``; calls the
Phase 22 review writer; creates a ``review_records`` row; calls ``approve_internal``; executes an
agent (live or mock); makes an LLM / AgentNet / MCP / resolver / connector / network call; creates
client-facing output; verifies financial impact; or publishes a capsule. Every "a call/write
happened" flag defaults to ``False``, and every draft stays ``draft`` / ``needs_review`` with
``approval_allowed=False`` and ``requires_human_review=True``.

**``ready_for_internal_use`` is not approval** — it does not authorize client-facing output,
financial verification, capsule publication, agent execution, or a ``review_records`` write. This
phase is analogous to Phase 29 (which planned review bundles without DB writes): Phase 32 plans
reviewer decisions without DB writes. It is **DB-free**; future persistence of reviewer decisions
is deferred to a later phase (Phase 33). See docs/INTERNAL_REVIEWER_DECISION_BOUNDARY.md and
docs/INTERNAL_REVIEWER_DECISION_GOVERNANCE_POLICY.md.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import List, Optional

# The only decision-planning action Phase 32 plans.
ALLOWED_DECISION_ACTIONS = frozenset({"prepare_internal_reviewer_decision"})

# Review-gate defaults carried onto every decision draft.
DEFAULT_OUTPUT_STATUS = "draft"
DEFAULT_REVIEW_STATUS = "needs_review"
DEFAULT_LIFECYCLE_STATUS = "draft"

# --- Allowed decision intents (deterministic) --------------------------------------------
NEEDS_MORE_EVIDENCE = "needs_more_evidence"
RETURN_FOR_REVISION = "return_for_revision"
READY_FOR_INTERNAL_USE = "ready_for_internal_use"  # NOT approval; internal-only readiness
BLOCKED_BY_SCOPE = "blocked_by_scope"
BLOCKED_BY_QUALITY = "blocked_by_quality"
BLOCKED_BY_MISSING_SOURCE = "blocked_by_missing_source"
REJECTED_FOR_POLICY = "rejected_for_policy"
DEFER_REVIEW = "defer_review"

ALLOWED_DECISION_INTENTS = frozenset({
    NEEDS_MORE_EVIDENCE, RETURN_FOR_REVISION, READY_FOR_INTERNAL_USE, BLOCKED_BY_SCOPE,
    BLOCKED_BY_QUALITY, BLOCKED_BY_MISSING_SOURCE, REJECTED_FOR_POLICY, DEFER_REVIEW,
})

# Route (recommendation only) per decision intent. return_for_revision is refined by
# ``return_to_stage`` (see ALLOWED_RETURN_STAGES) in the mapper.
INTENT_ROUTING = {
    NEEDS_MORE_EVIDENCE: "evidence_collection",
    RETURN_FOR_REVISION: "packet_processing_revision",
    READY_FOR_INTERNAL_USE: "internal_report_planning_candidate",
    BLOCKED_BY_SCOPE: "engagement_scope_review",
    BLOCKED_BY_QUALITY: "quality_remediation",
    BLOCKED_BY_MISSING_SOURCE: "source_ingestion_followup",
    REJECTED_FOR_POLICY: "governance_exception_review",
    DEFER_REVIEW: "review_backlog",
}

# Safe ``return_to_stage`` values for return_for_revision -> "<stage>_revision" routing.
ALLOWED_RETURN_STAGES = frozenset({"packet_processing", "source_ingestion", "evidence", "task_queue"})

# --- Decision readiness states (deterministic) -------------------------------------------
READY_TO_RECORD = "ready_to_record"  # well-formed decision draft; ready for a human/future writer
BLOCKED_INVALID_SCOPE = "blocked_invalid_scope"
BLOCKED_LIFECYCLE = "blocked_lifecycle"
BLOCKED_MISSING_REVIEW_BUNDLE = "blocked_missing_review_bundle"
BLOCKED_UNSUPPORTED_INTENT = "blocked_unsupported_intent"
BLOCKED_DISALLOWED_INTENT = "blocked_disallowed_intent"  # approval/publication/execution/etc.
BLOCKED_RAW_CONTENT = "blocked_raw_content"
BLOCKED_SECRET_LIKE_CONTENT = "blocked_secret_like_content"

READINESS_STATES = frozenset({
    READY_TO_RECORD, BLOCKED_INVALID_SCOPE, BLOCKED_LIFECYCLE, BLOCKED_MISSING_REVIEW_BUNDLE,
    BLOCKED_UNSUPPORTED_INTENT, BLOCKED_DISALLOWED_INTENT, BLOCKED_RAW_CONTENT,
    BLOCKED_SECRET_LIKE_CONTENT,
})

# --- Orchestration-level outcomes --------------------------------------------------------
OUTCOME_DENIED = "denied"      # request-level governance denied the whole request
OUTCOME_PLANNED = "planned"    # a decision draft + routing plan were produced


class StageName:
    """Deterministic stage identifiers reported on the result."""

    VALIDATE_REQUEST = "validate_request"
    BUILD_DECISION_DRAFT = "build_decision_draft"
    BUILD_ROUTING_PLAN = "build_routing_plan"
    ASSESS_READINESS = "assess_readiness"


@dataclass
class InternalReviewerDecisionRequest:
    """A request to prepare (never persist) a structured internal reviewer decision.

    Carries only ids/references, short safe labels, and a short safe summary — **never** a full
    ``packet_payload``, raw evidence/interview text, source bytes, generated agent output,
    arbitrary client content, credentials/secrets, DB URLs, raw SQL, stack traces, or
    client-facing language. ``context`` is optional safe metadata whose keys are scanned.
    """

    owner_id: Optional[str] = None
    client_id: Optional[str] = None
    engagement_id: Optional[str] = None
    requested_by: Optional[str] = None
    requester_role: Optional[str] = None
    authorization_scope: Optional[str] = None
    idempotency_key: Optional[str] = None
    review_bundle_ref: Optional[str] = None
    review_bundle_record_id: Optional[str] = None
    review_bundle_draft_ref: Optional[str] = None
    review_plan_item_refs: List[str] = field(default_factory=list)
    evidence_reference_ids: List[str] = field(default_factory=list)
    source_ingestion_record_ids: List[str] = field(default_factory=list)
    agent_task_queue_record_ids: List[str] = field(default_factory=list)
    reviewer_role: Optional[str] = None
    decision_intent: Optional[str] = None
    decision_reason_code: Optional[str] = None
    safe_decision_summary: Optional[str] = None
    return_to_stage: Optional[str] = None
    requested_followup_actions: List[str] = field(default_factory=list)
    strict_mode: bool = True
    requested_action: Optional[str] = "prepare_internal_reviewer_decision"
    source_phase: Optional[str] = None
    lifecycle_status: Optional[str] = None
    context: Optional[dict] = None  # safe metadata only; keys scanned for prohibited terms


@dataclass
class InternalReviewerDecisionDraft:
    """A production-shaped but review-gated internal reviewer decision draft (in-memory only).

    ``reviewer_decision_id`` and ``created_at`` are left ``None`` — Phase 32 stores nothing; a
    future persistence phase (Phase 33) would assign them. Nothing here is approved or persisted.
    """

    reviewer_decision_id: Optional[str] = None  # future persistence phase assigns; nothing stored
    owner_id: Optional[str] = None
    client_id: Optional[str] = None
    engagement_id: Optional[str] = None
    review_bundle_ref: Optional[str] = None
    review_bundle_record_id: Optional[str] = None
    review_bundle_draft_ref: Optional[str] = None
    review_plan_item_refs: List[str] = field(default_factory=list)
    evidence_reference_ids: List[str] = field(default_factory=list)
    source_ingestion_record_ids: List[str] = field(default_factory=list)
    agent_task_queue_record_ids: List[str] = field(default_factory=list)
    reviewer_role: Optional[str] = None
    decision_intent: Optional[str] = None
    decision_reason_code: Optional[str] = None
    safe_decision_summary: Optional[str] = None
    return_to_stage: Optional[str] = None
    requested_followup_actions: List[str] = field(default_factory=list)
    authorization_scope: Optional[str] = None
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
    client_facing_output_created: bool = False
    review_approval_made: bool = False
    reasons: List[str] = field(default_factory=list)
    warnings: List[str] = field(default_factory=list)
    created_at: Optional[str] = None  # reserved; Phase 32 stores nothing


@dataclass
class ReviewerDecisionRoutingPlan:
    """A deterministic routing recommendation (no action is taken)."""

    decision_intent: Optional[str] = None
    route_to: Optional[str] = None
    return_to_stage: Optional[str] = None
    recommendation_only: bool = True
    requested_followup_actions: List[str] = field(default_factory=list)
    reasons: List[str] = field(default_factory=list)
    warnings: List[str] = field(default_factory=list)


@dataclass
class ReviewerDecisionReadinessAssessment:
    """A deterministic decision-readiness assessment (no approval, no persistence)."""

    readiness_state: str = READY_TO_RECORD
    blocked: bool = False
    requires_human_review: bool = True
    approval_allowed: bool = False  # never True in Phase 32
    reasons: List[str] = field(default_factory=list)
    warnings: List[str] = field(default_factory=list)


@dataclass
class ReviewerDecisionValidationResult:
    """Result of the deterministic request-level validation."""

    permitted: bool = False
    identity_valid: bool = False
    scope_valid: bool = False
    has_review_bundle_ref: bool = False
    intent_valid: bool = False
    contains_prohibited_content: bool = False
    reasons: List[str] = field(default_factory=list)
    warnings: List[str] = field(default_factory=list)


@dataclass
class InternalReviewerDecisionResult:
    """The controlled result of preparing an internal reviewer decision (no side effects)."""

    outcome: str = OUTCOME_DENIED
    permitted: bool = False
    reason_code: Optional[str] = None
    status: str = "rejected"
    validation_result: Optional[ReviewerDecisionValidationResult] = None
    decision_draft: Optional[InternalReviewerDecisionDraft] = None
    routing_plan: Optional[ReviewerDecisionRoutingPlan] = None
    readiness_assessment: Optional[ReviewerDecisionReadinessAssessment] = None
    decision_draft_count: int = 0
    routing_plan_count: int = 0
    readiness_assessment_count: int = 0
    controlled_write_request_count: int = 0  # Phase 32 produces none
    stages_completed: List[str] = field(default_factory=list)
    stages_skipped: List[str] = field(default_factory=list)
    reasons: List[str] = field(default_factory=list)
    warnings: List[str] = field(default_factory=list)
    # Aggregate side-effect flags — all stay False in Phase 32.
    direct_database_write_made: bool = False
    database_connection_made: bool = False
    sql_execution_made: bool = False
    stored_record_created: bool = False
    review_records_write_made: bool = False
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
