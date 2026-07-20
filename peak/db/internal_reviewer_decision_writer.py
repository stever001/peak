"""Phase 33 — the controlled DB writer for ``internal_reviewer_decision_records``.

The seventh narrow live DB writer in Peak (after the Phase 20 ``agent_run_records``, Phase 21
``evidence_references``, Phase 22 ``review_records``, Phase 24 ``source_ingestion_records``, Phase
27 ``agent_task_queue_records``, and Phase 30 ``review_bundle_records`` writers). It accepts an
approved Phase 17 controlled-write request whose ``record_draft`` is a Phase 32
``InternalReviewerDecisionDraft`` and creates **exactly one** ``internal_reviewer_decision_records``
row — nothing else. It is a narrow internal persistence boundary, not a generic decision engine,
review engine, workflow engine, or CRUD repository.

**Non-approval.** This writer never approves anything (no ``approve_internal``), never calls the
Phase 22 review writer, and **never creates a ``review_records`` row**. It never executes an agent
(live or mock), never calls the Phase 13 executor / MockLLM / a live LLM / AgentNet / MCP /
resolver / connector / network, never creates an ``agent_run_records`` row, and produces no
client-facing output, financial verification, or capsule publication. It stores **review-gated,
non-approval** internal reviewer decision records only — every review/approval-posture flag on the
stored row is the not-approved / not-allowed / needs-review posture. **``ready_for_internal_use``
is not approval**: it does not authorize client-facing output, financial verification, capsule
publication, agent execution, or a ``review_records`` write.

Mandatory write-time rule: the writer does **not** trust the Phase 32 request or draft as proof
of authorization. At write time it loads the authoritative stored authorization subject (the
``Engagement`` row) from the database and requires
``request.authorization_scope == engagement.authorization_scope``. Identity matching (owner,
client, engagement) is necessary but **not sufficient**; a scope mismatch is denied even when
every identity matches. Missing stored scope and missing request scope are denied.

Content rule: only **safe references, safe summaries, routing labels, and safe metadata** are
persisted (owner/client/engagement, review-bundle refs, source/evidence/task-queue/review-plan ids,
reviewer_role, decision_intent, decision_reason_code, safe_decision_summary, return_to_stage,
route_to, requested_followup_actions, authorization_scope, statuses, posture booleans,
reasons/warnings) — **never** the raw packet payload, raw evidence/interview text, source file
bytes, generated agent output, arbitrary client content, credentials/secrets, a final review
approval/decision, stack traces, DB URLs, or raw SQL. A draft carrying such an attribute is
rejected without echoing the value, and a summary/followup label carrying a credential/DB-URL/
raw-SQL/raw-content marker is rejected (marker category only is reported, never the value).

Side-effect boundary: this module performs only the DB work needed to read the stored subject,
check idempotency, insert the authorized row, read it back, and commit/roll back. It may import
SQLAlchemy and ``peak.db`` (this is the DB layer). See
docs/INTERNAL_REVIEWER_DECISION_CONTROLLED_WRITER.md and
docs/INTERNAL_REVIEWER_DECISION_IDEMPOTENCY_POLICY.md.
"""

from __future__ import annotations

import hashlib
import json
import uuid
from typing import List, Optional, Tuple

from sqlalchemy.exc import IntegrityError, SQLAlchemyError

# Concrete input contracts (isinstance-checked, not duck-typed). Phase 32 is DB-free/stdlib, so
# importing its contracts/governance opens no database connection and pulls in no ORM.
from peak.persistence.contracts import ControlledWriteRequest, ControlledWriteSubject
from peak.persistence.write_plan import prepare_controlled_write
from peak.reviewer_decisions.contracts import (
    ALLOWED_DECISION_INTENTS,
    ALLOWED_RETURN_STAGES,
    DEFAULT_LIFECYCLE_STATUS,
    DEFAULT_OUTPUT_STATUS,
    DEFAULT_REVIEW_STATUS,
    INTENT_ROUTING,
    RETURN_FOR_REVISION,
    InternalReviewerDecisionDraft,
)
from peak.reviewer_decisions.governance import classify_prohibited_value_marker

from .models import Engagement, InternalReviewerDecisionRecord
from .session import create_session_factory
from .writer_contracts import (
    INTERNAL_REVIEWER_DECISION_TARGET_ACTION,
    INTERNAL_REVIEWER_DECISION_TARGET_TABLE,
    InternalReviewerDecisionWriteOutcome,
    InternalReviewerDecisionWriteReceipt,
)

BLOCKED_LIFECYCLE_STATUSES = frozenset({"revoked", "archived", "deleted_reference_only"})
SUPPORTED_SUBJECT_TYPES = frozenset({"engagement"})
REQUIRED_OUTPUT_STATUS = DEFAULT_OUTPUT_STATUS      # "draft"
REQUIRED_REVIEW_STATUS = DEFAULT_REVIEW_STATUS      # "needs_review"
REQUIRED_LIFECYCLE_STATUS = DEFAULT_LIFECYCLE_STATUS  # "draft"
_MAX_SUMMARY_LEN = 240  # a decision summary is a short single-line reviewer note

# Attributes a draft must never carry (raw content / generated output / a secret / an approval
# decision / a DB artifact). NOTE: legitimate ``decision_*`` fields on the draft are allowlisted in
# _SAFE_DRAFT_ATTRS and are skipped before substring matching, so "decision"/"approval" terms here
# only ever match injected attributes.
FORBIDDEN_CONTENT_SUBSTRINGS = (
    "packet_payload", "raw_packet", "raw_content", "raw_evidence", "evidence_text",
    "raw_interview", "interview_text", "source_bytes", "file_bytes", "raw_source",
    "generated_output", "agent_output", "llm_output", "llm_prompt", "prompt_text", "payload",
    "raw_sql", "sql_statement", "stack_trace", "traceback", "connection_string", "database_url",
    "db_url", "approval_decision", "approval_note", "final_decision", "signoff", "sign_off",
    "approve",
)
SECRET_TERMS = (
    "password", "secret", "api_key", "apikey", "token", "private_key", "privatekey",
    "credential", "access_key",
)
# Draft attributes that are legitimate and must never be flagged by the content scan.
_SAFE_DRAFT_ATTRS = frozenset({
    "reviewer_decision_id", "owner_id", "client_id", "engagement_id", "review_bundle_ref",
    "review_bundle_record_id", "review_bundle_draft_ref", "review_plan_item_refs",
    "evidence_reference_ids", "source_ingestion_record_ids", "agent_task_queue_record_ids",
    "reviewer_role", "decision_intent", "decision_reason_code", "safe_decision_summary",
    "return_to_stage", "requested_followup_actions", "authorization_scope", "output_status",
    "review_status", "lifecycle_status", "authoritative", "client_facing_approved",
    "capsule_candidate_ready", "financial_verified", "execution_allowed", "approval_allowed",
    "publication_allowed", "requires_human_review", "client_facing_output_created",
    "review_approval_made", "reasons", "warnings", "created_at",
})
_ID_PREFIX = "ird_"


def _is_blank(value) -> bool:
    return value is None or (isinstance(value, str) and not value.strip())


def _deny(reason_code: str, message: str, **flags) -> InternalReviewerDecisionWriteReceipt:
    receipt = InternalReviewerDecisionWriteReceipt(
        outcome=InternalReviewerDecisionWriteOutcome.DENIED, permitted=False,
        reason_code=reason_code, reasons=[message])
    for key, val in flags.items():
        setattr(receipt, key, val)
    return receipt


def _forbidden_content_attr(draft) -> Optional[str]:
    """Return a draft attribute name that would embed raw content / a decision / a secret, or None.

    Only attribute *names* are inspected/returned — never values, so no secret is echoed. Any
    attribute outside the known-safe set that matches a forbidden or secret term is rejected.
    """
    names = getattr(draft, "__dict__", {}) or {}
    for name in names:
        if name in _SAFE_DRAFT_ATTRS:
            continue
        low = str(name).lower()
        if any(term in low for term in FORBIDDEN_CONTENT_SUBSTRINGS):
            return name
        if any(term in low for term in SECRET_TERMS):
            return name
    return None


def _value_content_denial(draft) -> Optional[Tuple[str, str]]:
    """Return (reason_code, message) if a summary/followup *value* carries an unsafe marker.

    Reuses the Phase 32 non-echoing value scanner: only the marker *category* is reported, never
    the offending value. Also enforces the short-single-line shape for the summary.
    """
    summary = getattr(draft, "safe_decision_summary", None)
    if isinstance(summary, str):
        if "\n" in summary or "\r" in summary or len(summary) > _MAX_SUMMARY_LEN:
            return ("blocked_raw_content",
                    "safe_decision_summary must be a short single-line note, not raw content")
        cat = classify_prohibited_value_marker(summary)
        if cat is not None:
            code = "blocked_secret_like_content" if cat == "credential/secret" else "blocked_raw_content"
            return (code, f"safe_decision_summary contains a prohibited {cat} marker")
    for i, lbl in enumerate(getattr(draft, "requested_followup_actions", None) or []):
        if not isinstance(lbl, str):
            continue
        cat = classify_prohibited_value_marker(lbl)
        if cat is not None:
            code = "blocked_secret_like_content" if cat == "credential/secret" else "blocked_raw_content"
            return (code, f"requested_followup_actions[{i}] contains a prohibited {cat} marker")
    return None


def _route_for(draft: InternalReviewerDecisionDraft) -> str:
    """Deterministic route recommendation for the draft's decision intent (mirrors Phase 32).

    ``return_for_revision`` is refined by a safe ``return_to_stage`` into ``"<stage>_revision"``.
    """
    intent = getattr(draft, "decision_intent", None)
    if intent == RETURN_FOR_REVISION:
        stage = getattr(draft, "return_to_stage", None)
        if stage in ALLOWED_RETURN_STAGES:
            return f"{stage}_revision"
        return INTENT_ROUTING[RETURN_FOR_REVISION]
    return INTENT_ROUTING.get(intent, "review_backlog")


def _safe_list(value) -> List[str]:
    return [v for v in (value or []) if isinstance(v, str)]


def _payload_fingerprint(request: ControlledWriteRequest,
                         draft: InternalReviewerDecisionDraft, route_to: str) -> str:
    """Deterministic, canonical fingerprint of the write payload + identity (replay-conflict).

    Safe references/metadata only — no raw content participates.
    """
    payload = {
        "owner_id": request.owner_id,
        "client_id": request.client_id,
        "engagement_id": request.engagement_id,
        "review_bundle_ref": getattr(draft, "review_bundle_ref", None),
        "review_bundle_record_id": getattr(draft, "review_bundle_record_id", None),
        "review_bundle_draft_ref": getattr(draft, "review_bundle_draft_ref", None),
        "review_plan_item_refs": _safe_list(getattr(draft, "review_plan_item_refs", None)),
        "evidence_reference_ids": _safe_list(getattr(draft, "evidence_reference_ids", None)),
        "source_ingestion_record_ids": _safe_list(getattr(draft, "source_ingestion_record_ids", None)),
        "agent_task_queue_record_ids": _safe_list(getattr(draft, "agent_task_queue_record_ids", None)),
        "reviewer_role": getattr(draft, "reviewer_role", None),
        "decision_intent": getattr(draft, "decision_intent", None),
        "decision_reason_code": getattr(draft, "decision_reason_code", None),
        "safe_decision_summary": getattr(draft, "safe_decision_summary", None),
        "return_to_stage": getattr(draft, "return_to_stage", None),
        "requested_followup_actions": _safe_list(getattr(draft, "requested_followup_actions", None)),
        "route_to": route_to,
        "routing_reason_code": getattr(draft, "routing_reason_code", None),
        "authorization_scope": getattr(draft, "authorization_scope", None),
        "output_status": getattr(draft, "output_status", None),
        "review_status": getattr(draft, "review_status", None),
        "lifecycle_status": getattr(draft, "lifecycle_status", None),
        "authoritative": bool(getattr(draft, "authoritative", False)),
        "client_facing_approved": bool(getattr(draft, "client_facing_approved", False)),
        "capsule_candidate_ready": bool(getattr(draft, "capsule_candidate_ready", False)),
        "financial_verified": bool(getattr(draft, "financial_verified", False)),
        "execution_allowed": bool(getattr(draft, "execution_allowed", False)),
        "approval_allowed": bool(getattr(draft, "approval_allowed", False)),
        "publication_allowed": bool(getattr(draft, "publication_allowed", False)),
        "requires_human_review": bool(getattr(draft, "requires_human_review", True)),
        "client_facing_output_created": bool(getattr(draft, "client_facing_output_created", False)),
        "review_approval_made": bool(getattr(draft, "review_approval_made", False)),
    }
    blob = json.dumps(payload, sort_keys=True, separators=(",", ":"), default=str)
    return hashlib.sha256(blob.encode("utf-8")).hexdigest()


def _identity_mismatches(request: ControlledWriteRequest,
                         draft: InternalReviewerDecisionDraft) -> List[str]:
    """Independently compare identity across the request, draft, and engagement subject.
    Necessary, not sufficient — the DB stored-scope check is the authorization gate."""
    mismatches: List[str] = []
    subject = getattr(request, "subject", None)
    for attr in ("owner_id", "client_id", "engagement_id"):
        req_val = getattr(request, attr, None)
        if getattr(draft, attr, None) != req_val:
            mismatches.append(f"draft.{attr} does not match request.{attr}")
        if subject is not None and getattr(subject, attr, None) != req_val:
            mismatches.append(f"subject.{attr} does not match request.{attr}")
    # Draft scope must also match the request scope (necessary but not sufficient).
    if getattr(draft, "authorization_scope", None) != getattr(request, "authorization_scope", None):
        mismatches.append("draft.authorization_scope does not match request.authorization_scope")
    return mismatches


def _pre_db_validate(
    request,
) -> Tuple[Optional[InternalReviewerDecisionWriteReceipt], Optional[InternalReviewerDecisionDraft]]:
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
    plan = getattr(plan_result, "write_plan", None)
    if plan is None or getattr(plan, "requires_controlled_db_writer", False) is not True:
        return _deny("writer_not_required",
                     "controlled-write plan does not require the controlled DB writer"), None

    if getattr(request, "target_table", None) != INTERNAL_REVIEWER_DECISION_TARGET_TABLE:
        return _deny("wrong_target_table",
                     f"target_table must be '{INTERNAL_REVIEWER_DECISION_TARGET_TABLE}'"), None
    if getattr(request, "requested_action", None) != INTERNAL_REVIEWER_DECISION_TARGET_ACTION:
        return _deny("wrong_target_action",
                     f"requested_action must be '{INTERNAL_REVIEWER_DECISION_TARGET_ACTION}'"), None

    draft = getattr(request, "record_draft", None)
    if not isinstance(draft, InternalReviewerDecisionDraft):
        return _deny("invalid_record_draft",
                     "record_draft is not an InternalReviewerDecisionDraft"), None

    # Content rule (attribute names): reject any embedded raw content / decision / secret.
    forbidden = _forbidden_content_attr(draft)
    if forbidden is not None:
        return _deny("prohibited_content",
                     f"draft carries a prohibited content/decision/secret attribute '{forbidden}' "
                     "(only safe references and summaries may be persisted)"), None

    # Content rule (summary/followup values): non-echoing marker scan (Phase 32 hardening).
    value_denial = _value_content_denial(draft)
    if value_denial is not None:
        return _deny(value_denial[0], value_denial[1]), None

    # Decision-intent rule: only Phase 32 allowed internal-review intents (never approval /
    # publication / execution / financial / client-facing).
    intent = getattr(draft, "decision_intent", None)
    if _is_blank(intent):
        return _deny("missing_decision_intent", "draft.decision_intent is required"), None
    if intent not in ALLOWED_DECISION_INTENTS:
        return _deny("disallowed_decision_intent",
                     f"draft.decision_intent '{intent}' is not an allowed internal-review intent "
                     "(approval/publication/execution/financial/client-facing intents are denied)"), None

    # return_to_stage, if supplied, must be a safe known stage.
    rts = getattr(draft, "return_to_stage", None)
    if not _is_blank(rts) and rts not in ALLOWED_RETURN_STAGES:
        return _deny("invalid_return_to_stage",
                     f"draft.return_to_stage '{rts}' is not a recognized safe stage"), None

    # Review-gated, non-approval posture.
    if getattr(draft, "output_status", None) != REQUIRED_OUTPUT_STATUS:
        return _deny("invalid_draft_output_status",
                     f"draft.output_status must be '{REQUIRED_OUTPUT_STATUS}'"), None
    if getattr(draft, "review_status", None) != REQUIRED_REVIEW_STATUS:
        return _deny("invalid_draft_review_status",
                     f"draft.review_status must be '{REQUIRED_REVIEW_STATUS}'"), None
    if getattr(draft, "lifecycle_status", None) != REQUIRED_LIFECYCLE_STATUS:
        return _deny("invalid_draft_lifecycle_status",
                     f"draft.lifecycle_status must be '{REQUIRED_LIFECYCLE_STATUS}'"), None
    for flag, code in (
        ("authoritative", "prohibited_authoritative"),
        ("client_facing_approved", "prohibited_client_facing"),
        ("capsule_candidate_ready", "prohibited_capsule_candidate"),
        ("financial_verified", "prohibited_financial_verified"),
        ("execution_allowed", "prohibited_execution_allowed"),
        ("approval_allowed", "prohibited_approval_allowed"),
        ("publication_allowed", "prohibited_publication_allowed"),
        ("client_facing_output_created", "prohibited_client_facing_output"),
        ("review_approval_made", "prohibited_review_approval"),
    ):
        if getattr(draft, flag, False) is True:
            return _deny(code, f"draft.{flag} must be false (Phase 33 persists review-gated, "
                               "non-approval records only)"), None
    if getattr(draft, "requires_human_review", True) is not True:
        return _deny("prohibited_no_human_review",
                     "draft.requires_human_review must be true"), None

    # No caller-supplied server-controlled fields.
    if getattr(draft, "reviewer_decision_id", None) is not None:
        return _deny("caller_supplied_id",
                     "draft.reviewer_decision_id must be None (server-controlled)"), None
    if getattr(draft, "created_at", None) is not None:
        return _deny("caller_supplied_timestamp",
                     "draft.created_at must be None (server-controlled)"), None

    # Idempotency key present and valid.
    idem = getattr(request, "idempotency_key", None)
    if _is_blank(idem):
        return _deny("invalid_idempotency_key", "idempotency_key is required"), None
    if not isinstance(idem, str) or len(idem) > 128:
        return _deny("invalid_idempotency_key",
                     "idempotency_key must be a string of at most 128 characters"), None

    # A review-bundle reference (ref or record id) is required (mirrors Phase 32).
    if _is_blank(getattr(draft, "review_bundle_ref", None)) and _is_blank(
        getattr(draft, "review_bundle_record_id", None)
    ):
        return _deny("missing_review_bundle_ref",
                     "draft.review_bundle_ref or draft.review_bundle_record_id is required"), None

    # Required reviewer/decision labels present.
    for attr in ("reviewer_role", "decision_reason_code"):
        if _is_blank(getattr(draft, attr, None)):
            return _deny("missing_decision_field", f"draft.{attr} is required"), None

    # Required identity / traceability fields present.
    for attr in ("owner_id", "client_id", "engagement_id", "requested_by", "requester_role",
                 "authorization_scope"):
        if _is_blank(getattr(request, attr, None)):
            return _deny("missing_identity_field", f"request.{attr} is required"), None

    # Engagement authorization subject present, supported type, id present.
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


def _build_record(request: ControlledWriteRequest, draft: InternalReviewerDecisionDraft,
                  route_to: str, fingerprint: str) -> InternalReviewerDecisionRecord:
    """Explicit field mapping — safe references only, never raw content (no __dict__ copy)."""
    return InternalReviewerDecisionRecord(
        id=_ID_PREFIX + uuid.uuid4().hex[:16],  # server-controlled
        owner_id=request.owner_id,
        client_id=request.client_id,
        engagement_id=request.engagement_id,
        authorization_scope=request.authorization_scope,  # validated == stored scope
        review_bundle_ref=draft.review_bundle_ref,
        review_bundle_record_id=draft.review_bundle_record_id,
        review_bundle_draft_ref=draft.review_bundle_draft_ref,
        reviewer_role=draft.reviewer_role,
        decision_intent=draft.decision_intent,
        decision_reason_code=draft.decision_reason_code,
        safe_decision_summary=draft.safe_decision_summary,
        return_to_stage=draft.return_to_stage,
        route_to=route_to,  # server-derived deterministic routing recommendation
        routing_reason_code=getattr(draft, "routing_reason_code", None),
        review_status=REQUIRED_REVIEW_STATUS,  # review-gated (server-stamped)
        lifecycle_status=REQUIRED_LIFECYCLE_STATUS,
        output_status=REQUIRED_OUTPUT_STATUS,
        authoritative=False,
        client_facing_approved=False,
        capsule_candidate_ready=False,
        financial_verified=False,
        execution_allowed=False,
        approval_allowed=False,
        publication_allowed=False,
        requires_human_review=True,
        client_facing_output_created=False,
        review_approval_made=False,
        idempotency_key=request.idempotency_key,
        payload_fingerprint=fingerprint,
        created_by=request.requested_by,
        # created_at / updated_at are DB server_default (server-stamped).
        details_json={
            "review_plan_item_refs": _safe_list(draft.review_plan_item_refs),
            "evidence_reference_ids": _safe_list(draft.evidence_reference_ids),
            "source_ingestion_record_ids": _safe_list(draft.source_ingestion_record_ids),
            "agent_task_queue_record_ids": _safe_list(draft.agent_task_queue_record_ids),
            "requested_followup_actions": _safe_list(draft.requested_followup_actions),
            "reasons": _safe_list(draft.reasons),
            "warnings": _safe_list(draft.warnings),
            "source_phase": getattr(request, "source_phase", None),
        },
    )


def _find_existing(session, request: ControlledWriteRequest, idem: str):
    """Look up an existing row on the idempotency boundary (owner/client/engagement/key)."""
    return (
        session.query(InternalReviewerDecisionRecord)
        .filter_by(
            owner_id=request.owner_id,
            client_id=request.client_id,
            engagement_id=request.engagement_id,
            idempotency_key=idem,
        )
        .one_or_none()
    )


def _receipt_from_existing(existing: InternalReviewerDecisionRecord, idem: str,
                           outcome: str) -> InternalReviewerDecisionWriteReceipt:
    return InternalReviewerDecisionWriteReceipt(
        outcome=outcome, permitted=True, reason_code=outcome,
        stored_record_id=existing.id, idempotency_key=idem, audit_trace_ref=existing.id,
        database_connection_made=True, sql_execution_made=True,
        database_write_made=False, stored_record_created=False,
        existing_record_returned=True, transaction_committed=False,
        decision_intent=existing.decision_intent, route_to=existing.route_to,
        review_status=existing.review_status, output_status=existing.output_status,
        lifecycle_status=existing.lifecycle_status,
        reasons=["exact authorized replay; existing record returned, not modified"])


def build_decision_controlled_write_request(
    draft: InternalReviewerDecisionDraft,
    *,
    requested_by: str,
    requester_role: str,
    idempotency_key: str,
    subject: Optional[ControlledWriteSubject] = None,
    source_phase: str = "phase32",
    lifecycle_status: str = "active",
) -> ControlledWriteRequest:
    """Convenience planner: wrap a Phase 32 decision draft in a Phase 17 ControlledWriteRequest.

    This bridge lives in the Phase 33 (DB) layer — **not** in Phase 32 — so the reviewer-decision
    boundary stays strictly DB-free. It targets exactly
    ``internal_reviewer_decision_records`` / ``create_internal_reviewer_decision_record`` and does
    not open a database connection or persist anything; a caller passes the result to
    :func:`persist_internal_reviewer_decision_record`. If ``subject`` is omitted, an in-memory
    engagement subject snapshot is derived from the draft's identity (the write-time authorization
    gate still loads and trusts only the *stored* engagement, never this snapshot).
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
        target_table=INTERNAL_REVIEWER_DECISION_TARGET_TABLE,
        requested_action=INTERNAL_REVIEWER_DECISION_TARGET_ACTION,
        subject=subject,
        record_draft=draft,
        source_phase=source_phase,
        lifecycle_status=lifecycle_status,
        idempotency_key=idempotency_key,
    )


def persist_internal_reviewer_decision_record(
    controlled_write_request,
    *,
    session_factory=None,
    decision_request=None,
) -> InternalReviewerDecisionWriteReceipt:
    """Create one review-gated, **non-approval** ``internal_reviewer_decision_records`` row.

    ``session_factory`` is a zero-arg callable returning a SQLAlchemy ``Session`` (defaults to
    the controlled-DB session factory from the environment URL). ``decision_request`` is an
    optional Phase 32 ``InternalReviewerDecisionRequest`` / ``InternalReviewerDecisionResult``
    accepted for forward compatibility / cross-checking; the write-time authorization gate never
    trusts it.

    Returns a :class:`InternalReviewerDecisionWriteReceipt`; expected governance failures are
    typed denials, not exceptions. This writer approves nothing, calls no Phase 22 review writer,
    creates no ``review_records`` row, and never calls ``approve_internal``.
    ``ready_for_internal_use`` is **not** approval.
    """
    denial, draft = _pre_db_validate(controlled_write_request)
    if denial is not None:
        return denial

    request = controlled_write_request
    subject = request.subject
    idem = request.idempotency_key
    route_to = _route_for(draft)
    fingerprint = _payload_fingerprint(request, draft, route_to)

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
                    existing, idem, InternalReviewerDecisionWriteOutcome.IDEMPOTENT_REPLAY)
            return _deny("idempotency_conflict",
                         "idempotency key reused with a different payload/identity",
                         database_connection_made=True, sql_execution_made=True,
                         existing_record_returned=False)

        # --- Insert exactly one authorized row ---
        record = _build_record(request, draft, route_to, fingerprint)
        session.add(record)
        attempted_commit = True
        try:
            session.commit()
        except IntegrityError:
            # Uniqueness race: re-query INLINE (not via _find_existing) so a race is still
            # classifiable even if the pre-check helper missed it.
            session.rollback()
            raced = (
                session.query(InternalReviewerDecisionRecord)
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
                    raced, idem, InternalReviewerDecisionWriteOutcome.IDEMPOTENT_REPLAY)
            if raced is not None:
                return _deny("idempotency_conflict",
                             "idempotency key reused with a different payload/identity (race)",
                             database_connection_made=True, sql_execution_made=True,
                             existing_record_returned=False)
            return InternalReviewerDecisionWriteReceipt(
                outcome=InternalReviewerDecisionWriteOutcome.WRITE_OUTCOME_UNCERTAIN, permitted=True,
                reason_code="integrity_no_row", idempotency_key=idem,
                database_connection_made=True, sql_execution_made=True,
                database_write_made=False, stored_record_created=False,
                transaction_committed=False, outcome_uncertain=True,
                reasons=["integrity conflict without a matching row; write outcome uncertain"])

        session.refresh(record)  # load server-stamped created_at/updated_at
        created_iso = record.created_at.isoformat() if record.created_at else None
        return InternalReviewerDecisionWriteReceipt(
            outcome=InternalReviewerDecisionWriteOutcome.CREATED, permitted=True,
            reason_code="created",
            stored_record_id=record.id, idempotency_key=idem, audit_trace_ref=record.id,
            database_connection_made=True, sql_execution_made=True,
            database_write_made=True, stored_record_created=True,
            existing_record_returned=False, transaction_committed=True, outcome_uncertain=False,
            decision_intent=record.decision_intent, route_to=record.route_to,
            review_status=record.review_status, output_status=record.output_status,
            lifecycle_status=record.lifecycle_status,
            created_at=created_iso, database_write_at=created_iso,
            reasons=["created one review-gated, non-approval internal_reviewer_decision_records row"])

    except SQLAlchemyError as exc:  # infrastructure failure
        try:
            session.rollback()
        except Exception:  # noqa: BLE001 - rollback best-effort; never re-raise here
            pass
        safe = type(exc).__name__  # never leak SQL / connection / content details
        if attempted_commit:
            return InternalReviewerDecisionWriteReceipt(
                outcome=InternalReviewerDecisionWriteOutcome.WRITE_OUTCOME_UNCERTAIN, permitted=True,
                reason_code="commit_uncertain", idempotency_key=idem,
                database_connection_made=True, sql_execution_made=True,
                database_write_made=False, stored_record_created=False,
                transaction_committed=False, outcome_uncertain=True,
                reasons=[f"commit outcome could not be confirmed ({safe}); a record may or "
                         "may not exist"])
        return InternalReviewerDecisionWriteReceipt(
            outcome=InternalReviewerDecisionWriteOutcome.FAILED_BEFORE_WRITE, permitted=True,
            reason_code="failed_before_write", idempotency_key=idem,
            database_connection_made=True, sql_execution_made=True,
            database_write_made=False, stored_record_created=False,
            transaction_committed=False, outcome_uncertain=False,
            reasons=[f"infrastructure failure before any write ({safe}); no row created"])
    finally:
        session.close()
