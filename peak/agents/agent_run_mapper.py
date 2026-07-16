"""Agent-run-to-controlled-write mapping helpers (Phase 19).

Deterministic, **DB-aware but not DB-writing**. Connects the Phase 13 agent execution
harness output to the Phase 17 controlled write boundary:

    AgentTaskResult / AgentRunDraft
      -> AgentRunPersistenceDraft            (production-shaped, review-gated)
      -> ControlledWriteSubject              (Phase 17)
      -> ControlledWriteRequest              (target agent_run_records / create_agent_run_record)
      -> ControlledWritePlan                 (Phase 17 no-op plan)
      -> no DB write

Nothing here opens a database connection or imports SQLAlchemy / Alembic / ``peak.db``;
executes no SQL; makes no LLM, AgentNet, MCP, resolver, network, or file call; creates no
client-facing output; and publishes no capsule. The no-side-effect posture (``draft`` /
``needs_review`` and every "a call was made" flag ``False``) is preserved, and
``agent_run_record_id`` / ``created_at`` stay ``None`` for future controlled-DB assignment.
See docs/AGENT_RUN_PERSISTENCE_MAPPING.md and docs/AGENT_RUN_WRITE_PLAN_POLICY.md.
"""

from __future__ import annotations

# Bridges two existing boundaries: the Phase 17 controlled-write contracts and its no-op
# planner. (No SQLAlchemy / Alembic / peak.db import — those stay out of this package.)
from peak.persistence.contracts import ControlledWriteRequest, ControlledWriteSubject
from peak.persistence.write_plan import prepare_controlled_write

from .persistence_contracts import (
    AgentRunPersistenceDraft,
    AgentRunPersistenceMappingResult,
    AgentRunPersistenceRequest,
    TARGET_ACTION,
    TARGET_TABLE,
)
from .persistence_governance import evaluate_agent_run_persistence_request

# Every result carries this so a caller can never mistake a plan for an executed write.
_WRITE_PLAN_WARNING = (
    "agent run write plan only — a write plan is not a write; no database connection is "
    "opened and no SQL runs. A future controlled DB writer is required to persist this "
    "agent_run_records draft under access control."
)


def build_agent_run_persistence_draft(
    request: AgentRunPersistenceRequest,
) -> AgentRunPersistenceDraft:
    """Map an ``AgentTaskResult`` + ``AgentRunDraft`` into a review-gated persistence draft.

    ``agent_run_record_id`` and ``created_at`` are left ``None`` — a future controlled DB
    writer assigns them. The no-side-effect posture is stamped, never inherited from a claim
    on the input: draft / needs_review and every "a call was made" flag false. The Phase 13
    ``AgentTaskResult`` has no ``network_call_made`` / ``capsule_publication_made`` field, so
    those are set false here (not read from the input).
    """
    draft = getattr(request, "agent_run_draft", None)
    result = getattr(request, "agent_task_result", None)
    task_request = getattr(request, "agent_task_request", None)

    # requested_action / input_record_ids come from the run draft, falling back to the task
    # request where the draft does not carry them.
    requested_action = getattr(task_request, "requested_action", None)
    input_record_ids = list(getattr(draft, "input_record_ids", None) or []) or list(
        getattr(task_request, "input_record_ids", None) or []
    )
    prompt_contract_path = getattr(draft, "prompt_contract_path", None) or getattr(
        result, "prompt_contract_path", None
    )

    return AgentRunPersistenceDraft(
        agent_run_record_id=None,  # assigned later by a controlled-DB writer; nothing stored here
        owner_id=getattr(request, "owner_id", None),
        client_id=getattr(request, "client_id", None),
        engagement_id=getattr(request, "engagement_id", None),
        agent_name=getattr(draft, "agent_name", None) or getattr(task_request, "agent_name", None),
        workflow=getattr(draft, "workflow", None) or getattr(task_request, "workflow", None),
        requested_action=requested_action,
        input_record_ids=input_record_ids,
        prompt_contract_path=prompt_contract_path,
        resolver_context_requested=bool(getattr(draft, "resolver_context_requested", False)),
        resolver_context_used=bool(getattr(draft, "resolver_context_used", False)),
        # Review-gated / no-side-effect posture — stamped, not inherited.
        output_status="draft",
        review_status="needs_review",
        lifecycle_status="active",
        permitted=bool(getattr(result, "permitted", False)),
        llm_call_made=False,
        agentnet_call_made=False,
        database_write_made=False,
        network_call_made=False,
        client_facing_output_created=False,
        capsule_publication_made=False,
        reasons=list(getattr(result, "reasons", []) or []),
        warnings=list(getattr(result, "warnings", []) or []),
        created_at=None,  # reserved for future controlled-DB assignment
    )


def build_controlled_write_subject(request: AgentRunPersistenceRequest) -> ControlledWriteSubject:
    """Build a Phase 17 ``ControlledWriteSubject`` from the stored subject snapshot."""
    snapshot = getattr(request, "subject_snapshot", None)
    return ControlledWriteSubject(
        subject_record_id=getattr(snapshot, "subject_record_id", None),
        subject_record_type=getattr(snapshot, "subject_record_type", None),
        owner_id=getattr(snapshot, "owner_id", None),
        client_id=getattr(snapshot, "client_id", None),
        engagement_id=getattr(snapshot, "engagement_id", None),
        stored_authorization_scope=getattr(snapshot, "stored_authorization_scope", None),
        stored_output_status=getattr(snapshot, "stored_output_status", None),
        stored_review_status=getattr(snapshot, "stored_review_status", None),
        stored_lifecycle_status=getattr(snapshot, "stored_lifecycle_status", None),
        source_reference_id=getattr(snapshot, "source_reference_id", None),
    )


def build_controlled_write_request(
    request: AgentRunPersistenceRequest, agent_run_persistence_draft: AgentRunPersistenceDraft
) -> ControlledWriteRequest:
    """Build a Phase 17 ``ControlledWriteRequest`` targeting agent_run_records."""
    return ControlledWriteRequest(
        owner_id=getattr(request, "owner_id", None),
        client_id=getattr(request, "client_id", None),
        engagement_id=getattr(request, "engagement_id", None),
        requested_by=getattr(request, "requested_by", None),
        requester_role=getattr(request, "requester_role", None),
        authorization_scope=getattr(request, "authorization_scope", None),
        target_table=TARGET_TABLE,
        requested_action=TARGET_ACTION,
        subject=build_controlled_write_subject(request),
        record_draft=agent_run_persistence_draft,
        source_phase=getattr(request, "source_phase", None) or "phase19",
        lifecycle_status=getattr(request, "lifecycle_status", None),
        idempotency_key=getattr(request, "idempotency_key", None),
    )


def prepare_agent_run_persistence(
    request: AgentRunPersistenceRequest,
) -> AgentRunPersistenceMappingResult:
    """Map an agent run output into a no-side-effect controlled write plan."""
    governance = evaluate_agent_run_persistence_request(request)

    if not governance.permitted:
        return AgentRunPersistenceMappingResult(
            permitted=False,
            status="rejected",
            agent_run_persistence_draft=None,
            controlled_write_request=None,
            controlled_write_result=None,
            database_write_made=False,
            database_connection_made=False,
            sql_execution_made=False,
            stored_record_created=False,
            llm_call_made=False,
            agentnet_call_made=False,
            network_call_made=False,
            capsule_publication_made=False,
            client_facing_output_created=False,
            reasons=list(governance.reasons),
            warnings=list(governance.warnings),
        )

    draft = build_agent_run_persistence_draft(request)
    write_request = build_controlled_write_request(request, draft)
    # Route through the Phase 17 boundary — a no-op ControlledWriteResult (no DB, no SQL).
    write_result = prepare_controlled_write(write_request)

    warnings = [_WRITE_PLAN_WARNING]
    warnings.extend(getattr(write_result, "warnings", []) or [])
    permitted = bool(getattr(write_result, "permitted", False))

    return AgentRunPersistenceMappingResult(
        permitted=permitted,
        status="write_plan_prepared" if permitted else "rejected",
        agent_run_persistence_draft=draft,
        controlled_write_request=write_request,
        controlled_write_result=write_result,
        database_write_made=False,
        database_connection_made=False,
        sql_execution_made=False,
        stored_record_created=False,
        llm_call_made=False,
        agentnet_call_made=False,
        network_call_made=False,
        capsule_publication_made=False,
        client_facing_output_created=False,
        reasons=list(getattr(write_result, "reasons", []) or []),
        warnings=warnings,
    )
