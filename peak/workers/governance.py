"""Deterministic governance guards for the Evidence Normalization Worker (Phase 14).

Run *before* normalization. These checks enforce that a normalization run is authorized
and scoped, and that the output stays **review-gated**: a request may never make evidence
authoritative, client-facing, or capsule-published, and the result always defaults to
``draft`` / ``needs_review``.

Governance vocabulary mirrors the Phase 9 contracts (peak/db/enums.py and
schemas/*.schema.json are the source of truth); the blocking sets are local literals so
this module stays import-light and touches no database or network.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import List

from .contracts import EvidenceNormalizationRequest, EvidenceReviewGate

REVOKED_AUTHORIZATION_SCOPE = "revoked"
BLOCKED_LIFECYCLE_STATUSES = frozenset({"revoked", "archived", "deleted_reference_only"})
BLOCKED_REVIEW_STATUSES = frozenset({"rejected"})
FIXTURE_TEST_SCOPE = "fixture_test"


@dataclass
class EvidenceGovernanceDecision:
    """Result of the pre-normalization governance checks."""

    permitted: bool = False
    reasons: List[str] = field(default_factory=list)
    warnings: List[str] = field(default_factory=list)


def _is_blank(value) -> bool:
    return value is None or (isinstance(value, str) and not value.strip())


def evaluate_evidence_normalization_request(
    request: EvidenceNormalizationRequest,
) -> EvidenceGovernanceDecision:
    """Return a governance decision for an evidence normalization request."""
    reasons: list = []
    warnings: list = []

    # 1. Required identity / authorization fields.
    for attr in ("owner_id", "client_id", "engagement_id", "requested_by", "authorization_scope"):
        if _is_blank(getattr(request, attr, None)):
            reasons.append(f"{attr} is required")

    # 2. authorization_scope must not be revoked.
    auth = getattr(request, "authorization_scope", None)
    if auth == REVOKED_AUTHORIZATION_SCOPE:
        reasons.append("authorization_scope 'revoked' is not permitted")

    # 3. lifecycle_status must not be revoked/archived/deleted.
    lifecycle = getattr(request, "lifecycle_status", None)
    if lifecycle in BLOCKED_LIFECYCLE_STATUSES:
        reasons.append(
            f"lifecycle_status '{lifecycle}' is not permitted "
            "(must not be revoked, archived, or deleted_reference_only)"
        )

    # 4. review_status must not be rejected.
    review = getattr(request, "review_status", None)
    if review in BLOCKED_REVIEW_STATUSES:
        reasons.append(f"review_status '{review}' is rejected; normalization not permitted")

    # 5. raw_evidence and its source_reference are required.
    raw = getattr(request, "raw_evidence", None)
    source_ref = getattr(raw, "source_reference", None) if raw is not None else None
    if raw is None:
        reasons.append("raw_evidence is required")
    elif source_ref is None:
        reasons.append("raw_evidence.source_reference is required")

    # 6. source_reference.authorization_scope must be compatible with the request scope.
    if source_ref is not None:
        src_auth = getattr(source_ref, "authorization_scope", None)
        if not _is_blank(src_auth) and not _is_blank(auth) and src_auth != auth:
            reasons.append(
                f"source_reference authorization_scope '{src_auth}' is incompatible with "
                f"request authorization_scope '{auth}'"
            )

    # 7. No request may escalate authority, go client-facing, or publish capsules.
    if getattr(request, "authoritative", False):
        reasons.append("a request may not set authoritative=true")
    if getattr(request, "client_facing_approved", False) or getattr(
        request, "client_facing_output_requested", False
    ):
        reasons.append("a request may not request client_facing_approved / client-facing output")
    if getattr(request, "capsule_publication_requested", False) or getattr(
        request, "publish_capsule", False
    ):
        reasons.append("a request may not request capsule publication")

    # 8. fixture_test scope must not be mixed with live client/engagement scope.
    scopes = {auth}
    if source_ref is not None:
        scopes.add(getattr(source_ref, "authorization_scope", None))
    has_live_ref = not _is_blank(getattr(request, "client_id", None)) or not _is_blank(
        getattr(request, "engagement_id", None)
    )
    if FIXTURE_TEST_SCOPE in scopes and has_live_ref:
        reasons.append("fixture_test scope must not be mixed with live client/engagement scope")

    return EvidenceGovernanceDecision(permitted=not reasons, reasons=reasons, warnings=warnings)


def build_evidence_review_gate(request: EvidenceNormalizationRequest) -> EvidenceReviewGate:
    """Return the review gate stamped onto normalized output (defaults are the gate).

    Independent of the request contents: worker output is always draft/needs_review,
    non-authoritative, non-client-facing, and not a capsule candidate.
    """
    return EvidenceReviewGate()
