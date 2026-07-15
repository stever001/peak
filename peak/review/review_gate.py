"""QA / Review Gate — deterministic, no-side-effect (Phase 15).

Evaluates a ``ReviewDecisionRequest`` against the Phase 15 governance guards and derives a
**production-shaped but no-side-effect** ``ReviewGateResult``. The gate can approve a
subject for **internal reliance only**, reject it, return it for revision, supersede it, or
keep it under review — but it **persists nothing and confers no final authority**:

- **no database read/write** — no review record is stored;
- **no live LLM call, no AgentNet call, no MCP/resolver call, no network call**;
- **no file write, no client-facing output, no capsule publication**.

``approve_internal`` means internal reliance only. ``client_facing_approved`` and
``capsule_candidate_ready`` remain ``false`` in every case; client-facing approval,
financial-impact verification, and capsule publication remain separate and future. See
docs/QA_REVIEW_GATE.md and docs/REVIEW_DECISION_MODEL.md.
"""

from __future__ import annotations

from .contracts import (
    DEFAULT_LIFECYCLE_STATUS,
    DEFAULT_REVIEW_STATUS,
    ReviewActionPlan,
    ReviewDecision,
    ReviewDecisionRequest,
    ReviewGateResult,
)
from .governance import evaluate_review_request

# Effects a review decision may never execute in Phase 15 (documented on every action plan).
PROHIBITED_EFFECTS = (
    "client_facing_approval",
    "financial_impact_verification",
    "capsule_publication",
    "database_write",
    "live_llm_call",
    "agentnet_call",
    "network_call",
)


def _subject_lifecycle(request: ReviewDecisionRequest) -> str:
    """Return the subject's current lifecycle status, or the request's, or the default."""
    subject = getattr(request, "subject", None)
    sub_lifecycle = getattr(subject, "current_lifecycle_status", None) if subject else None
    if sub_lifecycle:
        return sub_lifecycle
    req_lifecycle = getattr(request, "lifecycle_status", None)
    return req_lifecycle or DEFAULT_LIFECYCLE_STATUS


def derive_next_state(request: ReviewDecisionRequest) -> ReviewDecision:
    """Map an allowed decision to its next governance state (no side effects).

    Uses the existing Phase 9 governance vocabulary (peak/db/enums.py). Client-facing
    approval and capsule readiness are never granted here — both stay ``false`` in every
    branch.
    """
    decision = getattr(request, "requested_decision", None)
    reasons: list = []
    warnings: list = []
    subject_lifecycle = _subject_lifecycle(request)

    # Defaults — non-authoritative, not client-facing, not a capsule candidate.
    next_output_status = "draft"
    next_review_status = DEFAULT_REVIEW_STATUS
    next_lifecycle_status = subject_lifecycle
    authoritative = False

    if decision == "approve_internal":
        # Internal reliance only. Authoritative for internal use; never client-facing.
        next_review_status = "approved_internal"
        next_output_status = "reviewed"
        authoritative = True
        reasons.append("approved for internal reliance only; not client-facing and not a capsule")
    elif decision == "reject":
        next_review_status = "rejected"
        # Lifecycle stays active unless the subject already indicates otherwise.
        next_lifecycle_status = subject_lifecycle or "active"
    elif decision == "return_for_revision":
        # No dedicated needs_revision state exists in the Phase 9 vocabulary; use
        # needs_review and record the intent.
        next_review_status = "needs_review"
        warnings.append(
            "no needs_revision state in governance vocabulary; using needs_review and "
            "recording return_for_revision intent"
        )
    elif decision == "supersede":
        # superseded exists in both ReviewStatus and LifecycleStatus.
        next_review_status = "superseded"
        next_lifecycle_status = "superseded"
    elif decision == "keep_needs_review":
        next_review_status = "needs_review"
    else:  # pragma: no cover - governance rejects unknown decisions before this point
        reasons.append(f"unhandled decision '{decision}'")

    return ReviewDecision(
        permitted=True,
        decision=decision,
        next_output_status=next_output_status,
        next_review_status=next_review_status,
        next_lifecycle_status=next_lifecycle_status,
        authoritative=authoritative,
        client_facing_approved=False,  # always false in Phase 15
        capsule_candidate_ready=False,  # always false in Phase 15
        reasons=reasons,
        warnings=warnings,
    )


def build_action_plan(
    request: ReviewDecisionRequest, decision: ReviewDecision
) -> ReviewActionPlan:
    """Describe (never execute) what a reviewer/writer would do next."""
    requested = getattr(request, "requested_decision", None)
    requires_follow_up = requested in ("return_for_revision", "supersede")
    if requested == "approve_internal":
        notes = (
            "Record an internal-reliance approval only. Client-facing approval, financial "
            "verification, and capsule publication remain separate future gates."
        )
        action = "record_internal_reliance_approval"
    elif requested == "reject":
        notes = "Record a rejection with reasons; the authoring worker/agent may resubmit."
        action = "record_rejection"
    elif requested == "return_for_revision":
        notes = "Return to the authoring worker/agent for revision; no state is finalized."
        action = "return_to_author"
    elif requested == "supersede":
        notes = "Mark superseded once a replacement record exists; do not delete the original."
        action = "record_supersession"
    else:  # keep_needs_review
        notes = "Leave under review; no advancement."
        action = "keep_under_review"

    return ReviewActionPlan(
        action=action,
        requires_human=True,
        requires_follow_up=requires_follow_up,
        allowed_next_state=getattr(decision, "next_review_status", None),
        prohibited_effects=list(PROHIBITED_EFFECTS),
        notes=notes,
    )


def evaluate_review_gate(request: ReviewDecisionRequest) -> ReviewGateResult:
    """Evaluate a review request into a no-side-effect gate result."""
    governance = evaluate_review_request(request)

    if not governance.permitted:
        return ReviewGateResult(
            permitted=False,
            status="rejected",
            decision=None,
            action_plan=None,
            database_write_made=False,
            llm_call_made=False,
            agentnet_call_made=False,
            network_call_made=False,
            capsule_publication_made=False,
            client_facing_output_created=False,
            reasons=list(governance.reasons),
            warnings=list(governance.warnings),
        )

    decision = derive_next_state(request)
    action_plan = build_action_plan(request, decision)

    return ReviewGateResult(
        permitted=True,
        status="evaluated",
        decision=decision,
        action_plan=action_plan,
        database_write_made=False,
        llm_call_made=False,
        agentnet_call_made=False,
        network_call_made=False,
        capsule_publication_made=False,
        client_facing_output_created=False,
        reasons=list(decision.reasons),
        warnings=list(governance.warnings) + list(decision.warnings),
    )
