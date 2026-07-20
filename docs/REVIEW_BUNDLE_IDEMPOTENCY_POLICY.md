# Review Bundle Idempotency Policy (Phase 30)

DB-enforced idempotency for the Phase 30 controlled review-bundle writer
([`REVIEW_BUNDLE_CONTROLLED_WRITER.md`](REVIEW_BUNDLE_CONTROLLED_WRITER.md)), mirroring the Phase
20–24 and 27 writers.

## Uniqueness boundary

A UNIQUE index `uq_review_bundle_records_idem` over
`(owner_id, client_id, engagement_id, idempotency_key)`. The identity context is part of the key
so an `idempotency_key` cannot collide across owner / client / engagement.

## Payload fingerprint

`payload_fingerprint` is a deterministic SHA-256 over a canonical, sorted JSON of the write
payload + identity — **safe references/metadata only, no raw content and no review decision**. It
includes: `owner_id`, `client_id`, `engagement_id`, `packet_processing_receipt_ref`,
`source_ingestion_record_ids`, `evidence_reference_ids`, `agent_task_queue_record_ids`,
`subject_refs` (id + type), `reviewer_role`, `review_reason`, `review_scope`, `output_status`,
`review_status`, `lifecycle_status`, `authoritative`, `client_facing_approved`,
`capsule_candidate_ready`, `financial_verified`, `execution_allowed`, `approval_allowed`,
`publication_allowed`, and `requires_human_review`.

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

Idempotency governs **persistence** only. A replay never approves anything, never calls the Phase
22 review writer, never creates a `review_records` row, and never executes an agent or calls an
LLM/AgentNet/resolver/network. Replays and conflicts alike leave the stored, review-gated,
not-approved posture untouched.

When the **Phase 31** orchestrator integration drives persistence, it builds one review bundle CWR
per Phase 29 draft (keyed `<packet_idempotency_key>::review::bundle::<i>`) and surfaces this
writer's replay/conflict outcomes on the packet receipt (`review_bundle_replay_count`,
`review_bundle_conflict_count`); a conflict makes the orchestration outcome `partial` and writes no
extra row.

The persisted `review_bundle_records` id is a safe reference the **Phase 32 Internal Reviewer
Decision Boundary** consumes to plan a reviewer decision; Phase 32 is DB-free, has its own
idempotency-key contract for a *future* Phase 33 writer, and persists nothing itself.
