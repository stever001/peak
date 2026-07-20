# Packet → Task Queue Orchestration Integration (Phase 28)

**Phase 28 integrates the queue path into orchestration.** It wires the Phase 26 task queue /
execution readiness boundary and the Phase 27 narrow DB writer into the existing Phase 25
controlled packet processing orchestrator. It is an **orchestration integration phase, not a new
writer phase**: no new table, no migration, no new writer, and no generic dispatcher.

## What changed

The Phase 25 orchestrator already derived Phase 13 `AgentTaskRequest` objects from a packet (its
`agent_task_planning` stage). Phase 28 adds two stages that consume those same derived objects:

1. **`agent_task_queue_readiness`** (DB-free, execution-free) — runs Phase 26
   `prepare_agent_task_queue_plan` over the derived tasks and exposes review-gated,
   **not-executed** queue drafts, readiness assessments, and plan-only Phase 17
   `ControlledWriteRequest` objects on the receipt.
2. **`agent_task_queue_persistence`** (only when explicitly requested) — persists those write
   requests through the Phase 27 narrow writer `persist_agent_task_queue_record`, one review-gated
   `agent_task_queue_records` row each.

## Options and defaults

- `include_agent_task_queue_readiness` — default **true** (readiness is DB-free and execution-free).
- `include_agent_task_queue_persistence` — default **false**.

All existing defaults are unchanged and remain safe: `plan_only=true`, source-ingestion
persistence off, evidence persistence off, agent task planning on, agent-run planning/persistence
off, task queue persistence off.

## Plan-only behavior (default, no side effects)

In default plan-only mode the orchestrator: calls Phase 23 `prepare_packet_ingestion`; derives
Phase 13 `AgentTaskRequest` objects; calls Phase 26 `prepare_agent_task_queue_plan`; and exposes
`task_queue_drafts`, `task_queue_readiness_assessments`, `task_queue_controlled_write_requests`,
`task_queue_draft_count`, `task_queue_blocked_count`, and
`task_queue_controlled_write_request_count`. **Plan-only queue readiness is allowed because it is
DB-free and execution-free.** Every side-effect flag stays `false`:
`database_connection_made`, `sql_execution_made`, `database_write_made`, `stored_record_created`,
`agent_execution_made`, `mock_agent_execution_made`, `llm_call_made`, `agentnet_call_made`,
`resolver_call_made`, `network_call_made`, `client_facing_output_created`,
`financial_verification_made`, `capsule_publication_made`.

## Controlled persistence behavior

The Phase 27 writer is called **only** when all of the following hold: `plan_only=false`,
`include_agent_task_queue_persistence=true`, a `session_factory` is supplied, and Phase 26
produced valid controlled write requests. The orchestrator then calls **only**
`persist_agent_task_queue_record` (never a dynamically-dispatched arbitrary writer), attaches each
Phase 27 receipt to `task_queue_write_receipts`, aggregates DB side-effect flags **only** from
actual writer calls, and supports idempotent replay / conflict via the writer. Partial success
(some rows created, some denied/failed) is reported deterministically as a `partial` stage
outcome.

### No-escalation rules

- `include_agent_task_queue_persistence=false` → **no** Phase 27 call even if a `session_factory`
  is supplied (`skipped_not_requested`).
- `include_agent_task_queue_persistence=true` **and** `plan_only=true` → `skipped_plan_only`.
- `include_agent_task_queue_persistence=true`, `plan_only=false`, but **no** `session_factory` →
  `skipped_missing_session_factory`.
- Phase 26 produced no valid controlled write requests → `skipped_no_safe_contract_path`.

**No persistence option may silently escalate plan-only mode.**

## Authorization model

The orchestrator may **preflight** request identity, packet-reference identity/scope, derived task
identity/scope, and queue-draft identity/scope. But **orchestrator preflight is not authoritative**
for writes: **stored Engagement authorization remains authoritative for every DB write** and is
enforced inside the Phase 27 writer, which re-loads the stored `Engagement` row at write-time and
requires `request.authorization_scope == engagement.authorization_scope`. **Identity matching is
necessary but not sufficient** — a stored-scope mismatch is denied by the writer even when every
identity matches, and the orchestrator surfaces that denial (a `partial` outcome; no row written).

## No execution

Packet processing still **never** executes an agent, calls the Phase 13 executor, instantiates or
calls `MockAgentExecutor` / `MockLLM`, calls a live LLM, AgentNet, MCP, a resolver, a connector,
or the network, and **never creates an `agent_run_records` row**. **Agent task queue persistence
is not execution** — it records that a task is queued for review, nothing more. No client-facing
output, financial verification, or capsule publication occurs.

## Packet / content safety

The receipt and queue integration outputs carry only counts, ids, safe references, safe summaries,
stage names, outcomes, reason codes, and warnings without raw values — **never** the full
`packet_payload`, raw evidence/interview text, raw source bytes, arbitrary client content,
credentials/secrets, LLM prompts with raw content, generated agent output, DB URLs, raw SQL, or
stack traces.

## Stage outcomes

`completed`, `skipped_not_requested`, `skipped_plan_only`, `skipped_missing_session_factory`,
`skipped_no_safe_contract_path`, `denied`, `failed_before_write`, `write_outcome_uncertain`, and
`partial`. The persistence stage is `completed` only when at least one Phase 27 writer receipt was
created or replayed and none failed; a mix is `partial`.

## Receipt fields

`task_queue_readiness_result`, `task_queue_drafts`, `task_queue_readiness_assessments`,
`task_queue_controlled_write_requests`, `task_queue_write_receipts`, `task_queue_draft_count`,
`task_queue_blocked_count`, `task_queue_controlled_write_request_count`,
`task_queue_persisted_count`, `task_queue_replay_count`, `task_queue_conflict_count`,
`task_queue_persistence_outcome`, and `task_queue_persistence_stage_outcome`.

## Boundaries

- **No new table, no migration** — Alembic head remains `006_agent_task_queue_records`; the
  controlled DB still has 12 tables.
- The Phase 23 ingestion package and the Phase 26 `peak/task_queue` package stay **DB-free**; the
  Phase 27 writer is imported **lazily** inside the persistence stage so plan-only mode runs
  without SQLAlchemy.
- The orchestrator imports no live LLM / MockLLM / executor / AgentNet / MCP / resolver /
  connector / network module.

## Downstream: Phase 29 review planning

The receipt this integration produces (packet-processing receipt ref, source-ingestion / evidence
/ agent-task-queue ids, task queue outputs) is safe-reference-only and can be handed to the
**Phase 29 Packet-Derived Review Orchestration Boundary**
([`PACKET_DERIVED_REVIEW_ORCHESTRATION_BOUNDARY.md`](PACKET_DERIVED_REVIEW_ORCHESTRATION_BOUNDARY.md))
to plan human review. Phase 29 is DB-free, approves nothing, and does not run inside this
integration — the handoff is by contract only. **Phase 31** completes that handoff inside the
orchestrator (the `review_orchestration` / `review_bundle_persistence` stages), consuming this
integration's task-queue outputs as safe references; see
[`PACKET_TO_REVIEW_BUNDLE_ORCHESTRATION_INTEGRATION.md`](PACKET_TO_REVIEW_BUNDLE_ORCHESTRATION_INTEGRATION.md).
