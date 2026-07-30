"""Managed Record Workflow — governed workflow integration over the existing writers (Phase 35).

A **workflow integration layer**, not a new persistence primitive. It sequences six already durable
record types through the narrow controlled DB writers that already exist, under explicit per-stage
persistence gates:

1. ``intake_note_records``               (Phase 34 ``persist_intake_note_record``)
2. ``source_ingestion_records``          (Phase 24 ``persist_source_ingestion_record``)
3. ``evidence_references``               (Phase 21 ``persist_evidence_reference``)
4. ``agent_task_queue_records``          (Phase 27 ``persist_agent_task_queue_record``)
5. ``review_bundle_records``             (Phase 30 ``persist_review_bundle_record``)
6. ``internal_reviewer_decision_records`` (Phase 33 ``persist_internal_reviewer_decision_record``)

Phase 35 adds **no DB table, model, or migration** (Alembic head stays ``009_intake_note_records``;
``make db-check`` stays at 15 tables), **no new Phase 17 allowlist pair**, no generic CRUD, no raw
SQL executor, and no broad repository. It calls **no** Phase 22 review writer and **no** agent-run
writer — ``review_records`` and ``agent_run_records`` are never written by this layer. It creates no
client-facing output, verifies no financial impact, publishes no capsule, executes no agent or LLM,
and makes no AgentNet / MCP / resolver / network call.

**Plan-only is the default.** A stage persists only when its gate is explicitly ``True``, its
payload is present and safe, and a ``session_factory`` is supplied. This layer never falls back to
an ambient environment DSN: a gated stage with no injected ``session_factory`` is denied before any
connection is opened, so standard validation needs no live database credentials and no network.

Authorization is **not** weakened here. Each narrow writer still loads the stored ``Engagement`` and
compares its stored ``authorization_scope`` at write time; the pre-flight identity checks in
``peak.workflows.governance`` are defense in depth that stop cross-tenant / cross-engagement
payloads before a writer is ever invoked.

The writers (which do use SQLAlchemy) are imported **lazily** inside the persistence step, so this
module imports and runs plan-only without a database driver installed.

See docs/MANAGED_RECORD_WORKFLOW_INTEGRATION.md and
docs/WORKFLOW_INTEGRATION_GOVERNANCE_POLICY.md.
"""

from __future__ import annotations

from peak.persistence.contracts import ControlledWriteRequest, ControlledWriteSubject

from .contracts import (
    HALTING_STAGE_OUTCOMES,
    STAGE_AGENT_TASK_QUEUE,
    STAGE_EVIDENCE_REFERENCE,
    STAGE_INTAKE_NOTE,
    STAGE_PAYLOAD_ATTRS,
    STAGE_REVIEW_BUNDLE,
    STAGE_REVIEWER_DECISION,
    STAGE_SOURCE_INGESTION,
    STAGE_TARGETS,
    WORKFLOW_STAGES,
    ManagedRecordWorkflowResult,
    WorkflowOutcome,
    WorkflowStageOutcome,
    WorkflowStageReceipt,
    WorkflowStageResult,
)
from .governance import (
    derive_stage_idempotency_key,
    evaluate_stage_payload,
    evaluate_workflow_request,
    sanitize_messages,
)

# Narrow-writer outcome strings (mirrored, not imported, so this module needs no peak.db import).
_WRITER_CREATED = "created"
_WRITER_REPLAY = "idempotent_replay"
_WRITER_DENIED = "denied"
_WRITER_FAILED = "failed_before_write"
_WRITER_UNCERTAIN = "write_outcome_uncertain"
_CONFLICT_REASON = "idempotency_conflict"


def run_managed_record_workflow(request, *, session_factory=None) -> ManagedRecordWorkflowResult:
    """Run one governed managed-record workflow and return a sanitized aggregate result.

    ``request`` is a :class:`~peak.workflows.contracts.ManagedRecordWorkflowRequest` carrying
    already-shaped stage drafts and an explicit ``persistence_gates`` map. ``session_factory`` is a
    zero-arg callable returning a SQLAlchemy ``Session``, passed straight through to the narrow
    writers; it is **required** for any gated stage and is never defaulted from the environment.

    Expected governance failures are typed denials, not exceptions. The result never echoes intake
    note text, raw packet/evidence/interview text, source bytes, generated agent output,
    credentials, DSNs, raw SQL, stack traces, client-facing language, or approval decisions.
    """
    result = ManagedRecordWorkflowResult()

    # --- 1. Request pre-flight (DB-free; no connection opened on denial) ---
    decision = evaluate_workflow_request(request)
    if not decision.permitted:
        result.outcome = WorkflowOutcome.DENIED
        result.permitted = False
        result.reason_code = decision.reason_code
        result.reasons = sanitize_messages(decision.reasons)
        result.warnings = sanitize_messages(decision.warnings)
        return result

    result.workflow_id = request.workflow_id
    result.owner_id = request.owner_id
    result.client_id = request.client_id
    result.engagement_id = request.engagement_id
    result.authorization_scope = request.authorization_scope
    result.strict_mode = bool(request.strict_mode)
    result.warnings.extend(sanitize_messages(decision.warnings))

    gates = {stage: bool((request.persistence_gates or {}).get(stage, False))
             for stage in WORKFLOW_STAGES}
    payloads = {stage: getattr(request, STAGE_PAYLOAD_ATTRS[stage], None)
                for stage in WORKFLOW_STAGES}
    result.stages_requested = [s for s in WORKFLOW_STAGES if payloads[s] is not None or gates[s]]

    # --- 2. Run the stages in workflow order; a halting stage stops every later stage ---
    for stage in WORKFLOW_STAGES:
        if result.halted_after_stage is not None:
            stage_result = WorkflowStageResult(
                stage=stage, outcome=WorkflowStageOutcome.HALTED,
                gate_enabled=gates[stage], payload_present=payloads[stage] is not None,
                reason_code="halted_by_earlier_stage",
                reasons=[f"stage not attempted: the workflow halted after "
                         f"'{result.halted_after_stage}'"])
            _record_stage(result, stage_result)
            continue

        stage_result = _run_stage(result, request, stage, gates[stage], payloads[stage],
                                  session_factory)
        _record_stage(result, stage_result)

        if stage_result.outcome in HALTING_STAGE_OUTCOMES:
            result.halted_after_stage = stage
            result.reasons.append(f"workflow halted after stage '{stage}' "
                                  f"({stage_result.reason_code or stage_result.outcome})")
            continue
        # Strict mode: any stage warning halts the workflow after that stage. Non-strict mode
        # collects the warning and continues — a warning creates no approval or client-facing
        # effect in either mode.
        if request.strict_mode and stage_result.warnings:
            result.halted_after_stage = stage
            result.reason_code = result.reason_code or "strict_mode_warning"
            result.reasons.append(f"strict_mode: workflow halted after stage '{stage}' "
                                  "because the stage produced a warning")

    _finalize(result)
    return result


# --------------------------------------------------------------------------- stage execution


def _run_stage(result, request, stage: str, gate: bool, payload,
               session_factory) -> WorkflowStageResult:
    """Execute (or plan, or skip) exactly one workflow stage."""
    table, action = STAGE_TARGETS[stage]
    stage_result = WorkflowStageResult(
        stage=stage, gate_enabled=gate, payload_present=payload is not None,
        target_table=table, target_action=action)

    # 2a. Nothing requested for this stage.
    if payload is None and not gate:
        stage_result.outcome = WorkflowStageOutcome.SKIPPED
        stage_result.reason_code = "not_requested"
        stage_result.reasons.append(f"stage '{stage}' has no payload and no persistence gate")
        return stage_result

    # 2b. Gate on, payload missing -> deny without invoking the writer.
    if payload is None and gate:
        stage_result.outcome = WorkflowStageOutcome.DENIED
        stage_result.reason_code = "missing_stage_payload"
        stage_result.reasons.append(
            f"stage '{stage}' persistence gate is enabled but {STAGE_PAYLOAD_ATTRS[stage]} "
            "is missing")
        return stage_result

    # 2c. Payload safety + identity consistency. Runs in plan-only mode too, so an unsafe payload
    #     is reported before it can ever be gated on. No DB connection is opened either way.
    payload_decision = evaluate_stage_payload(request, stage, payload)
    stage_result.warnings.extend(sanitize_messages(payload_decision.warnings))
    if not payload_decision.permitted:
        stage_result.outcome = WorkflowStageOutcome.DENIED
        stage_result.reason_code = payload_decision.reason_code
        stage_result.reasons.extend(sanitize_messages(payload_decision.reasons))
        return stage_result

    # 2d. Deterministic stage idempotency key (needed for the plan record as well as the write).
    key, key_source, key_denial = derive_stage_idempotency_key(request, stage, payload)
    if key_denial is not None:
        stage_result.outcome = WorkflowStageOutcome.DENIED
        stage_result.reason_code = key_denial
        stage_result.reasons.append(
            f"stage '{stage}': supply stage_idempotency_keys['{stage}'] or a workflow_id so a "
            "deterministic stage key can be derived"
            if key_denial == "missing_stage_idempotency_key"
            else f"stage '{stage}': derived idempotency key exceeds the writer's length bound")
        return stage_result
    stage_result.idempotency_key = key
    stage_result.idempotency_key_source = key_source
    result.stage_idempotency_keys[stage] = key

    # 2e. Gate off -> plan only. No writer is called and no connection is opened.
    if not gate:
        stage_result.outcome = WorkflowStageOutcome.PLANNED
        stage_result.reason_code = "plan_only_gate_disabled"
        stage_result.reasons.append(
            f"stage '{stage}' planned only: persistence_gates['{stage}'] is not enabled")
        return stage_result

    # 2f. Gate on but no injected session factory -> fail closed (never reach for an ambient DSN).
    if session_factory is None:
        stage_result.outcome = WorkflowStageOutcome.DENIED
        stage_result.reason_code = "missing_session_factory"
        stage_result.reasons.append(
            f"stage '{stage}' persistence gate is enabled but no session_factory was injected; "
            "this layer never falls back to an environment database URL")
        return stage_result

    # 2g. Invoke exactly one narrow controlled writer under the stage's own gate.
    controlled_write_request = _build_controlled_write_request(request, stage, payload, key)
    writer_receipt = _call_writer(stage, controlled_write_request, session_factory)
    stage_result.writer_called = True
    _apply_writer_receipt(result, stage_result, stage, writer_receipt)
    return stage_result


def _build_controlled_write_request(request, stage: str, payload, idempotency_key: str):
    """Build the Phase 17 ``ControlledWriteRequest`` for one stage.

    Identity, authorization scope, requester identity, and the stage idempotency key are all
    propagated from the workflow request. The stored ``Engagement`` named by ``subject_record_id``
    remains the authorization anchor — this object only *proposes* the write; the narrow writer
    re-validates it and compares the stored scope.
    """
    table, action = STAGE_TARGETS[stage]
    subject_id = request.subject_record_id or request.engagement_id
    subject = ControlledWriteSubject(
        subject_record_id=subject_id,
        subject_record_type="engagement",
        owner_id=request.owner_id,
        client_id=request.client_id,
        engagement_id=request.engagement_id,
        stored_authorization_scope=request.authorization_scope,
    )
    return ControlledWriteRequest(
        owner_id=request.owner_id,
        client_id=request.client_id,
        engagement_id=request.engagement_id,
        requested_by=request.requested_by,
        requester_role=request.requester_role,
        authorization_scope=request.authorization_scope,
        target_table=table,
        requested_action=action,
        subject=subject,
        record_draft=payload,
        source_phase=request.source_phase or "phase35",
        lifecycle_status=request.lifecycle_status,
        idempotency_key=idempotency_key,
    )


def _call_writer(stage: str, controlled_write_request, session_factory):
    """Call the one narrow controlled writer that owns this stage's table (lazy import).

    Only these six existing writer functions are ever reachable from this layer. No generic writer,
    no raw SQL executor, no Phase 22 review writer, no agent-run writer, no publication code.
    """
    if stage == STAGE_INTAKE_NOTE:
        from peak.db.intake_note_writer import persist_intake_note_record
        return persist_intake_note_record(controlled_write_request,
                                          session_factory=session_factory)
    if stage == STAGE_SOURCE_INGESTION:
        from peak.db.source_ingestion_writer import persist_source_ingestion_record
        return persist_source_ingestion_record(controlled_write_request,
                                               session_factory=session_factory)
    if stage == STAGE_EVIDENCE_REFERENCE:
        from peak.db.evidence_writer import persist_evidence_reference
        return persist_evidence_reference(controlled_write_request,
                                          session_factory=session_factory)
    if stage == STAGE_AGENT_TASK_QUEUE:
        from peak.db.agent_task_queue_writer import persist_agent_task_queue_record
        return persist_agent_task_queue_record(controlled_write_request,
                                               session_factory=session_factory)
    if stage == STAGE_REVIEW_BUNDLE:
        from peak.db.review_bundle_writer import persist_review_bundle_record
        return persist_review_bundle_record(controlled_write_request,
                                            session_factory=session_factory)
    if stage == STAGE_REVIEWER_DECISION:
        from peak.db.internal_reviewer_decision_writer import (
            persist_internal_reviewer_decision_record,
        )
        return persist_internal_reviewer_decision_record(controlled_write_request,
                                                         session_factory=session_factory)
    raise KeyError(stage)  # pragma: no cover - stage list is closed


# --------------------------------------------------------------------------- receipt handling


def _sanitized_receipt(stage: str, writer_receipt) -> WorkflowStageReceipt:
    """Copy only the safe fields out of a narrow-writer receipt (no content, no SQL, no DSN)."""
    def g(name, default=None):
        return getattr(writer_receipt, name, default)

    return WorkflowStageReceipt(
        stage=stage,
        target_table=g("target_table"),
        target_action=g("target_action"),
        writer_outcome=g("outcome"),
        permitted=bool(g("permitted", False)),
        reason_code=g("reason_code"),
        stored_record_id=g("stored_record_id"),
        idempotency_key=g("idempotency_key"),
        review_status=g("review_status"),
        lifecycle_status=g("lifecycle_status"),
        created_at=g("created_at"),
        database_connection_made=bool(g("database_connection_made", False)),
        sql_execution_made=bool(g("sql_execution_made", False)),
        database_write_made=bool(g("database_write_made", False)),
        stored_record_created=bool(g("stored_record_created", False)),
        existing_record_returned=bool(g("existing_record_returned", False)),
        transaction_committed=bool(g("transaction_committed", False)),
        outcome_uncertain=bool(g("outcome_uncertain", False)),
        reasons=sanitize_messages(g("reasons") or []),
        warnings=sanitize_messages(g("warnings") or []),
    )


def _apply_writer_receipt(result, stage_result, stage: str, writer_receipt) -> None:
    """Map one narrow-writer receipt onto the stage result and the aggregate side-effect flags."""
    receipt = _sanitized_receipt(stage, writer_receipt)
    stage_result.receipt = receipt
    stage_result.reason_code = receipt.reason_code
    stage_result.reasons.extend(receipt.reasons)
    stage_result.warnings.extend(receipt.warnings)

    # Aggregate the *actual*-behavior flags reported by the writer.
    result.database_connection_made |= receipt.database_connection_made
    result.sql_execution_made |= receipt.sql_execution_made
    result.database_write_made |= receipt.database_write_made
    result.stored_record_created |= receipt.stored_record_created

    outcome = receipt.writer_outcome
    if outcome == _WRITER_CREATED:
        stage_result.outcome = WorkflowStageOutcome.PERSISTED
        table = receipt.target_table or STAGE_TARGETS[stage][0]
        result.table_write_counts[table] = result.table_write_counts.get(table, 0) + 1
    elif outcome == _WRITER_REPLAY:
        stage_result.outcome = WorkflowStageOutcome.REPLAYED
    elif outcome == _WRITER_FAILED:
        stage_result.outcome = WorkflowStageOutcome.FAILED_BEFORE_WRITE
    elif outcome == _WRITER_UNCERTAIN:
        stage_result.outcome = WorkflowStageOutcome.WRITE_OUTCOME_UNCERTAIN
    elif receipt.reason_code == _CONFLICT_REASON:
        stage_result.outcome = WorkflowStageOutcome.CONFLICTED
    else:
        stage_result.outcome = WorkflowStageOutcome.DENIED

    if receipt.stored_record_id and stage_result.outcome in (
        WorkflowStageOutcome.PERSISTED, WorkflowStageOutcome.REPLAYED
    ):
        stage_result.created_record_ref = receipt.stored_record_id
        result.created_record_refs[stage] = receipt.stored_record_id


_OUTCOME_BUCKETS = {
    WorkflowStageOutcome.PLANNED: "stages_planned",
    WorkflowStageOutcome.SKIPPED: "stages_skipped",
    WorkflowStageOutcome.PERSISTED: "stages_persisted",
    WorkflowStageOutcome.REPLAYED: "stages_replayed",
    WorkflowStageOutcome.DENIED: "stages_denied",
    WorkflowStageOutcome.CONFLICTED: "stages_conflicted",
    WorkflowStageOutcome.FAILED_BEFORE_WRITE: "stages_denied",
    WorkflowStageOutcome.WRITE_OUTCOME_UNCERTAIN: "stages_denied",
    WorkflowStageOutcome.HALTED: "stages_halted",
}


def _record_stage(result, stage_result) -> None:
    """File one stage result into the aggregate result's bookkeeping."""
    result.stage_results[stage_result.stage] = stage_result
    bucket = _OUTCOME_BUCKETS.get(stage_result.outcome)
    if bucket:
        getattr(result, bucket).append(stage_result.stage)
    if stage_result.receipt is not None:
        result.receipts[stage_result.stage] = stage_result.receipt
    result.warnings.extend(stage_result.warnings)


def _finalize(result) -> None:
    """Set the aggregate outcome. Non-effect flags stay False — this layer produces none of them."""
    wrote = bool(result.stages_persisted or result.stages_replayed)
    if result.halted_after_stage is not None:
        result.outcome = WorkflowOutcome.PARTIAL if wrote else WorkflowOutcome.HALTED
        result.permitted = wrote
        result.reason_code = result.reason_code or "halted_after_stage"
    elif wrote:
        result.outcome = WorkflowOutcome.PERSISTED
        result.permitted = True
    else:
        result.outcome = WorkflowOutcome.PLANNED
        result.permitted = True
        result.reason_code = result.reason_code or "plan_only"
