"""Static registry of the known Peak internal agents/workers.

Maps each agent to its workflow, an **existing** prompt-contract file (or ``None`` where
no dedicated contract exists yet), governance defaults, and forward-looking flags. This
is a **catalog only** — it embeds no prompt text and invokes nothing. Prompt-contract
paths point at files already in ``prompts/`` (see docs/AGENT_WORKFLOWS.md).

Governance defaults follow the Phase 9 guardrails: every agent's output defaults to
``draft`` / ``needs_review``; agents never self-approve or create client-facing output.
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Optional

from .contracts import DEFAULT_OUTPUT_STATUS, DEFAULT_REVIEW_STATUS


@dataclass(frozen=True)
class AgentRegistryEntry:
    """One catalog entry describing a known Peak internal agent/worker."""

    agent_name: str
    workflow: str
    purpose: str
    prompt_contract_path: Optional[str] = None
    default_output_status: str = DEFAULT_OUTPUT_STATUS
    default_review_status: str = DEFAULT_REVIEW_STATUS
    # Whether this agent may request resolver grounding context in a *future* phase
    # (always through the Phase 12 governed boundary; never a live call in Phase 13).
    resolver_context_future: bool = False
    # Whether this agent's output could ever become client-facing — and then only after
    # an explicit human approval gate (never by the agent itself).
    client_facing_requires_human_approval: bool = False


# Order preserved for readability; lookups are by name.
_ENTRIES = (
    AgentRegistryEntry(
        agent_name="new_client_intake_agent",
        workflow="intake",
        purpose="Structure raw new-client intake into a ClientIntake draft.",
        prompt_contract_path="prompts/intake/normalize-client-intake.prompt.md",
        resolver_context_future=False,
    ),
    AgentRegistryEntry(
        agent_name="discovery_planning_agent",
        workflow="discovery",
        purpose="Turn intake into an assessment/discovery plan and initial system profile.",
        prompt_contract_path="prompts/discovery/generate-discovery-plan.prompt.md",
        resolver_context_future=True,
    ),
    AgentRegistryEntry(
        agent_name="interview_structuring_assistant",
        workflow="discovery",
        purpose="Structure stakeholder interview prep and notes into consistent form.",
        prompt_contract_path=None,
        resolver_context_future=False,
    ),
    AgentRegistryEntry(
        agent_name="walkaround_observation_worker",
        workflow="discovery",
        purpose="Structure on-site walk-around visual/workflow observations.",
        prompt_contract_path=None,
        resolver_context_future=False,
    ),
    AgentRegistryEntry(
        agent_name="evidence_normalization_worker",
        workflow="evidence",
        purpose="Normalize heterogeneous inputs into traceable evidence and candidate issues.",
        prompt_contract_path="prompts/evidence/extract-evidence-findings.prompt.md",
        resolver_context_future=True,
    ),
    AgentRegistryEntry(
        agent_name="initial_report_generation_agent",
        workflow="reporting",
        purpose="Draft an evidence-linked initial management report (internal draft).",
        prompt_contract_path="prompts/reporting/draft-initial-assessment-report.prompt.md",
        resolver_context_future=True,
        client_facing_requires_human_approval=True,
    ),
    AgentRegistryEntry(
        agent_name="quick_win_identification_agent",
        workflow="proposal",
        purpose="Identify low-effort, high-value quick wins from evidence (internal draft).",
        prompt_contract_path="prompts/reporting/draft-initial-assessment-report.prompt.md",
        resolver_context_future=True,
        client_facing_requires_human_approval=True,
    ),
    AgentRegistryEntry(
        agent_name="next_phase_proposal_agent",
        workflow="proposal",
        purpose="Draft recommendations and a next-phase proposal (internal draft).",
        prompt_contract_path="prompts/proposal/generate-next-phase-proposal.prompt.md",
        resolver_context_future=True,
        client_facing_requires_human_approval=True,
    ),
    AgentRegistryEntry(
        agent_name="internal_qa_governance_agent",
        workflow="qa",
        purpose="QA a packet/draft for evidence traceability, consistency, completeness.",
        prompt_contract_path="prompts/qa/review-assessment-packet.prompt.md",
        resolver_context_future=True,
    ),
    AgentRegistryEntry(
        agent_name="consultant_copilot",
        workflow="cross_cutting",
        purpose="Assist a consultant across workflows; internal-only drafting support.",
        prompt_contract_path=None,
        resolver_context_future=True,
    ),
)

# Public catalog keyed by agent_name.
AGENT_REGISTRY = {entry.agent_name: entry for entry in _ENTRIES}

# The exact set of known agents/workers (Phase 13).
KNOWN_AGENTS = tuple(entry.agent_name for entry in _ENTRIES)


def get_agent(agent_name) -> Optional[AgentRegistryEntry]:
    """Return the registry entry for ``agent_name``, or ``None`` if unknown."""
    if not agent_name:
        return None
    return AGENT_REGISTRY.get(agent_name)


def list_agents() -> list:
    """Return all registry entries in declaration order."""
    return list(_ENTRIES)
