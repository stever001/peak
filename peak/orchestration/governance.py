"""Deterministic preflight governance for the packet-processing orchestrator (Phase 25).

These checks are **helpful but not authoritative**. They confirm that the orchestration
request is internally consistent — request identity/scope, the packet reference's identity and
authorization scope, and (later, in the processor) the derived source/evidence/agent
identities. **Stored `Engagement` authorization remains authoritative for any DB write** and
is enforced inside the existing narrow DB writers, not here. Owner/client/engagement matching
is necessary but **not sufficient**.

Stdlib-only; no SQLAlchemy / Alembic / ``peak.db`` import, no LLM/AgentNet/network call. The
orchestrator never stores or echoes raw packet payload content.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import List, Optional

BLOCKED_LIFECYCLE_STATUSES = frozenset({"revoked", "archived", "deleted_reference_only"})


@dataclass
class OrchestrationGovernanceDecision:
    """Result of the deterministic preflight checks (advisory; not the DB write authority)."""

    permitted: bool = False
    reason_code: Optional[str] = None
    reasons: List[str] = field(default_factory=list)
    warnings: List[str] = field(default_factory=list)


def _is_blank(value) -> bool:
    return value is None or (isinstance(value, str) and not value.strip())


def _identity_consistent(reasons: list, request, other, label: str) -> None:
    """Append a reason for each owner/client/engagement field present on both but differing."""
    for attr in ("owner_id", "client_id", "engagement_id"):
        req_val = getattr(request, attr, None)
        other_val = getattr(other, attr, None)
        if not _is_blank(req_val) and not _is_blank(other_val) and req_val != other_val:
            reasons.append(f"{label}.{attr} '{other_val}' does not match request.{attr} '{req_val}'")


def evaluate_orchestration_request(request) -> OrchestrationGovernanceDecision:
    """Preflight-validate a packet ingestion request for orchestration (no side effects)."""
    reasons: list = []
    warnings: list = []

    for attr in ("owner_id", "client_id", "engagement_id", "requested_by", "requester_role",
                 "authorization_scope", "idempotency_key"):
        if _is_blank(getattr(request, attr, None)):
            reasons.append(f"request.{attr} is required")

    lifecycle = getattr(request, "lifecycle_status", None)
    if lifecycle in BLOCKED_LIFECYCLE_STATUSES:
        reasons.append(
            f"request.lifecycle_status '{lifecycle}' is not permitted "
            "(must not be revoked, archived, or deleted_reference_only)"
        )

    ref = getattr(request, "packet_reference", None)
    if ref is None:
        reasons.append("request.packet_reference is required")
    else:
        _identity_consistent(reasons, request, ref, "packet_reference")
        req_scope = getattr(request, "authorization_scope", None)
        ref_scope = getattr(ref, "authorization_scope", None)
        if _is_blank(ref_scope):
            reasons.append("packet_reference.authorization_scope is required")
        elif req_scope != ref_scope:
            reasons.append(
                f"request.authorization_scope '{req_scope}' does not match "
                f"packet_reference.authorization_scope '{ref_scope}' "
                "(owner/client/engagement matching is necessary but not sufficient)"
            )
        ref_lifecycle = getattr(ref, "lifecycle_status", None)
        if ref_lifecycle in BLOCKED_LIFECYCLE_STATUSES:
            reasons.append(
                f"packet_reference.lifecycle_status '{ref_lifecycle}' is not permitted"
            )

    reason_code = None if not reasons else "orchestration_preflight_denied"
    return OrchestrationGovernanceDecision(
        permitted=not reasons, reason_code=reason_code, reasons=reasons, warnings=warnings
    )


def derived_identity_mismatches(request, derived, label: str) -> List[str]:
    """Return owner/client/engagement mismatches between the request and a derived object.

    Used by the processor to preflight-check derived source drafts, evidence requests, and
    agent task requests. Advisory only — the narrow DB writers re-check against the stored
    ``Engagement`` at write-time.
    """
    reasons: list = []
    _identity_consistent(reasons, request, derived, label)
    return reasons
