# Packet → Review Bundle Orchestration Integration (Phase 31)

**Phase 31 integrates the review bundle path into packet orchestration.** It wires the Phase 29
review orchestration boundary and the Phase 30 narrow DB writer into the existing Phase 25/28
controlled packet processing orchestrator. It is an **orchestration integration phase, not a new
writer phase and not an approval phase**: no new table, no migration, no new writer, no generic
dispatcher.

## What changed

After processing a packet through the existing Phase 23/24/14/18/21/13/26/27 path, the
orchestrator gathers **safe references** from that work and adds two stages:

1. **`review_orchestration`** (DB-free, approval-free) — runs Phase 29 `prepare_packet_review_plan`
   over the safe references and exposes review-gated, **not-approved** review bundle drafts, review
   plan items, and readiness assessments on the receipt.
2. **`review_bundle_persistence`** (only when explicitly requested) — builds a Phase 17 controlled
   write request per draft and persists it through the Phase 30 narrow writer
   `persist_review_bundle_record`, one review-gated `review_bundle_records` row each.

## Safe references gathered

Only ids / receipt-ids / safe draft refs are gathered — **never** raw content: persisted
`source_ingestion_records` id (when source persistence ran), persisted `evidence_references` ids
(when evidence persistence ran), persisted `agent_task_queue_records` ids (when queue persistence
ran) **or** safe per-task queue-draft references otherwise, and a deterministic packet-processing
receipt ref (`pktproc::<idempotency_key>`) so there is always at least one review subject.

## Options and defaults

- `include_review_orchestration` — default **true** (Phase 29 is DB-free and approval-free).
- `include_review_bundle_persistence` — default **false**.

All existing defaults are unchanged and remain safe: `plan_only=true`, source/evidence/task-queue
persistence off, agent task planning + queue readiness on, agent-run planning/persistence off,
review bundle persistence off.

## Plan-only behavior (default, no side effects)

In default plan-only mode the orchestrator processes the packet, runs Phase 29 review
orchestration over safe refs, and exposes `review_orchestration_result`, `review_bundle_drafts`,
`review_plan_items`, `review_readiness_assessments`, and the `review_*_count` fields. Every
side-effect flag stays `false`: `direct_database_write_made`/`database_connection_made`/
`sql_execution_made`/`database_write_made`/`stored_record_created`, `review_approval_made`,
`client_facing_output_created`, `financial_verification_made`, `capsule_publication_made`,
`agent_execution_made`, `mock_agent_execution_made`, `llm_call_made`, `agentnet_call_made`,
`resolver_call_made`, `network_call_made`. **Plan-only review orchestration is allowed because
Phase 29 is DB-free and approval-free.**

## Controlled review bundle persistence

The Phase 30 writer is called **only** when all hold: `plan_only=false`,
`include_review_bundle_persistence=true`, a `session_factory` is supplied, and Phase 29 produced
review bundle drafts. The orchestrator then calls **only** `persist_review_bundle_record` (never a
dynamically-dispatched writer, **never Phase 22**, never creating a `review_records` row), attaches
each Phase 30 receipt to `review_bundle_write_receipts`, aggregates DB flags **only** from actual
writer calls, and supports idempotent replay / conflict via the writer. Partial success is reported
deterministically as a `partial` stage outcome.

### No-escalation rules

- `include_review_bundle_persistence=false` → **no** Phase 30 call even with a `session_factory`
  (`skipped_not_requested`).
- `include_review_bundle_persistence=true` **and** `plan_only=true` → `skipped_plan_only`.
- `include_review_bundle_persistence=true`, `plan_only=false`, but **no** `session_factory` →
  `skipped_missing_session_factory`.
- No review bundle drafts produced → `skipped_no_safe_contract_path`.

**No persistence option may silently escalate plan-only mode.**

## Authorization model

The orchestrator may **preflight** packet request identity, packet-reference identity/scope,
derived source/evidence/task-queue identity/scope, and review bundle draft identity/scope. But
**orchestrator preflight is not authoritative** for writes: **stored Engagement authorization
remains authoritative for every DB write** and is enforced inside the Phase 30 writer, which
re-loads the stored `Engagement` row at write-time and requires `request.authorization_scope ==
engagement.authorization_scope`. **Identity matching is necessary but not sufficient** — a
stored-scope mismatch is denied by the writer even when every identity matches, and the
orchestrator surfaces that denial (a `partial` outcome; no row written).

## No approval

**Review bundle persistence is not review approval.** Packet processing never approves a review,
never calls `approve_internal`, never calls the Phase 22 review writer, never creates a
`review_records` row, and never sets `review_approval_made` / `client_facing_output_created` /
`financial_verification_made` / `capsule_publication_made` true. **`ready_for_human_review` is not
approved** — it means a human reviewer may now act.

## No execution

Packet processing still never executes an agent, calls the Phase 13 executor / MockAgentExecutor /
MockLLM / a live LLM / AgentNet / MCP / resolver / network, or creates an `agent_run_records` row.

## Packet / content safety

The receipt and review integration outputs carry only counts, ids, safe refs, safe summaries,
stage names, outcomes, reason codes, and warnings without raw values — **never** the full
`packet_payload`, raw evidence/interview text, raw source bytes, arbitrary client content,
credentials/secrets, generated agent output, DB URLs, raw SQL, stack traces, or approval decisions.

## Stage outcomes

`completed`, `skipped_not_requested`, `skipped_plan_only`, `skipped_missing_session_factory`,
`skipped_no_safe_contract_path`, `denied`, `failed_before_write`, `write_outcome_uncertain`, and
`partial`. The review bundle persistence stage is `completed` only when at least one Phase 30
writer receipt was created or replayed and none failed; a mix is `partial`.

## Receipt fields

`review_orchestration_result`, `review_bundle_drafts`, `review_plan_items`,
`review_readiness_assessments`, `review_bundle_write_receipts`, `review_bundle_count`,
`review_plan_item_count`, `review_readiness_assessment_count`, `review_subject_count`,
`review_blocked_subject_count`, `review_bundle_persisted_count`, `review_bundle_replay_count`,
`review_bundle_conflict_count`, `review_bundle_persistence_outcome`, and
`review_bundle_persistence_stage_outcome`; plus the `review_approval_made` flag (always false).

## Boundaries

- **No new table, no migration** — Alembic head remains `007_review_bundle_records`; the controlled
  DB still has 13 tables.
- The Phase 23 ingestion, Phase 26 task_queue, and Phase 29 review_orchestration packages stay
  **DB-free**; the Phase 30 writer is imported **lazily** inside the persistence stage so plan-only
  mode runs without SQLAlchemy.
- The orchestrator imports no live LLM / MockLLM / executor / AgentNet / MCP / resolver / connector
  / network module, and never calls the Phase 22 review writer.

## Downstream: Phase 32 reviewer decisions

The `review_bundle_records` ids (and review-plan-item refs) this integration produces are safe
references the **Phase 32 Internal Reviewer Decision Boundary**
([`INTERNAL_REVIEWER_DECISION_BOUNDARY.md`](INTERNAL_REVIEWER_DECISION_BOUNDARY.md)) consumes to
plan a structured reviewer decision. Phase 32 is DB-free, approves nothing, and does not run inside
this integration — the handoff is by contract only.
