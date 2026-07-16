"""Phase 22 — the controlled DB writer for ``review_records``.

The third narrow live DB writer in Peak (after the Phase 20 ``agent_run_records`` and
Phase 21 ``evidence_references`` writers). It accepts an approved Phase 17 controlled-write
request whose ``record_draft`` is a Phase 16 ``ReviewRecordDraft`` and creates **exactly one**
``review_records`` row — nothing else. It is a narrow internal persistence boundary, not a
generic CRUD repository or arbitrary table writer.

Mandatory write-time rule: the writer does **not** trust the Phase 16 subject snapshot as
proof of authorization. At write time it loads the authoritative stored authorization
subject (the ``Engagement`` row) from the database and requires
``request.authorization_scope == engagement.authorization_scope``. Identity matching (owner,
client, engagement) is necessary but **not sufficient**; a scope mismatch is denied even when
every identity matches. Missing stored scope and missing request scope are denied.

Review posture: ``approve_internal`` means internal reliance only — it may set
``authoritative=true`` (only when ``next_review_status=approved_internal``) but never creates
client-facing approval. ``reject`` / ``return_for_revision`` / ``supersede`` /
``keep_needs_review`` must be non-authoritative. Decisions attempting ``client_facing_approve``,
``verify_financial_impact``, or ``publish_capsule`` are rejected outright.

Side-effect boundary: this module performs only the DB work needed to read the stored
subject, check idempotency, insert the authorized row, read it back, and commit/roll back.
It makes **no LLM/AgentNet/MCP/resolver/connector call, no external network request, no
client-facing approval, no financial verification, no capsule publication**, and it never
updates or deletes any record. It may import SQLAlchemy and ``peak.db`` (this is the DB
layer); it imports no LLM/AgentNet/connector/network client and no credentials.

See docs/REVIEW_CONTROLLED_WRITER.md and docs/REVIEW_IDEMPOTENCY_POLICY.md.
"""

from __future__ import annotations

import hashlib
import json
import uuid
from typing import List, Optional, Tuple

from sqlalchemy.exc import IntegrityError, SQLAlchemyError

# Concrete input contracts (isinstance-checked, not duck-typed).
from peak.review.persistence_contracts import (
    ReviewPersistenceRequest,
    ReviewRecordDraft,
)
from peak.persistence.contracts import ControlledWriteRequest
from peak.persistence.write_plan import prepare_controlled_write

from .models import Engagement, ReviewRecord
from .session import create_session_factory
from .writer_contracts import (
    REVIEW_TARGET_ACTION,
    REVIEW_TARGET_TABLE,
    ReviewWriteOutcome,
    ReviewWriteReceipt,
)

BLOCKED_LIFECYCLE_STATUSES = frozenset({"revoked", "archived", "deleted_reference_only"})
SUPPORTED_SUBJECT_TYPES = frozenset({"engagement"})
# Review decisions the writer accepts (Phase 15 vocabulary).
ALLOWED_DECISIONS = frozenset(
    {"approve_internal", "reject", "return_for_revision", "supersede", "keep_needs_review"}
)
# Decisions that are never persisted by this writer.
PROHIBITED_DECISIONS = frozenset(
    {"client_facing_approve", "verify_financial_impact", "publish_capsule"}
)
_ID_PREFIX = "rev_"


def _is_blank(value) -> bool:
    return value is None or (isinstance(value, str) and not value.strip())


def _deny(reason_code: str, message: str, **flags) -> ReviewWriteReceipt:
    receipt = ReviewWriteReceipt(
        outcome=ReviewWriteOutcome.DENIED,
        permitted=False,
        reason_code=reason_code,
        reasons=[message],
    )
    for key, val in flags.items():
        setattr(receipt, key, val)
    return receipt


def _payload_fingerprint(request: ControlledWriteRequest, draft: ReviewRecordDraft) -> str:
    """Deterministic, canonical fingerprint of the write payload + identity (replay-conflict)."""
    payload = {
        "owner_id": request.owner_id,
        "client_id": request.client_id,
        "engagement_id": request.engagement_id,
        "subject_record_id": draft.subject_record_id,
        "subject_record_type": draft.subject_record_type,
        "reviewer_role": draft.reviewer_role,
        "requested_by": draft.requested_by,
        "decision": draft.decision,
        "next_output_status": draft.next_output_status,
        "next_review_status": draft.next_review_status,
        "next_lifecycle_status": draft.next_lifecycle_status,
        "authoritative": bool(draft.authoritative),
        "client_facing_approved": bool(draft.client_facing_approved),
        "capsule_candidate_ready": bool(draft.capsule_candidate_ready),
        "source_reference_id": draft.source_reference_id,
        "reasons": list(draft.reasons or []),
        "warnings": list(draft.warnings or []),
    }
    blob = json.dumps(payload, sort_keys=True, separators=(",", ":"), default=str)
    return hashlib.sha256(blob.encode("utf-8")).hexdigest()


def _identity_mismatches(request: ControlledWriteRequest, draft: ReviewRecordDraft,
                         persistence_request: Optional[ReviewPersistenceRequest]) -> List[str]:
    """Independently compare identity across the request, draft, engagement subject, and
    (optional) Phase 16 persistence request. Necessary, not sufficient — the DB stored-scope
    check is the authorization gate. Note: ``draft.subject_record_id`` is the reviewed target
    (not owner/client/engagement) and is cross-checked against the persistence snapshot."""
    mismatches: List[str] = []
    subject = getattr(request, "subject", None)  # the Engagement authorization anchor
    dims = ("owner_id", "client_id", "engagement_id")

    for attr in dims:
        req_val = getattr(request, attr, None)
        if getattr(draft, attr, None) != req_val:
            mismatches.append(f"draft.{attr} does not match request.{attr}")
        if subject is not None and getattr(subject, attr, None) != req_val:
            mismatches.append(f"subject.{attr} does not match request.{attr}")

    if persistence_request is not None:
        for attr in dims:
            req_val = getattr(request, attr, None)
            if getattr(persistence_request, attr, None) != req_val:
                mismatches.append(f"persistence_request.{attr} does not match request.{attr}")
        snap = getattr(persistence_request, "subject_snapshot", None)
        if snap is not None and getattr(snap, "subject_record_id", None) != draft.subject_record_id:
            mismatches.append("persistence_request.subject_snapshot.subject_record_id "
                              "does not match draft.subject_record_id (reviewed target)")
    return mismatches


def _validate_review_decision(draft: ReviewRecordDraft) -> Optional[Tuple[str, str]]:
    """Return ``(reason_code, message)`` if the decision/posture is invalid, else ``None``."""
    decision = getattr(draft, "decision", None)
    if _is_blank(decision):
        return "invalid_decision", "draft.decision is required"
    if decision in PROHIBITED_DECISIONS:
        return ("prohibited_decision",
                f"decision '{decision}' is not permitted (no client-facing approval, "
                "financial verification, or capsule publication)")
    if decision not in ALLOWED_DECISIONS:
        return "invalid_decision", f"decision '{decision}' is not an allowed review decision"

    authoritative = bool(getattr(draft, "authoritative", False))
    next_review = getattr(draft, "next_review_status", None)
    if decision == "approve_internal":
        # Internal reliance only; must land on approved_internal.
        if next_review != "approved_internal":
            return ("invalid_approve_internal_state",
                    "approve_internal requires next_review_status='approved_internal'")
    else:
        # reject / return_for_revision / supersede / keep_needs_review must not be authoritative.
        if authoritative:
            return ("prohibited_authoritative",
                    f"authoritative=true is only allowed for approve_internal, not '{decision}'")
    return None


def _pre_db_validate(
    request, persistence_request
) -> Tuple[Optional[ReviewWriteReceipt], Optional[ReviewRecordDraft]]:
    """All governance checks that must pass *before* any DB connection is opened."""
    if not isinstance(request, ControlledWriteRequest):
        return _deny("invalid_request_type",
                     "controlled write request is not a ControlledWriteRequest"), None
    if persistence_request is not None and not isinstance(
        persistence_request, ReviewPersistenceRequest
    ):
        return _deny("invalid_persistence_request_type",
                     "persistence_request is not a ReviewPersistenceRequest"), None

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

    if getattr(request, "target_table", None) != REVIEW_TARGET_TABLE:
        return _deny("wrong_target_table", f"target_table must be '{REVIEW_TARGET_TABLE}'"), None
    if getattr(request, "requested_action", None) != REVIEW_TARGET_ACTION:
        return _deny("wrong_target_action",
                     f"requested_action must be '{REVIEW_TARGET_ACTION}'"), None

    draft = getattr(request, "record_draft", None)
    if not isinstance(draft, ReviewRecordDraft):
        return _deny("invalid_record_draft", "record_draft is not a ReviewRecordDraft"), None

    # Decision + authoritative posture.
    decision_error = _validate_review_decision(draft)
    if decision_error is not None:
        return _deny(*decision_error), None

    # Client-facing / capsule posture (never created by a review write).
    if getattr(draft, "client_facing_approved", False) is True:
        return _deny("prohibited_client_facing", "draft.client_facing_approved must be false"), None
    if getattr(draft, "capsule_candidate_ready", False) is True:
        return _deny("prohibited_capsule_candidate",
                     "draft.capsule_candidate_ready must be false"), None
    # Defensive: any side-effect flag, if a future draft variant carries one.
    for flag in ("database_write_made", "llm_call_made", "agentnet_call_made",
                 "network_call_made", "client_facing_output_created", "capsule_publication_made"):
        if getattr(draft, flag, False) is True:
            return _deny("prohibited_side_effect_state", f"draft.{flag} must be false"), None

    # No caller-supplied server-controlled fields.
    if getattr(draft, "review_record_id", None) is not None:
        return _deny("caller_supplied_id",
                     "draft.review_record_id must be None (server-controlled)"), None
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

    # The reviewed target must be identified.
    if _is_blank(getattr(draft, "subject_record_id", None)):
        return _deny("missing_review_target",
                     "draft.subject_record_id (reviewed target) is required"), None

    # Engagement authorization subject present, supported type, id present.
    subject = getattr(request, "subject", None)
    if subject is None:
        return _deny("missing_subject", "request.subject is required"), None
    if getattr(subject, "subject_record_type", None) not in SUPPORTED_SUBJECT_TYPES:
        return _deny("unsupported_subject_type",
                     "subject.subject_record_type must be 'engagement'"), None
    if _is_blank(getattr(subject, "subject_record_id", None)):
        return _deny("missing_subject", "subject.subject_record_id is required"), None

    mismatches = _identity_mismatches(request, draft, persistence_request)
    if mismatches:
        return _deny("identity_mismatch", "; ".join(mismatches)), None

    return None, draft


def _build_record(request: ControlledWriteRequest, draft: ReviewRecordDraft,
                  persistence_request: Optional[ReviewPersistenceRequest],
                  fingerprint: str) -> ReviewRecord:
    """Explicit field mapping to server-controlled + governed columns (no __dict__)."""
    snap = getattr(persistence_request, "subject_snapshot", None)
    previous_status = getattr(snap, "stored_review_status", None) if snap is not None else None
    return ReviewRecord(
        id=_ID_PREFIX + uuid.uuid4().hex[:16],  # server-controlled
        owner_id=request.owner_id,
        client_id=request.client_id,
        engagement_id=request.engagement_id,
        authorization_scope=request.authorization_scope,  # validated == stored scope
        # The reviewed target (distinct from the Engagement authorization anchor).
        target_id=draft.subject_record_id,
        subject_record_type=draft.subject_record_type,
        decision=draft.decision,
        authoritative=bool(draft.authoritative),
        previous_status=previous_status,
        new_status=draft.next_review_status,
        review_status=draft.next_review_status or "needs_review",
        lifecycle_status=draft.next_lifecycle_status or "active",
        output_status=draft.next_output_status or "draft",
        reviewer=draft.requested_by,
        idempotency_key=request.idempotency_key,
        payload_fingerprint=fingerprint,
        created_by=request.requested_by,
        # created_at / updated_at are DB server_default (server-stamped).
        details_json={
            "reviewer_role": draft.reviewer_role,
            "client_facing_approved": bool(draft.client_facing_approved),
            "capsule_candidate_ready": bool(draft.capsule_candidate_ready),
            "reasons": list(draft.reasons or []),
            "warnings": list(draft.warnings or []),
            "source_reference_id": draft.source_reference_id,
            "source_phase": getattr(request, "source_phase", None),
        },
    )


def _find_existing(session, request: ControlledWriteRequest, idem: str):
    """Look up an existing row on the idempotency boundary (owner/client/engagement/key)."""
    return (
        session.query(ReviewRecord)
        .filter_by(
            owner_id=request.owner_id,
            client_id=request.client_id,
            engagement_id=request.engagement_id,
            idempotency_key=idem,
        )
        .one_or_none()
    )


def _receipt_from_existing(existing: ReviewRecord, idem: str, outcome: str) -> ReviewWriteReceipt:
    return ReviewWriteReceipt(
        outcome=outcome,
        permitted=True,
        reason_code=outcome,
        stored_record_id=existing.id,
        idempotency_key=idem,
        audit_trace_ref=existing.id,
        database_connection_made=True,
        sql_execution_made=True,
        database_write_made=False,
        stored_record_created=False,
        existing_record_returned=True,
        transaction_committed=False,
        decision=existing.decision,
        authoritative=bool(existing.authoritative),
        review_status=existing.review_status,
        output_status=existing.output_status,
        reasons=["exact authorized replay; existing record returned, not modified"],
    )


def persist_review_record(
    controlled_write_request,
    *,
    session_factory=None,
    persistence_request=None,
) -> ReviewWriteReceipt:
    """Create one ``review_records`` row for an approved controlled write.

    ``session_factory`` is a zero-arg callable returning a SQLAlchemy ``Session`` (defaults
    to the controlled-DB session factory from the environment URL). ``persistence_request``
    is the optional Phase 16 ``ReviewPersistenceRequest`` used for extra cross-object
    identity validation and to source the reviewed target's prior status.

    Returns a :class:`ReviewWriteReceipt`; expected governance failures are typed denials,
    not exceptions. Unexpected infrastructure failures are converted into a safe structured
    ``failed_before_write`` / ``write_outcome_uncertain`` result where feasible.
    """
    denial, draft = _pre_db_validate(controlled_write_request, persistence_request)
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
        sql_made = True
        if engagement is None:
            return _deny("missing_subject",
                         "stored authorization subject (engagement) not found",
                         database_connection_made=True, sql_execution_made=sql_made)

        stored_scope = engagement.authorization_scope
        if _is_blank(stored_scope):
            return _deny("missing_stored_scope",
                         "stored subject has no authorization_scope",
                         database_connection_made=True, sql_execution_made=sql_made)
        if request.authorization_scope != stored_scope:
            return _deny("stored_scope_mismatch",
                         "request.authorization_scope does not match the stored subject's "
                         "authorization_scope (identity match is not sufficient)",
                         database_connection_made=True, sql_execution_made=sql_made)

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
                         database_connection_made=True, sql_execution_made=sql_made)

        if engagement.lifecycle_status in BLOCKED_LIFECYCLE_STATUSES:
            return _deny("subject_lifecycle_blocked",
                         f"stored subject lifecycle_status '{engagement.lifecycle_status}' "
                         "is not permitted",
                         database_connection_made=True, sql_execution_made=sql_made)

        # --- Idempotency pre-check (common replay path; race is covered below) ---
        existing = _find_existing(session, request, idem)
        if existing is not None:
            if existing.payload_fingerprint == fingerprint:
                return _receipt_from_existing(existing, idem, ReviewWriteOutcome.IDEMPOTENT_REPLAY)
            return _deny("idempotency_conflict",
                         "idempotency key reused with a different payload/identity",
                         database_connection_made=True, sql_execution_made=sql_made,
                         existing_record_returned=False)

        # --- Insert exactly one authorized row ---
        record = _build_record(request, draft, persistence_request, fingerprint)
        session.add(record)
        attempted_commit = True
        try:
            session.commit()
        except IntegrityError:
            # Uniqueness race: re-query INLINE (not via _find_existing) so a race is still
            # classifiable even if the pre-check helper missed it.
            session.rollback()
            raced = (
                session.query(ReviewRecord)
                .filter_by(
                    owner_id=request.owner_id,
                    client_id=request.client_id,
                    engagement_id=request.engagement_id,
                    idempotency_key=idem,
                )
                .one_or_none()
            )
            if raced is not None and raced.payload_fingerprint == fingerprint:
                return _receipt_from_existing(raced, idem, ReviewWriteOutcome.IDEMPOTENT_REPLAY)
            if raced is not None:
                return _deny("idempotency_conflict",
                             "idempotency key reused with a different payload/identity (race)",
                             database_connection_made=True, sql_execution_made=True,
                             existing_record_returned=False)
            return ReviewWriteReceipt(
                outcome=ReviewWriteOutcome.WRITE_OUTCOME_UNCERTAIN, permitted=True,
                reason_code="integrity_no_row", idempotency_key=idem,
                database_connection_made=True, sql_execution_made=True,
                database_write_made=False, stored_record_created=False,
                transaction_committed=False, outcome_uncertain=True,
                reasons=["integrity conflict without a matching row; write outcome uncertain"],
            )

        session.refresh(record)  # load server-stamped created_at/updated_at
        created_iso = record.created_at.isoformat() if record.created_at else None
        return ReviewWriteReceipt(
            outcome=ReviewWriteOutcome.CREATED,
            permitted=True,
            reason_code="created",
            stored_record_id=record.id,
            idempotency_key=idem,
            audit_trace_ref=record.id,
            database_connection_made=True,
            sql_execution_made=True,
            database_write_made=True,
            stored_record_created=True,
            existing_record_returned=False,
            transaction_committed=True,
            outcome_uncertain=False,
            decision=record.decision,
            authoritative=bool(record.authoritative),
            review_status=record.review_status,
            output_status=record.output_status,
            created_at=created_iso,
            database_write_at=created_iso,
            reasons=["created one review_records row"],
        )

    except SQLAlchemyError as exc:  # infrastructure failure
        try:
            session.rollback()
        except Exception:  # noqa: BLE001 - rollback best-effort; never re-raise here
            pass
        safe = type(exc).__name__  # never leak SQL / connection details
        if attempted_commit:
            return ReviewWriteReceipt(
                outcome=ReviewWriteOutcome.WRITE_OUTCOME_UNCERTAIN, permitted=True,
                reason_code="commit_uncertain", idempotency_key=idem,
                database_connection_made=True, sql_execution_made=True,
                database_write_made=False, stored_record_created=False,
                transaction_committed=False, outcome_uncertain=True,
                reasons=[f"commit outcome could not be confirmed ({safe}); a record may or "
                         "may not exist"],
            )
        return ReviewWriteReceipt(
            outcome=ReviewWriteOutcome.FAILED_BEFORE_WRITE, permitted=True,
            reason_code="failed_before_write", idempotency_key=idem,
            database_connection_made=True, sql_execution_made=True,
            database_write_made=False, stored_record_created=False,
            transaction_committed=False, outcome_uncertain=False,
            reasons=[f"infrastructure failure before any write ({safe}); no row created"],
        )
    finally:
        session.close()
