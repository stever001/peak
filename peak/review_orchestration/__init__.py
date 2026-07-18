"""Peak Packet-Derived Review Orchestration Boundary (Phase 29).

A **review-planning boundary**, not a review-approval phase, review engine, workflow engine, or
DB writer. It consumes safe references, receipts, and metadata produced by prior phases (packet
processing, source ingestion, evidence, agent task queue) and prepares **review-ready** plans for
human reviewers — review bundle drafts, review plan items, and review readiness assessments —
**without approving anything, executing anything, or writing to the database.**

This phase is analogous to Phase 26: Phase 26 planned agent task queue readiness without DB
writes; Phase 29 plans human-review readiness without DB writes. It is **DB-free** and produces
**no** ``ControlledWriteRequest`` objects; future persistence of review plans is deferred to a
later phase. **"Ready for human review" never means approved** — every draft stays ``draft`` /
``needs_review`` with ``approval_allowed=False`` and ``requires_human_review=True``.

Nothing is approved, executed, or written; no LLM / MockLLM / agent / AgentNet / MCP / resolver /
connector / network call is made; no client-facing output, financial verification, or capsule
publication occurs. This package imports only stdlib. See
docs/PACKET_DERIVED_REVIEW_ORCHESTRATION_BOUNDARY.md and
docs/REVIEW_ORCHESTRATION_GOVERNANCE_POLICY.md.
"""

from __future__ import annotations

from .contracts import (
    ALLOWED_REVIEW_ACTIONS,
    BLOCKED_APPROVAL_INTENT,
    BLOCKED_EXECUTION_INTENT,
    BLOCKED_FINANCIAL_VERIFICATION_INTENT,
    BLOCKED_INVALID_SCOPE,
    BLOCKED_LIFECYCLE,
    BLOCKED_NO_SUBJECTS,
    BLOCKED_PUBLICATION_INTENT,
    BLOCKED_RAW_CONTENT,
    BLOCKED_SECRET_LIKE_CONTENT,
    BLOCKED_STATES,
    ITEM_AGENT_TASK_QUEUE_REVIEW,
    ITEM_CROSS_STAGE_CONSISTENCY_REVIEW,
    ITEM_EVIDENCE_REFERENCE_REVIEW,
    ITEM_MISSING_EVIDENCE_REVIEW,
    ITEM_PACKET_PROCESSING_REVIEW,
    ITEM_READINESS_EXCEPTION_REVIEW,
    ITEM_SOURCE_INGESTION_REVIEW,
    OUTCOME_BLOCKED,
    OUTCOME_DENIED,
    OUTCOME_PLANNED,
    READINESS_STATES,
    READY_FOR_HUMAN_REVIEW,
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
from .governance import (
    ReviewOrchestrationGovernanceDecision,
    evaluate_packet_review_request,
    scan_prohibited_content,
    subject_identity_mismatches,
)
from .review_planner import (
    prepare_packet_review_plan,
    validate_packet_review_request,
)

__all__ = [
    # contracts
    "PacketReviewOrchestrationRequest",
    "PacketReviewOrchestrationResult",
    "PacketReviewPlan",
    "ReviewBundleDraft",
    "ReviewPlanItem",
    "ReviewReadinessAssessment",
    "ReviewSubjectReference",
    "ReviewOrchestrationValidationResult",
    "StageName",
    "ALLOWED_REVIEW_ACTIONS",
    "READINESS_STATES",
    "BLOCKED_STATES",
    "READY_FOR_HUMAN_REVIEW",
    "BLOCKED_NO_SUBJECTS",
    "BLOCKED_INVALID_SCOPE",
    "BLOCKED_LIFECYCLE",
    "BLOCKED_RAW_CONTENT",
    "BLOCKED_SECRET_LIKE_CONTENT",
    "BLOCKED_EXECUTION_INTENT",
    "BLOCKED_APPROVAL_INTENT",
    "BLOCKED_PUBLICATION_INTENT",
    "BLOCKED_FINANCIAL_VERIFICATION_INTENT",
    "ITEM_SOURCE_INGESTION_REVIEW",
    "ITEM_EVIDENCE_REFERENCE_REVIEW",
    "ITEM_AGENT_TASK_QUEUE_REVIEW",
    "ITEM_PACKET_PROCESSING_REVIEW",
    "ITEM_CROSS_STAGE_CONSISTENCY_REVIEW",
    "ITEM_MISSING_EVIDENCE_REVIEW",
    "ITEM_READINESS_EXCEPTION_REVIEW",
    "OUTCOME_DENIED",
    "OUTCOME_PLANNED",
    "OUTCOME_BLOCKED",
    # governance
    "ReviewOrchestrationGovernanceDecision",
    "evaluate_packet_review_request",
    "scan_prohibited_content",
    "subject_identity_mismatches",
    # planner / entry points
    "prepare_packet_review_plan",
    "validate_packet_review_request",
]
