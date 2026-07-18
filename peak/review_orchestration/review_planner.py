"""Deterministic packet-derived review-planning helpers (Phase 29).

Maps safe packet-derived references (source-ingestion ids, evidence-reference ids, agent
task-queue ids, and packet-processing / receipt refs) into **review-ready** plans for human
reviewers:

    PacketReviewOrchestrationRequest (safe references only)
      -> ReviewSubjectReference[]        (id + type; never raw content)
      -> ReviewPlanItem[]                (grouped safe references; needs_review)
      -> ReviewBundleDraft               (review-gated; never persisted; never approved)
      -> ReviewReadinessAssessment       (ready_for_human_review — NOT approved)
      -> no DB write, no approval, no execution

Nothing here opens a database connection or imports SQLAlchemy / Alembic / ``peak.db``; approves
anything; executes a live or mock agent/LLM; makes an AgentNet/MCP/resolver/connector/network
call; creates client-facing output; verifies financial impact; or publishes a capsule. It imports
only stdlib plus this package's own DB-free contracts/governance. **Phase 29 is DB-free**: it
produces **no** ``ControlledWriteRequest`` objects and writes nothing; future persistence of
review plans is deferred to a later phase.

This mirrors Phase 26: it prepares review-readiness plans exactly as Phase 26 prepared task-queue
readiness plans — without writing or approving anything. See
docs/PACKET_DERIVED_REVIEW_ORCHESTRATION_BOUNDARY.md and
docs/REVIEW_ORCHESTRATION_GOVERNANCE_POLICY.md.
"""

from __future__ import annotations

from typing import List

from .contracts import (
    ITEM_AGENT_TASK_QUEUE_REVIEW,
    ITEM_CROSS_STAGE_CONSISTENCY_REVIEW,
    ITEM_EVIDENCE_REFERENCE_REVIEW,
    ITEM_MISSING_EVIDENCE_REVIEW,
    ITEM_PACKET_PROCESSING_REVIEW,
    ITEM_SOURCE_INGESTION_REVIEW,
    OUTCOME_BLOCKED,
    OUTCOME_DENIED,
    OUTCOME_PLANNED,
    READY_FOR_HUMAN_REVIEW,
    BLOCKED_NO_SUBJECTS,
    SUBJECT_AGENT_TASK_QUEUE,
    SUBJECT_EVIDENCE_REFERENCE,
    SUBJECT_PACKET_PROCESSING,
    SUBJECT_SOURCE_INGESTION,
    PacketReviewOrchestrationRequest,
    PacketReviewOrchestrationResult,
    PacketReviewPlan,
    ReviewBundleDraft,
    ReviewOrchestrationValidationResult,
    ReviewPlanItem,
    ReviewReadinessAssessment,
    ReviewSubjectReference,
    StageName,
)
from .governance import _has_subjects, _is_blank, evaluate_packet_review_request

_PLAN_WARNING = (
    "review orchestration plans are not approvals and not writes — no database connection is "
    "opened, no agent/LLM/AgentNet/resolver/network call is made, nothing is approved, and no "
    "review record is stored; a human reviewer acts on these plans"
)
_DEFAULT_REVIEWER_ROLE = "internal_reviewer"

# item_type -> (priority, subject_type) for the id-list-backed review items.
_ID_ITEM_SPECS = (
    ("source_ingestion_record_ids", ITEM_SOURCE_INGESTION_REVIEW, 20, SUBJECT_SOURCE_INGESTION),
    ("evidence_reference_ids", ITEM_EVIDENCE_REFERENCE_REVIEW, 30, SUBJECT_EVIDENCE_REFERENCE),
    ("agent_task_queue_record_ids", ITEM_AGENT_TASK_QUEUE_REVIEW, 40, SUBJECT_AGENT_TASK_QUEUE),
)


def validate_packet_review_request(
    request: PacketReviewOrchestrationRequest,
) -> ReviewOrchestrationValidationResult:
    """Build the structured request-level ``ReviewOrchestrationValidationResult``."""
    governance = evaluate_packet_review_request(request)
    identity_valid = all(
        not _is_blank(getattr(request, a, None))
        for a in ("owner_id", "client_id", "engagement_id"))
    scope_valid = not _is_blank(getattr(request, "authorization_scope", None))
    contains_prohibited = any(
        t in " ".join(governance.reasons).lower()
        for t in ("secret", "raw-content", "raw content", "arbitrary content", "intent"))
    return ReviewOrchestrationValidationResult(
        permitted=governance.permitted,
        identity_valid=identity_valid,
        scope_valid=scope_valid,
        has_subjects=_has_subjects(request),
        contains_prohibited_content=contains_prohibited,
        reasons=list(governance.reasons),
        warnings=list(governance.warnings),
    )


def _reviewer_role(request) -> str:
    role = getattr(request, "reviewer_role", None)
    return role if role else _DEFAULT_REVIEWER_ROLE


def _subject_refs(request: PacketReviewOrchestrationRequest) -> List[ReviewSubjectReference]:
    """Build safe subject references (id + type, stamped with request identity)."""
    refs: List[ReviewSubjectReference] = []

    def _add(ids, subject_type):
        for sid in ids or []:
            refs.append(ReviewSubjectReference(
                subject_ref_id=sid, subject_type=subject_type,
                owner_id=request.owner_id, client_id=request.client_id,
                engagement_id=request.engagement_id,
                authorization_scope=request.authorization_scope))

    _add(getattr(request, "source_ingestion_record_ids", None), SUBJECT_SOURCE_INGESTION)
    _add(getattr(request, "evidence_reference_ids", None), SUBJECT_EVIDENCE_REFERENCE)
    _add(getattr(request, "agent_task_queue_record_ids", None), SUBJECT_AGENT_TASK_QUEUE)
    if getattr(request, "packet_processing_receipt_ref", None):
        _add([request.packet_processing_receipt_ref], SUBJECT_PACKET_PROCESSING)
    return refs


def _build_review_items(request: PacketReviewOrchestrationRequest) -> List[ReviewPlanItem]:
    """Build deterministic review plan items grouping safe references only."""
    base = getattr(request, "idempotency_key", None)
    role = _reviewer_role(request)
    items: List[ReviewPlanItem] = []
    present_types = 0

    for field_name, item_type, priority, _subject_type in _ID_ITEM_SPECS:
        ids = list(getattr(request, field_name, None) or [])
        if not ids:
            continue
        present_types += 1
        items.append(ReviewPlanItem(
            item_id=f"{base}::item::{item_type}", item_type=item_type,
            subject_refs=list(ids), priority=priority, required_reviewer_role=role,
            reasons=[], warnings=[_PLAN_WARNING]))

    if getattr(request, "packet_processing_receipt_ref", None):
        present_types += 1
        items.append(ReviewPlanItem(
            item_id=f"{base}::item::{ITEM_PACKET_PROCESSING_REVIEW}",
            item_type=ITEM_PACKET_PROCESSING_REVIEW,
            subject_refs=[request.packet_processing_receipt_ref], priority=10,
            required_reviewer_role=role, warnings=[_PLAN_WARNING]))

    # A cross-stage consistency item is useful only when more than one stage is represented.
    if present_types > 1:
        items.append(ReviewPlanItem(
            item_id=f"{base}::item::{ITEM_CROSS_STAGE_CONSISTENCY_REVIEW}",
            item_type=ITEM_CROSS_STAGE_CONSISTENCY_REVIEW, subject_refs=[], priority=50,
            required_reviewer_role=role,
            reasons=["multiple packet-derived stages present; confirm cross-stage consistency"],
            warnings=[_PLAN_WARNING]))

    # A missing-evidence exception when task-queue/source subjects exist but no evidence refs do.
    has_evidence = bool(getattr(request, "evidence_reference_ids", None))
    has_work = bool(getattr(request, "agent_task_queue_record_ids", None)
                    or getattr(request, "source_ingestion_record_ids", None))
    if has_work and not has_evidence:
        items.append(ReviewPlanItem(
            item_id=f"{base}::item::{ITEM_MISSING_EVIDENCE_REVIEW}",
            item_type=ITEM_MISSING_EVIDENCE_REVIEW, subject_refs=[], priority=60,
            required_reviewer_role=role,
            reasons=["source/task-queue subjects present but no evidence references supplied"],
            warnings=[_PLAN_WARNING]))
    return items


def _build_bundle(request, subject_refs, review_scope) -> ReviewBundleDraft:
    """Map the request into a single review-gated ``ReviewBundleDraft`` (never persisted)."""
    return ReviewBundleDraft(
        review_bundle_id=None,  # Phase 29 stores nothing; a future phase would assign this
        owner_id=request.owner_id, client_id=request.client_id, engagement_id=request.engagement_id,
        packet_processing_receipt_ref=getattr(request, "packet_processing_receipt_ref", None),
        source_ingestion_record_ids=list(getattr(request, "source_ingestion_record_ids", None) or []),
        evidence_reference_ids=list(getattr(request, "evidence_reference_ids", None) or []),
        agent_task_queue_record_ids=list(getattr(request, "agent_task_queue_record_ids", None) or []),
        subject_refs=list(subject_refs),
        reviewer_role=_reviewer_role(request),
        review_reason=getattr(request, "review_reason", None),
        review_scope=review_scope,
        output_status="draft", review_status="needs_review", lifecycle_status="draft",
        authoritative=False, client_facing_approved=False, capsule_candidate_ready=False,
        financial_verified=False, execution_allowed=False, approval_allowed=False,
        publication_allowed=False, requires_human_review=True,
        reasons=[], warnings=[_PLAN_WARNING], created_at=None)


def _denied_result(request, governance, validation_result) -> PacketReviewOrchestrationResult:
    """A side-effect-free denied result carrying a blocked readiness assessment.

    The assessment is attached via a no-side-effect plan (bundles/items empty) so the blocked
    readiness state is inspectable; nothing is stored and no write request is produced.
    """
    from .contracts import BLOCKED_INVALID_SCOPE
    assessment = ReviewReadinessAssessment(
        readiness_state=governance.readiness_state or BLOCKED_INVALID_SCOPE,
        blocked=True, reasons=list(governance.reasons))
    plan = PacketReviewPlan(
        permitted=False, review_bundles=[], review_plan_items=[],
        readiness_assessments=[assessment], reasons=list(governance.reasons))
    return PacketReviewOrchestrationResult(
        outcome=OUTCOME_DENIED, permitted=False,
        reason_code=governance.reason_code or "review_request_denied",
        status="rejected", validation_result=validation_result, plan=plan,
        review_bundle_count=0, review_plan_item_count=0, readiness_assessment_count=1,
        subject_count=0, blocked_subject_count=0, controlled_write_request_count=0,
        stages_completed=[StageName.VALIDATE_REQUEST],
        stages_skipped=[StageName.BUILD_SUBJECT_REFS, StageName.BUILD_REVIEW_ITEMS,
                        StageName.ASSESS_READINESS],
        reasons=list(governance.reasons), warnings=[])


def prepare_packet_review_plan(
    request: PacketReviewOrchestrationRequest,
) -> PacketReviewOrchestrationResult:
    """Prepare a no-side-effect packet-derived human-review plan.

    Public entry point. Returns a fully typed ``PacketReviewOrchestrationResult`` with all
    side-effect flags ``False``. Nothing is approved, executed, or written. **"Ready for human
    review" never means approved.**
    """
    governance = evaluate_packet_review_request(request)
    validation_result = validate_packet_review_request(request)
    if not governance.permitted:
        return _denied_result(request, governance, validation_result)

    subject_refs = _subject_refs(request)

    # Non-strict mode with no subjects: permitted but not review-ready (no side effects).
    if not subject_refs:
        assessment = ReviewReadinessAssessment(
            readiness_state=BLOCKED_NO_SUBJECTS, blocked=True, subject_count=0,
            reasons=["no safe subject references supplied; nothing to plan for review"])
        plan = PacketReviewPlan(
            permitted=True, review_bundles=[], review_plan_items=[],
            readiness_assessments=[assessment], warnings=[_PLAN_WARNING])
        return PacketReviewOrchestrationResult(
            outcome=OUTCOME_BLOCKED, permitted=True, reason_code=BLOCKED_NO_SUBJECTS,
            status="no_subjects", validation_result=validation_result, plan=plan,
            review_bundle_count=0, review_plan_item_count=0, readiness_assessment_count=1,
            subject_count=0, blocked_subject_count=0, controlled_write_request_count=0,
            stages_completed=[StageName.VALIDATE_REQUEST, StageName.BUILD_SUBJECT_REFS,
                              StageName.ASSESS_READINESS],
            stages_skipped=[StageName.BUILD_REVIEW_ITEMS],
            reasons=[], warnings=[_PLAN_WARNING])

    review_scope = getattr(request, "authorization_scope", None)
    items = _build_review_items(request)
    bundle = _build_bundle(request, subject_refs, review_scope)
    assessment = ReviewReadinessAssessment(
        readiness_state=READY_FOR_HUMAN_REVIEW, blocked=False, subject_count=len(subject_refs),
        warnings=["ready for human review does not mean approved; a human reviewer decides"])

    plan = PacketReviewPlan(
        permitted=True, review_bundles=[bundle], review_plan_items=items,
        readiness_assessments=[assessment], controlled_write_requests=[],
        reasons=[], warnings=[_PLAN_WARNING])

    return PacketReviewOrchestrationResult(
        outcome=OUTCOME_PLANNED, permitted=True, reason_code=None,
        status="review_plan_prepared", validation_result=validation_result, plan=plan,
        review_bundle_count=1, review_plan_item_count=len(items),
        readiness_assessment_count=1, subject_count=len(subject_refs), blocked_subject_count=0,
        controlled_write_request_count=0,
        stages_completed=[StageName.VALIDATE_REQUEST, StageName.BUILD_SUBJECT_REFS,
                          StageName.BUILD_REVIEW_ITEMS, StageName.ASSESS_READINESS],
        stages_skipped=[], reasons=[], warnings=[_PLAN_WARNING])
