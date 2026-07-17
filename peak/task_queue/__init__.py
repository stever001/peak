"""Peak Controlled Agent Task Queue / Execution Readiness Boundary (Phase 26).

A **readiness/queue-planning boundary**, not an executor, task runner, job queue, workflow
engine, or DB writer. It accepts derived Phase 13 ``AgentTaskRequest`` objects (typically
produced by the Phase 23 ingestion boundary and surfaced by the Phase 25 orchestrator) and
prepares **production-shaped but review-gated** Agent Task Queue drafts and Execution Readiness
assessments — **without executing any agent, calling any LLM/AgentNet/resolver, touching the
network, or writing to the database.**

This phase is analogous to Phase 23: Phase 23 prepared source ingestion / packet-derived plans
without DB writes; Phase 26 prepares task-queue / execution-readiness plans without DB writes.
A future Phase 27 may add a narrow DB-backed writer for ``agent_task_queue_records``; Phase 26
builds only a plan-only Phase 17 ``ControlledWriteRequest`` artifact for it and never calls a
writer. "Ready" here never means "execute now": every valid task still requires human review,
``execution_allowed`` stays ``False``, and no live flag is ever set.

DB writers, agents, LLMs, AgentNet/MCP/resolver, and the network are never imported or called.
This package imports only stdlib plus the DB-free Phase 13 registry and Phase 17 controlled-write
contracts. See docs/AGENT_TASK_QUEUE_READINESS_BOUNDARY.md and
docs/AGENT_TASK_QUEUE_GOVERNANCE_POLICY.md.
"""

from __future__ import annotations

from .contracts import (
    AGENT_TASK_QUEUE_ACTION,
    AGENT_TASK_QUEUE_TABLE,
    ALLOWED_QUEUE_ACTIONS,
    BLOCKED_BY_POLICY,
    BLOCKED_INVALID_SCOPE,
    BLOCKED_LIFECYCLE,
    BLOCKED_MISSING_EVIDENCE,
    BLOCKED_STATES,
    BLOCKED_UNKNOWN_AGENT,
    EVIDENCE_DEPENDENT_WORKFLOWS,
    OUTCOME_BLOCKED,
    OUTCOME_DENIED,
    OUTCOME_PARTIAL,
    OUTCOME_PLANNED,
    QUEUED_FOR_REVIEW,
    READINESS_STATES,
    READY_FOR_FUTURE_CONTROLLED_EXECUTION,
    AgentExecutionReadinessAssessment,
    AgentTaskQueueDraft,
    AgentTaskQueuePlan,
    AgentTaskQueueReadinessResult,
    AgentTaskQueueRequest,
    AgentTaskQueueValidationResult,
    StageName,
)
from .governance import (
    AgentTaskQueueGovernanceDecision,
    TaskReadinessClassification,
    classify_task_readiness,
    evaluate_agent_task_queue_request,
    task_identity_mismatches,
)
from .task_queue_mapper import (
    build_queue_controlled_write_request,
    build_queue_draft,
    prepare_agent_task_queue_plan,
    validate_agent_task_queue_request,
)

__all__ = [
    # contracts
    "AgentTaskQueueRequest",
    "AgentTaskQueueDraft",
    "AgentExecutionReadinessAssessment",
    "AgentTaskQueuePlan",
    "AgentTaskQueueReadinessResult",
    "AgentTaskQueueValidationResult",
    "StageName",
    "AGENT_TASK_QUEUE_TABLE",
    "AGENT_TASK_QUEUE_ACTION",
    "ALLOWED_QUEUE_ACTIONS",
    "EVIDENCE_DEPENDENT_WORKFLOWS",
    "READINESS_STATES",
    "BLOCKED_STATES",
    "QUEUED_FOR_REVIEW",
    "READY_FOR_FUTURE_CONTROLLED_EXECUTION",
    "BLOCKED_BY_POLICY",
    "BLOCKED_MISSING_EVIDENCE",
    "BLOCKED_UNKNOWN_AGENT",
    "BLOCKED_INVALID_SCOPE",
    "BLOCKED_LIFECYCLE",
    "OUTCOME_DENIED",
    "OUTCOME_PLANNED",
    "OUTCOME_PARTIAL",
    "OUTCOME_BLOCKED",
    # governance
    "AgentTaskQueueGovernanceDecision",
    "TaskReadinessClassification",
    "evaluate_agent_task_queue_request",
    "classify_task_readiness",
    "task_identity_mismatches",
    # mapper / entry points
    "prepare_agent_task_queue_plan",
    "validate_agent_task_queue_request",
    "build_queue_draft",
    "build_queue_controlled_write_request",
]
