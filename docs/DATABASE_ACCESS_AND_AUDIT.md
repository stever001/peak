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
