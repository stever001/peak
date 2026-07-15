"""Deterministic guards for the Evidence Persistence Mapping (Phase 18).

Run *before* any evidence persistence draft or controlled write plan is built. These checks
enforce that a mapping request is authorized and scoped, that the Phase 14 normalization
output it carries was itself permitted and side-effect-free and stayed review-gated, and
that mapping stays **DB-aware but not DB-writing** — nothing may create client-facing
approval, verify financial impact, or publish a capsule, and no plan is a real write.

**Critical scope rule:** the request's ``authorization_scope`` must equal the parent
subject's **stored** ``authorization_scope`` (``subject_snapshot.stored_authorization_scope``).
Because a freshly normalized evidence record may have no stored DB row yet, the stored
parent/source/engagement subject is the authorization anchor. Owner/client/engagement
matching is necessary but **not sufficient**; the request scope alone is insufficient.

This module is **stdlib-only** and imports no SQLAlchemy, Alembic, or ``peak.db`` module.
Governance vocabulary mirrors the Phase 9 contracts (peak/db/enums.py and
schemas/*.schema.json are the source of truth); the blocking sets are local literals.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import List

from .persistence_contracts import (
    ALLOWED_PERSISTENCE_ACTION,
    EvidencePersistenceDecision,
    EvidencePersistenceRequest,
    TARGET_ACTION,
    TARGET_TABLE,
)

REVOKED_AUTHORIZATION_SCOPE = "revoked"
BLOCKED_LIFECYCLE_STATUSES = frozenset({"revoked", "archived", "deleted_reference_only"})
FIXTURE_TEST_SCOPE = "fixture_test"

# Normalization-result flags that must be False before the output may be persistence-mapped.
# (Any True flag means the Phase 14 worker already had a side effect — refuse to map.)
NORMALIZATION_FORBIDDEN_TRUE_FLAGS = (
    "database_write_made",
    "llm_call_made",
    "agentnet_call_made",
    "network_call_made",
    "capsule_publication_made",
)


@dataclass
class EvidencePersistenceGovernanceDecision:
    """Result of the pre-mapping governance checks."""

    permitted: bool = False
    reasons: List[str] = field(default_factory=list)
    warnings: List[str] = field(default_factory=list)


def _is_blank(value) -> bool:
    return value is None or (isinstance(value, str) and not value.strip())


def validate_evidence_subject_scope(
    request: EvidencePersistenceRequest,
) -> EvidencePersistenceGovernanceDecision:
    """Compare request scope AND identity against the stored parent subject snapshot.

    Owner/client/engagement must match (necessary) both the subject snapshot and — where
    present — the normalized record, and
    ``request.authorization_scope == subject_snapshot.stored_authorization_scope`` (the
    sufficient scope check). Matching identity alone is **not** sufficient.
    """
    reasons: list = []
    subject = getattr(request, "subject_snapshot", None)
    if subject is None:
        return EvidencePersistenceGovernanceDecision(
            permitted=False, reasons=["subject_snapshot is required"]
        )

    # Identity matching against the subject snapshot — necessary but not sufficient.
    for attr in ("owner_id", "client_id", "engagement_id"):
        req_val = getattr(request, attr, None)
        sub_val = getattr(subject, attr, None)
        if not _is_blank(req_val) and not _is_blank(sub_val) and req_val != sub_val:
            reasons.append(
                f"subject_snapshot {attr} '{sub_val}' does not match request {attr} '{req_val}'"
            )

    # Identity matching against the normalized record — the evidence must belong to the
    # same owner/client/engagement it is being persisted under.
    record = getattr(request, "normalized_record", None)
    if record is not None:
        for attr in ("owner_id", "client_id", "engagement_id"):
            req_val = getattr(request, attr, None)
            rec_val = getattr(record, attr, None)
            if not _is_blank(req_val) and not _is_blank(rec_val) and req_val != rec_val:
                reasons.append(
                    f"normalized_record {attr} '{rec_val}' does not match request {attr} "
                    f"'{req_val}'"
                )

    # Stored-scope matching — the sufficient scope gate.
    req_scope = getattr(request, "authorization_scope", None)
    stored_scope = getattr(subject, "stored_authorization_scope", None)
    if _is_blank(stored_scope):
        reasons.append(
            "subject_snapshot.stored_authorization_scope is required; a future controlled "
            "writer must load the parent subject's stored scope, not rely only on the "
            "request scope"
        )
    elif req_scope != stored_scope:
        reasons.append(
            f"request.authorization_scope '{req_scope}' does not match "
            f"subject_snapshot.stored_authorization_scope '{stored_scope}' "
            "(owner/client/engagement matching is necessary but not sufficient)"
        )

    return EvidencePersistenceGovernanceDecision(permitted=not reasons, reasons=reasons)


def validate_normalization_result_for_persistence(
    request: EvidencePersistenceRequest,
) -> EvidencePersistenceGovernanceDecision:
    """The Phase 14 output must be permitted, side-effect-free, and still review-gated."""
    reasons: list = []
    result = getattr(request, "normalization_result", None)
    record = getattr(request, "normalized_record", None)

    if result is None:
        reasons.append("normalization_result is required")
    else:
        if getattr(result, "permitted", False) is not True:
            reasons.append("normalization_result must be permitted=true before persistence mapping")
        for flag in NORMALIZATION_FORBIDDEN_TRUE_FLAGS:
            if getattr(result, flag, False) is True:
                reasons.append(
                    f"normalization_result.{flag} must be false (no side effect may exist)"
                )

    if record is None:
        reasons.append("normalized_record is required")
    else:
        # Review-gated posture must be intact — mapping never advances authority.
        if getattr(record, "output_status", None) != "draft":
            reasons.append("normalized_record.output_status must be 'draft'")
        if getattr(record, "review_status", None) != "needs_review":
            reasons.append("normalized_record.review_status must be 'needs_review'")
        if getattr(record, "authoritative", False) is not False:
            reasons.append("normalized_record.authoritative must be false")
        if getattr(record, "client_facing_approved", False) is not False:
            reasons.append(
                "normalized_record.client_facing_approved must be false; no persistence "
                "mapping may create client-facing approval"
            )
        if getattr(record, "capsule_candidate_ready", False) is not False:
            reasons.append(
                "normalized_record.capsule_candidate_ready must be false; no persistence "
                "mapping may publish capsules"
            )

    return EvidencePersistenceGovernanceDecision(permitted=not reasons, reasons=reasons)


def evaluate_evidence_persistence_request(
    request: EvidencePersistenceRequest,
) -> EvidencePersistenceGovernanceDecision:
    """Return a governance decision for an evidence persistence request (no side effects)."""
    reasons: list = []
    warnings: list = []

    # 1. Required identity / authorization fields.
    for attr in (
        "owner_id",
        "client_id",
        "engagement_id",
        "requested_by",
        "requester_role",
        "authorization_scope",
    ):
        if _is_blank(getattr(request, attr, None)):
            reasons.append(f"{attr} is required")

    # 2. idempotency_key is required for future write safety.
    if _is_blank(getattr(request, "idempotency_key", None)):
        reasons.append("idempotency_key is required for future write safety")

    # 3. authorization_scope must not be revoked.
    auth = getattr(request, "authorization_scope", None)
    if auth == REVOKED_AUTHORIZATION_SCOPE:
        reasons.append("authorization_scope 'revoked' is not permitted")

    # 4. requested_persistence_action must be the one allowed action.
    action = getattr(request, "requested_persistence_action", None)
    if _is_blank(action):
        reasons.append("requested_persistence_action is required")
    elif action != ALLOWED_PERSISTENCE_ACTION:
        reasons.append(
            f"requested_persistence_action '{action}' is not '{ALLOWED_PERSISTENCE_ACTION}'"
        )

    # 5. request lifecycle_status must not be revoked/archived/deleted.
    lifecycle = getattr(request, "lifecycle_status", None)
    if lifecycle in BLOCKED_LIFECYCLE_STATUSES:
        reasons.append(
            f"lifecycle_status '{lifecycle}' is not permitted "
            "(must not be revoked, archived, or deleted_reference_only)"
        )

    # 6. subject_snapshot required; its stored lifecycle must not be revoked/archived/deleted.
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
        # 7. Subject/record identity + STORED scope comparison (necessary + sufficient).
        scope_check = validate_evidence_subject_scope(request)
        reasons.extend(scope_check.reasons)

    # 8. The carried normalization output must be permitted, side-effect-free, review-gated.
    norm_check = validate_normalization_result_for_persistence(request)
    reasons.extend(norm_check.reasons)

    # 9. fixture_test scope must not be mixed with live client/engagement scope.
    scopes = {auth}
    if subject is not None:
        scopes.add(getattr(subject, "stored_authorization_scope", None))
    has_live_ref = not _is_blank(getattr(request, "client_id", None)) or not _is_blank(
        getattr(request, "engagement_id", None)
    )
    if FIXTURE_TEST_SCOPE in scopes and has_live_ref:
        reasons.append("fixture_test scope must not be mixed with live client/engagement scope")

    return EvidencePersistenceGovernanceDecision(
        permitted=not reasons, reasons=reasons, warnings=warnings
    )


def build_evidence_persistence_decision(
    request: EvidencePersistenceRequest,
) -> EvidencePersistenceDecision:
    """Evaluate the request and return an ``EvidencePersistenceDecision`` (no side effects)."""
    governance = evaluate_evidence_persistence_request(request)
    return EvidencePersistenceDecision(
        permitted=governance.permitted,
        persistence_action=getattr(request, "requested_persistence_action", None),
        target_table=TARGET_TABLE,
        requested_action=TARGET_ACTION,
        reasons=list(governance.reasons),
        warnings=list(governance.warnings),
    )
