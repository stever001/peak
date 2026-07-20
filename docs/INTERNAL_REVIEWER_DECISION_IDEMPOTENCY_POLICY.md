# Internal Reviewer Decision Idempotency Policy (Phase 33)

DB-enforced idempotency for the Phase 33 controlled internal-reviewer-decision writer
([`INTERNAL_REVIEWER_DECISION_CONTROLLED_WRITER.md`](INTERNAL_REVIEWER_DECISION_CONTROLLED_WRITER.md)),
mirroring the Phase 20–24, 27, and 30 writers.

## Uniqueness boundary

A UNIQUE index `uq_internal_reviewer_decision_records_idem` over
`(owner_id, client_id, engagement_id, idempotency_key)`. The identity context is part of the key
so an `idempotency_key` cannot collide across owner / client / engagement.

## Payload fingerprint

`payload_fingerprint` is a deterministic SHA-256 over a canonical, sorted JSON of the write
payload + identity — **safe references/metadata only, no raw content and no review approval /
decision**. It includes: `owner_id`, `client_id`, `engagement_id`, `review_bundle_ref`,
`review_bundle_record_id`, `review_bundle_draft_ref`, `review_plan_item_refs`,
`evidence_reference_ids`, `source_ingestion_record_ids`, `agent_task_queue_record_ids`,
`reviewer_role`, `decision_intent`, `decision_reason_code`, `safe_decision_summary`,
`return_to_stage`, `requested_followup_actions`, `route_to`, `routing_reason_code`,
`authorization_scope`, `output_status`, `review_status`, `lifecycle_status`, `authoritative`,
`client_facing_approved`, `capsule_candidate_ready`, `financial_verified`, `execution_allowed`,
`approval_allowed`, `publication_allowed`, `requires_human_review`, `client_facing_output_created`,
and `review_approval_made`.

## Replay vs. conflict

- **Same identity boundary + same `idempotency_key` + same fingerprint → `idempotent_replay`.**
  The existing row id is returned; **no mutation** occurs; `database_write_made` and
  `stored_record_created` are false and `existing_record_returned` is true.
- **Same identity boundary + same `idempotency_key` + different fingerprint →
  `idempotency_conflict`** (a `denied` outcome). No row is created or modified; the existing row is
  unchanged.

## Race handling

The common path does an idempotency pre-check. Under a concurrent race the pre-check may miss and
the `INSERT` then violates the unique index, raising `IntegrityError`. The writer rolls back and
**re-queries inline** on the same boundary: a matching fingerprint resolves to `idempotent_replay`;
a differing fingerprint resolves to `idempotency_conflict`; and the pathological "integrity error
but no matching row" case resolves to `write_outcome_uncertain` (never a false "no record" claim).

## Non-approval invariant

Idempotency governs **persistence** only. A replay never approves anything, never calls
`approve_internal`, never calls the Phase 22 review writer, never creates a `review_records` row,
and never executes an agent or calls an LLM/AgentNet/resolver/network. Replays and conflicts alike
leave the stored, review-gated, non-approval posture untouched. `ready_for_internal_use` remains
**not** approval on every replay.
