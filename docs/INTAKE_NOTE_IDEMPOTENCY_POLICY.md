# Intake Note Idempotency Policy (Phase 34)

DB-enforced idempotency for the Phase 34 controlled intake-note writer
([`INTAKE_NOTE_CONTROLLED_WRITER.md`](INTAKE_NOTE_CONTROLLED_WRITER.md)), mirroring the Phase 20–24,
27, 30, and 33 writers.

## Uniqueness boundary

A UNIQUE index `uq_intake_note_records_idem` over
`(owner_id, client_id, engagement_id, idempotency_key)`. The identity context is part of the key so
an `idempotency_key` cannot collide across owner / client / engagement.

## Payload fingerprint

`payload_fingerprint` is a deterministic SHA-256 over a canonical, sorted JSON of the write payload
+ identity. Because `note_text` may be large and must never be duplicated or leaked, **the note body
participates only as a hash** (`note_text_sha256`), never as a re-stored copy. The fingerprint
includes: `owner_id`, `client_id`, `engagement_id`, `authorization_scope`, `note_type`,
`note_source`, `note_text_sha256`, `note_summary`, `captured_by`, `captured_role`, `source_ref`,
`source_ingestion_record_id`, `related_evidence_reference_id`, `related_review_bundle_record_id`,
`review_status`, `lifecycle_status`, and the posture booleans (`client_facing_approved`,
`financial_verified`, `capsule_candidate_ready`, `publication_allowed`, `execution_allowed`,
`requires_human_review`).

## Replay vs. conflict

- **Same identity boundary + same `idempotency_key` + same fingerprint → `idempotent_replay`.**
  The existing row id is returned; **no mutation** occurs; `database_write_made` and
  `stored_record_created` are false and `existing_record_returned` is true.
- **Same identity boundary + same `idempotency_key` + different fingerprint →
  `idempotency_conflict`** (a `denied` outcome). No row is created or modified; the existing row is
  unchanged. Because the note body is hashed into the fingerprint, an edited note under the same key
  is correctly detected as a conflict, not silently replayed.

## Race handling

The common path does an idempotency pre-check. Under a concurrent race the pre-check may miss and
the `INSERT` then violates the unique index, raising `IntegrityError`. The writer rolls back and
**re-queries inline** on the same boundary: a matching fingerprint resolves to `idempotent_replay`;
a differing fingerprint resolves to `idempotency_conflict`; and the pathological "integrity error
but no matching row" case resolves to `write_outcome_uncertain` (never a false "no record" claim).

## Non-final invariant

Idempotency governs **persistence** only. A replay never approves anything, never publishes, never
executes, never calls the Phase 22 review writer, and never creates a `review_records` /
`agent_run_records` row. Replays and conflicts alike leave the stored, review-gated, non-final
posture untouched, and no `note_text` is ever echoed in a receipt.
