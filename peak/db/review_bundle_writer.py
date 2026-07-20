"""Phase 30 — the controlled DB writer for ``review_bundle_records``.

The sixth narrow live DB writer in Peak (after the Phase 20 ``agent_run_records``, Phase 21
``evidence_references``, Phase 22 ``review_records``, Phase 24 ``source_ingestion_records``, and
Phase 27 ``agent_task_queue_records`` writers). It accepts an approved Phase 17 controlled-write
request whose ``record_draft`` is a Phase 29 ``ReviewBundleDraft`` and creates **exactly one**
``review_bundle_records`` row — nothing else. It is a narrow internal persistence boundary, not a
generic review engine, workflow engine, or CRUD repository.

**No approval.** This writer never approves anything (no ``approve_internal``), never calls the
Phase 22 review writer, and **never creates a ``review_records`` row**. It never executes an agent
(live or mock), never calls the Phase 13 executor / MockLLM / a live LLM / AgentNet / MCP /
resolver / connector / network, never creates an ``agent_run_records`` row, and produces no
client-facing output, financial verification, or capsule publication. It stores **review-gated,
not-approved** review bundle records only — every review/approval-posture flag on the stored row
is the not-approved / not-allowed / needs-review posture.

Mandatory write-time rule: the writer does **not** trust the Phase 29 request or draft as proof
of authorization. At write time it loads the authoritative stored authorization subject (the
``Engagement`` row) from the database and requires
``request.authorization_scope == engagement.authorization_scope``. Identity matching (owner,
client, engagement) is necessary but **not sufficient**; a scope mismatch is denied even when
every identity matches. Missing stored scope and missing request scope are denied.

Content rule: only **safe references, counts, and safe metadata** are persisted (owner/client/
engagement, packet-processing receipt ref, source/evidence/task-queue ids, subject refs,
reviewer_role, review_reason, review_scope, statuses, posture booleans, reasons/warnings) —
**never** the raw packet payload, raw evidence/interview text, source file bytes, generated agent
output, arbitrary client content, credentials/secrets, a final review decision, stack traces, DB
URLs, or raw SQL. A draft carrying such an attribute is rejected without echoing the value.

Side-effect boundary: this module performs only the DB work needed to read the stored subject,
check idempotency, insert the authorized row, read it back, and commit/roll back. It may import
SQLAlchemy and ``peak.db`` (this is the DB layer). See docs/REVIEW_BUNDLE_CONTROLLED_WRITER.md and
docs/REVIEW_BUNDLE_IDEMPOTENCY_POLICY.md.
"""

from __future__ import annotations

import hashlib
import json
import uuid
from typing import List, Optional, Tuple

from sqlalchemy.exc import IntegrityError, SQLAlchemyError

# Concrete input contracts (isinstance-checked, not duck-typed). Phase 29 is DB-free/stdlib.
from peak.persistence.contracts import ControlledWriteRequest
from peak.persistence.write_plan import prepare_controlled_write
from peak.review_orchestration.contracts import ReviewBundleDraft

from .models import Engagement, ReviewBundleRecord
from .session import create_session_factory
from .writer_contracts import (
    REVIEW_BUNDLE_TARGET_ACTION,
    REVIEW_BUNDLE_TARGET_TABLE,
    ReviewBundleWriteOutcome,
    ReviewBundleWriteReceipt,
)

BLOCKED_LIFECYCLE_STATUSES = frozenset({"revoked", "archived", "deleted_reference_only"})
SUPPORTED_SUBJECT_TYPES = frozenset({"engagement"})
REQUIRED_OUTPUT_STATUS = "draft"
REQUIRED_REVIEW_STATUS = "needs_review"
REQUIRED_LIFECYCLE_STATUS = "draft"
# Attributes a draft must never carry (raw content / generated output / a secret / a decision).
FORBIDDEN_CONTENT_SUBSTRINGS = (
    "packet_payload", "raw_packet", "raw_content", "raw_evidence", "evidence_text",
    "raw_interview", "interview_text", "source_bytes", "file_bytes", "raw_source",
    "generated_output", "agent_output", "llm_output", "llm_prompt", "prompt_text", "raw_sql",
    "stack_trace", "traceback", "connection_string", "database_url", "decision", "approval_note",
    "signoff", "sign_off",
)
SECRET_TERMS = (
    "password", "secret", "api_key", "apikey", "token", "private_key", "privatekey",
    "credential", "access_key",
)
# Draft attributes that are legitimate and must never be flagged by the content scan.
_SAFE_DRAFT_ATTRS = frozenset({
    "review_bundle_id", "owner_id", "client_id", "engagement_id", "packet_processing_receipt_ref",
    "source_ingestion_record_ids", "evidence_reference_ids", "agent_task_queue_record_ids",
    "subject_refs", "reviewer_role", "review_reason", "review_scope", "output_status",
    "review_status", "lifecycle_status", "authoritative", "client_facing_approved",
    "capsule_candidate_ready", "financial_verified", "execution_allowed", "approval_allowed",
    "publication_allowed", "requires_human_review", "reasons", "warnings", "created_at",
})
_ID_PREFIX = "rvb_"


def _is_blank(value) -> bool:
    return value is None or (isinstance(value, str) and not value.strip())


def _deny(reason_code: str, message: str, **flags) -> ReviewBundleWriteReceipt:
    receipt = ReviewBundleWriteReceipt(
        outcome=ReviewBundleWriteOutcome.DENIED, permitted=False,
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


def _safe_subject_refs(draft) -> List[dict]:
    """Serialize subject refs to safe {id, type} dicts only (never raw content)."""
    refs = []
    for r in getattr(draft, "subject_refs", None) or []:
        refs.append({
            "subject_ref_id": getattr(r, "subject_ref_id", None),
            "subject_type": getattr(r, "subject_type", None),
        })
    return refs


def _payload_fingerprint(request: ControlledWriteRequest, draft: ReviewBundleDraft) -> str:
    """Deterministic, canonical fingerprint of the write payload + identity (replay-conflict).

    Safe references/metadata only — no raw content participates.
    """
    payload = {
        "owner_id": request.owner_id,
        "client_id": request.client_id,
        "engagement_id": request.engagement_id,
        "packet_processing_receipt_ref": draft.packet_processing_receipt_ref,
        "source_ingestion_record_ids": list(draft.source_ingestion_record_ids or []),
        "evidence_reference_ids": list(draft.evidence_reference_ids or []),
        "agent_task_queue_record_ids": list(draft.agent_task_queue_record_ids or []),
        "subject_refs": _safe_subject_refs(draft),
        "reviewer_role": draft.reviewer_role,
        "review_reason": draft.review_reason,
        "review_scope": draft.review_scope,
        "output_status": draft.output_status,
        "review_status": draft.review_status,
        "lifecycle_status": draft.lifecycle_status,
        "authoritative": bool(draft.authoritative),
        "client_facing_approved": bool(draft.client_facing_approved),
        "capsule_candidate_ready": bool(draft.capsule_candidate_ready),
        "financial_verified": bool(draft.financial_verified),
        "execution_allowed": bool(draft.execution_allowed),
        "approval_allowed": bool(draft.approval_allowed),
        "publication_allowed": bool(draft.publication_allowed),
        "requires_human_review": bool(draft.requires_human_review),
    }
    blob = json.dumps(payload, sort_keys=True, separators=(",", ":"), default=str)
    return hashlib.sha256(blob.encode("utf-8")).hexdigest()


def _identity_mismatches(request: ControlledWriteRequest, draft: ReviewBundleDraft) -> List[str]:
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
    return mismatches


def _pre_db_validate(
    request,
) -> Tuple[Optional[ReviewBundleWriteReceipt], Optional[ReviewBundleDraft]]:
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

    if getattr(request, "target_table", None) != REVIEW_BUNDLE_TARGET_TABLE:
        return _deny("wrong_target_table",
                     f"target_table must be '{REVIEW_BUNDLE_TARGET_TABLE}'"), None
    if getattr(request, "requested_action", None) != REVIEW_BUNDLE_TARGET_ACTION:
        return _deny("wrong_target_action",
                     f"requested_action must be '{REVIEW_BUNDLE_TARGET_ACTION}'"), None

    draft = getattr(request, "record_draft", None)
    if not isinstance(draft, ReviewBundleDraft):
        return _deny("invalid_record_draft", "record_draft is not a ReviewBundleDraft"), None

    # Content rule: safe references only — reject any embedded raw content / decision / secret.
    forbidden = _forbidden_content_attr(draft)
    if forbidden is not None:
        return _deny("prohibited_content",
                     f"draft carries a prohibited content/decision/secret attribute '{forbidden}' "
                     "(only safe references and summaries may be persisted)"), None

    # Review-gated, not-approved posture.
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
    ):
        if getattr(draft, flag, False) is True:
            return _deny(code, f"draft.{flag} must be false (Phase 30 persists review-gated, "
                               "not-approved records only)"), None
    if getattr(draft, "requires_human_review", True) is not True:
        return _deny("prohibited_no_human_review",
                     "draft.requires_human_review must be true"), None

    # No caller-supplied server-controlled fields.
    if getattr(draft, "review_bundle_id", None) is not None:
        return _deny("caller_supplied_id",
                     "draft.review_bundle_id must be None (server-controlled)"), None
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


def _build_record(request: ControlledWriteRequest, draft: ReviewBundleDraft,
                  fingerprint: str) -> ReviewBundleRecord:
    """Explicit field mapping — safe references only, never raw content (no __dict__ copy)."""
    return ReviewBundleRecord(
        id=_ID_PREFIX + uuid.uuid4().hex[:16],  # server-controlled
        owner_id=request.owner_id,
        client_id=request.client_id,
        engagement_id=request.engagement_id,
        authorization_scope=request.authorization_scope,  # validated == stored scope
        packet_processing_receipt_ref=draft.packet_processing_receipt_ref,
        reviewer_role=draft.reviewer_role,
        review_reason=draft.review_reason,
        review_scope=draft.review_scope,
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
        idempotency_key=request.idempotency_key,
        payload_fingerprint=fingerprint,
        created_by=request.requested_by,
        # created_at / updated_at are DB server_default (server-stamped).
        details_json={
            "source_ingestion_record_ids": list(draft.source_ingestion_record_ids or []),
            "evidence_reference_ids": list(draft.evidence_reference_ids or []),
            "agent_task_queue_record_ids": list(draft.agent_task_queue_record_ids or []),
            "subject_refs": _safe_subject_refs(draft),
            "reasons": list(draft.reasons or []),
            "warnings": list(draft.warnings or []),
            "source_phase": getattr(request, "source_phase", None),
        },
    )


def _find_existing(session, request: ControlledWriteRequest, idem: str):
    """Look up an existing row on the idempotency boundary (owner/client/engagement/key)."""
    return (
        session.query(ReviewBundleRecord)
        .filter_by(
            owner_id=request.owner_id,
            client_id=request.client_id,
            engagement_id=request.engagement_id,
            idempotency_key=idem,
        )
        .one_or_none()
    )


def _receipt_from_existing(existing: ReviewBundleRecord, idem: str,
                           outcome: str) -> ReviewBundleWriteReceipt:
    return ReviewBundleWriteReceipt(
        outcome=outcome, permitted=True, reason_code=outcome,
        stored_record_id=existing.id, idempotency_key=idem, audit_trace_ref=existing.id,
        database_connection_made=True, sql_execution_made=True,
        database_write_made=False, stored_record_created=False,
        existing_record_returned=True, transaction_committed=False,
        review_status=existing.review_status, output_status=existing.output_status,
        lifecycle_status=existing.lifecycle_status,
        reasons=["exact authorized replay; existing record returned, not modified"])


def persist_review_bundle_record(
    controlled_write_request,
    *,
    session_factory=None,
    review_request=None,
) -> ReviewBundleWriteReceipt:
    """Create one review-gated, **not-approved** ``review_bundle_records`` row.

    ``session_factory`` is a zero-arg callable returning a SQLAlchemy ``Session`` (defaults to
    the controlled-DB session factory from the environment URL). ``review_request`` is an optional
    Phase 29 ``PacketReviewOrchestrationRequest`` / ``PacketReviewOrchestrationResult`` accepted
    for forward compatibility; the write-time authorization gate never trusts it.

    Returns a :class:`ReviewBundleWriteReceipt`; expected governance failures are typed denials,
    not exceptions. This writer approves nothing, calls no Phase 22 review writer, and creates no
    ``review_records`` row.
    """
    denial, draft = _pre_db_validate(controlled_write_request)
    if denial is not None:
        return denial

    request = controlled_write_request
    subject = request.subject
    idem = request.idempotency_key
    fingerprint = _payload_fingerprint(request, draft)

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
                    existing, idem, ReviewBundleWriteOutcome.IDEMPOTENT_REPLAY)
            return _deny("idempotency_conflict",
                         "idempotency key reused with a different payload/identity",
                         database_connection_made=True, sql_execution_made=True,
                         existing_record_returned=False)

        # --- Insert exactly one authorized row ---
        record = _build_record(request, draft, fingerprint)
        session.add(record)
        attempted_commit = True
        try:
            session.commit()
        except IntegrityError:
            # Uniqueness race: re-query INLINE (not via _find_existing) so a race is still
            # classifiable even if the pre-check helper missed it.
            session.rollback()
            raced = (
                session.query(ReviewBundleRecord)
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
                    raced, idem, ReviewBundleWriteOutcome.IDEMPOTENT_REPLAY)
            if raced is not None:
                return _deny("idempotency_conflict",
                             "idempotency key reused with a different payload/identity (race)",
                             database_connection_made=True, sql_execution_made=True,
                             existing_record_returned=False)
            return ReviewBundleWriteReceipt(
                outcome=ReviewBundleWriteOutcome.WRITE_OUTCOME_UNCERTAIN, permitted=True,
                reason_code="integrity_no_row", idempotency_key=idem,
                database_connection_made=True, sql_execution_made=True,
                database_write_made=False, stored_record_created=False,
                transaction_committed=False, outcome_uncertain=True,
                reasons=["integrity conflict without a matching row; write outcome uncertain"])

        session.refresh(record)  # load server-stamped created_at/updated_at
        created_iso = record.created_at.isoformat() if record.created_at else None
        return ReviewBundleWriteReceipt(
            outcome=ReviewBundleWriteOutcome.CREATED, permitted=True, reason_code="created",
            stored_record_id=record.id, idempotency_key=idem, audit_trace_ref=record.id,
            database_connection_made=True, sql_execution_made=True,
            database_write_made=True, stored_record_created=True,
            existing_record_returned=False, transaction_committed=True, outcome_uncertain=False,
            review_status=record.review_status, output_status=record.output_status,
            lifecycle_status=record.lifecycle_status,
            created_at=created_iso, database_write_at=created_iso,
            reasons=["created one review-gated, not-approved review_bundle_records row"])

    except SQLAlchemyError as exc:  # infrastructure failure
        try:
            session.rollback()
        except Exception:  # noqa: BLE001 - rollback best-effort; never re-raise here
            pass
        safe = type(exc).__name__  # never leak SQL / connection / content details
        if attempted_commit:
            return ReviewBundleWriteReceipt(
                outcome=ReviewBundleWriteOutcome.WRITE_OUTCOME_UNCERTAIN, permitted=True,
                reason_code="commit_uncertain", idempotency_key=idem,
                database_connection_made=True, sql_execution_made=True,
                database_write_made=False, stored_record_created=False,
                transaction_committed=False, outcome_uncertain=True,
                reasons=[f"commit outcome could not be confirmed ({safe}); a record may or "
                         "may not exist"])
        return ReviewBundleWriteReceipt(
            outcome=ReviewBundleWriteOutcome.FAILED_BEFORE_WRITE, permitted=True,
            reason_code="failed_before_write", idempotency_key=idem,
            database_connection_made=True, sql_execution_made=True,
            database_write_made=False, stored_record_created=False,
            transaction_committed=False, outcome_uncertain=False,
            reasons=[f"infrastructure failure before any write ({safe}); no row created"])
    finally:
        session.close()
