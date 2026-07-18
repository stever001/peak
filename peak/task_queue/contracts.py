"""Contracts for the Controlled Agent Task Queue / Execution Readiness Boundary (Phase 26).

**A readiness/queue-planning boundary, not an executor and not a DB writer.** These
lightweight dataclasses describe how Peak turns derived Phase 13 ``AgentTaskRequest`` objects
into **production-shaped but review-gated** Agent Task Queue drafts and Execution Readiness
assessments — **without executing any agent, calling any LLM/AgentNet/resolver, touching the
network, or writing to the database.** A queue draft is a plan for a *future* controlled
execution phase (after human review); it is never a run and never a stored row.

Nothing here opens a database connection or imports SQLAlchemy / Alembic / ``peak.db``; calls
a live or mock agent/LLM; makes an AgentNet/MCP/resolver/network call; creates client-facing
output; verifies financial impact; or publishes a capsule. Every "a call/write happened" flag
defaults to ``False``, and every draft stays ``draft`` / ``needs_review`` / ``not_executed``
with ``execution_allowed=False``. This module analogises Phase 23 (which prepared source
ingestion plans without DB writes): Phase 26 prepares task-queue/readiness plans without DB
writes. See docs/AGENT_TASK_QUEUE_READINESS_BOUNDARY.md and
docs/AGENT_TASK_QUEUE_GOVERNANCE_POLICY.md.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import List, Optional

# The only queue action Phase 26 plans.
ALLOWED_QUEUE_ACTIONS = frozenset({"prepare_agent_task_queue_plan"})

# The future controlled-write target for an agent task queue record. This table is **not yet**
# on the Phase 17 allowlist and no writer exists — a future Phase 27 would add both. Phase 26
# only builds a plan-only ``ControlledWriteRequest`` artifact for it; nothing is written.
AGENT_TASK_QUEUE_TABLE = "agent_task_queue_records"
AGENT_TASK_QUEUE_ACTION = "create_agent_task_queue_record"

# Review-gate defaults carried onto every queue draft.
DEFAULT_OUTPUT_STATUS = "draft"
DEFAULT_REVIEW_STATUS = "needs_review"
DEFAULT_LIFECYCLE_STATUS = "draft"

# Workflows whose agents structurally consume prior evidence; a queue draft for one of these
# with no evidence input wired is marked ``blocked_missing_evidence``.
EVIDENCE_DEPENDENT_WORKFLOWS = frozenset({"reporting", "proposal", "qa"})

# --- Execution readiness states (deterministic) ------------------------------------------
QUEUED_FOR_REVIEW = "queued_for_review"
BLOCKED_BY_POLICY = "blocked_by_policy"
BLOCKED_MISSING_EVIDENCE = "blocked_missing_evidence"
BLOCKED_UNKNOWN_AGENT = "blocked_unknown_agent"
BLOCKED_INVALID_SCOPE = "blocked_invalid_scope"
BLOCKED_LIFECYCLE = "blocked_lifecycle"
# "Ready" here means **structurally ready for a later controlled execution phase after
# review** — it never means "execute now". ``execution_allowed`` stays ``False`` and
# ``requires_human_review`` stays ``True`` even in this state.
READY_FOR_FUTURE_CONTROLLED_EXECUTION = "ready_for_future_controlled_execution"

READINESS_STATES = frozenset(
    {
        QUEUED_FOR_REVIEW,
        BLOCKED_BY_POLICY,
        BLOCKED_MISSING_EVIDENCE,
        BLOCKED_UNKNOWN_AGENT,
        BLOCKED_INVALID_SCOPE,
        BLOCKED_LIFECYCLE,
        READY_FOR_FUTURE_CONTROLLED_EXECUTION,
    }
)
BLOCKED_STATES = frozenset(
    {
        BLOCKED_BY_POLICY,
        BLOCKED_MISSING_EVIDENCE,
        BLOCKED_UNKNOWN_AGENT,
        BLOCKED_INVALID_SCOPE,
        BLOCKED_LIFECYCLE,
    }
)

# --- Orchestration-level outcomes --------------------------------------------------------
OUTCOME_DENIED = "denied"        # request-level governance denied the whole request
OUTCOME_PLANNED = "planned"      # every task became a review-gated queue draft
OUTCOME_PARTIAL = "partial"      # some tasks queued, some blocked
OUTCOME_BLOCKED = "blocked"      # every task was blocked (request itself was permitted)


class StageName:
    """Deterministic stage identifiers reported on the result."""

    VALIDATE_REQUEST = "validate_request"
    CLASSIFY_READINESS = "classify_readiness"
    BUILD_QUEUE_DRAFTS = "build_queue_drafts"
    PLAN_CONTROLLED_WRITES = "plan_controlled_writes"


@dataclass
class AgentTaskQueueRequest:
    """A request to prepare (never execute) an agent task queue / readiness plan.

    ``agent_task_requests`` are Phase 13 ``AgentTaskRequest`` objects (typically derived by the
    Phase 23 ingestion boundary and surfaced by the Phase 25 orchestrator). **No raw packet
    payload, raw evidence/interview text, source bytes, credentials, or arbitrary client data
    may be supplied** — only ids/references and safe metadata. ``context`` is optional safe
    metadata whose keys are scanned for prohibited terms.
    """

    owner_id: Optional[str] = None
    client_id: Optional[str] = None
    engagement_id: Optional[str] = None
    requested_by: Optional[str] = None
    requester_role: Optional[str] = None
    authorization_scope: Optional[str] = None
    idempotency_key: Optional[str] = None
    agent_task_requests: List[object] = field(default_factory=list)  # Phase 13 AgentTaskRequest
    source_ingestion_record_id: Optional[str] = None
    evidence_reference_ids: List[str] = field(default_factory=list)
    packet_processing_run_ref: Optional[str] = None
    orchestration_ref: Optional[str] = None
    context: Optional[dict] = None  # safe metadata only; keys are scanned for prohibited terms
    reason: Optional[str] = None
    requested_action: Optional[str] = "prepare_agent_task_queue_plan"
    source_phase: Optional[str] = None
    lifecycle_status: Optional[str] = None


@dataclass
class AgentTaskQueueDraft:
    """A production-shaped but review-gated agent task queue draft (in-memory only).

    ``agent_task_queue_record_id`` and ``created_at`` are left ``None`` — a *future* narrow
    controlled DB writer (not this phase) assigns them. Nothing here is persisted, and no agent
    is executed. ``task_input_ref`` carries only ids/references (never raw payload/text).
    """

    agent_task_queue_record_id: Optional[str] = None  # future controlled-DB writer assigns
    owner_id: Optional[str] = None
    client_id: Optional[str] = None
    engagement_id: Optional[str] = None
    agent_name: Optional[str] = None
    workflow: Optional[str] = None
    task_type: Optional[str] = None
    requested_action: Optional[str] = None
    task_input_ref: List[str] = field(default_factory=list)  # input record ids only, never raw text
    task_input_summary: Optional[str] = None  # a safe count/shape summary, never raw content
    source_ingestion_record_id: Optional[str] = None
    evidence_reference_ids: List[str] = field(default_factory=list)
    packet_processing_run_ref: Optional[str] = None
    orchestration_ref: Optional[str] = None
    prompt_contract_path: Optional[str] = None
    authorization_scope: Optional[str] = None
    idempotency_key: Optional[str] = None  # deterministic per-task key
    readiness_state: Optional[str] = None  # non-blocked readiness state (Phase 26 classification)
    output_status: str = DEFAULT_OUTPUT_STATUS
    review_status: str = DEFAULT_REVIEW_STATUS
    lifecycle_status: str = DEFAULT_LIFECYCLE_STATUS
    authoritative: bool = False
    client_facing_approved: bool = False
    capsule_candidate_ready: bool = False
    execution_status: str = "not_executed"
    execution_allowed: bool = False
    llm_execution_allowed: bool = False
    agentnet_context_allowed: bool = False
    resolver_context_allowed: bool = False
    network_allowed: bool = False
    requires_human_review: bool = True
    reasons: List[str] = field(default_factory=list)
    warnings: List[str] = field(default_factory=list)
    created_at: Optional[str] = None  # reserved for future controlled-DB assignment


@dataclass
class AgentExecutionReadinessAssessment:
    """A deterministic execution-readiness assessment for one agent task (no execution)."""

    agent_name: Optional[str] = None
    task_index: int = 0
    readiness_state: str = QUEUED_FOR_REVIEW
    blocked: bool = False
    requires_human_review: bool = True
    execution_allowed: bool = False  # never True in Phase 26
    missing_evidence: bool = False
    queue_draft_idempotency_key: Optional[str] = None
    reasons: List[str] = field(default_factory=list)
    warnings: List[str] = field(default_factory=list)


@dataclass
class AgentTaskQueuePlan:
    """The controlled, no-side-effect queue/readiness plan derived from the request."""

    permitted: bool = False
    queue_drafts: List[AgentTaskQueueDraft] = field(default_factory=list)
    readiness_assessments: List[AgentExecutionReadinessAssessment] = field(default_factory=list)
    controlled_write_requests: List[object] = field(default_factory=list)  # Phase 17 CWRs (plans only)
    direct_database_write_made: bool = False
    database_connection_made: bool = False
    sql_execution_made: bool = False
    stored_record_created: bool = False
    agent_execution_made: bool = False
    mock_agent_execution_made: bool = False
    llm_call_made: bool = False
    agentnet_call_made: bool = False
    resolver_call_made: bool = False
    network_call_made: bool = False
    client_facing_output_created: bool = False
    financial_verification_made: bool = False
    capsule_publication_made: bool = False
    reasons: List[str] = field(default_factory=list)
    warnings: List[str] = field(default_factory=list)


@dataclass
class AgentTaskQueueValidationResult:
    """Result of the deterministic request-level validation."""

    permitted: bool = False
    identity_valid: bool = False
    scope_valid: bool = False
    has_tasks: bool = False
    contains_prohibited_content: bool = False
    reasons: List[str] = field(default_factory=list)
    warnings: List[str] = field(default_factory=list)


@dataclass
class AgentTaskQueueReadinessResult:
    """The controlled result of preparing an agent task queue / readiness plan (no side effects)."""

    outcome: str = OUTCOME_DENIED
    permitted: bool = False
    reason_code: Optional[str] = None
    status: str = "rejected"
    validation_result: Optional[AgentTaskQueueValidationResult] = None
    plan: Optional[AgentTaskQueuePlan] = None
    task_count_received: int = 0
    queue_draft_count: int = 0
    readiness_assessment_count: int = 0
    controlled_write_request_count: int = 0
    blocked_task_count: int = 0
    stages_completed: List[str] = field(default_factory=list)
    stages_skipped: List[str] = field(default_factory=list)
    reasons: List[str] = field(default_factory=list)
    warnings: List[str] = field(default_factory=list)
    # Aggregate side-effect flags — all stay False in Phase 26.
    direct_database_write_made: bool = False
    database_connection_made: bool = False
    sql_execution_made: bool = False
    stored_record_created: bool = False
    agent_execution_made: bool = False
    mock_agent_execution_made: bool = False
    llm_call_made: bool = False
    agentnet_call_made: bool = False
    resolver_call_made: bool = False
    network_call_made: bool = False
    client_facing_output_created: bool = False
    financial_verification_made: bool = False
    capsule_publication_made: bool = False
