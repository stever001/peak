"""Contracts for the future Peak internal agent execution harness.

**Source contracts only — no live execution.** These lightweight dataclasses describe how
a future agent task is *requested*, governed, and recorded. Nothing here calls an LLM,
AgentNet, an MCP connector, a resolver, a database, or the network, and nothing produces
client-facing output.

Defaults encode the Phase 13 posture: agent output is `draft` / `needs_review`, and every
"a call was made" flag is ``False``. See docs/AGENT_EXECUTION_HARNESS.md and
docs/AGENT_RUN_RECORDS.md.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import List, Optional

# Default governance posture for any agent output in Phase 13.
DEFAULT_OUTPUT_STATUS = "draft"
DEFAULT_REVIEW_STATUS = "needs_review"
DEFAULT_LIFECYCLE_STATUS = "draft"


@dataclass
class AgentTaskRequest:
    """A request to run a future Peak internal agent/worker for one workflow step."""

    agent_name: Optional[str] = None
    workflow: Optional[str] = None
    owner_id: Optional[str] = None
    client_id: Optional[str] = None
    engagement_id: Optional[str] = None
    requested_action: Optional[str] = None
    input_record_ids: List[str] = field(default_factory=list)
    prompt_contract_path: Optional[str] = None
    authorization_scope: Optional[str] = None
    review_status: Optional[str] = None
    lifecycle_status: Optional[str] = None
    resolver_context_allowed: bool = False
    llm_execution_allowed: bool = False
    client_facing_output_requested: bool = False


@dataclass
class AgentTaskResult:
    """The controlled result of a (mock, non-executing) agent task."""

    permitted: bool = False
    status: str = "rejected"
    output_status: str = DEFAULT_OUTPUT_STATUS
    review_status: str = DEFAULT_REVIEW_STATUS
    lifecycle_status: str = DEFAULT_LIFECYCLE_STATUS
    reasons: List[str] = field(default_factory=list)
    warnings: List[str] = field(default_factory=list)
    prompt_contract_path: Optional[str] = None
    resolver_context_used: bool = False
    llm_call_made: bool = False
    agentnet_call_made: bool = False
    database_write_made: bool = False
    client_facing_output_created: bool = False


@dataclass
class AgentContextRequest:
    """Intent to load authorized engagement context for an agent (future)."""

    owner_id: Optional[str] = None
    client_id: Optional[str] = None
    engagement_id: Optional[str] = None
    input_record_ids: List[str] = field(default_factory=list)
    authorization_scope: Optional[str] = None
    resolver_context_allowed: bool = False


@dataclass
class AgentContextBundle:
    """The context a future agent would reason over.

    In Phase 13 nothing is loaded: ``loaded`` stays ``False`` and no records are read
    from any database, controlled store, or resolver.
    """

    owner_id: Optional[str] = None
    client_id: Optional[str] = None
    engagement_id: Optional[str] = None
    input_record_ids: List[str] = field(default_factory=list)
    loaded: bool = False
    resolver_context_used: bool = False
    resolver_boundary_note: str = ""
    warnings: List[str] = field(default_factory=list)


@dataclass
class PromptContractReference:
    """A pointer to an existing prompt-contract file (no prompt text is embedded)."""

    agent_name: Optional[str] = None
    workflow: Optional[str] = None
    prompt_contract_path: Optional[str] = None
    exists: bool = False


@dataclass
class AgentExecutionDecision:
    """Result of deterministic pre-execution governance checks."""

    agent_name: Optional[str] = None
    permitted: bool = False
    reasons: List[str] = field(default_factory=list)
    warnings: List[str] = field(default_factory=list)
    output_status: str = DEFAULT_OUTPUT_STATUS
    review_status: str = DEFAULT_REVIEW_STATUS
    llm_call_made: bool = False
    agentnet_call_made: bool = False
    database_write_made: bool = False
    client_facing_output_created: bool = False


@dataclass
class AgentRunDraft:
    """Shape helper for a *future* ``AgentRunRecord`` (see docs/AGENT_RUN_RECORDS.md).

    This is an in-memory draft only. **No agent run record is stored in Phase 13**;
    persisting one requires the controlled-database integration described in the docs.
    """

    agent_run_id: Optional[str] = None
    agent_name: Optional[str] = None
    workflow: Optional[str] = None
    owner_id: Optional[str] = None
    client_id: Optional[str] = None
    engagement_id: Optional[str] = None
    input_record_ids: List[str] = field(default_factory=list)
    prompt_contract_path: Optional[str] = None
    resolver_context_requested: bool = False
    resolver_context_used: bool = False
    llm_call_made: bool = False
    agentnet_call_made: bool = False
    database_write_made: bool = False
    output_record_ids: List[str] = field(default_factory=list)
    output_status: str = DEFAULT_OUTPUT_STATUS
    review_status: str = DEFAULT_REVIEW_STATUS
    lifecycle_status: str = DEFAULT_LIFECYCLE_STATUS
    warnings: List[str] = field(default_factory=list)
    reasons: List[str] = field(default_factory=list)
    created_at: Optional[str] = None
    created_by: Optional[str] = None
