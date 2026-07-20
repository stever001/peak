"""Deterministic governance guards for the Internal Reviewer Decision Boundary (Phase 32).

Run *before* a decision draft / routing plan is built. Request-level checks enforce that a
reviewer-decision request is authorized and scoped, names a review bundle, carries a **short safe**
reviewer role / decision reason code / decision summary, uses an **allowed** decision intent, and
carries **no raw packet/evidence/interview/source content, no credential/secret/DB-URL/raw-SQL
fields, and no approval / publication / execution / financial / client-facing intent**. It is a
**decision-planning** boundary — it never approves anything, and **``ready_for_internal_use`` is
not approval**.

**Critical scope rule:** the request's ``authorization_scope`` must be present, and any structured
reference that carries owner/client/engagement/scope must match the request. Owner/client/
engagement matching is necessary but **not sufficient**; scope must match too.

This module is **stdlib-only**. It imports no SQLAlchemy, Alembic, ``peak.db``, Phase 22 review
writer, live/mock LLM, AgentNet/MCP/resolver/connector, or network module.
"""

from __future__ import annotations

import re
from dataclasses import dataclass, field
from typing import List, Optional, Tuple

from .contracts import (
    ALLOWED_DECISION_ACTIONS,
    ALLOWED_DECISION_INTENTS,
    ALLOWED_RETURN_STAGES,
    BLOCKED_DISALLOWED_INTENT,
    BLOCKED_INVALID_SCOPE,
    BLOCKED_LIFECYCLE,
    BLOCKED_MISSING_REVIEW_BUNDLE,
    BLOCKED_RAW_CONTENT,
    BLOCKED_SECRET_LIKE_CONTENT,
    BLOCKED_UNSUPPORTED_INTENT,
    InternalReviewerDecisionRequest,
)

REVOKED_AUTHORIZATION_SCOPE = "revoked"
BLOCKED_LIFECYCLE_STATUSES = frozenset({"revoked", "archived", "deleted_reference_only"})
_MAX_REF_LEN = 128     # a safe id/ref is short; longer/multiline values look like raw content
_MAX_LABEL_LEN = 64    # role labels / reason codes / followup labels are short
_MAX_SUMMARY_LEN = 240  # a decision summary is a short single-line reviewer note

SECRET_KEY_TERMS = (
    "password", "secret", "api_key", "apikey", "token", "private_key", "privatekey",
    "credential", "connection_string", "access_key",
)
RAW_CONTENT_KEY_TERMS = (
    "packet_payload", "raw_packet", "raw_evidence", "evidence_text", "raw_interview",
    "interview_text", "raw_text", "raw_content", "source_bytes", "file_bytes", "raw_source",
    "generated_output", "agent_output", "llm_output", "prompt_text", "payload",
)
# DB-URL / raw-SQL key terms (never persisted or accepted).
DB_ARTIFACT_KEY_TERMS = ("database_url", "db_url", "raw_sql", "sql_statement", "stack_trace",
                         "traceback")
# Disallowed-intent terms: approval / publication / execution / financial / client-facing.
APPROVAL_INTENT_TERMS = ("approve", "approval", "sign_off", "signoff", "final_approval")
PUBLICATION_INTENT_TERMS = ("publish", "capsule")
EXECUTION_INTENT_TERMS = ("execute", "run_agent", "mock_agent", "agent_execution", "llm_call")
FINANCIAL_INTENT_TERMS = ("verify_financial", "financial_verif")
CLIENT_FACING_INTENT_TERMS = ("client_facing", "create_report_for_client", "send_to_client",
                              "to_client")

# --- Value-safety markers (non-echoing) --------------------------------------------------
# Free-text-ish fields (safe_decision_summary, requested_followup_actions labels) may be carried
# into the decision draft/result, so they are pattern-scanned for obvious unsafe markers. Only the
# field name and the marker *category* are ever reported — never the offending value. This is
# marker/pattern matching, not semantic inspection.
_SECRET_VALUE_MARKERS = ("password", "secret", "api_key", "apikey", "token", "private_key",
                         "credential", "connection_string", "access_key")
_DB_URL_VALUE_MARKERS = ("database_url", "postgres://", "mysql://", "sqlite://", "mongodb://")
_RAW_SQL_VALUE_MARKERS = ("select *", "insert into", "delete from", "drop table", "alter table")
# UPDATE ... SET is matched by a tighter, whitespace-tolerant, case-insensitive pattern (not a bare
# "update " substring) so harmless notes like "please update the report" are not rejected.
_RAW_SQL_UPDATE_RE = re.compile(r"\bupdate\b\s+\S.*?\bset\b", re.IGNORECASE | re.DOTALL)
_RAW_CONTENT_VALUE_MARKERS = ("packet_payload", "raw_evidence_text", "raw_interview_text",
                              "source_bytes", "generated_output")
_JSON_KEYVALUE_RE = re.compile(r'"[^"\n]{1,64}"\s*:')


def classify_prohibited_value_marker(value: str) -> Optional[str]:
    """Return a marker *category* string if ``value`` carries an obvious unsafe marker, else None.

    **Public, DB-free classifier** — the supported cross-boundary interface for consumers (e.g. the
    Phase 33 DB writer) that must re-enforce this value-safety guard at their own boundary without
    reaching into a private helper. It opens no database connection and imports no ``peak.db``.

    Categories: 'credential/secret', 'DB-URL/DSN', 'raw-SQL', 'raw-content', 'JSON/object'. Only the
    category is returned — never the value — so nothing sensitive is echoed. No semantic inspection.
    """
    if not isinstance(value, str):
        return None
    low = value.lower()
    if any(t in low for t in _SECRET_VALUE_MARKERS):
        return "credential/secret"
    if any(t in low for t in _DB_URL_VALUE_MARKERS):
        return "DB-URL/DSN"
    if any(t in low for t in _RAW_SQL_VALUE_MARKERS) or _RAW_SQL_UPDATE_RE.search(value):
        return "raw-SQL"
    if any(t in low for t in _RAW_CONTENT_VALUE_MARKERS):
        return "raw-content"
    stripped = value.strip()
    if stripped.startswith("{") or stripped.startswith("["):
        return "JSON/object"
    if _JSON_KEYVALUE_RE.search(value):
        return "JSON/object"
    return None


# Backward-compatible private alias for Phase 32's own internal call sites. Delegates to the public
# classifier above — same behavior, same categories.
_value_marker_category = classify_prohibited_value_marker


@dataclass
class ReviewerDecisionGovernanceDecision:
    """Result of the pre-plan request-level governance checks."""

    permitted: bool = False
    reason_code: Optional[str] = None
    readiness_state: Optional[str] = None  # a blocked_* state hint when not permitted
    reasons: List[str] = field(default_factory=list)
    warnings: List[str] = field(default_factory=list)


def _is_blank(value) -> bool:
    return value is None or (isinstance(value, str) and not value.strip())


def _iter_keys(value):
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


def _ref_lists(request: InternalReviewerDecisionRequest):
    for name in ("review_plan_item_refs", "evidence_reference_ids", "source_ingestion_record_ids",
                 "agent_task_queue_record_ids", "requested_followup_actions"):
        yield name, list(getattr(request, name, None) or [])


def _label_ok(value, max_len) -> bool:
    """A short single-line safe label — no email/credential shape, no newline, bounded length."""
    if value is None:
        return True
    if not isinstance(value, str):
        return False
    if "@" in value or "\n" in value or "\r" in value or len(value) > max_len:
        return False
    low = value.lower()
    if any(t in low for t in SECRET_KEY_TERMS):
        return False
    return True


def scan_prohibited_content(
    request: InternalReviewerDecisionRequest,
) -> Tuple[Optional[str], List[str]]:
    """Return (readiness_state, reasons) for any prohibited content, or (None, []).

    Reports **key names / field names only** — never values — so no secret or raw content is
    echoed. Also rejects non-string / over-long / multiline ref-and-label entries.
    """
    keys = _all_keys(request)
    context = getattr(request, "context", None)
    if isinstance(context, dict):
        keys += _all_keys(context)
    low = [k.lower() for k in keys]

    def _hit(terms):
        return sorted({k for k, lk in zip(keys, low) if any(t in lk for t in terms)})

    if _hit(SECRET_KEY_TERMS):
        return BLOCKED_SECRET_LIKE_CONTENT, [
            "request contains prohibited credential/secret key(s): " + ", ".join(_hit(SECRET_KEY_TERMS))]
    if _hit(RAW_CONTENT_KEY_TERMS):
        return BLOCKED_RAW_CONTENT, [
            "request contains prohibited raw-content key(s): " + ", ".join(_hit(RAW_CONTENT_KEY_TERMS))]
    if _hit(DB_ARTIFACT_KEY_TERMS):
        return BLOCKED_RAW_CONTENT, [
            "request contains prohibited DB-URL/raw-SQL/stack-trace key(s): "
            + ", ".join(_hit(DB_ARTIFACT_KEY_TERMS))]

    # Ref/label values must be short single-line strings (ids/labels), not arbitrary content.
    for field_name, values in _ref_lists(request):
        for i, v in enumerate(values):
            if not isinstance(v, str):
                return BLOCKED_RAW_CONTENT, [
                    f"{field_name}[{i}] is not a string reference/label (arbitrary content rejected)"]
            if "\n" in v or "\r" in v or len(v) > _MAX_REF_LEN:
                return BLOCKED_RAW_CONTENT, [
                    f"{field_name}[{i}] looks like raw content, not a short reference/label"]
    for name in ("review_bundle_ref", "review_bundle_record_id", "review_bundle_draft_ref"):
        v = getattr(request, name, None)
        if isinstance(v, str) and ("\n" in v or len(v) > _MAX_REF_LEN):
            return BLOCKED_RAW_CONTENT, [f"{name} looks like raw content, not a short reference"]
    summary = getattr(request, "safe_decision_summary", None)
    if isinstance(summary, str) and ("\n" in summary or "\r" in summary or len(summary) > _MAX_SUMMARY_LEN):
        return BLOCKED_RAW_CONTENT, [
            "safe_decision_summary must be a short single-line note, not raw content"]

    # Value-safety guard (non-echoing): summary + followup labels must carry no unsafe markers.
    if isinstance(summary, str):
        cat = _value_marker_category(summary)
        if cat is not None:
            state = BLOCKED_SECRET_LIKE_CONTENT if cat == "credential/secret" else BLOCKED_RAW_CONTENT
            return state, [f"safe_decision_summary contains a prohibited {cat} marker"]
    for i, lbl in enumerate(getattr(request, "requested_followup_actions", None) or []):
        cat = _value_marker_category(lbl) if isinstance(lbl, str) else None
        if cat is not None:
            state = BLOCKED_SECRET_LIKE_CONTENT if cat == "credential/secret" else BLOCKED_RAW_CONTENT
            return state, [f"requested_followup_actions[{i}] contains a prohibited {cat} marker"]
    return None, []


def _disallowed_intent_state(intent) -> Optional[str]:
    """Return BLOCKED_DISALLOWED_INTENT if the intent implies approval/publication/execution/
    financial/client-facing, else None."""
    low = str(intent).lower()
    groups = (APPROVAL_INTENT_TERMS, PUBLICATION_INTENT_TERMS, EXECUTION_INTENT_TERMS,
              FINANCIAL_INTENT_TERMS, CLIENT_FACING_INTENT_TERMS)
    if any(t in low for group in groups for t in group):
        return BLOCKED_DISALLOWED_INTENT
    return None


def subject_identity_mismatches(request: InternalReviewerDecisionRequest) -> List[str]:
    """Compare any structured refs (in ``context['subject_refs']``) against the request.

    Plain id-list entries carry no identity and are trusted as belonging to the request's scope.
    Structured refs — if present — must match owner/client/engagement and authorization_scope.
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


def evaluate_internal_reviewer_decision_request(
    request: InternalReviewerDecisionRequest,
) -> ReviewerDecisionGovernanceDecision:
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
    elif action not in ALLOWED_DECISION_ACTIONS:
        reasons.append(f"requested_action '{action}' is not one of {sorted(ALLOWED_DECISION_ACTIONS)}")

    # Review bundle reference (either ref or record id) is required.
    if _is_blank(getattr(request, "review_bundle_ref", None)) and _is_blank(
        getattr(request, "review_bundle_record_id", None)
    ):
        return ReviewerDecisionGovernanceDecision(
            permitted=False, reason_code="reviewer_decision_denied",
            readiness_state=BLOCKED_MISSING_REVIEW_BUNDLE,
            reasons=["review_bundle_ref or review_bundle_record_id is required"])

    if not _label_ok(getattr(request, "reviewer_role", None), _MAX_LABEL_LEN) or _is_blank(
        getattr(request, "reviewer_role", None)
    ):
        return ReviewerDecisionGovernanceDecision(
            permitted=False, reason_code="reviewer_decision_denied",
            readiness_state=BLOCKED_SECRET_LIKE_CONTENT,
            reasons=["reviewer_role must be a short safe role label "
                     "(no email/credential/PII-like value)"])
    if not _label_ok(getattr(request, "decision_reason_code", None), _MAX_LABEL_LEN) or _is_blank(
        getattr(request, "decision_reason_code", None)
    ):
        reasons.append("decision_reason_code must be a short safe reason code")
    for i, lbl in enumerate(getattr(request, "requested_followup_actions", None) or []):
        if not _label_ok(lbl, _MAX_LABEL_LEN):
            reasons.append(f"requested_followup_actions[{i}] must be a short safe label")

    lifecycle = getattr(request, "lifecycle_status", None)
    if lifecycle in BLOCKED_LIFECYCLE_STATUSES:
        return ReviewerDecisionGovernanceDecision(
            permitted=False, reason_code="reviewer_decision_denied",
            readiness_state=BLOCKED_LIFECYCLE,
            reasons=[f"lifecycle_status '{lifecycle}' is not permitted "
                     "(must not be revoked, archived, or deleted_reference_only)"])

    # Decision intent: allowed set only. A disallowed (approval/publication/execution/financial/
    # client-facing) intent is denied with a specific readiness state.
    intent = getattr(request, "decision_intent", None)
    if _is_blank(intent):
        reasons.append("decision_intent is required")
    elif intent not in ALLOWED_DECISION_INTENTS:
        state = _disallowed_intent_state(intent) or BLOCKED_UNSUPPORTED_INTENT
        return ReviewerDecisionGovernanceDecision(
            permitted=False, reason_code="reviewer_decision_denied", readiness_state=state,
            reasons=[f"decision_intent '{intent}' is not an allowed internal-review intent"])

    # return_to_stage, if supplied, must be a safe known stage.
    rts = getattr(request, "return_to_stage", None)
    if not _is_blank(rts) and rts not in ALLOWED_RETURN_STAGES:
        reasons.append(f"return_to_stage '{rts}' is not one of {sorted(ALLOWED_RETURN_STAGES)}")

    # Prohibited content (secret / raw / DB-artifact) + ref/label shape.
    state, content_reasons = scan_prohibited_content(request)
    if state is not None:
        return ReviewerDecisionGovernanceDecision(
            permitted=False, reason_code="reviewer_decision_denied",
            readiness_state=state, reasons=content_reasons)

    # Structured subject-reference identity/scope (necessary but not sufficient).
    mismatches = subject_identity_mismatches(request)
    if mismatches:
        return ReviewerDecisionGovernanceDecision(
            permitted=False, reason_code="reviewer_decision_denied",
            readiness_state=BLOCKED_INVALID_SCOPE, reasons=mismatches)

    if reasons:
        return ReviewerDecisionGovernanceDecision(
            permitted=False, reason_code="reviewer_decision_denied",
            readiness_state=BLOCKED_INVALID_SCOPE, reasons=reasons)
    return ReviewerDecisionGovernanceDecision(permitted=True)
