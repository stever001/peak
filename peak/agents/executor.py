"""No-op / mock executor for the future Peak internal agent harness.

Orchestrates the *shape* of an agent run without executing anything: it runs governance
checks, looks up the registry entry, selects the (existing) prompt-contract reference,
optionally routes a resolver-context request through the **Phase 12 governed mock
boundary** (still no live call), consults the mock LLM (no call), and returns a controlled
``AgentTaskResult``.

Hard guarantees (Phase 13): **never** calls an LLM, AgentNet, an MCP connector, a
resolver, a database, or the network; **never** writes files; **never** creates
client-facing output. Output defaults to ``draft`` / ``needs_review``.
"""

from __future__ import annotations

import os

from .contracts import (
    AgentRunDraft,
    AgentTaskRequest,
    AgentTaskResult,
    PromptContractReference,
)
from .governance import evaluate_agent_task
from .registry import get_agent

# Repo root, used only to check that a referenced prompt-contract file exists (read-only;
# no file is written and no content is loaded).
_REPO_ROOT = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))


def select_prompt_contract(request: AgentTaskRequest, entry=None) -> PromptContractReference:
    """Resolve the prompt-contract reference for a request (no prompt text is loaded)."""
    if entry is None:
        entry = get_agent(getattr(request, "agent_name", None))
    path = getattr(request, "prompt_contract_path", None)
    if not path and entry is not None:
        path = entry.prompt_contract_path
    workflow = entry.workflow if entry is not None else getattr(request, "workflow", None)
    exists = bool(path) and os.path.isfile(os.path.join(_REPO_ROOT, path))
    return PromptContractReference(
        agent_name=getattr(request, "agent_name", None),
        workflow=workflow,
        prompt_contract_path=path,
        exists=exists,
    )


class MockAgentExecutor:
    """Inert executor: governs and plans an agent run, but executes nothing."""

    def execute(self, request: AgentTaskRequest) -> AgentTaskResult:
        decision = evaluate_agent_task(request)
        entry = get_agent(getattr(request, "agent_name", None))
        prompt_ref = select_prompt_contract(request, entry)
        warnings = list(decision.warnings)

        if not decision.permitted:
            return AgentTaskResult(
                permitted=False,
                status="rejected",
                output_status="draft",
                review_status="needs_review",
                lifecycle_status="draft",
                reasons=list(decision.reasons),
                warnings=warnings,
                prompt_contract_path=prompt_ref.prompt_contract_path,
                resolver_context_used=False,
                llm_call_made=False,
                agentnet_call_made=False,
                database_write_made=False,
                client_facing_output_created=False,
            )

        # Permitted — still a mock. Optionally route resolver context through the Phase 12
        # governed boundary. That boundary is itself a no-network mock: no live call.
        if getattr(request, "resolver_context_allowed", False) and entry is not None \
                and entry.resolver_context_future:
            self._route_resolver_context(request, warnings)

        # Consult the mock LLM — this makes no call and returns a disabled-execution note.
        from .mock_llm import MockLLM

        llm_response = MockLLM().complete()
        warnings.append(llm_response.message)

        return AgentTaskResult(
            permitted=True,
            status="planned_mock_no_execution",
            output_status="draft",
            review_status="needs_review",
            lifecycle_status="draft",
            reasons=[],
            warnings=warnings,
            prompt_contract_path=prompt_ref.prompt_contract_path,
            resolver_context_used=False,  # mock boundary returns no live context
            llm_call_made=False,
            agentnet_call_made=False,
            database_write_made=False,
            client_facing_output_created=False,
        )

    def _route_resolver_context(self, request: AgentTaskRequest, warnings: list) -> None:
        """Route a resolver-context request through the Phase 12 mock boundary.

        Uses peak.agentnet's governed **mock** boundary, which performs no network/MCP/
        resolver/AgentNet call. Any warnings it emits are surfaced; no context is loaded.
        """
        from peak.agentnet.contracts import ResolverContextRequest
        from peak.agentnet.mock_mcp import MockAgentNetMCPBoundary

        ctx_request = ResolverContextRequest(
            owner_id=getattr(request, "owner_id", None),
            client_id=getattr(request, "client_id", None),
            engagement_id=getattr(request, "engagement_id", None),
            authorization_scope=getattr(request, "authorization_scope", None),
            resolver_scope=getattr(request, "workflow", None),
            query=getattr(request, "requested_action", None),
        )
        response = MockAgentNetMCPBoundary().resolve(ctx_request)
        warnings.append(
            "resolver context routed through Phase 12 mock boundary (no live call)"
        )
        for warning in response.warnings:
            warnings.append(warning)


def build_run_draft(request: AgentTaskRequest, result: AgentTaskResult) -> AgentRunDraft:
    """Build an in-memory AgentRunDraft from a request/result. **Not stored.**

    Mirrors the future ``AgentRunRecord`` shape (docs/AGENT_RUN_RECORDS.md). Phase 13
    persists nothing: ``agent_run_id`` and timestamps are left unset for a future
    controlled-DB writer to assign.
    """
    return AgentRunDraft(
        agent_run_id=None,
        agent_name=getattr(request, "agent_name", None),
        workflow=getattr(request, "workflow", None),
        owner_id=getattr(request, "owner_id", None),
        client_id=getattr(request, "client_id", None),
        engagement_id=getattr(request, "engagement_id", None),
        input_record_ids=list(getattr(request, "input_record_ids", []) or []),
        prompt_contract_path=result.prompt_contract_path,
        resolver_context_requested=bool(getattr(request, "resolver_context_allowed", False)),
        resolver_context_used=result.resolver_context_used,
        llm_call_made=result.llm_call_made,
        agentnet_call_made=result.agentnet_call_made,
        database_write_made=result.database_write_made,
        output_record_ids=[],
        output_status=result.output_status,
        review_status=result.review_status,
        lifecycle_status=result.lifecycle_status,
        warnings=list(result.warnings),
        reasons=list(result.reasons),
        created_at=None,
        created_by=None,
    )
