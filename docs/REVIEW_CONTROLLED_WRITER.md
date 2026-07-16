# Review Record Controlled Writer (Phase 22)

The **third real DB-backed persistence path** in Peak: a narrow controlled writer that
creates `review_records` rows from the Phase 16 review persistence mapping output. It applies
the same pattern as the Phase 20 (`agent_run_records`) and Phase 21 (`evidence_references`)
writers to a third table. It is a tightly scoped internal persistence boundary — **not** a
generic CRUD repository, database service, or arbitrary table writer. **AgentNet integration
is not complete.**

## Where it sits (Phases 15 → 16 → 17 → 22)

- **Phase 15** ([`QA_REVIEW_GATE.md`](QA_REVIEW_GATE.md), [`REVIEW_DECISION_MODEL.md`](REVIEW_DECISION_MODEL.md))
  computes a review decision (`approve_internal` / `reject` / `return_for_revision` /
  `supersede` / `keep_needs_review`) with no side effects.
- **Phase 16** ([`REVIEW_PERSISTENCE_BOUNDARY.md`](REVIEW_PERSISTENCE_BOUNDARY.md),
  [`DB_BACKED_REVIEW_SCOPE_POLICY.md`](DB_BACKED_REVIEW_SCOPE_POLICY.md)) maps a permitted
  decision into a `ReviewRecordDraft` — DB-free.
- **Phase 17** ([`CONTROLLED_DB_WRITER_BOUNDARY.md`](CONTROLLED_DB_WRITER_BOUNDARY.md)) is the
  generic controlled-write boundary: table/action allowlist, idempotency key, snapshot-level
  stored-scope check. It plans, it does not write.
- **Phase 22** (this document, [`../peak/db/review_writer.py`](../peak/db/review_writer.py))
  actually **writes to the database**, under all the governance, authorization, idempotency,
  and audit boundaries the earlier phases established. It consumes a Phase 17
  `ControlledWriteRequest` whose `record_draft` is a Phase 16 `ReviewRecordDraft`.

The Phase 16 review-persistence mapper stays **DB-free**. The live writer lives in the DB
layer (`peak.db`); it imports **no** LLM, AgentNet, connector, network-client, or credential
module.

## Write-time DB-backed authorization

The writer does **not** trust the Phase 16 subject snapshot as proof of authorization. At
**write-time** it:

1. loads the **authoritative stored authorization subject** (the `Engagement` row) from the
   database, by its tightly scoped id — never accepting a caller-provided stored object;
2. requires `request.authorization_scope == engagement.authorization_scope` (the **stored
   authorization** scope read from the DB);
3. rejects a **missing stored scope** and a **missing request scope**;
4. re-validates that the stored subject's owner / client / engagement identity matches the
   request, and that its lifecycle is not `revoked` / `archived` / `deleted_reference_only`.

### Selected authorization anchor and rationale

The anchor is the **`Engagement`** record (table `engagements`), matching Phases 20–21. A
review action is engagement-scoped, and the engagement row carries the governed
`authorization_scope`, `owner_id`, `client_id`, and `lifecycle_status`. Note that a review
record has **two** distinct subjects: the **authorization anchor** (the engagement, carried
on `ControlledWriteRequest.subject`) and the **reviewed target** (the record the decision is
about, carried on `ReviewRecordDraft.subject_record_id` and persisted as the row's
`target_id`). Authorization is always anchored to the engagement.

### Identity matching is necessary but not sufficient

Even when owner, client, and engagement identities all match, the write is **denied** when
`request.authorization_scope` differs from the stored `engagement.authorization_scope`.
Identity proves *who*; the stored scope proves *whether the write is currently authorized*.
The writer independently re-validates identity across the controlled-write request, the
draft, the engagement subject, and the Phase 16 persistence request (including that its
subject snapshot matches the reviewed target), and rejects any mismatch.

## Allowed table / action (explicit allowlist)

Exactly one target is permitted:

- `target_table = review_records`
- `requested_action = create_review_record`

Everything else is rejected: any other table, any other action, `update`, `delete`,
`upsert`, arbitrary SQL, arbitrary column selection, caller-selected model classes, and
caller-selected repository functions.

## Review decision posture

The writer persists only governed review outcomes. In short, approve_internal means internal
reliance only — never client-facing approval.

- **Allowed decisions:** `approve_internal`, `reject`, `return_for_revision`, `supersede`,
  `keep_needs_review`.
- **`approve_internal` means internal reliance only.** It may set `authoritative=true` — but
  **only** when `next_review_status=approved_internal` — and it **never** creates
  client-facing approval.
- **`reject` / `return_for_revision` / `supersede` / `keep_needs_review` must be
  non-authoritative** (`authoritative=false`).
- **Prohibited decisions** are rejected outright: `client_facing_approve`,
  `verify_financial_impact`, `publish_capsule`.
- `client_facing_approved=true` and `capsule_candidate_ready=true` on the draft are rejected;
  a review write **never** creates client-facing approval or a capsule candidate.

## Server-controlled fields

The writer stamps **server-controlled** fields with an explicit field mapping (never
`__dict__` / `asdict` / a caller mapping): the record id (`rev_<hex>`), `created_at` /
`updated_at` (DB `server_default`), and audit `created_by`. Caller-supplied values for
server-controlled fields (`review_record_id`, `created_at`) are rejected. The decision and
its next states map to real columns (`decision`, `authoritative`, `new_status`,
`review_status`, `lifecycle_status`, `output_status`); the reviewed target is `target_id` +
`subject_record_type`; reviewer role, reasons, warnings, and flags are stored in
`details_json`.

## Idempotency, replay, and replay conflict

Idempotency is **DB-enforced** by a unique index over
`(owner_id, client_id, engagement_id, idempotency_key)`. See
[`REVIEW_IDEMPOTENCY_POLICY.md`](REVIEW_IDEMPOTENCY_POLICY.md). An exact authorized replay
returns an `idempotent_replay` receipt referencing the existing row and does not create or
mutate a second row; reuse of the same key with a conflicting payload/identity is denied;
payload equivalence is determined by a deterministic `payload_fingerprint`.

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

Every attempt returns a typed `ReviewWriteReceipt` (in
[`../peak/db/writer_contracts.py`](../peak/db/writer_contracts.py)) — production-shaped and
auditable, exposing no credentials, SQL strings, connection URLs, or raw stored content. It
echoes the recorded `decision` / `authoritative` / `review_status` / `output_status`, and its
flags report **actual** behavior: a denial before any connection reports
`database_connection_made=false` / `sql_execution_made=false`; an idempotent replay reports
reads but no new record; a created result reports the committed write; an uncertain outcome
sets `outcome_uncertain=true`.

## Side-effect boundaries

Phase 22 performs only the DB work required to read the stored subject, check idempotency,
insert the authorized row, read it back, and commit or roll back. It does **no LLM** call,
**no AgentNet** call, no MCP/resolver/connector call, no external network request, **no
client-facing approval**, **no financial verification**, and **no capsule publication**, and
it never modifies another business record, never updates an existing review record, and never
deletes anything.

## Denial model

Expected governance failures return typed denials (with a machine `reason_code`) rather than
uncontrolled exceptions: wrong table/action, unpermitted plan, invalid/prohibited decision,
prohibited authoritative, invalid approve_internal state, identity mismatch,
missing/mismatched authorization scope, missing subject, invalid idempotency key, conflicting
replay, caller-supplied id/timestamp, and prohibited client-facing/capsule posture. Unexpected
infrastructure failures are converted, where feasible, into a safe `failed_before_write` /
`write_outcome_uncertain` result that leaks no credentials, SQL, stack traces, or connection
details.

## Schema / migration

Migration `004_review_idempotency` adds only what this phase needs to `review_records`:
`decision`, `subject_record_type`, `authoritative`, `output_status`, `idempotency_key`,
`payload_fingerprint`, and the `uq_review_records_idem` unique index. It is additive and
non-destructive with a full downgrade path; it contains **no INSERT, no seed, and no data**.
No production database is accessed; local dependency-backed checks use a temporary SQLite
database built from the models.
