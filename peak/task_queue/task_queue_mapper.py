"""Deterministic agent-task-queue / execution-readiness mapping helpers (Phase 26).

Maps derived Phase 13 ``AgentTaskRequest`` objects into **production-shaped but review-gated**,
no-side-effect plans:

    AgentTaskQueueRequest (carrying Phase 13 AgentTaskRequest[])
      -> AgentExecutionReadinessAssessment[]  (deterministic readiness states)
      -> AgentTaskQueueDraft[]                 (review-gated; never persisted; never executed)
      -> Phase 17 ControlledWriteRequest[]     (plan only; a write plan is not a write)
      -> no DB write, no agent/LLM/AgentNet/resolver/network call

Nothing here opens a database connection or imports SQLAlchemy / Alembic / ``peak.db``;
executes a live or mock agent/LLM; makes an AgentNet/MCP/resolver/network call; calls a Phase
20/21/22/24 DB writer; creates client-facing output; verifies financial impact; or publishes a
capsule. Every derived draft stays ``draft`` / ``needs_review`` / ``not_executed`` with
``execution_allowed=False``. It imports **only** other DB-free, no-side-effect Peak contracts
(the Phase 13 agents registry and the Phase 17 controlled-write contracts).

This mirrors Phase 23: it prepares queue/readiness plans exactly as Phase 23 prepared source
ingestion plans — without writing anything. A future Phase 27 may add a narrow DB-backed writer
for ``agent_task_queue_records``; Phase 26 builds only the plan-only request artifact for it.
See docs/AGENT_TASK_QUEUE_READINESS_BOUNDARY.md and docs/AGENT_TASK_QUEUE_GOVERNANCE_POLICY.md.
"""

from __future__ import annotations

from typing import List, Optional

# DB-free, no-side-effect contracts from earlier phases (none import peak.db / SQLAlchemy).
from peak.agents.registry import get_agent
from peak.persistence.contracts import ControlledWriteRequest, ControlledWriteSubject

from .contracts import (
    AGENT_TASK_QUEUE_ACTION,
    AGENT_TASK_QUEUE_TABLE,
    BLOCKED_STATES,
    OUTCOME_BLOCKED,
    OUTCOME_DENIED,
    OUTCOME_PARTIAL,
    OUTCOME_PLANNED,
    AgentExecutionReadinessAssessment,
    AgentTaskQueueDraft,
    AgentTaskQueuePlan,
    AgentTaskQueueReadinessResult,
    AgentTaskQueueRequest,
    AgentTaskQueueValidationResult,
    StageName,
)
from .governance import (
    classify_task_readiness,
    evaluate_agent_task_queue_request,
    task_identity_mismatches,
)

_QUEUE_PLAN_WARNING = (
    "agent task queue plans are not writes and not executions — no database connection is "
    "opened, no SQL runs, no agent/LLM/AgentNet/resolver/network call is made, and no queue "
    "record is stored; a future narrow agent_task_queue_records writer (not this phase) is "
    "required to persist a row"
)


def _derived_idempotency_key(base_key, index: int, agent_name) -> str:
    """Deterministic per-task idempotency key so queue drafts do not collide on the boundary."""
    return f"{base_key}::taskq::{index}::{agent_name}"


def _task_input_summary(task) -> str:
    """A safe count/shape summary of a task's inputs — never raw content."""
    ids = list(getattr(task, "input_record_ids", []) or [])
    return f"{len(ids)} input record id(s)"


def validate_agent_task_queue_request(
    request: AgentTaskQueueRequest,
) -> AgentTaskQueueValidationResult:
    """Build the structured request-level ``AgentTaskQueueValidationResult``."""
    governance = evaluate_agent_task_queue_request(request)
    tasks = getattr(request, "agent_task_requests", None) or []
    has_tasks = isinstance(tasks, (list, tuple)) and len(tasks) > 0

    scope_valid = not _is_blank(getattr(request, "authorization_scope", None))
    identity_valid = all(
        not _is_blank(getattr(request, a, None))
        for a in ("owner_id", "client_id", "engagement_id")
    )
    contains_prohibited = any(
        "prohibited" in r for r in governance.reasons
    )
    return AgentTaskQueueValidationResult(
        permitted=governance.permitted,
        identity_valid=identity_valid,
        scope_valid=scope_valid,
        has_tasks=has_tasks,
        contains_prohibited_content=contains_prohibited,
        reasons=list(governance.reasons),
        warnings=list(governance.warnings),
    )


def _is_blank(value) -> bool:
    return value is None or (isinstance(value, str) and not value.strip())


def build_queue_draft(
    request: AgentTaskQueueRequest, task, index: int
) -> AgentTaskQueueDraft:
    """Map one valid Phase 13 task into a review-gated ``AgentTaskQueueDraft`` (never stored).

    ``agent_task_queue_record_id`` and ``created_at`` are left ``None`` — a *future* narrow
    controlled DB writer assigns them. The review-gate and no-execution posture is stamped, not
    inherited. Only ids/references are carried; no raw payload/text.
    """
    entry = get_agent(getattr(task, "agent_name", None))
    workflow = getattr(entry, "workflow", None) or getattr(task, "workflow", None)
    prompt_contract_path = getattr(entry, "prompt_contract_path", None) or getattr(
        task, "prompt_contract_path", None
    )
    return AgentTaskQueueDraft(
        agent_task_queue_record_id=None,  # future controlled-DB writer assigns; nothing stored
        owner_id=getattr(request, "owner_id", None),
        client_id=getattr(request, "client_id", None),
        engagement_id=getattr(request, "engagement_id", None),
        agent_name=getattr(task, "agent_name", None),
        workflow=workflow,
        task_type=workflow,
        requested_action=getattr(task, "requested_action", None),
        task_input_ref=list(getattr(task, "input_record_ids", []) or []),
        task_input_summary=_task_input_summary(task),
        source_ingestion_record_id=getattr(request, "source_ingestion_record_id", None),
        evidence_reference_ids=list(getattr(request, "evidence_reference_ids", []) or []),
        prompt_contract_path=prompt_contract_path,
        authorization_scope=getattr(request, "authorization_scope", None),
        idempotency_key=_derived_idempotency_key(
            getattr(request, "idempotency_key", None), index, getattr(task, "agent_name", None)
        ),
        output_status="draft",
        review_status="needs_review",
        lifecycle_status="draft",
        authoritative=False,
        client_facing_approved=False,
        capsule_candidate_ready=False,
        execution_status="not_executed",
        execution_allowed=False,
        llm_execution_allowed=False,
        agentnet_context_allowed=False,
        resolver_context_allowed=False,
        network_allowed=False,
        requires_human_review=True,
        reasons=[],
        warnings=[_QUEUE_PLAN_WARNING],
        created_at=None,  # reserved for future controlled-DB assignment
    )


def build_queue_controlled_write_request(
    request: AgentTaskQueueRequest, draft: AgentTaskQueueDraft
) -> ControlledWriteRequest:
    """Build a Phase 17 ``ControlledWriteRequest`` for a *future* agent_task_queue_records write.

    A **plan only** — nothing is executed and no DB writer is called. The target table
    ``agent_task_queue_records`` is not yet on the Phase 17 allowlist and has no writer; a future
    Phase 27 would add both. The subject remains the engagement (the authorization anchor a
    future writer would re-load and re-check at write time).
    """
    subject = ControlledWriteSubject(
        subject_record_id=getattr(request, "engagement_id", None),
        subject_record_type="engagement",
        owner_id=getattr(request, "owner_id", None),
        client_id=getattr(request, "client_id", None),
        engagement_id=getattr(request, "engagement_id", None),
        stored_authorization_scope=getattr(request, "authorization_scope", None),
    )
    return ControlledWriteRequest(
        owner_id=getattr(request, "owner_id", None),
        client_id=getattr(request, "client_id", None),
        engagement_id=getattr(request, "engagement_id", None),
        requested_by=getattr(request, "requested_by", None),
        requester_role=getattr(request, "requester_role", None),
        authorization_scope=getattr(request, "authorization_scope", None),
        target_table=AGENT_TASK_QUEUE_TABLE,
        requested_action=AGENT_TASK_QUEUE_ACTION,
        subject=subject,
        record_draft=draft,
        source_phase=getattr(request, "source_phase", None) or "phase26",
        lifecycle_status=getattr(request, "lifecycle_status", None),
        idempotency_key=draft.idempotency_key,
    )


def _denied_result(
    request: AgentTaskQueueRequest, governance, validation_result
) -> AgentTaskQueueReadinessResult:
    """Build a side-effect-free denied result (governance rejected the whole request)."""
    return AgentTaskQueueReadinessResult(
        outcome=OUTCOME_DENIED,
        permitted=False,
        reason_code=governance.reason_code or "queue_request_denied",
        status="rejected",
        validation_result=validation_result,
        plan=None,
        task_count_received=len(getattr(request, "agent_task_requests", []) or []),
        queue_draft_count=0,
        readiness_assessment_count=0,
        controlled_write_request_count=0,
        blocked_task_count=0,
        stages_completed=[StageName.VALIDATE_REQUEST],
        stages_skipped=[
            StageName.CLASSIFY_READINESS,
            StageName.BUILD_QUEUE_DRAFTS,
            StageName.PLAN_CONTROLLED_WRITES,
        ],
        reasons=list(governance.reasons),
        warnings=list(governance.warnings),
    )


def prepare_agent_task_queue_plan(
    request: AgentTaskQueueRequest,
) -> AgentTaskQueueReadinessResult:
    """Prepare a no-side-effect agent task queue / execution readiness plan.

    Public entry point. Returns a fully typed ``AgentTaskQueueReadinessResult`` with all
    side-effect flags ``False``. No agent is executed, no LLM/AgentNet/resolver/network call is
    made, and no DB row is written.
    """
    governance = evaluate_agent_task_queue_request(request)
    validation_result = validate_agent_task_queue_request(request)

    if not governance.permitted:
        return _denied_result(request, governance, validation_result)

    tasks = list(getattr(request, "agent_task_requests", []) or [])
    assessments: List[AgentExecutionReadinessAssessment] = []
    drafts: List[AgentTaskQueueDraft] = []
    write_requests: List[ControlledWriteRequest] = []
    warnings: List[str] = [_QUEUE_PLAN_WARNING]
    blocked_count = 0

    for index, task in enumerate(tasks):
        classification = classify_task_readiness(request, task, index)
        assessment = AgentExecutionReadinessAssessment(
            agent_name=getattr(task, "agent_name", None),
            task_index=index,
            readiness_state=classification.readiness_state,
            blocked=classification.blocked,
            requires_human_review=True,
            execution_allowed=False,
            missing_evidence=classification.missing_evidence,
            reasons=list(classification.reasons),
            warnings=list(classification.warnings),
        )
        if classification.blocked or classification.readiness_state in BLOCKED_STATES:
            blocked_count += 1
            warnings.extend(classification.reasons)
            assessments.append(assessment)
            continue
        draft = build_queue_draft(request, task, index)
        assessment.queue_draft_idempotency_key = draft.idempotency_key
        drafts.append(draft)
        write_requests.append(build_queue_controlled_write_request(request, draft))
        assessments.append(assessment)

    plan = AgentTaskQueuePlan(
        permitted=True,
        queue_drafts=drafts,
        readiness_assessments=assessments,
        controlled_write_requests=write_requests,
        reasons=[],
        warnings=warnings,
    )

    if drafts and blocked_count == 0:
        outcome = OUTCOME_PLANNED
        status = "queue_plan_prepared"
    elif drafts and blocked_count > 0:
        outcome = OUTCOME_PARTIAL
        status = "queue_plan_partial"
    else:
        outcome = OUTCOME_BLOCKED
        status = "all_tasks_blocked"

    return AgentTaskQueueReadinessResult(
        outcome=outcome,
        permitted=True,
        reason_code=None,
        status=status,
        validation_result=validation_result,
        plan=plan,
        task_count_received=len(tasks),
        queue_draft_count=len(drafts),
        readiness_assessment_count=len(assessments),
        controlled_write_request_count=len(write_requests),
        blocked_task_count=blocked_count,
        stages_completed=[
            StageName.VALIDATE_REQUEST,
            StageName.CLASSIFY_READINESS,
            StageName.BUILD_QUEUE_DRAFTS,
            StageName.PLAN_CONTROLLED_WRITES,
        ],
        stages_skipped=[],
        reasons=[],
        warnings=warnings,
    )
