"""Deterministic governance guards for the Internal Assessment Report Planning Boundary (Phase 36).

Run *before* any plan is assembled. Request-level checks enforce that a report-planning request is
authorized and scoped, names a plan id, targets **supported internal sections only**, keeps an
**internal** audience, carries **no elevated posture**, and carries **no raw packet/intake/evidence/
interview/source content, no credential/secret/DB-URL/raw-SQL/stack-trace fields, and no approval /
publication / execution / financial / client-facing intent**.

**Critical scope rule:** the request's ``authorization_scope`` must be present, and any structured
reference that carries owner/client/engagement/scope must match the request. Owner/client/
engagement matching is necessary but **not sufficient**; scope must match too. Cross-tenant and
cross-engagement references are denied before they can reach a plan.

Denials report **field names, reference positions, and marker categories only** — never the
offending value — so nothing sensitive is echoed.

This module is **stdlib-only** apart from the public, DB-free Phase 32 value classifier. It imports
no SQLAlchemy, Alembic, ``peak.db``, DB writer, live/mock LLM, AgentNet/MCP/resolver/connector, or
network module.

See docs/INTERNAL_REPORT_ASSEMBLY_GOVERNANCE_POLICY.md.
"""

from __future__ import annotations

import re
from dataclasses import dataclass, field
from typing import List, Optional, Tuple

# Public, DB-free Phase 32 value classifier (returns a marker *category*, never the value).
from peak.reviewer_decisions.governance import classify_prohibited_value_marker

from .contracts import (
    ALLOWED_AUDIENCES,
    ALLOWED_REPORT_ACTIONS,
    BLOCKED_DISALLOWED_INTENT,
    BLOCKED_DISALLOWED_POSTURE,
    BLOCKED_DUPLICATE_SECTION,
    BLOCKED_INVALID_SCOPE,
    BLOCKED_LIFECYCLE,
    BLOCKED_MISSING_IDENTITY,
    BLOCKED_MISSING_PLAN_ID,
    BLOCKED_RAW_CONTENT,
    BLOCKED_REFERENCE_IDENTITY,
    BLOCKED_SECRET_LIKE_CONTENT,
    BLOCKED_UNSUPPORTED_AUDIENCE,
    BLOCKED_UNSUPPORTED_SECTION,
    REF_CATEGORIES,
    SUPPORTED_SECTION_IDS,
    GovernedRecordReference,
    InternalAssessmentReportPlanRequest,
    InternalReportPlanningValidationResult,
)

REVOKED_AUTHORIZATION_SCOPE = "revoked"
BLOCKED_LIFECYCLE_STATUSES = frozenset({"revoked", "archived", "deleted_reference_only"})

_MAX_ID_LEN = 128
_MAX_REF_LEN = 128     # a safe id/ref is short; longer/multiline values look like raw content
_MAX_LABEL_LEN = 64    # role labels and section ids are short
_MAX_PURPOSE_LEN = 240  # report_purpose is a short single-line internal label

#: A safe short ref/id: no whitespace, no newlines, no quotes, bounded length.
SAFE_REF_RE = re.compile(r"^[A-Za-z0-9_.:/\-]{1,128}$")

# --- Prohibited key terms (scanned on *unexpected* attributes and context keys) -------------
SECRET_KEY_TERMS = (
    "password", "passwd", "secret", "api_key", "apikey", "token", "private_key", "privatekey",
    "credential", "credentials", "connection_string", "access_key", "resolver_credentials",
)
RAW_CONTENT_KEY_TERMS = (
    "note_text", "raw_note_text", "packet_payload", "raw_packet", "raw_evidence", "evidence_text",
    "raw_evidence_text", "raw_interview", "interview_text", "raw_interview_text", "raw_text",
    "raw_content", "source_bytes", "file_bytes", "raw_source", "generated_output", "agent_output",
    "llm_output", "llm_prompt", "prompt_text",
)
DB_ARTIFACT_KEY_TERMS = (
    "database_url", "db_url", "dsn", "raw_sql", "sql_statement", "stack_trace", "traceback",
)
# Approval / publication / execution / financial / client-facing intent, by key name.
DISALLOWED_INTENT_KEY_TERMS = (
    "final_client_report", "client_facing_output", "client_report", "approval_decision",
    "approve_internal", "approve_client_facing", "sign_off", "signoff", "publish_capsule",
    "agentnet_publish", "publish_report", "send_to_client", "to_client",
    "export_client_deliverable", "verify_financial", "financial_verif", "roi_verified",
    "savings_verified",
)

#: A stack trace is not caught by the Phase 32 value classifier, so it is matched here directly.
_STACKTRACE_RE = re.compile(
    r"traceback \(most recent call last\)|File \"[^\"]+\", line \d+", re.IGNORECASE)

#: Posture flags that must stay at their safe default on the request.
REQUIRED_FALSE_POSTURE_FLAGS = (
    "client_facing_approved", "financial_verified", "capsule_candidate_ready",
    "publication_allowed", "execution_allowed",
)
REQUIRED_TRUE_POSTURE_FLAGS = ("requires_human_review",)

REQUIRED_IDENTITY_FIELDS = ("owner_id", "client_id", "engagement_id", "authorization_scope",
                            "requested_by", "requester_role")


@dataclass
class ReportPlanningGovernanceDecision:
    """Result of the DB-free request-level governance checks (no side effects)."""

    permitted: bool = False
    reason_code: Optional[str] = None
    blocked_state: Optional[str] = None
    validation: Optional[InternalReportPlanningValidationResult] = None
    reasons: List[str] = field(default_factory=list)
    warnings: List[str] = field(default_factory=list)


def _is_blank(value) -> bool:
    return value is None or (isinstance(value, str) and not value.strip())


def _safe_name(name) -> str:
    """Render a caller-supplied key without echoing an arbitrary value."""
    if isinstance(name, str) and re.match(r"^[A-Za-z0-9_.\-]{1,64}$", name):
        return name
    return "<unsafe-field-name>"


def _iter_nested_keys(value) -> List[str]:
    keys: List[str] = []
    if isinstance(value, dict):
        for key, val in value.items():
            if isinstance(key, str):
                keys.append(key)
            keys.extend(_iter_nested_keys(val))
    elif isinstance(value, (list, tuple)):
        for item in value:
            keys.extend(_iter_nested_keys(item))
    return keys


def _unexpected_attr_names(request) -> List[str]:
    """Attribute names the caller bolted onto the request beyond its declared fields.

    Declared fields are known-safe posture/identity/reference fields whose *values* are validated
    explicitly elsewhere, so only unexpected attributes are name-scanned. This is what stops a
    smuggled ``note_text`` / ``database_url`` / ``approve_client_facing`` attribute.
    """
    declared = set(getattr(type(request), "__dataclass_fields__", {}))
    own = getattr(request, "__dict__", None) or {}
    return [k for k in own if isinstance(k, str) and k not in declared]


def classify_value(value: str) -> Optional[str]:
    """Return a marker *category* for an unsafe value, or ``None``. Never returns the value."""
    if not isinstance(value, str):
        return None
    if _STACKTRACE_RE.search(value):
        return "stack-trace"
    return classify_prohibited_value_marker(value)


def scan_prohibited_content(request) -> Tuple[Optional[str], List[str]]:
    """Return ``(blocked_state, reasons)`` for any prohibited key or value, or ``(None, [])``.

    Reports **key names / field names / marker categories only** — never values.
    """
    names = _unexpected_attr_names(request)
    context = getattr(request, "context", None)
    if isinstance(context, dict):
        names += _iter_nested_keys(context)
    low = [n.lower() for n in names]

    def _hit(terms):
        return sorted({_safe_name(n) for n, ln in zip(names, low) if any(t in ln for t in terms)})

    for terms, state, label in (
        (SECRET_KEY_TERMS, BLOCKED_SECRET_LIKE_CONTENT, "credential/secret"),
        (RAW_CONTENT_KEY_TERMS, BLOCKED_RAW_CONTENT, "raw-content"),
        (DB_ARTIFACT_KEY_TERMS, BLOCKED_RAW_CONTENT, "DB-URL/raw-SQL/stack-trace"),
        (DISALLOWED_INTENT_KEY_TERMS, BLOCKED_DISALLOWED_INTENT,
         "approval/publication/execution/financial/client-facing intent"),
    ):
        hits = _hit(terms)
        if hits:
            return state, [f"request contains prohibited {label} key(s): " + ", ".join(hits)]

    # Reference values must be short, single-line, safe ids — not arbitrary content.
    for category, values in _iter_reference_values(request):
        for index, value in values:
            if not isinstance(value, str):
                return BLOCKED_RAW_CONTENT, [
                    f"{category}[{index}] is not a string reference (arbitrary content rejected)"]
            if "\n" in value or "\r" in value or len(value) > _MAX_REF_LEN:
                return BLOCKED_RAW_CONTENT, [
                    f"{category}[{index}] looks like raw content, not a short reference"]
            if not SAFE_REF_RE.match(value):
                return BLOCKED_RAW_CONTENT, [
                    f"{category}[{index}] is not a safe short reference (value not echoed)"]
            marker = classify_value(value)
            if marker is not None:
                return BLOCKED_RAW_CONTENT, [
                    f"{category}[{index}] carries a {marker} marker (value not echoed)"]

    # Short scalar labels/refs.
    for name, max_len in (("report_plan_id", _MAX_ID_LEN), ("idempotency_key", _MAX_ID_LEN),
                          ("workflow_id", _MAX_ID_LEN),
                          ("managed_record_workflow_ref", _MAX_REF_LEN),
                          ("requested_by", _MAX_LABEL_LEN), ("requester_role", _MAX_LABEL_LEN),
                          ("report_purpose", _MAX_PURPOSE_LEN)):
        value = getattr(request, name, None)
        if value is None:
            continue
        if not isinstance(value, str):
            return BLOCKED_RAW_CONTENT, [f"{name} must be a short safe string"]
        if "\n" in value or "\r" in value or len(value) > max_len:
            return BLOCKED_RAW_CONTENT, [
                f"{name} must be a short single-line label, not raw content"]
        marker = classify_value(value)
        if marker is not None:
            return BLOCKED_RAW_CONTENT, [
                f"{name} carries a {marker} marker (value not echoed)"]

    return None, []


def _iter_reference_values(request):
    """Yield ``(category, [(index, record_id), ...])`` across every reference category.

    Accepts plain string ids and :class:`GovernedRecordReference` objects alike.
    """
    for category in REF_CATEGORIES:
        entries = []
        for index, item in enumerate(list(getattr(request, category, None) or [])):
            if isinstance(item, GovernedRecordReference):
                entries.append((index, item.record_id))
            else:
                entries.append((index, item))
        yield category, entries


def reference_identity_mismatches(request) -> List[str]:
    """Compare every structured reference's tenant/engagement/scope against the request.

    Returns human-readable mismatch descriptions (field names and category/index only, never
    values). Necessary but **not sufficient**: the durable records themselves were written under
    their own stored-``Engagement`` authorization by the earlier phases.
    """
    mismatches: List[str] = []
    for category in REF_CATEGORIES:
        for index, item in enumerate(list(getattr(request, category, None) or [])):
            if not isinstance(item, GovernedRecordReference):
                continue
            for attr in ("owner_id", "client_id", "engagement_id"):
                value = getattr(item, attr, None)
                if value is not None and value != getattr(request, attr, None):
                    mismatches.append(
                        f"{category}[{index}].{attr} does not match the request {attr}")
            scope = getattr(item, "authorization_scope", None)
            if scope is not None and scope != getattr(request, "authorization_scope", None):
                mismatches.append(
                    f"{category}[{index}].authorization_scope does not match the request "
                    "authorization_scope")
            record_type = getattr(item, "record_type", None)
            if record_type is not None and not SAFE_REF_RE.match(str(record_type)):
                mismatches.append(f"{category}[{index}].record_type is not a safe short label")
    return mismatches


def evaluate_internal_assessment_report_plan_request(
    request,
) -> ReportPlanningGovernanceDecision:
    """Validate a report-planning request. Returns a typed decision; raises nothing expected."""
    validation = InternalReportPlanningValidationResult()

    def deny(reason_code, blocked_state, message):
        validation.blocked_state = blocked_state
        validation.reasons.append(message)
        return ReportPlanningGovernanceDecision(
            permitted=False, reason_code=reason_code, blocked_state=blocked_state,
            validation=validation, reasons=[message])

    # 1. Concrete request type (reject duck-typed objects at the boundary).
    if not isinstance(request, InternalAssessmentReportPlanRequest):
        return deny("invalid_request_type", BLOCKED_RAW_CONTENT,
                    "request is not an InternalAssessmentReportPlanRequest")

    # 2. Requested action.
    action = getattr(request, "requested_action", None)
    if action is not None and action not in ALLOWED_REPORT_ACTIONS:
        return deny("unsupported_action", BLOCKED_DISALLOWED_INTENT,
                    "requested_action is not 'prepare_internal_assessment_report_plan'")

    # 3. Required identity / traceability.
    for attr in REQUIRED_IDENTITY_FIELDS:
        value = getattr(request, attr, None)
        if _is_blank(value):
            return deny("missing_identity_field", BLOCKED_MISSING_IDENTITY,
                        f"request.{attr} is required")
        if not isinstance(value, str) or len(value) > _MAX_ID_LEN:
            return deny("invalid_identity_field", BLOCKED_MISSING_IDENTITY,
                        f"request.{attr} must be a string of at most {_MAX_ID_LEN} characters")
    validation.identity_valid = True

    # 4. Scope must be present and not revoked.
    if request.authorization_scope == REVOKED_AUTHORIZATION_SCOPE:
        return deny("blocked_authorization_scope", BLOCKED_INVALID_SCOPE,
                    "authorization_scope 'revoked' is not permitted")
    validation.scope_valid = True

    # 5. Lifecycle status, when supplied, must not be a blocked one.
    lifecycle = getattr(request, "lifecycle_status", None)
    if lifecycle in BLOCKED_LIFECYCLE_STATUSES:
        return deny("blocked_lifecycle_status", BLOCKED_LIFECYCLE,
                    f"lifecycle_status '{_safe_name(lifecycle)}' is not permitted")

    # 6. Plan identity — report_plan_id or idempotency_key.
    if _is_blank(request.report_plan_id) and _is_blank(request.idempotency_key):
        return deny("missing_report_plan_id", BLOCKED_MISSING_PLAN_ID,
                    "one of report_plan_id / idempotency_key is required")
    for name in ("report_plan_id", "idempotency_key"):
        value = getattr(request, name, None)
        if value is not None and not _is_blank(value) and not SAFE_REF_RE.match(str(value)):
            return deny("invalid_report_plan_id", BLOCKED_MISSING_PLAN_ID,
                        f"{name} must be a short safe identifier")
    validation.plan_id_valid = True

    # 7. Audience must be internal.
    if request.audience not in ALLOWED_AUDIENCES:
        return deny("unsupported_audience", BLOCKED_UNSUPPORTED_AUDIENCE,
                    "audience must be 'internal' (this boundary produces no client-facing output)")
    validation.audience_valid = True

    # 8. Posture flags must stay at their safe defaults.
    for flag in REQUIRED_FALSE_POSTURE_FLAGS:
        if getattr(request, flag, False) is not False:
            return deny("prohibited_posture", BLOCKED_DISALLOWED_POSTURE,
                        f"request.{flag} must be false (this boundary approves, verifies, "
                        "publishes, and executes nothing)")
    for flag in REQUIRED_TRUE_POSTURE_FLAGS:
        if getattr(request, flag, True) is not True:
            return deny("prohibited_posture", BLOCKED_DISALLOWED_POSTURE,
                        f"request.{flag} must be true (an internal report plan always requires "
                        "human review)")
    validation.posture_valid = True

    # 9. Requested sections: supported, non-duplicated.
    requested = list(getattr(request, "requested_sections", None) or [])
    seen = set()
    for section in requested:
        if not isinstance(section, str) or section not in SUPPORTED_SECTION_IDS:
            return deny("unsupported_section", BLOCKED_UNSUPPORTED_SECTION,
                        f"requested section '{_safe_name(section)}' is not a supported internal "
                        "report section")
        if section in seen:
            return deny("duplicate_section", BLOCKED_DUPLICATE_SECTION,
                        f"requested section '{_safe_name(section)}' is listed more than once")
        seen.add(section)
    validation.sections_valid = True

    # 10. Prohibited keys / values (never echoing a value).
    blocked_state, reasons = scan_prohibited_content(request)
    if blocked_state is not None:
        validation.contains_prohibited_content = True
        return deny("prohibited_content", blocked_state, reasons[0])

    # 11. Structured reference identity / scope consistency.
    mismatches = reference_identity_mismatches(request)
    if mismatches:
        return deny("reference_identity_mismatch", BLOCKED_REFERENCE_IDENTITY,
                    "; ".join(mismatches))
    validation.references_valid = True

    # 12. At least one governed reference, unless a skeletal plan is explicitly allowed.
    total_refs = sum(len(list(getattr(request, c, None) or [])) for c in REF_CATEGORIES)
    validation.has_any_reference = total_refs > 0
    warnings: List[str] = []
    if total_refs == 0:
        if not getattr(request, "allow_empty_reference_plan", False):
            return deny("no_governed_references", BLOCKED_REFERENCE_IDENTITY,
                        "at least one governed record reference is required; set "
                        "allow_empty_reference_plan=True for a skeletal plan")
        warnings.append(
            "skeletal plan: no governed record references were supplied, so every section is "
            "unsupported and every required category is an open gap")

    validation.permitted = True
    validation.warnings.extend(warnings)
    return ReportPlanningGovernanceDecision(
        permitted=True, validation=validation, warnings=warnings)
