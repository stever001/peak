"""Peak Internal Reviewer Decision Boundary (Phase 32).

A **decision-planning boundary**, not a review-approval phase, review engine, workflow engine, or
DB writer. It lets Peak represent a **structured internal reviewer decision** against a review
bundle / review plan items — producing a review-gated decision *draft*, a decision-readiness
assessment, and a deterministic **routing recommendation** — **without persisting anything,
approving anything, or touching the database.**

This phase is analogous to Phase 29: Phase 29 planned review bundles without DB writes; Phase 32
plans reviewer decisions without DB writes. It is **DB-free** and produces **no**
``ControlledWriteRequest`` objects; future persistence of reviewer decisions is deferred to Phase
33. **``ready_for_internal_use`` is not approval** — it authorizes no client-facing output, no
financial verification, no capsule publication, no agent execution, and no ``review_records`` write.

Nothing is approved, executed, or written; no Phase 22 review writer is called; no ``review_records``
row is created; no LLM / MockLLM / agent / AgentNet / MCP / resolver / connector / network call is
made. This package imports only stdlib. See docs/INTERNAL_REVIEWER_DECISION_BOUNDARY.md and
docs/INTERNAL_REVIEWER_DECISION_GOVERNANCE_POLICY.md.
"""

from __future__ import annotations

from .contracts import (
    ALLOWED_DECISION_ACTIONS,
    ALLOWED_DECISION_INTENTS,
    ALLOWED_RETURN_STAGES,
    BLOCKED_BY_MISSING_SOURCE,
    BLOCKED_BY_QUALITY,
    BLOCKED_BY_SCOPE,
    BLOCKED_DISALLOWED_INTENT,
    BLOCKED_INVALID_SCOPE,
    BLOCKED_LIFECYCLE,
    BLOCKED_MISSING_REVIEW_BUNDLE,
    BLOCKED_RAW_CONTENT,
    BLOCKED_SECRET_LIKE_CONTENT,
    BLOCKED_UNSUPPORTED_INTENT,
    DEFER_REVIEW,
    INTENT_ROUTING,
    NEEDS_MORE_EVIDENCE,
    OUTCOME_DENIED,
    OUTCOME_PLANNED,
    READINESS_STATES,
    READY_FOR_INTERNAL_USE,
    READY_TO_RECORD,
    REJECTED_FOR_POLICY,
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
    ReviewerDecisionGovernanceDecision,
    evaluate_internal_reviewer_decision_request,
    scan_prohibited_content,
    subject_identity_mismatches,
)
from .decision_mapper import (
    build_decision_draft,
    build_routing_plan,
    prepare_internal_reviewer_decision,
    validate_internal_reviewer_decision_request,
)

__all__ = [
    # contracts
    "InternalReviewerDecisionRequest",
    "InternalReviewerDecisionDraft",
    "ReviewerDecisionRoutingPlan",
    "ReviewerDecisionReadinessAssessment",
    "InternalReviewerDecisionResult",
    "ReviewerDecisionValidationResult",
    "StageName",
    "ALLOWED_DECISION_ACTIONS",
    "ALLOWED_DECISION_INTENTS",
    "ALLOWED_RETURN_STAGES",
    "INTENT_ROUTING",
    "READINESS_STATES",
    "READY_TO_RECORD",
    # intents
    "NEEDS_MORE_EVIDENCE",
    "RETURN_FOR_REVISION",
    "READY_FOR_INTERNAL_USE",
    "BLOCKED_BY_SCOPE",
    "BLOCKED_BY_QUALITY",
    "BLOCKED_BY_MISSING_SOURCE",
    "REJECTED_FOR_POLICY",
    "DEFER_REVIEW",
    # readiness / outcomes
    "BLOCKED_INVALID_SCOPE",
    "BLOCKED_LIFECYCLE",
    "BLOCKED_MISSING_REVIEW_BUNDLE",
    "BLOCKED_UNSUPPORTED_INTENT",
    "BLOCKED_DISALLOWED_INTENT",
    "BLOCKED_RAW_CONTENT",
    "BLOCKED_SECRET_LIKE_CONTENT",
    "OUTCOME_DENIED",
    "OUTCOME_PLANNED",
    # governance
    "ReviewerDecisionGovernanceDecision",
    "evaluate_internal_reviewer_decision_request",
    "scan_prohibited_content",
    "subject_identity_mismatches",
    # mapper / entry points
    "prepare_internal_reviewer_decision",
    "validate_internal_reviewer_decision_request",
    "build_decision_draft",
    "build_routing_plan",
]
