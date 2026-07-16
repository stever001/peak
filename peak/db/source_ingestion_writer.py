"""Phase 24 — the controlled DB writer for ``source_ingestion_records``.

The fourth narrow live DB writer in Peak (after the Phase 20 ``agent_run_records``, Phase 21
``evidence_references``, and Phase 22 ``review_records`` writers). It accepts an approved
Phase 17 controlled-write request whose ``record_draft`` is a Phase 23 ``SourceIngestionDraft``
and creates **exactly one** ``source_ingestion_records`` row — nothing else. It is a narrow
internal persistence boundary, not a generic CRUD repository, an arbitrary packet importer, or
a packet-payload store.

Mandatory write-time rule: the writer does **not** trust the Phase 23 packet reference or draft
as proof of authorization. At write time it loads the authoritative stored authorization
subject (the ``Engagement`` row) from the database and requires
``request.authorization_scope == engagement.authorization_scope``. Identity matching (owner,
client, engagement) is necessary but **not sufficient**; a scope mismatch is denied even when
every identity matches. Missing stored scope and missing request scope are denied.

Packet content rule: only packet **metadata** is persisted (reference id, schema name/version,
source type, location reference, hash) — **never** the full packet payload, raw interview or
evidence text, source file bytes, arbitrary packet JSON, or any credential/secret. A draft
carrying a ``packet_payload`` / ``raw_packet_content`` / secret-like attribute is rejected.

Side-effect boundary: this module performs only the DB work needed to read the stored subject,
check idempotency, insert the authorized row, read it back, and commit/roll back. It makes
**no LLM/AgentNet/MCP/resolver/connector call, no external network request, no client-facing
approval, no financial verification, no capsule publication**, and it never updates or deletes
any record. It may import SQLAlchemy and ``peak.db`` (this is the DB layer); it imports no
LLM/AgentNet/connector/network client and no credentials.

See docs/SOURCE_INGESTION_CONTROLLED_WRITER.md and docs/SOURCE_INGESTION_IDEMPOTENCY_POLICY.md.
"""

from __future__ import annotations

import hashlib
import json
import uuid
from typing import List, Optional, Tuple

from sqlalchemy.exc import IntegrityError, SQLAlchemyError

# Concrete input contracts (isinstance-checked, not duck-typed).
from peak.ingestion.contracts import PacketIngestionRequest, SourceIngestionDraft
from peak.persistence.contracts import ControlledWriteRequest
from peak.persistence.write_plan import prepare_controlled_write

from .models import Engagement, SourceIngestionRecord
from .session import create_session_factory
from .writer_contracts import (
    SOURCE_INGESTION_TARGET_ACTION,
    SOURCE_INGESTION_TARGET_TABLE,
    SourceIngestionWriteOutcome,
    SourceIngestionWriteReceipt,
)

BLOCKED_LIFECYCLE_STATUSES = frozenset({"revoked", "archived", "deleted_reference_only"})
SUPPORTED_SUBJECT_TYPES = frozenset({"engagement"})
# Attributes a draft must never carry (would embed raw packet content or secrets).
FORBIDDEN_CONTENT_ATTRS = ("packet_payload", "raw_packet_content", "raw_content", "payload")
SECRET_TERMS = (
    "password", "secret", "api_key", "apikey", "token", "private_key", "privatekey",
    "credential", "connection_string", "access_key",
)
_ID_PREFIX = "ing_"


def _is_blank(value) -> bool:
    return value is None or (isinstance(value, str) and not value.strip())


def _deny(reason_code: str, message: str, **flags) -> SourceIngestionWriteReceipt:
    receipt = SourceIngestionWriteReceipt(
        outcome=SourceIngestionWriteOutcome.DENIED,
        permitted=False,
        reason_code=reason_code,
        reasons=[message],
    )
    for key, val in flags.items():
        setattr(receipt, key, val)
    return receipt


def _forbidden_content_attr(draft) -> Optional[str]:
    """Return a draft attribute name that would embed raw packet content / a secret, or None.

    Only attribute *names* are inspected/returned — never values, so no secret is echoed.
    """
    names = getattr(draft, "__dict__", {}) or {}
    for name in names:
        low = str(name).lower()
        if low in FORBIDDEN_CONTENT_ATTRS:
            return name
        if any(term in low for term in SECRET_TERMS):
            return name
    return None


def _payload_fingerprint(request: ControlledWriteRequest, draft: SourceIngestionDraft) -> str:
    """Deterministic, canonical fingerprint of the write payload + identity (replay-conflict).

    Packet **metadata** only — no packet payload or raw content participates.
    """
    payload = {
        "owner_id": request.owner_id,
        "client_id": request.client_id,
        "engagement_id": request.engagement_id,
        "packet_reference_id": draft.packet_reference_id,
        "packet_schema_name": draft.packet_schema_name,
        "packet_schema_version": draft.packet_schema_version,
        "packet_source_type": draft.packet_source_type,
        "packet_location_reference": draft.packet_location_reference,
        "packet_hash": draft.packet_hash,
        "output_status": draft.output_status,
        "review_status": draft.review_status,
        "lifecycle_status": draft.lifecycle_status,
        "authoritative": bool(draft.authoritative),
        "client_facing_approved": bool(draft.client_facing_approved),
        "capsule_candidate_ready": bool(draft.capsule_candidate_ready),
    }
    blob = json.dumps(payload, sort_keys=True, separators=(",", ":"), default=str)
    return hashlib.sha256(blob.encode("utf-8")).hexdigest()


def _identity_mismatches(request: ControlledWriteRequest, draft: SourceIngestionDraft,
                         persistence_request: Optional[PacketIngestionRequest]) -> List[str]:
    """Independently compare identity across the request, draft, engagement subject, and
    (optional) Phase 23 packet ingestion request. Necessary, not sufficient — the DB
    stored-scope check is the authorization gate."""
    mismatches: List[str] = []
    subject = getattr(request, "subject", None)
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
        ref = getattr(persistence_request, "packet_reference", None)
        if ref is not None and getattr(ref, "packet_reference_id", None) != draft.packet_reference_id:
            mismatches.append("persistence_request.packet_reference.packet_reference_id "
                              "does not match draft.packet_reference_id")
    return mismatches


def _pre_db_validate(
    request, persistence_request
) -> Tuple[Optional[SourceIngestionWriteReceipt], Optional[SourceIngestionDraft]]:
    """All governance checks that must pass *before* any DB connection is opened."""
    if not isinstance(request, ControlledWriteRequest):
        return _deny("invalid_request_type",
                     "controlled write request is not a ControlledWriteRequest"), None
    if persistence_request is not None and not isinstance(
        persistence_request, PacketIngestionRequest
    ):
        return _deny("invalid_persistence_request_type",
                     "persistence_request is not a PacketIngestionRequest"), None

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

    if getattr(request, "target_table", None) != SOURCE_INGESTION_TARGET_TABLE:
        return _deny("wrong_target_table",
                     f"target_table must be '{SOURCE_INGESTION_TARGET_TABLE}'"), None
    if getattr(request, "requested_action", None) != SOURCE_INGESTION_TARGET_ACTION:
        return _deny("wrong_target_action",
                     f"requested_action must be '{SOURCE_INGESTION_TARGET_ACTION}'"), None

    draft = getattr(request, "record_draft", None)
    if not isinstance(draft, SourceIngestionDraft):
        return _deny("invalid_record_draft", "record_draft is not a SourceIngestionDraft"), None

    # Packet content rule: metadata only — reject any embedded payload / raw content / secret.
    forbidden = _forbidden_content_attr(draft)
    if forbidden is not None:
        return _deny("prohibited_packet_content",
                     f"draft carries a prohibited content/secret attribute '{forbidden}' "
                     "(only packet metadata may be persisted)"), None

    # Review-gated posture.
    if getattr(draft, "output_status", None) != "draft":
        return _deny("invalid_draft_output_status", "draft.output_status must be 'draft'"), None
    if getattr(draft, "review_status", None) != "needs_review":
        return _deny("invalid_draft_review_status",
                     "draft.review_status must be 'needs_review'"), None
    if getattr(draft, "lifecycle_status", None) != "active":
        return _deny("invalid_draft_lifecycle_status",
                     "draft.lifecycle_status must be 'active'"), None
    if getattr(draft, "authoritative", False) is True:
        return _deny("prohibited_authoritative", "draft.authoritative must be false"), None
    if getattr(draft, "client_facing_approved", False) is True:
        return _deny("prohibited_client_facing",
                     "draft.client_facing_approved must be false"), None
    if getattr(draft, "capsule_candidate_ready", False) is True:
        return _deny("prohibited_capsule_candidate",
                     "draft.capsule_candidate_ready must be false"), None

    # No caller-supplied server-controlled fields.
    if getattr(draft, "source_ingestion_record_id", None) is not None:
        return _deny("caller_supplied_id",
                     "draft.source_ingestion_record_id must be None (server-controlled)"), None
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

    # The packet reference id is the record's source reference (a required stored column).
    if _is_blank(getattr(draft, "packet_reference_id", None)):
        return _deny("missing_source_reference",
                     "draft.packet_reference_id is required (persisted as source_reference_id)"), None

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


def _build_record(request: ControlledWriteRequest, draft: SourceIngestionDraft,
                  fingerprint: str) -> SourceIngestionRecord:
    """Explicit field mapping — metadata only, never raw packet content (no __dict__ copy)."""
    return SourceIngestionRecord(
        id=_ID_PREFIX + uuid.uuid4().hex[:16],  # server-controlled
        owner_id=request.owner_id,
        client_id=request.client_id,
        engagement_id=request.engagement_id,
        authorization_scope=request.authorization_scope,  # validated == stored scope
        source_reference_id=draft.packet_reference_id,  # the packet reference (required column)
        review_status="needs_review",  # review-gated (server-stamped)
        lifecycle_status="active",
        output_status="draft",  # review-gated (server-stamped)
        idempotency_key=request.idempotency_key,
        payload_fingerprint=fingerprint,
        created_by=request.requested_by,
        # created_at / updated_at are DB server_default (server-stamped); captured_at unset.
        details_json={
            "packet_reference_id": draft.packet_reference_id,
            "packet_schema_name": draft.packet_schema_name,
            "packet_schema_version": draft.packet_schema_version,
            "packet_source_type": draft.packet_source_type,
            "packet_location_reference": draft.packet_location_reference,
            "packet_hash": draft.packet_hash,
            "authoritative": bool(draft.authoritative),
            "client_facing_approved": bool(draft.client_facing_approved),
            "capsule_candidate_ready": bool(draft.capsule_candidate_ready),
            "reasons": list(draft.reasons or []),
            "warnings": list(draft.warnings or []),
            "source_phase": getattr(request, "source_phase", None),
        },
    )


def _find_existing(session, request: ControlledWriteRequest, idem: str):
    """Look up an existing row on the idempotency boundary (owner/client/engagement/key)."""
    return (
        session.query(SourceIngestionRecord)
        .filter_by(
            owner_id=request.owner_id,
            client_id=request.client_id,
            engagement_id=request.engagement_id,
            idempotency_key=idem,
        )
        .one_or_none()
    )


def _receipt_from_existing(existing: SourceIngestionRecord, idem: str,
                           outcome: str) -> SourceIngestionWriteReceipt:
    return SourceIngestionWriteReceipt(
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
        review_status=existing.review_status,
        output_status=existing.output_status,
        reasons=["exact authorized replay; existing record returned, not modified"],
    )


def persist_source_ingestion_record(
    controlled_write_request,
    *,
    session_factory=None,
    persistence_request=None,
) -> SourceIngestionWriteReceipt:
    """Create one review-gated ``source_ingestion_records`` row for an approved controlled write.

    ``session_factory`` is a zero-arg callable returning a SQLAlchemy ``Session`` (defaults to
    the controlled-DB session factory from the environment URL). ``persistence_request`` is the
    optional Phase 23 ``PacketIngestionRequest`` used for extra cross-object identity validation.

    Returns a :class:`SourceIngestionWriteReceipt`; expected governance failures are typed
    denials, not exceptions. Unexpected infrastructure failures are converted into a safe
    structured ``failed_before_write`` / ``write_outcome_uncertain`` result where feasible.
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
                return _receipt_from_existing(
                    existing, idem, SourceIngestionWriteOutcome.IDEMPOTENT_REPLAY
                )
            return _deny("idempotency_conflict",
                         "idempotency key reused with a different payload/identity",
                         database_connection_made=True, sql_execution_made=sql_made,
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
                session.query(SourceIngestionRecord)
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
                    raced, idem, SourceIngestionWriteOutcome.IDEMPOTENT_REPLAY
                )
            if raced is not None:
                return _deny("idempotency_conflict",
                             "idempotency key reused with a different payload/identity (race)",
                             database_connection_made=True, sql_execution_made=True,
                             existing_record_returned=False)
            return SourceIngestionWriteReceipt(
                outcome=SourceIngestionWriteOutcome.WRITE_OUTCOME_UNCERTAIN, permitted=True,
                reason_code="integrity_no_row", idempotency_key=idem,
                database_connection_made=True, sql_execution_made=True,
                database_write_made=False, stored_record_created=False,
                transaction_committed=False, outcome_uncertain=True,
                reasons=["integrity conflict without a matching row; write outcome uncertain"],
            )

        session.refresh(record)  # load server-stamped created_at/updated_at
        created_iso = record.created_at.isoformat() if record.created_at else None
        return SourceIngestionWriteReceipt(
            outcome=SourceIngestionWriteOutcome.CREATED,
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
            review_status=record.review_status,
            output_status=record.output_status,
            created_at=created_iso,
            database_write_at=created_iso,
            reasons=["created one review-gated source_ingestion_records row"],
        )

    except SQLAlchemyError as exc:  # infrastructure failure
        try:
            session.rollback()
        except Exception:  # noqa: BLE001 - rollback best-effort; never re-raise here
            pass
        safe = type(exc).__name__  # never leak SQL / connection / packet details
        if attempted_commit:
            return SourceIngestionWriteReceipt(
                outcome=SourceIngestionWriteOutcome.WRITE_OUTCOME_UNCERTAIN, permitted=True,
                reason_code="commit_uncertain", idempotency_key=idem,
                database_connection_made=True, sql_execution_made=True,
                database_write_made=False, stored_record_created=False,
                transaction_committed=False, outcome_uncertain=True,
                reasons=[f"commit outcome could not be confirmed ({safe}); a record may or "
                         "may not exist"],
            )
        return SourceIngestionWriteReceipt(
            outcome=SourceIngestionWriteOutcome.FAILED_BEFORE_WRITE, permitted=True,
            reason_code="failed_before_write", idempotency_key=idem,
            database_connection_made=True, sql_execution_made=True,
            database_write_made=False, stored_record_created=False,
            transaction_committed=False, outcome_uncertain=False,
            reasons=[f"infrastructure failure before any write ({safe}); no row created"],
        )
    finally:
        session.close()
