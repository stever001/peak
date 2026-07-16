# Agent Run Controlled Writer (Phase 20)

The first **real DB-backed persistence path** in Peak: a narrow controlled writer that
creates review-gated `agent_run_records` rows from the Phase 19 persistence mapping output.
It is a tightly scoped internal persistence boundary — **not** a generic CRUD repository,
database service, or arbitrary table writer. **AgentNet integration is not complete.**

## Where it sits (Phases 13 → 17 → 19 → 20)

- **Phase 13** ([`AGENT_EXECUTION_HARNESS.md`](AGENT_EXECUTION_HARNESS.md)) governs and drafts
  a (mock, non-executing) agent run — `AgentTaskResult` + `AgentRunDraft`.
- **Phase 17** ([`CONTROLLED_DB_WRITER_BOUNDARY.md`](CONTROLLED_DB_WRITER_BOUNDARY.md)) is the
  generic controlled-write boundary: table/action allowlist, idempotency key, snapshot-level
  stored-scope check. It plans, it does not write.
- **Phase 19** ([`AGENT_RUN_PERSISTENCE_MAPPING.md`](AGENT_RUN_PERSISTENCE_MAPPING.md)) maps
  the agent run output into an `AgentRunPersistenceDraft` and a Phase 17
  `ControlledWriteRequest` targeting `agent_run_records` / `create_agent_run_record` — still
  DB-free.
- **Phase 20** (this document, [`../peak/db/agent_run_writer.py`](../peak/db/agent_run_writer.py))
  is the first phase that **actually writes to the database**, under all the governance,
  authorization, idempotency, and audit boundaries the earlier phases established.

The Phase 19 agent-domain mapper stays **DB-free**. The live writer lives in the DB layer
(`peak.db`), which may use SQLAlchemy and the ORM models; it imports **no** LLM, AgentNet,
connector, network-client, or credential module.

## Write-time DB-backed authorization

The writer does **not** trust the Phase 19 subject snapshot as proof of authorization. The
snapshot is a mapping-time convenience; by write time the underlying record may have been
re-scoped or revoked. At **write-time** the writer:

1. loads the **authoritative stored authorization subject** (the `Engagement` row) from the
   database, by its tightly scoped id — never accepting a caller-provided stored object;
2. requires `request.authorization_scope == engagement.authorization_scope` (the **stored
   authorization** scope read from the DB);
3. rejects a **missing stored scope** and a **missing request scope**;
4. re-validates that the stored subject's owner / client / engagement identity matches the
   request.

### Selected authorization anchor and rationale

The anchor is the **`Engagement`** record (table `engagements`, id `eng_<slug>`). An agent
run is scoped to an engagement, and the engagement row carries the governed
`authorization_scope`, `owner_id`, `client_id`, and `lifecycle_status` for that engagement's
work. The new `agent_run_records` row has **no stored row of its own yet**, so it inherits
write authority from the engagement — which is exactly the record whose stored scope governs
whether this write is allowed. No redundant authorization table is introduced; the existing
engagement model is the correct, already-defined anchor.

### Identity matching is necessary but not sufficient

Even when owner, client, engagement, and subject identities all match, the write is **denied**
when `request.authorization_scope` differs from the stored `engagement.authorization_scope`.
Identity proves *who*; the stored scope proves *whether the write is currently authorized*.
The writer independently re-validates identity across the controlled-write request, the
Phase 19 persistence request, the persistence draft, the originating agent task request, and
the stored subject, and rejects any mismatch.

## Allowed table / action (explicit allowlist)

Exactly one target is permitted:

- `target_table = agent_run_records`
- `requested_action = create_agent_run_record`

Everything else is rejected: any other table, any other action, `update`, `delete`,
`upsert`, arbitrary SQL, arbitrary column selection, caller-selected model classes, and
caller-selected repository functions. There is no generic write surface.

## Input acceptance (concrete contracts, not duck typing)

The writer consumes the production-shaped Phase 17 `ControlledWriteRequest` (with its
`record_draft` being a Phase 19 `AgentRunPersistenceDraft`) produced through the Phase 17/19
path, plus the optional Phase 19 `AgentRunPersistenceRequest` for extra cross-object identity
validation. It **isinstance-checks** the concrete contracts and rejects malformed or
duck-typed objects that merely expose a few matching attributes. It validates that:

- the controlled-write plan was permitted and requires the controlled DB writer;
- the target table/action are the allowlisted pair;
- the draft is a Phase 19 draft with `output_status=draft` and `review_status=needs_review`;
- the draft carries **no caller-supplied** record id and **no caller-supplied** timestamp;
- all prohibited side-effect flags remain false;
- the idempotency key is present and valid;
- all required identity/traceability fields are present.

## Review-gated creation only, and server-controlled fields

The writer may create only an `agent_run_records` row with `output_status=draft` and
`review_status=needs_review`. It stamps **server-controlled** fields with an explicit field
mapping (never `__dict__` / `asdict` / a caller mapping): the record id (`arun_<hex>`),
`created_at` / `updated_at` (DB `server_default`), `output_status`, `review_status`,
`lifecycle_status`, `idempotency_key`, `payload_fingerprint`, and audit `created_by`.
Caller-supplied values for server-controlled fields are rejected. Non-governance detail
(agent name, workflow, input record ids, resolver flags) is stored in `details_json`.

## Idempotency, replay, and replay conflict

Idempotency is **DB-enforced** by a unique index over
`(owner_id, client_id, engagement_id, idempotency_key)`. See
[`AGENT_RUN_IDEMPOTENCY_POLICY.md`](AGENT_RUN_IDEMPOTENCY_POLICY.md) for the full policy. In
short:

- an exact authorized replay returns an `idempotent_replay` receipt referencing the existing
  row and **does not** create or mutate a second row;
- reuse of the same key with a conflicting payload/identity is **denied**, not treated as a
  replay;
- payload equivalence is determined by a deterministic `payload_fingerprint`.

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

Every attempt returns a typed `AgentRunWriteReceipt` (in
[`../peak/db/writer_contracts.py`](../peak/db/writer_contracts.py)) — production-shaped and
auditable, exposing no credentials, SQL strings, connection URLs, or raw stored content. Its
flags report **actual** behavior: a denial before any connection reports
`database_connection_made=false` / `sql_execution_made=false`; an idempotent replay reports
reads but no new record; a created result reports the committed write; an uncertain outcome
sets `outcome_uncertain=true`.

## Side-effect boundaries

Phase 20 performs only the DB work required to read the stored subject, check idempotency,
insert the authorized row, read it back, and commit or roll back. It does **no LLM** call,
**no AgentNet** call, no MCP/resolver/connector call, no external network request, no
client-facing output, no financial verification or calculation, no email, no unrelated
enqueue, **no capsule publication**, and it never modifies another business record, never
changes a record away from `needs_review`, never updates an existing agent-run record, and
never deletes anything.

## Denial model

Expected governance failures return typed denials (with a machine `reason_code`) rather than
uncontrolled exceptions: wrong table/action, unpermitted plan, missing writer requirement,
invalid draft posture, identity mismatch, missing/mismatched authorization scope, missing
subject, invalid idempotency key, conflicting replay, caller-supplied id/timestamp, and
prohibited side-effect state. Unexpected infrastructure failures are converted, where
feasible, into a safe `failed_before_write` / `write_outcome_uncertain` result that leaks no
credentials, SQL, stack traces, or connection details.

## Schema / migration

Migration `002_agent_run_idempotency` adds only what this phase needs to
`agent_run_records`: `output_status`, `idempotency_key`, `payload_fingerprint`, and the
`uq_agent_run_records_idem` unique index. It is additive and non-destructive with a full
downgrade path; it contains **no INSERT, no seed, and no data**. No production database is
accessed; local dependency-backed checks use a temporary SQLite database built from the
models.
