# Intake Note Controlled Writer (Phase 34)

The **eighth** narrow live DB writer in Peak (after the Phase 20 `agent_run_records`, Phase 21
`evidence_references`, Phase 22 `review_records`, Phase 24 `source_ingestion_records`, Phase 27
`agent_task_queue_records`, Phase 30 `review_bundle_records`, and Phase 33
`internal_reviewer_decision_records` writers). It persists **exactly one** `intake_note_records` row
from an `IntakeNoteDraft` routed through the Phase 17 `ControlledWriteRequest` boundary — allowing
only `intake_note_records` / `create_intake_note_record`. It is a narrow internal persistence
boundary, not a generic decision engine, workflow engine, CRUD repository, or arbitrary SQL executor.

Public entry point:

```
persist_intake_note_record(controlled_write_request, *, session_factory=None) -> IntakeNoteWriteReceipt
```

A DB-layer planner helper `build_intake_note_controlled_write_request(draft, *, requested_by,
requester_role, idempotency_key, ...)` wraps an `IntakeNoteDraft` in the Phase 17 request for this
exact table/action; it opens no database connection and persists nothing.

## First-class operational notes (note_text is stored — in the managed DB only)

Intake notes are **first-class operational records**: client interviews, consultant observations,
warehouse walkaround notes, discovery calls, document/source intake comments, controlled
packet-ingestion outputs, and consultant-authored notes. Unlike prior summary-only records, this
table intentionally stores authorized operational prose in **`note_text`**.

- **Acceptable:** real authorized intake note text stored in the **managed DB**.
- **Not acceptable:** real intake note text in Git, fixtures, examples, sample packets, logs,
  receipts, or test data. Tests use only synthetic, marker-free note text.
- **Receipts and denial reasons never echo `note_text` / note body** — only field names and marker
  *categories* are ever reported.

## Non-approval / non-publication / non-execution

This writer approves nothing, **never calls `approve_internal`**, never calls the **Phase 22 review
writer**, and **never creates a `review_records` row**. It never executes an agent (live or mock),
never calls the Phase 13 executor / MockLLM / a live LLM / **AgentNet (including any AgentNet
publication)** / MCP / resolver / connector / network, never creates an `agent_run_records` row, and
produces no client-facing output, financial verification, or capsule publication. Every stored row
is **review-gated and non-final**: `review_status=needs_review`, `lifecycle_status=draft`,
`client_facing_approved=false`, `financial_verified=false`, `capsule_candidate_ready=false`,
`publication_allowed=false`, `execution_allowed=false`, `requires_human_review=true`.

## Write-time authorization (stored Engagement is authoritative)

The writer does **not** trust caller-supplied scope. At **write-time** it loads the authoritative
stored `Engagement` row and requires, in order:

1. the `Engagement` row exists (subject `subject_record_type="engagement"`, id present);
2. `engagement.authorization_scope` is present;
3. `request.authorization_scope == engagement.authorization_scope`;
4. `engagement.owner_id == request.owner_id`, `engagement.client_id == request.client_id`,
   `engagement.id == request.engagement_id`;
5. `engagement.lifecycle_status` is not `revoked` / `archived` / `deleted_reference_only`.

**Identity matching is necessary but not sufficient** — a stored-scope mismatch is denied even when
every identity matches. Missing stored scope and missing request scope are denied.

## Content safety — bounded prose, non-echoing

`note_text` is a managed-DB storage field, not a short label, so **ordinary operational prose
passes**. It is rejected (without echoing the value — only the marker *category* is reported) when it
carries:

- a **credential/secret assignment** (e.g. `api_key=…`, `password: …`, an `AKIA…` key, a bearer
  token) — note that bare secret *words* in prose are allowed; only assignment/key shapes are
  rejected;
- a **DB URL/DSN** (`postgres://`, `mysql://`, `database_url`, …);
- **raw SQL** (`SELECT * FROM`, `INSERT INTO`, `DROP TABLE`, `UPDATE … SET`, …);
- a **private key** block (`-----BEGIN … PRIVATE KEY-----`);
- a **stack trace**;
- **raw-content field tokens** (`source_bytes`, `generated_output`, `packet_payload`, `base64,`);
- a **raw JSON dump** (the whole note parses as a JSON object/array, or contains ≥ 3 `"key":` pairs).

Bounds (documented and enforced): `note_text` ≤ **16,000** chars; `note_summary` ≤ **500** chars,
single line; `note_type` / `note_source` / `captured_role` ≤ 64 chars; `captured_by` / `source_ref`
/ related ids ≤ 128 chars. Short label/ref fields and `note_summary` are held to the stricter public
value-marker classifier (`classify_prohibited_value_marker`) so any marker in those short fields is
rejected. `note_text` is never echoed in receipts, warnings, or denial reasons; a hash
(`note_text_sha256`) is used for the fingerprint so the body is not duplicated.

## Idempotency

See [`INTAKE_NOTE_IDEMPOTENCY_POLICY.md`](INTAKE_NOTE_IDEMPOTENCY_POLICY.md). The DB-enforced
uniqueness boundary is `(owner_id, client_id, engagement_id, idempotency_key)`, with a deterministic
`payload_fingerprint` (the note body participates as a SHA-256 hash) distinguishing an exact
`idempotent_replay` from a conflicting `idempotency_conflict`. A uniqueness race is resolved by an
`IntegrityError` re-query, mirroring Phases 20–24, 27, 30, and 33.

## Receipt and outcomes

`IntakeNoteWriteReceipt` reports `outcome` (`created` / `idempotent_replay` / `denied` /
`failed_before_write` / `write_outcome_uncertain`), `permitted`, `reason_code`, `target_table`,
`target_action`, `stored_record_id`, `idempotency_key`, `audit_trace_ref`, the actual-behavior flags
(`database_connection_made`, `sql_execution_made`, `database_write_made`, `stored_record_created`,
`existing_record_returned`, `transaction_committed`, `outcome_uncertain`), the safe routing labels
(`note_type`, `note_source`, `review_status`, `lifecycle_status`), the always-false non-effect flags
(`review_records_write_made`, `review_approval_made`, `client_facing_output_created`,
`financial_verification_made`, `capsule_publication_made`, `agentnet_publication_made`,
`agent_execution_made`, `llm_call_made`, `agentnet_call_made`, `resolver_call_made`,
`network_call_made`), and server-stamped `created_at` / `database_write_at`. It contains **no
credentials, DB URL, raw SQL, `note_text` / note body, or stack trace**. An **uncertain** commit
never falsely claims no record exists.

## Migration and table

Migration `009_intake_note_records` (`down_revision = 008_internal_reviewer_decision_records`)
creates the single new `intake_note_records` table (governance/audit columns + `note_text` TEXT +
safe label/ref columns + non-final posture columns + idempotency columns + the unique index). It is
additive and non-destructive, contains **no INSERT and no seed data**, and its downgrade drops only
the new table/indexes/constraint. Alembic remains single-head; `make db-check` now expects **exactly
15 tables**.

**SQLite is only the fast local structural-smoke path — not the production-readiness proof path.**
Managed MySQL test/staging validation is required before treating this writer as production-ready;
see [`MANAGED_MYSQL_PERSISTENCE_RUBRIC.md`](MANAGED_MYSQL_PERSISTENCE_RUBRIC.md) and
[`PRODUCTION_PARITY_DB_VALIDATION.md`](PRODUCTION_PARITY_DB_VALIDATION.md).

## Boundaries

- **One table/action only:** `intake_note_records` / `create_intake_note_record`. Any other table
  or action (update / delete / upsert / approve / publish / execute / client-facing approval /
  financial verification / raw SQL, or a `review_records` / `agent_run_records` target) is denied.
- **No approval, no `approve_internal`, no Phase 22 writer call, no `review_records` write.**
- **No agent / mock-agent / LLM / MockLLM / AgentNet / AgentNet publication / MCP / resolver /
  connector / network call; no `agent_run_records` write; no client-facing output, financial
  verification, or capsule publication; never updates or deletes.**
