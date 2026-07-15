"""Peak internal QA / Review Gate (Phase 15).

Phase 15 defines how Peak evaluates worker/agent outputs (e.g. the Phase 14 evidence
drafts) for internal approval, rejection, return for revision, supersession, or continued
review. Decisions are **production-shaped but no-side-effect**: the gate persists nothing
and confers no final authority.

- **no database read/write, no stored review records**;
- **no live LLM call, no AgentNet call, no MCP/resolver call, no network call**;
- **no file write, no client-facing output, no capsule publication**.

``approve_internal`` means **internal reliance only**. Client-facing approval,
financial-impact verification, and capsule publication remain separate and future;
``client_facing_approved`` and ``capsule_candidate_ready`` stay ``false`` in every case.

See docs/QA_REVIEW_GATE.md and docs/REVIEW_DECISION_MODEL.md.
"""

from __future__ import annotations

from .contracts import (
    ALLOWED_DECISIONS,
    PROHIBITED_DECISIONS,
    ReviewActionPlan,
    ReviewChecklistResult,
    ReviewDecision,
    ReviewDecisionRequest,
    ReviewGateResult,
    ReviewSubjectReference,
)
from .governance import (
    ReviewGovernanceDecision,
    build_review_checklist,
    evaluate_review_request,
    validate_requested_decision,
)
from .review_gate import (
    build_action_plan,
    derive_next_state,
    evaluate_review_gate,
)

__all__ = [
    "ALLOWED_DECISIONS",
    "PROHIBITED_DECISIONS",
    "ReviewSubjectReference",
    "ReviewChecklistResult",
    "ReviewDecisionRequest",
    "ReviewDecision",
    "ReviewActionPlan",
    "ReviewGateResult",
    "ReviewGovernanceDecision",
    "evaluate_review_request",
    "validate_requested_decision",
    "build_review_checklist",
    "evaluate_review_gate",
    "derive_next_state",
    "build_action_plan",
]
