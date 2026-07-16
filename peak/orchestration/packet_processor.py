"""Controlled Engagement Packet Processing Orchestrator (Phase 25).

A **controlled sequencing layer** over existing narrow boundaries. It accepts a Phase 23
``PacketIngestionRequest``, routes it through the Phase 23 ingestion boundary, exposes the
derived plan (source ingestion draft + plan-only controlled write request, Phase 14 evidence
normalization requests, Phase 13 agent task requests), and — **only when explicitly requested
and a ``session_factory`` is supplied** — persists through the existing narrow DB writers
(Phase 24 source-ingestion, Phase 21 evidence). It **never** invents a generic writer, writes
an unsupported table, executes an agent or LLM, calls AgentNet/MCP/resolver/network, creates
client-facing output, verifies financial impact, or publishes a capsule.

Plan-only is the default and is no-side-effect: no DB writer, no DB connection, no SQL, no
stored record, all side-effect flags ``False``. No stage silently escalates from plan-only to
persistence. Receipts carry only counts, ids, stage names, safe metadata, warnings, and reason
codes — never raw packet payload, raw evidence/interview text, credentials, SQL, connection
URLs, or stack traces.

Agent-run persistence (Phase 19/20) is intentionally left **plan-only** here: wiring it would
require running the Phase 13 mock executor (which consults the disabled ``MockLLM`` interface)
and synthesizing a run subject — breadth this narrow orchestrator declines. It is reported as
``skipped_no_safe_contract_path`` with a clear reason.

DB writers are imported **lazily** inside the persistence stages, so this module (and plan-only
mode) imports and runs without SQLAlchemy. See docs/CONTROLLED_PACKET_PROCESSING_ORCHESTRATOR.md
and docs/PACKET_PROCESSING_ORCHESTRATION_POLICY.md.
"""

from __future__ import annotations

from typing import List, Optional

# DB-free, no-side-effect upstream contracts/helpers (none import peak.db / SQLAlchemy).
from peak.evidence.evidence_record_mapper import prepare_evidence_persistence
from peak.evidence.persistence_contracts import (
    EvidencePersistenceRequest,
    EvidencePersistenceSubjectSnapshot,
)
from peak.ingestion.packet_mapper import prepare_packet_ingestion
from peak.workers.evidence_normalization import normalize_evidence

from .contracts import (
    STAGE_AGENT_RUN_RECORD_PERSISTENCE,
    STAGE_AGENT_RUN_RECORD_PLANNING,
    STAGE_AGENT_TASK_PLANNING,
    STAGE_EVIDENCE_NORMALIZATION,
    STAGE_EVIDENCE_PERSISTENCE,
    STAGE_SOURCE_INGESTION_PERSISTENCE,
    OrchestrationOutcome,
    OrchestrationStageOptions,
    PacketProcessingReceipt,
    StageOutcome,
    StageResult,
)
from .governance import derived_identity_mismatches, evaluate_orchestration_request

# Writer outcome (str) -> orchestration stage outcome (str).
_WRITER_OUTCOME_TO_STAGE = {
    "created": StageOutcome.COMPLETED,
    "idempotent_replay": StageOutcome.COMPLETED,
    "denied": StageOutcome.DENIED,
    "failed_before_write": StageOutcome.FAILED_BEFORE_WRITE,
    "write_outcome_uncertain": StageOutcome.WRITE_OUTCOME_UNCERTAIN,
}
_FAILURE_OUTCOMES = frozenset(
    {StageOutcome.DENIED, StageOutcome.FAILED_BEFORE_WRITE, StageOutcome.WRITE_OUTCOME_UNCERTAIN}
)
# Reason explaining why agent-run persistence is not wired in this phase (no secret content).
_AGENT_RUN_DEFERRED_REASON = (
    "agent run record persistence is not wired in Phase 25: it would require running the "
    "Phase 13 mock executor (which consults the disabled MockLLM interface) and synthesizing a "
    "run subject; deferred to keep orchestration narrow and LLM-interface-free"
)


def _stages_requested(options: OrchestrationStageOptions) -> List[str]:
    requested: List[str] = []
    if options.include_evidence_normalization:
        requested.append(STAGE_EVIDENCE_NORMALIZATION)
    if options.include_agent_task_planning:
        requested.append(STAGE_AGENT_TASK_PLANNING)
    if options.include_source_ingestion_persistence:
        requested.append(STAGE_SOURCE_INGESTION_PERSISTENCE)
    if options.include_evidence_persistence:
        requested.append(STAGE_EVIDENCE_PERSISTENCE)
    if options.include_agent_run_record_planning:
        requested.append(STAGE_AGENT_RUN_RECORD_PLANNING)
    if options.include_agent_run_record_persistence:
        requested.append(STAGE_AGENT_RUN_RECORD_PERSISTENCE)
    return requested


def _record_stage(receipt: PacketProcessingReceipt, stage: str, outcome: str,
                  reason: Optional[str] = None, item_count: int = 0,
                  writer_receipt: Optional[object] = None) -> None:
    receipt.stage_results.append(
        StageResult(stage=stage, outcome=outcome, reason=reason, item_count=item_count,
                    receipt=writer_receipt)
    )
    if outcome == StageOutcome.COMPLETED:
        receipt.stages_completed.append(stage)
    elif outcome in _FAILURE_OUTCOMES:
        receipt.stages_failed.append(stage)
    else:
        receipt.stages_skipped.append(stage)
    if reason:
        receipt.warnings.append(f"{stage}: {reason}")


def _apply_writer_flags(receipt: PacketProcessingReceipt, w) -> str:
    """OR a narrow-writer receipt's DB flags into the aggregate and map its outcome."""
    receipt.database_connection_made = receipt.database_connection_made or bool(
        getattr(w, "database_connection_made", False))
    receipt.sql_execution_made = receipt.sql_execution_made or bool(
        getattr(w, "sql_execution_made", False))
    receipt.database_write_made = receipt.database_write_made or bool(
        getattr(w, "database_write_made", False))
    receipt.stored_record_created = receipt.stored_record_created or bool(
        getattr(w, "stored_record_created", False))
    return _WRITER_OUTCOME_TO_STAGE.get(getattr(w, "outcome", None), StageOutcome.DENIED)


def _persistence_skip(options, session_factory, plan_only, has_plan) -> Optional[str]:
    """Return a skip outcome for a persistence stage, or None if it should run."""
    if plan_only:
        return StageOutcome.SKIPPED_PLAN_ONLY
    if session_factory is None:
        return StageOutcome.SKIPPED_MISSING_SESSION_FACTORY
    if not has_plan:
        return StageOutcome.SKIPPED_NO_SAFE_CONTRACT_PATH
    return None


def process_engagement_packet(
    request,
    *,
    options: Optional[OrchestrationStageOptions] = None,
    session_factory=None,
) -> PacketProcessingReceipt:
    """Orchestrate controlled processing of one engagement packet (plan-only by default)."""
    options = options or OrchestrationStageOptions()
    receipt = PacketProcessingReceipt(plan_only=bool(options.plan_only))
    receipt.stages_requested = _stages_requested(options)

    # --- Preflight governance (advisory; DB writers remain authoritative) ---
    governance = evaluate_orchestration_request(request)
    if not governance.permitted:
        receipt.orchestration_outcome = OrchestrationOutcome.DENIED
        receipt.permitted = False
        receipt.reason_code = governance.reason_code
        receipt.reasons = list(governance.reasons)
        return receipt

    # --- Phase 23 ingestion boundary (DB-free; validates the packet, derives the plan) ---
    ingestion_result = prepare_packet_ingestion(request)
    receipt.packet_ingestion_result = ingestion_result
    if not getattr(ingestion_result, "permitted", False):
        receipt.orchestration_outcome = OrchestrationOutcome.DENIED
        receipt.permitted = False
        receipt.reason_code = "packet_ingestion_denied"
        receipt.reasons = list(getattr(ingestion_result, "reasons", []) or [])
        receipt.warnings.extend(getattr(ingestion_result, "warnings", []) or [])
        return receipt

    plan = getattr(ingestion_result, "ingestion_plan", None)
    source_draft = getattr(plan, "source_ingestion_draft", None) if plan is not None else None
    cwrs = getattr(plan, "controlled_write_requests", []) if plan is not None else []
    source_cwr = cwrs[0] if cwrs else None
    evidence_plan = getattr(plan, "evidence_plan", None) if plan is not None else None
    agent_plan = getattr(plan, "agent_task_plan", None) if plan is not None else None
    evidence_requests = list(getattr(evidence_plan, "evidence_requests", []) or [])
    agent_task_requests = list(getattr(agent_plan, "agent_task_requests", []) or [])

    receipt.source_ingestion_draft = source_draft
    receipt.source_controlled_write_request = source_cwr
    receipt.evidence_normalization_requests = evidence_requests
    receipt.agent_task_requests = agent_task_requests
    if agent_plan is not None:
        receipt.warnings.extend(getattr(agent_plan, "warnings", []) or [])

    # --- Derived-identity preflight (advisory) ---
    mismatches: List[str] = []
    if source_draft is not None:
        mismatches += derived_identity_mismatches(request, source_draft, "source_ingestion_draft")
    for i, ev in enumerate(evidence_requests):
        mismatches += derived_identity_mismatches(request, ev, f"evidence_request[{i}]")
    for i, at in enumerate(agent_task_requests):
        mismatches += derived_identity_mismatches(request, at, f"agent_task_request[{i}]")
    if mismatches:
        receipt.orchestration_outcome = OrchestrationOutcome.DENIED
        receipt.permitted = False
        receipt.reason_code = "derived_identity_mismatch"
        receipt.reasons = mismatches
        return receipt

    receipt.permitted = True

    # --- Stage: evidence normalization (DB-free deterministic worker) ---
    normalized_records: List[object] = []
    if options.include_evidence_normalization:
        for i, ev in enumerate(evidence_requests):
            result = normalize_evidence(ev)
            if getattr(result, "permitted", False) and getattr(result, "normalized_record", None):
                normalized_records.append((ev, result))
            else:
                receipt.warnings.append(f"evidence_request[{i}] not normalizable; skipped")
        receipt.evidence_normalization_count = len(normalized_records)
        _record_stage(receipt, STAGE_EVIDENCE_NORMALIZATION, StageOutcome.COMPLETED,
                      item_count=len(normalized_records))
    else:
        _record_stage(receipt, STAGE_EVIDENCE_NORMALIZATION, StageOutcome.SKIPPED_NOT_REQUESTED)

    # --- Stage: agent task planning (DB-free; exposes derived Phase 13 requests) ---
    if options.include_agent_task_planning:
        receipt.agent_task_count = len(agent_task_requests)
        _record_stage(receipt, STAGE_AGENT_TASK_PLANNING, StageOutcome.COMPLETED,
                      item_count=len(agent_task_requests))
    else:
        _record_stage(receipt, STAGE_AGENT_TASK_PLANNING, StageOutcome.SKIPPED_NOT_REQUESTED)

    # --- Stage: source ingestion persistence (Phase 24 writer) ---
    if not options.include_source_ingestion_persistence:
        _record_stage(receipt, STAGE_SOURCE_INGESTION_PERSISTENCE, StageOutcome.SKIPPED_NOT_REQUESTED)
    else:
        skip = _persistence_skip(options, session_factory, options.plan_only, source_cwr is not None)
        if skip is not None:
            reason = ("no source_ingestion controlled write request was produced"
                      if skip == StageOutcome.SKIPPED_NO_SAFE_CONTRACT_PATH else None)
            _record_stage(receipt, STAGE_SOURCE_INGESTION_PERSISTENCE, skip, reason=reason)
        else:
            from peak.db.source_ingestion_writer import persist_source_ingestion_record

            w = persist_source_ingestion_record(
                source_cwr, session_factory=session_factory, persistence_request=request)
            receipt.source_ingestion_persistence_receipt = w
            outcome = _apply_writer_flags(receipt, w)
            _record_stage(receipt, STAGE_SOURCE_INGESTION_PERSISTENCE, outcome,
                          reason=getattr(w, "reason_code", None), writer_receipt=w)

    # --- Stage: evidence persistence (Phase 18 mapping -> Phase 21 writer) ---
    if not options.include_evidence_persistence:
        _record_stage(receipt, STAGE_EVIDENCE_PERSISTENCE, StageOutcome.SKIPPED_NOT_REQUESTED)
    else:
        skip = _persistence_skip(options, session_factory, options.plan_only,
                                 bool(normalized_records))
        if skip is not None:
            reason = ("no safe contract path: evidence normalization produced no records "
                      "(enable include_evidence_normalization)"
                      if skip == StageOutcome.SKIPPED_NO_SAFE_CONTRACT_PATH else None)
            _record_stage(receipt, STAGE_EVIDENCE_PERSISTENCE, skip, reason=reason)
        else:
            _run_evidence_persistence(receipt, request, normalized_records, session_factory)

    # --- Stage: agent run record planning / persistence (intentionally deferred) ---
    if options.include_agent_run_record_planning:
        _record_stage(receipt, STAGE_AGENT_RUN_RECORD_PLANNING,
                      StageOutcome.SKIPPED_NO_SAFE_CONTRACT_PATH, reason=_AGENT_RUN_DEFERRED_REASON)
    if options.include_agent_run_record_persistence:
        _record_stage(receipt, STAGE_AGENT_RUN_RECORD_PERSISTENCE,
                      StageOutcome.SKIPPED_NO_SAFE_CONTRACT_PATH, reason=_AGENT_RUN_DEFERRED_REASON)

    _finalize_outcome(receipt, options)
    return receipt


def _run_evidence_persistence(receipt, request, normalized_records, session_factory) -> None:
    """Persist each normalized evidence record via Phase 18 mapping + the Phase 21 writer."""
    from peak.db.evidence_writer import persist_evidence_reference

    base_key = getattr(request, "idempotency_key", None)
    per_record_outcomes: List[str] = []
    for i, (_ev, norm_result) in enumerate(normalized_records):
        record = getattr(norm_result, "normalized_record", None)
        snapshot = EvidencePersistenceSubjectSnapshot(
            subject_record_id=request.engagement_id,
            subject_record_type="engagement",  # the Phase 21 writer's authorization anchor
            owner_id=request.owner_id,
            client_id=request.client_id,
            engagement_id=request.engagement_id,
            stored_authorization_scope=request.authorization_scope,
            stored_lifecycle_status="active",
            source_reference_id=getattr(record, "source_reference_id", None),
        )
        ev_request = EvidencePersistenceRequest(
            owner_id=request.owner_id,
            client_id=request.client_id,
            engagement_id=request.engagement_id,
            requested_by=request.requested_by,
            requester_role=request.requester_role,
            authorization_scope=request.authorization_scope,
            normalization_result=norm_result,
            normalized_record=record,
            subject_snapshot=snapshot,
            requested_persistence_action="prepare_evidence_reference_write_plan",
            source_phase="phase25",
            idempotency_key=f"{base_key}::evid::{i}",
            lifecycle_status="active",
        )
        mapping = prepare_evidence_persistence(ev_request)
        cwr = getattr(mapping, "controlled_write_request", None)
        if not getattr(mapping, "permitted", False) or cwr is None:
            receipt.warnings.append(f"evidence_request[{i}] mapping not permitted; skipped")
            per_record_outcomes.append(StageOutcome.DENIED)
            continue
        w = persist_evidence_reference(cwr, session_factory=session_factory,
                                       persistence_request=ev_request)
        receipt.evidence_persistence_receipts.append(w)
        per_record_outcomes.append(_apply_writer_flags(receipt, w))

    # Aggregate: worst-of the per-record outcomes governs the stage.
    if not per_record_outcomes:
        _record_stage(receipt, STAGE_EVIDENCE_PERSISTENCE, StageOutcome.SKIPPED_NO_SAFE_CONTRACT_PATH,
                      reason="no evidence records to persist")
        return
    if StageOutcome.WRITE_OUTCOME_UNCERTAIN in per_record_outcomes:
        stage_outcome = StageOutcome.WRITE_OUTCOME_UNCERTAIN
    elif StageOutcome.FAILED_BEFORE_WRITE in per_record_outcomes:
        stage_outcome = StageOutcome.FAILED_BEFORE_WRITE
    elif StageOutcome.DENIED in per_record_outcomes:
        stage_outcome = StageOutcome.DENIED
    else:
        stage_outcome = StageOutcome.COMPLETED
    _record_stage(receipt, STAGE_EVIDENCE_PERSISTENCE, stage_outcome,
                  item_count=len(receipt.evidence_persistence_receipts))


def _finalize_outcome(receipt: PacketProcessingReceipt, options: OrchestrationStageOptions) -> None:
    """Set the aggregate orchestration outcome from the stage results."""
    persistence_stages = {
        STAGE_SOURCE_INGESTION_PERSISTENCE,
        STAGE_EVIDENCE_PERSISTENCE,
        STAGE_AGENT_RUN_RECORD_PERSISTENCE,
    }
    persistence_results = [s for s in receipt.stage_results if s.stage in persistence_stages]
    any_failed = any(s.outcome in _FAILURE_OUTCOMES for s in persistence_results)
    any_completed = any(s.outcome == StageOutcome.COMPLETED for s in persistence_results)

    if options.plan_only:
        receipt.orchestration_outcome = OrchestrationOutcome.PLANNED
    elif any_failed:
        receipt.orchestration_outcome = OrchestrationOutcome.PARTIAL
    elif any_completed:
        receipt.orchestration_outcome = OrchestrationOutcome.PERSISTED
    else:
        # Persistence requested but every persistence stage was skipped -> effectively planned.
        receipt.orchestration_outcome = OrchestrationOutcome.PLANNED
