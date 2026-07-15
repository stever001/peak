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

See docs/AGENT_EXECUTION_HARNESS.md and docs/AGENT_RUN_RECORDS.md.
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

__all__ = [
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
]
