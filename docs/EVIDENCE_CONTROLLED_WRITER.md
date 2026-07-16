# Evidence Controlled Writer (Phase 21)

The **second real DB-backed persistence path** in Peak: a narrow controlled writer that
creates review-gated `evidence_references` rows from the Phase 18 evidence persistence
mapping output. It applies the same pattern as the Phase 20 `agent_run_records` writer to a
second table. It is a tightly scoped internal persistence boundary — **not** a generic CRUD
repository, database service, or arbitrary table writer. **AgentNet integration is not
complete.**

## Where it sits (Phases 14 → 17 → 18 → 21)

- **Phase 14** ([`EVIDENCE_NORMALIZATION_WORKER.md`](EVIDENCE_NORMALIZATION_WORKER.md))
  normalizes raw evidence into a review-gated `NormalizedEvidenceRecord` — no side effects.
- **Phase 17** ([`CONTROLLED_DB_WRITER_BOUNDARY.md`](CONTROLLED_DB_WRITER_BOUNDARY.md)) is the
  generic controlled-write boundary: table/action allowlist, idempotency key, snapshot-level
  stored-scope check. It plans, it does not write.
- **Phase 18** ([`EVIDENCE_PERSISTENCE_MAPPING.md`](EVIDENCE_PERSISTENCE_MAPPING.md)) maps a
  normalized record into an `EvidencePersistenceDraft` and a Phase 17 `ControlledWriteRequest`
  targeting `evidence_references` / `create_draft` — still DB-free.
- **Phase 21** (this document, [`../peak/db/evidence_writer.py`](../peak/db/evidence_writer.py))
  actually **writes to the database**, under all the governance, authorization, idempotency,
  and audit boundaries the earlier phases established.

The Phase 18 evidence-domain mapper stays **DB-free**. The live writer lives in the DB layer
(`peak.db`), which may use SQLAlchemy and the ORM models; it imports **no** LLM, AgentNet,
connector, network-client, or credential module.

## Write-time DB-backed authorization

The writer does **not** trust the Phase 18 subject snapshot as proof of authorization. At
**write-time** it:

1. loads the **authoritative stored authorization subject** (the `Engagement` row) from the
   database, by its tightly scoped id — never accepting a caller-provided stored object;
2. requires `request.authorization_scope == engagement.authorization_scope` (the **stored
   authorization** scope read from the DB);
3. rejects a **missing stored scope** and a **missing request scope**;
4. re-validates that the stored subject's owner / client / engagement identity matches the
   request, and that its lifecycle is not `revoked` / `archived` / `deleted_reference_only`.

### Selected authorization anchor and rationale

The anchor is the **`Engagement`** record (table `engagements`), matching Phase 20. Evidence
is engagement-scoped, and the engagement row carries the governed `authorization_scope`,
`owner_id`, `client_id`, and `lifecycle_status`. A freshly normalized evidence record has
**no stored row of its own yet**, so it inherits write authority from the engagement — the
record whose stored scope governs whether this write is allowed. No redundant authorization
table is introduced.

### Identity matching is necessary but not sufficient

Even when owner, client, engagement, and subject identities all match, the write is **denied**
when `request.authorization_scope` differs from the stored `engagement.authorization_scope`.
Identity proves *who*; the stored scope proves *whether the write is currently authorized*.
The writer independently re-validates identity across the controlled-write request, the
Phase 18 persistence request, the persistence draft, the normalized record, and the stored
subject, and rejects any mismatch.

## Allowed table / action (explicit allowlist)

Exactly one target is permitted:

- `target_table = evidence_references`
- `requested_action = create_draft`

Everything else is rejected: any other table, any other action, `update`, `delete`,
`upsert`, arbitrary SQL, arbitrary column selection, caller-selected model classes, and
caller-selected repository functions. Client-facing approval, financial verification, and
capsule publication are not actions this writer can take.

## Input acceptance (concrete contracts, not duck typing)

The writer consumes the production-shaped Phase 17 `ControlledWriteRequest` (with its
`record_draft` being a Phase 18 `EvidencePersistenceDraft`) produced through the Phase 17/18
path, plus the optional Phase 18 `EvidencePersistenceRequest` for extra cross-object identity
validation. It **isinstance-checks** the concrete contracts and rejects malformed or
duck-typed objects. It validates that the plan was permitted and requires the controlled DB
writer; the target table/action are the allowlisted pair; the draft is a Phase 18 draft;
and the idempotency key and identity fields are present.

## Review-gated creation only, and server-controlled fields

The writer may create only an `evidence_references` row that is review-gated. Required draft
posture (all enforced): `output_status=draft`, `review_status=needs_review`,
`lifecycle_status=active`, `authoritative=false`, `client_facing_approved=false`,
`capsule_candidate_ready=false`. It stamps **server-controlled** fields with an explicit
field mapping (never `__dict__` / `asdict` / a caller mapping): the record id (`evid_<hex>`),
`created_at` / `updated_at` (DB `server_default`), `output_status`, `review_status`,
`lifecycle_status`, `idempotency_key`, `payload_fingerprint`, and audit `created_by`.
Caller-supplied values for server-controlled fields (`evidence_record_id`, `created_at`) are
rejected. Normalized detail (title, observed condition, areas, source location, confidence)
is stored in `details_json`; `evidence_type` / `source_type` / `reliability` / `summary` map
to their existing real columns.

## Idempotency, replay, and replay conflict

Idempotency is **DB-enforced** by a unique index over
`(owner_id, client_id, engagement_id, idempotency_key)`. See
[`EVIDENCE_IDEMPOTENCY_POLICY.md`](EVIDENCE_IDEMPOTENCY_POLICY.md) for the full policy. In
short: an exact authorized replay returns an `idempotent_replay` receipt referencing the
existing row and does not create or mutate a second row; reuse of the same key with a
conflicting payload/identity is denied; payload equivalence is determined by a deterministic
`payload_fingerprint`.

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

Every attempt returns a typed `EvidenceWriteReceipt` (in
[`../peak/db/writer_contracts.py`](../peak/db/writer_contracts.py)) — production-shaped and
auditable, exposing no credentials, SQL strings, connection URLs, or raw stored content. Its
flags report **actual** behavior: a denial before any connection reports
`database_connection_made=false` / `sql_execution_made=false`; an idempotent replay reports
reads but no new record; a created result reports the committed write; an uncertain outcome
sets `outcome_uncertain=true`.

## Side-effect boundaries

Phase 21 performs only the DB work required to read the stored subject, check idempotency,
insert the authorized row, read it back, and commit or roll back. It does **no LLM** call,
**no AgentNet** call, no MCP/resolver/connector call, no external network request, no
client-facing approval, no financial verification or calculation, **no capsule publication**,
and it never modifies another business record, never changes a record away from
`needs_review`, never updates an existing evidence record, and never deletes anything.

## Denial model

Expected governance failures return typed denials (with a machine `reason_code`) rather than
uncontrolled exceptions: wrong table/action, unpermitted plan, invalid draft posture,
identity mismatch, missing/mismatched authorization scope, missing subject, invalid
idempotency key, conflicting replay, caller-supplied id/timestamp, and prohibited posture
(authoritative / client-facing / capsule-ready). Unexpected infrastructure failures are
converted, where feasible, into a safe `failed_before_write` / `write_outcome_uncertain`
result that leaks no credentials, SQL, stack traces, or connection details.

## Schema / migration

Migration `003_evidence_idempotency` adds only what this phase needs to `evidence_references`:
`output_status`, `idempotency_key`, `payload_fingerprint`, and the
`uq_evidence_references_idem` unique index. It is additive and non-destructive with a full
downgrade path; it contains **no INSERT, no seed, and no data**. No production database is
accessed; local dependency-backed checks use a temporary SQLite database built from the
models.
