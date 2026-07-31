"""Controlled DB writer for internal report review packets (Phase 38).

The **tenth** narrow live DB writer. It persists **exactly one**
``internal_report_review_packets`` row from an :class:`InternalReportReviewPacketDraft`, through
the Phase 17 ``ControlledWriteRequest`` boundary, allowing only
``internal_report_review_packets`` / ``create_internal_report_review_packet``.

A packet is the **internal-only review packet** handed to a Peak human reviewer for a Phase 37
``internal_assessment_report_drafts`` row. It records *what the reviewer was shown and asked to
evaluate*: a section review checklist, reference-only evidence traces, open gaps, blocked items,
short internal reviewer questions, a readiness checklist, required follow-up actions, and
future-gate placeholders.

**A packet is not a decision.** ``packet_status`` is fixed at ``ready_for_internal_review`` and
``reviewer_decision_status`` at ``not_decided``; ``reviewer_decision_record_id`` must be absent at
creation. A stored row can never be misread as a review outcome.

**What is never stored or echoed:** final client-facing language, raw intake-note / packet /
evidence / interview text, source bytes, generated agent output, LLM prompts, credentials or
secrets, DSNs, raw SQL, stack traces, approval decisions, ROI or savings figures, capsule payloads,
and AgentNet publish payloads. Denial reasons report only a field name, an item position, or a
marker *category* — never the offending value.

Write-time authorization loads the **stored** ``Engagement`` and compares its stored
``authorization_scope``; identity matching is necessary but **not sufficient**. The writer then
loads the **stored** Phase 37 report draft and verifies its tenant, scope, and internal-only
posture — a caller-supplied reference alone never proves stored posture.

This writer approves nothing, verifies nothing financially, publishes nothing, executes nothing,
calls no Phase 22 review writer, creates no ``review_records`` / ``agent_run_records`` row, and
makes no LLM / MockLLM / agent / AgentNet / MCP / resolver / connector / network call.

See docs/INTERNAL_REPORT_REVIEW_PACKET_CONTROLLED_WRITER.md and
docs/INTERNAL_REPORT_REVIEW_PACKET_IDEMPOTENCY_POLICY.md.
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
# Public, DB-free Phase 32 value classifier (imports no peak.db).
from peak.reviewer_decisions.governance import classify_prohibited_value_marker

from .models import (
    Engagement,
    InternalAssessmentReportDraftRecord,
    InternalReportReviewPacketRecord,
)
from .session import create_session_factory
from .writer_contracts import (
    INTERNAL_REPORT_REVIEW_PACKET_TARGET_ACTION,
    INTERNAL_REPORT_REVIEW_PACKET_TARGET_TABLE,
    REVIEW_PACKET_DECISION_STATUS,
    REVIEW_PACKET_SOURCE_REPORT_DRAFT_TABLE,
    REVIEW_PACKET_STATUS,
    InternalReportReviewPacketDraft,
    InternalReportReviewPacketWriteOutcome,
    InternalReportReviewPacketWriteReceipt,
)

BLOCKED_LIFECYCLE_STATUSES = frozenset({"revoked", "archived", "deleted_reference_only"})
SUPPORTED_SUBJECT_TYPES = frozenset({"engagement"})

AUDIENCE_INTERNAL = "internal"
REQUIRED_REVIEW_STATUS = "needs_review"
REQUIRED_LIFECYCLE_STATUS = "draft"

# The stored Phase 37 report-draft posture a packet may be built on (mirrors that writer).
REQUIRED_DRAFT_OUTPUT_STATUS = "plan_persisted"
REQUIRED_DRAFT_REVIEW_STATUS = "needs_review"
REQUIRED_DRAFT_LIFECYCLE_STATUS = "draft"

# Bounds (documented in docs/INTERNAL_REPORT_REVIEW_PACKET_CONTROLLED_WRITER.md).
MAX_REF_LEN = 128
MAX_LABEL_LEN = 64
MAX_PURPOSE_LEN = 240
MAX_QUESTION_LEN = 240
MAX_REASON_LEN = 500
MAX_SECTION_REVIEW_ITEMS = 200
MAX_REVIEWER_QUESTIONS = 100
MAX_READINESS_ITEMS = 100
MAX_FOLLOWUP_ACTIONS = 200
MAX_OPEN_GAPS = 500
MAX_BLOCKED_ITEMS = 500
MAX_EVIDENCE_TRACE_REFS = 2000
MAX_FUTURE_ITEMS = 500
_ID_PREFIX = "irrp_"

# Posture flags that must be false on the draft and are hard-coded false on the stored row.
REQUIRED_FALSE_PACKET_FLAGS = (
    "client_facing_approved", "review_approval_made", "financial_verified",
    "capsule_candidate_ready", "publication_allowed", "execution_allowed",
)

# Allowed checklist / action statuses. None of these implies approval, sign-off, publication, a
# financial verification, or any client-facing outcome — that is the point of the allowlist.
ALLOWED_CHECK_STATUSES = frozenset({"not_started", "in_review", "needs_followup", "complete"})
ALLOWED_ACTION_STATUSES = frozenset({"open", "in_progress", "blocked", "done"})

# Strict per-family key sets. An item carrying any other key is denied.
SECTION_REVIEW_KEYS = frozenset({"section_id", "check_id", "status"})
READINESS_KEYS = frozenset({"check_id", "status"})
FOLLOWUP_KEYS = frozenset({"action_id", "status"})

#: Prohibited attribute-name markers. Only *unexpected* attributes (anything the caller bolted onto
#: the draft beyond its declared dataclass fields) are name-scanned; declared fields are known-safe
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

#: Client-facing / approval / publication language markers. Reviewer questions and purpose labels
#: are the only prose-ish fields a packet carries, so they are additionally scanned for intent.
PROHIBITED_INTENT_MARKERS = (
    "send to client", "send to the client", "client deliverable", "client-facing deliverable",
    "final report", "final client", "approve for client", "approved for client",
    "sign off", "sign-off", "publish capsule", "publish to agentnet", "roi of", "verified savings",
)

#: A safe short ref/id: no whitespace, no newlines, no quotes, bounded length.
_SAFE_REF_RE = re.compile(r"^[A-Za-z0-9_.:/\-]{1,128}$")
#: A stack trace is not caught by the Phase 32 value classifier, so it is matched here directly.
_STACKTRACE_RE = re.compile(
    r"traceback \(most recent call last\)|File \"[^\"]+\", line \d+", re.IGNORECASE)
#: Structural JSON-dump shapes; the Phase 32 classifier reports 'JSON/object' for any merely
#: bracket-prefixed value, so a prose verdict is narrowed to real object/array dumps.
_JSON_KEYVALUE_RE = re.compile(r'"[^"\n]{1,64}"\s*:')


def _is_blank(value) -> bool:
    return value is None or (isinstance(value, str) and not value.strip())


def _deny(reason_code: str, message: str,
          **flags) -> InternalReportReviewPacketWriteReceipt:
    receipt = InternalReportReviewPacketWriteReceipt(
        outcome=InternalReportReviewPacketWriteOutcome.DENIED, permitted=False,
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


def _intent_marker(value) -> Optional[str]:
    """Return 'client-facing/approval intent' when a prose field carries a disallowed intent."""
    if not isinstance(value, str):
        return None
    low = value.lower()
    if any(marker in low for marker in PROHIBITED_INTENT_MARKERS):
        return "client-facing/approval intent"
    return None


def _safe_name(name) -> str:
    if isinstance(name, str) and re.match(r"^[A-Za-z0-9_.\-]{1,64}$", name):
        return name
    return "<unsafe-field-name>"


def _ref_ok(value) -> bool:
    return isinstance(value, str) and bool(_SAFE_REF_RE.match(value))


def _safe_str_list(values, limit: int) -> List[str]:
    return [v for v in (values or []) if isinstance(v, str) and v.strip()][:limit]


def _label_ok(value, max_len: int) -> bool:
    """A short single-line safe label — no newline, no marker, no intent, bounded length."""
    if value is None:
        return True
    if not isinstance(value, str):
        return False
    if "\n" in value or "\r" in value or len(value) > max_len:
        return False
    return _value_marker(value, strict_json=False) is None and _intent_marker(value) is None


# --------------------------------------------------------------------------- draft safety


def _unexpected_attr_names(draft) -> List[str]:
    declared = set(getattr(type(draft), "__dataclass_fields__", {}))
    own = getattr(draft, "__dict__", None) or {}
    return [k for k in own if isinstance(k, str) and k not in declared]


def _draft_key_denial(draft) -> Optional[Tuple[str, str]]:
    """Deny any *unexpected* draft attribute whose name looks like raw content / a secret / intent."""
    for name in sorted(_unexpected_attr_names(draft)):
        low = name.lower()
        if any(marker in low for marker in PROHIBITED_KEY_MARKERS):
            return ("prohibited_packet_key",
                    f"packet draft carries a prohibited attribute '{_safe_name(name)}'")
    return None


def _draft_posture_denial(draft) -> Optional[Tuple[str, str]]:
    """Re-verify the internal-only, pre-decision posture at the write boundary."""
    if draft.audience != AUDIENCE_INTERNAL:
        return ("prohibited_audience",
                "draft.audience must be 'internal' (this writer persists no client-facing artifact)")
    if draft.packet_status != REVIEW_PACKET_STATUS:
        return ("invalid_packet_status",
                f"draft.packet_status must be '{REVIEW_PACKET_STATUS}'")
    if draft.review_status != REQUIRED_REVIEW_STATUS:
        return ("invalid_review_status",
                f"draft.review_status must be '{REQUIRED_REVIEW_STATUS}'")
    if draft.lifecycle_status != REQUIRED_LIFECYCLE_STATUS:
        return ("invalid_lifecycle_status",
                f"draft.lifecycle_status must be '{REQUIRED_LIFECYCLE_STATUS}'")
    if draft.reviewer_decision_status != REVIEW_PACKET_DECISION_STATUS:
        return ("invalid_reviewer_decision_status",
                f"draft.reviewer_decision_status must be '{REVIEW_PACKET_DECISION_STATUS}' "
                "(a packet is created before any reviewer decision exists)")
    if draft.reviewer_decision_record_id is not None:
        return ("prohibited_reviewer_decision_link",
                "draft.reviewer_decision_record_id must be None at creation (a packet is created "
                "before any reviewer decision exists; linkage is a later controlled path)")
    for flag in REQUIRED_FALSE_PACKET_FLAGS:
        if getattr(draft, flag, False) is not False:
            return ("prohibited_posture",
                    f"draft.{flag} must be false (this writer approves, verifies, publishes, and "
                    "executes nothing)")
    if getattr(draft, "requires_human_review", True) is not True:
        return ("prohibited_posture", "draft.requires_human_review must be true")
    return None


def _checklist_denial(items, field_name: str, allowed_keys, required_keys,
                      allowed_statuses, limit: int) -> Optional[Tuple[str, str]]:
    """Validate one checklist/action family: strict dict shape, safe labels, allowed status."""
    if not isinstance(items, list):
        return ("invalid_packet_field", f"draft.{field_name} must be a list")
    for index, item in enumerate(items[:limit]):
        base = f"{field_name}[{index}]"
        if not isinstance(item, dict):
            return ("invalid_packet_field", f"draft.{base} must be a dict")
        keys = set(item)
        extra = keys - allowed_keys
        if extra:
            return ("prohibited_packet_key",
                    f"draft.{base} carries unexpected key(s): "
                    + ", ".join(sorted(_safe_name(k) for k in extra)))
        missing = required_keys - keys
        if missing:
            return ("invalid_packet_field",
                    f"draft.{base} is missing key(s): " + ", ".join(sorted(missing)))
        for key, value in item.items():
            if not _ref_ok(value):
                return ("unsafe_packet_reference",
                        f"draft.{base}.{_safe_name(key)} is not a short safe label "
                        "(value not echoed)")
            if _value_marker(value) is not None:
                return ("prohibited_packet_value",
                        f"draft.{base}.{_safe_name(key)} carries a "
                        f"{_value_marker(value)} marker (value not echoed)")
        if item["status"] not in allowed_statuses:
            return ("invalid_packet_status_value",
                    f"draft.{base}.status is not an allowed internal status "
                    "(approval/publication/financial statuses are never accepted)")
    return None


def _draft_content_denial(draft) -> Optional[Tuple[str, str]]:
    """Verify every persisted reference/label is a short safe id carrying no unsafe marker."""
    # 1. Plain reference lists.
    for field_name in ("evidence_trace_refs", "open_gaps", "blocked_items",
                       "future_financial_verification_items", "future_capsule_candidate_items"):
        values = getattr(draft, field_name, None)
        if not isinstance(values, list):
            return ("invalid_packet_field", f"draft.{field_name} must be a list")
        for index, value in enumerate(values):
            if not _ref_ok(value):
                return ("unsafe_packet_reference",
                        f"draft.{field_name}[{index}] is not a short safe reference "
                        "(value not echoed)")
            marker = _value_marker(value)
            if marker is not None:
                return ("prohibited_packet_value",
                        f"draft.{field_name}[{index}] carries a {marker} marker "
                        "(value not echoed)")

    # 2. Checklist families.
    for items, field_name, allowed, required, statuses, limit in (
        (draft.section_review_checklist, "section_review_checklist", SECTION_REVIEW_KEYS,
         SECTION_REVIEW_KEYS, ALLOWED_CHECK_STATUSES, MAX_SECTION_REVIEW_ITEMS),
        (draft.readiness_checklist, "readiness_checklist", READINESS_KEYS, READINESS_KEYS,
         ALLOWED_CHECK_STATUSES, MAX_READINESS_ITEMS),
        (draft.required_followup_actions, "required_followup_actions", FOLLOWUP_KEYS,
         FOLLOWUP_KEYS, ALLOWED_ACTION_STATUSES, MAX_FOLLOWUP_ACTIONS),
    ):
        denial = _checklist_denial(items, field_name, allowed, required, statuses, limit)
        if denial is not None:
            return denial

    # 3. Reviewer questions — the only prose-ish list. Short, single-line, marker- and
    #    intent-scanned so a client-facing sentence can never be smuggled in.
    if not isinstance(draft.reviewer_questions, list):
        return ("invalid_packet_field", "draft.reviewer_questions must be a list")
    for index, question in enumerate(draft.reviewer_questions):
        base = f"reviewer_questions[{index}]"
        if not isinstance(question, str) or not question.strip():
            return ("invalid_packet_field", f"draft.{base} must be a non-empty string")
        if "\n" in question or "\r" in question or len(question) > MAX_QUESTION_LEN:
            return ("unsafe_packet_reference",
                    f"draft.{base} must be a short single-line internal prompt, not raw content")
        marker = _value_marker(question, strict_json=False)
        if marker is not None:
            return ("prohibited_packet_value",
                    f"draft.{base} carries a {marker} marker (value not echoed)")
        if _intent_marker(question) is not None:
            return ("prohibited_packet_intent",
                    f"draft.{base} carries client-facing/approval intent (value not echoed)")

    # 4. Bounded reasons / warnings.
    for field_name in ("reasons", "warnings"):
        values = getattr(draft, field_name, None)
        if not isinstance(values, list):
            return ("invalid_packet_field", f"draft.{field_name} must be a list")
        for index, value in enumerate(values):
            if not isinstance(value, str):
                return ("invalid_packet_field", f"draft.{field_name}[{index}] must be a string")
            if "\n" in value or "\r" in value or len(value) > MAX_REASON_LEN:
                return ("unsafe_packet_reference",
                        f"draft.{field_name}[{index}] must be a short single-line note")
            marker = _value_marker(value, strict_json=False)
            if marker is not None:
                return ("prohibited_packet_value",
                        f"draft.{field_name}[{index}] carries a {marker} marker "
                        "(value not echoed)")
    return None


def _draft_bounds_denial(draft) -> Optional[Tuple[str, str]]:
    """Cap every list family so a JSON column cannot grow unbounded."""
    for field_name, limit in (("section_review_checklist", MAX_SECTION_REVIEW_ITEMS),
                              ("reviewer_questions", MAX_REVIEWER_QUESTIONS),
                              ("readiness_checklist", MAX_READINESS_ITEMS),
                              ("required_followup_actions", MAX_FOLLOWUP_ACTIONS),
                              ("open_gaps", MAX_OPEN_GAPS),
                              ("blocked_items", MAX_BLOCKED_ITEMS),
                              ("evidence_trace_refs", MAX_EVIDENCE_TRACE_REFS),
                              ("future_financial_verification_items", MAX_FUTURE_ITEMS),
                              ("future_capsule_candidate_items", MAX_FUTURE_ITEMS)):
        values = getattr(draft, field_name, None) or []
        if len(values) > limit:
            return ("packet_too_large",
                    f"packet draft carries more than {limit} {field_name}")
    return None


def _identity_mismatches(request: ControlledWriteRequest,
                         draft: InternalReportReviewPacketDraft) -> List[str]:
    """Compare identity across the request, draft, and engagement subject (pre-DB defense in depth)."""
    mismatches: List[str] = []
    subject = getattr(request, "subject", None)
    for attr in ("owner_id", "client_id", "engagement_id"):
        req_val = getattr(request, attr, None)
        if getattr(draft, attr, None) != req_val:
            mismatches.append(f"draft.{attr} does not match request.{attr}")
        if subject is not None and getattr(subject, attr, None) != req_val:
            mismatches.append(f"subject.{attr} does not match request.{attr}")
    if getattr(draft, "authorization_scope", None) != getattr(request, "authorization_scope", None):
        mismatches.append("draft.authorization_scope does not match request.authorization_scope")
    return mismatches


# --------------------------------------------------------------------------- pre-DB validation


def _pre_db_validate(
    request,
) -> Tuple[Optional[InternalReportReviewPacketWriteReceipt],
           Optional[InternalReportReviewPacketDraft]]:
    """All governance checks that must pass *before* any DB connection is opened."""
    if not isinstance(request, ControlledWriteRequest):
        return _deny("invalid_request_type",
                     "controlled write request is not a ControlledWriteRequest"), None

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

    if getattr(request, "target_table", None) != INTERNAL_REPORT_REVIEW_PACKET_TARGET_TABLE:
        return _deny("wrong_target_table",
                     f"target_table must be '{INTERNAL_REPORT_REVIEW_PACKET_TARGET_TABLE}'"), None
    if getattr(request, "requested_action", None) != INTERNAL_REPORT_REVIEW_PACKET_TARGET_ACTION:
        return _deny("wrong_target_action",
                     "requested_action must be "
                     f"'{INTERNAL_REPORT_REVIEW_PACKET_TARGET_ACTION}'"), None

    draft = getattr(request, "record_draft", None)
    if not isinstance(draft, InternalReportReviewPacketDraft):
        return _deny("invalid_record_draft",
                     "record_draft is not an InternalReportReviewPacketDraft"), None

    # Server-controlled fields must not be caller-supplied.
    if getattr(draft, "review_packet_id", None) is not None:
        return _deny("caller_supplied_id",
                     "draft.review_packet_id must be None (server-controlled)"), None
    if getattr(draft, "created_at", None) is not None:
        return _deny("caller_supplied_timestamp",
                     "draft.created_at must be None (server-stamped created_at is "
                     "authoritative)"), None

    for check in (_draft_key_denial, _draft_posture_denial, _draft_bounds_denial,
                  _draft_content_denial):
        denial = check(draft)
        if denial is not None:
            return _deny(denial[0], denial[1]), None

    # Report-draft linkage refs.
    if _is_blank(getattr(draft, "internal_assessment_report_draft_id", None)):
        return _deny("missing_report_draft_ref",
                     "draft.internal_assessment_report_draft_id is required"), None
    for attr in ("internal_assessment_report_draft_id", "report_plan_id"):
        if not _ref_ok(getattr(draft, attr, None)):
            return _deny("invalid_report_draft_ref",
                         f"draft.{attr} must be a short safe identifier"), None
    if _is_blank(getattr(draft, "plan_fingerprint", None)):
        return _deny("missing_plan_fingerprint", "draft.plan_fingerprint is required"), None
    for attr in ("plan_fingerprint", "report_draft_payload_fingerprint"):
        value = getattr(draft, attr, None)
        if value is not None and not re.fullmatch(r"[0-9a-f]{64}", str(value)):
            return _deny("invalid_fingerprint",
                         f"draft.{attr} must be a 64-character sha256 hex digest"), None

    # Short safe labels.
    for attr, max_len in (("assigned_reviewer", MAX_REF_LEN),
                          ("packet_purpose", MAX_PURPOSE_LEN)):
        if not _label_ok(getattr(draft, attr, None), max_len):
            return _deny("invalid_packet_label",
                         f"draft.{attr} must be a short single-line safe label"), None

    idem = getattr(request, "idempotency_key", None)
    if _is_blank(idem):
        return _deny("invalid_idempotency_key", "idempotency_key is required"), None
    if not isinstance(idem, str) or len(idem) > 128:
        return _deny("invalid_idempotency_key",
                     "idempotency_key must be a string of at most 128 characters"), None

    for attr in ("owner_id", "client_id", "engagement_id", "requested_by", "requester_role",
                 "authorization_scope"):
        if _is_blank(getattr(request, attr, None)):
            return _deny("missing_identity_field", f"request.{attr} is required"), None

    subject = getattr(request, "subject", None)
    if subject is None:
        return _deny("missing_subject", "request.subject is required"), None
    if getattr(subject, "subject_record_type", None) not in SUPPORTED_SUBJECT_TYPES:
        return _deny("unsupported_subject_type",
                     "subject.subject_record_type must be 'engagement'"), None
    if _is_blank(getattr(subject, "subject_record_id", None)):
        return _deny("missing_subject", "subject.subject_record_id is required"), None

    mismatches = _identity_mismatches(request, draft)
    if mismatches:
        return _deny("identity_mismatch", "; ".join(mismatches)), None

    return None, draft


def _stored_report_draft_denial(stored, request, draft):
    """Verify the **stored** Phase 37 report draft's tenant, scope, and internal-only posture.

    A caller-supplied reference alone never proves stored posture — this is why the packet writer
    reads the report-draft row rather than trusting the ref (linkage mode B).
    """
    if stored is None:
        return ("missing_report_draft",
                "stored internal assessment report draft not found")
    for attr, req_attr in (("owner_id", "owner_id"), ("client_id", "client_id"),
                           ("engagement_id", "engagement_id"),
                           ("authorization_scope", "authorization_scope")):
        if getattr(stored, attr, None) != getattr(request, req_attr, None):
            return ("report_draft_identity_mismatch",
                    f"stored report draft {attr} does not match request.{req_attr}")
    if getattr(stored, "audience", None) != AUDIENCE_INTERNAL:
        return ("report_draft_not_internal", "stored report draft audience is not 'internal'")
    if getattr(stored, "output_status", None) != REQUIRED_DRAFT_OUTPUT_STATUS:
        return ("report_draft_invalid_output_status",
                f"stored report draft output_status must be '{REQUIRED_DRAFT_OUTPUT_STATUS}'")
    if getattr(stored, "review_status", None) != REQUIRED_DRAFT_REVIEW_STATUS:
        return ("report_draft_invalid_review_status",
                f"stored report draft review_status must be '{REQUIRED_DRAFT_REVIEW_STATUS}'")
    if getattr(stored, "lifecycle_status", None) != REQUIRED_DRAFT_LIFECYCLE_STATUS:
        return ("report_draft_invalid_lifecycle_status",
                f"stored report draft lifecycle_status must be "
                f"'{REQUIRED_DRAFT_LIFECYCLE_STATUS}'")
    for flag in ("client_facing_approved", "financial_verified", "capsule_candidate_ready",
                 "publication_allowed", "execution_allowed"):
        if getattr(stored, flag, False) is not False:
            return ("report_draft_posture_elevated",
                    f"stored report draft {flag} must be false")
    if getattr(stored, "requires_human_review", True) is not True:
        return ("report_draft_posture_elevated",
                "stored report draft requires_human_review must be true")
    # Provenance the packet claims must match the stored draft.
    if draft.report_plan_id != getattr(stored, "report_plan_id", None):
        return ("report_draft_provenance_mismatch",
                "draft.report_plan_id does not match the stored report draft's report_plan_id")
    if draft.plan_fingerprint != getattr(stored, "plan_fingerprint", None):
        return ("report_draft_provenance_mismatch",
                "draft.plan_fingerprint does not match the stored report draft's plan_fingerprint")
    supplied_fp = getattr(draft, "report_draft_payload_fingerprint", None)
    if supplied_fp is not None and supplied_fp != getattr(stored, "payload_fingerprint", None):
        return ("report_draft_provenance_mismatch",
                "draft.report_draft_payload_fingerprint does not match the stored report draft's "
                "payload_fingerprint")
    return None


# --------------------------------------------------------------------------- serialization


def _checklist_payload(items, allowed_keys, limit: int) -> List[dict]:
    return [{k: item[k] for k in sorted(allowed_keys) if k in item}
            for item in (items or [])[:limit] if isinstance(item, dict)]


def _payload_fingerprint(request: ControlledWriteRequest,
                         draft: InternalReportReviewPacketDraft,
                         report_draft_payload_fingerprint: Optional[str]) -> str:
    """A deterministic, canonical digest over the identity + the stored packet payload."""
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
        "internal_assessment_report_draft_id": draft.internal_assessment_report_draft_id,
        "source_report_draft_table": REVIEW_PACKET_SOURCE_REPORT_DRAFT_TABLE,
        "report_plan_id": draft.report_plan_id,
        "plan_fingerprint": draft.plan_fingerprint,
        "report_draft_payload_fingerprint": report_draft_payload_fingerprint,
        "assigned_reviewer": draft.assigned_reviewer,
        "packet_purpose": draft.packet_purpose,
        "audience": AUDIENCE_INTERNAL,
        "packet_status": REVIEW_PACKET_STATUS,
        "review_status": REQUIRED_REVIEW_STATUS,
        "lifecycle_status": REQUIRED_LIFECYCLE_STATUS,
        "reviewer_decision_status": REVIEW_PACKET_DECISION_STATUS,
        "section_review_checklist": _checklist_payload(
            draft.section_review_checklist, SECTION_REVIEW_KEYS, MAX_SECTION_REVIEW_ITEMS),
        "evidence_trace_refs": _safe_str_list(draft.evidence_trace_refs,
                                              MAX_EVIDENCE_TRACE_REFS),
        "open_gaps": _safe_str_list(draft.open_gaps, MAX_OPEN_GAPS),
        "blocked_items": _safe_str_list(draft.blocked_items, MAX_BLOCKED_ITEMS),
        "reviewer_questions": _safe_str_list(draft.reviewer_questions, MAX_REVIEWER_QUESTIONS),
        "readiness_checklist": _checklist_payload(
            draft.readiness_checklist, READINESS_KEYS, MAX_READINESS_ITEMS),
        "required_followup_actions": _checklist_payload(
            draft.required_followup_actions, FOLLOWUP_KEYS, MAX_FOLLOWUP_ACTIONS),
        "future_financial_verification_items": _safe_str_list(
            draft.future_financial_verification_items, MAX_FUTURE_ITEMS),
        "future_capsule_candidate_items": _safe_str_list(
            draft.future_capsule_candidate_items, MAX_FUTURE_ITEMS),
        "client_facing_approved": False,
        "review_approval_made": False,
        "financial_verified": False,
        "capsule_candidate_ready": False,
        "publication_allowed": False,
        "execution_allowed": False,
        "requires_human_review": True,
    }
    blob = json.dumps(material, sort_keys=True, separators=(",", ":"), default=str)
    return hashlib.sha256(blob.encode("utf-8")).hexdigest()


def _build_record(request: ControlledWriteRequest, draft: InternalReportReviewPacketDraft,
                  report_draft_payload_fingerprint: Optional[str],
                  fingerprint: str) -> InternalReportReviewPacketRecord:
    """Explicit field mapping — labels, statuses, and references only (no ``__dict__`` copy)."""
    return InternalReportReviewPacketRecord(
        id=_ID_PREFIX + uuid.uuid4().hex[:16],  # server-controlled
        owner_id=request.owner_id,
        client_id=request.client_id,
        engagement_id=request.engagement_id,
        authorization_scope=request.authorization_scope,  # validated == stored scope
        internal_assessment_report_draft_id=draft.internal_assessment_report_draft_id,
        source_report_draft_table=REVIEW_PACKET_SOURCE_REPORT_DRAFT_TABLE,
        report_plan_id=draft.report_plan_id,
        plan_fingerprint=draft.plan_fingerprint,
        report_draft_payload_fingerprint=report_draft_payload_fingerprint,
        requested_by=request.requested_by,
        requester_role=request.requester_role,
        assigned_reviewer=draft.assigned_reviewer,
        packet_purpose=draft.packet_purpose,
        audience=AUDIENCE_INTERNAL,                 # server-stamped; internal only
        packet_status=REVIEW_PACKET_STATUS,         # server-stamped; pre-decision
        review_status=REQUIRED_REVIEW_STATUS,
        lifecycle_status=REQUIRED_LIFECYCLE_STATUS,
        reviewer_decision_record_id=None,           # never linked at creation
        reviewer_decision_status=REVIEW_PACKET_DECISION_STATUS,
        section_review_checklist_json=_checklist_payload(
            draft.section_review_checklist, SECTION_REVIEW_KEYS, MAX_SECTION_REVIEW_ITEMS),
        evidence_trace_refs_json=_safe_str_list(draft.evidence_trace_refs,
                                                MAX_EVIDENCE_TRACE_REFS),
        open_gaps_json=_safe_str_list(draft.open_gaps, MAX_OPEN_GAPS),
        blocked_items_json=_safe_str_list(draft.blocked_items, MAX_BLOCKED_ITEMS),
        reviewer_questions_json=_safe_str_list(draft.reviewer_questions, MAX_REVIEWER_QUESTIONS),
        readiness_checklist_json=_checklist_payload(
            draft.readiness_checklist, READINESS_KEYS, MAX_READINESS_ITEMS),
        required_followup_actions_json=_checklist_payload(
            draft.required_followup_actions, FOLLOWUP_KEYS, MAX_FOLLOWUP_ACTIONS),
        future_financial_verification_items_json=_safe_str_list(
            draft.future_financial_verification_items, MAX_FUTURE_ITEMS),
        future_capsule_candidate_items_json=_safe_str_list(
            draft.future_capsule_candidate_items, MAX_FUTURE_ITEMS),
        reasons_json=_safe_str_list(draft.reasons, MAX_REVIEWER_QUESTIONS),
        warnings_json=_safe_str_list(draft.warnings, MAX_REVIEWER_QUESTIONS),
        client_facing_approved=False,
        review_approval_made=False,
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
            "section_review_item_count": len(draft.section_review_checklist or []),
            "reviewer_question_count": len(draft.reviewer_questions or []),
            "readiness_check_item_count": len(draft.readiness_checklist or []),
            "required_followup_action_count": len(draft.required_followup_actions or []),
            "open_gap_count": len(draft.open_gaps or []),
            "evidence_trace_ref_count": len(draft.evidence_trace_refs or []),
        },
    )


def _find_existing(session, request: ControlledWriteRequest, idem: str):
    """Look up an existing row on the idempotency boundary (owner/client/engagement/key)."""
    return (
        session.query(InternalReportReviewPacketRecord)
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

    def _n(key, column):
        return int(details.get(key) or len(getattr(record, column, None) or []))

    return {
        "section_review_item_count": _n("section_review_item_count",
                                        "section_review_checklist_json"),
        "reviewer_question_count": _n("reviewer_question_count", "reviewer_questions_json"),
        "readiness_check_item_count": _n("readiness_check_item_count",
                                         "readiness_checklist_json"),
        "required_followup_action_count": _n("required_followup_action_count",
                                             "required_followup_actions_json"),
        "open_gap_count": _n("open_gap_count", "open_gaps_json"),
        "evidence_trace_ref_count": _n("evidence_trace_ref_count", "evidence_trace_refs_json"),
    }


def _receipt_from_existing(existing, idem: str,
                           outcome: str) -> InternalReportReviewPacketWriteReceipt:
    return InternalReportReviewPacketWriteReceipt(
        outcome=outcome, permitted=True, reason_code=outcome,
        stored_record_id=existing.id,
        internal_assessment_report_draft_id=existing.internal_assessment_report_draft_id,
        report_plan_id=existing.report_plan_id, plan_fingerprint=existing.plan_fingerprint,
        idempotency_key=idem, audit_trace_ref=existing.id,
        database_connection_made=True, sql_execution_made=True,
        database_write_made=False, stored_record_created=False,
        existing_record_returned=True, transaction_committed=False,
        audience=existing.audience, packet_status=existing.packet_status,
        review_status=existing.review_status, lifecycle_status=existing.lifecycle_status,
        reviewer_decision_status=existing.reviewer_decision_status,
        reasons=["exact authorized replay; existing record returned, not modified"],
        **_counts_from(existing))


def build_internal_report_review_packet_write_request(
    draft: InternalReportReviewPacketDraft,
    *,
    requested_by: str,
    requester_role: str,
    idempotency_key: str,
    subject: Optional[ControlledWriteSubject] = None,
    source_phase: str = "phase38",
    lifecycle_status: str = "active",
) -> ControlledWriteRequest:
    """Convenience planner: wrap a packet draft in a Phase 17 ``ControlledWriteRequest``.

    Targets exactly ``internal_report_review_packets`` /
    ``create_internal_report_review_packet`` and opens no database connection; a caller passes the
    result to :func:`persist_internal_report_review_packet`. If ``subject`` is omitted, an
    in-memory engagement subject snapshot is derived from the draft's identity (the write-time gate
    still loads and trusts only the *stored* engagement).
    """
    if subject is None:
        subject = ControlledWriteSubject(
            subject_record_id=draft.engagement_id,
            subject_record_type="engagement",
            owner_id=draft.owner_id,
            client_id=draft.client_id,
            engagement_id=draft.engagement_id,
            stored_authorization_scope=draft.authorization_scope,
            stored_lifecycle_status=lifecycle_status,
        )
    return ControlledWriteRequest(
        owner_id=draft.owner_id,
        client_id=draft.client_id,
        engagement_id=draft.engagement_id,
        requested_by=requested_by,
        requester_role=requester_role,
        authorization_scope=draft.authorization_scope,
        target_table=INTERNAL_REPORT_REVIEW_PACKET_TARGET_TABLE,
        requested_action=INTERNAL_REPORT_REVIEW_PACKET_TARGET_ACTION,
        subject=subject,
        record_draft=draft,
        source_phase=source_phase,
        lifecycle_status=lifecycle_status,
        idempotency_key=idempotency_key,
    )


def persist_internal_report_review_packet(
    controlled_write_request,
    *,
    session_factory=None,
) -> InternalReportReviewPacketWriteReceipt:
    """Create one review-gated, **internal-only, pre-decision** review packet row.

    ``session_factory`` is a zero-arg callable returning a SQLAlchemy ``Session`` (defaults to the
    controlled-DB session factory from the environment URL).

    Returns an :class:`InternalReportReviewPacketWriteReceipt`; expected governance failures are
    typed denials, not exceptions. Receipts and denial reasons **never echo report prose, raw
    note/packet/evidence/interview content, generated output, credentials, DSNs, raw SQL, stack
    traces, ROI figures, or approval decisions**. This writer approves nothing, verifies nothing
    financially, publishes nothing, executes nothing, calls no Phase 22 review writer, and creates
    no ``review_records`` / ``agent_run_records`` row.
    """
    denial, draft = _pre_db_validate(controlled_write_request)
    if denial is not None:
        return denial

    request = controlled_write_request
    subject = request.subject
    idem = request.idempotency_key

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

        # --- Stored report-draft linkage (mode B): read the row, never trust the ref alone ---
        stored_draft = session.get(InternalAssessmentReportDraftRecord,
                                   draft.internal_assessment_report_draft_id)
        link_denial = _stored_report_draft_denial(stored_draft, request, draft)
        if link_denial is not None:
            return _deny(link_denial[0], link_denial[1],
                         database_connection_made=True, sql_execution_made=True)
        report_draft_payload_fingerprint = stored_draft.payload_fingerprint

        fingerprint = _payload_fingerprint(request, draft, report_draft_payload_fingerprint)

        # --- Idempotency pre-check (common replay path; race is covered below) ---
        existing = _find_existing(session, request, idem)
        if existing is not None:
            if existing.payload_fingerprint == fingerprint:
                return _receipt_from_existing(
                    existing, idem, InternalReportReviewPacketWriteOutcome.IDEMPOTENT_REPLAY)
            return _deny("idempotency_conflict",
                         "idempotency key reused with a different payload/identity",
                         database_connection_made=True, sql_execution_made=True,
                         existing_record_returned=False)

        # --- Insert exactly one authorized row ---
        record = _build_record(request, draft, report_draft_payload_fingerprint, fingerprint)
        session.add(record)
        attempted_commit = True
        try:
            session.commit()
        except IntegrityError:
            # Uniqueness race: re-query INLINE (not via _find_existing) so a race is still
            # classifiable even if the pre-check helper missed it.
            session.rollback()
            raced = (
                session.query(InternalReportReviewPacketRecord)
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
                    raced, idem, InternalReportReviewPacketWriteOutcome.IDEMPOTENT_REPLAY)
            if raced is not None:
                return _deny("idempotency_conflict",
                             "idempotency key reused with a different payload/identity (race)",
                             database_connection_made=True, sql_execution_made=True,
                             existing_record_returned=False)
            return InternalReportReviewPacketWriteReceipt(
                outcome=InternalReportReviewPacketWriteOutcome.WRITE_OUTCOME_UNCERTAIN,
                permitted=True, reason_code="integrity_no_row", idempotency_key=idem,
                database_connection_made=True, sql_execution_made=True,
                database_write_made=False, stored_record_created=False,
                transaction_committed=False, outcome_uncertain=True,
                reasons=["integrity conflict without a matching row; write outcome uncertain"])

        session.refresh(record)  # load server-stamped created_at/updated_at
        created_iso = record.created_at.isoformat() if record.created_at else None
        return InternalReportReviewPacketWriteReceipt(
            outcome=InternalReportReviewPacketWriteOutcome.CREATED, permitted=True,
            reason_code="created",
            stored_record_id=record.id,
            internal_assessment_report_draft_id=record.internal_assessment_report_draft_id,
            report_plan_id=record.report_plan_id, plan_fingerprint=record.plan_fingerprint,
            idempotency_key=idem, audit_trace_ref=record.id,
            database_connection_made=True, sql_execution_made=True,
            database_write_made=True, stored_record_created=True,
            existing_record_returned=False, transaction_committed=True, outcome_uncertain=False,
            audience=record.audience, packet_status=record.packet_status,
            review_status=record.review_status, lifecycle_status=record.lifecycle_status,
            reviewer_decision_status=record.reviewer_decision_status,
            created_at=created_iso, database_write_at=created_iso,
            reasons=["created one review-gated, internal-only internal_report_review_packets row "
                     "(a pre-decision reviewer packet, not a review outcome)"],
            **_counts_from(record))

    except SQLAlchemyError as exc:  # infrastructure failure
        try:
            session.rollback()
        except Exception:  # noqa: BLE001 - rollback best-effort; never re-raise here
            pass
        safe = type(exc).__name__  # never leak SQL / connection / packet content details
        if attempted_commit:
            return InternalReportReviewPacketWriteReceipt(
                outcome=InternalReportReviewPacketWriteOutcome.WRITE_OUTCOME_UNCERTAIN,
                permitted=True, reason_code="commit_uncertain", idempotency_key=idem,
                database_connection_made=True, sql_execution_made=True,
                database_write_made=False, stored_record_created=False,
                transaction_committed=False, outcome_uncertain=True,
                reasons=[f"commit outcome could not be confirmed ({safe}); a record may or "
                         "may not exist"])
        return InternalReportReviewPacketWriteReceipt(
            outcome=InternalReportReviewPacketWriteOutcome.FAILED_BEFORE_WRITE, permitted=True,
            reason_code="failed_before_write", idempotency_key=idem,
            database_connection_made=True, sql_execution_made=True,
            database_write_made=False, stored_record_created=False,
            transaction_committed=False, outcome_uncertain=False,
            reasons=[f"infrastructure failure before any write ({safe}); no row created"])
    finally:
        session.close()
