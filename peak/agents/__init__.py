"""Peak internal agent execution harness — scaffold only.

Defines how future Peak internal agents/workers will be **invoked, governed, and
recorded**, without executing anything. Phase 13 makes **no live LLM, AgentNet, MCP,
resolver, database, API, or network call**, and produces **no client-facing output**.

Contents:
- ``contracts`` — request/result/decision/context/run-draft dataclasses.
- ``registry`` — the static catalog of the 10 known agents/workers.
- ``governance`` — deterministic pre-execution checks (draft/needs_review defaults).
- ``executor`` — a no-op mock executor that governs and plans a run but executes nothing.
- ``mock_llm`` — a no-op LLM interface (live execution disabled).

Phase 19 adds the **Agent Run Persistence Mapping** — mapping a Phase 13 agent run output
(``AgentTaskResult`` + ``AgentRunDraft``) into a *future* controlled write plan for the
``agent_run_records`` table via the Phase 17 boundary. It is **DB-aware but not
DB-writing**: no database connection, no SQL, no stored records, and the agent execution
harness still does not write directly to the DB.

- ``persistence_contracts`` — agent run persistence dataclasses.
- ``persistence_governance`` — deterministic pre-mapping checks (stored-scope, review-gate).
- ``agent_run_mapper`` — maps agent output → Phase 17 controlled write plan (no-op).

See docs/AGENT_EXECUTION_HARNESS.md, docs/AGENT_RUN_RECORDS.md,
docs/AGENT_RUN_PERSISTENCE_MAPPING.md, and docs/AGENT_RUN_WRITE_PLAN_POLICY.md.
"""

from __future__ import annotations

from .contracts import (
    AgentContextBundle,
    AgentContextRequest,
    AgentExecutionDecision,
    AgentRunDraft,
    AgentTaskRequest,
    AgentTaskResult,
    PromptContractReference,
)
from .executor import MockAgentExecutor, build_run_draft, select_prompt_contract
from .governance import evaluate_agent_task
from .mock_llm import MockLLM, MockLLMResponse
from .registry import (
    AGENT_REGISTRY,
    KNOWN_AGENTS,
    AgentRegistryEntry,
    get_agent,
    list_agents,
)
from .persistence_contracts import (
    ALLOWED_PERSISTENCE_ACTION,
    TARGET_ACTION,
    TARGET_TABLE,
    AgentRunPersistenceDecision,
    AgentRunPersistenceDraft,
    AgentRunPersistenceMappingResult,
    AgentRunPersistenceRequest,
    AgentRunPersistenceSubjectSnapshot,
)
from .persistence_governance import (
    AgentRunPersistenceGovernanceDecision,
    build_agent_run_persistence_decision,
    evaluate_agent_run_persistence_request,
    validate_agent_run_subject_scope,
    validate_agent_task_result_for_persistence,
)
from .agent_run_mapper import (
    build_agent_run_persistence_draft,
    build_controlled_write_request,
    build_controlled_write_subject,
    prepare_agent_run_persistence,
)

__all__ = [
    # Phase 13 — execution harness
    "AgentTaskRequest",
    "AgentTaskResult",
    "AgentContextRequest",
    "AgentContextBundle",
    "AgentRunDraft",
    "PromptContractReference",
    "AgentExecutionDecision",
    "AGENT_REGISTRY",
    "KNOWN_AGENTS",
    "AgentRegistryEntry",
    "get_agent",
    "list_agents",
    "evaluate_agent_task",
    "MockAgentExecutor",
    "select_prompt_contract",
    "build_run_draft",
    "MockLLM",
    "MockLLMResponse",
    # Phase 19 — agent run persistence mapping
    "ALLOWED_PERSISTENCE_ACTION",
    "TARGET_TABLE",
    "TARGET_ACTION",
    "AgentRunPersistenceSubjectSnapshot",
    "AgentRunPersistenceRequest",
    "AgentRunPersistenceDraft",
    "AgentRunPersistenceDecision",
    "AgentRunPersistenceMappingResult",
    "AgentRunPersistenceGovernanceDecision",
    "evaluate_agent_run_persistence_request",
    "validate_agent_run_subject_scope",
    "validate_agent_task_result_for_persistence",
    "build_agent_run_persistence_decision",
    "build_agent_run_persistence_draft",
    "build_controlled_write_subject",
    "build_controlled_write_request",
    "prepare_agent_run_persistence",
]
