"""Deterministic pre-execution governance checks for the agent harness.

Run *before* any (future) agent execution. Phase 13 performs no live execution: these
functions only decide whether a task *would be* permitted and why, and they hard-enforce
the Phase 9 guardrails — agent output defaults to ``draft`` / ``needs_review``, and agents
never self-approve, create client-facing output, publish capsules, or verify financial
impact.

Governance vocabulary mirrors the Phase 9 contracts (peak/db/enums.py and
schemas/*.schema.json are the source of truth); the blocking sets below are local
literals so this module stays import-light and does not touch the DB layer.
"""

from __future__ import annotations

from .contracts import AgentExecutionDecision, AgentTaskRequest
from .registry import get_agent

# Lifecycle statuses that block any agent execution.
BLOCKED_LIFECYCLE_STATUSES = frozenset({"revoked", "archived", "deleted_reference_only"})

# Review statuses that block execution.
BLOCKED_REVIEW_STATUSES = frozenset({"rejected"})

# Standing reminders emitted on every decision (documenting the hard limits).
STANDING_WARNINGS = (
    "agent output defaults to draft/needs_review; agents cannot self-approve "
    "(approved_internal or client_facing_approved)",
    "agent execution cannot publish capsules or verify financial impact",
)


def _is_blank(value) -> bool:
    return value is None or (isinstance(value, str) and not value.strip())


def evaluate_agent_task(request: AgentTaskRequest) -> AgentExecutionDecision:
    """Return a governance decision for an agent task request (no execution)."""
    reasons: list = []
    warnings: list = list(STANDING_WARNINGS)

    agent_name = getattr(request, "agent_name", None)

    # 1. agent_name must exist in the registry.
    entry = get_agent(agent_name)
    if entry is None:
        reasons.append(f"agent_name '{agent_name}' is not a known Peak agent/worker")

    # 2. owner_id is always required.
    if _is_blank(getattr(request, "owner_id", None)):
        reasons.append("owner_id is required")

    # 3. A live engagement workflow needs a client_id or engagement_id.
    has_live_ref = not _is_blank(getattr(request, "client_id", None)) or not _is_blank(
        getattr(request, "engagement_id", None)
    )
    if not has_live_ref:
        reasons.append("client_id or engagement_id is required for engagement workflows")

    # 4. lifecycle_status must not be revoked/archived/deleted.
    lifecycle = getattr(request, "lifecycle_status", None)
    if lifecycle in BLOCKED_LIFECYCLE_STATUSES:
        reasons.append(
            f"lifecycle_status '{lifecycle}' is not permitted "
            "(must not be revoked, archived, or deleted_reference_only)"
        )

    # 5. review_status must not be rejected.
    review = getattr(request, "review_status", None)
    if review in BLOCKED_REVIEW_STATUSES:
        reasons.append(f"review_status '{review}' is rejected; execution not permitted")

    # 6. No client-facing output in Phase 13 (agents can never create it).
    if getattr(request, "client_facing_output_requested", False):
        reasons.append(
            "client_facing_output_requested is not allowed: agents cannot create "
            "client-facing output (human approval gate required)"
        )

    # 7. No live LLM execution in Phase 13.
    if getattr(request, "llm_execution_allowed", False):
        reasons.append(
            "llm_execution_allowed must be false in Phase 13 (mock execution only; "
            "no live LLM call)"
        )

    # 8. Resolver context is permitted only via the Phase 12 governed mock boundary.
    if getattr(request, "resolver_context_allowed", False):
        warnings.append(
            "resolver context will be routed only through the Phase 12 governed mock "
            "boundary; no live resolver/AgentNet call is made"
        )

    return AgentExecutionDecision(
        agent_name=agent_name,
        permitted=not reasons,
        reasons=reasons,
        warnings=warnings,
        output_status="draft",
        review_status="needs_review",
        llm_call_made=False,
        agentnet_call_made=False,
        database_write_made=False,
        client_facing_output_created=False,
    )
