# Agent Task Queue Idempotency Policy (Phase 27)

DB-enforced idempotency for the Phase 27 controlled agent-task-queue writer
([`AGENT_TASK_QUEUE_CONTROLLED_WRITER.md`](AGENT_TASK_QUEUE_CONTROLLED_WRITER.md)), mirroring the
Phase 20–24 writers.

## Uniqueness boundary

A UNIQUE index `uq_agent_task_queue_records_idem` over
`(owner_id, client_id, engagement_id, idempotency_key)`. The identity context is part of the key
so an `idempotency_key` cannot collide across owner / client / engagement. Phase 26 derives a
deterministic per-task key (`<request.idempotency_key>::taskq::<index>::<agent_name>`), so each
queue draft carries a distinct key on this boundary.

## Payload fingerprint

`payload_fingerprint` is a deterministic SHA-256 over a canonical, sorted JSON of the write
payload + identity — **safe references/metadata only, no raw content**. It includes:
`owner_id`, `client_id`, `engagement_id`, `agent_name`, `task_type`, `requested_action`,
`task_input_ref`, `safe_input_summary`, `source_ingestion_record_id`, `evidence_reference_ids`,
`packet_processing_run_ref`, `orchestration_ref`, `authorization_scope`, `readiness_state`,
`output_status`, `review_status`, `lifecycle_status`, `execution_status`, `authoritative`,
`client_facing_approved`, `capsule_candidate_ready`, `execution_allowed`,
`llm_execution_allowed`, `agentnet_context_allowed`, `resolver_context_allowed`,
`network_allowed`, and `requires_human_review`.

## Replay vs. conflict

- **Same identity boundary + same `idempotency_key` + same fingerprint → `idempotent_replay`.**
  The existing row id is returned; **no mutation** occurs; `database_write_made` and
  `stored_record_created` are false and `existing_record_returned` is true.
- **Same identity boundary + same `idempotency_key` + different fingerprint →
  `idempotency_conflict`** (a `denied` outcome). No row is created or modified; the existing row
  is unchanged.

## Race handling

The common path does an idempotency pre-check. Under a concurrent race the pre-check may miss
and the `INSERT` then violates the unique index, raising `IntegrityError`. The writer rolls back
and **re-queries inline** on the same boundary: a matching fingerprint resolves to
`idempotent_replay`; a differing fingerprint resolves to `idempotency_conflict`; and the
pathological "integrity error but no matching row" case resolves to `write_outcome_uncertain`
(never a false "no record" claim).

## Non-execution invariant

Idempotency governs **persistence** only. A replay never executes an agent, never calls an
LLM/AgentNet/resolver/network, and never creates an `agent_run_records` row. Replays and
conflicts alike leave the stored, review-gated, not-executed posture untouched.
