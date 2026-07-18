"""Deterministic governance guards for the Packet-Derived Review Orchestration Boundary (Phase 29).

Run *before* a review plan is built. Request-level checks enforce that a review-planning request
is authorized and scoped, carries an idempotency key, references at least one safe subject (in
strict mode), and carries **no raw packet/evidence/interview/source content, no credential/secret
fields, and no approval / execution / publication / financial-verification intent**. It is a
**review-planning** boundary — it never approves anything, and **"ready for human review" never
means approved**.

**Critical scope rule:** the request's ``authorization_scope`` must be present, and any structured
subject reference that carries owner/client/engagement/scope must match the request.
Owner/client/engagement matching is necessary but **not sufficient**; scope must match too.

This module is **stdlib-only**. It imports no SQLAlchemy, Alembic, ``peak.db``, live/mock LLM,
AgentNet/MCP/resolver/connector, or network module.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import List, Optional, Tuple

from .contracts import (
    ALLOWED_REVIEW_ACTIONS,
    BLOCKED_APPROVAL_INTENT,
    BLOCKED_EXECUTION_INTENT,
    BLOCKED_FINANCIAL_VERIFICATION_INTENT,
    BLOCKED_INVALID_SCOPE,
    BLOCKED_LIFECYCLE,
    BLOCKED_PUBLICATION_INTENT,
    BLOCKED_RAW_CONTENT,
    BLOCKED_SECRET_LIKE_CONTENT,
    PacketReviewOrchestrationRequest,
)

REVOKED_AUTHORIZATION_SCOPE = "revoked"
BLOCKED_LIFECYCLE_STATUSES = frozenset({"revoked", "archived", "deleted_reference_only"})
_MAX_REF_LEN = 128  # a safe id/ref is short; longer/multiline values look like raw content

# Credential/secret term substrings that must never appear as request/context keys.
SECRET_KEY_TERMS = (
    "password", "secret", "api_key", "apikey", "token", "private_key", "privatekey",
    "credential", "connection_string", "access_key",
)
# Raw-content term substrings that must never appear as request/context keys. Phase 29 accepts
# ids and references only — never raw payloads, raw text, source/file bytes, or generated output.
RAW_CONTENT_KEY_TERMS = (
    "packet_payload", "raw_packet", "raw_evidence", "evidence_text", "raw_interview",
    "interview_text", "raw_text", "raw_content", "source_bytes", "file_bytes", "raw_source",
    "generated_output", "agent_output", "llm_output", "prompt_text", "payload",
)
# Prohibited-intent term substrings: any request/context key asking Phase 29 to approve, execute,
# publish, verify financials, or produce client-facing output is denied. Phase 29 only *plans*.
APPROVAL_INTENT_TERMS = ("approve", "approval", "sign_off", "signoff", "client_facing")
EXECUTION_INTENT_TERMS = ("execute", "run_agent", "mock_agent", "agent_execution", "llm_call",
                          "network", "http")
PUBLICATION_INTENT_TERMS = ("publish", "capsule_publication", "capsule_candidate")
FINANCIAL_INTENT_TERMS = ("verify_financial", "financial_verif", "financial_verification")


@dataclass
class ReviewOrchestrationGovernanceDecision:
    """Result of the pre-plan request-level governance checks."""

    permitted: bool = False
    reason_code: Optional[str] = None
    readiness_state: Optional[str] = None  # a blocked_* state hint when not permitted
    reasons: List[str] = field(default_factory=list)
    warnings: List[str] = field(default_factory=list)


def _is_blank(value) -> bool:
    return value is None or (isinstance(value, str) and not value.strip())


def _iter_keys(value):
    """Yield every key found anywhere in a nested dict/list structure (keys only, no values)."""
    if isinstance(value, dict):
        for key, val in value.items():
            yield key
            yield from _iter_keys(val)
    elif isinstance(value, (list, tuple)):
        for item in value:
            yield from _iter_keys(item)


def _all_keys(container) -> List[str]:
    keys: List[str] = []
    own = getattr(container, "__dict__", None)
    if isinstance(own, dict):
        for key, val in own.items():
            keys.append(key)
            keys.extend(_iter_keys(val))
    elif isinstance(container, dict):
        keys.extend(_iter_keys(container))
    return [k for k in keys if isinstance(k, str)]


def _ref_lists(request: PacketReviewOrchestrationRequest):
    """Yield (field_name, list) for every id/ref list field on the request."""
    for name in (
        "source_ingestion_record_ids", "evidence_reference_ids", "agent_task_queue_record_ids",
        "agent_task_queue_draft_refs", "source_ingestion_receipt_refs", "evidence_receipt_refs",
        "task_queue_receipt_refs",
    ):
        yield name, list(getattr(request, name, None) or [])


def scan_prohibited_content(
    request: PacketReviewOrchestrationRequest,
) -> Tuple[Optional[str], List[str]]:
    """Return (readiness_state, reasons) for any prohibited content/intent, or (None, []).

    Reports **key names / field names only** — never values — so no secret or raw content is
    echoed. Checks: secret-like keys, raw-content keys, approval/execution/publication/financial
    intent keys, non-string ref entries (arbitrary JSON/content), and over-long/multiline ref
    values (raw content).
    """
    keys = _all_keys(request)
    context = getattr(request, "context", None)
    if isinstance(context, dict):
        keys += _all_keys(context)
    low = [k.lower() for k in keys]

    def _hit(terms):
        return sorted({k for k, lk in zip(keys, low) if any(t in lk for t in terms)})

    secret_hits = _hit(SECRET_KEY_TERMS)
    if secret_hits:
        return BLOCKED_SECRET_LIKE_CONTENT, [
            "request contains prohibited credential/secret key(s): " + ", ".join(secret_hits)]
    raw_hits = _hit(RAW_CONTENT_KEY_TERMS)
    if raw_hits:
        return BLOCKED_RAW_CONTENT, [
            "request contains prohibited raw-content key(s): " + ", ".join(raw_hits)]
    if _hit(APPROVAL_INTENT_TERMS):
        return BLOCKED_APPROVAL_INTENT, [
            "request contains prohibited approval/client-facing intent key(s): "
            + ", ".join(_hit(APPROVAL_INTENT_TERMS))]
    if _hit(EXECUTION_INTENT_TERMS):
        return BLOCKED_EXECUTION_INTENT, [
            "request contains prohibited execution/network intent key(s): "
            + ", ".join(_hit(EXECUTION_INTENT_TERMS))]
    if _hit(PUBLICATION_INTENT_TERMS):
        return BLOCKED_PUBLICATION_INTENT, [
            "request contains prohibited capsule/publication intent key(s): "
            + ", ".join(_hit(PUBLICATION_INTENT_TERMS))]
    if _hit(FINANCIAL_INTENT_TERMS):
        return BLOCKED_FINANCIAL_VERIFICATION_INTENT, [
            "request contains prohibited financial-verification intent key(s): "
            + ", ".join(_hit(FINANCIAL_INTENT_TERMS))]

    # Ref-value shape: refs must be short strings (ids), never arbitrary objects or raw text.
    for field_name, values in _ref_lists(request):
        for i, v in enumerate(values):
            if not isinstance(v, str):
                return BLOCKED_RAW_CONTENT, [
                    f"{field_name}[{i}] is not a string id/reference (arbitrary content rejected)"]
            if "\n" in v or "\r" in v or len(v) > _MAX_REF_LEN:
                return BLOCKED_RAW_CONTENT, [
                    f"{field_name}[{i}] looks like raw content, not a short id/reference"]
    for name in ("packet_processing_receipt_ref",):
        v = getattr(request, name, None)
        if isinstance(v, str) and ("\n" in v or len(v) > _MAX_REF_LEN):
            return BLOCKED_RAW_CONTENT, [f"{name} looks like raw content, not a short reference"]
    return None, []


def _has_subjects(request: PacketReviewOrchestrationRequest) -> bool:
    if getattr(request, "packet_processing_receipt_ref", None):
        return True
    for _name, values in _ref_lists(request):
        if values:
            return True
    return False


def _reviewer_role_ok(reviewer_role) -> bool:
    """A reviewer_role must be a short role label — not an email/credential/PII-like blob."""
    if reviewer_role is None:
        return True
    if not isinstance(reviewer_role, str):
        return False
    if "@" in reviewer_role or len(reviewer_role) > 64 or "\n" in reviewer_role:
        return False
    return True


def evaluate_packet_review_request(
    request: PacketReviewOrchestrationRequest,
) -> ReviewOrchestrationGovernanceDecision:
    """Return a request-level governance decision (no side effects)."""
    reasons: List[str] = []

    for attr in ("owner_id", "client_id", "engagement_id", "requested_by", "requester_role",
                 "authorization_scope"):
        if _is_blank(getattr(request, attr, None)):
            reasons.append(f"{attr} is required")
    if _is_blank(getattr(request, "idempotency_key", None)):
        reasons.append("idempotency_key is required")

    auth = getattr(request, "authorization_scope", None)
    if auth == REVOKED_AUTHORIZATION_SCOPE:
        reasons.append("authorization_scope 'revoked' is not permitted")

    action = getattr(request, "requested_action", None)
    if _is_blank(action):
        reasons.append("requested_action is required")
    elif action not in ALLOWED_REVIEW_ACTIONS:
        # An action outside the allowlist may signal approval/publication/execution intent.
        low = str(action).lower()
        if any(t in low for t in APPROVAL_INTENT_TERMS):
            return ReviewOrchestrationGovernanceDecision(
                permitted=False, reason_code="review_request_denied",
                readiness_state=BLOCKED_APPROVAL_INTENT,
                reasons=[f"requested_action '{action}' implies approval; Phase 29 only plans review"])
        reasons.append(
            f"requested_action '{action}' is not one of {sorted(ALLOWED_REVIEW_ACTIONS)}")

    if not _reviewer_role_ok(getattr(request, "reviewer_role", None)):
        return ReviewOrchestrationGovernanceDecision(
            permitted=False, reason_code="review_request_denied",
            readiness_state=BLOCKED_SECRET_LIKE_CONTENT,
            reasons=["reviewer_role must be a short role label (no email/credential/PII-like value)"])

    lifecycle = getattr(request, "lifecycle_status", None)
    if lifecycle in BLOCKED_LIFECYCLE_STATUSES:
        return ReviewOrchestrationGovernanceDecision(
            permitted=False, reason_code="review_request_denied",
            readiness_state=BLOCKED_LIFECYCLE,
            reasons=[f"lifecycle_status '{lifecycle}' is not permitted "
                     "(must not be revoked, archived, or deleted_reference_only)"])

    # Prohibited content / intent (secret / raw / approval / execution / publication / financial).
    state, content_reasons = scan_prohibited_content(request)
    if state is not None:
        return ReviewOrchestrationGovernanceDecision(
            permitted=False, reason_code="review_request_denied",
            readiness_state=state, reasons=content_reasons)

    # Structured subject-reference identity/scope (necessary but not sufficient).
    mismatches = subject_identity_mismatches(request)
    if mismatches:
        return ReviewOrchestrationGovernanceDecision(
            permitted=False, reason_code="review_request_denied",
            readiness_state=BLOCKED_INVALID_SCOPE, reasons=mismatches)

    # Strict mode requires at least one safe subject reference.
    if getattr(request, "strict_mode", True) and not _has_subjects(request):
        reasons.append("at least one safe subject reference is required in strict_mode")

    if reasons:
        return ReviewOrchestrationGovernanceDecision(
            permitted=False, reason_code="review_request_denied",
            readiness_state=BLOCKED_INVALID_SCOPE, reasons=reasons)
    return ReviewOrchestrationGovernanceDecision(permitted=True)


def subject_identity_mismatches(request: PacketReviewOrchestrationRequest) -> List[str]:
    """Compare any structured subject refs (in ``context['subject_refs']``) against the request.

    Plain id-list entries carry no identity and are trusted as belonging to the request's scope
    (the caller supplied them under the authorized request). Structured refs — if present — must
    match owner/client/engagement and authorization_scope.
    """
    reasons: List[str] = []
    context = getattr(request, "context", None)
    structured = []
    if isinstance(context, dict):
        raw = context.get("subject_refs")
        if isinstance(raw, (list, tuple)):
            structured = [r for r in raw if isinstance(r, dict)]
    for i, ref in enumerate(structured):
        for attr in ("owner_id", "client_id", "engagement_id"):
            rv = ref.get(attr)
            if rv is not None and rv != getattr(request, attr, None):
                reasons.append(f"subject_refs[{i}].{attr} does not match request.{attr}")
        rs = ref.get("authorization_scope")
        if rs is not None and rs != getattr(request, "authorization_scope", None):
            reasons.append(
                f"subject_refs[{i}].authorization_scope does not match request.authorization_scope "
                "(owner/client/engagement matching is necessary but not sufficient)")
    return reasons
