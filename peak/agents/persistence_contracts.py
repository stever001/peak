"""Contracts for the Agent Run Persistence Mapping (Phase 19).

**DB-aware but not DB-writing.** These dataclasses describe how a Phase 13 agent run output
(``AgentTaskResult`` + ``AgentRunDraft``) is mapped into a *future* controlled write plan for
the ``agent_run_records`` table — the persistence draft, the request, the decision, and the
mapping result — **without connecting to a database, importing a live SQLAlchemy session,
executing SQL, persisting records, or reading records.**

This module is domain-specific agent-run persistence mapping. It lives in ``peak.agents``
(the agent domain) but is deliberately kept out of ``peak.db`` and imports no SQLAlchemy, no
Alembic, and no ``peak.db`` session/model modules. It *does* bridge two existing boundaries —
the Phase 13 agent contracts (``peak.agents.contracts``) and the Phase 17 controlled-write
contracts (``peak.persistence``) — because Phase 19 connects them.

**Source contracts only — no stored records.** Nothing here opens a database connection,
runs SQL, writes a file, calls an LLM/AgentNet/MCP/resolver, touches the network, produces
client-facing output, or publishes a capsule. See docs/AGENT_RUN_PERSISTENCE_MAPPING.md and
docs/AGENT_RUN_WRITE_PLAN_POLICY.md.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import List, Optional

# The only persistence action Phase 19 plans, and the table/action it maps to.
ALLOWED_PERSISTENCE_ACTION = "prepare_agent_run_record_write_plan"
TARGET_TABLE = "agent_run_records"
TARGET_ACTION = "create_agent_run_record"

# Review-gated posture defaults carried onto every agent run persistence draft.
DEFAULT_OUTPUT_STATUS = "draft"
DEFAULT_REVIEW_STATUS = "needs_review"
DEFAULT_LIFECYCLE_STATUS = "active"


@dataclass
class AgentRunPersistenceSubjectSnapshot:
    """The stored engagement/client/subject that authorizes the agent run write.

    Because the new agent run record itself has **no stored DB row yet**, this snapshot is
    the scope anchor for the future write: ``stored_authorization_scope`` is the parent
    record's own persisted scope — the value a future controlled writer must compare the
    request scope against. In Phase 19 the caller supplies it in memory; a future
    controlled-DB reader would load it.
    """

    subject_record_id: Optional[str] = None
    subject_record_type: Optional[str] = None
    owner_id: Optional[str] = None
    client_id: Optional[str] = None
    engagement_id: Optional[str] = None
    stored_authorization_scope: Optional[str] = None
    stored_output_status: Optional[str] = None
    stored_review_status: Optional[str] = None
    stored_lifecycle_status: Optional[str] = None
    source_reference_id: Optional[str] = None


@dataclass
class AgentRunPersistenceRequest:
    """A request to map a Phase 13 agent run output into a controlled write plan."""

    owner_id: Optional[str] = None
    client_id: Optional[str] = None
    engagement_id: Optional[str] = None
    requested_by: Optional[str] = None
    requester_role: Optional[str] = None
    authorization_scope: Optional[str] = None
    agent_task_request: Optional[object] = None  # a Phase 13 AgentTaskRequest
    agent_task_result: Optional[object] = None  # a Phase 13 AgentTaskResult
    agent_run_draft: Optional[object] = None  # a Phase 13 AgentRunDraft
    subject_snapshot: Optional[AgentRunPersistenceSubjectSnapshot] = None
    requested_persistence_action: Optional[str] = None
    source_phase: Optional[str] = None
    idempotency_key: Optional[str] = None
    lifecycle_status: Optional[str] = None


@dataclass
class AgentRunPersistenceDraft:
    """A production-shaped but review-gated agent run draft (in-memory only; never stored).

    ``agent_run_record_id`` and ``created_at`` are left ``None`` — a future controlled DB
    writer assigns them. The no-side-effect posture is preserved: ``draft`` /
    ``needs_review`` and every "a call was made" flag ``False``.
    """

    agent_run_record_id: Optional[str] = None  # assigned by a future controlled-DB writer
    owner_id: Optional[str] = None
    client_id: Optional[str] = None
    engagement_id: Optional[str] = None
    agent_name: Optional[str] = None
    workflow: Optional[str] = None
    requested_action: Optional[str] = None
    input_record_ids: List[str] = field(default_factory=list)
    prompt_contract_path: Optional[str] = None
    resolver_context_requested: bool = False
    resolver_context_used: bool = False
    output_status: str = DEFAULT_OUTPUT_STATUS
    review_status: str = DEFAULT_REVIEW_STATUS
    lifecycle_status: str = DEFAULT_LIFECYCLE_STATUS
    permitted: bool = False
    llm_call_made: bool = False
    agentnet_call_made: bool = False
    database_write_made: bool = False
    network_call_made: bool = False
    client_facing_output_created: bool = False
    capsule_publication_made: bool = False
    reasons: List[str] = field(default_factory=list)
    warnings: List[str] = field(default_factory=list)
    created_at: Optional[str] = None  # reserved for future controlled-DB assignment


@dataclass
class AgentRunPersistenceDecision:
    """Result of the pre-mapping governance checks (no side effects)."""

    permitted: bool = False
    persistence_action: Optional[str] = None
    target_table: Optional[str] = None
    requested_action: Optional[str] = None
    reasons: List[str] = field(default_factory=list)
    warnings: List[str] = field(default_factory=list)


@dataclass
class AgentRunPersistenceMappingResult:
    """The controlled result of mapping an agent run into a write plan (no side effects)."""

    permitted: bool = False
    status: str = "rejected"
    agent_run_persistence_draft: Optional[AgentRunPersistenceDraft] = None
    controlled_write_request: Optional[object] = None  # a Phase 17 ControlledWriteRequest
    controlled_write_result: Optional[object] = None  # a Phase 17 ControlledWriteResult
    database_write_made: bool = False
    database_connection_made: bool = False
    sql_execution_made: bool = False
    stored_record_created: bool = False
    llm_call_made: bool = False
    agentnet_call_made: bool = False
    network_call_made: bool = False
    capsule_publication_made: bool = False
    client_facing_output_created: bool = False
    reasons: List[str] = field(default_factory=list)
    warnings: List[str] = field(default_factory=list)
