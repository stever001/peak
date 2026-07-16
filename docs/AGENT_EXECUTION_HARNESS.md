# Agent Execution Harness (Phase 13)

A **scaffold** for how future Peak internal agents/workers will be **invoked, governed,
and recorded**. **No live execution yet:** nothing here calls an LLM, AgentNet, an MCP
connector, a resolver, a database, an API, or the network, and nothing produces
client-facing output. **AgentNet integration is not complete.**

## Purpose

Peak's consulting workflows (intake, discovery, evidence normalization, reporting,
proposal, QA, and a cross-cutting consultant copilot) will eventually be operated by
governed internal agents. Before any runtime exists, this phase fixes the **contracts and
control flow**: what an agent task looks like, which governance checks gate it, how a
prompt contract is selected, and what an agent run would record — so the governance and
audit posture is defined *before* execution is built.

## No live execution

The only runnable path is a **mock**:

- [`../peak/agents/executor.py`](../peak/agents/executor.py) — `MockAgentExecutor` runs
  governance, selects a prompt-contract reference, optionally routes resolver context
  through the Phase 12 mock boundary, consults the mock LLM, and returns an
  `AgentTaskResult`. It executes nothing.
- [`../peak/agents/mock_llm.py`](../peak/agents/mock_llm.py) — `MockLLM` makes no model
  call and reports live LLM execution is disabled.

Every result carries `llm_call_made = False`, `agentnet_call_made = False`,
`database_write_made = False`, and `client_facing_output_created = False`.

## Loading authorized engagement context (future)

A future agent would load only **authorized** engagement context — records for the
`owner_id` / `client_id` / `engagement_id` it is permitted to see — from Peak's controlled
engagement storage (see [`CONTROLLED_DATA_ARCHITECTURE.md`](CONTROLLED_DATA_ARCHITECTURE.md)
and [`DATABASE_ACCESS_AND_AUDIT.md`](DATABASE_ACCESS_AND_AUDIT.md)). In Phase 13 the
`AgentContextBundle` is **never loaded** (`loaded = False`): no store or database is read.

## Selecting prompt contracts

Agents do not embed prompt text. Each registry entry
([`../peak/agents/registry.py`](../peak/agents/registry.py)) points at an **existing**
prompt-contract file under [`../prompts/`](../prompts/) (or `None` where no dedicated
contract exists yet). `select_prompt_contract()` resolves the reference and reports
whether the file exists — it never loads or runs the contract. See
[`AGENT_WORKFLOWS.md`](AGENT_WORKFLOWS.md) for the workflow↔contract map.

## How the Phase 12 resolver boundary fits in

When a task sets `resolver_context_allowed` and the agent is eligible
(`resolver_context_future`), the executor routes a resolver-context request through the
**Phase 12 governed mock boundary**
([`AGENTNET_MCP_BOUNDARY.md`](AGENTNET_MCP_BOUNDARY.md)). That boundary is itself a
no-network mock — it makes **no live resolver/AgentNet/MCP call** — so `resolver_context_used`
stays `False` and no context is actually loaded.

## Outputs default to draft / needs_review

Governance ([`../peak/agents/governance.py`](../peak/agents/governance.py)) forces agent
output to `output_status = draft` and `review_status = needs_review`. A task is rejected
when: `agent_name` is unknown; `owner_id` is missing; no `client_id`/`engagement_id` is
present; `lifecycle_status` is `revoked`/`archived`/`deleted_reference_only`;
`review_status` is `rejected`; `client_facing_output_requested` is true; or
`llm_execution_allowed` is true.

## Why human review gates matter

The harness encodes the Phase 9 guardrails ([`GOVERNANCE_STATES.md`](GOVERNANCE_STATES.md),
[`STATE_TRANSITIONS.md`](STATE_TRANSITIONS.md)): agents **draft**, humans **decide**. An
agent may **never** self-advance to `approved_internal` or `client_facing_approved`,
**never** create client-facing output, **never** publish capsules, and **never** verify
financial impact. These gates keep every client-bound artifact under consultant/QA review.

## Relationship to the known agents/workers

The registry catalogs the 10 known agents/workers — `new_client_intake_agent`,
`discovery_planning_agent`, `interview_structuring_assistant`,
`walkaround_observation_worker`, `evidence_normalization_worker`,
`initial_report_generation_agent`, `quick_win_identification_agent`,
`next_phase_proposal_agent`, `internal_qa_governance_agent`, and `consultant_copilot` —
each mapped to a workflow, a prompt contract (where one exists), governance defaults, and
forward-looking flags. They are described here as **future** capabilities; none executes.

The `evidence_normalization_worker` is the first to get a concrete, production-shaped
implementation in [`../peak/workers/`](../peak/workers/) (Phase 14) — deterministic and
review-gated, still with no live call and no stored data. See
[`EVIDENCE_NORMALIZATION_WORKER.md`](EVIDENCE_NORMALIZATION_WORKER.md).

The `internal_qa_governance_agent` counterpart is the **QA / Review Gate**
([`../peak/review/`](../peak/review/), Phase 15): a production-shaped but no-side-effect
scaffold that evaluates worker/agent outputs (like the Phase 14 drafts) for internal
approval, rejection, return for revision, supersession, or continued review — storing
nothing and never creating client-facing approval. See
[`QA_REVIEW_GATE.md`](QA_REVIEW_GATE.md) and [`REVIEW_DECISION_MODEL.md`](REVIEW_DECISION_MODEL.md).

## No client-facing output from the harness

The harness produces **no client-facing output**. Any artifact an agent drafts is internal
and defaults to `draft`/`needs_review`; becoming client-facing requires an explicit human
approval gate outside this harness. Nothing is stored, published, or sent.

## Persistence is planned, never executed here (Phase 19)

The harness never writes to the database. When an agent run output (`AgentTaskResult` +
`AgentRunDraft`) is destined for controlled storage, the **Phase 19 Agent Run Persistence
Mapping** ([`AGENT_RUN_PERSISTENCE_MAPPING.md`](AGENT_RUN_PERSISTENCE_MAPPING.md),
[`../peak/agents/`](../peak/agents/)) maps it into a production-shaped but review-gated
`AgentRunPersistenceDraft` and routes it through the Phase 17 controlled writer boundary as a
no-op plan targeting `agent_run_records` / `create_agent_run_record` — **DB-aware but not
DB-writing**. **Agent execution still does not write directly to the DB**; a future
controlled DB writer executes the plan after the allowlist, `idempotency_key`, and
stored-scope checks pass.

That writer now exists as the **Phase 20 Agent Run Controlled Writer**
([`AGENT_RUN_CONTROLLED_WRITER.md`](AGENT_RUN_CONTROLLED_WRITER.md),
[`../peak/db/agent_run_writer.py`](../peak/db/agent_run_writer.py)) — the first real
DB-backed persistence path. It still is not the harness: the harness governs and drafts, the
Phase 19 mapper plans, and the Phase 20 writer (in the DB layer) creates one review-gated
`agent_run_records` row after re-loading the authoritative stored `Engagement` scope and
enforcing DB-level idempotency.
