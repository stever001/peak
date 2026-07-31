"""Controlled DB writer for internal assessment report drafts (Phase 37).

The **ninth** narrow live DB writer and the persistence counterpart to the Phase 36 DB-free
internal assessment report planning boundary. It persists **exactly one**
``internal_assessment_report_drafts`` row from a Phase 36 :class:`InternalAssessmentReportPlan`,
through the Phase 17 ``ControlledWriteRequest`` boundary, allowing only
``internal_assessment_report_drafts`` / ``create_internal_assessment_report_draft``.

**What is stored is a persisted *plan*, not a drafted report.** The row holds section metadata,
reference-only evidence traces, finding/recommendation candidate slots, open gaps, blocked items,
and future-gate placeholders. ``output_status`` is fixed at ``plan_persisted`` precisely so a stored
row can never be misread as report prose.

**What is never stored or echoed:** final client-facing language, raw intake-note / packet /
evidence / interview text, source bytes, generated agent output, LLM prompts, credentials or
secrets, DSNs, raw SQL, stack traces, approval decisions, ROI or savings figures, capsule payloads,
and AgentNet publish payloads. Denial reasons report only a field name, a reference position, or a
marker *category* — never the offending value.

Write-time authorization loads the **stored** ``Engagement`` and compares its stored
``authorization_scope``. Identity matching is necessary but **not sufficient**, and the Phase 36
plan/request is never trusted as the authorization source.

This writer approves nothing, verifies nothing financially, publishes nothing, executes nothing,
calls no Phase 22 review writer, creates no ``review_records`` / ``agent_run_records`` row, and
makes no LLM / MockLLM / agent / AgentNet / MCP / resolver / connector / network call.

See docs/INTERNAL_ASSESSMENT_REPORT_DRAFT_CONTROLLED_WRITER.md and
docs/INTERNAL_ASSESSMENT_REPORT_DRAFT_IDEMPOTENCY_POLICY.md.
"""

from __future__ import annotations

import hashlib
import json
import re
import uuid
from typing import List, Optional, Tuple

from sqlalchemy.exc import IntegrityError, SQLAlchemyError

from peak.persistence.contracts import ControlledWriteRequest, ControlledWriteSubject
from peak.persistence.write_plan import prepare_controlled_write
# DB-free Phase 36 plan contract + the public Phase 32 value classifier (neither imports peak.db).
from peak.reports.contracts import AUDIENCE_INTERNAL, InternalAssessmentReportPlan
from peak.reviewer_decisions.governance import classify_prohibited_value_marker

from .models import Engagement, InternalAssessmentReportDraftRecord
from .session import create_session_factory
from .writer_contracts import (
    INTERNAL_ASSESSMENT_REPORT_DRAFT_TARGET_ACTION,
    INTERNAL_ASSESSMENT_REPORT_DRAFT_TARGET_TABLE,
    InternalAssessmentReportDraftWriteOutcome,
    InternalAssessmentReportDraftWriteReceipt,
)

BLOCKED_LIFECYCLE_STATUSES = frozenset({"revoked", "archived", "deleted_reference_only"})
SUPPORTED_SUBJECT_TYPES = frozenset({"engagement"})

# The exact stored posture. "plan_persisted" is the documented, deliberate choice: a row is a
# persisted Phase 36 plan, never a drafted report (docs/INTERNAL_ASSESSMENT_REPORT_DRAFT_CONTROLLED_WRITER.md).
STORED_OUTPUT_STATUS = "plan_persisted"
REQUIRED_REVIEW_STATUS = "needs_review"
REQUIRED_LIFECYCLE_STATUS = "draft"
REQUIRED_PLAN_OUTPUT_STATUS = "plan"  # the Phase 36 plan's own fixed value

# Bounds (documented in docs/INTERNAL_ASSESSMENT_REPORT_DRAFT_CONTROLLED_WRITER.md).
MAX_REF_LEN = 128
MAX_LABEL_LEN = 64
MAX_PURPOSE_LEN = 240
MAX_REASON_LEN = 500
MAX_SECTIONS = 64
MAX_CANDIDATES = 500
MAX_GAPS = 500
MAX_REFS_PER_FIELD = 2000
_ID_PREFIX = "iard_"

# Posture flags that must be false on the plan and are hard-coded false on the stored row.
REQUIRED_FALSE_PLAN_FLAGS = (
    "client_facing_approved", "financial_verified", "capsule_candidate_ready",
    "publication_allowed", "execution_allowed",
)

#: Prohibited attribute-name markers. Only *unexpected* attributes (anything the caller bolted onto
#: the plan beyond its declared dataclass fields) are name-scanned; declared fields are known-safe
#: structural fields whose values are validated explicitly below.
PROHIBITED_KEY_MARKERS = (
    "note_text", "raw_note_text", "packet_payload", "raw_packet", "raw_evidence", "evidence_text",
    "raw_evidence_text", "raw_interview", "interview_text", "raw_interview_text", "raw_text",
    "raw_content", "source_bytes", "file_bytes", "raw_source", "generated_output", "agent_output",
    "llm_output", "llm_prompt", "prompt_text",
    "database_url", "db_url", "dsn", "connection_string", "raw_sql", "sql_statement",
    "stack_trace", "traceback",
    "final_client_report", "client_facing_output", "client_report", "approval_decision",
    "approve_internal", "approve_client_facing", "sign_off", "signoff", "publish_capsule",
    "agentnet_publish", "publish_report", "send_to_client", "to_client",
    "export_client_deliverable", "verify_financial", "financial_verif", "roi_verified",
    "savings_verified", "resolver_credentials",
    "password", "passwd", "secret", "api_key", "apikey", "token", "private_key", "privatekey",
    "credential", "credentials", "access_key",
)

#: A safe short ref/id: no whitespace, no newlines, no quotes, bounded length.
_SAFE_REF_RE = re.compile(r"^[A-Za-z0-9_.:/\-]{1,128}$")
#: A stack trace is not caught by the Phase 32 value classifier, so it is matched here directly.
_STACKTRACE_RE = re.compile(
    r"traceback \(most recent call last\)|File \"[^\"]+\", line \d+", re.IGNORECASE)
#: Structural JSON-dump shapes (the Phase 32 classifier reports 'JSON/object' for any merely
#: bracket-prefixed value, which legitimately fires on worker-generated titles like
#: "[draft] visual_observation"). Narrowed to values that really look like a dumped object/array.
_JSON_KEYVALUE_RE = re.compile(r'"[^"\n]{1,64}"\s*:')


def _is_blank(value) -> bool:
    return value is None or (isinstance(value, str) and not value.strip())


def _deny(reason_code: str, message: str,
          **flags) -> InternalAssessmentReportDraftWriteReceipt:
    receipt = InternalAssessmentReportDraftWriteReceipt(
        outcome=InternalAssessmentReportDraftWriteOutcome.DENIED, permitted=False,
        reason_code=reason_code, reasons=[message])
    for key, val in flags.items():
        setattr(receipt, key, val)
    return receipt


def _looks_like_json_dump(value: str) -> bool:
    stripped = value.strip()
    if _JSON_KEYVALUE_RE.search(value):
        return True
    return ((stripped.startswith("{") and stripped.endswith("}"))
            or (stripped.startswith("[") and stripped.endswith("]")))


def _value_marker(value, *, strict_json: bool = True) -> Optional[str]:
    """Return a marker *category* for an unsafe value, or ``None``. Never returns the value."""
    if not isinstance(value, str):
        return None
    if _STACKTRACE_RE.search(value):
        return "stack-trace"
    category = classify_prohibited_value_marker(value)
    if category == "JSON/object" and not strict_json and not _looks_like_json_dump(value):
        return None
    return category


def _safe_name(name) -> str:
    if isinstance(name, str) and re.match(r"^[A-Za-z0-9_.\-]{1,64}$", name):
        return name
    return "<unsafe-field-name>"


def _ref_ok(value) -> bool:
    return isinstance(value, str) and bool(_SAFE_REF_RE.match(value))


def _safe_str_list(values, limit: int = MAX_REFS_PER_FIELD) -> List[str]:
    return [v for v in (values or []) if isinstance(v, str) and v.strip()][:limit]


def _label_ok(value, max_len: int) -> bool:
    """A short single-line safe label — no newline, no marker, bounded length."""
    if value is None:
        return True
    if not isinstance(value, str):
        return False
    if "\n" in value or "\r" in value or len(value) > max_len:
        return False
    return _value_marker(value, strict_json=False) is None


# --------------------------------------------------------------------------- plan safety


def _unexpected_attr_names(plan) -> List[str]:
    declared = set(getattr(type(plan), "__dataclass_fields__", {}))
    own = getattr(plan, "__dict__", None) or {}
    return [k for k in own if isinstance(k, str) and k not in declared]


def _plan_key_denial(plan) -> Optional[Tuple[str, str]]:
    """Deny any *unexpected* plan attribute whose name looks like raw content / a secret / intent."""
    for name in sorted(_unexpected_attr_names(plan)):
        low = name.lower()
        if any(marker in low for marker in PROHIBITED_KEY_MARKERS):
            return ("prohibited_plan_key",
                    f"plan carries a prohibited attribute '{_safe_name(name)}'")
    return None


def _iter_plan_ref_strings(plan):
    """Yield ``(field_label, value)`` for every reference/label string carried by the plan.

    Walks the structural payload the writer will persist, so an unsafe value cannot be smuggled
    into a JSON column through a nested section / trace / candidate / gap object.
    """
    for index, section in enumerate(plan.sections or []):
        base = f"sections[{index}]"
        yield f"{base}.section_id", getattr(section, "section_id", None)
        yield f"{base}.readiness_state", getattr(section, "readiness_state", None)
        for cat_field in ("required_ref_categories", "satisfied_ref_categories",
                          "missing_ref_categories"):
            for j, cat in enumerate(getattr(section, cat_field, None) or []):
                yield f"{base}.{cat_field}[{j}]", cat
    for section_id, trace in (plan.evidence_trace_map or {}).items():
        base = f"evidence_trace_map[{_safe_name(section_id)}]"
        yield f"{base}.section_id", getattr(trace, "section_id", None)
        for category, refs in (getattr(trace, "supporting_refs", None) or {}).items():
            for j, ref in enumerate(refs or []):
                yield f"{base}.supporting_refs.{_safe_name(category)}[{j}]", ref
        for j, cat in enumerate(getattr(trace, "missing_categories", None) or []):
            yield f"{base}.missing_categories[{j}]", cat
    for index, finding in enumerate(plan.finding_candidates or []):
        base = f"finding_candidates[{index}]"
        yield f"{base}.finding_candidate_id", getattr(finding, "finding_candidate_id", None)
        yield f"{base}.section_id", getattr(finding, "section_id", None)
        yield f"{base}.readiness_state", getattr(finding, "readiness_state", None)
        for field_name in ("evidence_support_refs", "review_support_refs"):
            for j, ref in enumerate(getattr(finding, field_name, None) or []):
                yield f"{base}.{field_name}[{j}]", ref
    for index, rec in enumerate(plan.recommendation_candidates or []):
        base = f"recommendation_candidates[{index}]"
        yield f"{base}.recommendation_candidate_id", getattr(
            rec, "recommendation_candidate_id", None)
        yield f"{base}.section_id", getattr(rec, "section_id", None)
        yield f"{base}.readiness_state", getattr(rec, "readiness_state", None)
        yield f"{base}.audience", getattr(rec, "audience", None)
        for field_name in ("reviewer_decision_refs", "review_support_refs",
                           "evidence_support_refs"):
            for j, ref in enumerate(getattr(rec, field_name, None) or []):
                yield f"{base}.{field_name}[{j}]", ref
    for index, gap in enumerate(plan.open_gaps or []):
        base = f"open_gaps[{index}]"
        yield f"{base}.gap_id", getattr(gap, "gap_id", None)
        yield f"{base}.gap_kind", getattr(gap, "gap_kind", None)
        yield f"{base}.section_id", getattr(gap, "section_id", None)
        yield f"{base}.missing_ref_category", getattr(gap, "missing_ref_category", None)
        yield f"{base}.missing_record_type", getattr(gap, "missing_record_type", None)
    for field_name in ("blocked_items", "future_financial_verification_items",
                       "future_capsule_candidate_items"):
        for j, item in enumerate(getattr(plan, field_name, None) or []):
            yield f"{field_name}[{j}]", item


def _plan_content_denial(plan) -> Optional[Tuple[str, str]]:
    """Verify every persisted reference/label is a short safe id and carries no unsafe marker."""
    for label, value in _iter_plan_ref_strings(plan):
        if value is None:
            continue
        if not _ref_ok(value):
            return ("unsafe_plan_reference",
                    f"plan {label} is not a short safe reference/label (value not echoed)")
        marker = _value_marker(value)
        if marker is not None:
            return ("prohibited_plan_value",
                    f"plan {label} carries a {marker} marker (value not echoed)")
    # Free-text-ish plan fields (fixed section titles, gap notes, blocked reasons, reasons /
    # warnings) are bounded and marker-scanned; a JSON/object verdict is narrowed for prose.
    prose_fields = []
    for index, section in enumerate(plan.sections or []):
        prose_fields.append((f"sections[{index}].title", getattr(section, "title", None)))
        prose_fields.append(
            (f"sections[{index}].blocked_reason", getattr(section, "blocked_reason", None)))
    for index, gap in enumerate(plan.open_gaps or []):
        prose_fields.append((f"open_gaps[{index}].note", getattr(gap, "note", None)))
    for index, finding in enumerate(plan.finding_candidates or []):
        prose_fields.append(
            (f"finding_candidates[{index}].blocked_reason",
             getattr(finding, "blocked_reason", None)))
    for index, rec in enumerate(plan.recommendation_candidates or []):
        prose_fields.append(
            (f"recommendation_candidates[{index}].blocked_reason",
             getattr(rec, "blocked_reason", None)))
    for index, reason in enumerate(plan.reasons or []):
        prose_fields.append((f"reasons[{index}]", reason))
    for index, warning in enumerate(plan.warnings or []):
        prose_fields.append((f"warnings[{index}]", warning))
    for label, value in prose_fields:
        if value is None:
            continue
        if not isinstance(value, str):
            return ("unsafe_plan_reference", f"plan {label} must be a string")
        if "\n" in value or "\r" in value or len(value) > MAX_REASON_LEN:
            return ("unsafe_plan_reference",
                    f"plan {label} must be a short single-line note, not raw content")
        marker = _value_marker(value, strict_json=False)
        if marker is not None:
            return ("prohibited_plan_value",
                    f"plan {label} carries a {marker} marker (value not echoed)")
    return None


def _plan_posture_denial(plan) -> Optional[Tuple[str, str]]:
    """Independently re-verify the Phase 36 internal-only posture at the write boundary."""
    if plan.audience != AUDIENCE_INTERNAL:
        return ("prohibited_audience",
                "plan.audience must be 'internal' (this writer persists no client-facing artifact)")
    if plan.output_status != REQUIRED_PLAN_OUTPUT_STATUS:
        return ("invalid_plan_output_status",
                f"plan.output_status must be '{REQUIRED_PLAN_OUTPUT_STATUS}'")
    if plan.review_status != REQUIRED_REVIEW_STATUS:
        return ("invalid_plan_review_status",
                f"plan.review_status must be '{REQUIRED_REVIEW_STATUS}'")
    if plan.lifecycle_status != REQUIRED_LIFECYCLE_STATUS:
        return ("invalid_plan_lifecycle_status",
                f"plan.lifecycle_status must be '{REQUIRED_LIFECYCLE_STATUS}'")
    for flag in REQUIRED_FALSE_PLAN_FLAGS:
        if getattr(plan, flag, False) is not False:
            return ("prohibited_posture",
                    f"plan.{flag} must be false (this writer approves, verifies, publishes, and "
                    "executes nothing)")
    if getattr(plan, "requires_human_review", True) is not True:
        return ("prohibited_posture", "plan.requires_human_review must be true")
    # Every recommendation candidate must itself stay internal-only.
    for index, rec in enumerate(plan.recommendation_candidates or []):
        if getattr(rec, "audience", None) != AUDIENCE_INTERNAL:
            return ("prohibited_audience",
                    f"recommendation_candidates[{index}].audience must be 'internal'")
        for flag in REQUIRED_FALSE_PLAN_FLAGS:
            if getattr(rec, flag, False) is not False:
                return ("prohibited_posture",
                        f"recommendation_candidates[{index}].{flag} must be false")
        if getattr(rec, "requires_human_review", True) is not True:
            return ("prohibited_posture",
                    f"recommendation_candidates[{index}].requires_human_review must be true")
    for index, finding in enumerate(plan.finding_candidates or []):
        for flag in ("client_facing_approved", "financial_verified", "capsule_candidate_ready",
                     "publication_allowed"):
            if getattr(finding, flag, False) is not False:
                return ("prohibited_posture",
                        f"finding_candidates[{index}].{flag} must be false")
        if getattr(finding, "requires_human_review", True) is not True:
            return ("prohibited_posture",
                    f"finding_candidates[{index}].requires_human_review must be true")
    return None


def _identity_mismatches(request: ControlledWriteRequest,
                         plan: InternalAssessmentReportPlan) -> List[str]:
    """Compare identity across the request, plan, and engagement subject (pre-DB, defense in depth)."""
    mismatches: List[str] = []
    subject = getattr(request, "subject", None)
    for attr in ("owner_id", "client_id", "engagement_id"):
        req_val = getattr(request, attr, None)
        if getattr(plan, attr, None) != req_val:
            mismatches.append(f"plan.{attr} does not match request.{attr}")
        if subject is not None and getattr(subject, attr, None) != req_val:
            mismatches.append(f"subject.{attr} does not match request.{attr}")
    if getattr(plan, "authorization_scope", None) != getattr(request, "authorization_scope", None):
        mismatches.append("plan.authorization_scope does not match request.authorization_scope")
    return mismatches


# --------------------------------------------------------------------------- pre-DB validation


def _pre_db_validate(
    request, report_request,
) -> Tuple[Optional[InternalAssessmentReportDraftWriteReceipt],
           Optional[InternalAssessmentReportPlan]]:
    """All governance checks that must pass *before* any DB connection is opened.

    A denial here honestly reports ``database_connection_made = False`` and
    ``sql_execution_made = False``.
    """
    if not isinstance(request, ControlledWriteRequest):
        return _deny("invalid_request_type",
                     "controlled write request is not a ControlledWriteRequest"), None

    # Independently revalidate through the Phase 17 boundary (allowlist, idempotency, snapshot
    # scope, identity). Planning-time defense in depth.
    plan_result = prepare_controlled_write(request)
    if not getattr(plan_result, "permitted", False):
        return _deny("plan_not_permitted",
                     "Phase 17 controlled-write plan was not permitted",
                     reasons=list(getattr(plan_result, "reasons", []) or [])
                     or ["Phase 17 controlled-write plan was not permitted"]), None
    write_plan = getattr(plan_result, "write_plan", None)
    if write_plan is None or getattr(write_plan, "requires_controlled_db_writer", False) is not True:
        return _deny("writer_not_required",
                     "controlled-write plan does not require the controlled DB writer"), None

    # Allowlist: exactly this table + action.
    if getattr(request, "target_table", None) != INTERNAL_ASSESSMENT_REPORT_DRAFT_TARGET_TABLE:
        return _deny("wrong_target_table",
                     f"target_table must be '{INTERNAL_ASSESSMENT_REPORT_DRAFT_TARGET_TABLE}'"), None
    if getattr(request, "requested_action", None) != INTERNAL_ASSESSMENT_REPORT_DRAFT_TARGET_ACTION:
        return _deny("wrong_target_action",
                     f"requested_action must be "
                     f"'{INTERNAL_ASSESSMENT_REPORT_DRAFT_TARGET_ACTION}'"), None

    # record_draft must be a concrete Phase 36 plan.
    plan = getattr(request, "record_draft", None)
    if not isinstance(plan, InternalAssessmentReportPlan):
        return _deny("invalid_record_draft",
                     "record_draft is not an InternalAssessmentReportPlan"), None

    # Optional Phase 36 request, accepted only for cross-checking.
    if report_request is not None:
        for attr in ("owner_id", "client_id", "engagement_id", "authorization_scope"):
            if getattr(report_request, attr, None) != getattr(request, attr, None):
                return _deny("identity_mismatch",
                             f"report_request.{attr} does not match request.{attr}"), None
        # Provenance: the cross-check request must describe *this* plan. Phase 36 derives
        # ``plan.report_plan_id`` as ``report_plan_id or idempotency_key``, so the same derivation
        # is used here — a legitimately matched pair can never be denied. Only field names are
        # reported; neither report_plan_id value is ever echoed.
        cross_plan_id = (getattr(report_request, "report_plan_id", None)
                         or getattr(report_request, "idempotency_key", None))
        if not _is_blank(cross_plan_id) and cross_plan_id != getattr(plan, "report_plan_id", None):
            return _deny("identity_mismatch",
                         "report_request.report_plan_id does not match plan.report_plan_id "
                         "(the cross-check request describes a different report plan)"), None

    # Server-controlled fields must not be caller-supplied. The Phase 36 plan has no
    # report_draft_id / created_at of its own, so a caller can only supply them as extra
    # attributes — which is exactly what is rejected here.
    for attr in ("report_draft_id", "created_at", "id", "stored_record_id"):
        if getattr(plan, attr, None) is not None:
            return _deny("caller_supplied_id" if attr != "created_at"
                         else "caller_supplied_timestamp",
                         f"plan.{attr} must be None (server-controlled)"), None

    # Prohibited attribute names, then internal-only posture, then value/reference safety.
    for check in (_plan_key_denial, _plan_posture_denial, _plan_content_denial):
        denial = check(plan)
        if denial is not None:
            return _deny(denial[0], denial[1]), None

    # Plan identity refs must be short safe labels.
    if _is_blank(getattr(plan, "report_plan_id", None)):
        return _deny("missing_report_plan_id", "plan.report_plan_id is required"), None
    if not _ref_ok(plan.report_plan_id):
        return _deny("invalid_report_plan_id",
                     "plan.report_plan_id must be a short safe identifier"), None
    if _is_blank(getattr(plan, "plan_fingerprint", None)):
        return _deny("missing_plan_fingerprint", "plan.plan_fingerprint is required"), None
    if not re.fullmatch(r"[0-9a-f]{64}", str(plan.plan_fingerprint or "")):
        return _deny("invalid_plan_fingerprint",
                     "plan.plan_fingerprint must be a 64-character sha256 hex digest"), None
    for attr, max_len in (("requested_by", MAX_REF_LEN), ("requester_role", MAX_LABEL_LEN),
                          ("workflow_id", MAX_REF_LEN),
                          ("managed_record_workflow_ref", MAX_REF_LEN)):
        val = getattr(plan, attr, None)
        if val is not None and not _label_ok(val, max_len):
            return _deny("invalid_plan_label",
                         f"plan.{attr} must be a short single-line safe label"), None
    if plan.report_purpose is not None and not _label_ok(plan.report_purpose, MAX_PURPOSE_LEN):
        return _deny("invalid_plan_label",
                     "plan.report_purpose must be a short single-line safe label"), None

    # Structural bounds — a plan cannot grow unbounded JSON columns.
    if len(plan.sections or []) > MAX_SECTIONS:
        return _deny("plan_too_large", f"plan carries more than {MAX_SECTIONS} sections"), None
    for field_name, limit in (("finding_candidates", MAX_CANDIDATES),
                              ("recommendation_candidates", MAX_CANDIDATES),
                              ("open_gaps", MAX_GAPS)):
        if len(getattr(plan, field_name, None) or []) > limit:
            return _deny("plan_too_large",
                         f"plan carries more than {limit} {field_name}"), None

    # Idempotency key present and valid.
    idem = getattr(request, "idempotency_key", None)
    if _is_blank(idem):
        return _deny("invalid_idempotency_key", "idempotency_key is required"), None
    if not isinstance(idem, str) or len(idem) > 128:
        return _deny("invalid_idempotency_key",
                     "idempotency_key must be a string of at most 128 characters"), None

    # Required identity / traceability fields.
    for attr in ("owner_id", "client_id", "engagement_id", "requested_by", "requester_role",
                 "authorization_scope"):
        if _is_blank(getattr(request, attr, None)):
            return _deny("missing_identity_field", f"request.{attr} is required"), None

    # Subject present, supported type, id present.
    subject = getattr(request, "subject", None)
    if subject is None:
        return _deny("missing_subject", "request.subject is required"), None
    if getattr(subject, "subject_record_type", None) not in SUPPORTED_SUBJECT_TYPES:
        return _deny("unsupported_subject_type",
                     "subject.subject_record_type must be 'engagement'"), None
    if _is_blank(getattr(subject, "subject_record_id", None)):
        return _deny("missing_subject", "subject.subject_record_id is required"), None

    mismatches = _identity_mismatches(request, plan)
    if mismatches:
        return _deny("identity_mismatch", "; ".join(mismatches)), None

    return None, plan


# --------------------------------------------------------------------------- serialization


def _sections_payload(plan) -> List[dict]:
    return [
        {
            "section_id": s.section_id,
            "title": s.title,
            "order": s.order,
            "readiness_state": s.readiness_state,
            "required_ref_categories": _safe_str_list(s.required_ref_categories),
            "satisfied_ref_categories": _safe_str_list(s.satisfied_ref_categories),
            "missing_ref_categories": _safe_str_list(s.missing_ref_categories),
            "supporting_ref_count": int(s.supporting_ref_count or 0),
            "synthesis_only": bool(s.synthesis_only),
            "blocked_reason": s.blocked_reason,
        }
        for s in (plan.sections or [])
    ]


def _trace_payload(plan) -> dict:
    return {
        section_id: {
            "section_id": trace.section_id,
            "supporting_refs": {
                category: _safe_str_list(refs)
                for category, refs in (trace.supporting_refs or {}).items()
            },
            "supporting_ref_count": int(trace.supporting_ref_count or 0),
            "missing_categories": _safe_str_list(trace.missing_categories),
        }
        for section_id, trace in (plan.evidence_trace_map or {}).items()
    }


def _findings_payload(plan) -> List[dict]:
    return [
        {
            "finding_candidate_id": f.finding_candidate_id,
            "section_id": f.section_id,
            "evidence_support_refs": _safe_str_list(f.evidence_support_refs),
            "review_support_refs": _safe_str_list(f.review_support_refs),
            "readiness_state": f.readiness_state,
            "blocked_reason": f.blocked_reason,
            "requires_human_review": True,
            "client_facing_approved": False,
        }
        for f in (plan.finding_candidates or [])
    ]


def _recommendations_payload(plan) -> List[dict]:
    return [
        {
            "recommendation_candidate_id": c.recommendation_candidate_id,
            "section_id": c.section_id,
            "reviewer_decision_refs": _safe_str_list(c.reviewer_decision_refs),
            "review_support_refs": _safe_str_list(c.review_support_refs),
            "evidence_support_refs": _safe_str_list(c.evidence_support_refs),
            "readiness_state": c.readiness_state,
            "audience": AUDIENCE_INTERNAL,
            "requires_financial_verification": bool(c.requires_financial_verification),
            "blocked_reason": c.blocked_reason,
            # Stored posture is hard-coded, never copied from the caller.
            "requires_human_review": True,
            "client_facing_approved": False,
            "financial_verified": False,
            "capsule_candidate_ready": False,
            "publication_allowed": False,
            "execution_allowed": False,
        }
        for c in (plan.recommendation_candidates or [])
    ]


def _gaps_payload(plan) -> List[dict]:
    return [
        {
            "gap_id": g.gap_id,
            "gap_kind": g.gap_kind,
            "section_id": g.section_id,
            "missing_ref_category": g.missing_ref_category,
            "missing_record_type": g.missing_record_type,
            "blocks_section": bool(g.blocks_section),
            "note": g.note,
        }
        for g in (plan.open_gaps or [])
    ]


def _payload_fingerprint(request: ControlledWriteRequest,
                         plan: InternalAssessmentReportPlan) -> str:
    """A deterministic, canonical digest over the identity + the stored plan payload.

    Backs replay-vs-conflict detection: an exact authorized replay reproduces this digest; any
    change to identity, plan provenance, structure, references, or posture changes it.
    """
    material = {
        "owner_id": request.owner_id,
        "client_id": request.client_id,
        "engagement_id": request.engagement_id,
        "authorization_scope": request.authorization_scope,
        "requested_by": request.requested_by,
        "requester_role": request.requester_role,
        "target_table": request.target_table,
        "requested_action": request.requested_action,
        "idempotency_key": request.idempotency_key,
        "report_plan_id": plan.report_plan_id,
        "plan_fingerprint": plan.plan_fingerprint,
        "report_purpose": plan.report_purpose,
        "workflow_id": plan.workflow_id,
        "managed_record_workflow_ref": plan.managed_record_workflow_ref,
        "audience": AUDIENCE_INTERNAL,
        "sections": _sections_payload(plan),
        "evidence_trace_map": _trace_payload(plan),
        "finding_candidates": _findings_payload(plan),
        "recommendation_candidates": _recommendations_payload(plan),
        "open_gaps": _gaps_payload(plan),
        "blocked_items": _safe_str_list(plan.blocked_items),
        "future_financial_verification_items": _safe_str_list(
            plan.future_financial_verification_items),
        "future_capsule_candidate_items": _safe_str_list(plan.future_capsule_candidate_items),
        "output_status": STORED_OUTPUT_STATUS,
        "review_status": REQUIRED_REVIEW_STATUS,
        "lifecycle_status": REQUIRED_LIFECYCLE_STATUS,
        "client_facing_approved": False,
        "financial_verified": False,
        "capsule_candidate_ready": False,
        "publication_allowed": False,
        "execution_allowed": False,
        "requires_human_review": True,
    }
    blob = json.dumps(material, sort_keys=True, separators=(",", ":"), default=str)
    return hashlib.sha256(blob.encode("utf-8")).hexdigest()


def _build_record(request: ControlledWriteRequest, plan: InternalAssessmentReportPlan,
                  fingerprint: str) -> InternalAssessmentReportDraftRecord:
    """Explicit field mapping — structure and references only (no ``__dict__`` copy, no prose)."""
    return InternalAssessmentReportDraftRecord(
        id=_ID_PREFIX + uuid.uuid4().hex[:16],  # server-controlled
        owner_id=request.owner_id,
        client_id=request.client_id,
        engagement_id=request.engagement_id,
        authorization_scope=request.authorization_scope,  # validated == stored scope
        report_plan_id=plan.report_plan_id,
        plan_fingerprint=plan.plan_fingerprint,
        requested_by=request.requested_by,
        requester_role=request.requester_role,
        report_purpose=plan.report_purpose,
        audience=AUDIENCE_INTERNAL,                 # server-stamped; internal only
        sections_json=_sections_payload(plan),
        evidence_trace_map_json=_trace_payload(plan),
        finding_candidates_json=_findings_payload(plan),
        recommendation_candidates_json=_recommendations_payload(plan),
        open_gaps_json=_gaps_payload(plan),
        blocked_items_json=_safe_str_list(plan.blocked_items),
        future_financial_verification_items_json=_safe_str_list(
            plan.future_financial_verification_items),
        future_capsule_candidate_items_json=_safe_str_list(plan.future_capsule_candidate_items),
        reasons_json=[r for r in _safe_str_list(plan.reasons) if len(r) <= MAX_REASON_LEN],
        warnings_json=[w for w in _safe_str_list(plan.warnings) if len(w) <= MAX_REASON_LEN],
        output_status=STORED_OUTPUT_STATUS,         # server-stamped: a persisted plan, not a report
        review_status=REQUIRED_REVIEW_STATUS,       # review-gated (server-stamped)
        lifecycle_status=REQUIRED_LIFECYCLE_STATUS,
        client_facing_approved=False,
        financial_verified=False,
        capsule_candidate_ready=False,
        publication_allowed=False,
        execution_allowed=False,
        requires_human_review=True,
        idempotency_key=request.idempotency_key,
        payload_fingerprint=fingerprint,
        created_by=request.requested_by,
        # created_at / updated_at are DB server_default (server-stamped).
        details_json={
            "source_phase": getattr(request, "source_phase", None),
            "section_count": len(plan.sections or []),
            "finding_candidate_count": len(plan.finding_candidates or []),
            "recommendation_candidate_count": len(plan.recommendation_candidates or []),
            "open_gap_count": len(plan.open_gaps or []),
        },
    )


def _find_existing(session, request: ControlledWriteRequest, idem: str):
    """Look up an existing row on the idempotency boundary (owner/client/engagement/key)."""
    return (
        session.query(InternalAssessmentReportDraftRecord)
        .filter_by(
            owner_id=request.owner_id,
            client_id=request.client_id,
            engagement_id=request.engagement_id,
            idempotency_key=idem,
        )
        .one_or_none()
    )


def _counts_from(record) -> dict:
    details = getattr(record, "details_json", None) or {}
    return {
        "section_count": int(details.get("section_count") or len(record.sections_json or [])),
        "finding_candidate_count": int(
            details.get("finding_candidate_count") or len(record.finding_candidates_json or [])),
        "recommendation_candidate_count": int(
            details.get("recommendation_candidate_count")
            or len(record.recommendation_candidates_json or [])),
        "open_gap_count": int(details.get("open_gap_count") or len(record.open_gaps_json or [])),
    }


def _receipt_from_existing(existing, idem: str,
                           outcome: str) -> InternalAssessmentReportDraftWriteReceipt:
    return InternalAssessmentReportDraftWriteReceipt(
        outcome=outcome, permitted=True, reason_code=outcome,
        stored_record_id=existing.id, report_plan_id=existing.report_plan_id,
        plan_fingerprint=existing.plan_fingerprint,
        idempotency_key=idem, audit_trace_ref=existing.id,
        database_connection_made=True, sql_execution_made=True,
        database_write_made=False, stored_record_created=False,
        existing_record_returned=True, transaction_committed=False,
        audience=existing.audience, output_status=existing.output_status,
        review_status=existing.review_status, lifecycle_status=existing.lifecycle_status,
        reasons=["exact authorized replay; existing record returned, not modified"],
        **_counts_from(existing))


def build_internal_assessment_report_draft_write_request(
    plan: InternalAssessmentReportPlan,
    *,
    requested_by: str,
    requester_role: str,
    idempotency_key: str,
    subject: Optional[ControlledWriteSubject] = None,
    source_phase: str = "phase37",
    lifecycle_status: str = "active",
) -> ControlledWriteRequest:
    """Convenience planner: wrap a Phase 36 plan in a Phase 17 ``ControlledWriteRequest``.

    Targets exactly ``internal_assessment_report_drafts`` /
    ``create_internal_assessment_report_draft`` and opens no database connection; a caller passes
    the result to :func:`persist_internal_assessment_report_draft`. This bridge lives in the DB
    layer **by design**, so the Phase 36 ``peak.reports`` package stays DB-free — mirroring the
    Phase 33/34 precedent. If ``subject`` is omitted, an in-memory engagement subject snapshot is
    derived from the plan's identity (the write-time gate still loads and trusts only the *stored*
    engagement).
    """
    if subject is None:
        subject = ControlledWriteSubject(
            subject_record_id=plan.engagement_id,
            subject_record_type="engagement",
            owner_id=plan.owner_id,
            client_id=plan.client_id,
            engagement_id=plan.engagement_id,
            stored_authorization_scope=plan.authorization_scope,
            stored_lifecycle_status=lifecycle_status,
        )
    return ControlledWriteRequest(
        owner_id=plan.owner_id,
        client_id=plan.client_id,
        engagement_id=plan.engagement_id,
        requested_by=requested_by,
        requester_role=requester_role,
        authorization_scope=plan.authorization_scope,
        target_table=INTERNAL_ASSESSMENT_REPORT_DRAFT_TARGET_TABLE,
        requested_action=INTERNAL_ASSESSMENT_REPORT_DRAFT_TARGET_ACTION,
        subject=subject,
        record_draft=plan,
        source_phase=source_phase,
        lifecycle_status=lifecycle_status,
        idempotency_key=idempotency_key,
    )


def persist_internal_assessment_report_draft(
    controlled_write_request,
    *,
    session_factory=None,
    report_request=None,
) -> InternalAssessmentReportDraftWriteReceipt:
    """Create one review-gated, **internal-only** ``internal_assessment_report_drafts`` row.

    ``session_factory`` is a zero-arg callable returning a SQLAlchemy ``Session`` (defaults to the
    controlled-DB session factory from the environment URL). ``report_request`` is an optional
    Phase 36 ``InternalAssessmentReportPlanRequest`` accepted only for cross-checking identity; the
    write-time authorization gate never trusts it.

    Returns an :class:`InternalAssessmentReportDraftWriteReceipt`; expected governance failures are
    typed denials, not exceptions. Receipts and denial reasons **never echo report prose, raw
    note/packet/evidence/interview content, generated output, credentials, DSNs, raw SQL, stack
    traces, ROI figures, or approval decisions**. This writer approves nothing, verifies nothing
    financially, publishes nothing, executes nothing, calls no Phase 22 review writer, and creates
    no ``review_records`` / ``agent_run_records`` row.
    """
    denial, plan = _pre_db_validate(controlled_write_request, report_request)
    if denial is not None:
        return denial

    request = controlled_write_request
    subject = request.subject
    idem = request.idempotency_key
    fingerprint = _payload_fingerprint(request, plan)

    factory = session_factory or create_session_factory()
    session = factory()
    attempted_commit = False
    try:
        # --- DB-backed authorization: load the authoritative stored subject ---
        engagement = session.get(Engagement, subject.subject_record_id)
        if engagement is None:
            return _deny("missing_subject",
                         "stored authorization subject (engagement) not found",
                         database_connection_made=True, sql_execution_made=True)

        stored_scope = engagement.authorization_scope
        if _is_blank(stored_scope):
            return _deny("missing_stored_scope",
                         "stored subject has no authorization_scope",
                         database_connection_made=True, sql_execution_made=True)
        if request.authorization_scope != stored_scope:
            return _deny("stored_scope_mismatch",
                         "request.authorization_scope does not match the stored subject's "
                         "authorization_scope (identity match is not sufficient)",
                         database_connection_made=True, sql_execution_made=True)

        subj_mismatch = []
        if engagement.owner_id != request.owner_id:
            subj_mismatch.append("engagement.owner_id")
        if engagement.client_id != request.client_id:
            subj_mismatch.append("engagement.client_id")
        if engagement.id != request.engagement_id:
            subj_mismatch.append("engagement.id != request.engagement_id")
        if subj_mismatch:
            return _deny("identity_mismatch",
                         "stored subject identity mismatch: " + ", ".join(subj_mismatch),
                         database_connection_made=True, sql_execution_made=True)

        if engagement.lifecycle_status in BLOCKED_LIFECYCLE_STATUSES:
            return _deny("subject_lifecycle_blocked",
                         f"stored subject lifecycle_status '{engagement.lifecycle_status}' "
                         "is not permitted",
                         database_connection_made=True, sql_execution_made=True)

        # --- Idempotency pre-check (common replay path; race is covered below) ---
        existing = _find_existing(session, request, idem)
        if existing is not None:
            if existing.payload_fingerprint == fingerprint:
                return _receipt_from_existing(
                    existing, idem,
                    InternalAssessmentReportDraftWriteOutcome.IDEMPOTENT_REPLAY)
            return _deny("idempotency_conflict",
                         "idempotency key reused with a different payload/identity",
                         database_connection_made=True, sql_execution_made=True,
                         existing_record_returned=False)

        # --- Insert exactly one authorized row ---
        record = _build_record(request, plan, fingerprint)
        session.add(record)
        attempted_commit = True
        try:
            session.commit()
        except IntegrityError:
            # Uniqueness race: re-query INLINE (not via _find_existing) so a race is still
            # classifiable even if the pre-check helper missed it.
            session.rollback()
            raced = (
                session.query(InternalAssessmentReportDraftRecord)
                .filter_by(
                    owner_id=request.owner_id,
                    client_id=request.client_id,
                    engagement_id=request.engagement_id,
                    idempotency_key=idem,
                )
                .one_or_none()
            )
            if raced is not None and raced.payload_fingerprint == fingerprint:
                return _receipt_from_existing(
                    raced, idem, InternalAssessmentReportDraftWriteOutcome.IDEMPOTENT_REPLAY)
            if raced is not None:
                return _deny("idempotency_conflict",
                             "idempotency key reused with a different payload/identity (race)",
                             database_connection_made=True, sql_execution_made=True,
                             existing_record_returned=False)
            return InternalAssessmentReportDraftWriteReceipt(
                outcome=InternalAssessmentReportDraftWriteOutcome.WRITE_OUTCOME_UNCERTAIN,
                permitted=True, reason_code="integrity_no_row", idempotency_key=idem,
                database_connection_made=True, sql_execution_made=True,
                database_write_made=False, stored_record_created=False,
                transaction_committed=False, outcome_uncertain=True,
                reasons=["integrity conflict without a matching row; write outcome uncertain"])

        session.refresh(record)  # load server-stamped created_at/updated_at
        created_iso = record.created_at.isoformat() if record.created_at else None
        return InternalAssessmentReportDraftWriteReceipt(
            outcome=InternalAssessmentReportDraftWriteOutcome.CREATED, permitted=True,
            reason_code="created",
            stored_record_id=record.id, report_plan_id=record.report_plan_id,
            plan_fingerprint=record.plan_fingerprint,
            idempotency_key=idem, audit_trace_ref=record.id,
            database_connection_made=True, sql_execution_made=True,
            database_write_made=True, stored_record_created=True,
            existing_record_returned=False, transaction_committed=True, outcome_uncertain=False,
            audience=record.audience, output_status=record.output_status,
            review_status=record.review_status, lifecycle_status=record.lifecycle_status,
            created_at=created_iso, database_write_at=created_iso,
            reasons=["created one review-gated, internal-only internal_assessment_report_drafts "
                     "row (a persisted plan, not a drafted report)"],
            **_counts_from(record))

    except SQLAlchemyError as exc:  # infrastructure failure
        try:
            session.rollback()
        except Exception:  # noqa: BLE001 - rollback best-effort; never re-raise here
            pass
        safe = type(exc).__name__  # never leak SQL / connection / plan content details
        if attempted_commit:
            return InternalAssessmentReportDraftWriteReceipt(
                outcome=InternalAssessmentReportDraftWriteOutcome.WRITE_OUTCOME_UNCERTAIN,
                permitted=True, reason_code="commit_uncertain", idempotency_key=idem,
                database_connection_made=True, sql_execution_made=True,
                database_write_made=False, stored_record_created=False,
                transaction_committed=False, outcome_uncertain=True,
                reasons=[f"commit outcome could not be confirmed ({safe}); a record may or "
                         "may not exist"])
        return InternalAssessmentReportDraftWriteReceipt(
            outcome=InternalAssessmentReportDraftWriteOutcome.FAILED_BEFORE_WRITE, permitted=True,
            reason_code="failed_before_write", idempotency_key=idem,
            database_connection_made=True, sql_execution_made=True,
            database_write_made=False, stored_record_created=False,
            transaction_committed=False, outcome_uncertain=False,
            reasons=[f"infrastructure failure before any write ({safe}); no row created"])
    finally:
        session.close()
