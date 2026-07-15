"""Deterministic persistence-readiness guards for the Review Persistence Boundary (Phase 16).

Run *before* any review-record draft or write plan is built. These checks enforce that a
persistence request is authorized and scoped, that the Phase 15 gate result it carries was
itself permitted and side-effect-free, and that persistence planning stays **DB-aware but
not DB-writing** — nothing may create client-facing approval, verify financial impact, or
publish a capsule, and no plan is a real write.

**Critical scope rule:** the request's ``authorization_scope`` must equal the subject
record's **stored** ``authorization_scope`` (``subject_snapshot.stored_authorization_scope``).
Owner/client/engagement matching is necessary but **not sufficient**; the request scope
alone is insufficient. A future DB-backed review must load that stored scope from the
controlled DB.

Governance vocabulary mirrors the Phase 9 contracts (peak/db/enums.py and
schemas/*.schema.json are the source of truth); the blocking sets are local literals so
this module stays import-light and touches no database or network.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import List

from .persistence_contracts import (
    ALLOWED_PERSISTENCE_ACTIONS,
    ReviewPersistenceDecision,
    ReviewPersistenceRequest,
)

REVOKED_AUTHORIZATION_SCOPE = "revoked"
BLOCKED_LIFECYCLE_STATUSES = frozenset({"revoked", "archived", "deleted_reference_only"})
FIXTURE_TEST_SCOPE = "fixture_test"

# Gate-result flags that must be False before a permitted gate result may be persisted.
# (Any True flag means the Phase 15 gate already had a side effect — refuse to plan.)
GATE_RESULT_FORBIDDEN_TRUE_FLAGS = (
    "database_write_made",
    "client_facing_output_created",
    "capsule_publication_made",
    "llm_call_made",
    "agentnet_call_made",
    "network_call_made",
)


@dataclass
class ReviewPersistenceGovernanceDecision:
    """Result of the pre-persistence governance checks."""

    permitted: bool = False
    reasons: List[str] = field(default_factory=list)
    warnings: List[str] = field(default_factory=list)


def _is_blank(value) -> bool:
    return value is None or (isinstance(value, str) and not value.strip())


def validate_subject_scope_against_request(
    request: ReviewPersistenceRequest,
) -> ReviewPersistenceGovernanceDecision:
    """Compare request scope AND identity against the stored subject snapshot.

    Owner/client/engagement must match (necessary), and
    ``request.authorization_scope == subject_snapshot.stored_authorization_scope``
    (the sufficient scope check). Matching identity alone is **not** sufficient.
    """
    reasons: list = []
    subject = getattr(request, "subject_snapshot", None)
    if subject is None:
        return ReviewPersistenceGovernanceDecision(
            permitted=False, reasons=["subject_snapshot is required"]
        )

    # Identity matching — necessary but not sufficient.
    for attr in ("owner_id", "client_id", "engagement_id"):
        req_val = getattr(request, attr, None)
        sub_val = getattr(subject, attr, None)
        if not _is_blank(req_val) and not _is_blank(sub_val) and req_val != sub_val:
            reasons.append(
                f"subject_snapshot {attr} '{sub_val}' does not match request {attr} '{req_val}'"
            )

    # Stored-scope matching — the sufficient scope gate.
    req_scope = getattr(request, "authorization_scope", None)
    stored_scope = getattr(subject, "stored_authorization_scope", None)
    if _is_blank(stored_scope):
        reasons.append(
            "subject_snapshot.stored_authorization_scope is required; a DB-backed review "
            "must load the subject's stored scope, not rely only on the request scope"
        )
    elif req_scope != stored_scope:
        reasons.append(
            f"request.authorization_scope '{req_scope}' does not match "
            f"subject_snapshot.stored_authorization_scope '{stored_scope}' "
            "(owner/client/engagement matching is necessary but not sufficient)"
        )

    return ReviewPersistenceGovernanceDecision(permitted=not reasons, reasons=reasons)


def validate_gate_result_for_persistence(
    request: ReviewPersistenceRequest,
) -> ReviewPersistenceGovernanceDecision:
    """The carried Phase 15 gate result must be permitted and fully side-effect-free."""
    reasons: list = []
    gate = getattr(request, "review_gate_result", None)
    if gate is None:
        return ReviewPersistenceGovernanceDecision(
            permitted=False, reasons=["review_gate_result is required"]
        )
    if getattr(gate, "permitted", False) is not True:
        reasons.append("review_gate_result must be permitted=true before persistence planning")
    for flag in GATE_RESULT_FORBIDDEN_TRUE_FLAGS:
        if getattr(gate, flag, False) is True:
            reasons.append(f"review_gate_result.{flag} must be false (no side effect may exist)")
    return ReviewPersistenceGovernanceDecision(permitted=not reasons, reasons=reasons)


def evaluate_review_persistence_request(
    request: ReviewPersistenceRequest,
) -> ReviewPersistenceGovernanceDecision:
    """Return a governance decision for a review persistence request (no side effects)."""
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

    # 3. requested_persistence_action must be allowed.
    action = getattr(request, "requested_persistence_action", None)
    if _is_blank(action):
        reasons.append("requested_persistence_action is required")
    elif action not in ALLOWED_PERSISTENCE_ACTIONS:
        reasons.append(
            f"requested_persistence_action '{action}' is not one of "
            f"{sorted(ALLOWED_PERSISTENCE_ACTIONS)}"
        )

    # 4. request lifecycle_status must not be revoked/archived/deleted.
    lifecycle = getattr(request, "lifecycle_status", None)
    if lifecycle in BLOCKED_LIFECYCLE_STATUSES:
        reasons.append(
            f"lifecycle_status '{lifecycle}' is not permitted "
            "(must not be revoked, archived, or deleted_reference_only)"
        )

    # 5. subject_snapshot required; its stored lifecycle must not be revoked/archived/deleted.
    subject = getattr(request, "subject_snapshot", None)
    if subject is None:
        reasons.append("subject_snapshot is required")
    else:
        stored_lifecycle = getattr(subject, "stored_lifecycle_status", None)
        if stored_lifecycle in BLOCKED_LIFECYCLE_STATUSES:
            reasons.append(
                f"subject_snapshot.stored_lifecycle_status '{stored_lifecycle}' is not "
                "permitted (must not be revoked, archived, or deleted_reference_only)"
            )

    # 6. Subject identity + STORED scope comparison (necessary + sufficient).
    if subject is not None:
        scope_check = validate_subject_scope_against_request(request)
        reasons.extend(scope_check.reasons)

    # 7. The carried gate result must be permitted and side-effect-free.
    if getattr(request, "review_gate_result", None) is None:
        reasons.append("review_gate_result is required")
    else:
        gate_check = validate_gate_result_for_persistence(request)
        reasons.extend(gate_check.reasons)
        # 7a. A persistence plan may never inherit a client-facing/capsule flag from the
        #     gate decision — Phase 16 creates neither.
        decision = getattr(request.review_gate_result, "decision", None)
        if decision is not None:
            if getattr(decision, "client_facing_approved", False) is True:
                reasons.append(
                    "review_gate_result.decision.client_facing_approved is true; "
                    "no persistence decision may create client-facing approval"
                )
            if getattr(decision, "capsule_candidate_ready", False) is True:
                reasons.append(
                    "review_gate_result.decision.capsule_candidate_ready is true; "
                    "no persistence decision may publish capsules"
                )

    # 8. fixture_test scope must not be mixed with live client/engagement scope.
    scopes = {auth}
    if subject is not None:
        scopes.add(getattr(subject, "stored_authorization_scope", None))
    has_live_ref = not _is_blank(getattr(request, "client_id", None)) or not _is_blank(
        getattr(request, "engagement_id", None)
    )
    if FIXTURE_TEST_SCOPE in scopes and has_live_ref:
        reasons.append("fixture_test scope must not be mixed with live client/engagement scope")

    return ReviewPersistenceGovernanceDecision(
        permitted=not reasons, reasons=reasons, warnings=warnings
    )


def build_persistence_decision(request: ReviewPersistenceRequest) -> ReviewPersistenceDecision:
    """Evaluate the request and return a ``ReviewPersistenceDecision`` (no side effects).

    Carries the requested action alongside the permit/deny outcome so callers get the
    decision and action together.
    """
    governance = evaluate_review_persistence_request(request)
    return ReviewPersistenceDecision(
        permitted=governance.permitted,
        persistence_action=getattr(request, "requested_persistence_action", None),
        reasons=list(governance.reasons),
        warnings=list(governance.warnings),
    )
