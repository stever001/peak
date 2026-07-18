"""Phase 27 — the controlled DB writer for ``agent_task_queue_records``.

The fifth narrow live DB writer in Peak (after the Phase 20 ``agent_run_records``, Phase 21
``evidence_references``, Phase 22 ``review_records``, and Phase 24 ``source_ingestion_records``
writers). It accepts an approved Phase 17 controlled-write request whose ``record_draft`` is a
Phase 26 ``AgentTaskQueueDraft`` and creates **exactly one** ``agent_task_queue_records`` row —
nothing else. It is a narrow internal persistence boundary, not a generic task runner, job
queue, workflow engine, or CRUD repository.

**No execution.** This writer never executes an agent (live or mock), never calls the Phase 13
executor / MockLLM / a live LLM / AgentNet / MCP / resolver / connector / network, and never
creates an ``agent_run_records`` row. It stores **review-gated, not-executed** queue records
only — every execution-posture flag on the stored row is the not-executed / not-allowed /
needs-review posture.

Mandatory write-time rule: the writer does **not** trust the Phase 26 queue request or draft as
proof of authorization. At write time it loads the authoritative stored authorization subject
(the ``Engagement`` row) from the database and requires
``request.authorization_scope == engagement.authorization_scope``. Identity matching (owner,
client, engagement) is necessary but **not sufficient**; a scope mismatch is denied even when
every identity matches. Missing stored scope and missing request scope are denied.

Content rule: only **safe references and safe summaries** are persisted (owner/client/engagement,
agent_name, task_type/requested_action, task_input_ref, safe_input_summary,
source_ingestion_record_id, evidence_reference_ids, packet_processing_run_ref / orchestration_ref,
authorization_scope, readiness_state, statuses, posture booleans, reasons/warnings) — **never**
the raw packet payload, raw evidence/interview text, source file bytes, generated agent output,
LLM prompts with raw content, credentials/secrets, stack traces, DB URLs, or raw SQL. A draft
carrying such an attribute is rejected without echoing the value.

Side-effect boundary: this module performs only the DB work needed to read the stored subject,
check idempotency, insert the authorized row, read it back, and commit/roll back. It may import
SQLAlchemy and ``peak.db`` (this is the DB layer). See docs/AGENT_TASK_QUEUE_CONTROLLED_WRITER.md
and docs/AGENT_TASK_QUEUE_IDEMPOTENCY_POLICY.md.
"""

from __future__ import annotations

import hashlib
import json
import uuid
from typing import List, Optional, Tuple

from sqlalchemy.exc import IntegrityError, SQLAlchemyError

# Concrete input contracts (isinstance-checked, not duck-typed).
from peak.persistence.contracts import ControlledWriteRequest
from peak.persistence.write_plan import prepare_controlled_write
from peak.task_queue.contracts import AgentTaskQueueDraft

from .models import AgentTaskQueueRecord, Engagement
from .session import create_session_factory
from .writer_contracts import (
    AGENT_TASK_QUEUE_TARGET_ACTION,
    AGENT_TASK_QUEUE_TARGET_TABLE,
    AgentTaskQueueWriteOutcome,
    AgentTaskQueueWriteReceipt,
)

BLOCKED_LIFECYCLE_STATUSES = frozenset({"revoked", "archived", "deleted_reference_only"})
SUPPORTED_SUBJECT_TYPES = frozenset({"engagement"})
# Only these non-blocked readiness states are persistable (blocked_* tasks have no queue draft).
PERSISTABLE_READINESS_STATES = frozenset(
    {"queued_for_review", "ready_for_future_controlled_execution"}
)
# The Phase 26 draft posture this writer persists exactly (mirror Phase 26).
REQUIRED_OUTPUT_STATUS = "draft"
REQUIRED_REVIEW_STATUS = "needs_review"
REQUIRED_LIFECYCLE_STATUS = "draft"
REQUIRED_EXECUTION_STATUS = "not_executed"
# Attributes a draft must never carry (would embed raw content / generated output / a secret).
FORBIDDEN_CONTENT_SUBSTRINGS = (
    "packet_payload", "raw_packet", "raw_content", "payload", "raw_evidence", "evidence_text",
    "raw_interview", "interview_text", "source_bytes", "file_bytes", "raw_source",
    "generated_output", "agent_output", "llm_output", "llm_prompt", "prompt_text", "raw_sql",
    "stack_trace", "traceback", "connection_string", "database_url",
)
SECRET_TERMS = (
    "password", "secret", "api_key", "apikey", "token", "private_key", "privatekey",
    "credential", "access_key",
)
# Draft attributes that are legitimate and must never be flagged by the content scan.
_SAFE_DRAFT_ATTRS = frozenset(
    {
        "agent_task_queue_record_id", "owner_id", "client_id", "engagement_id", "agent_name",
        "workflow", "task_type", "requested_action", "task_input_ref", "task_input_summary",
        "source_ingestion_record_id", "evidence_reference_ids", "packet_processing_run_ref",
        "orchestration_ref", "prompt_contract_path", "authorization_scope", "idempotency_key",
        "readiness_state", "output_status", "review_status", "lifecycle_status", "authoritative",
        "client_facing_approved", "capsule_candidate_ready", "execution_status",
        "execution_allowed", "llm_execution_allowed", "agentnet_context_allowed",
        "resolver_context_allowed", "network_allowed", "requires_human_review", "reasons",
        "warnings", "created_at",
    }
)
_ID_PREFIX = "atq_"


def _is_blank(value) -> bool:
    return value is None or (isinstance(value, str) and not value.strip())


def _deny(reason_code: str, message: str, **flags) -> AgentTaskQueueWriteReceipt:
    receipt = AgentTaskQueueWriteReceipt(
        outcome=AgentTaskQueueWriteOutcome.DENIED,
        permitted=False,
        reason_code=reason_code,
        reasons=[message],
    )
    for key, val in flags.items():
        setattr(receipt, key, val)
    return receipt


def _forbidden_content_attr(draft) -> Optional[str]:
    """Return a draft attribute name that would embed raw content / output / a secret, or None.

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


def _payload_fingerprint(request: ControlledWriteRequest, draft: AgentTaskQueueDraft) -> str:
    """Deterministic, canonical fingerprint of the write payload + identity (replay-conflict).

    Safe references/metadata only — no raw content participates.
    """
    payload = {
        "owner_id": request.owner_id,
        "client_id": request.client_id,
        "engagement_id": request.engagement_id,
        "agent_name": draft.agent_name,
        "task_type": draft.task_type,
        "requested_action": draft.requested_action,
        "task_input_ref": list(draft.task_input_ref or []),
        "safe_input_summary": draft.task_input_summary,
        "source_ingestion_record_id": draft.source_ingestion_record_id,
        "evidence_reference_ids": list(draft.evidence_reference_ids or []),
        "packet_processing_run_ref": draft.packet_processing_run_ref,
        "orchestration_ref": draft.orchestration_ref,
        "authorization_scope": request.authorization_scope,
        "readiness_state": draft.readiness_state,
        "output_status": draft.output_status,
        "review_status": draft.review_status,
        "lifecycle_status": draft.lifecycle_status,
        "execution_status": draft.execution_status,
        "authoritative": bool(draft.authoritative),
        "client_facing_approved": bool(draft.client_facing_approved),
        "capsule_candidate_ready": bool(draft.capsule_candidate_ready),
        "execution_allowed": bool(draft.execution_allowed),
        "llm_execution_allowed": bool(draft.llm_execution_allowed),
        "agentnet_context_allowed": bool(draft.agentnet_context_allowed),
        "resolver_context_allowed": bool(draft.resolver_context_allowed),
        "network_allowed": bool(draft.network_allowed),
        "requires_human_review": bool(draft.requires_human_review),
    }
    blob = json.dumps(payload, sort_keys=True, separators=(",", ":"), default=str)
    return hashlib.sha256(blob.encode("utf-8")).hexdigest()


def _identity_mismatches(request: ControlledWriteRequest, draft: AgentTaskQueueDraft) -> List[str]:
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
    # Scope: the draft's carried scope must match the request scope (write-time DB check follows).
    if getattr(draft, "authorization_scope", None) != getattr(request, "authorization_scope", None):
        mismatches.append("draft.authorization_scope does not match request.authorization_scope")
    return mismatches


def _known_agent(agent_name) -> bool:
    """Return True if ``agent_name`` is in the Phase 13 registry (DB-free lookup, imported lazily)."""
    from peak.agents.registry import get_agent  # lazy: keep the DB-writer import graph minimal

    return get_agent(agent_name) is not None


def _pre_db_validate(
    request,
) -> Tuple[Optional[AgentTaskQueueWriteReceipt], Optional[AgentTaskQueueDraft]]:
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

    if getattr(request, "target_table", None) != AGENT_TASK_QUEUE_TARGET_TABLE:
        return _deny("wrong_target_table",
                     f"target_table must be '{AGENT_TASK_QUEUE_TARGET_TABLE}'"), None
    if getattr(request, "requested_action", None) != AGENT_TASK_QUEUE_TARGET_ACTION:
        return _deny("wrong_target_action",
                     f"requested_action must be '{AGENT_TASK_QUEUE_TARGET_ACTION}'"), None

    draft = getattr(request, "record_draft", None)
    if not isinstance(draft, AgentTaskQueueDraft):
        return _deny("invalid_record_draft", "record_draft is not an AgentTaskQueueDraft"), None

    # Content rule: safe references only — reject any embedded raw content / output / secret.
    forbidden = _forbidden_content_attr(draft)
    if forbidden is not None:
        return _deny("prohibited_content",
                     f"draft carries a prohibited content/secret attribute '{forbidden}' "
                     "(only safe references and summaries may be persisted)"), None

    # Review-gated, not-executed posture (mirror Phase 26 exactly).
    if getattr(draft, "output_status", None) != REQUIRED_OUTPUT_STATUS:
        return _deny("invalid_draft_output_status",
                     f"draft.output_status must be '{REQUIRED_OUTPUT_STATUS}'"), None
    if getattr(draft, "review_status", None) != REQUIRED_REVIEW_STATUS:
        return _deny("invalid_draft_review_status",
                     f"draft.review_status must be '{REQUIRED_REVIEW_STATUS}'"), None
    if getattr(draft, "lifecycle_status", None) != REQUIRED_LIFECYCLE_STATUS:
        return _deny("invalid_draft_lifecycle_status",
                     f"draft.lifecycle_status must be '{REQUIRED_LIFECYCLE_STATUS}'"), None
    if getattr(draft, "execution_status", None) != REQUIRED_EXECUTION_STATUS:
        return _deny("invalid_execution_status",
                     f"draft.execution_status must be '{REQUIRED_EXECUTION_STATUS}'"), None
    if getattr(draft, "authoritative", False) is True:
        return _deny("prohibited_authoritative", "draft.authoritative must be false"), None
    if getattr(draft, "client_facing_approved", False) is True:
        return _deny("prohibited_client_facing",
                     "draft.client_facing_approved must be false"), None
    if getattr(draft, "capsule_candidate_ready", False) is True:
        return _deny("prohibited_capsule_candidate",
                     "draft.capsule_candidate_ready must be false"), None
    # No execution / LLM / AgentNet / resolver / network may ever be enabled.
    for flag, code in (
        ("execution_allowed", "prohibited_execution_allowed"),
        ("llm_execution_allowed", "prohibited_llm_execution"),
        ("agentnet_context_allowed", "prohibited_agentnet_context"),
        ("resolver_context_allowed", "prohibited_resolver_context"),
        ("network_allowed", "prohibited_network"),
    ):
        if getattr(draft, flag, False) is True:
            return _deny(code, f"draft.{flag} must be false (Phase 27 persists non-executed "
                               "queue records only)"), None
    if getattr(draft, "requires_human_review", True) is not True:
        return _deny("prohibited_no_human_review",
                     "draft.requires_human_review must be true"), None

    # Readiness state must be a non-blocked, persistable state.
    readiness = getattr(draft, "readiness_state", None)
    if _is_blank(readiness):
        return _deny("missing_readiness_state", "draft.readiness_state is required"), None
    if readiness not in PERSISTABLE_READINESS_STATES:
        return _deny("non_persistable_readiness_state",
                     f"draft.readiness_state '{readiness}' is not persistable "
                     f"(only {sorted(PERSISTABLE_READINESS_STATES)} may be stored; blocked "
                     "tasks have no queue draft)"), None

    # No caller-supplied server-controlled fields.
    if getattr(draft, "agent_task_queue_record_id", None) is not None:
        return _deny("caller_supplied_id",
                     "draft.agent_task_queue_record_id must be None (server-controlled)"), None
    if getattr(draft, "created_at", None) is not None:
        return _deny("caller_supplied_timestamp",
                     "draft.created_at must be None (server-controlled)"), None

    # Agent identity / registry gate.
    agent_name = getattr(draft, "agent_name", None)
    if _is_blank(agent_name):
        return _deny("missing_agent_name", "draft.agent_name is required"), None
    if not _known_agent(agent_name):
        return _deny("unknown_agent",
                     f"agent_name '{agent_name}' is not in the Phase 13 registry"), None
    if _is_blank(getattr(draft, "task_type", None)) and _is_blank(
        getattr(draft, "requested_action", None)
    ):
        return _deny("missing_task_type",
                     "draft.task_type or draft.requested_action is required"), None

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


def _build_record(request: ControlledWriteRequest, draft: AgentTaskQueueDraft,
                  fingerprint: str) -> AgentTaskQueueRecord:
    """Explicit field mapping — safe references only, never raw content (no __dict__ copy)."""
    return AgentTaskQueueRecord(
        id=_ID_PREFIX + uuid.uuid4().hex[:16],  # server-controlled
        owner_id=request.owner_id,
        client_id=request.client_id,
        engagement_id=request.engagement_id,
        authorization_scope=request.authorization_scope,  # validated == stored scope
        agent_name=draft.agent_name,
        task_type=draft.task_type,
        requested_action=draft.requested_action,
        source_ingestion_record_id=draft.source_ingestion_record_id,
        readiness_state=draft.readiness_state,
        review_status=REQUIRED_REVIEW_STATUS,  # review-gated (server-stamped)
        lifecycle_status=REQUIRED_LIFECYCLE_STATUS,
        output_status=REQUIRED_OUTPUT_STATUS,
        execution_status=REQUIRED_EXECUTION_STATUS,  # never-executed (server-stamped)
        authoritative=False,
        client_facing_approved=False,
        capsule_candidate_ready=False,
        execution_allowed=False,
        llm_execution_allowed=False,
        agentnet_context_allowed=False,
        resolver_context_allowed=False,
        network_allowed=False,
        requires_human_review=True,
        idempotency_key=request.idempotency_key,
        payload_fingerprint=fingerprint,
        created_by=request.requested_by,
        # created_at / updated_at are DB server_default (server-stamped).
        details_json={
            "task_input_ref": list(draft.task_input_ref or []),
            "safe_input_summary": draft.task_input_summary,
            "evidence_reference_ids": list(draft.evidence_reference_ids or []),
            "packet_processing_run_ref": draft.packet_processing_run_ref,
            "orchestration_ref": draft.orchestration_ref,
            "prompt_contract_path": draft.prompt_contract_path,
            "workflow": getattr(draft, "workflow", None),
            "reasons": list(draft.reasons or []),
            "warnings": list(draft.warnings or []),
            "source_phase": getattr(request, "source_phase", None),
        },
    )


def _find_existing(session, request: ControlledWriteRequest, idem: str):
    """Look up an existing row on the idempotency boundary (owner/client/engagement/key)."""
    return (
        session.query(AgentTaskQueueRecord)
        .filter_by(
            owner_id=request.owner_id,
            client_id=request.client_id,
            engagement_id=request.engagement_id,
            idempotency_key=idem,
        )
        .one_or_none()
    )


def _receipt_from_existing(existing: AgentTaskQueueRecord, idem: str,
                           outcome: str) -> AgentTaskQueueWriteReceipt:
    return AgentTaskQueueWriteReceipt(
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
        execution_status=existing.execution_status,
        readiness_state=existing.readiness_state,
        reasons=["exact authorized replay; existing record returned, not modified"],
    )


def persist_agent_task_queue_record(
    controlled_write_request,
    *,
    session_factory=None,
    readiness_request=None,
) -> AgentTaskQueueWriteReceipt:
    """Create one review-gated, **not-executed** ``agent_task_queue_records`` row.

    ``session_factory`` is a zero-arg callable returning a SQLAlchemy ``Session`` (defaults to
    the controlled-DB session factory from the environment URL). ``readiness_request`` is an
    optional Phase 26 ``AgentTaskQueueRequest`` / ``AgentTaskQueueReadinessResult`` accepted for
    forward compatibility; the write-time authorization gate never trusts it.

    Returns an :class:`AgentTaskQueueWriteReceipt`; expected governance failures are typed
    denials, not exceptions. This writer executes no agent and creates no ``agent_run_records``
    row.
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
                    existing, idem, AgentTaskQueueWriteOutcome.IDEMPOTENT_REPLAY
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
            # Uniqueness race: re-query INLINE so a race is still classifiable.
            session.rollback()
            raced = (
                session.query(AgentTaskQueueRecord)
                .filter_by(owner_id=request.owner_id, client_id=request.client_id,
                           engagement_id=request.engagement_id, idempotency_key=idem)
                .one_or_none()
            )
            if raced is not None and raced.payload_fingerprint == fingerprint:
                return _receipt_from_existing(
                    raced, idem, AgentTaskQueueWriteOutcome.IDEMPOTENT_REPLAY
                )
            if raced is not None:
                return _deny("idempotency_conflict",
                             "idempotency key reused with a different payload/identity (race)",
                             database_connection_made=True, sql_execution_made=True,
                             existing_record_returned=False)
            return AgentTaskQueueWriteReceipt(
                outcome=AgentTaskQueueWriteOutcome.WRITE_OUTCOME_UNCERTAIN, permitted=True,
                reason_code="integrity_no_row", idempotency_key=idem,
                database_connection_made=True, sql_execution_made=True,
                database_write_made=False, stored_record_created=False,
                transaction_committed=False, outcome_uncertain=True,
                reasons=["integrity conflict without a matching row; write outcome uncertain"],
            )

        session.refresh(record)  # load server-stamped created_at/updated_at
        created_iso = record.created_at.isoformat() if record.created_at else None
        return AgentTaskQueueWriteReceipt(
            outcome=AgentTaskQueueWriteOutcome.CREATED,
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
            execution_status=record.execution_status,
            readiness_state=record.readiness_state,
            created_at=created_iso,
            database_write_at=created_iso,
            reasons=["created one review-gated, not-executed agent_task_queue_records row"],
        )

    except SQLAlchemyError as exc:  # infrastructure failure
        try:
            session.rollback()
        except Exception:  # noqa: BLE001 - rollback best-effort; never re-raise here
            pass
        safe = type(exc).__name__  # never leak SQL / connection / content details
        if attempted_commit:
            return AgentTaskQueueWriteReceipt(
                outcome=AgentTaskQueueWriteOutcome.WRITE_OUTCOME_UNCERTAIN, permitted=True,
                reason_code="commit_uncertain", idempotency_key=idem,
                database_connection_made=True, sql_execution_made=True,
                database_write_made=False, stored_record_created=False,
                transaction_committed=False, outcome_uncertain=True,
                reasons=[f"commit outcome could not be confirmed ({safe}); a record may or "
                         "may not exist"],
            )
        return AgentTaskQueueWriteReceipt(
            outcome=AgentTaskQueueWriteOutcome.FAILED_BEFORE_WRITE, permitted=True,
            reason_code="failed_before_write", idempotency_key=idem,
            database_connection_made=True, sql_execution_made=True,
            database_write_made=False, stored_record_created=False,
            transaction_committed=False, outcome_uncertain=False,
            reasons=[f"infrastructure failure before any write ({safe}); no row created"],
        )
    finally:
        session.close()
