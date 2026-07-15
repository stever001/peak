"""Contracts for the QA / Review Gate (Phase 15).

Production-shaped but **no-side-effect** dataclasses for internal review decisions on
worker/agent outputs (e.g. the Phase 14 evidence drafts). The review gate can produce a
production-shaped decision — approve for *internal reliance*, reject, return for revision,
supersede, or keep under review — but it **persists nothing and confers no final
authority**.

**Source contracts only — no stored review records.** Nothing here calls an LLM, AgentNet,
an MCP connector, a resolver, a database, or the network, and nothing produces
client-facing output or publishes a capsule. ``approve_internal`` means **internal
reliance only**; client-facing approval, financial-impact verification, and capsule
publication remain separate and future. See docs/QA_REVIEW_GATE.md and
docs/REVIEW_DECISION_MODEL.md.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import List, Optional

# Decisions a Phase 15 reviewer may request (mirrors ReviewStatus / LifecycleStatus vocab).
ALLOWED_DECISIONS = frozenset(
    {
        "approve_internal",
        "reject",
        "return_for_revision",
        "supersede",
        "keep_needs_review",
    }
)

# Decisions that are explicitly out of scope for Phase 15 — a request naming any of these
# is rejected outright. Client-facing approval, financial verification, and capsule
# publication remain separate, human-gated, and future.
PROHIBITED_DECISIONS = frozenset(
    {
        "client_facing_approve",
        "publish_capsule",
        "verify_financial_impact",
        "approve_authoritative_external",
    }
)

# No-side-effect posture defaults stamped onto every result in Phase 15.
DEFAULT_REVIEW_STATUS = "needs_review"
DEFAULT_LIFECYCLE_STATUS = "active"


@dataclass
class ReviewSubjectReference:
    """The worker/agent output under review (pointer/metadata; no sensitive content)."""

    subject_record_id: Optional[str] = None
    subject_record_type: Optional[str] = None
    owner_id: Optional[str] = None
    client_id: Optional[str] = None
    engagement_id: Optional[str] = None
    source_reference_id: Optional[str] = None
    current_output_status: Optional[str] = None
    current_review_status: Optional[str] = None
    current_lifecycle_status: Optional[str] = None
    authoritative: bool = False
    client_facing_approved: bool = False
    capsule_candidate_ready: bool = False


@dataclass
class ReviewChecklistResult:
    """The deterministic pre-review checklist evaluated for a subject."""

    source_traceable: bool = False
    scope_valid: bool = False
    evidence_complete: bool = False
    confidence_acceptable: bool = False
    no_contradiction_flags: bool = False
    no_client_facing_claims: bool = False
    no_financial_verification_claim: bool = False
    no_capsule_publication_request: bool = False
    required_human_review_completed: bool = False
    warnings: List[str] = field(default_factory=list)
    missing_items: List[str] = field(default_factory=list)


@dataclass
class ReviewDecisionRequest:
    """A request to evaluate a review decision on a subject (no side effects)."""

    owner_id: Optional[str] = None
    client_id: Optional[str] = None
    engagement_id: Optional[str] = None
    requested_by: Optional[str] = None
    reviewer_role: Optional[str] = None
    authorization_scope: Optional[str] = None
    requested_decision: Optional[str] = None
    subject: Optional[ReviewSubjectReference] = None
    checklist: Optional[ReviewChecklistResult] = None
    decision_notes: Optional[str] = None
    lifecycle_status: Optional[str] = None


@dataclass
class ReviewDecision:
    """The evaluated review decision (in-memory only; nothing is persisted)."""

    permitted: bool = False
    decision: Optional[str] = None
    next_output_status: Optional[str] = None
    next_review_status: str = DEFAULT_REVIEW_STATUS
    next_lifecycle_status: str = DEFAULT_LIFECYCLE_STATUS
    authoritative: bool = False
    client_facing_approved: bool = False
    capsule_candidate_ready: bool = False
    reasons: List[str] = field(default_factory=list)
    warnings: List[str] = field(default_factory=list)


@dataclass
class ReviewActionPlan:
    """What a reviewer/writer would do next — description only; no effect is executed."""

    action: Optional[str] = None
    requires_human: bool = True
    requires_follow_up: bool = False
    allowed_next_state: Optional[str] = None
    prohibited_effects: List[str] = field(default_factory=list)
    notes: str = ""


@dataclass
class ReviewGateResult:
    """The controlled result of a review-gate evaluation (no side effects)."""

    permitted: bool = False
    status: str = "rejected"
    decision: Optional[ReviewDecision] = None
    action_plan: Optional[ReviewActionPlan] = None
    database_write_made: bool = False
    llm_call_made: bool = False
    agentnet_call_made: bool = False
    network_call_made: bool = False
    capsule_publication_made: bool = False
    client_facing_output_created: bool = False
    reasons: List[str] = field(default_factory=list)
    warnings: List[str] = field(default_factory=list)
