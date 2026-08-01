"""Controlled DB writer for internal report review packet decisions (Phase 39).

The **eleventh** narrow live DB writer. It persists **exactly one**
``internal_report_review_packet_decisions`` row from an
:class:`InternalReportReviewPacketDecisionDraft`, through the Phase 17 ``ControlledWriteRequest``
boundary, allowing only ``internal_report_review_packet_decisions`` /
``create_internal_report_review_packet_decision``.

A row is a Peak human reviewer's **internal-only decision** on a Phase 38
``internal_report_review_packets`` row, preserving the audit chain
packet -> report draft -> report plan.

**Why a separate table rather than the Phase 33 writer.** The Phase 33
``internal_reviewer_decision_records`` writer cannot represent this artifact: it hard-requires a
review-bundle reference (a packet decision has none), and its explicit record mapping has a closed
``details_json`` key set with no slot for packet / report-draft / plan linkage, so that provenance
would be silently dropped. A decision written that way could not answer *which review packet was
this decision about?*

**A decision is internal only.** ``decision_scope`` is fixed at ``internal_report_review_packet``
and ``audience`` at ``internal``. ``ready_for_internal_use`` is **not** client-facing approval.
Nothing here approves anything for client use, verifies a financial claim, publishes a capsule, or
executes anything.

**This writer mutates nothing else.** It reads the stored ``Engagement``, the stored packet, and
the stored report draft, and inserts one decision row. It never updates the packet row, never
updates the report draft row, calls no Phase 22 review writer, and creates no ``review_records`` /
``agent_run_records`` row.

**What is never stored or echoed:** final client-facing language, raw intake-note / packet /
evidence / interview text, source bytes, generated agent output, LLM prompts, credentials or
secrets, DSNs, raw SQL, stack traces, client-facing approvals, ROI or savings figures, capsule
payloads, and AgentNet publish payloads. Denial reasons report only a field name, an item position,
or a marker *category* — never the offending value.

See docs/INTERNAL_REPORT_REVIEW_PACKET_DECISION_CONTROLLED_WRITER.md and
docs/INTERNAL_REPORT_REVIEW_PACKET_DECISION_IDEMPOTENCY_POLICY.md.
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
# Public, DB-free Phase 32 decision vocabulary + value classifier (neither imports peak.db).
from peak.reviewer_decisions.contracts import ALLOWED_DECISION_INTENTS
from peak.reviewer_decisions.governance import classify_prohibited_value_marker

from .models import (
    Engagement,
    InternalAssessmentReportDraftRecord,
    InternalReportReviewPacketDecisionRecord,
    InternalReportReviewPacketRecord,
)
from .session import create_session_factory
from .writer_contracts import (
    PACKET_DECISION_SCOPE,
    PACKET_DECISION_SOURCE_PACKET_TABLE,
    PACKET_DECISION_SOURCE_REPORT_DRAFT_TABLE,
    PACKET_DECISION_STATUS_NEEDS_FOLLOWUP,
    PACKET_DECISION_STATUS_RECORDED,
    PACKET_DECISION_TARGET_ACTION,
    PACKET_DECISION_TARGET_TABLE,
    InternalReportReviewPacketDecisionDraft,
    InternalReportReviewPacketDecisionWriteOutcome,
    InternalReportReviewPacketDecisionWriteReceipt,
)

BLOCKED_LIFECYCLE_STATUSES = frozenset({"revoked", "archived", "deleted_reference_only"})
SUPPORTED_SUBJECT_TYPES = frozenset({"engagement"})

AUDIENCE_INTERNAL = "internal"
# The governed Phase 9 axes stay inside their vocabulary; the decision-specific axis is separate.
REQUIRED_REVIEW_STATUS = "needs_review"
REQUIRED_LIFECYCLE_STATUS = "draft"

# The stored Phase 38 packet posture a decision may be recorded against.
REQUIRED_PACKET_STATUS = "ready_for_internal_review"
REQUIRED_PACKET_REVIEW_STATUS = "needs_review"
REQUIRED_PACKET_LIFECYCLE_STATUS = "draft"
REQUIRED_PACKET_DECISION_STATUS = "not_decided"
# The stored Phase 37 report-draft posture (mirrors that writer).
REQUIRED_DRAFT_OUTPUT_STATUS = "plan_persisted"
REQUIRED_DRAFT_REVIEW_STATUS = "needs_review"
REQUIRED_DRAFT_LIFECYCLE_STATUS = "draft"

#: Intents that leave open work. Everything else in the closed vocabulary records a decision.
#: This mapping is server-side and deterministic — ``decision_status`` is never caller-supplied.
NEEDS_FOLLOWUP_INTENTS = frozenset({
    "needs_more_evidence", "return_for_revision", "blocked_by_scope", "blocked_by_quality",
    "blocked_by_missing_source", "defer_review",
})

# Bounds (documented in docs/INTERNAL_REPORT_REVIEW_PACKET_DECISION_CONTROLLED_WRITER.md).
MAX_REF_LEN = 128
MAX_SUMMARY_LEN = 240
MAX_REASON_LEN = 500
MAX_FOLLOWUP_ACTIONS = 200
MAX_NOTES = 100
_ID_PREFIX = "irrpd_"

# Posture flags that must be false on the draft and are hard-coded false on the stored row.
REQUIRED_FALSE_FLAGS = (
    "client_facing_approved", "review_approval_made", "financial_verified",
    "capsule_candidate_ready", "publication_allowed", "execution_allowed",
)

ALLOWED_ACTION_STATUSES = frozenset({"open", "in_progress", "blocked", "done"})
FOLLOWUP_KEYS = frozenset({"action_id", "status"})

#: Prohibited attribute-name markers, scanned only on *unexpected* draft attributes.
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

#: Client-facing / approval / publication / execution language markers for the prose-ish fields.
PROHIBITED_INTENT_MARKERS = (
    "send to client", "send to the client", "client deliverable", "client-facing deliverable",
    "final report", "final client", "approve for client", "approved for client",
    "sign off", "sign-off", "publish capsule", "publish to agentnet", "roi of", "verified savings",
    "run the agent", "call the llm", "resolver lookup",
)

_SAFE_REF_RE = re.compile(r"^[A-Za-z0-9_.:/\-]{1,128}$")
_STACKTRACE_RE = re.compile(
    r"traceback \(most recent call last\)|File \"[^\"]+\", line \d+", re.IGNORECASE)
_JSON_KEYVALUE_RE = re.compile(r'"[^"\n]{1,64}"\s*:')


def _is_blank(value) -> bool:
    return value is None or (isinstance(value, str) and not value.strip())


def _deny(reason_code: str, message: str,
          **flags) -> InternalReportReviewPacketDecisionWriteReceipt:
    receipt = InternalReportReviewPacketDecisionWriteReceipt(
        outcome=InternalReportReviewPacketDecisionWriteOutcome.DENIED, permitted=False,
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
    if not isinstance(value, str):
        return None
    low = value.lower()
    if any(marker in low for marker in PROHIBITED_INTENT_MARKERS):
        return "client-facing/approval/execution intent"
    return None


def _safe_name(name) -> str:
    if isinstance(name, str) and re.match(r"^[A-Za-z0-9_.\-]{1,64}$", name):
        return name
    return "<unsafe-field-name>"


def _ref_ok(value) -> bool:
    return isinstance(value, str) and bool(_SAFE_REF_RE.match(value))


def _safe_str_list(values, limit: int) -> List[str]:
    return [v for v in (values or []) if isinstance(v, str) and v.strip()][:limit]


def _decision_status_for(intent: str) -> str:
    """Server-derived decision axis. Deterministic; never caller-supplied."""
    return (PACKET_DECISION_STATUS_NEEDS_FOLLOWUP if intent in NEEDS_FOLLOWUP_INTENTS
            else PACKET_DECISION_STATUS_RECORDED)


# --------------------------------------------------------------------------- draft safety


def _unexpected_attr_names(draft) -> List[str]:
    declared = set(getattr(type(draft), "__dataclass_fields__", {}))
    own = getattr(draft, "__dict__", None) or {}
    return [k for k in own if isinstance(k, str) and k not in declared]


def _draft_key_denial(draft) -> Optional[Tuple[str, str]]:
    for name in sorted(_unexpected_attr_names(draft)):
        low = name.lower()
        if any(marker in low for marker in PROHIBITED_KEY_MARKERS):
            return ("prohibited_decision_key",
                    f"decision draft carries a prohibited attribute '{_safe_name(name)}'")
    return None


def _draft_posture_denial(draft) -> Optional[Tuple[str, str]]:
    if draft.audience != AUDIENCE_INTERNAL:
        return ("prohibited_audience",
                "draft.audience must be 'internal' (this writer persists no client-facing artifact)")
    for flag in REQUIRED_FALSE_FLAGS:
        if getattr(draft, flag, False) is not False:
            return ("prohibited_posture",
                    f"draft.{flag} must be false (this writer approves nothing for client use, "
                    "verifies nothing financially, publishes nothing, and executes nothing)")
    if getattr(draft, "requires_human_review", True) is not True:
        return ("prohibited_posture", "draft.requires_human_review must be true")
    return None


def _draft_content_denial(draft) -> Optional[Tuple[str, str]]:
    """Verify every persisted reference/label is short, safe, and marker-free."""
    # 1. Reference/label scalars.
    for name in ("internal_report_review_packet_id", "internal_assessment_report_draft_id",
                 "report_plan_id", "reviewer_ref"):
        value = getattr(draft, name, None)
        if value is None:
            continue
        if not _ref_ok(value):
            return ("unsafe_decision_reference",
                    f"draft.{name} is not a short safe reference (value not echoed)")
        if _value_marker(value) is not None:
            return ("prohibited_decision_value",
                    f"draft.{name} carries a {_value_marker(value)} marker (value not echoed)")

    # 2. Follow-up actions — strict dicts with a closed status vocabulary.
    actions = getattr(draft, "requested_followup_actions", None)
    if not isinstance(actions, list):
        return ("invalid_decision_field", "draft.requested_followup_actions must be a list")
    for index, item in enumerate(actions[:MAX_FOLLOWUP_ACTIONS]):
        base = f"requested_followup_actions[{index}]"
        if not isinstance(item, dict):
            return ("invalid_decision_field", f"draft.{base} must be a dict")
        extra = set(item) - FOLLOWUP_KEYS
        if extra:
            return ("prohibited_decision_key",
                    f"draft.{base} carries unexpected key(s): "
                    + ", ".join(sorted(_safe_name(k) for k in extra)))
        missing = FOLLOWUP_KEYS - set(item)
        if missing:
            return ("invalid_decision_field",
                    f"draft.{base} is missing key(s): " + ", ".join(sorted(missing)))
        for key, value in item.items():
            if not _ref_ok(value):
                return ("unsafe_decision_reference",
                        f"draft.{base}.{_safe_name(key)} is not a short safe label "
                        "(value not echoed)")
            if _value_marker(value) is not None:
                return ("prohibited_decision_value",
                        f"draft.{base}.{_safe_name(key)} carries a "
                        f"{_value_marker(value)} marker (value not echoed)")
        if item["status"] not in ALLOWED_ACTION_STATUSES:
            return ("invalid_decision_status_value",
                    f"draft.{base}.status is not an allowed internal action status "
                    "(approval/publication/financial statuses are never accepted)")

    # 3. The one prose-ish field plus bounded notes — marker- and intent-scanned.
    summary = getattr(draft, "safe_decision_summary", None)
    if summary is not None:
        if not isinstance(summary, str):
            return ("invalid_decision_field", "draft.safe_decision_summary must be a string")
        if "\n" in summary or "\r" in summary or len(summary) > MAX_SUMMARY_LEN:
            return ("unsafe_decision_reference",
                    "draft.safe_decision_summary must be a short single-line internal note")
        if _value_marker(summary, strict_json=False) is not None:
            return ("prohibited_decision_value",
                    f"draft.safe_decision_summary carries a "
                    f"{_value_marker(summary, strict_json=False)} marker (value not echoed)")
        if _intent_marker(summary) is not None:
            return ("prohibited_decision_intent_language",
                    "draft.safe_decision_summary carries client-facing/approval/execution intent "
                    "(value not echoed)")
    for field_name in ("reasons", "warnings"):
        values = getattr(draft, field_name, None)
        if not isinstance(values, list):
            return ("invalid_decision_field", f"draft.{field_name} must be a list")
        for index, value in enumerate(values):
            if not isinstance(value, str):
                return ("invalid_decision_field", f"draft.{field_name}[{index}] must be a string")
            if "\n" in value or "\r" in value or len(value) > MAX_REASON_LEN:
                return ("unsafe_decision_reference",
                        f"draft.{field_name}[{index}] must be a short single-line note")
            if _value_marker(value, strict_json=False) is not None:
                return ("prohibited_decision_value",
                        f"draft.{field_name}[{index}] carries a "
                        f"{_value_marker(value, strict_json=False)} marker (value not echoed)")
            if _intent_marker(value) is not None:
                return ("prohibited_decision_intent_language",
                        f"draft.{field_name}[{index}] carries client-facing/approval/execution "
                        "intent (value not echoed)")
    return None


def _draft_bounds_denial(draft) -> Optional[Tuple[str, str]]:
    for field_name, limit in (("requested_followup_actions", MAX_FOLLOWUP_ACTIONS),
                              ("reasons", MAX_NOTES), ("warnings", MAX_NOTES)):
        if len(getattr(draft, field_name, None) or []) > limit:
            return ("decision_too_large",
                    f"decision draft carries more than {limit} {field_name}")
    return None


def _identity_mismatches(request, draft) -> List[str]:
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
) -> Tuple[Optional[InternalReportReviewPacketDecisionWriteReceipt],
           Optional[InternalReportReviewPacketDecisionDraft]]:
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

    if getattr(request, "target_table", None) != PACKET_DECISION_TARGET_TABLE:
        return _deny("wrong_target_table",
                     f"target_table must be '{PACKET_DECISION_TARGET_TABLE}'"), None
    if getattr(request, "requested_action", None) != PACKET_DECISION_TARGET_ACTION:
        return _deny("wrong_target_action",
                     f"requested_action must be '{PACKET_DECISION_TARGET_ACTION}'"), None

    draft = getattr(request, "record_draft", None)
    if not isinstance(draft, InternalReportReviewPacketDecisionDraft):
        return _deny("invalid_record_draft",
                     "record_draft is not an InternalReportReviewPacketDecisionDraft"), None

    if getattr(draft, "decision_record_id", None) is not None:
        return _deny("caller_supplied_id",
                     "draft.decision_record_id must be None (server-controlled)"), None
    if getattr(draft, "created_at", None) is not None:
        return _deny("caller_supplied_timestamp",
                     "draft.created_at must be None (server-stamped created_at is "
                     "authoritative)"), None

    for check in (_draft_key_denial, _draft_posture_denial, _draft_bounds_denial,
                  _draft_content_denial):
        denial = check(draft)
        if denial is not None:
            return _deny(denial[0], denial[1]), None

    # Decision intent: the closed Phase 32 internal-only vocabulary. Approval-like, client-facing,
    # publication, financial, and execution intents are never in that set, so they are denied here.
    intent = getattr(draft, "decision_intent", None)
    if _is_blank(intent):
        return _deny("missing_decision_intent", "draft.decision_intent is required"), None
    if intent not in ALLOWED_DECISION_INTENTS:
        return _deny("disallowed_decision_intent",
                     f"draft.decision_intent '{_safe_name(intent)}' is not an allowed internal "
                     "decision intent (approval / client-facing / publication / financial / "
                     "execution intents are denied)"), None

    # Required audit-chain refs.
    for attr in ("internal_report_review_packet_id", "internal_assessment_report_draft_id",
                 "report_plan_id"):
        if _is_blank(getattr(draft, attr, None)):
            return _deny("missing_linkage_ref", f"draft.{attr} is required"), None
    if _is_blank(getattr(draft, "plan_fingerprint", None)):
        return _deny("missing_plan_fingerprint", "draft.plan_fingerprint is required"), None
    for attr in ("plan_fingerprint", "report_draft_payload_fingerprint",
                 "packet_payload_fingerprint"):
        value = getattr(draft, attr, None)
        if value is not None and not re.fullmatch(r"[0-9a-f]{64}", str(value)):
            return _deny("invalid_fingerprint",
                         f"draft.{attr} must be a 64-character sha256 hex digest"), None

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


def _stored_packet_denial(packet, request, draft):
    """Verify the **stored** Phase 38 packet's tenant, scope, linkage, and pre-decision posture."""
    if packet is None:
        return ("missing_packet", "stored internal report review packet not found")
    for attr in ("owner_id", "client_id", "engagement_id", "authorization_scope"):
        if getattr(packet, attr, None) != getattr(request, attr, None):
            return ("packet_identity_mismatch",
                    f"stored packet {attr} does not match request.{attr}")
    for attr in ("internal_assessment_report_draft_id", "report_plan_id", "plan_fingerprint"):
        if getattr(packet, attr, None) != getattr(draft, attr, None):
            return ("packet_linkage_mismatch",
                    f"stored packet {attr} does not match the decision draft's {attr}")
    supplied = getattr(draft, "packet_payload_fingerprint", None)
    if supplied is not None and supplied != getattr(packet, "payload_fingerprint", None):
        return ("packet_linkage_mismatch",
                "draft.packet_payload_fingerprint does not match the stored packet's "
                "payload_fingerprint")
    if getattr(packet, "audience", None) != AUDIENCE_INTERNAL:
        return ("packet_not_internal", "stored packet audience is not 'internal'")
    if getattr(packet, "packet_status", None) != REQUIRED_PACKET_STATUS:
        return ("packet_invalid_status",
                f"stored packet packet_status must be '{REQUIRED_PACKET_STATUS}'")
    if getattr(packet, "review_status", None) != REQUIRED_PACKET_REVIEW_STATUS:
        return ("packet_invalid_review_status",
                f"stored packet review_status must be '{REQUIRED_PACKET_REVIEW_STATUS}'")
    if getattr(packet, "lifecycle_status", None) != REQUIRED_PACKET_LIFECYCLE_STATUS:
        return ("packet_invalid_lifecycle_status",
                f"stored packet lifecycle_status must be '{REQUIRED_PACKET_LIFECYCLE_STATUS}'")
    if getattr(packet, "reviewer_decision_status", None) != REQUIRED_PACKET_DECISION_STATUS:
        return ("packet_already_decided",
                f"stored packet reviewer_decision_status must be "
                f"'{REQUIRED_PACKET_DECISION_STATUS}'")
    if getattr(packet, "reviewer_decision_record_id", None) is not None:
        return ("packet_already_decided",
                "stored packet already carries a reviewer_decision_record_id")
    for flag in REQUIRED_FALSE_FLAGS:
        if getattr(packet, flag, False) is not False:
            return ("packet_posture_elevated", f"stored packet {flag} must be false")
    if getattr(packet, "requires_human_review", True) is not True:
        return ("packet_posture_elevated", "stored packet requires_human_review must be true")
    return None


def _stored_report_draft_denial(stored, request, packet, draft):
    """Verify the **stored** Phase 37 report draft the packet points at (defence in depth)."""
    if stored is None:
        return ("missing_report_draft", "stored internal assessment report draft not found")
    if stored.id != getattr(packet, "internal_assessment_report_draft_id", None):
        return ("report_draft_linkage_mismatch",
                "stored report draft id does not match the packet's report-draft reference")
    for attr in ("owner_id", "client_id", "engagement_id", "authorization_scope"):
        if getattr(stored, attr, None) != getattr(request, attr, None):
            return ("report_draft_identity_mismatch",
                    f"stored report draft {attr} does not match request.{attr}")
    for attr in ("report_plan_id", "plan_fingerprint"):
        if getattr(stored, attr, None) != getattr(draft, attr, None):
            return ("report_draft_linkage_mismatch",
                    f"stored report draft {attr} does not match the decision draft's {attr}")
    supplied = getattr(draft, "report_draft_payload_fingerprint", None)
    if supplied is not None and supplied != getattr(stored, "payload_fingerprint", None):
        return ("report_draft_linkage_mismatch",
                "draft.report_draft_payload_fingerprint does not match the stored report draft's "
                "payload_fingerprint")
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
    return None


# --------------------------------------------------------------------------- serialization


def _followup_payload(draft) -> List[dict]:
    return [{k: item[k] for k in sorted(FOLLOWUP_KEYS) if k in item}
            for item in (draft.requested_followup_actions or [])[:MAX_FOLLOWUP_ACTIONS]
            if isinstance(item, dict)]


def _payload_fingerprint(request, draft, decision_status: str,
                         report_draft_fp: Optional[str], packet_fp: Optional[str]) -> str:
    """A deterministic, canonical digest over the identity + the stored decision payload."""
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
        "internal_report_review_packet_id": draft.internal_report_review_packet_id,
        "source_packet_table": PACKET_DECISION_SOURCE_PACKET_TABLE,
        "internal_assessment_report_draft_id": draft.internal_assessment_report_draft_id,
        "source_report_draft_table": PACKET_DECISION_SOURCE_REPORT_DRAFT_TABLE,
        "report_plan_id": draft.report_plan_id,
        "plan_fingerprint": draft.plan_fingerprint,
        "report_draft_payload_fingerprint": report_draft_fp,
        "packet_payload_fingerprint": packet_fp,
        "reviewer_ref": draft.reviewer_ref,
        "decision_intent": draft.decision_intent,
        "safe_decision_summary": draft.safe_decision_summary,
        "requested_followup_actions": _followup_payload(draft),
        "decision_status": decision_status,
        "decision_scope": PACKET_DECISION_SCOPE,
        "audience": AUDIENCE_INTERNAL,
        "review_status": REQUIRED_REVIEW_STATUS,
        "lifecycle_status": REQUIRED_LIFECYCLE_STATUS,
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


def _build_record(request, draft, decision_status: str, report_draft_fp: Optional[str],
                  packet_fp: Optional[str],
                  fingerprint: str) -> InternalReportReviewPacketDecisionRecord:
    """Explicit field mapping — labels, statuses, and references only (no ``__dict__`` copy)."""
    return InternalReportReviewPacketDecisionRecord(
        id=_ID_PREFIX + uuid.uuid4().hex[:16],  # server-controlled
        owner_id=request.owner_id,
        client_id=request.client_id,
        engagement_id=request.engagement_id,
        authorization_scope=request.authorization_scope,  # validated == stored scope
        internal_report_review_packet_id=draft.internal_report_review_packet_id,
        source_packet_table=PACKET_DECISION_SOURCE_PACKET_TABLE,
        internal_assessment_report_draft_id=draft.internal_assessment_report_draft_id,
        source_report_draft_table=PACKET_DECISION_SOURCE_REPORT_DRAFT_TABLE,
        report_plan_id=draft.report_plan_id,
        plan_fingerprint=draft.plan_fingerprint,
        report_draft_payload_fingerprint=report_draft_fp,  # copied from the stored row
        packet_payload_fingerprint=packet_fp,              # copied from the stored row
        requested_by=request.requested_by,
        requester_role=request.requester_role,
        reviewer_ref=draft.reviewer_ref,
        decision_intent=draft.decision_intent,
        safe_decision_summary=draft.safe_decision_summary,
        requested_followup_actions_json=_followup_payload(draft),
        decision_status=decision_status,      # server-derived from decision_intent
        decision_scope=PACKET_DECISION_SCOPE,  # server-stamped
        audience=AUDIENCE_INTERNAL,            # server-stamped; internal only
        review_status=REQUIRED_REVIEW_STATUS,  # governed Phase 9 vocabulary (server-stamped)
        lifecycle_status=REQUIRED_LIFECYCLE_STATUS,
        reasons_json=_safe_str_list(draft.reasons, MAX_NOTES),
        warnings_json=_safe_str_list(draft.warnings, MAX_NOTES),
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
            "requested_followup_action_count": len(draft.requested_followup_actions or []),
        },
    )


def _find_existing(session, request, idem: str):
    return (
        session.query(InternalReportReviewPacketDecisionRecord)
        .filter_by(
            owner_id=request.owner_id,
            client_id=request.client_id,
            engagement_id=request.engagement_id,
            idempotency_key=idem,
        )
        .one_or_none()
    )


def _receipt_from_existing(existing, idem: str,
                           outcome: str) -> InternalReportReviewPacketDecisionWriteReceipt:
    details = getattr(existing, "details_json", None) or {}
    return InternalReportReviewPacketDecisionWriteReceipt(
        outcome=outcome, permitted=True, reason_code=outcome,
        stored_record_id=existing.id,
        internal_report_review_packet_id=existing.internal_report_review_packet_id,
        internal_assessment_report_draft_id=existing.internal_assessment_report_draft_id,
        report_plan_id=existing.report_plan_id, plan_fingerprint=existing.plan_fingerprint,
        decision_intent=existing.decision_intent,
        idempotency_key=idem, audit_trace_ref=existing.id,
        database_connection_made=True, sql_execution_made=True,
        database_write_made=False, stored_record_created=False,
        existing_record_returned=True, transaction_committed=False,
        audience=existing.audience, decision_scope=existing.decision_scope,
        decision_status=existing.decision_status, review_status=existing.review_status,
        lifecycle_status=existing.lifecycle_status,
        requested_followup_action_count=int(
            details.get("requested_followup_action_count")
            or len(existing.requested_followup_actions_json or [])),
        reasons=["exact authorized replay; existing record returned, not modified"])


def build_packet_decision_write_request(
    draft: InternalReportReviewPacketDecisionDraft,
    *,
    requested_by: str,
    requester_role: str,
    idempotency_key: str,
    subject: Optional[ControlledWriteSubject] = None,
    source_phase: str = "phase39",
    lifecycle_status: str = "active",
) -> ControlledWriteRequest:
    """Convenience planner: wrap a decision draft in a Phase 17 ``ControlledWriteRequest``.

    Targets exactly ``internal_report_review_packet_decisions`` /
    ``create_internal_report_review_packet_decision`` and opens no database connection.
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
        target_table=PACKET_DECISION_TARGET_TABLE,
        requested_action=PACKET_DECISION_TARGET_ACTION,
        subject=subject,
        record_draft=draft,
        source_phase=source_phase,
        lifecycle_status=lifecycle_status,
        idempotency_key=idempotency_key,
    )


def persist_internal_report_review_packet_decision(
    controlled_write_request,
    *,
    session_factory=None,
) -> InternalReportReviewPacketDecisionWriteReceipt:
    """Create one internal-only ``internal_report_review_packet_decisions`` row.

    ``session_factory`` is a zero-arg callable returning a SQLAlchemy ``Session`` (defaults to the
    controlled-DB session factory from the environment URL).

    Returns an :class:`InternalReportReviewPacketDecisionWriteReceipt`; expected governance
    failures are typed denials, not exceptions. Receipts and denial reasons **never echo report
    prose, raw content, credentials, DSNs, raw SQL, stack traces, ROI figures, or client-facing
    approvals**. This writer updates **no** packet or report-draft row, calls no Phase 22 review
    writer, and creates no ``review_records`` / ``agent_run_records`` row.
    """
    denial, draft = _pre_db_validate(controlled_write_request)
    if denial is not None:
        return denial

    request = controlled_write_request
    subject = request.subject
    idem = request.idempotency_key
    decision_status = _decision_status_for(draft.decision_intent)

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

        # --- Stored packet (read-only; never updated) ---
        packet = session.get(InternalReportReviewPacketRecord,
                             draft.internal_report_review_packet_id)
        packet_denial = _stored_packet_denial(packet, request, draft)
        if packet_denial is not None:
            return _deny(packet_denial[0], packet_denial[1],
                         database_connection_made=True, sql_execution_made=True)

        # --- Stored report draft (read-only; never updated) ---
        report_draft = session.get(InternalAssessmentReportDraftRecord,
                                   packet.internal_assessment_report_draft_id)
        draft_denial = _stored_report_draft_denial(report_draft, request, packet, draft)
        if draft_denial is not None:
            return _deny(draft_denial[0], draft_denial[1],
                         database_connection_made=True, sql_execution_made=True)

        packet_fp = packet.payload_fingerprint
        report_draft_fp = report_draft.payload_fingerprint
        fingerprint = _payload_fingerprint(request, draft, decision_status,
                                           report_draft_fp, packet_fp)

        # --- Idempotency pre-check (common replay path; race is covered below) ---
        existing = _find_existing(session, request, idem)
        if existing is not None:
            if existing.payload_fingerprint == fingerprint:
                return _receipt_from_existing(
                    existing, idem,
                    InternalReportReviewPacketDecisionWriteOutcome.IDEMPOTENT_REPLAY)
            return _deny("idempotency_conflict",
                         "idempotency key reused with a different payload/identity",
                         database_connection_made=True, sql_execution_made=True,
                         existing_record_returned=False)

        # --- Insert exactly one authorized row ---
        record = _build_record(request, draft, decision_status, report_draft_fp, packet_fp,
                               fingerprint)
        session.add(record)
        attempted_commit = True
        try:
            session.commit()
        except IntegrityError:
            session.rollback()
            raced = (
                session.query(InternalReportReviewPacketDecisionRecord)
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
                    raced, idem,
                    InternalReportReviewPacketDecisionWriteOutcome.IDEMPOTENT_REPLAY)
            if raced is not None:
                return _deny("idempotency_conflict",
                             "idempotency key reused with a different payload/identity (race)",
                             database_connection_made=True, sql_execution_made=True,
                             existing_record_returned=False)
            return InternalReportReviewPacketDecisionWriteReceipt(
                outcome=InternalReportReviewPacketDecisionWriteOutcome.WRITE_OUTCOME_UNCERTAIN,
                permitted=True, reason_code="integrity_no_row", idempotency_key=idem,
                database_connection_made=True, sql_execution_made=True,
                database_write_made=False, stored_record_created=False,
                transaction_committed=False, outcome_uncertain=True,
                reasons=["integrity conflict without a matching row; write outcome uncertain"])

        session.refresh(record)  # load server-stamped created_at/updated_at
        created_iso = record.created_at.isoformat() if record.created_at else None
        return InternalReportReviewPacketDecisionWriteReceipt(
            outcome=InternalReportReviewPacketDecisionWriteOutcome.CREATED, permitted=True,
            reason_code="created",
            stored_record_id=record.id,
            internal_report_review_packet_id=record.internal_report_review_packet_id,
            internal_assessment_report_draft_id=record.internal_assessment_report_draft_id,
            report_plan_id=record.report_plan_id, plan_fingerprint=record.plan_fingerprint,
            decision_intent=record.decision_intent,
            idempotency_key=idem, audit_trace_ref=record.id,
            database_connection_made=True, sql_execution_made=True,
            database_write_made=True, stored_record_created=True,
            existing_record_returned=False, transaction_committed=True, outcome_uncertain=False,
            audience=record.audience, decision_scope=record.decision_scope,
            decision_status=record.decision_status, review_status=record.review_status,
            lifecycle_status=record.lifecycle_status,
            requested_followup_action_count=len(record.requested_followup_actions_json or []),
            created_at=created_iso, database_write_at=created_iso,
            reasons=["created one internal-only internal_report_review_packet_decisions row "
                     "(no packet or report-draft row was modified)"])

    except SQLAlchemyError as exc:  # infrastructure failure
        try:
            session.rollback()
        except Exception:  # noqa: BLE001 - rollback best-effort; never re-raise here
            pass
        safe = type(exc).__name__  # never leak SQL / connection / decision content details
        if attempted_commit:
            return InternalReportReviewPacketDecisionWriteReceipt(
                outcome=InternalReportReviewPacketDecisionWriteOutcome.WRITE_OUTCOME_UNCERTAIN,
                permitted=True, reason_code="commit_uncertain", idempotency_key=idem,
                database_connection_made=True, sql_execution_made=True,
                database_write_made=False, stored_record_created=False,
                transaction_committed=False, outcome_uncertain=True,
                reasons=[f"commit outcome could not be confirmed ({safe}); a record may or "
                         "may not exist"])
        return InternalReportReviewPacketDecisionWriteReceipt(
            outcome=InternalReportReviewPacketDecisionWriteOutcome.FAILED_BEFORE_WRITE,
            permitted=True, reason_code="failed_before_write", idempotency_key=idem,
            database_connection_made=True, sql_execution_made=True,
            database_write_made=False, stored_record_created=False,
            transaction_committed=False, outcome_uncertain=False,
            reasons=[f"infrastructure failure before any write ({safe}); no row created"])
    finally:
        session.close()
