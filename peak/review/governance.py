"""Deterministic governance guards for the QA / Review Gate (Phase 15).

Run *before* a review decision is derived. These checks enforce that a review request is
authorized, scoped, and names an allowed decision, and that no decision can create
client-facing approval, verify financial impact, or publish a capsule. They persist
nothing and confer no authority — a permitted request only means the gate *may* derive a
production-shaped, no-side-effect decision.

Governance vocabulary mirrors the Phase 9 contracts (peak/db/enums.py and
schemas/*.schema.json are the source of truth); the blocking sets are local literals so
this module stays import-light and touches no database or network.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import List

from .contracts import (
    ALLOWED_DECISIONS,
    PROHIBITED_DECISIONS,
    ReviewChecklistResult,
    ReviewDecisionRequest,
    ReviewSubjectReference,
)

REVOKED_AUTHORIZATION_SCOPE = "revoked"
BLOCKED_LIFECYCLE_STATUSES = frozenset({"revoked", "archived", "deleted_reference_only"})
FIXTURE_TEST_SCOPE = "fixture_test"
# Checks that must all hold before a subject may be approved for internal reliance.
APPROVE_INTERNAL_CHECKS = (
    "source_traceable",
    "scope_valid",
    "evidence_complete",
    "confidence_acceptable",
    "no_contradiction_flags",
    "no_client_facing_claims",
    "no_financial_verification_claim",
    "no_capsule_publication_request",
    "required_human_review_completed",
)


@dataclass
class ReviewGovernanceDecision:
    """Result of the pre-review governance checks."""

    permitted: bool = False
    reasons: List[str] = field(default_factory=list)
    warnings: List[str] = field(default_factory=list)


def _is_blank(value) -> bool:
    return value is None or (isinstance(value, str) and not value.strip())


def validate_requested_decision(request: ReviewDecisionRequest) -> ReviewGovernanceDecision:
    """Check only that ``requested_decision`` is allowed and not prohibited."""
    reasons: list = []
    decision = getattr(request, "requested_decision", None)
    if _is_blank(decision):
        reasons.append("requested_decision is required")
    elif decision in PROHIBITED_DECISIONS:
        reasons.append(
            f"requested_decision '{decision}' is prohibited in Phase 15 "
            "(client-facing approval, financial verification, capsule publication, and "
            "external authoritative approval remain separate and future)"
        )
    elif decision not in ALLOWED_DECISIONS:
        reasons.append(
            f"requested_decision '{decision}' is not one of "
            f"{sorted(ALLOWED_DECISIONS)}"
        )
    return ReviewGovernanceDecision(permitted=not reasons, reasons=reasons)


def build_review_checklist(subject: ReviewSubjectReference) -> ReviewChecklistResult:
    """Return the checklist a reviewer would apply, keyed off subject posture.

    Deterministic and conservative: this does not *infer* quality. It seeds the structural
    checks that can be read from the subject's own posture (a subject that already claims
    to be authoritative / client-facing / capsule-ready is flagged), and leaves the
    substantive checks (traceability, evidence completeness, human review) to the caller,
    who populates them from the actual review. Nothing here is stored.
    """
    warnings: list = []
    subject_ok = subject is not None
    no_client_facing_claims = subject_ok and not getattr(subject, "client_facing_approved", False)
    no_capsule_publication_request = subject_ok and not getattr(
        subject, "capsule_candidate_ready", False
    )
    if not subject_ok:
        warnings.append("subject is missing; checklist defaults to not-satisfied")
    if subject_ok and getattr(subject, "client_facing_approved", False):
        warnings.append("subject already flags client_facing_approved; Phase 15 cannot create it")
    if subject_ok and getattr(subject, "capsule_candidate_ready", False):
        warnings.append("subject already flags capsule_candidate_ready; Phase 15 cannot create it")
    return ReviewChecklistResult(
        source_traceable=False,
        scope_valid=subject_ok,
        evidence_complete=False,
        confidence_acceptable=False,
        no_contradiction_flags=True,
        no_client_facing_claims=no_client_facing_claims,
        no_financial_verification_claim=True,
        no_capsule_publication_request=no_capsule_publication_request,
        required_human_review_completed=False,
        warnings=warnings,
        missing_items=[],
    )


def evaluate_review_request(request: ReviewDecisionRequest) -> ReviewGovernanceDecision:
    """Return a governance decision for a review request (no side effects)."""
    reasons: list = []
    warnings: list = []

    # 1. Required identity / authorization fields.
    for attr in (
        "owner_id",
        "client_id",
        "engagement_id",
        "requested_by",
        "reviewer_role",
        "authorization_scope",
    ):
        if _is_blank(getattr(request, attr, None)):
            reasons.append(f"{attr} is required")

    # 2. authorization_scope must not be revoked.
    auth = getattr(request, "authorization_scope", None)
    if auth == REVOKED_AUTHORIZATION_SCOPE:
        reasons.append("authorization_scope 'revoked' is not permitted")

    # 3. requested_decision must be allowed and not prohibited.
    decision_check = validate_requested_decision(request)
    reasons.extend(decision_check.reasons)
    decision = getattr(request, "requested_decision", None)

    # 4. request lifecycle_status must not be revoked/archived/deleted.
    lifecycle = getattr(request, "lifecycle_status", None)
    if lifecycle in BLOCKED_LIFECYCLE_STATUSES:
        reasons.append(
            f"lifecycle_status '{lifecycle}' is not permitted "
            "(must not be revoked, archived, or deleted_reference_only)"
        )

    # 5. subject is required, and its scope must match the request.
    subject = getattr(request, "subject", None)
    if subject is None:
        reasons.append("subject is required")
    else:
        for attr in ("owner_id", "client_id", "engagement_id"):
            req_val = getattr(request, attr, None)
            sub_val = getattr(subject, attr, None)
            if not _is_blank(req_val) and not _is_blank(sub_val) and req_val != sub_val:
                reasons.append(
                    f"subject {attr} '{sub_val}' does not match request {attr} '{req_val}'"
                )
        # 6. subject lifecycle must not be revoked/archived/deleted.
        sub_lifecycle = getattr(subject, "current_lifecycle_status", None)
        if sub_lifecycle in BLOCKED_LIFECYCLE_STATUSES:
            reasons.append(
                f"subject current_lifecycle_status '{sub_lifecycle}' is not permitted "
                "(must not be revoked, archived, or deleted_reference_only)"
            )

    # 7. Phase 15 may preserve an existing client_facing_approved review status but must
    #    never *create* one. Any decision that would touch such a subject is a warning; a
    #    decision that tries to re-approve it client-facing is impossible here by design.
    sub_review = getattr(subject, "current_review_status", None) if subject is not None else None
    if sub_review == "client_facing_approved":
        warnings.append(
            "subject current_review_status is client_facing_approved; Phase 15 preserves it "
            "but creates no client-facing approval"
        )

    # 8. fixture_test scope must not be mixed with live client/engagement scope.
    scopes = {auth}
    if subject is not None:
        # subject carries no authorization_scope of its own; the request scope governs it.
        pass
    has_live_ref = not _is_blank(getattr(request, "client_id", None)) or not _is_blank(
        getattr(request, "engagement_id", None)
    )
    if FIXTURE_TEST_SCOPE in scopes and has_live_ref:
        reasons.append("fixture_test scope must not be mixed with live client/engagement scope")

    # 9. approve_internal requires a complete, all-true checklist.
    if decision == "approve_internal":
        checklist = getattr(request, "checklist", None)
        if checklist is None:
            reasons.append("approve_internal requires a checklist; none was provided")
        else:
            for check in APPROVE_INTERNAL_CHECKS:
                if getattr(checklist, check, False) is not True:
                    reasons.append(f"approve_internal requires {check}=true")
            for item in getattr(checklist, "missing_items", []) or []:
                reasons.append(f"approve_internal blocked by missing checklist item: {item}")

    # 10. reject / return_for_revision may proceed with an incomplete checklist, but any
    #     missing items or warnings are surfaced (not silently dropped).
    if decision in ("reject", "return_for_revision"):
        checklist = getattr(request, "checklist", None)
        if checklist is not None:
            for item in getattr(checklist, "missing_items", []) or []:
                warnings.append(f"{decision} with missing checklist item: {item}")
            for w in getattr(checklist, "warnings", []) or []:
                warnings.append(f"{decision} checklist warning: {w}")

    return ReviewGovernanceDecision(permitted=not reasons, reasons=reasons, warnings=warnings)
