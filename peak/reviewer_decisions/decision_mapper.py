"""Deterministic internal-reviewer-decision mapping helpers (Phase 32).

Maps safe review-bundle / review-plan-item references and safe reviewer selections into an
internal reviewer **decision draft**, a **routing recommendation**, and a decision-readiness
assessment:

    InternalReviewerDecisionRequest (safe references + short safe labels)
      -> InternalReviewerDecisionDraft   (review-gated; never persisted; never approved)
      -> ReviewerDecisionRoutingPlan     (recommendation only; no action taken)
      -> ReviewerDecisionReadinessAssessment
      -> no DB write, no approval, no execution, no review_records write

Nothing here opens a database connection or imports SQLAlchemy / Alembic / ``peak.db``; calls the
Phase 22 review writer; creates a ``review_records`` row; approves anything; executes an agent;
makes an LLM / AgentNet / MCP / resolver / connector / network call; creates client-facing output;
verifies financial impact; or publishes a capsule. It imports only stdlib plus this package's own
DB-free contracts/governance. **Phase 32 is DB-free**: it produces **no** ``ControlledWriteRequest``
objects and writes nothing; future persistence of reviewer decisions is deferred to Phase 33.

**``ready_for_internal_use`` is not approval.** This mirrors Phase 29: it plans reviewer decisions
exactly as Phase 29 planned review bundles — without writing or approving anything. See
docs/INTERNAL_REVIEWER_DECISION_BOUNDARY.md and
docs/INTERNAL_REVIEWER_DECISION_GOVERNANCE_POLICY.md.
"""

from __future__ import annotations

from typing import Optional

from .contracts import (
    ALLOWED_RETURN_STAGES,
    INTENT_ROUTING,
    OUTCOME_DENIED,
    OUTCOME_PLANNED,
    READY_TO_RECORD,
    RETURN_FOR_REVISION,
    InternalReviewerDecisionDraft,
    InternalReviewerDecisionRequest,
    InternalReviewerDecisionResult,
    ReviewerDecisionReadinessAssessment,
    ReviewerDecisionRoutingPlan,
    ReviewerDecisionValidationResult,
    StageName,
)
from .governance import (
    _is_blank,
    evaluate_internal_reviewer_decision_request,
)

_PLAN_WARNING = (
    "internal reviewer decision plans are not approvals and not writes — no database connection is "
    "opened, nothing is approved, no review_records row is written, and no agent/LLM/AgentNet/"
    "resolver/network call is made; a human (or a future Phase 33 writer) acts on these drafts"
)
_READY_INTERNAL_WARNING = (
    "ready_for_internal_use means internal reliance readiness only — it is NOT approval and does "
    "not authorize client-facing output, financial verification, capsule publication, agent "
    "execution, or a review_records write"
)


def validate_internal_reviewer_decision_request(
    request: InternalReviewerDecisionRequest,
) -> ReviewerDecisionValidationResult:
    """Build the structured request-level ``ReviewerDecisionValidationResult``."""
    from .contracts import ALLOWED_DECISION_INTENTS

    governance = evaluate_internal_reviewer_decision_request(request)
    identity_valid = all(
        not _is_blank(getattr(request, a, None))
        for a in ("owner_id", "client_id", "engagement_id"))
    scope_valid = not _is_blank(getattr(request, "authorization_scope", None))
    has_bundle = not _is_blank(getattr(request, "review_bundle_ref", None)) or not _is_blank(
        getattr(request, "review_bundle_record_id", None))
    intent_valid = getattr(request, "decision_intent", None) in ALLOWED_DECISION_INTENTS
    contains_prohibited = any(
        t in " ".join(governance.reasons).lower()
        for t in ("secret", "raw-content", "raw content", "arbitrary content", "db-url", "raw-sql"))
    return ReviewerDecisionValidationResult(
        permitted=governance.permitted,
        identity_valid=identity_valid,
        scope_valid=scope_valid,
        has_review_bundle_ref=has_bundle,
        intent_valid=intent_valid,
        contains_prohibited_content=contains_prohibited,
        reasons=list(governance.reasons),
        warnings=list(governance.warnings),
    )


def _route_for(request: InternalReviewerDecisionRequest) -> str:
    """Deterministic route recommendation for the decision intent (refined by return_to_stage)."""
    intent = getattr(request, "decision_intent", None)
    if intent == RETURN_FOR_REVISION:
        stage = getattr(request, "return_to_stage", None)
        if stage in ALLOWED_RETURN_STAGES:
            return f"{stage}_revision"
        return INTENT_ROUTING[RETURN_FOR_REVISION]
    return INTENT_ROUTING.get(intent, "review_backlog")


def build_decision_draft(request: InternalReviewerDecisionRequest) -> InternalReviewerDecisionDraft:
    """Map one valid request into a review-gated ``InternalReviewerDecisionDraft`` (never stored)."""
    warnings = [_PLAN_WARNING]
    from .contracts import READY_FOR_INTERNAL_USE
    if getattr(request, "decision_intent", None) == READY_FOR_INTERNAL_USE:
        warnings.append(_READY_INTERNAL_WARNING)
    return InternalReviewerDecisionDraft(
        reviewer_decision_id=None,  # Phase 32 stores nothing; a future phase would assign this
        owner_id=request.owner_id, client_id=request.client_id, engagement_id=request.engagement_id,
        review_bundle_ref=getattr(request, "review_bundle_ref", None),
        review_bundle_record_id=getattr(request, "review_bundle_record_id", None),
        review_bundle_draft_ref=getattr(request, "review_bundle_draft_ref", None),
        review_plan_item_refs=list(getattr(request, "review_plan_item_refs", None) or []),
        evidence_reference_ids=list(getattr(request, "evidence_reference_ids", None) or []),
        source_ingestion_record_ids=list(getattr(request, "source_ingestion_record_ids", None) or []),
        agent_task_queue_record_ids=list(getattr(request, "agent_task_queue_record_ids", None) or []),
        reviewer_role=getattr(request, "reviewer_role", None),
        decision_intent=getattr(request, "decision_intent", None),
        decision_reason_code=getattr(request, "decision_reason_code", None),
        safe_decision_summary=getattr(request, "safe_decision_summary", None),
        return_to_stage=getattr(request, "return_to_stage", None),
        requested_followup_actions=list(getattr(request, "requested_followup_actions", None) or []),
        authorization_scope=getattr(request, "authorization_scope", None),
        output_status="draft", review_status="needs_review", lifecycle_status="draft",
        authoritative=False, client_facing_approved=False, capsule_candidate_ready=False,
        financial_verified=False, execution_allowed=False, approval_allowed=False,
        publication_allowed=False, requires_human_review=True, client_facing_output_created=False,
        review_approval_made=False, reasons=[], warnings=warnings, created_at=None)


def build_routing_plan(request: InternalReviewerDecisionRequest) -> ReviewerDecisionRoutingPlan:
    """Build the deterministic routing recommendation (no action is taken)."""
    return ReviewerDecisionRoutingPlan(
        decision_intent=getattr(request, "decision_intent", None),
        route_to=_route_for(request),
        return_to_stage=getattr(request, "return_to_stage", None),
        recommendation_only=True,
        requested_followup_actions=list(getattr(request, "requested_followup_actions", None) or []),
        reasons=[], warnings=[_PLAN_WARNING])


def _denied_result(request, governance, validation_result) -> InternalReviewerDecisionResult:
    """A side-effect-free denied result carrying a blocked readiness assessment."""
    from .contracts import BLOCKED_INVALID_SCOPE
    assessment = ReviewerDecisionReadinessAssessment(
        readiness_state=governance.readiness_state or BLOCKED_INVALID_SCOPE,
        blocked=True, reasons=list(governance.reasons))
    return InternalReviewerDecisionResult(
        outcome=OUTCOME_DENIED, permitted=False,
        reason_code=governance.reason_code or "reviewer_decision_denied",
        status="rejected", validation_result=validation_result,
        decision_draft=None, routing_plan=None, readiness_assessment=assessment,
        decision_draft_count=0, routing_plan_count=0, readiness_assessment_count=1,
        controlled_write_request_count=0,
        stages_completed=[StageName.VALIDATE_REQUEST],
        stages_skipped=[StageName.BUILD_DECISION_DRAFT, StageName.BUILD_ROUTING_PLAN,
                        StageName.ASSESS_READINESS],
        reasons=list(governance.reasons), warnings=[])


def prepare_internal_reviewer_decision(
    request: InternalReviewerDecisionRequest,
) -> InternalReviewerDecisionResult:
    """Prepare a no-side-effect internal reviewer decision draft + routing recommendation.

    Public entry point. Returns a fully typed ``InternalReviewerDecisionResult`` with all
    side-effect flags ``False``. Nothing is approved, executed, or written; no ``review_records``
    row is created. **``ready_for_internal_use`` is not approval.**
    """
    governance = evaluate_internal_reviewer_decision_request(request)
    validation_result = validate_internal_reviewer_decision_request(request)
    if not governance.permitted:
        return _denied_result(request, governance, validation_result)

    draft = build_decision_draft(request)
    routing_plan = build_routing_plan(request)
    assessment = ReviewerDecisionReadinessAssessment(
        readiness_state=READY_TO_RECORD, blocked=False,
        warnings=["ready_to_record means the decision draft is well-formed for a human/future "
                  "writer; it is not an approval"])

    return InternalReviewerDecisionResult(
        outcome=OUTCOME_PLANNED, permitted=True, reason_code=None,
        status="decision_plan_prepared", validation_result=validation_result,
        decision_draft=draft, routing_plan=routing_plan, readiness_assessment=assessment,
        decision_draft_count=1, routing_plan_count=1, readiness_assessment_count=1,
        controlled_write_request_count=0,
        stages_completed=[StageName.VALIDATE_REQUEST, StageName.BUILD_DECISION_DRAFT,
                          StageName.BUILD_ROUTING_PLAN, StageName.ASSESS_READINESS],
        stages_skipped=[], reasons=[], warnings=[_PLAN_WARNING])
