# Database Access and Audit

Planned access-control and audit model for Peak's controlled engagement database.
**Planning only — no database, access-control code, or stored data is created.** AgentNet
grounding is **intended future architecture, not implemented**.

## Access-control assumptions

- The database is **private and internal** to Peak; there is **no client data in Git** and
  no public access. It holds live client data only for **authorized engagement work**.
- Access is **scoped by identity fields**: `owner_id`, `client_id`, `engagement_id`. A
  principal sees only the clients/engagements it is authorized for.
- Every record carries an `authorization_scope` that gates use and disclosure (see
  [`GOVERNANCE_STATES.md`](GOVERNANCE_STATES.md)); `revoked` blocks access.
- Least privilege by default; elevation (e.g. client-facing approval, capsule publication)
  is an explicit governed action, not a default.

## Roles

| Role | Can | Cannot |
| --- | --- | --- |
| **Peak admin** | Manage clients/engagements, roles, authorization scopes | Bypass human-review gates |
| **Peak consultant** | Create/edit engagement records; run prompt contracts by hand; advance review up to `consultant_reviewed` | Set `qa_reviewed`/`approved_internal` alone where separation is required; approve client-facing without the gate |
| **QA reviewer** | Set `qa_reviewed`/`approved_internal`; record `ReviewRecord`s | Author the work they review (separation of duties) |
| **Client approver** *(future)* | Provide client-side approvals within their engagement | Access other engagements/clients |
| **Agent worker** *(future)* | Draft records defaulting to `draft`/`needs_review` under `agent_run_id` | Approve, verify, or publish anything (see limits below) |
| **Resolver publisher** *(future)* | Execute governed capsule publication after approval | Publish without an approved `CapsulePublicationCandidate` |

## Audit fields (every record)

- `created_at`, `created_by`
- `updated_at`, `updated_by`
- `source_reference_ids` — `SourceSystemReference` ids the record derives from
- `evidence_ids` — `EvidenceReference` ids grounding the record
- `review_status` — governance review state
- `lifecycle_status` — lifecycle state
- `authorization_scope` — how the record may be used
- `agent_run_id` — set where an agent/worker produced or edited the record

These make every record **traceable**: who created/changed it, from what sources and
evidence, under what authorization, in what review/lifecycle state, and (if applicable)
which agent run produced it. As of Phase 11 these audit and governance fields are **real
columns** on the SQLAlchemy models ([`../peak/db/base.py`](../peak/db/base.py)),
never hidden inside `details_json`.

## Human review gates

- No record becomes client-facing without an explicit human `client_facing_approved`
  (see [`STATE_TRANSITIONS.md`](STATE_TRANSITIONS.md)).
- Financial impact reaches `verified`/`client_facing_approved` only after finance/human
  review.
- Resolver capsules are activated/promoted/published only through governance approval.
- Separation of duties: reviewers should not approve their own authored work where the
  process requires independence.

## Agent permission limits

For any future agent worker:

- **No agent may mark a record `client_facing_approved`.**
- **No agent may publish capsules** (or approve a `CapsulePublicationCandidate`) **without
  human/governance approval.**
- **No agent may verify financial impact without human review** (agents may reach at most
  `calculated`/`finance_review_needed`).
- **No agent may promote a capsule to methodology** — it may only *propose* a
  `methodology_candidate`.
- Agent-generated records **default to `draft` or `needs_review`** and carry an
  `agent_run_id` for provenance; advancement happens only through the human gates above.

These limits are **contract-level** and human-enforced; no agent runtime exists yet. The
Phase 13 scaffold in [`../peak/agents/`](../peak/agents/) encodes them as deterministic
pre-execution checks around a no-op mock executor (no live call, output defaults to
`draft`/`needs_review`); the provenance record it would eventually write is described in
[`AGENT_RUN_RECORDS.md`](AGENT_RUN_RECORDS.md). See
[`AGENT_EXECUTION_HARNESS.md`](AGENT_EXECUTION_HARNESS.md).

The Phase 14 **Evidence Normalization Worker** ([`../peak/workers/`](../peak/workers/))
applies the same posture to a production-shaped worker: its output is review-gated
(`draft`/`needs_review`, non-authoritative, non-client-facing) and it performs **no
database write** — a future governed writer persists reviewed records under these access
and audit rules. See [`EVIDENCE_RECORD_LIFECYCLE.md`](EVIDENCE_RECORD_LIFECYCLE.md).

The Phase 15 **QA / Review Gate** ([`../peak/review/`](../peak/review/)) is where a QA
reviewer's decision on such output is computed — production-shaped but **no-side-effect**.
`approve_internal` means internal reliance only; a review decision may never create
client-facing approval, verify financial impact, or publish a capsule. It writes nothing —
there are **no stored review records** in this phase — and a future governed writer would
persist the decision as the `ReviewRecord` above under these same access and audit rules.
See [`QA_REVIEW_GATE.md`](QA_REVIEW_GATE.md) and [`REVIEW_DECISION_MODEL.md`](REVIEW_DECISION_MODEL.md).

The Phase 16 **Review Persistence Boundary** ([`REVIEW_PERSISTENCE_BOUNDARY.md`](REVIEW_PERSISTENCE_BOUNDARY.md))
prepares that future `ReviewRecord` write — **DB-aware but not DB-writing**. It maps a
permitted `ReviewGateResult` into a `ReviewRecordDraft` and a no-op `ReviewWritePlan`
targeting `review_records`, but opens no DB connection and performs **no live database
read/write**; a future controlled-DB writer executes the plan under these rules. A
**critical access rule** lives here: a DB-backed review must load the subject record's
**stored** `authorization_scope` from the controlled DB and require
`request.authorization_scope == subject.stored_authorization_scope` — owner/client/engagement
matching is necessary but not sufficient. The persisted `ReviewRecord` should record both
the stored scope matched and the request scope presented, so the scope check is auditable.
See [`DB_BACKED_REVIEW_SCOPE_POLICY.md`](DB_BACKED_REVIEW_SCOPE_POLICY.md).

The Phase 17 **Controlled DB Writer Boundary** ([`CONTROLLED_DB_WRITER_BOUNDARY.md`](CONTROLLED_DB_WRITER_BOUNDARY.md),
[`CONTROLLED_WRITE_ALLOWLIST.md`](CONTROLLED_WRITE_ALLOWLIST.md)) is the generic front door
every future controlled write passes through — **DB-aware but not DB-writing**. Before any
plan is built it enforces a **table/action allowlist** (only `evidence_references`,
`engagement_records`, `review_records`, `agent_run_records`, `source_ingestion_records`, and
`capsule_publication_candidates` — never `clients` / `engagements` / `financial_impact_estimates` /
`resolver_capsule_records`), requires an `idempotency_key` for write safety, and re-runs the
stored-scope check (`request.authorization_scope == subject.stored_authorization_scope`;
identity matching necessary but not sufficient). Publish / client-facing-approve /
verify-financial / delete / migrate / seed / raw_sql actions are rejected, so the future
writer maps only allowlisted actions to parameterized operations under these audit rules —
it opens no connection and runs no SQL in this phase. A future writer would persist a
`ControlledWriteAuditDraft` (recording table, action, requester/role, idempotency key,
decision, and reasons) for each attempt.

The Phase 18 **Evidence Persistence Mapping** ([`EVIDENCE_PERSISTENCE_MAPPING.md`](EVIDENCE_PERSISTENCE_MAPPING.md),
[`EVIDENCE_WRITE_PLAN_POLICY.md`](EVIDENCE_WRITE_PLAN_POLICY.md)) is the first domain to use
that front door: it maps a Phase 14 normalized evidence record to a `ControlledWriteRequest`
for `evidence_references` / `create_draft`. Because the new evidence has **no stored row
yet**, its write authority is anchored to the **stored parent/source/engagement subject** —
the future writer loads that subject's `stored_authorization_scope` and requires
`request.authorization_scope == subject.stored_authorization_scope` (identity matching
necessary but not sufficient). Evidence workers still do not write directly to the DB, and
the review gate (`draft` / `needs_review`, non-authoritative, non-client-facing) is preserved
into the draft the writer would persist.

The Phase 19 **Agent Run Persistence Mapping** ([`AGENT_RUN_PERSISTENCE_MAPPING.md`](AGENT_RUN_PERSISTENCE_MAPPING.md),
[`AGENT_RUN_WRITE_PLAN_POLICY.md`](AGENT_RUN_WRITE_PLAN_POLICY.md)) is the second domain to
use that front door: it maps a Phase 13 agent run output (`AgentTaskResult` +
`AgentRunDraft`) to a `ControlledWriteRequest` for `agent_run_records` /
`create_agent_run_record`. As with evidence, the new agent run record has **no stored row
yet**, so its write authority is anchored to the **stored engagement/client/subject** — the
future writer loads that subject's `stored_authorization_scope` and requires
`request.authorization_scope == subject.stored_authorization_scope` (identity matching
necessary but not sufficient). Agent execution still does not write directly to the DB, and
the no-side-effect posture (`draft` / `needs_review`, all call/write flags false) is preserved
into the draft the writer would persist as provenance.

The Phase 20 **Agent Run Controlled Writer** ([`AGENT_RUN_CONTROLLED_WRITER.md`](AGENT_RUN_CONTROLLED_WRITER.md),
[`AGENT_RUN_IDEMPOTENCY_POLICY.md`](AGENT_RUN_IDEMPOTENCY_POLICY.md),
[`../peak/db/agent_run_writer.py`](../peak/db/agent_run_writer.py)) is that writer, now real.
It is the first component to actually write to the controlled database, and it enforces the
access/audit rules here at write-time: it loads the authoritative stored `Engagement` row and
requires `request.authorization_scope == engagement.authorization_scope` (the snapshot is
**not** trusted); it re-checks stored-subject identity and lifecycle; it creates only a
review-gated row (`output_status=draft`, `review_status=needs_review`) with server-controlled
id/timestamps/audit fields (`created_by` from the requester); and it enforces idempotency with
a DB unique index over `(owner_id, client_id, engagement_id, idempotency_key)` plus a payload
fingerprint. It never updates or deletes, and it returns a typed receipt carrying no
credentials, SQL, or connection details. Missing stored scope, missing request scope, a
stored-scope mismatch, or a conflicting idempotency replay are all denied with no row written.

The Phase 21 **Evidence Controlled Writer** ([`EVIDENCE_CONTROLLED_WRITER.md`](EVIDENCE_CONTROLLED_WRITER.md),
[`EVIDENCE_IDEMPOTENCY_POLICY.md`](EVIDENCE_IDEMPOTENCY_POLICY.md),
[`../peak/db/evidence_writer.py`](../peak/db/evidence_writer.py)) is the second such writer,
for `evidence_references` (`create_draft`). It enforces the same access/audit rules — stored
`Engagement` scope comparison (snapshot not trusted), stored-subject identity + lifecycle
re-check, review-gated row (`output_status=draft`, `review_status=needs_review`,
`lifecycle_status=active`, non-authoritative, non-client-facing, non-capsule) with
server-controlled id/timestamps and `created_by`, and DB-enforced idempotency over
`(owner_id, client_id, engagement_id, idempotency_key)` + payload fingerprint. It never
updates or deletes and returns a typed receipt with no credentials/SQL/connection details.

The Phase 22 **Review Record Controlled Writer** ([`REVIEW_CONTROLLED_WRITER.md`](REVIEW_CONTROLLED_WRITER.md),
[`REVIEW_IDEMPOTENCY_POLICY.md`](REVIEW_IDEMPOTENCY_POLICY.md),
[`../peak/db/review_writer.py`](../peak/db/review_writer.py)) is the third such writer, for
`review_records` (`create_review_record`). It enforces the same access/audit rules — stored
`Engagement` scope comparison (snapshot not trusted), stored-subject identity + lifecycle
re-check, server-controlled id/timestamps and `created_by`, and DB-enforced idempotency over
`(owner_id, client_id, engagement_id, idempotency_key)` + payload fingerprint. It records the
review decision and its next states (`decision`, `authoritative`, `new_status`,
`review_status`, `lifecycle_status`, `output_status`) with the reviewed target as `target_id`,
enforces that `approve_internal` is internal-reliance-only (never client-facing) while other
decisions stay non-authoritative, and rejects `client_facing_approve` / `verify_financial_impact`
/ `publish_capsule`. It never updates or deletes and returns a typed receipt with no
credentials/SQL/connection details.

The Phase 23 **Engagement Packet Ingestion Boundary** ([`ENGAGEMENT_PACKET_INGESTION_BOUNDARY.md`](ENGAGEMENT_PACKET_INGESTION_BOUNDARY.md),
[`PACKET_TO_CONTROLLED_WORKFLOW_POLICY.md`](PACKET_TO_CONTROLLED_WORKFLOW_POLICY.md),
[`../peak/ingestion/`](../peak/ingestion/)) sits upstream of these writers and **does not write
to the database at all** — it is an ingestion boundary that derives review-gated plans from an
external `EngagementPacket`. It validates packet identity/scope (`request.authorization_scope
== packet_reference.authorization_scope`; identity necessary but not sufficient), requires an
`idempotency_key`, and rejects credential/secret payload keys without echoing secret values. A
`source_ingestion_records` row is only ever *planned* there (a no-op Phase 17
`ControlledWriteRequest`).

The Phase 24 **Source Ingestion Record Controlled Writer** ([`SOURCE_INGESTION_CONTROLLED_WRITER.md`](SOURCE_INGESTION_CONTROLLED_WRITER.md),
[`SOURCE_INGESTION_IDEMPOTENCY_POLICY.md`](SOURCE_INGESTION_IDEMPOTENCY_POLICY.md),
[`../peak/db/source_ingestion_writer.py`](../peak/db/source_ingestion_writer.py)) is the fourth
such writer, for `source_ingestion_records` (`create_source_ingestion_record`). It enforces the
same access/audit rules — stored `Engagement` scope comparison (packet reference/draft not
trusted), stored-subject identity + lifecycle re-check, server-controlled id/timestamps and
`created_by`, and DB-enforced idempotency over `(owner_id, client_id, engagement_id,
idempotency_key)` + a metadata-only payload fingerprint. It persists **packet metadata only**
(reference id, schema, source type, location reference, hash), never the full packet payload,
raw content, or secrets, and rejects any draft carrying such content. It never updates or
deletes and returns a typed receipt with no credentials/SQL/connection/packet content.

The **Phase 25 Controlled Packet Processing Orchestrator**
([`CONTROLLED_PACKET_PROCESSING_ORCHESTRATOR.md`](CONTROLLED_PACKET_PROCESSING_ORCHESTRATOR.md))
may call these narrow writers in sequence, but it changes none of the access/audit rules here:
each writer still re-loads the authoritative stored `Engagement` scope at write-time (the
orchestrator's preflight identity checks are advisory, not a substitute), server-controls
id/timestamps and `created_by`, and enforces DB-level idempotency. The orchestration receipt
likewise carries no credentials, SQL, connection details, or raw packet payload content.

The **Phase 27** agent-task-queue writer
([`AGENT_TASK_QUEUE_CONTROLLED_WRITER.md`](AGENT_TASK_QUEUE_CONTROLLED_WRITER.md)) applies the same
access/audit rules to the new `agent_task_queue_records` table: write-time stored-`Engagement`
scope re-check (identity necessary but not sufficient), server-controlled id/timestamps and
`created_by`, DB-level idempotency, and a typed receipt with no credentials/SQL/connection/raw
content. It stores **safe references only** and a review-gated, **not-executed** posture — it
executes no agent and creates no `agent_run_records` row.

The **Phase 29 Packet-Derived Review Orchestration Boundary**
([`PACKET_DERIVED_REVIEW_ORCHESTRATION_BOUNDARY.md`](PACKET_DERIVED_REVIEW_ORCHESTRATION_BOUNDARY.md))
touches the database not at all: it is DB-free, opens no connection, writes no row, and approves
nothing. There is therefore no new access/audit surface in Phase 29.

The **Phase 30** review-bundle writer
([`REVIEW_BUNDLE_CONTROLLED_WRITER.md`](REVIEW_BUNDLE_CONTROLLED_WRITER.md)) applies the same
access/audit rules to the new `review_bundle_records` table: write-time stored-`Engagement` scope
re-check (identity necessary but not sufficient), server-controlled id/timestamps and `created_by`,
DB-level idempotency, and a typed receipt with no credentials/SQL/connection/raw content or review
decision. It stores **safe references only** and a review-gated, **not-approved** posture — it
approves nothing, calls no Phase 22 review writer, and creates no `review_records` row. **Phase 31**
may drive this writer from the Phase 25/28 orchestrator but changes none of these access/audit
rules: the write-time stored-`Engagement` scope re-check stays inside the writer (orchestrator
preflight is advisory, not a substitute).

The **Phase 32 Internal Reviewer Decision Boundary**
([`INTERNAL_REVIEWER_DECISION_BOUNDARY.md`](INTERNAL_REVIEWER_DECISION_BOUNDARY.md)) touches the
database not at all: it is DB-free, opens no connection, writes no row, approves nothing, and
creates no `review_records` row. There is therefore no new access/audit surface in Phase 32.

---

## Phase 37 — report-draft writes are audited like every other controlled write

`internal_assessment_report_drafts` rows carry the universal audit columns plus `requested_by` /
`requester_role`, `report_plan_id` / `plan_fingerprint` provenance, and `idempotency_key` /
`payload_fingerprint`. Every write returns a typed receipt whose flags report **actual** behavior and
which never echoes report prose, raw content, credentials, DSNs, raw SQL, stack traces, or approval
decisions. See
[`INTERNAL_ASSESSMENT_REPORT_DRAFT_CONTROLLED_WRITER.md`](INTERNAL_ASSESSMENT_REPORT_DRAFT_CONTROLLED_WRITER.md).

---

## Phase 38 — review-packet writes are audited like every other controlled write

`internal_report_review_packets` rows carry the universal audit columns plus `requested_by` /
`requester_role` / `assigned_reviewer`, full report-draft linkage and provenance, and
`idempotency_key` / `payload_fingerprint`. The packet is an **audit artifact in its own right**: it
records what a reviewer was shown, which is why the table has no update path — a changed packet is a
new row and the prior one stays intact. Every write returns a typed receipt whose flags report
**actual** behavior and which never echoes report prose, raw content, credentials, DSNs, raw SQL,
stack traces, or approval decisions. See
[`INTERNAL_REPORT_REVIEW_PACKET_CONTROLLED_WRITER.md`](INTERNAL_REPORT_REVIEW_PACKET_CONTROLLED_WRITER.md).

---

## Phase 39 — decisions are append-only audit facts

`internal_report_review_packet_decisions` rows carry the universal audit columns plus
`requested_by` / `requester_role` / `reviewer_ref`, the full packet -> report-draft -> report-plan
chain, both upstream payload fingerprints, and `idempotency_key` / `payload_fingerprint`. The table
has **no update path**: a reviewer changing their mind writes a new row under a new key, and the
prior decision stays intact — what a reviewer decided, and when, is a historical fact. The writer is
insert-only and never modifies the packet or report-draft row. See
[`INTERNAL_REPORT_REVIEW_PACKET_DECISION_CONTROLLED_WRITER.md`](INTERNAL_REPORT_REVIEW_PACKET_DECISION_CONTROLLED_WRITER.md).

---

## Phase 42 — comparison semantics are an audit concern

Audit trails depend on identity comparisons being exact. If `owner_id`, `client_id`,
`engagement_id`, or `idempotency_key` compare case-insensitively, then two audit records that
should be distinct can be merged by the database itself — and the audit trail records the merge,
not the intent.

The controlled schema currently leaves these comparisons to the managed server's default collation.
This is a recorded open finding, not an accepted position. See
[`GOVERNED_MYSQL_COLLATION_POLICY.md`](GOVERNED_MYSQL_COLLATION_POLICY.md).

---

## Phase 43 — read-only production introspection

Peak now inspects the real deployed database directly, under a boundary that is enforced
structurally rather than by convention: a hard-coded query allowlist, a guard that runs before
every execution, and a second check at the driver boundary. Only `SELECT`/`SHOW` metadata queries
are reachable; no code path exists that accepts SQL from a caller.

Access rules for this path: no schema mutation, no data write, no migration execution, no cleanup or
delete, no DSN or credential in output, and **no production row value in output** — aggregates
return counts only. The tool fails closed without an explicit read-only affirmation. See
[`PRODUCTION_MYSQL_COLLATION_VERIFICATION.md`](PRODUCTION_MYSQL_COLLATION_VERIFICATION.md).

---

## Phase 44 — identity comparisons are now explicit in source

The governed columns that audit trails depend on — `owner_id`, `client_id`, `engagement_id`,
`idempotency_key`, and the fingerprints — now pin a deterministic collation in the models and in
migration `013`, so their comparison semantics no longer depend on a server default.

This holds in source control. It becomes true of the audit trail itself only once migration `013`
has been executed against production and `make production-mysql-collation-verify` confirms it.

## Phase 49 — database credentials are separated by role, in source

Access control at the application layer means little if every process connects as the same database
user. Three roles now read three distinct environment variables, and the code paths that read them
do not overlap:

| Variable | Read by | Credential should hold |
| --- | --- | --- |
| `PEAK_RUNTIME_DATABASE_URL` | `peak/db/session.py` — application/runtime sessions | `SELECT` + `INSERT` only |
| `PEAK_DATABASE_URL` | `alembic/env.py` — Alembic / migration / bootstrap only | schema-change privileges |
| `PEAK_PRODUCTION_DB_URL` | `tools/production_mysql_collation_verify.py` — read-only verifier only | read-only, plus an explicit affirmation |

**Runtime never falls back to `PEAK_DATABASE_URL`.** If the runtime variable is unset, session
creation raises rather than borrowing the migration credential — a fallback would hand
schema-changing privileges to application code precisely when configuration went wrong. The error
names the missing variable and nothing else; no value is ever printed.

Phase 48 verified the runtime credential holds exactly `SELECT` + `INSERT` on the application
schema, with no `UPDATE`, `DELETE`, DDL, global grant, or `GRANT OPTION` — which is all the
create-only controlled writers require. The audit consequence is that a runtime process **cannot**
rewrite or remove an audit record even if application logic were compromised: append is the only
write it is permitted.

Local harnesses need none of these variables. Every controlled writer accepts an explicit
`session_factory=`, and `create_session_factory(url=...)` accepts an explicit URL — that is the
supported way to point a test at a temporary SQLite database.

## Phase 50 — runtime connectivity is provable, and provably harmless

The role separation in Phase 49 is only worth as much as the evidence that it holds in a live
environment. `tools/production_runtime_connectivity_gate.py` supplies that evidence on demand: it
connects through the application's own session path using `PEAK_RUNTIME_DATABASE_URL`, having first
removed `PEAK_DATABASE_URL` and `PEAK_PRODUCTION_DB_URL` from its own process — so a successful
connection *proves* the runtime credential stood alone.

For audit purposes the important property is what the gate **cannot** do. It issues exactly two
hard-coded statements, `SELECT 1` and `SHOW GRANTS FOR CURRENT_USER`, both identity-checked before
execution. Neither reads an application table: there is no `FROM` clause, no `COUNT(`, and no
application table name anywhere in the tool. Grants are parsed in memory and only booleans are
emitted — the user, host, and database names in each grant line are discarded. Failures report the
exception type only, because driver messages embed the connection string.

The gate re-asserts the Phase 48 posture: `SELECT` + `INSERT` and nothing more. That is the audit
guarantee behind append-only history — a runtime process cannot rewrite or delete an audit record,
because it holds neither `UPDATE` nor `DELETE`. Re-run the gate before any change to runtime
connectivity; grant posture can drift, and the check is cheap and non-mutating.

## Phase 51 — writing is a governance decision, gated separately from connectivity

Access control decides what a credential *could* do. It does not decide what *should* be written, or
by whose authority. Phase 51 separates those questions: connectivity and grants are settled by the
Phase 48–50 gates, while the decision to write anything at all is recorded by
`tools/production_writer_enablement_decision_gate.py` (`make writer-enablement-decision-gate`).

The current recorded decision is **no production write and no writer enablement**. The gate refuses
(exit 3) any request to record a write-authorizing path, and it contacts no database — it has no
engine, session, writer, or driver import, reads no environment variable, and issues no statement.

Two audit consequences are worth stating plainly:

**A passing runtime connectivity gate is not write permission.** It is evidence that the plumbing
and privileges are correct. Treating it as authorization would collapse a governance decision into a
technical one.

**Runtime holds no `DELETE`, so a synthetic record is durable.** Anything runtime writes — including
an administrative or smoke record — cannot be removed by runtime. Removal requires the migration
credential under separate approval. Any such record must therefore be assumed to remain permanently
in the governed audit history, which is exactly why the cleanup posture has to be decided *before*
the write rather than discovered after it.

Before any future write, re-run all three gates: the read-only verifier, the runtime connectivity
gate, and the decision gate. Each is cheap and non-mutating, and posture drifts.

## Phase 53 — the authorization anchor the audit trail hangs from

Phase 53 is **plan only**: no production write, no writer enablement, no synthetic smoke write, no
engagement record, no intake note. It answers what "wait for authorized engagement data" concretely
requires, by reading source.

**The anchor is a stored `Engagement` row with a populated `authorization_scope`.** Every controlled
writer loads that row at write time and requires the request's scope to equal the stored scope.
Identity matching — owner, client, engagement — is necessary but not sufficient; a scope mismatch is
denied even when every identity matches. This is what makes the audit trail meaningful: no governed
row can exist without a stored, scoped authority it descends from.

Two findings matter for access control:

**No controlled Engagement writer exists.** No writer targets `engagements`; the table sits in
`PROHIBITED_TABLES` alongside `clients` as an identity/root record, and no engagement-creating
action is on the allowlist. The runtime credential's `INSERT` is schema-wide, so what actually
prevents an unauthorized anchor from being created is the missing writer and the allowlist — a code
and governance block, not a privilege block. Both must stay intact.

**The planned first write needs no new privilege.** It requires `SELECT` (load the stored
engagement, check idempotency, read back) and `INSERT` (one row), which is exactly the Phase 48/50
runtime posture. It requires no `UPDATE` and no `DELETE`.

The Phase 51 no-write / no-enablement decision remains in force and the first production write
remains deferred. Synthetic smoke-writing stays disallowed unless separately approved, and — since
runtime holds no `DELETE` — any such record would be durable. See
[`PHASE53_AUTHORIZED_ENGAGEMENT_INTAKE_PATH.md`](PHASE53_AUTHORIZED_ENGAGEMENT_INTAKE_PATH.md).

## Phase 54 — creating the anchor the audit trail hangs from

Phase 53 named the stored `Engagement` row as the anchor every governed write descends from, and
noted that nothing could create one. Phase 54 adds that path — and **creates no engagement record,
no intake note, and no synthetic smoke record**.

For access control the important part is *how* the grant was made. `engagements` **stays** on
`PROHIBITED_TABLES`, because it is a root/identity record and the generic write path must never
reach it. The anchor writer instead travels a second, one-pair gate — exactly `engagements` /
`create_engagement_authorization_anchor` — checked pair-wise, so neither half opens anything on its
own. `clients` is listed as never writable and is refused by both gates.

The generic path's decisive check — request scope must equal the *stored* subject's scope — cannot
apply when the row being created *is* that subject. It is replaced, not weakened, by gates that are
checkable without a prior row: the exact pair, an absent subject, governed and bounded identity, a
canonical non-revoked scope, an allowed initial lifecycle and status, an idempotency key, and
value-marker screening on free text. All of them fail closed before any connection is opened.

Two audit properties worth stating:

**No overwrite path exists.** Re-creating an anchor id with a different governed definition is
denied, not applied. The stored anchor cannot be edited by this writer — it has no `UPDATE` — so an
anchor's authorization scope is fixed at creation as far as runtime is concerned.

**Runtime still holds no `DELETE`, so an anchor is durable.** Cleanup cannot be assumed: removing an
anchor would require the migration credential under separate approval. That is why the retention
posture belongs in the authorization decision for the first production anchor rather than after it.

The Phase 51 no-write / no-enablement decision remains in force and the first production anchor
creation remains separately approved future work. See
[`PHASE54_CONTROLLED_ENGAGEMENT_AUTHORIZATION_ANCHOR_WRITER.md`](PHASE54_CONTROLLED_ENGAGEMENT_AUTHORIZATION_ANCHOR_WRITER.md).

## Phase 55 — internal test engagements must be isolated by classification, not convention

Phase 55 defines a future category of governed record: **durable internal test / training
engagements**. It creates none, enables no writer, and contacts no database.

For access control the requirement is specific: **real clients must not be able to query, view,
list, infer, or join into internal test engagements** — and aggregates, counts, search results,
exports, and error messages all count as exposure. That isolation must be enforced by an explicit
classification predicate in whatever read path is eventually built, **not** by a `client_id` prefix,
a label, or any naming convention.

Two properties of the current design matter here:

**Isolation today is write-side only.** Option A scopes every controlled write to
`(owner_id, client_id, engagement_id)` and its stored anchor. **No client-facing read or query path
exists in the repository at all**, so nothing can leak today — but there is also no read-side
isolation to inherit, which is why it has to be designed alongside the classification columns.

**There is no governed client registry to reserve from.** `clients` is never writable by any
controlled path, so an internal-test `client_id` cannot be reserved in the database. Collision
avoidance with real client records must therefore be guaranteed by the creation packet and stated
explicitly before the first such record exists.

Capsule publication for these records is permitted only under a compound rule: the engagement must
be **explicitly classified as authorized for publication** *and* **contain no real client data** —
both, checked at publication time. Nothing is published today; publication remains deferred.

Runtime still holds no `DELETE`, so these records are durable — which suits their intent, and is
exactly why disposable synthetic smoke records remain disallowed. The Phase 51 no-write /
no-enablement decision remains in force. See
[`PHASE55_INTERNAL_TEST_ENGAGEMENT_CLASSIFICATION.md`](PHASE55_INTERNAL_TEST_ENGAGEMENT_CLASSIFICATION.md).

## Phase 56 — classification is recorded; read-side isolation is still to build

Internal test engagements are now classifiable on the row: `engagement_category=internal_test`
requires `real_client_data=false`, `client_accessible=false`, and a reserved `client_id` namespace
(`99999` or a reserved prefix). The reserved value is a **visible marker, not the whole control**,
and the rule is bidirectional — a real client engagement may not use that namespace, so the two
cannot bleed together.

Capsule publication requires **explicit authorization and no real client data**, checked together.
A real client engagement may not authorize publication here at all.

**The flag is the contract, not the enforcement.** No client-facing read path exists yet; whichever
one is built must filter on `client_accessible` / `engagement_category` explicitly. Runtime still
holds no `DELETE`, so these records are durable and cleanup is not assumed. **Phase 56 created no
records**, and the Phase 51 no-write / no-enablement decision remains in force. See
[`PHASE56_INTERNAL_TEST_ENGAGEMENT_SUPPORT.md`](PHASE56_INTERNAL_TEST_ENGAGEMENT_SUPPORT.md).

## Phase 57 — read-side isolation is now enforceable, not just recorded

The Phase 56 classification columns are now backed by a **read-side isolation primitive**. Future
real-client read paths must use it rather than filtering by hand.

**Exclusion is the default.** The client-facing mode admits only `real_client` +
`client_accessible` + `real_client_data`, and cannot be widened into internal test visibility by any
argument. Internal/admin reads must **explicitly opt in** to see internal test engagements, and an
unrecognised mode fails closed rather than falling open.

**`client_id=99999` is not sufficient by itself.** A reserved id is excluded from client-facing
reads as defence in depth, but the control is the classification columns: an internal test record
with an ordinary `client_id` is excluded too, and narrowing a query by `client_id` cannot resurrect
an excluded row.

**Publication eligibility is separate from client visibility** — the compound rule (`internal_test`
+ no real client data + not client-accessible + explicitly authorized) describes a record that is
publishable *and* invisible to every client.

The primitive opens no connection, writes nothing, and invokes no writer. **Phase 57 created no
records**; migration 014 was applied to production later, in **Phase 58** (see below). See
[`PHASE57_INTERNAL_TEST_READ_ISOLATION.md`](PHASE57_INTERNAL_TEST_READ_ISOLATION.md).

## Phase 58 — migration 014 applied to production, under three authorized actions

**Migration `014_engagement_classification` was applied to production in Phase 58.** Production
schema now supports the Engagement classification fields (`engagement_category`, `real_client_data`,
`client_accessible`, `capsule_publication_authorized`).

Exactly three production actions were authorized, each with a single-purpose credential:

| # | Action | Credential | Mutates production |
| --- | --- | --- | --- |
| 1 | pre-migration read-only verification | read-only verifier | no |
| 2 | `alembic upgrade 014_engagement_classification` | production migration | schema + `alembic_version` only |
| 3 | post-migration read-only verification | read-only verifier | no |

**The production verifier's expected head is now `014`, not `013`.** The pin in
[`tools/production_mysql_collation_verify.py`](../tools/production_mysql_collation_verify.py) tracks
the live production head, so it moves only when a migration has genuinely been applied to
production. `engagement_category` is classified `governed_scope`, so it is covered by the same
deterministic-collation requirement as every other governed identifier; the production governed
column count moves from 211 to 212 and all 11 idempotency boundaries stay case-sensitive.

**No production application records were created, read, updated, or deleted.** Verification read
`INFORMATION_SCHEMA` metadata and `alembic_version` only — no app table rows, counts, or probes; the
collision probe stayed opt-in and unrun. **No writer was invoked**, **no runtime credential was
used**, no downgrade or manual `ALTER` was performed, and **no credential, DSN, or environment value
was printed or committed** — env files were sourced inside subshells only.

**No internal test engagement was created.** The first internal test engagement anchor remains
**separately approved** future work; 014 makes the classification representable, not authorized. The
read-side isolation primitive exists, but **future client-facing paths must actually use it**.
Properly gated production test records are allowed later — only with
`engagement_category=internal_test`, `real_client_data=false`, `client_accessible=false`, and a
reserved test namespace/value, and only as durable internal/admin records whose cleanup posture is
decided before the write. See
[`PHASE58_PRODUCTION_MIGRATION_014_VERIFICATION.md`](PHASE58_PRODUCTION_MIGRATION_014_VERIFICATION.md).

## Phase 59 — the first production application record, under one authorized write

**One durable `internal_test` engagement anchor was created in production**, through the existing
Phase 54/56 controlled writer. It is the first application record Peak has written to production.

| Credential | Used for | Mutates production |
| --- | --- | --- |
| read-only verifier | schema posture, before and after | no |
| runtime | connectivity gate (metadata + grants only) | no |
| runtime | **exactly one** controlled writer invocation | one `engagements` row |
| migration | **not used** | — |

The **runtime credential was used only through the controlled writer path** — resolved by
`create_session_factory`, which reads `PEAK_RUNTIME_DATABASE_URL` and no other variable. The
connectivity gate confirmed `SELECT` + `INSERT` with no excess grants, no global privileges, and no
`GRANT OPTION`. **Runtime DELETE is unavailable**, so this record cannot be removed by the
application and deletion is not expected — cleanup posture was decided before the write.

**No real client record was created** (`clients` remains never-writable), **no intake note**, no
downstream record, and no capsule. No `UPDATE`, `DELETE`, manual SQL, cleanup, or stamp was issued,
and no app table was scanned, counted, or probed — the only reads were the writer's own
single-primary-key existence check and the read-back of the row it created. No credential, DSN,
environment value, or raw grant was printed or committed.

The record holds **no real client data** and is **not client-accessible**; it uses the reserved
internal/test namespace as a visible marker on top of those controls, never instead of them. It is
publication-*eligible* only because the compound rule is satisfied; nothing was published.

**Future real-client read paths must use Phase 57 read isolation.** A query that bypasses
`apply_read_isolation` is not protected by it, and an internal test row now genuinely exists in
production. Distinguish the three postures: the approved **durable internal_test anchor** is now
created; a **disposable production smoke record** is still disallowed; unauthorized **writer
enablement** is still disallowed. See
[`PHASE59_FIRST_INTERNAL_TEST_ENGAGEMENT_ANCHOR.md`](PHASE59_FIRST_INTERNAL_TEST_ENGAGEMENT_ANCHOR.md).

## Phase 60 — the first intake note, authorized by the stored engagement

**One durable `internal_test` intake note was created in production**, tied to `internal_test_001` /
`99999` / `internal_peak_only`, through the unchanged Phase 34 controlled writer. It is the second
production application record, and the first one whose authorization came from a *stored* row.

**Authorization is the stored engagement, not the caller's claim.** At write time the writer loaded
the `Engagement` anchor created in Phase 59 and required
`request.authorization_scope == engagement.authorization_scope`. Identity matching (owner, client,
engagement) is necessary but explicitly not sufficient. Without that stored anchor the write would
have been denied as `missing_subject` — which is exactly why Phase 59 had to come first.

| Credential | Used for | Mutates production |
| --- | --- | --- |
| read-only verifier | schema posture, before and after | no |
| runtime | connectivity gate (metadata + grants only) | no |
| runtime | **exactly one** controlled intake-note writer invocation | one `intake_note_records` row |
| migration | **not used** | — |

The record is review-gated and non-final and is **not client-facing**. It contains **no real client
data** and is durable internal/admin data, **not disposable smoke**. **No Client record, no
additional Engagement record, no downstream record, and no capsule** were created. No `UPDATE`,
`DELETE`, manual SQL, cleanup, or stamp was issued, and no app table was scanned, counted, or probed
beyond the writer's own stored-engagement load and idempotency lookup.

**Intake prose never enters source control.** The writer's standing rule is that note bodies are
acceptable only in the managed DB; the operator utility therefore reads the body from outside the
repository and reports only its length and SHA-256, and receipts never echo note content. Intake
questions are grounded in
[`PEAK_INTAKE_QUESTION_TAXONOMY_V0.md`](PEAK_INTAKE_QUESTION_TAXONOMY_V0.md); future client-facing
forms should be generated from the taxonomy, not guessed, and future GeoSites intake should
replicate the same derive-from-deliverables approach. See
[`PHASE60_FIRST_INTERNAL_TEST_INTAKE_NOTE.md`](PHASE60_FIRST_INTERNAL_TEST_INTAKE_NOTE.md).

## Phase 61 — reviewing a stored record, under a stored anchor

**One internal review decision record was created** in production for the Phase 60 intake note
`intn_b8b86b8c196c4595`, through the unchanged Phase 22 `review_records` writer. It is the third
production application record, and the first whose *target* is another stored record.

Two separate identities are involved and the writer keeps them apart: the **authorization anchor**
is the `internal_test_001` engagement (`request.subject`, which must be an `engagement`), and the
**reviewed target** is the intake note (`draft.subject_record_id`, stored as `target_id`). As with
Phase 60, authorization came from the stored engagement — the writer loaded it and required the
request scope to match the stored `internal_peak_only` scope.

| Credential | Used for | Mutates production |
| --- | --- | --- |
| read-only verifier | schema posture, before and after | no |
| runtime | connectivity gate (metadata + grants only) | no |
| runtime | **exactly one** controlled review writer invocation | one `review_records` row |
| migration | **not used** | — |

The decision is `approve_internal` — the writer's vocabulary for internal reliance only; it refuses
`client_facing_approve`, `verify_financial_impact`, and `publish_capsule` outright. It is
non-authoritative, non-client-facing, and authorizes **source/evidence collection, not report or
capsule publication**. The intake note **remains internal-only and non-client-facing**.

**No Client record, no additional Engagement, no second intake note, and no
source/evidence/report/capsule record** were created. No `UPDATE`, `DELETE`, manual SQL, cleanup, or
stamp was issued, and no app table was scanned, counted, or probed beyond the writer's own
stored-engagement load and idempotency lookup. **The findings carry no note prose** — they are
category labels and gap descriptors derived from the V0 taxonomy, and the note body was never read
by this phase's tools. See
[`PHASE61_INTERNAL_TEST_INTAKE_REVIEW_DECISION.md`](PHASE61_INTERNAL_TEST_INTAKE_REVIEW_DECISION.md).

## Phase 62 — planning a collection step without touching production

Phase 62 is **planning-only**. No credential of any role was used, no connection was opened, no SQL
was issued, no writer was invoked, and **no production record was created**.

| Credential | Used for | Mutates production |
| --- | --- | --- |
| read-only verifier | **not used** | — |
| runtime | **not used** | — |
| migration | **not used** | — |

The Phase 61 review decision now feeds a **concrete source/evidence request plan**: ten prioritized
source/evidence requests, each mapped to Intake Taxonomy V0 categories and to the downstream
deliverable it supports. The plan is internal/admin only, covers no real client data, and produces
no client-facing output.

**Phase 63 should create the first internal_test source ingestion record** — through the unchanged
Phase 24 writer, `source_ingestion_records` / `create_source_ingestion_record`, anchored on the
stored `internal_test_001` engagement — **if the inspected writer contract supports it**, meaning a
real internal_test artifact exists at write time. If none does, Phase 63 must defer rather than
fabricate a packet reference. **Evidence and source collection precede analysis, report drafting,
and capsule publication**, both of which remain unauthorized. See
[`PHASE62_INTERNAL_TEST_SOURCE_EVIDENCE_REQUEST_PLAN.md`](PHASE62_INTERNAL_TEST_SOURCE_EVIDENCE_REQUEST_PLAN.md).

## Phase 63 — registering an artifact, under a stored anchor

Phase 63 writes **exactly one** `source_ingestion_records` row through the unchanged Phase 24
controlled writer, under the stored `internal_test_001` engagement anchor.

| Credential | Used for | Mutates production |
| --- | --- | --- |
| read-only verifier | schema posture, before and after | no |
| runtime | connectivity gate (metadata + grants only) | no |
| runtime | **exactly one** controlled source-ingestion writer invocation | one `source_ingestion_records` row |
| migration | **not used** | — |

The read-only verifier reported `verified_safe_no_remediation_required` both before and after the
write (head `014`, 212 governed columns deterministic, `data_write_made=False`). The runtime gate
reported required grants present, no excess grants, no global privileges, no `GRANT OPTION`, and
`app_table_read_made=False`.

**Only metadata reached the database** — packet reference, schema, source type, a logical
`internal-test-artifact://` location reference, and a SHA-256 hash. The artifact body lives outside
the repository, is never committed, and is opened only in binary to compute its length and hash;
no filesystem path is stored on the row.

**No evidence reference was created** — evidence characterization still follows source ingestion.
No Client record, no additional Engagement, no intake note, no review record, and no
report/capsule/client-facing output were created. No `UPDATE`, `DELETE`, manual SQL, cleanup, or
stamp was issued, and no app table was scanned, counted, or probed beyond the writer's own
stored-engagement load and idempotency lookup. See
[`PHASE63_FIRST_INTERNAL_TEST_SOURCE_INGESTION.md`](PHASE63_FIRST_INTERNAL_TEST_SOURCE_INGESTION.md).

## Phase 64 — planning the next collection batch without touching production

Phase 64 is **planning-only**. No credential of any role was used, no connection was opened, no SQL
was issued, no writer was invoked, and **no production record was created**.

| Credential | Used for | Mutates production |
| --- | --- | --- |
| read-only verifier | **not used** | — |
| runtime | **not used** | — |
| migration | **not used** | — |

**Phase 63 registered R8**; **Phase 64 defines the R1–R7 artifact collection** that follows it.
**Artifact bodies remain outside the repository** and never enter the database — source ingestion
persists metadata only: packet reference, schema, source type, a logical
`internal-test-artifact://` location reference, and a SHA-256 hash.

**Phase 65 should create the external artifact(s) and register `source_ingestion_records`, not
`evidence_references` yet.** Collection does not require the R8 map to be reviewed; *attribution*
does, because R8's authority precedence rule is still provisional and unconfirmed — so reliability
may not be asserted until it is settled. **Capsule publication remains unauthorized despite the live
AgentNet resolver**, which is a real production target and therefore a reason to keep the gate shut
rather than to relax it. See
[`PHASE64_INTERNAL_TEST_R1_R7_SOURCE_ARTIFACT_COLLECTION_PLAN.md`](PHASE64_INTERNAL_TEST_R1_R7_SOURCE_ARTIFACT_COLLECTION_PLAN.md).

## Phase 65 — two artifact registrations, under the same stored anchor

Phase 65 writes **exactly two** `source_ingestion_records` rows through the unchanged Phase 24
writer: **R2 (the SKU/item master export) first, then R1 (the current inventory export by SKU and
location)**. Both are anchored to the stored `internal_test_001` engagement, and at write time the
writer loads that stored `Engagement` row and requires `request.authorization_scope ==
engagement.authorization_scope` — identity matching is necessary but not sufficient.

| Credential | Used for | Mutates production |
| --- | --- | --- |
| read-only verifier | pre-write and post-write schema/collation verification (no app rows read) | no |
| runtime | the two `INSERT`s, via the writer only (`SELECT` + `INSERT` grants only) | yes — two rows |
| migration | **not used** | — |

**Only metadata was persisted** — packet reference, schema name and version, source type, a logical
`internal-test-artifact://phase65/…` location reference, and a SHA-256 hash computed over the exact
artifact bytes. **The artifact bodies live outside the repository**, were never decoded, printed,
logged, or committed, and never entered the database. No filesystem path reached a row.

**R1's location dimension is provisional** and is recorded as such on the row: the R8 location/bin
model is unconfirmed, so any future evidence from R1 must carry degraded reliability for
location-attributed claims. **No evidence reference was created** — R8 review remains a precondition
for attribution, not for collection.

Each record carries its own idempotency key. An exact replay returns the existing row unmodified; a
changed hash under the same key is refused as an `idempotency_conflict`, never an overwrite. No
`UPDATE`, `DELETE`, manual SQL, cleanup, or `alembic stamp` was issued, and no app table was
scanned, counted, or probed beyond the writer's own stored-engagement load and idempotency lookup.
**R3–R7 remain deferred**, and **AgentNet resolver publication remains unauthorized** despite the
live public resolver. See
[`PHASE65_R1_R2_INTERNAL_TEST_SOURCE_INGESTION.md`](PHASE65_R1_R2_INTERNAL_TEST_SOURCE_INGESTION.md).

## Phase 66 — reviewing a registered source, under the same stored anchor

Phase 66 writes **exactly one** `review_records` row through the unchanged Phase 22 review writer,
recording the internal review decision on the **R2** source ingestion record
(`ing_884c94df03c34908`). The reviewed target is stored in `target_id` with
`subject_record_type='source_ingestion_record'`; the **authorization anchor stays the
`internal_test_001` engagement**, and at write time the writer loads that stored `Engagement` row
and requires `request.authorization_scope == engagement.authorization_scope`.

| Credential | Used for | Mutates production |
| --- | --- | --- |
| read-only verifier | pre-write and post-write schema/collation verification (no app rows read) | no |
| runtime | the one `INSERT`, via the writer only (`SELECT` + `INSERT` grants only) | yes — one row |
| migration | **not used** | — |

**The decision is `approve_internal`, non-authoritative.** It authorizes one narrow next step — a
future `evidence_reference` about **item-master source availability and data readiness** — and
nothing wider. **No evidence reference was created.** R1 stays provisional, **R8 stays provisional**
(`needs_review` / `draft` / `authoritative=false`), R3–R7 stay deferred, and report drafting,
capsule candidacy, client-facing output, and **AgentNet resolver publication remain unauthorized**
despite the live public resolver.

**No artifact body was read.** The Phase 66 operator opens no file and computes no hash; the stored
findings are sanitized structural counts and named gaps, never artifact text or row values. No
`UPDATE`, `DELETE`, manual SQL, cleanup, or `alembic stamp` was issued, and no app table was
scanned, counted, or probed beyond the writer's own stored-engagement load and idempotency lookup.
See
[`PHASE66_INTERNAL_TEST_SOURCE_INGESTION_REVIEW_DECISION.md`](PHASE66_INTERNAL_TEST_SOURCE_INGESTION_REVIEW_DECISION.md).

## Phase 67 — the first evidence reference, under the same stored anchor

Phase 67 writes **exactly one** `evidence_references` row (`evid_56437d9b9c764560`) through the
unchanged Phase 21 evidence writer, for the Phase 66-approved **R2** source ingestion record
(`ing_884c94df03c34908`). The
**authorization anchor stays the `internal_test_001` engagement** — the writer requires the subject
to be an `engagement`, loads that stored `Engagement` row at write time, and requires
`request.authorization_scope == engagement.authorization_scope`. The evidenced source is carried on
`source_reference_id` (the registered packet) and `source_location` (a *logical* in-Peak locator,
never a filesystem path); the supporting review `rev_bf7f18a13d8f461c` is named in the row's
descriptive text, because the table has no typed related-object column.

| Credential | Used for | Mutates production |
| --- | --- | --- |
| read-only verifier | pre-write and post-write schema/collation verification (no app rows read) | no |
| runtime | the one `INSERT`, via the writer only (`SELECT` + `INSERT` grants only) | yes — one row |
| migration | **not used** | — |

**The evidence scope is item-master source availability and data readiness only**, and **no
inventory accuracy conclusion was made**. The row is `needs_review` / `draft` / `active`, with
`reliability='low'` and `evidence_status='collected'`; `evidence_references` has **no
`authoritative` column**, and the writer refuses any draft claiming `authoritative`,
`client_facing_approved`, or `capsule_candidate_ready`. R1 stays provisional pending R9, **R8 stays
provisional** (`needs_review` / `draft` / `authoritative=false`), R3–R7 stay deferred, and report
drafting, capsule candidacy, client-facing output, and **AgentNet resolver publication remain
unauthorized** despite the live public resolver.

**No artifact body was read.** The Phase 67 operator opens no file and computes no hash; the stored
text is sanitized structural counts, posture flags, named gaps, and record ids — never artifact
text or row values. No `UPDATE`, `DELETE`, manual SQL, cleanup, or `alembic stamp` was issued, and
no app table was scanned, counted, or probed beyond the writer's own stored-engagement load and
idempotency lookup. See
[`PHASE67_FIRST_INTERNAL_TEST_EVIDENCE_REFERENCE.md`](PHASE67_FIRST_INTERNAL_TEST_EVIDENCE_REFERENCE.md).

## Phase 68 — reviewing an evidence reference, under the same stored anchor

Phase 68 writes **exactly one** `review_records` row (`rev_de2b6e73f6c94c67`) through the
unchanged Phase 22 review writer, recording the internal review decision on the Phase 67 **R2 evidence reference**
(`evid_56437d9b9c764560`). The reviewed target is stored in `target_id` with
`subject_record_type='evidence_reference'`; the **authorization anchor stays the
`internal_test_001` engagement**, and at write time the writer loads that stored `Engagement` row
and requires `request.authorization_scope == engagement.authorization_scope`.

| Credential | Used for | Mutates production |
| --- | --- | --- |
| read-only verifier | pre-write and post-write schema/collation verification (no app rows read) | no |
| runtime | the one `INSERT`, via the writer only (`SELECT` + `INSERT` grants only) | yes — one row |
| migration | **not used** | — |

**The decision is `approve_internal`, non-authoritative.** It authorizes one narrow next step — a
future **internal assessment finding** about item-master source availability and data readiness —
and nothing wider. **The evidence remains low confidence and non-authoritative**, and **no
inventory accuracy conclusion was made**. **The reviewed evidence row is not modified**: a review
records a decision about a target, and the writer has no `UPDATE` path. R1 stays provisional pending
**R9**, **R8 stays provisional** (`needs_review` / `draft` / `authoritative=false`), R3–R7 stay
deferred, and report drafting, capsule publication, client-facing output, and **AgentNet resolver
publication remain unauthorized** despite the live public resolver.

**No artifact body was read.** The Phase 68 operator opens no file and computes no hash; the stored
findings are sanitized structural counts and named gaps, never artifact text or row values. No
`UPDATE`, `DELETE`, manual SQL, cleanup, or `alembic stamp` was issued, and no app table was
scanned, counted, or probed beyond the writer's own stored-engagement load and idempotency lookup.
See
[`PHASE68_R2_EVIDENCE_REFERENCE_REVIEW_DECISION.md`](PHASE68_R2_EVIDENCE_REFERENCE_REVIEW_DECISION.md).

## Phase 69 — collecting the R9 location model, under the same stored anchor

Phase 69 writes **exactly one** `source_ingestion_records` row (`ing_64b2e2648ac1402b`) through the
unchanged **Phase 24** source ingestion writer, registering the internal test **R9 location/bin
naming model** artifact. Same stored anchor as every phase since 59: `internal_test_001` / `99999` /
`peak_internal_admin` / `internal_peak_only`, loaded from the database at write time and compared
against the request scope. Head stays `014` — no migration, no model, no writer, no allowlist pair.

| credential | what it did in Phase 69 | wrote? |
| --- | --- | --- |
| read-only | pre-write and post-write schema/collation verify only; no app rows read | no |
| runtime | the one `INSERT`, via the writer only (`SELECT` + `INSERT` grants only) | yes — one row |
| migration | **not used** | — |

**R9 is a location/bin naming model artifact**, and its **body lives outside the repository**. Only
**metadata, the `packet_hash`, and the logical location reference**
`internal-test-artifact://phase69/r9-location-bin-naming-model-v1` were persisted — never a
filesystem path, an export row, an item or SKU value, a quantity, or a location identifier, bin
code, aisle, rack, warehouse, or site name. The artifact is a field-level and concept-level
description containing no instance data at all.

**R9 was collected to unblock a future R1 location-dimension review.** It **does not validate
inventory quantities**, is not an inventory accuracy finding, and **does not make R1 evidence-ready
by itself** — R1's location dimension remains provisional, and **R9 must be reviewed before use in
evidence references**. It landed `needs_review` / `draft` / `active` with `authoritative=false`.

**No evidence reference, no review record, no report, no capsule, no client-facing output, and no
AgentNet publication record was created.** **R8 remains provisional** (`needs_review` / `draft` /
`authoritative=false`, precedence unconfirmed), **R3–R7 remain deferred**, and the AgentNet public
resolver is live but **publication remains gated and unauthorized**.

**No artifact body was printed, committed, or stored.** The operator opens the file in binary solely
to compute its length and SHA-256; the bytes are never decoded or logged. No `UPDATE`, `DELETE`,
manual SQL, cleanup, or `alembic stamp` was issued, and no app table was scanned, counted, or probed
beyond the writer's own stored-engagement load and idempotency lookup. See
[`PHASE69_R9_LOCATION_BIN_MODEL_SOURCE_INGESTION.md`](PHASE69_R9_LOCATION_BIN_MODEL_SOURCE_INGESTION.md).

## Phase 70 — reviewing the R9 location model, under the same stored anchor

Phase 70 writes **exactly one** `review_records` row (`rev_3ecc0891f4fe48ce`) through the unchanged
**Phase 22** review writer, recording the internal review decision on the Phase 69 **R9 source
ingestion record** (`ing_64b2e2648ac1402b`, the location/bin naming model). Same stored anchor as
every phase since 59: `internal_test_001` / `99999` / `peak_internal_admin` / `internal_peak_only`,
loaded from the database at write time and compared against the request scope. Head stays `014` —
no migration, no model, no writer, no allowlist pair.

| credential | what it did in Phase 70 | wrote? |
| --- | --- | --- |
| read-only | pre-write and post-write schema/collation verify only; no app rows read | no |
| runtime | the one `INSERT`, via the writer only (`SELECT` + `INSERT` grants only) | yes — one row |
| migration | **not used** | — |

**The decision is `approve_internal`, non-authoritative.** It approves R9 **only for future evidence
work about R1 location-dimension readiness** and nothing wider. `authoritative` was left false
deliberately: R9 answers none of its own questions, its ownership is undetermined, and R8 is
unreviewed.

**No evidence reference was created.** **R1's location dimension remains provisional** — this
decision does not lift that marking. **R9 does not validate inventory quantities** (it holds no
instance data at all), **does not resolve R8 authority precedence**, and **does not resolve R5 WMS
scope uncertainty**. **R3–R7 stay deferred**, and report drafting, capsule publication,
client-facing output, and **AgentNet resolver publication remain unauthorized** despite the live
public resolver.

**The reviewed R9 row is not modified**: a review records a decision about a target, and the writer
has no `UPDATE` path — R9 still reads `needs_review` / `draft`.

**No artifact body was read.** The Phase 70 operator opens no file and computes no hash; the stored
findings are sanitized structural counts, posture flags, and named gaps, never artifact text, item
or SKU values, quantities, or location identifiers. No `UPDATE`, `DELETE`, manual SQL, cleanup, or
`alembic stamp` was issued, and no app table was scanned, counted, or probed beyond the writer's own
stored-engagement load and idempotency lookup. See
[`PHASE70_R9_SOURCE_INGESTION_REVIEW_DECISION.md`](PHASE70_R9_SOURCE_INGESTION_REVIEW_DECISION.md).

## Phase 71 — planning-only; no credential was used at all

Phase 71 is a **planning phase**. It contacted **no production database**, sourced **no environment
file**, used **no credential** — read-only, runtime, or migration — invoked **no writer**, and
created **no production record of any kind**. Head stays `014`; no migration, model, writer,
allowlist pair, or operator utility was added.

| credential | what it did in Phase 71 | wrote? |
| --- | --- | --- |
| read-only | **not used** | — |
| runtime | **not used** | — |
| migration | **not used** | — |

**No `evidence_reference`, `review_record`, or `source_ingestion_record` was created**, and no
report, capsule, client-facing output, or AgentNet/resolver publication was produced or authorized.

**The finding is a sequencing one.** R1 cannot yet support a location-dimension evidence reference
because R9 **defines the questions that must be answered but does not answer them**. **R1 remains
provisional**; **R9 is reviewed but non-authoritative and remains a question set, not an answered
model**; R8 authority precedence and R5 WMS scope remain unresolved; R3–R7 remain deferred. The next
useful production step is likely an **R10 measured location model answer set source ingestion**
(Phase 72), followed by its review — each separately approved.

**No artifact body was read into the repository.** Both registered artifacts were re-read for
**structure only** — field names, roles, and counts — with no body printed, copied, or committed and
no location, bin, aisle, rack, warehouse, or site values read or recorded. See
[`PHASE71_R1_R9_EVIDENCE_READINESS_PLAN.md`](PHASE71_R1_R9_EVIDENCE_READINESS_PLAN.md).

## Phase 72 — collecting the R10 answer set, under the same stored anchor

Phase 72 writes **exactly one** `source_ingestion_records` row (`ing_b26d137a0a334ee9`) through the
unchanged **Phase 24** source ingestion writer, registering the internal test **R10 measured
location model answer set**. Same stored anchor as every phase since 59: `internal_test_001` /
`99999` / `peak_internal_admin` / `internal_peak_only`, loaded from the database at write time and
compared against the request scope. Head stays `014` — no migration, no model, no writer, no
allowlist pair.

| credential | what it did in Phase 72 | wrote? |
| --- | --- | --- |
| read-only | pre-write and post-write schema/collation verify only; no app rows read | no |
| runtime | the one `INSERT`, via the writer only (`SELECT` + `INSERT` grants only) | yes — one row |
| migration | **not used** | — |

**R10 is a measured location model answer set responding to R9's question set**, and its **body
lives outside the repository**. Only **metadata, the `packet_hash`, and the logical location
reference** `internal-test-artifact://phase72/r10-location-model-answer-set-v1` were persisted —
never a filesystem path, an export row, an item or SKU value, a quantity, or a location identifier,
bin code, aisle, rack, warehouse, or site name.

**R10 includes negative and unknown answers.** All 15 Phase 71 checklist items are present, none was
dropped or softened, and 11 of 15 resolve to a negative, unknown, or blocked state. The headline
finding is that **R1's location dimension is not currently readable**.

**R10 remains `needs_review` / `draft` / `authoritative=false` and must be reviewed before use in
evidence references.** It **does not validate inventory quantities**, **does not lift R1's
provisional location marking**, **does not resolve R8 authority precedence** (items recorded
`blocked_by_r8`), and **does not resolve R5 WMS scope** (items recorded `blocked_by_r5`).

**No evidence reference, no review record, no report, no capsule, no client-facing output, and no
AgentNet publication record was created.** **R1 remains provisional**, **R3–R7 remain deferred**, and
the AgentNet public resolver is live but **publication remains gated and unauthorized**.

**No artifact body was printed, committed, or stored.** The operator opens the file in binary solely
to compute its length and SHA-256; the bytes are never decoded or logged. No `UPDATE`, `DELETE`,
manual SQL, cleanup, or `alembic stamp` was issued, and no app table was scanned, counted, or probed
beyond the writer's own stored-engagement load and idempotency lookup. See
[`PHASE72_R10_LOCATION_MODEL_ANSWER_SET_SOURCE_INGESTION.md`](PHASE72_R10_LOCATION_MODEL_ANSWER_SET_SOURCE_INGESTION.md).

## Phase 73 — two writes: the R10 review and the first negative finding

Phase 73 writes **exactly two** rows under the same stored anchor (`internal_test_001` / `99999` /
`peak_internal_admin` / `internal_peak_only`): one `review_records` row (`rev_9b6b0a67bae54a51`)
through the unchanged **Phase 22** writer, reviewing the R10 source ingestion
(`ing_b26d137a0a334ee9`), and one `evidence_references` row (`evid_f26c5f8fc0aa44d4`) through the
unchanged **Phase 21** writer. Head stays `014` — **no migration, model, writer, allowlist pair,
operator utility, or harness was added**. Both writes were driven by a temporary executor held
outside the repository and never committed.

| credential | what it did in Phase 73 | wrote? |
| --- | --- | --- |
| read-only | pre-write and post-write schema/collation verify only; no app rows read | no |
| runtime | the two `INSERT`s, via the writers only (`SELECT` + `INSERT` grants only) | yes — two rows |
| migration | **not used** | — |

**The review is `approve_internal`, non-authoritative**, approving R10 only for evidence about R1
location-dimension data readiness. **The evidence finding is unfavourable**: under thresholds fixed
in advance, **R1's location dimension is not currently readable and not reliable enough** to carry
location-attributed evidence. Write 2 proceeded only because write 1 was created; both were newly
created, not replays.

**This is a data-readiness and reliability finding, not an inventory accuracy finding.** No
inventory accuracy conclusion was made. **R1 remains provisional**, **R8 authority precedence and R5
WMS scope remain unresolved**, **R3–R7 remain deferred**, and report drafting, capsule publication,
client-facing output, and **AgentNet resolver publication remain unauthorized** despite the live
public resolver.

**No artifact body was read, printed, committed, or stored.** The stored records carry answer-state
counts, threshold results, posture flags, and record ids only. The reviewed R10 row and the R1/R9
records were **not modified** — neither writer has an `UPDATE` path. No `UPDATE`, `DELETE`, manual
SQL, cleanup, or `alembic stamp` was issued, and no app table was scanned, counted, or probed beyond
the writers' own stored-engagement loads and idempotency lookups. See
[`PHASE73_R10_REVIEW_LOCATION_READINESS_EVIDENCE.md`](PHASE73_R10_REVIEW_LOCATION_READINESS_EVIDENCE.md).

---

## Phase 74 — two writes: the evidence review and the minimal internal assessment outline

Phase 74 writes **exactly two** rows under the same stored anchor (`internal_test_001` / `99999` /
`peak_internal_admin` / `internal_peak_only`): one `review_records` row (`rev_d94d4711ac12420b`)
through the unchanged **Phase 22** writer, reviewing the Phase 73 location-readiness evidence
reference (`evid_f26c5f8fc0aa44d4`), and one `internal_assessment_report_drafts` row
(`iard_50814a78a44243c2`) through the unchanged **Phase 37** writer, planned by the DB-free
**Phase 36** planner. Head stays `014` — **no migration, model, writer, allowlist pair, operator
utility, or harness was added**. Both writes were driven by a temporary executor held outside the
repository and never committed.

| credential | what it did in Phase 74 | wrote? |
| --- | --- | --- |
| read-only | pre-write and post-write schema/collation verify only; no app rows read | no |
| runtime | the two `INSERT`s, via the writers only (`SELECT` + `INSERT` grants only) | yes — two rows |
| migration | **not used** | — |

**The review is `approve_internal`, non-authoritative**, approving the location-readiness evidence
only for one minimal internal assessment finding / report outline. **The assessment outline is
`plan_persisted` / `needs_review` / `draft`, `audience=internal`**, with every approval, financial,
capsule, publication, and execution flag `false` and `requires_human_review=true`. Write 2 proceeded
only because write 1 was created; both were newly created, not replays.

**The assessment finding: R1's location dimension is not currently readable or reliable enough to
carry location-attributed evidence under thresholds fixed in advance. This is a data-readiness and
reliability finding, not an inventory accuracy finding**, and downstream reports must not reframe it
as one — an instruction recorded on the review row's `warnings` as well as in the docs. **R1 remains
provisional**, **R8 authority precedence and R5 WMS scope remain unresolved**, **R3–R7 remain
deferred**, and report finalization, capsule publication, client-facing output, and **AgentNet
resolver publication remain unauthorized** despite the live public resolver. No capsule candidate was
created: `future_capsule_candidate_items_json` names a *future* gate, and the row's
`capsule_candidate_ready` / `publication_allowed` are `false`.

**No artifact body was read, printed, committed, or stored.** The stored records carry record ids,
readiness states, section metadata, posture flags, and short safe labels only. The reviewed evidence
reference and every upstream record were **not modified** — neither writer has an `UPDATE` path. No
`UPDATE`, `DELETE`, manual SQL, cleanup, or `alembic stamp` was issued, and no app table was
scanned, counted, or probed beyond the writers' own stored-engagement loads and idempotency lookups.
See
[`PHASE74_LOCATION_READINESS_INTERNAL_ASSESSMENT.md`](PHASE74_LOCATION_READINESS_INTERNAL_ASSESSMENT.md).

---

## Phase 75 — no production access, no writes

Phase 75 **contacted no production database**. No environment file was sourced, no connection was
opened, no writer was invoked, and **no row of any kind was created** — no `review_bundle_records`,
no `internal_assessment_report_drafts`, no `review_records`, no source ingestion, evidence reference,
Client, Engagement, intake note, capsule, report, client-facing output, or AgentNet publication.

| credential | what it did in Phase 75 | wrote? |
| --- | --- | --- |
| read-only | **not used** — the pre-write verifier gates writes, and no write was attempted | no |
| runtime | **not used** | no |
| migration | **not used** | — |

The phase's preferred path was to create one `review_bundle_records` row and one revised outline. It
was **declined on honesty grounds**: a review bundle is a Phase 29-derived inbox item that records
material as *queued for* human review (`ready_for_human_review`, `approval_allowed=false`,
`requires_human_review=true`), not as reviewed — so it cannot honestly satisfy a
`blocked_no_review_support` check, it has **no field or column for a review record id** (the model
excludes "a final review decision" by design), and this chain's material has in fact already been
reviewed at `rev_9b6b0a67bae54a51` and `rev_d94d4711ac12420b`. **No substitute `review_records` row
was created to appear to progress.**

**No `UPDATE`, `DELETE`, manual SQL, cleanup, or `alembic stamp` was issued**, no app table was
scanned, counted, or probed, no schema was changed, and no migration was run. Head stays `014` and
**no new infrastructure was added**. The Phase 74 outline is unmodified. The finding remains
**data-readiness / reliability only and must not be restated as inventory accuracy**; **R1 remains
provisional**, **R8 and R5 remain unresolved**, **R3–R7 remain deferred**; and report finalization,
capsule publication, client-facing output, and **AgentNet resolver publication remain unauthorized**.
**No artifact body was read, printed, committed, or stored.** See
[`PHASE75_LOCATION_ASSESSMENT_REVIEW_SUPPORT.md`](PHASE75_LOCATION_ASSESSMENT_REVIEW_SUPPORT.md).

---

## Phase 76 — two writes: the R8 review and the R5 WMS scope clarification

Phase 76 writes **exactly two** rows under the same stored anchor (`internal_test_001` / `99999` /
`peak_internal_admin` / `internal_peak_only`): one `review_records` row (`rev_1d9696e9218b4e35`)
through the unchanged **Phase 22** writer, reviewing the R8 source ingestion
(`ing_4fb70519cbf84401`), and one `source_ingestion_records` row (`ing_f7a4cc20f1f148c7`) through the
unchanged **Phase 24** writer, registering the R5 WMS scope clarification. Head stays `014` — **no
migration, model, writer, allowlist pair, schema, operator utility, or harness was added**. Both
writes were driven by a temporary executor held outside the repository and never committed.

| credential | what it did in Phase 76 | wrote? |
| --- | --- | --- |
| read-only | pre-write and post-write schema/collation verify only; no app rows read | no |
| runtime | the two `INSERT`s, via the writers only (`SELECT` + `INSERT` grants only) | yes — two rows |
| migration | **not used** | — |

**The R8 review is `approve_internal`, non-authoritative**, approving R8 as a source-map and
precedence **framing** artifact only. It **does not confirm authority precedence** — R8's own rule is
`provisional_unconfirmed` with 2 prerequisites. **Registration integrity was not re-verified**: no
`packet_hash` is committed to the repo, and reading the stored row would be an app-row read outside
this phase's permitted stored-engagement and idempotency lookups, so no integrity claim is made.

**The R5 row registers a blocker enumeration**, `draft` / `needs_review` / `active`,
`authoritative=false` — 15 scope items with 0 favourable resolutions (1 `answered_no`, 3 `unknown`,
9 `not_measured`, 2 `blocked_by_r8`). Write 2 proceeded only because write 1 was created; both were
newly created, not replays.

**Clarified, not resolved: R8 authority precedence and R5 WMS scope both remain unresolved.** No
inventory accuracy conclusion was made. **R1 remains provisional**, the Phase 73 negative finding
stands as **data-readiness / reliability only and must not be restated as inventory accuracy**,
**R3–R7 remain deferred**, the Phase 74 outline is unmodified with `fnd_000` still
`blocked_no_review_support`, and report finalization, capsule publication, client-facing output, and
**AgentNet resolver publication remain unauthorized**.

**No artifact body was printed, committed, or stored.** The stored rows carry packet metadata,
answer-state counts, posture flags, and record ids only — no organisation or system names, item or
SKU values, quantities, or location, bin, aisle, rack, warehouse or site identifiers. The reviewed R8
row was **not modified** — the review writer has no `UPDATE` path. No `UPDATE`, `DELETE`, manual SQL,
cleanup, or `alembic stamp` was issued, and no app table was scanned, counted, or probed beyond the
writers' own stored-engagement loads and idempotency lookups. See
[`PHASE76_R8_R5_BLOCKER_CLARIFICATION.md`](PHASE76_R8_R5_BLOCKER_CLARIFICATION.md).

---

## Phase 77 — no production access, no writes

Phase 77 **contacted no production database**. No environment file was sourced, no connection was
opened, no writer was invoked, and **no row of any kind was created** — no `review_records`, no
source ingestion, evidence reference, review bundle, report draft, Client, Engagement, intake note,
capsule, client-facing output, or AgentNet publication.

| credential | what it did in Phase 77 | wrote? |
| --- | --- | --- |
| read-only | **not used** — no write was attempted, so the pre-write verifier was not run | no |
| runtime | **not used** — the runtime connectivity gate was run in `--self-test` mode only | no |
| migration | **not used** | — |

Phase 77 is a **parallel preparation phase**: read-only subagents mapped the review posture for the
R5 WMS scope clarification (`ing_f7a4cc20f1f148c7`), the R8 confirmation prerequisites, and the
remaining R3–R7 dependency order. Analysis was parallelized; **no production write was**, because
none was performed.

**No `UPDATE`, `DELETE`, manual SQL, cleanup, or `alembic stamp` was issued**, no app table was
scanned, counted, or probed, no schema was changed, and no migration was run. Head stays `014` and
**no new infrastructure was added**. **No artifact body was read, printed, committed, or stored** —
artifact contact was limited to structural shape (key names, value types, one array length), and no
organisation or system name, site, warehouse, location, bin, aisle, rack, item or SKU identifier, and
no quantity or row value was read out or recorded. **No artifact string value was read**, including
the two `authority_precedence_rule.confirmation_required_before` entries — only the array's length,
a count already on record in Phase 76. The **content of the two R8 confirmation prerequisites is not
recorded in this repository**; the Phase 77 doc reconstructs it by inference from downstream records
and labels it as such.

**No real client data** was involved — this chain is `internal_test` only. The AgentNet resolver gate
stays **shut rather than relaxed** precisely because the public resolver is live.

The Phase 74 outline is unmodified and `fnd_000` remains `blocked_no_review_support`. The finding
remains **data-readiness / reliability only and must not be restated as inventory accuracy**; **R1
remains provisional**, **R8 authority precedence and R5 WMS scope both remain unresolved**, the
**Phase 64 R5 receiving/putaway export remains uncollected**, **R3–R7 remain deferred**; and report
finalization, capsule publication, client-facing output, and **AgentNet resolver publication remain
unauthorized**. See
[`PHASE77_PARALLEL_PREP_R8_R5.md`](PHASE77_PARALLEL_PREP_R8_R5.md).

---

## Phase 78 — one write: the R5 WMS scope clarification review

Phase 78 creates **one** production row: a `review_records` row (`rev_e283136f679a46dd`, Phase 22
writer) reviewing the R5 WMS scope clarification source ingestion (`ing_f7a4cc20f1f148c7`), under the
unchanged `internal_test_001` / `99999` / `internal_peak_only` anchor.

| credential | what it did in Phase 78 | wrote? |
| --- | --- | --- |
| read-only | pre-write and post-write collation verification; `readonly_queries_only=true`, information-schema only, no app rows read | no |
| runtime | connectivity gate (`app_table_read_made=false`), then **one** `INSERT` through the review writer | **yes — one row** |
| migration | **not used** | — |

**Both pre-checks passed before the write.** The read-only verifier confirmed production head
`014_engagement_classification`, 18 base tables plus `alembic_version`, and 212/212 governed columns
deterministic. The runtime gate confirmed `required_grants_present=true`,
`excess_grants_present=false`, `global_privileges_present=false`, and `grant_option_present=false`.
The verifier was re-run after the write and returned `verified_safe_no_remediation_required`
unchanged.

**Idempotency was rehearsed off-production first**, against a temporary SQLite database, varying a
field the payload fingerprint actually covers (`reasons`) — which produced `idempotency_conflict` as
required. Varying only `source_phase` produced `idempotent_replay`, because
`_payload_fingerprint` excludes it; that control is why the rehearsal proves what it claims. The
production write returned `created`, and an identical replay returned `idempotent_replay` with
`database_write_made=false`, confirming **exactly one row**.

**No `UPDATE`, `DELETE`, manual SQL, cleanup, or `alembic stamp` was issued**, no application table
was scanned, counted, or probed beyond the writer's own stored-engagement load and idempotency
lookup, no schema was changed, and no migration was run. Head stays `014` and **no new infrastructure
was added** — execution used a temporary scratchpad executor outside the repository, and no
persistent operator or harness was committed.

**No artifact body was printed, committed, or stored.** The stored row carries posture flags,
answer-state counts, non-claims, and record ids only. Phase 78 also read R8's two authority-precedence
prerequisites from the **local artifact** — after a pattern safety screen showed both were
single-token concept slugs with no digits, codes, identifiers, or quantities — and documents them as
**sanitized concepts only**: quantitative findings, and an evidence reliability rating. **No
production row was read to obtain them**, and no R8 hash or integrity verification is claimed.

**Approved as a scope-blocker enumeration only.** The R5 WMS scope clarification is now
`approved_internal` / `draft` / `authoritative=false`; **R5 WMS scope itself remains unresolved** (0
of 15 items favourable) and the review **validates no inventory quantities and no inventory
accuracy**. **R8 authority precedence remains unresolved** and R8 remains non-authoritative. **R1
remains provisional**, the **Phase 64 R5 receiving/putaway export remains uncollected**, **R3–R7
remain deferred with R4 conditionally required / scope-dependent**, the Phase 74 outline is
unmodified with `fnd_000` still `blocked_no_review_support`, and report finalization, capsule
publication, client-facing output, and **AgentNet resolver publication remain unauthorized**. See
[`PHASE78_R5_WMS_SCOPE_REVIEW.md`](PHASE78_R5_WMS_SCOPE_REVIEW.md).

---

## Phase 79 — one write: the R8 measurement-feasibility source ingestion

Phase 79 creates **one** production row: a `source_ingestion_records` row (`ing_0d671226f2ba4760`,
Phase 24 writer) registering an **R8 authority-precedence measurement-feasibility assessment**, under
the unchanged `internal_test_001` / `99999` / `internal_peak_only` anchor.

| credential | what it did in Phase 79 | wrote? |
| --- | --- | --- |
| read-only | pre-write and post-write collation verification; `readonly_queries_only=true`, information-schema only, no app rows read | no |
| runtime | connectivity gate (`app_table_read_made=false`), then **one** `INSERT` through the source-ingestion writer | **yes — one row** |
| migration | **not used** | — |

**Both pre-checks passed before the write** — head `014_engagement_classification`, 18 base tables
plus `alembic_version`, 0 governed columns at risk; `required_grants_present=true`,
`excess_grants_present=false`, `global_privileges_present=false`, `grant_option_present=false`. The
verifier was re-run after the write and returned `verified_safe_no_remediation_required` unchanged.

**Idempotency was rehearsed off-production first**, against temporary SQLite, varying fields the
payload fingerprint actually covers — the packet location reference and the packet hash — each of
which produced `idempotency_conflict`. This writer's fingerprint covers packet **metadata only**;
`reasons` and `warnings` do not participate, unlike the review writer. Production returned `created`
with `stored_record_created=true` and `transaction_committed=true` — exactly one row.

**No `UPDATE`, `DELETE`, manual SQL, cleanup, or `alembic stamp` was issued**, no application table
was scanned, counted, or probed beyond the writer's own stored-engagement load and idempotency
lookup, no schema was changed, and no migration was run. Head stays `014` and **no new infrastructure
was added** — a temporary scratchpad executor outside the repository, nothing persistent committed.

**No artifact body was printed, committed, or stored.** The stored row carries packet metadata and a
SHA-256 only; the body lives outside the repository and outside the database, and the hash value is
not disclosed in the docs. Prior artifacts were inspected **structurally only**.

**The feasibility result is a clean negative.** The internal_test scenario **cannot produce** either
R8 confirmation prerequisite — quantitative findings, or an evidence reliability rating — both
recorded `blocked_by_missing_measurement`. Every collected source is description-level and there is
no live system to measure against, so this is a **measurement gap, not a collection gap**; collecting
the remaining requests would not resolve it. **Nothing was fabricated.**

**Registration is collection, not review.** The row is `needs_review` / `draft` /
`authoritative=false` and **is not evidence**. **R8 authority precedence remains unresolved** and R8
remains non-authoritative; recording that a question cannot be answered here is not closing it. **R1
remains provisional**, the location finding stays **data-readiness and reliability only**, the **R5
WMS scope clarification remains a reviewed scope-blocker enumeration only**, the **Phase 64 R5
export remains uncollected**, **R3–R7 remain deferred** with the count/variance request conditionally
required, the Phase 74 outline is unmodified with `fnd_000` still `blocked_no_review_support`, and
report finalization, capsule publication, client-facing output, and **AgentNet resolver publication
remain unauthorized**. See
[`PHASE79_R8_MEASUREMENT_FEASIBILITY_SOURCE_INGESTION.md`](PHASE79_R8_MEASUREMENT_FEASIBILITY_SOURCE_INGESTION.md).

---

## Phase 80 — one write: the R8 measurement-feasibility review and scenario closure

Phase 80 creates **one** production row: a `review_records` row (`rev_4208b1882d044069`, Phase 22
writer) reviewing the R8 measurement-feasibility source ingestion (`ing_0d671226f2ba4760`), under the
unchanged `internal_test_001` / `99999` / `internal_peak_only` anchor.

| credential | what it did in Phase 80 | wrote? |
| --- | --- | --- |
| read-only | pre-write and post-write collation verification; `readonly_queries_only=true`, information-schema only, no app rows read | no |
| runtime | connectivity gate (`app_table_read_made=false`), then **one** `INSERT` through the review writer | **yes — one row** |
| migration | **not used** | — |

**Both pre-checks passed before the write** — head `014_engagement_classification`, 18 base tables
plus `alembic_version`, 0 governed columns at risk; `required_grants_present=true`,
`excess_grants_present=false`. The verifier was re-run after the write and returned
`verified_safe_no_remediation_required` unchanged.

**Idempotency was rehearsed off-production first**, against temporary SQLite, varying `reasons` — a
field this writer's fingerprint covers — which produced `idempotency_conflict`; varying only
`source_phase` produced `idempotent_replay`, since the fingerprint excludes it. Production returned
`created` with `stored_record_created=true` and `transaction_committed=true` — exactly one row.

**The closure is a recorded decision, not a state change.** `approve_internal` /
`authoritative=false` approves the feasibility assessment for internal reliance and records that
**this internal_test scenario cannot confirm R8 authority precedence**, because it cannot produce
either required input. Critically, **no R8 row was modified**: the R8 source ingestion
(`ing_4fb70519cbf84401`) and the earlier R8 review (`rev_1d9696e9218b4e35`) are untouched — this
writer has no `UPDATE` path — so R8 still reads exactly as before, non-authoritative with its
precedence rule unconfirmed. The closure lives in the new review's recorded reasons, not as a status
transition.

**No `UPDATE`, `DELETE`, manual SQL, cleanup, or `alembic stamp` was issued**, no application table
was scanned, counted, or probed beyond the writer's own stored-engagement load and idempotency
lookup, no schema was changed, and no migration was run. Head stays `014` and **no new infrastructure
was added** — a temporary scratchpad executor outside the repository, nothing persistent committed.
**No artifact body was printed, committed, or stored**, and **no hash or integrity confirmation is
claimed** — the Phase 79 source is evaluated **as registered**.

**The closure is scenario-specific and narrow.** It does **not** mean R8 precedence is false, and it
does **not** mean real client data could not confirm R8 in a future engagement. The reviewed source
remains **source-only, not evidence**. **R1 remains provisional**, the location finding stays
**data-readiness and reliability only**, the **R5 WMS scope clarification remains a reviewed
scope-blocker enumeration only**, the **Phase 64 R5 export remains uncollected**, **R3–R7 remain
deferred** with the count/variance request conditionally required, the Phase 74 outline is unmodified
with `fnd_000` still `blocked_no_review_support`, and report finalization, capsule publication,
client-facing output, and **AgentNet resolver publication remain unauthorized**. See
[`PHASE80_R8_MEASUREMENT_FEASIBILITY_REVIEW_CLOSURE.md`](PHASE80_R8_MEASUREMENT_FEASIBILITY_REVIEW_CLOSURE.md).

---

## Phase 81 — no production access, no writes, no credentials created

Phase 81 **contacted no database**. No environment file was sourced, no connection was opened, no
cloud console or API was contacted, no writer was invoked, and **no row of any kind was created** —
in production or anywhere else. **No database, service, schema, user, or credential was created**, and
no migration was run.

| credential | what it did in Phase 81 | wrote? |
| --- | --- | --- |
| read-only | **not used** — no write was attempted and no verifier was run | no |
| runtime | **not used** — the runtime connectivity gate was run in `--self-test` mode only | no |
| migration | **not used** | — |

Phase 81 is a **planning phase** for a production-parity **lab** MySQL environment (`peak_lab`). It
plans; it provisions nothing. See
[`PHASE81_PRODUCTION_PARITY_LAB_MYSQL_PLAN.md`](PHASE81_PRODUCTION_PARITY_LAB_MYSQL_PLAN.md).

**The lab credential model mirrors the Phase 49 split and reuses nothing from production.** Three lab
users, three privilege sets, never interchangeable and never pointed at the same database user:

| lab role | lab user | privileges | out-of-repo variable | mirrors |
| --- | --- | --- | --- | --- |
| migration | `peak_lab_migrate` | DDL on `peak_lab` only | `PEAK_LAB_MIGRATION_URL` | `PEAK_DATABASE_URL` |
| runtime | `peak_lab_runtime` | **`SELECT` + `INSERT` only** | `PEAK_LAB_RUNTIME_URL` | `PEAK_RUNTIME_DATABASE_URL` |
| read-only verifier | `peak_lab_readonly` | `SELECT` only | `PEAK_LAB_READONLY_URL` | `PEAK_PRODUCTION_DB_URL` |

**The lab runtime credential must be provisioned to exactly `SELECT` + `INSERT`.** This is not a
formality: the Phase 50 gate's `REQUIRED_GRANTS` / `FORBIDDEN_GRANTS` are fixed, so a lab runtime user
carrying `DELETE` for convenience **fails the gate**. Matching the production posture keeps the gate
reusable unmodified and preserves what a pass means. **Reset and teardown use the migration
credential**, deliberately and separately — never runtime. The audit consequence carries over intact:
a lab runtime process cannot rewrite or remove what it wrote, so **lab records are durable by
construction** and must be designed that way rather than written and cleaned up.

**Secrets stay outside the repository and are never printed.** Phase 82 may add documented variable
*names* and an out-of-repo template — never a value. Failures continue to be reported by exception
**type** only, because driver messages embed the connection string.

**One seam is recorded rather than hidden.** `alembic/env.py` reads **only** `PEAK_DATABASE_URL` —
there is no second target, no `-x`, and no section switching — so targeting the lab means placing a
lab DSN in the production-named variable. Phase 82's control is procedural: a dedicated lab shell that
has never held a production value, with one role variable exported at a time. Production being already
at head `014` makes a misdirected `alembic upgrade head` a no-op today; **that stops being true the
moment a `015` exists**, which is one more reason no `015` is authored while this seam stands.

**No production credential is reused, no production data is copied, and no real client data enters the
lab.** No pseudo-client data, fixture, example, or sample packet is committed to the repository. The
lab receives **no client-facing report authority, no final-report authority, no capsule publication
authority, and no AgentNet resolver publication authority**; the AgentNet resolver gate stays **shut
rather than relaxed**, precisely because the public resolver is live. The lab does **not** reuse the
production `internal_test_001` / `99999` / `internal_peak_only` anchor — that anchor is a production
row.

**Nothing moved.** Head stays `014_engagement_classification` with 14 migrations, 18 tables, and 12
writers. **R1 remains provisional**, the location finding stays **data-readiness and reliability only,
never inventory accuracy**, the **R5 WMS scope clarification remains a reviewed scope-blocker
enumeration only**, the **Phase 64 R5 export remains uncollected**, **R3–R7 remain deferred**, the
Phase 74 outline is unmodified with `fnd_000` still `blocked_no_review_support`, and report
finalization, client-facing output, capsule publication, and **AgentNet resolver publication remain
unauthorized**.

---

## Phase 82 — no production access, no cloud contact, no credentials created

Phase 82 **contacted no database and no cloud service, API, or console**. No environment file was
created or sourced, no connection was opened, no writer was invoked, and **no row of any kind was
created** — in production or anywhere else. **No database, service, schema, user, or credential was
created**, and no migration was run.

| credential | what it did in Phase 82 | wrote? |
| --- | --- | --- |
| read-only | **not used** — no verifier was run | no |
| runtime | **not used** — the runtime connectivity gate was run in `--self-test` mode only | no |
| migration | **not used** | — |

Phase 82 is a **readiness/runbook phase** for the production-parity lab MySQL environment. It writes
the runbook Phase 83 executes; it provisions nothing. See
[`PHASE82_LAB_MYSQL_PROVISIONING_READINESS.md`](PHASE82_LAB_MYSQL_PROVISIONING_READINESS.md).
**Phase 83 requires explicit user approval, because it creates recurring-cost managed
infrastructure** — approval is not implied by the runbook's existence.

**The lab credential plan, superseding the Phase 81 read-only name.** Names only; **no secret value
enters this repository in any phase.**

| lab role | lab user | privileges | out-of-repo env file | the one variable that file sets |
| --- | --- | --- | --- | --- |
| migration | `peak_lab_migrate` | DDL on `peak_lab` only | `peak-lab-migrate.env` | `PEAK_DATABASE_URL` |
| runtime | `peak_lab_runtime` | **`SELECT` + `INSERT` only** | `peak-lab-runtime.env` | `PEAK_RUNTIME_DATABASE_URL` |
| read-only verifier | `peak_lab_verify_ro` *(was `peak_lab_readonly`)* | `SELECT` only | `peak-lab-ro.env` | `PEAK_PRODUCTION_DB_URL` + `PEAK_PRODUCTION_DB_READONLY_CONFIRM=1` |

**None of these files exist.** They are named here and created in Phase 83, outside the repository.
No `GRANT OPTION`, no broad grants, no global privileges beyond `USAGE`, no `UPDATE`/`DELETE` for
runtime unless separately approved, **no production credential reused**, and **no credential for
AgentNet publication, capsule publication, final report, or client-facing output**.

**The seam is wider than Phase 81 recorded, and the shell guard is therefore mandatory.** Phase 81
flagged that `alembic/env.py` reads only `PEAK_DATABASE_URL`. Reading the tools shows **all three
roles** place a lab DSN in a production-named variable: the connectivity gate reads only
`PEAK_RUNTIME_DATABASE_URL` and the collation verifier reads `PEAK_PRODUCTION_DB_URL` /
`PEAK_DATABASE_URL` and requires `PEAK_PRODUCTION_DB_READONLY_CONFIRM`. **No variable name says
"lab", so the name cannot tell an operator which environment it points at.** Phase 83's control is
procedural and required: a fresh shell that has never held a production value, no production env
sourced, exactly one lab env file at a time, context verified before migrating, **never** `env` /
`printenv` / `set` / `set -x`, an explicit lab assertion on host/service/user before
`alembic upgrade`, a full stop if any name mentions the production service or a production user, and
the shell closed or unset afterwards. `PEAK_LAB_CONFIRM` is **reserved and reads as a no-op** — no
script reads it — and the `PEAK_LAB_*_URL` names from Phase 81 are **retired as operative names**,
since nothing reads them either.

**One control is real rather than procedural:** the connectivity gate scrubs `PEAK_DATABASE_URL`,
`PEAK_PRODUCTION_DB_URL`, and `PEAK_PRODUCTION_DB_READONLY_CONFIRM` from its own process environment
before anything else runs, so it cannot silently fall back to a migration or production variable.

**Phase 83 is provisioning, migration, and verification only** — apply the existing **14** migrations
to `peak_lab` alone, reach head `014_engagement_classification`, expect **18** tables plus
`alembic_version`, verify head/table/migration counts, governed collation via the lab read-only
credential, and the grant posture of each lab credential. **No `015`. No `peak_lab_scenario`. No
measured rows. No writer invocation. No Peak record.** Production is not touched at any step.

**Nothing moved.** Head stays `014_engagement_classification` with 14 migrations, 18 tables, and 12
writers, and **no standing production write enablement**. **R1 remains provisional**, the location
finding stays **data-readiness and reliability only, never inventory accuracy**, the **R5 WMS scope
clarification remains a reviewed scope-blocker enumeration only**, the **Phase 64 R5 export remains
uncollected**, **R3–R7 remain deferred**, the Phase 74 outline is unmodified with `fnd_000` still
`blocked_no_review_support`, and report finalization, client-facing output, capsule publication, and
**AgentNet resolver publication remain unauthorized**.

---

## Phase 83 — the lab exists: one managed service, three credentials, no production contact

Phase 83 executed the Phase 82 runbook under explicit user approval. It **contacted no production
system**: no production environment file was sourced, no production connection was opened, no
production verifier was run against production, and no production service, network, or configuration
was changed. **No writer was invoked and no record was created through any Peak writer.**

| credential | what it did in Phase 83 | wrote? |
| --- | --- | --- |
| production read-only | **not used** | no |
| production runtime | **not used** | no |
| production migration | **not used** | no |
| **lab** `peak_lab_migrate` | applied the existing 14 migrations to `peak_lab` | schema only — **no application row** |
| **lab** `peak_lab_runtime` | connectivity + grant gate: `SELECT 1`, `SHOW GRANTS` | no |
| **lab** `peak_lab_verify_ro` | read-only schema, collation, and emptiness verification | no |

See [`PHASE83_PEAK_LAB_PROVISIONING_AND_VERIFICATION.md`](PHASE83_PEAK_LAB_PROVISIONING_AND_VERIFICATION.md).

**The lab credential posture, verified on the server by `SHOW GRANTS`:**

| credential | global | on `peak_lab.*` | `GRANT OPTION` |
| --- | --- | --- | --- |
| `peak_lab_migrate` | `USAGE` only | `SELECT, INSERT, UPDATE, DELETE, CREATE, DROP, REFERENCES, INDEX, ALTER` | **none** |
| `peak_lab_runtime` | `USAGE` only | **`SELECT, INSERT`** | **none** |
| `peak_lab_verify_ro` | `USAGE` only | **`SELECT`** | **none** |

Each was reduced with `REVOKE ALL PRIVILEGES, GRANT OPTION` before being granted exactly its role.
**No privilege on `*.*` beyond `USAGE`**, which the Phase 50 gate treats as `HARMLESS_GLOBAL`. No
production credential was reused and no production data was copied. **The runtime credential has no
`UPDATE` and no `DELETE`**, so whatever it writes later is permanent by construction.

**The gate passed live against the lab runtime credential:** `connectivity_succeeded=true`,
`required_grants_present=true`, `excess_grants_present=false`, `global_privileges_present=false`,
`grant_option_present=false`, `app_table_read_made=false`, `writer_invoked=false`,
`secrets_printed=false`.

**Two output captions are mandatory, and are not cosmetic.** Both tools print production-named
results because they read production-named variables: the verifier reported
`production_connection_made=true` and the gate reported `production_connectivity_result=succeeded`.
**Both runs were lab-targeted; no production connection was attempted or made.** The gate also
reported `ready_for_later_writer_enablement=true` — that is **prerequisite evidence about a lab
credential, not write permission and not a production statement.** The Phase 51 decision gate remains
the authority and still reports `safe_to_write_production_now=false`.

**One incident, recorded rather than hidden.** While authoring the lab env files, a DSN written
**unquoted** caused the shell to fail glob expansion on the `?` in its query string and **echo the
line, including the migration credential's password**, before any guard could run. **The
`peak_lab_migrate` credential was rotated**, and the exposed value was never used afterwards. Every
lab env value is now single-quoted, and the files are generated by an out-of-repo helper that reads
passwords with hidden input and URL-encodes them, removing hand-editing from the path. The temporary
admin env file contemplated in planning was **never created** — the administrative SQL ran in an
operator session instead.

**Nothing in production moved.** Repo head stays `014_engagement_classification` with 14 migrations,
18 tables, and 12 writers, and **no standing production write enablement**. **R1 remains
provisional**, the location finding stays **data-readiness and reliability only, never inventory
accuracy**, the **R5 WMS scope clarification remains a reviewed scope-blocker enumeration only**, the
**Phase 64 R5 export remains uncollected**, **R3–R7 remain deferred**, the Phase 74 outline is
unmodified with `fnd_000` still `blocked_no_review_support`, and report finalization, client-facing
output, capsule publication, and **AgentNet resolver publication remain unauthorized**.

---

## Phase 84 — the Alembic migration target guard (source-only Fix Now; no database contacted)

**Phase 83's largest residual risk is closed.** `alembic/env.py` read `PEAK_DATABASE_URL` and nothing
else, so **no variable name said which environment the URL pointed at** and only shell discipline kept
a lab migration off production. That was survivable only while production and the repository were both
at head `014` with nothing left to apply — an accident of timing, not a control, and one that expires
the moment a `015` exists. See
[`PHASE84_ALEMBIC_TARGET_GUARD_FIX.md`](PHASE84_ALEMBIC_TARGET_GUARD_FIX.md).

**No production or lab database was contacted.** No environment file was sourced, no connection
opened, **no migration run against any live target**, no `015` created, no `peak_lab_scenario` created,
no writer invoked, and no record created. Source, tests, and docs only; every URL exercised is
**synthetic**.

**MySQL/MariaDB migrations now require an explicit, confirmed target**, checked before the engine is
created:

| variable | value | required when |
| --- | --- | --- |
| `PEAK_ALEMBIC_TARGET` | `lab` \| `production` | every MySQL/MariaDB migration |
| `PEAK_LAB_MIGRATION_CONFIRM` | `1` | target is `lab` |
| `PEAK_PRODUCTION_MIGRATION_CONFIRM` | `1` | target is `production` |

**Lab migrations must name `peak_lab` and connect as `peak_lab_migrate`**, with the lab confirmation
set; `defaultdb`, any other schema, any other user (including `peak_lab_runtime`), and any
production marker are refused. **Production migrations require their own separate confirmation**,
refuse any `peak_lab` marker, and **remain unauthorized outside a separately approved phase** — passing
the guard means the URL is consistent with production, never that the migration is approved.
`PEAK_DATABASE_URL` is unchanged and remains the one variable naming the URL. **`PEAK_LAB_CONFIRM` is
deliberately not used**, because Phase 82 published it as reserved and a no-op.

**SQLite and every other dialect bypass the guard entirely** with no environment set, so local
temporary-file harnesses are unaffected.

**Value-free by construction.** The guard opens no file, imports no driver, creates no engine, issues
no SQL, and keeps only the parsed user and database — host, port, password, and query string are
discarded. Failure messages carry the target, a classification of the user and schema, and a reason
code, and the harness asserts that none of them contains a password, host, port, query parameter, or
connection string.

**The shell discipline still applies in full.** The guard does not replace it; it is a second,
independent control that fails the run rather than trusting the shell was right. **Three known gaps
stay open:** the guard checks the URL's names, not which host is behind them; the production branch is
necessarily weaker than the lab branch, since production's names are not recorded in this repository
and must not be; and the connectivity gate and collation verifier still take a lab DSN in a
production-named variable with no target of their own.

**Nothing moved.** Head stays `014_engagement_classification` with 14 migrations, 18 tables, and 12
writers, and **no standing production write enablement** — the Phase 51 gate still reports
`safe_to_write_production_now=false`. **This fix must be committed and accepted before any migration
`015` or further lab migration work**; the scenario-seeding work Phase 83 §10 called "Phase 84" is
renumbered to **Phase 85**.

## Phase 85 — two scenario-scoped lab credentials, and the schema they can reach

Phase 85 created and seeded **`peak_lab_scenario`**, a **lab-only simulated source-system schema** that
is **not Alembic-managed**, holds **no Peak controlled table**, and is **never production**. It added
**two new dedicated credentials**; **no controlled-schema credential was expanded**, and **no
production credential was used, created, or altered.**

| credential | global | on `peak_lab_scenario.*` | `GRANT OPTION` | can enumerate `peak_lab`? |
| --- | --- | --- | --- | --- |
| `peak_lab_scenario_loader` | `USAGE` only | `SELECT, INSERT, UPDATE, DELETE, CREATE, DROP, REFERENCES, INDEX, ALTER` | **none** | **no** |
| `peak_lab_scenario_ro` | `USAGE` only | **`SELECT`** | **none** | **no** |

Verified by reading `SHOW GRANTS` back **as each credential in turn**: each holds **exactly one**
database-level grant, on the scenario schema, and **neither can enumerate a single `peak_lab` table**.
Isolation is confirmed by measurement, not inferred from grant text.

**Newly provisioned service users on this lab platform arrive holding global `ALL PRIVILEGES` WITH
`GRANT OPTION`, including `CREATE USER`.** As created, both scenario credentials could read and write
every controlled `peak_lab` table. **Reduction is a mandatory provisioning step, not tidying**, and its
result must be verified by connecting as the credential rather than assumed. Two operational notes
follow from this and are recorded in full in the phase document: the reduction requires globals to be
stripped **before** the database grant is issued, by a second account still holding `GRANT OPTION`,
because on this server `REVOKE ALL PRIVILEGES ON *.*` also clears database-level grants; and the
control-plane API **returns a masked placeholder instead of a stored password**, so service
credentials can be reset but never recovered. **The service administrator password was deliberately not
reset.**

Both credentials live in **out-of-repo environment files, mode `600`**, each setting exactly one
single-quoted variable with a URL-encoded password: `peak-lab-scenario-loader.env` sets
`PEAK_LAB_SCENARIO_LOADER_URL`, and `peak-lab-scenario-ro.env` sets `PEAK_LAB_SCENARIO_RO_URL`. **No
repository tool reads either variable**, and none was changed to — the scenario tooling is out-of-repo,
so it names its own variables honestly instead of extending the Phase 82 §3 seam, where every lab DSN
sits in a production-named variable that cannot say which environment it points at.

**Caption, required.** Under `peak_lab_verify_ro`, the scenario schema reports as **not present**. That
is least privilege working correctly — that credential holds no grant on the scenario schema — **not
evidence that the schema is absent.** Do not read a `peak_lab_verify_ro` schema listing as proof either
way.

**Phase 85 made no production access, ran no live Alembic migration, created no migration `015`, wrote
nothing to any `peak_lab` controlled table, invoked no writer, and created no Peak record.** `peak_lab`
was re-verified afterwards at head `014_engagement_classification`, `alembic_version` **1 row**, and **0
application rows across all 18 controlled tables**. **No scenario row body, secret, DSN, host, port,
service URI, provider name, certificate path, environment value, or local secret path is committed.**
See [`PHASE85_PEAK_LAB_SCENARIO_SEEDING.md`](PHASE85_PEAK_LAB_SCENARIO_SEEDING.md).

---

## Phase 88 — the scenario read-only credential, exercised and proven read-only

Phase 88 measured `peak_lab_scenario` under **`peak_lab_scenario_ro`**, the read-only role Phase 85
created. **Every statement was a `SELECT`.**

Before connecting, **seventeen value-free structural checks** passed against the environment file:
existence, mode `600`, exactly one variable, the expected variable name, a single-quoted value, the
expected scheme, the expected role, the expected target database, and the *presence* — never the
content — of password, host, port and certificate path. The target was confirmed to be neither the
controlled lab schema, nor the platform default schema, nor anything carrying a production marker.
**No value was printed, echoed, or logged.**

Privileges were then read back **as the credential itself**: global `USAGE` only, **exactly one**
database-level grant (`SELECT`, on the scenario schema), **no `GRANT OPTION`**, no grant naming the
controlled schema, and **zero controlled-schema tables visible**.

**Five write attempts were issued deliberately as a negative control** — `INSERT`, `UPDATE`,
`DELETE`, `CREATE TABLE`, `DROP TABLE` — and **all five were refused by the server** with a
permission error. Read-only posture is therefore established **by measurement, not by grant text
alone**. Nothing was created or removed; each statement was rejected before execution. This is
recorded here so that a reader of the server's audit log finds the explanation rather than an
unexplained set of denied statements.

**The Phase 82 §3 seam was encountered directly.** The lab read-only credential file sets a
**production-named variable** while pointing at the lab schema. Phase 88 guarded against it by
asserting the target database and role name **before** opening the connection rather than trusting
the variable name. Nothing was changed; the seam remains a standing trap for any tool or operator
that reads a variable name as an environment label.

**Phase 88 made no production access, ran no live Alembic migration, created no migration `015`,
wrote nothing to `peak_lab` or `peak_lab_scenario`, invoked no writer, and created no Peak record.**
`peak_lab` was re-verified under its own read-only credential at head `014_engagement_classification`
with **0 application rows across all 18 controlled tables**. **No row body, secret, DSN, host, port,
service URI, provider name, certificate path, environment value, or local secret path is committed.**
See [`PHASE88_LAB_SCENARIO_MEASUREMENT.md`](PHASE88_LAB_SCENARIO_MEASUREMENT.md).

---

## Phase 89 — a lab writer authority, named separately from every other authority

Phase 89 added a **lab-only** writer enablement decision path. **It contacted no database**, read no
credential file, invoked no writer, and created no record; every URL in the module and its tests is
synthetic and unroutable.

The point for access and audit is the **variable contract**. Lab writer enablement is authorized by
`PEAK_WRITER_TARGET=lab` plus `PEAK_LAB_WRITER_ENABLEMENT_CONFIRM=1`, with the target DSN in
`PEAK_LAB_WRITER_TARGET_URL` and the requested writer targets in `PEAK_LAB_WRITER_TARGETS`. The
confirmation accepts **only** the exact string `1`, so a half-set or inherited variable fails closed.

**Nine variables are explicitly refused as authorizers**, and each refusal is tested: the Phase 82
reserved no-op; the three Phase 84 migration variables — migrating the lab and writing rows to it
are different powers; the two Phase 85 scenario variables, neither of which is a Peak writer
credential; and the three production-named URL variables, which must never authorize a lab write.
**One confirmation must never grant two authorities.**

This is the direct answer to the Phase 82 §3 seam recorded above and encountered in Phase 88, where
a production-named variable pointed at the lab and the name could not say which environment it
meant. The new variables name their own purpose. The seam itself is unchanged for the existing lab
roles and remains open.

**Only `peak_lab_runtime` is an approved lab writer role** — `SELECT` + `INSERT`, no `DELETE`, the
right shape for create-only writers. The lab **migration** role and the scenario read-only role are
both refused, as are any production-marked user, the scenario schema, the provider default schema,
and any schema that is not exactly `peak_lab`.

**Production is unreachable from this path.** Every production field is false on every branch, and
running the Phase 51 production gate with every lab variable set produces **byte-identical** output
to running it with none. **No secret, DSN, host, port, certificate path, query parameter, or
environment value appears in any decision output** — the harness asserts a decision built from a URL
containing all of them contains none. See
[`PHASE89_LAB_WRITER_ENABLEMENT_GATE.md`](PHASE89_LAB_WRITER_ENABLEMENT_GATE.md).

---

## Phase 90 — the first Peak writer invocation against the lab, under a second confirmation

Phase 90 created **one** durable `engagements` row in `peak_lab` through the existing Phase 54/56
controlled anchor writer. **No production access occurred**, no other writer was invoked, no other
record was created, no live Alembic migration ran, and no migration `015` was created.

**The credential.** The lab **runtime** role, verified before use by sixteen value-free structural
checks of its environment file — mode `600`, exactly one variable, the expected variable name,
scheme, role, target database, and the *presence* (never the content) of password, host, port and
CA path; not the provider default, not the scenario schema, no production marker, and not the
migration or scenario role. **No value was printed, echoed, or logged.**

Read back as the credential itself: `SELECT, INSERT` plus `USAGE`, **no `GRANT OPTION`**, and **no
visibility into `peak_lab_scenario`** — 0 schemas, 0 tables. Writing to the scenario schema was
therefore structurally impossible on this path, not merely disallowed by policy.

**The authority.** A new confirmation, `PEAK_LAB_ENGAGEMENT_ANCHOR_BOOTSTRAP_CONFIRM=1`, required
**in addition to** every Phase 89 lab check, with the anchor as the **only** requested target. The
anchor pair remains outside the ordinary enableable set, so no ordinary lab request can reach it,
and mixing it with a data-record target denies the whole request. Bootstrapping an identity/root
record and writing data records stay different authorities. Every previously refused authorizer —
the Phase 82 reserved no-op, the Phase 84 migration variables, the Phase 85 scenario variables, and
the production-named URL variables — remains refused.

**No removal path, by design.** The runtime role holds no `DELETE`. The record is durable, no
cleanup was attempted or built, and a correction means a new engagement id rather than a rewrite.
Removing it would require the migration credential — a separate approval and a separate risk, not
authorized here.

**Production is unchanged.** The Phase 51 gate is byte-identical and its output is byte-identical
with the bootstrap variables set. **No secret, DSN, host, port, certificate path, query parameter,
environment value, or row body appears in any output or in this repository.** See
[`PHASE90_LAB_ENGAGEMENT_ANCHOR_BOOTSTRAP.md`](PHASE90_LAB_ENGAGEMENT_ANCHOR_BOOTSTRAP.md).
