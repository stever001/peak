# Source Ingestion Record Controlled Writer (Phase 24)

The **fourth real DB-backed persistence path** in Peak: a narrow controlled writer that
creates `source_ingestion_records` rows from the Phase 23 engagement-packet ingestion output.
It applies the same pattern as the Phase 20 (`agent_run_records`), Phase 21
(`evidence_references`), and Phase 22 (`review_records`) writers to a fourth table. It is a
tightly scoped internal persistence boundary — **not** a generic CRUD repository, an arbitrary
packet importer, or a packet-payload store. **AgentNet integration is not complete.**

## Where it sits (Phase 23 → 17 → 24)

- **Phase 23** ([`ENGAGEMENT_PACKET_INGESTION_BOUNDARY.md`](ENGAGEMENT_PACKET_INGESTION_BOUNDARY.md),
  [`PACKET_TO_CONTROLLED_WORKFLOW_POLICY.md`](PACKET_TO_CONTROLLED_WORKFLOW_POLICY.md)) validates
  an external `EngagementPacket` and derives a review-gated `SourceIngestionDraft` plus a
  plan-only Phase 17 `ControlledWriteRequest` — DB-free.
- **Phase 17** ([`CONTROLLED_DB_WRITER_BOUNDARY.md`](CONTROLLED_DB_WRITER_BOUNDARY.md)) is the
  generic controlled-write boundary: table/action allowlist, idempotency key, snapshot-level
  stored-scope check. It plans, it does not write.
- **Phase 24** (this document, [`../peak/db/source_ingestion_writer.py`](../peak/db/source_ingestion_writer.py))
  actually **writes to the database**, under all the governance, authorization, idempotency,
  and audit boundaries the earlier phases established. It consumes a Phase 17
  `ControlledWriteRequest` whose `record_draft` is a Phase 23 `SourceIngestionDraft`.

The Phase 23 ingestion package stays **DB-free**. The live writer lives in the DB layer
(`peak.db`); it imports **no** LLM, AgentNet, connector, network-client, or credential module.

## Write-time DB-backed authorization

The writer does **not** trust the Phase 23 packet reference or draft as proof of
authorization. At **write-time** it:

1. loads the **authoritative stored authorization subject** (the `Engagement` row) from the
   database, by its tightly scoped id — never accepting a caller-provided stored object;
2. requires `request.authorization_scope == engagement.authorization_scope` (the **stored
   authorization** scope read from the DB);
3. rejects a **missing stored scope** and a **missing request scope**;
4. re-validates that the stored subject's owner / client / engagement identity matches the
   request, and that its lifecycle is not `revoked` / `archived` / `deleted_reference_only`.

### Selected authorization anchor and rationale

The anchor is the **`Engagement`** record (table `engagements`), matching Phases 20–22. A
packet ingestion is engagement-scoped, and the engagement row carries the governed
`authorization_scope`, `owner_id`, `client_id`, and `lifecycle_status`. The new source
ingestion record has **no stored row of its own yet**, so it inherits write authority from
the engagement — the record whose stored scope governs whether this write is allowed. No
redundant authorization table is introduced.

### Identity matching is necessary but not sufficient

Even when owner, client, and engagement identities all match, the write is **denied** when
`request.authorization_scope` differs from the stored `engagement.authorization_scope`.
Identity proves *who*; the stored scope proves *whether the write is currently authorized*.
The writer independently re-validates identity across the controlled-write request, the
draft, the engagement subject, and the Phase 23 packet ingestion request, and rejects any
mismatch.

## Allowed table / action (explicit allowlist)

Exactly one target is permitted:

- `target_table = source_ingestion_records`
- `requested_action = create_source_ingestion_record`

Everything else is rejected: any other table, any other action, `update`, `delete`,
`upsert`, arbitrary SQL, arbitrary column selection, caller-selected model classes,
caller-selected repository functions, and any arbitrary packet importer behavior.

## Packet metadata only — no packet payload storage

This is the defining rule of the source-ingestion writer: it persists **packet metadata
only**. Allowed metadata is `packet_reference_id`, `packet_schema_name`,
`packet_schema_version`, `packet_source_type`, `packet_location_reference`, `packet_hash`,
the owner/client/engagement identity, the output/review/lifecycle statuses, reasons/warnings,
the `idempotency_key`, and the `payload_fingerprint`. It **never** persists the full
`packet_payload`, raw interview text, raw evidence body, source file bytes, arbitrary packet
JSON, or any credential/secret. A draft carrying a `packet_payload` / `raw_packet_content` /
secret-like attribute is **rejected** (`prohibited_packet_content`), and only attribute names
— never values — are surfaced in the reason.

## Review-gated creation only, and server-controlled fields

The writer may create only a review-gated row: required draft posture `output_status=draft`,
`review_status=needs_review`, `lifecycle_status=active`, non-authoritative, not
client-facing-approved, not a capsule candidate. It stamps **server-controlled** fields with
an explicit field mapping (never `__dict__` / `asdict` / a caller mapping): the record id
(`ing_<hex>`), `created_at` / `updated_at` (DB `server_default`), `output_status`,
`review_status`, `lifecycle_status`, `idempotency_key`, `payload_fingerprint`, and audit
`created_by`. Caller-supplied values for server-controlled fields
(`source_ingestion_record_id`, `created_at`) are rejected. The packet reference id is stored
as the record's `source_reference_id`; other packet metadata lives in `details_json`.

## Idempotency, replay, and replay conflict

Idempotency is **DB-enforced** by a unique index over
`(owner_id, client_id, engagement_id, idempotency_key)`. See
[`SOURCE_INGESTION_IDEMPOTENCY_POLICY.md`](SOURCE_INGESTION_IDEMPOTENCY_POLICY.md). An exact
authorized replay returns an `idempotent_replay` receipt referencing the existing row and does
not create or mutate a second row; reuse of the same key with a conflicting payload/identity is
denied; payload equivalence is determined by a deterministic `payload_fingerprint` (over packet
**metadata** only).

## Transaction behavior and outcome semantics

Authorization, idempotency, insert, and read-back happen in a controlled transactional
sequence. A DB uniqueness constraint (not check-then-insert) prevents duplicate rows under a
race; an `IntegrityError` is handled deterministically (re-query → replay or conflict). The
writer distinguishes:

- `created` — the row was inserted and the transaction committed;
- `idempotent_replay` — an existing equivalent row was returned; nothing new was written;
- `denied` — a governance/authorization failure; no row written;
- `failed_before_write` — an infrastructure failure **before** any insert was attempted;
- `write_outcome_uncertain` — the process could not confirm whether the commit succeeded.

`failed_before_write` is never reported once a commit may have occurred. When
`write_outcome_uncertain` is set, the create/commit booleans are indeterminate and the
uncertain outcome governs — the receipt does not falsely claim that no record exists.

## Persistence receipt

Every attempt returns a typed `SourceIngestionWriteReceipt` (in
[`../peak/db/writer_contracts.py`](../peak/db/writer_contracts.py)) — production-shaped and
auditable, exposing no credentials, SQL strings, connection URLs, or **raw packet content**.
Its flags report **actual** behavior: a denial before any connection reports
`database_connection_made=false` / `sql_execution_made=false`; an idempotent replay reports
reads but no new record; a created result reports the committed write; an uncertain outcome
sets `outcome_uncertain=true`.

## Side-effect boundaries

Phase 24 performs only the DB work required to read the stored subject, check idempotency,
insert the authorized row, read it back, and commit or roll back. It does **no LLM** call,
**no AgentNet** call, no MCP/resolver/connector call, no external network request, **no
client-facing approval**, **no financial verification**, and **no capsule publication**, and
it never modifies another business record, never updates an existing source ingestion record,
and never deletes anything.

## Denial model

Expected governance failures return typed denials (with a machine `reason_code`) rather than
uncontrolled exceptions: wrong table/action, unpermitted plan, invalid draft posture,
identity mismatch, missing/mismatched authorization scope, missing subject, invalid
idempotency key, conflicting replay, caller-supplied id/timestamp, prohibited packet content,
and missing source reference. Unexpected infrastructure failures are converted, where
feasible, into a safe `failed_before_write` / `write_outcome_uncertain` result that leaks no
credentials, SQL, stack traces, or packet content.

## Schema / migration

Migration `005_source_ingestion_idempotency` adds only what this phase needs to
`source_ingestion_records`: `output_status`, `idempotency_key`, `payload_fingerprint`, and the
`uq_source_ingestion_records_idem` unique index. It is additive and non-destructive with a full
downgrade path; it contains **no INSERT, no seed, and no data**. No production database is
accessed; local dependency-backed checks use a temporary SQLite database built from the models.
