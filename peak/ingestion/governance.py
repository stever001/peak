"""Deterministic governance guards for the Engagement Packet Ingestion Boundary (Phase 23).

Run *before* any ingestion plan is derived. These checks enforce that a packet ingestion
request is authorized and scoped, that the packet reference's identity and **stored**
authorization scope match the request, that the packet payload is a dict-like structure that
carries **no credential/secret keys**, and that ingestion stays a **no-side-effect boundary**:
nothing may write to the database, call an LLM/AgentNet/network, create client-facing
approval, verify financial impact, or publish a capsule. Packet contents are never persisted.

**Critical scope rule:** the request's ``authorization_scope`` must equal the packet
reference's ``authorization_scope``, and identity (owner/client/engagement) must match.
Owner/client/engagement matching is necessary but **not sufficient**; the scope must match
too.

This module is **stdlib-only** and imports no SQLAlchemy, Alembic, or ``peak.db`` module.
Governance vocabulary mirrors the Phase 9 contracts; the blocking sets are local literals.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import List

from .contracts import (
    ALLOWED_INGESTION_ACTIONS,
    EVIDENCE_LIKE_SECTIONS,
    PacketIngestionRequest,
    PacketValidationResult,
)

REVOKED_AUTHORIZATION_SCOPE = "revoked"
BLOCKED_LIFECYCLE_STATUSES = frozenset({"revoked", "archived", "deleted_reference_only"})
FIXTURE_TEST_SCOPE = "fixture_test"

# Credential/secret term substrings that must never appear as packet-payload keys.
SECRET_KEY_TERMS = (
    "password",
    "secret",
    "api_key",
    "apikey",
    "token",
    "private_key",
    "privatekey",
    "credential",
    "connection_string",
    "access_key",
)


@dataclass
class PacketIngestionGovernanceDecision:
    """Result of the pre-ingestion governance checks."""

    permitted: bool = False
    reasons: List[str] = field(default_factory=list)
    warnings: List[str] = field(default_factory=list)


def _is_blank(value) -> bool:
    return value is None or (isinstance(value, str) and not value.strip())


def _iter_keys(payload):
    """Yield every key found anywhere in a nested dict/list structure (keys only, no values)."""
    if isinstance(payload, dict):
        for key, val in payload.items():
            yield key
            yield from _iter_keys(val)
    elif isinstance(payload, (list, tuple)):
        for item in payload:
            yield from _iter_keys(item)


def _secret_key_hits(payload) -> List[str]:
    """Return the (safe) key names that match a prohibited credential/secret term.

    Only key names are returned — **never values** — so no secret is echoed.
    """
    hits: List[str] = []
    for key in _iter_keys(payload):
        if not isinstance(key, str):
            continue
        low = key.lower()
        if any(term in low for term in SECRET_KEY_TERMS):
            hits.append(key)
    return hits


def validate_packet_reference_scope(
    request: PacketIngestionRequest,
) -> PacketIngestionGovernanceDecision:
    """Compare request identity + scope against the packet reference. Identity is necessary
    but not sufficient; the authorization scope must match too."""
    reasons: list = []
    ref = getattr(request, "packet_reference", None)
    if ref is None:
        return PacketIngestionGovernanceDecision(
            permitted=False, reasons=["packet_reference is required"]
        )

    for attr in ("owner_id", "client_id", "engagement_id"):
        req_val = getattr(request, attr, None)
        ref_val = getattr(ref, attr, None)
        if not _is_blank(req_val) and not _is_blank(ref_val) and req_val != ref_val:
            mismatch = f"packet_reference {attr} '{ref_val}' does not match request {attr} '{req_val}'"
            reasons.append(mismatch)

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
            f"packet_reference.lifecycle_status '{ref_lifecycle}' is not permitted "
            "(must not be revoked, archived, or deleted_reference_only)"
        )

    return PacketIngestionGovernanceDecision(permitted=not reasons, reasons=reasons)


def validate_packet_payload_shape(
    request: PacketIngestionRequest,
) -> PacketIngestionGovernanceDecision:
    """The packet payload must be a dict-like structure carrying no credential/secret keys."""
    reasons: list = []
    payload = getattr(request, "packet_payload", None)
    if payload is None:
        return PacketIngestionGovernanceDecision(
            permitted=False, reasons=["packet_payload is required"]
        )
    if not isinstance(payload, dict):
        return PacketIngestionGovernanceDecision(
            permitted=False, reasons=["packet_payload must be a dict-like object"]
        )
    hits = _secret_key_hits(payload)
    if hits:
        # Report the key names only (never values); do not echo secrets.
        reasons.append(
            "packet_payload contains prohibited credential/secret key(s): "
            + ", ".join(sorted(set(hits)))
        )
    return PacketIngestionGovernanceDecision(permitted=not reasons, reasons=reasons)


def evaluate_packet_ingestion_request(
    request: PacketIngestionRequest,
) -> PacketIngestionGovernanceDecision:
    """Return a governance decision for a packet ingestion request (no side effects)."""
    reasons: list = []
    warnings: list = []

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

    if _is_blank(getattr(request, "idempotency_key", None)):
        reasons.append("idempotency_key is required")

    auth = getattr(request, "authorization_scope", None)
    if auth == REVOKED_AUTHORIZATION_SCOPE:
        reasons.append("authorization_scope 'revoked' is not permitted")

    action = getattr(request, "requested_ingestion_action", None)
    if _is_blank(action):
        reasons.append("requested_ingestion_action is required")
    elif action not in ALLOWED_INGESTION_ACTIONS:
        reasons.append(
            f"requested_ingestion_action '{action}' is not one of "
            f"{sorted(ALLOWED_INGESTION_ACTIONS)}"
        )

    lifecycle = getattr(request, "lifecycle_status", None)
    if lifecycle in BLOCKED_LIFECYCLE_STATUSES:
        reasons.append(
            f"lifecycle_status '{lifecycle}' is not permitted "
            "(must not be revoked, archived, or deleted_reference_only)"
        )

    if getattr(request, "packet_reference", None) is None:
        reasons.append("packet_reference is required")
    else:
        scope_check = validate_packet_reference_scope(request)
        reasons.extend(scope_check.reasons)

    if getattr(request, "packet_payload", None) is None:
        reasons.append("packet_payload is required")
    else:
        payload_check = validate_packet_payload_shape(request)
        reasons.extend(payload_check.reasons)

    # fixture_test scope must not be mixed with live client/engagement scope.
    scopes = {auth}
    ref = getattr(request, "packet_reference", None)
    if ref is not None:
        scopes.add(getattr(ref, "authorization_scope", None))
    has_live_ref = not _is_blank(getattr(request, "client_id", None)) or not _is_blank(
        getattr(request, "engagement_id", None)
    )
    if FIXTURE_TEST_SCOPE in scopes and has_live_ref:
        reasons.append("fixture_test scope must not be mixed with live client/engagement scope")

    return PacketIngestionGovernanceDecision(
        permitted=not reasons, reasons=reasons, warnings=warnings
    )


def build_packet_validation_result(request: PacketIngestionRequest) -> PacketValidationResult:
    """Build the structured ``PacketValidationResult`` for a packet ingestion request."""
    governance = evaluate_packet_ingestion_request(request)
    ref = getattr(request, "packet_reference", None)
    payload = getattr(request, "packet_payload", None)

    schema_valid = isinstance(payload, dict) and ref is not None
    identity_valid = ref is not None and all(
        getattr(ref, a, None) == getattr(request, a, None)
        for a in ("owner_id", "client_id", "engagement_id")
    )
    scope_valid = ref is not None and getattr(ref, "authorization_scope", None) == getattr(
        request, "authorization_scope", None
    ) and not _is_blank(getattr(request, "authorization_scope", None))

    # A packet from an engagement carries client material whenever any client-material
    # section is present; it is handled under the controlled path and never persisted here.
    contains_client_data = isinstance(payload, dict) and any(
        section in payload for section in EVIDENCE_LIKE_SECTIONS
    )

    return PacketValidationResult(
        permitted=governance.permitted,
        schema_valid=schema_valid,
        identity_valid=identity_valid,
        scope_valid=scope_valid,
        contains_client_data=contains_client_data,
        allowed_for_ingestion=governance.permitted,
        reasons=list(governance.reasons),
        warnings=list(governance.warnings),
        missing_items=[],
    )
