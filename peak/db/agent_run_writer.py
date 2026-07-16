"""Phase 20 — the controlled DB writer for ``agent_run_records``.

The first real DB-backed persistence path in Peak. It accepts an approved, review-gated
Phase 17/Phase 19 controlled-write request and creates **exactly one** draft
``agent_run_records`` row — nothing else. It is a narrow internal persistence boundary, not
a generic CRUD repository or arbitrary table writer.

Mandatory write-time rule: the writer does **not** trust the Phase 19 subject snapshot as
proof of authorization. At write time it loads the authoritative stored authorization
subject (the ``Engagement`` row) from the database and requires
``request.authorization_scope == engagement.authorization_scope``. Identity matching (owner,
client, engagement, subject) is necessary but **not sufficient**; a scope mismatch is denied
even when every identity matches. Missing stored scope and missing request scope are denied.

Side-effect boundary: this module performs only the DB work needed to read the stored
subject, check idempotency, insert the authorized row, read it back, and commit/roll back.
It makes **no LLM/AgentNet/MCP/resolver/connector call, no external network request, no
client-facing output, no financial verification, no capsule publication**, and it never
updates or deletes any record. It may import SQLAlchemy and ``peak.db`` (this is the DB
layer); it imports no LLM/AgentNet/connector/network client and no credentials.

See docs/AGENT_RUN_CONTROLLED_WRITER.md and docs/AGENT_RUN_IDEMPOTENCY_POLICY.md.
"""

from __future__ import annotations

import hashlib
import json
import uuid
from typing import List, Optional, Tuple

from sqlalchemy.exc import IntegrityError, SQLAlchemyError

# Concrete input contracts (isinstance-checked, not duck-typed).
from peak.agents.persistence_contracts import (
    AgentRunPersistenceDraft,
    AgentRunPersistenceRequest,
)
from peak.persistence.contracts import ControlledWriteRequest
from peak.persistence.write_plan import prepare_controlled_write

from .models import AgentRunRecord, Engagement
from .session import create_session_factory
from .writer_contracts import (
    TARGET_ACTION,
    TARGET_TABLE,
    AgentRunWriteOutcome,
    AgentRunWriteReceipt,
)

BLOCKED_LIFECYCLE_STATUSES = frozenset({"revoked", "archived", "deleted_reference_only"})
# The only stored authorization anchor this writer supports (the engagement row).
SUPPORTED_SUBJECT_TYPES = frozenset({"engagement"})
_ID_PREFIX = "arun_"


def _is_blank(value) -> bool:
    return value is None or (isinstance(value, str) and not value.strip())


def _deny(reason_code: str, message: str, **flags) -> AgentRunWriteReceipt:
    receipt = AgentRunWriteReceipt(
        outcome=AgentRunWriteOutcome.DENIED,
        permitted=False,
        reason_code=reason_code,
        reasons=[message],
    )
    for key, val in flags.items():
        setattr(receipt, key, val)
    return receipt


def _payload_fingerprint(request: ControlledWriteRequest, draft: AgentRunPersistenceDraft) -> str:
    """Deterministic fingerprint of the write payload + identity (for replay-conflict)."""
    subject = getattr(request, "subject", None)
    payload = {
        "owner_id": request.owner_id,
        "client_id": request.client_id,
        "engagement_id": request.engagement_id,
        "subject_record_id": getattr(subject, "subject_record_id", None),
        "agent_name": draft.agent_name,
        "workflow": draft.workflow,
        "requested_action": draft.requested_action,
        "prompt_contract_path": draft.prompt_contract_path,
        "input_record_ids": sorted(draft.input_record_ids or []),
    }
    blob = json.dumps(payload, sort_keys=True, separators=(",", ":"), default=str)
    return hashlib.sha256(blob.encode("utf-8")).hexdigest()


def _identity_mismatches(request: ControlledWriteRequest, draft: AgentRunPersistenceDraft,
                         persistence_request: Optional[AgentRunPersistenceRequest]) -> List[str]:
    """Independently compare identity across the request, draft, subject, and (optional)
    Phase 19 persistence request / its agent task request + run draft. Necessary, not
    sufficient — the DB stored-scope check is the authorization gate."""
    mismatches: List[str] = []
    subject = getattr(request, "subject", None)
    dims = ("owner_id", "client_id", "engagement_id")

    for attr in dims:
        req_val = getattr(request, attr, None)
        # request vs draft
        if getattr(draft, attr, None) != req_val:
            mismatches.append(f"draft.{attr} does not match request.{attr}")
        # request vs subject
        if subject is not None and getattr(subject, attr, None) != req_val:
            mismatches.append(f"subject.{attr} does not match request.{attr}")

    if persistence_request is not None:
        for attr in dims:
            req_val = getattr(request, attr, None)
            if getattr(persistence_request, attr, None) != req_val:
                mismatches.append(f"persistence_request.{attr} does not match request.{attr}")
        task_req = getattr(persistence_request, "agent_task_request", None)
        run_draft = getattr(persistence_request, "agent_run_draft", None)
        for label, obj in (("agent_task_request", task_req), ("agent_run_draft", run_draft)):
            if obj is None:
                continue
            for attr in dims:
                obj_val = getattr(obj, attr, None)
                req_val = getattr(request, attr, None)
                if obj_val is not None and obj_val != req_val:
                    mismatches.append(f"{label}.{attr} does not match request.{attr}")
        snap = getattr(persistence_request, "subject_snapshot", None)
        if snap is not None and subject is not None:
            if getattr(snap, "subject_record_id", None) != getattr(subject, "subject_record_id", None):
                mismatches.append("persistence_request.subject_snapshot.subject_record_id "
                                  "does not match request.subject.subject_record_id")
    return mismatches


def _pre_db_validate(
    request, persistence_request
) -> Tuple[Optional[AgentRunWriteReceipt], Optional[AgentRunPersistenceDraft]]:
    """All governance checks that must pass *before* any DB connection is opened.

    Returns ``(denial_receipt, None)`` on failure or ``(None, draft)`` on success. A denial
    here honestly reports ``database_connection_made = False`` and ``sql_execution_made =
    False``.
    """
    # 1. Concrete request type (reject duck-typed objects at the boundary).
    if not isinstance(request, ControlledWriteRequest):
        return _deny("invalid_request_type",
                     "controlled write request is not a ControlledWriteRequest"), None
    if persistence_request is not None and not isinstance(
        persistence_request, AgentRunPersistenceRequest
    ):
        return _deny("invalid_persistence_request_type",
                     "persistence_request is not an AgentRunPersistenceRequest"), None

    # 2. Independently revalidate through the Phase 17 boundary (allowlist, idempotency,
    #    snapshot-level scope, identity). This is planning-time defense in depth.
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

    # 3. Allowlist: exactly this table + action.
    if getattr(request, "target_table", None) != TARGET_TABLE:
        return _deny("wrong_target_table",
                     f"target_table must be '{TARGET_TABLE}'"), None
    if getattr(request, "requested_action", None) != TARGET_ACTION:
        return _deny("wrong_target_action",
                     f"requested_action must be '{TARGET_ACTION}'"), None

    # 4. record_draft must be a concrete Phase 19 draft.
    draft = getattr(request, "record_draft", None)
    if not isinstance(draft, AgentRunPersistenceDraft):
        return _deny("invalid_record_draft",
                     "record_draft is not an AgentRunPersistenceDraft"), None

    # 5. Review-gated draft posture (mapping never advances authority).
    if getattr(draft, "output_status", None) != "draft":
        return _deny("invalid_draft_output_status",
                     "draft.output_status must be 'draft'"), None
    if getattr(draft, "review_status", None) != "needs_review":
        return _deny("invalid_draft_review_status",
                     "draft.review_status must be 'needs_review'"), None
    for flag in ("database_write_made", "llm_call_made", "agentnet_call_made",
                 "network_call_made", "client_facing_output_created", "capsule_publication_made"):
        if getattr(draft, flag, False) is True:
            return _deny("prohibited_side_effect_state",
                         f"draft.{flag} must be false"), None

    # 6. No caller-supplied server-controlled fields.
    if getattr(draft, "agent_run_record_id", None) is not None:
        return _deny("caller_supplied_id",
                     "draft.agent_run_record_id must be None (server-controlled)"), None
    if getattr(draft, "created_at", None) is not None:
        return _deny("caller_supplied_timestamp",
                     "draft.created_at must be None (server-controlled)"), None

    # 7. Idempotency key present and valid.
    idem = getattr(request, "idempotency_key", None)
    if _is_blank(idem):
        return _deny("invalid_idempotency_key", "idempotency_key is required"), None
    if not isinstance(idem, str) or len(idem) > 128:
        return _deny("invalid_idempotency_key",
                     "idempotency_key must be a string of at most 128 characters"), None

    # 8. Required identity / traceability fields present.
    for attr in ("owner_id", "client_id", "engagement_id", "requested_by", "requester_role",
                 "authorization_scope"):
        if _is_blank(getattr(request, attr, None)):
            return _deny("missing_identity_field", f"request.{attr} is required"), None

    # 9. Subject present, supported type, id present.
    subject = getattr(request, "subject", None)
    if subject is None:
        return _deny("missing_subject", "request.subject is required"), None
    if getattr(subject, "subject_record_type", None) not in SUPPORTED_SUBJECT_TYPES:
        return _deny("unsupported_subject_type",
                     "subject.subject_record_type must be 'engagement'"), None
    if _is_blank(getattr(subject, "subject_record_id", None)):
        return _deny("missing_subject", "subject.subject_record_id is required"), None

    # 10. Independent identity consistency across objects.
    mismatches = _identity_mismatches(request, draft, persistence_request)
    if mismatches:
        return _deny("identity_mismatch", "; ".join(mismatches)), None

    return None, draft


def _build_record(request: ControlledWriteRequest, draft: AgentRunPersistenceDraft,
                  fingerprint: str) -> AgentRunRecord:
    """Explicit field mapping to server-controlled + review-gated columns (no __dict__)."""
    return AgentRunRecord(
        id=_ID_PREFIX + uuid.uuid4().hex[:16],  # server-controlled
        owner_id=request.owner_id,
        client_id=request.client_id,
        engagement_id=request.engagement_id,
        authorization_scope=request.authorization_scope,  # validated == stored scope
        review_status="needs_review",  # review-gated (server-stamped)
        lifecycle_status="active",
        output_status="draft",  # review-gated (server-stamped)
        idempotency_key=request.idempotency_key,
        payload_fingerprint=fingerprint,
        prompt_contract_ref=draft.prompt_contract_path,
        created_by=request.requested_by,
        # created_at / updated_at are DB server_default (server-stamped).
        details_json={
            "agent_name": draft.agent_name,
            "workflow": draft.workflow,
            "requested_action": draft.requested_action,
            "input_record_ids": list(draft.input_record_ids or []),
            "resolver_context_requested": bool(draft.resolver_context_requested),
            "resolver_context_used": bool(draft.resolver_context_used),
            "source_phase": getattr(request, "source_phase", None),
        },
    )


def _find_existing(session, request: ControlledWriteRequest, idem: str):
    """Look up an existing row on the idempotency boundary (owner/client/engagement/key).

    Factored out so the pre-insert check is isolated; the post-insert IntegrityError branch
    re-queries inline so a race can still be classified even if this pre-check missed it.
    """
    return (
        session.query(AgentRunRecord)
        .filter_by(
            owner_id=request.owner_id,
            client_id=request.client_id,
            engagement_id=request.engagement_id,
            idempotency_key=idem,
        )
        .one_or_none()
    )


def _receipt_from_existing(existing: AgentRunRecord, idem: str,
                           outcome: str) -> AgentRunWriteReceipt:
    return AgentRunWriteReceipt(
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


def persist_agent_run_record(
    controlled_write_request,
    *,
    session_factory=None,
    persistence_request=None,
) -> AgentRunWriteReceipt:
    """Create one review-gated ``agent_run_records`` row for an approved controlled write.

    ``session_factory`` is a zero-arg callable returning a SQLAlchemy ``Session`` (defaults
    to the controlled-DB session factory from the environment URL). ``persistence_request``
    is the optional Phase 19 ``AgentRunPersistenceRequest`` used for extra cross-object
    identity validation.

    Returns an :class:`AgentRunWriteReceipt`; expected governance failures are typed denials,
    not exceptions. Unexpected infrastructure failures are converted into a safe structured
    ``failed_before_write`` / ``write_outcome_uncertain`` result where feasible.
    """
    # --- Pre-DB governance (no connection opened on denial) ---
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

        # Identity of the stored subject must match the request (owner/client/engagement).
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
                    existing, idem, AgentRunWriteOutcome.IDEMPOTENT_REPLAY
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
            # Uniqueness race: another writer inserted between our check and commit.
            session.rollback()
            raced = (
                session.query(AgentRunRecord)
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
                    raced, idem, AgentRunWriteOutcome.IDEMPOTENT_REPLAY
                )
            if raced is not None:
                return _deny("idempotency_conflict",
                             "idempotency key reused with a different payload/identity (race)",
                             database_connection_made=True, sql_execution_made=True,
                             existing_record_returned=False)
            # Constraint violated but no matching row found — genuinely uncertain.
            return AgentRunWriteReceipt(
                outcome=AgentRunWriteOutcome.WRITE_OUTCOME_UNCERTAIN, permitted=True,
                reason_code="integrity_no_row", idempotency_key=idem,
                database_connection_made=True, sql_execution_made=True,
                database_write_made=False, stored_record_created=False,
                transaction_committed=False, outcome_uncertain=True,
                reasons=["integrity conflict without a matching row; write outcome uncertain"],
            )

        session.refresh(record)  # load server-stamped created_at/updated_at
        created_iso = record.created_at.isoformat() if record.created_at else None
        return AgentRunWriteReceipt(
            outcome=AgentRunWriteOutcome.CREATED,
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
            reasons=["created one review-gated agent_run_records row"],
        )

    except SQLAlchemyError as exc:  # infrastructure failure
        try:
            session.rollback()
        except Exception:  # noqa: BLE001 - rollback best-effort; never re-raise here
            pass
        safe = type(exc).__name__  # never leak SQL / connection details
        if attempted_commit:
            return AgentRunWriteReceipt(
                outcome=AgentRunWriteOutcome.WRITE_OUTCOME_UNCERTAIN, permitted=True,
                reason_code="commit_uncertain", idempotency_key=idem,
                database_connection_made=True, sql_execution_made=True,
                database_write_made=False, stored_record_created=False,
                transaction_committed=False, outcome_uncertain=True,
                reasons=[f"commit outcome could not be confirmed ({safe}); a record may or "
                         "may not exist"],
            )
        return AgentRunWriteReceipt(
            outcome=AgentRunWriteOutcome.FAILED_BEFORE_WRITE, permitted=True,
            reason_code="failed_before_write", idempotency_key=idem,
            database_connection_made=True, sql_execution_made=True,
            database_write_made=False, stored_record_created=False,
            transaction_committed=False, outcome_uncertain=False,
            reasons=[f"infrastructure failure before any write ({safe}); no row created"],
        )
    finally:
        session.close()
