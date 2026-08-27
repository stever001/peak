# Database Scaffold (Phase 11)

A **minimal local scaffold** for Peak's controlled engagement database. This phase adds
**source assets only** — SQLAlchemy models, enum contracts, Alembic migrations, and
config templates. **No data is committed** and no production database is deployed.
AgentNet grounding remains **intended future architecture, not implemented**.

## Decisions

- **MySQL** is the target controlled engagement database (the system of record for live
  engagement data). Not SQLite; not PostgreSQL (unless later justified).
- **Python** is the worker/tooling layer, with **SQLAlchemy** (models), **Alembic**
  (migrations), and **PyMySQL** (driver).
- The **repo stays source-only.** Models and migrations define **structure only**; no
  client data, seed data, fixtures, dumps, or credentials are committed.

## Layout

```
peak/
  __init__.py
  db/
    __init__.py
    base.py       # DeclarativeBase + governance/audit mixins (MySQL InnoDB/utf8mb4)
    enums.py      # Python enums mirroring the Phase 9 canonical governance values
    models.py     # 13 controlled-database models (schema only)
    session.py    # engine/session from PEAK_DATABASE_URL (no credentials in repo)
alembic.ini       # Alembic config; URL comes from the environment, not this file
alembic/
  env.py          # reads PEAK_DATABASE_URL; target_metadata = Base.metadata
  version_table_hardening.py   # Phase 47: alembic_version.version_num preflight (bookkeeping only)
  versions/
    001_initial_controlled_database_schema.py   # tables only, no inserts
    002_agent_run_idempotency.py                # Phase 20: agent_run_records columns + unique index (no data)
    003_evidence_idempotency.py                 # Phase 21: evidence_references columns + unique index (no data)
    004_review_idempotency.py                   # Phase 22: review_records columns + unique index (no data)
    005_source_ingestion_idempotency.py         # Phase 24: source_ingestion_records columns + unique index (no data)
    006_agent_task_queue_records.py             # Phase 27: agent_task_queue_records table (new table, no data)
    007_review_bundle_records.py                # Phase 30: review_bundle_records table (new table, no data)
.env.example      # placeholders only (PEAK_DATABASE_URL=...); .env is gitignored
requirements.txt  # SQLAlchemy / alembic / PyMySQL (runtime tooling)
```

## Models & governance

The models cover: `Client`, `Engagement`, `EngagementRecord`, `EvidenceReference`,
`SourceSystemReference`, `FinancialImpactEstimate`, `ResolverCapsuleRecord`,
`ReviewRecord`, `AgentRunRecord`, `CapsulePublicationCandidate`, `SourceIngestionRecord`,
`AgentTaskQueueRecord` (Phase 27), and `ReviewBundleRecord` (Phase 30)
(see [`DATABASE_RECORD_MODEL.md`](DATABASE_RECORD_MODEL.md)).

- **Prefixed string IDs** (`client_`, `eng_`, `evid_`, …), not autoincrement.
- **Governance and audit fields are real columns** — `owner_id`, `authorization_scope`,
  `review_status`, `lifecycle_status`, `created_at/by`, `updated_at/by`, `agent_run_id` —
  never hidden inside `details_json` (which is for non-governance detail only).
- Governance values come from `peak/db/enums.py`, whose **source of truth is the Phase 9
  schemas** ([`GOVERNANCE_STATES.md`](GOVERNANCE_STATES.md)); the enums are enforced
  app-side.
- Indexes on `owner_id`, `client_id`, `engagement_id`, `review_status`,
  `lifecycle_status`, `authorization_scope`.

## Credentials & environment

- The MySQL URL is read from the **`PEAK_DATABASE_URL`** environment variable (see
  `.env.example`), never from the repo.
- **`.env` is gitignored** and must never be committed. `.env.example` holds
  **placeholders only**.
- Databases, dumps, backups, and `*.sql`/`*.db` files are gitignored.

## Using it (outside the repo, with a real MySQL server)

```bash
python3 -m pip install -r requirements.txt      # SQLAlchemy / alembic / PyMySQL
cp .env.example .env                            # then set a real PEAK_DATABASE_URL
alembic upgrade head                            # create the schema (no data)
```

Applying migrations requires a running MySQL server and real credentials — **none of
which live in this repo**. Client data belongs in the controlled MySQL database and, in
future, resolver capsules — **not in Git**.

## Verifying the scaffold locally (no database)

The scaffold can be verified **without a MySQL server** by importing the models and
inspecting metadata. Install the runtime dependencies into a local virtual environment
(the `.venv/` directory is gitignored and must never be committed):

```bash
python3 -m venv .venv
.venv/bin/python -m pip install -r requirements.txt      # SQLAlchemy / alembic / PyMySQL
.venv/bin/python -m pip install -r requirements-dev.txt  # jsonschema (validation harness)

# dependency-backed scaffold check (imports models, verifies the 15 tables and columns)
.venv/bin/python tests/validate_phase11_db_scaffold.py

# or run the whole validation suite through the venv interpreter
make validate PYTHON=.venv/bin/python
```

When SQLAlchemy/Alembic are installed, the Phase 11 check additionally imports
`peak.db.models`, confirms `Base.metadata` defines **exactly** the 13 expected tables with
unique names, and asserts every table carries the required governance/audit columns
(`owner_id`, `authorization_scope`, `review_status`, `lifecycle_status`, `created_at`,
`updated_at`). Without those dependencies the same check runs structurally and skips the
import step. None of this connects to a database or writes any data.

> Model annotations use `typing.Optional[...]` (not the `X | None` union) so the
> SQLAlchemy models import on the repo's baseline `python3` (3.9+) as well as newer
> interpreters.

## Scope of Phase 11

Local scaffold only: schema definitions and migrations. **Not** included: production
deployment, seed/fixtures, API, resolver integration, ingestion pipeline, agent runtime,
LLM/AgentNet integration, or client-facing functionality. See
[`DATABASE_IMPLEMENTATION_PLAN.md`](DATABASE_IMPLEMENTATION_PLAN.md) for the staged plan.

Resolver *access* (grounding lookups via the existing AgentNet MCP connector) is
scaffolded separately as a governance boundary in
[`AGENTNET_MCP_BOUNDARY.md`](AGENTNET_MCP_BOUNDARY.md) — also contracts only, with no live
calls and no AgentNet integration.

---

## Phase 37 — internal_assessment_report_drafts (16th table)

Migration `010_internal_assessment_report_drafts` adds the sixteenth table, backing the Phase 37
controlled internal-assessment-report-draft writer. Schema only: no INSERT, no seed data, no
destructive change; the downgrade drops only the new table. `make db-check` now expects **16
tables**. See
[`INTERNAL_ASSESSMENT_REPORT_DRAFT_CONTROLLED_WRITER.md`](INTERNAL_ASSESSMENT_REPORT_DRAFT_CONTROLLED_WRITER.md).

---

## Phase 38 — internal_report_review_packets (17th table)

Migration `011_internal_report_review_packets` adds the seventeenth table, backing the Phase 38
controlled internal-report-review-packet writer. Schema only: no INSERT, no seed data, no
destructive change; the downgrade drops only the new table. `make db-check` now expects **17
tables**. Index names are pinned short so every identifier fits MySQL's 64-character limit. See
[`INTERNAL_REPORT_REVIEW_PACKET_CONTROLLED_WRITER.md`](INTERNAL_REPORT_REVIEW_PACKET_CONTROLLED_WRITER.md).

---

## Phase 39 — internal_report_review_packet_decisions (18th table)

Migration `012_internal_report_review_packet_decisions` adds the eighteenth table, backing the
Phase 39 controlled packet-decision writer. Schema only: no INSERT, no seed data, no destructive
change; the downgrade drops only the new table. `make db-check` now expects **18 tables**. Index
names use a short `ix_irrpd_` prefix so every identifier fits MySQL's 64-character limit. See
[`INTERNAL_REPORT_REVIEW_PACKET_DECISION_CONTROLLED_WRITER.md`](INTERNAL_REPORT_REVIEW_PACKET_DECISION_CONTROLLED_WRITER.md).

---

## Phase 41 — MySQL parity is checked automatically

The scaffold targets MySQL, but local validation runs on SQLite, and the two disagree in ways
SQLite will not report — most concretely MySQL's **64-character identifier limit**. Since Phase 41
that gap is machine-checked offline by
[`tools/managed_mysql_parity_check.py`](../tools/managed_mysql_parity_check.py)
(`make mysql-parity-static`, and part of `make validate` via `make validate-phase41`).

When adding a table whose name approaches ~25 characters, do not rely on convention-derived index
names: `ix_<table>_<column>` overflows quickly. Pin a short explicit prefix, as
`internal_report_review_packet_decisions` does with `ix_irrpd_*`. See
[`MANAGED_MYSQL_PRODUCTION_PARITY_VALIDATION.md`](MANAGED_MYSQL_PRODUCTION_PARITY_VALIDATION.md).

---

## Phase 42 — state the collation on governed columns

The scaffold pins `InnoDB` and `utf8mb4` but **no collation**, so the managed server's default
currently decides case sensitivity for every comparison.

When adding a governed string column — an id, a tenant/engagement ref, an authorization scope, an
idempotency key, or a fingerprint — **state its collation explicitly**. Silence means "whatever the
server happens to default to", which is not a decision. See
[`GOVERNED_MYSQL_COLLATION_POLICY.md`](GOVERNED_MYSQL_COLLATION_POLICY.md) and run
`make mysql-collation-audit`.

---

## Phase 44 — use GovernedString for governed columns

The scaffold now states comparison semantics explicitly. `peak.db.base.GovernedString(length)`
pins `utf8mb4_bin` on MySQL via `with_variant` and leaves SQLite untouched, so the local
structural-smoke path keeps working. Use it for any column whose comparison decides identity,
authorization, uniqueness, or integrity; use plain `String`/`Text` for prose and JSON detail.

## Phase 47 — long revision ids are safe on a fresh MySQL bootstrap

Alembic creates its bookkeeping table as `version_num VARCHAR(32)`, but five revision ids here are
longer than that (up to 43 characters). On a fresh MySQL/MariaDB database that combination fails
partway through `alembic upgrade head`: the migration's DDL commits, then Alembic cannot record it.

`alembic/env.py` now runs a preflight before migrations that creates `alembic_version` at
`version_num VARCHAR(255) NOT NULL` when absent, widens it when narrower, and does nothing otherwise.
SQLite is skipped entirely, so the local structural-smoke path is unchanged, and offline mode opens
no connection. A source-side guard fails loudly if a new revision id would ever exceed the configured
width — so prefer short revision identifiers, but a long one can no longer break a bootstrap
silently.

The preflight is Alembic bookkeeping only: two fixed statements naming just `alembic_version` and
`version_num`, no application-table DDL. See
[`PHASE47_ALEMBIC_VERSION_TABLE_HARDENING.md`](PHASE47_ALEMBIC_VERSION_TABLE_HARDENING.md).

## Phase 49 — runtime and migration read different variables

`peak/db/session.py` reads **`PEAK_RUNTIME_DATABASE_URL`**; `alembic/env.py` reads
**`PEAK_DATABASE_URL`**; the read-only production verifier reads **`PEAK_PRODUCTION_DB_URL`**. The
three are deliberately not interchangeable — see `.env.example` for the placeholder form and
[`PHASE49_RUNTIME_DATABASE_URL_SEPARATION.md`](PHASE49_RUNTIME_DATABASE_URL_SEPARATION.md) for why.

Do **not** set `PEAK_DATABASE_URL` in a runtime environment file. Runtime does not fall back to it;
it fails closed with a message naming the missing variable, because silently borrowing the migration
credential would give application code schema-change privileges.

For local work, pass an explicit URL instead of setting any of them:
`create_session_factory(url="sqlite:///tmp/x.db")`, or inject `session_factory=` into a writer.

## Phase 50 — checking runtime connectivity without touching data

`make runtime-connectivity-gate` runs a read-only check that the runtime credential can connect
through `peak/db/session.py` and still holds exactly `SELECT` + `INSERT`. It is **opt-in** and not
part of `make validate`, because it can reach the real deployed database.

It refuses (exit 2) when `PEAK_RUNTIME_DATABASE_URL` is unset, never reads `PEAK_DATABASE_URL` or
`PEAK_PRODUCTION_DB_URL`, issues only `SELECT 1` and `SHOW GRANTS FOR CURRENT_USER`, writes nothing,
reads no application table, and prints booleans rather than any connection detail.

`--self-test` exercises its logic with no database at all, and refuses to run if a runtime URL is
set so it can never stand in for a live check. See
[`PHASE50_CONTROLLED_RUNTIME_CONNECTIVITY_GATE.md`](PHASE50_CONTROLLED_RUNTIME_CONNECTIVITY_GATE.md).

## Phase 51 — the writer enablement decision gate

`make writer-enablement-decision-gate` prints the current, machine-checkable decision about
production writes. Today that decision is **no production smoke-write and no writer enablement**.

The tool is offline by construction: no database connection, no engine or session import, no writer
import, no environment read, no statement, no file access. It exits 0 for the no-write path and
refuses with exit 3 if asked to record a write-authorizing path. `--json` emits a single parseable
document on stdout.

It is opt-in and not part of `make validate`; the static harness `make validate-phase51` is.

Before any future write, re-run the read-only verifier, the runtime connectivity gate, and this
decision gate — and note that runtime holds no `DELETE`, so any synthetic record it writes is
durable. Pass `PYTHON=.venv/bin/python` to the two live gates: `PYTHON` defaults to `python3`, which
may have no database driver. The connectivity gate then fails closed and reports
`failure_category=local_driver_unavailable` with a `FIX:` line — a local interpreter problem, **not**
a production connectivity failure, and it authorizes nothing either way. See
[`PHASE51_WRITER_ENABLEMENT_DECISION_GATE.md`](PHASE51_WRITER_ENABLEMENT_DECISION_GATE.md).

## Phase 53 — planning the first authorized engagement / intake write path

Phase 53 is **plan only**: no production write, no writer enablement, no synthetic smoke write, no
engagement record, no intake note, no schema or migration change. Head stays at
`013_governed_identifier_collation_policy`; 13 migrations and 18 tables are unchanged.

Reading source established the shape of the first real write:

- **`Engagement` (`engagements`) exists** from migration `001_initial`, so the schema side of the
  authorization anchor is already in place. Nothing needs to be added to the scaffold.
- **No controlled Engagement writer exists.** No writer targets `engagements`; the table is in
  `PROHIBITED_TABLES` and no engagement-creating action is on the allowlist.
- **The intake note writer exists** (Phase 34) and **requires a stored `Engagement` whose
  `authorization_scope` matches the request** — it denies on missing subject, blank stored scope,
  scope mismatch, identity mismatch, or a blocked subject lifecycle. So the first intake note cannot
  be written without the anchor.
- **All eleven writers load that same anchor**; nine depend on it alone, and two additionally need a
  stored parent draft or packet. That ordering makes the **intake note writer** the recommended
  first real operational writer once an authorized engagement exists.

**Recommended next phase: Phase 54 should add a create-only controlled Engagement authorization
anchor writer** — and create no engagement record. The Phase 51 no-write / no-enablement decision is
unchanged, Phase 50 connectivity remains prerequisite evidence rather than write permission, and no
synthetic smoke-write is authorized. See
[`PHASE53_AUTHORIZED_ENGAGEMENT_INTAKE_PATH.md`](PHASE53_AUTHORIZED_ENGAGEMENT_INTAKE_PATH.md).

## Phase 54 — the engagement authorization anchor writer

Phase 54 adds the twelfth narrow controlled writer,
[`peak/db/engagement_authorization_anchor_writer.py`](../peak/db/engagement_authorization_anchor_writer.py),
and **creates no engagement record**. Head stays at `013_governed_identifier_collation_policy`; 13
migrations and 18 tables are unchanged, and there is **no migration 014 and no model change**.

It is the governed code path Phase 53 identified as missing: every other writer loads a stored
`Engagement` anchor and matches its scope against it, and nothing could create that anchor.

- **Create-only.** One `session.add`, one commit. No `UPDATE`, `DELETE`, `merge`, bulk operation,
  raw SQL, or schema operation. `SELECT` + `INSERT` remains sufficient.
- **One pair, not a hole.** `engagements` stays on `PROHIBITED_TABLES`; the writer travels a
  separate one-pair gate, `engagements` / `create_engagement_authorization_anchor`. The generic
  allowlist is unchanged at 13 tables and 15 actions, and `clients` is unreachable by any path.
- **No new columns.** The anchor's primary key is its idempotency boundary, and the replay
  fingerprint is recomputed from the stored row's governed fields — so no `idempotency_key` /
  `payload_fingerprint` column and no migration were needed. A conflicting definition under the
  same id is denied, never overwritten.

The Phase 51 no-write / no-enablement decision is unchanged, and the first production anchor
creation remains separately approved future work. See
[`PHASE54_CONTROLLED_ENGAGEMENT_AUTHORIZATION_ANCHOR_WRITER.md`](PHASE54_CONTROLLED_ENGAGEMENT_AUTHORIZATION_ANCHOR_WRITER.md).

## Phase 55 — classifying durable internal test engagements (planning only)

Phase 55 is **plan and classification only**: no production write, no writer enablement, no
engagement record of any kind, no intake note, no synthetic smoke record, no capsule published. Head
stays at `013_governed_identifier_collation_policy`; 13 migrations, 18 tables, and 12 writers are
unchanged, and there is **no migration 014 and no model change**.

Peak will eventually keep a small number of **durable internal test / training engagements** — used
for training, live testing, and demonstration, retained deliberately, never client-accessible, and
carrying no real client data unless separately and explicitly authorized. They are a distinct
category from disposable synthetic smoke records (still disallowed) and from the in-memory synthetic
fixtures the harnesses build.

Inspection found the scaffold cannot express that yet:

- **`Engagement` has no classification columns.** It carries `id`, `client_id`, `engagement_label`,
  `status` plus the governance/audit mixins — and none of the `client_facing_approved` /
  `capsule_candidate_ready` / `publication_allowed` real booleans that eight other record tables use.
- **No workaround is sound.** `authorization_scope` would be overloaded onto an orthogonal axis;
  `fixture_test` is refused for anchors because they need live client/engagement identity;
  `engagement_label` and `id`-prefix conventions are too fragile to carry governance; and
  `details_json` is documented as non-governance detail only.

**Recommended next phase: Phase 56 adds the governed classification columns, extends the anchor
writer to validate them, and creates no records.** The Phase 51 no-write / no-enablement decision is
unchanged. See
[`PHASE55_INTERNAL_TEST_ENGAGEMENT_CLASSIFICATION.md`](PHASE55_INTERNAL_TEST_ENGAGEMENT_CLASSIFICATION.md).

## Phase 56 — engagement classification columns

Migration `014_engagement_classification` adds four real columns to `engagements`:
`engagement_category` (governed string; `real_client` / `internal_test`), `real_client_data`,
`client_accessible`, and `capsule_publication_authorized`. Head moves to `014`; **18 tables and 12
writers are unchanged**, no table was added, and `Client` was not altered.

Defaults are the safe direction — an unclassified row is a real client engagement, and publication
is never granted by default. Additive and reversible, with no INSERT or seed data. **Phase 56
creates no records**. Production was still at 013 at the time; migration 014 was applied to
production later, in **Phase 58** (see below). See
[`PHASE56_INTERNAL_TEST_ENGAGEMENT_SUPPORT.md`](PHASE56_INTERNAL_TEST_ENGAGEMENT_SUPPORT.md).

## Phase 57 — the read-side isolation primitive

[`peak/db/engagement_read_isolation.py`](../peak/db/engagement_read_isolation.py) turns the Phase 56
classification columns into enforcement. It adds no table, model, writer, migration, or allowlist
pair — head stays at `014_engagement_classification` with 18 tables and 12 writers.

It exposes row predicates (`is_client_visible`, `is_visible_in_mode`, `is_publication_eligible`) and
SQLAlchemy filter clauses (`client_visible_filter`, `internal_admin_filter`,
`publication_eligible_filter`, `apply_read_isolation`). The default mode is client-facing and
**excludes internal test engagements**; internal/admin views must explicitly opt in. The helper opens
no connection and executes nothing — the caller owns the session. See
[`PHASE57_INTERNAL_TEST_READ_ISOLATION.md`](PHASE57_INTERNAL_TEST_READ_ISOLATION.md).

## Phase 58 — migration 014 applied to production

Phase 58 applies migration `014_engagement_classification` **to production**, using the production
migration credential and the explicit revision (never an open-ended `upgrade head`). It adds no
table, model, writer, or allowlist pair — head stays at `014_engagement_classification` with **14
migrations, 18 tables, and 12 writers** — but production now matches it. **Production schema now
supports the Engagement classification fields** `engagement_category`, `real_client_data`,
`client_accessible`, and `capsule_publication_authorized`, plus
`ix_engagements_engagement_category`.

**The production verifier's expected head is now `014`, not `013`.**
[`tools/production_mysql_collation_verify.py`](../tools/production_mysql_collation_verify.py) tracks
the live production head deliberately, and the pin moves only when a migration has actually been
applied there. `engagement_category` is a `governed_scope` column, so it joins the deterministic
collation posture and the production governed-column count moves from 211 to 212.

**No production application records were created**, read, updated, or deleted; **no internal test
engagement was created**; no writer was invoked; and no runtime credential was used. The first
internal test engagement anchor remains **separately approved** future work. The read-side isolation
primitive exists, but future client-facing paths must actually use it. Properly gated production
test records are allowed later — only with `engagement_category=internal_test`,
`real_client_data=false`, `client_accessible=false`, and a reserved test namespace/value. See
[`PHASE58_PRODUCTION_MIGRATION_014_VERIFICATION.md`](PHASE58_PRODUCTION_MIGRATION_014_VERIFICATION.md).

## Phase 59 — the first durable internal test engagement anchor

Phase 59 creates **one** durable `internal_test` engagement anchor in production through the
unchanged Phase 54/56 controlled writer — Peak's first production application record. It adds no
migration, table, model, writer, or allowlist pair: head stays at `014_engagement_classification`
with **14 migrations, 18 tables, and 12 writers**, `engagements` stays prohibited generically, and
`clients` stays never-writable.

The anchor is `engagement_category=internal_test`, `real_client_data=false`,
`client_accessible=false`, `capsule_publication_authorized=true`, in the reserved `99999` client
namespace, scope `internal_peak_only`, `status`/`lifecycle_status` `active`, `review_status`
server-stamped `needs_review`. Classification lives in **real columns** — not in `details_json`,
the label, the scope, or the id prefix.

It is a **durable internal/admin record, not disposable smoke**: runtime holds `SELECT` + `INSERT`
and no `DELETE`, so it cannot be cleaned up and is not meant to be. **No Client record, no intake
note, no downstream record, and no capsule** were created; publication *eligibility* follows from
the compound internal_test / no-real-client-data / not-client-accessible rule and is not
publication. A new operator utility,
[`tools/create_internal_test_engagement_anchor.py`](../tools/create_internal_test_engagement_anchor.py),
holds the one hard-coded packet and is dry-run by default. See
[`PHASE59_FIRST_INTERNAL_TEST_ENGAGEMENT_ANCHOR.md`](PHASE59_FIRST_INTERNAL_TEST_ENGAGEMENT_ANCHOR.md).

## Phase 60 — intake taxonomy V0 and the first internal test intake note

Phase 60 creates **one** durable `internal_test` intake note in production through the unchanged
Phase 34 controlled writer, attached to the Phase 59 anchor. It adds no migration, table, model,
writer, or allowlist pair: head stays at `014_engagement_classification` with **14 migrations, 18
tables, and 12 writers**.

The note is tied to `internal_test_001` / `99999` / `internal_peak_only`, is review-gated and
non-final (`review_status=needs_review`, `lifecycle_status=draft`), and is **not client-facing** —
`client_facing_approved`, `publication_allowed`, `capsule_candidate_ready`, `execution_allowed`, and
`financial_verified` are all false. It contains **no real client data** and is a durable
internal/admin record, **not disposable smoke**.

**No Client record, no additional Engagement record, no downstream record, and no capsule** were
created. Authorization came from the stored engagement: the writer loads the `Engagement` row and
requires the request scope to match the stored scope — identity matching alone is not sufficient.

**The note body is not in this repository.** Intake prose belongs only in the managed DB, so the
operator utility
[`tools/create_internal_test_intake_note.py`](../tools/create_internal_test_intake_note.py) loads it
at runtime from a file outside the repo and prints only its length and SHA-256. Intake questions are
now grounded in
[`PEAK_INTAKE_QUESTION_TAXONOMY_V0.md`](PEAK_INTAKE_QUESTION_TAXONOMY_V0.md). See
[`PHASE60_FIRST_INTERNAL_TEST_INTAKE_NOTE.md`](PHASE60_FIRST_INTERNAL_TEST_INTAKE_NOTE.md).

## Phase 61 — the internal test intake review decision

Phase 61 creates **one** `review_records` row in production through the unchanged Phase 22
controlled writer, recording an internal review decision on the Phase 60 intake note. It adds no
migration, table, model, writer, or allowlist pair: head stays at `014_engagement_classification`
with **14 migrations, 18 tables, and 12 writers**.

The writer keeps the **authorization anchor** (`request.subject`, which must be the `engagement`)
separate from the **reviewed target** (`draft.subject_record_id`, stored as `target_id`), so the
intake note `intn_b8b86b8c196c4595` is reviewed under the `internal_test_001` anchor's authority
without overloading either field. The bundle-shaped `internal_reviewer_decision_records` draft has
no reviewed-target field and was rejected for that reason.

Decision `approve_internal`, `authoritative=false`, `approved_internal` / `draft`,
`client_facing_approved=false`, `capsule_candidate_ready=false`. **The decision authorizes moving
toward source/evidence collection, not report or capsule publication.** Covered and incomplete
taxonomy categories and eight next evidence requests are recorded as concise findings — category
labels and gap descriptors, never note prose. **No Client record, no additional Engagement, no
second intake note, and no source/evidence/report/capsule record** were created. See
[`PHASE61_INTERNAL_TEST_INTAKE_REVIEW_DECISION.md`](PHASE61_INTERNAL_TEST_INTAKE_REVIEW_DECISION.md).

## Phase 62 — the internal test source/evidence request plan

Phase 62 is **planning-only and creates no production record.** It contacts no database, invokes no
writer, and reads no environment file. Head stays at `014_engagement_classification` with **14
migrations, 18 tables, and 12 writers**; no migration, model, writer, or allowlist pair is added.

The Phase 61 review decision now feeds a **concrete source/evidence request plan** — ten prioritized
requests, each mapped to Intake Taxonomy V0 categories and to the downstream deliverable it feeds.
**Evidence and source collection precede analysis, report drafting, and capsule publication**, and
report drafting and capsule publication remain unauthorized.

**Phase 63 should create the first internal_test source ingestion record** if the inspected
writer contract supports it — meaning a real internal_test artifact exists at write time; if none
does, Phase 63 defers rather than fabricates a packet reference. Inspecting the existing writers
gives that path: the unchanged Phase 24
[`source_ingestion_writer.py`](../peak/db/source_ingestion_writer.py) →
`source_ingestion_records` / `create_source_ingestion_record`, anchored on the stored
`internal_test_001` engagement. It is metadata-only by contract and never persists a packet payload.
`evidence_references` comes **after** source ingestion, not before: its columns assert
`evidence_status`, `reliability`, and characterization that presuppose a registered source.

One honest gap is recorded: a **request that has been made but not yet fulfilled** has no writable
representation. `source_system_references` models exactly that (`source_system_access_status`:
`not_requested`/`requested`/…) but has no writer and no allowlist pair. No writer was added; the
request state lives in the plan document instead. See
[`PHASE62_INTERNAL_TEST_SOURCE_EVIDENCE_REQUEST_PLAN.md`](PHASE62_INTERNAL_TEST_SOURCE_EVIDENCE_REQUEST_PLAN.md).

## Phase 63 — the first internal test source ingestion record

Phase 63 creates **one** `source_ingestion_records` row in production through the unchanged Phase 24
controlled writer, registering the R8 system-of-record and data-export map artifact
(`ing_4fb70519cbf84401`). It adds no migration, table, model, writer, or allowlist pair: head stays
at `014_engagement_classification` with **14 migrations, 18 tables, and 12 writers**.

**Only metadata was persisted** — packet reference id, schema name/version, source type, a logical
`internal-test-artifact://` location reference, and the `packet_hash`. The artifact body lives
**outside the repository** and never enters the database; the writer refuses any draft carrying
`packet_payload`, `raw_packet_content`, `raw_content`, `payload`, or a secret-named attribute.

Posture is `needs_review` / `draft`, `authoritative=false`, `client_facing_approved=false`,
`capsule_candidate_ready=false`. **No evidence reference was created** — `evidence_references`
assert `evidence_status` and `reliability`, so they still come **after** source ingestion, never
before. No Client record, no additional Engagement, no intake note, no review record, and no
report or capsule record were created. See
[`PHASE63_FIRST_INTERNAL_TEST_SOURCE_INGESTION.md`](PHASE63_FIRST_INTERNAL_TEST_SOURCE_INGESTION.md).

## Phase 64 — the R1–R7 source artifact collection plan

Phase 64 is **planning-only and creates no production record.** Head stays at
`014_engagement_classification` with **14 migrations, 18 tables, and 12 writers**; no migration,
model, writer, allowlist pair, or operator utility is added.

**Phase 63 registered R8** (`ing_4fb70519cbf84401`), and **Phase 64 defines the R1–R7 artifact
collection** that follows it: for each request, an artifact type, minimum expected fields or document
sections, an external filename under the approved out-of-repo directory, a logical
`internal-test-artifact://phase65/…` location reference, a `packet_reference_id`, schema name and
version, source type, a SHA-256 hash requirement, taxonomy categories, and the downstream
deliverable.

**Artifact bodies remain outside the repository** and out of the database. Source ingestion persists
metadata only — packet reference, schema, source type, logical location, hash.

**Phase 65 should create the external artifact(s) and register `source_ingestion_records`, not
`evidence_references` yet.** The recommended batch is R2 then R1: the R8 map records R2 as the only
unblocked request, and R1 is uninterpretable without the item master. **Capsule publication remains
unauthorized despite the live AgentNet resolver.** See
[`PHASE64_INTERNAL_TEST_R1_R7_SOURCE_ARTIFACT_COLLECTION_PLAN.md`](PHASE64_INTERNAL_TEST_R1_R7_SOURCE_ARTIFACT_COLLECTION_PLAN.md).

## Phase 65 — the R2 and R1 internal test source ingestion records

Phase 65 creates **two** `source_ingestion_records` rows in production (`ing_884c94df03c34908` and
`ing_a2abb497f471458e`) through the unchanged Phase 24
writer — **R2 (SKU/item master export) first, then R1 (current inventory by SKU and location)**.
Head stays at `014_engagement_classification` with **14 migrations, 18 tables, and 12 writers**; no
migration, model, writer, or allowlist pair is added.

**R2 first** because the Phase 63 R8 map records it as the only unblocked request and because it is
the interpretive key for R1. **R1's location dimension is registered as explicitly provisional** —
the R8 location/bin naming model is unconfirmed, so location-attributed claims derived from R1 must
carry degraded reliability until R9 lands.

**Artifact bodies remain outside the repository** and out of the database. Only metadata was
persisted — packet reference, schema name and version, source type, a logical
`internal-test-artifact://phase65/…` location reference, and a SHA-256 hash. No artifact body was
printed, committed, or stored, and no fixture or sample packet was committed.

**No evidence reference, report, capsule, or client-facing output was created**, and no Client,
Engagement, intake, or review record. **R3–R7 remain deferred** behind their unresolved R8 blockers,
with R9 (the location/bin naming model) the natural next request. **AgentNet resolver publication
remains unauthorized** despite the live public resolver. See
[`PHASE65_R1_R2_INTERNAL_TEST_SOURCE_INGESTION.md`](PHASE65_R1_R2_INTERNAL_TEST_SOURCE_INGESTION.md).

## Phase 66 — the internal test source ingestion review decision

Phase 66 creates **one** `review_records` row in production (`rev_bf7f18a13d8f461c`) through the
unchanged Phase 22 review writer, recording the internal review decision on the **R2** source ingestion record
(`ing_884c94df03c34908`). Head stays at `014_engagement_classification` with **14 migrations, 18
tables, and 12 writers**; no migration, model, writer, or allowlist pair is added.

**No field is overloaded.** The review writer already separates the authorization anchor
(`request.subject`, required to be the engagement) from the reviewed target (`subject_record_id` /
`subject_record_type`, stored as `target_id`), so `source_ingestion_record` is an honest
`subject_record_type` — the shape Phase 61 used for the intake note.

**The decision is `approve_internal` and non-authoritative**, authorizing only a future
`evidence_reference` about **item-master source availability and data readiness**. **No evidence
reference was created yet.** R1's location dimension stays provisional, **R8 stays provisional**
(`needs_review` / `draft` / `authoritative=false`), **R3–R7 stay deferred**, and report drafting,
capsule candidacy, client-facing output, and **AgentNet resolver publication remain unauthorized**
despite the live public resolver.

**No artifact body was read, printed, committed, or stored.** See
[`PHASE66_INTERNAL_TEST_SOURCE_INGESTION_REVIEW_DECISION.md`](PHASE66_INTERNAL_TEST_SOURCE_INGESTION_REVIEW_DECISION.md).

## Phase 67 — the first internal test evidence reference

Phase 67 creates **one** `evidence_references` row in production (`evid_56437d9b9c764560`)
through the unchanged Phase 21 evidence writer, for the Phase 66-approved **R2** source ingestion record (`ing_884c94df03c34908`),
supported by review record `rev_bf7f18a13d8f461c`. Head stays at `014_engagement_classification`
with **14 migrations, 18 tables, and 12 writers**; no migration, model, writer, or allowlist pair is
added.

**No field is overloaded.** `source_reference_id` carries the registered packet reference,
`source_location` carries a *logical* in-Peak locator for the R2 record, `evidence_type` /
`source_type` are `document` (the artifact is a field-level export description, not an export of
rows), and the claim and its limits live in the free descriptive text. Three contract limits are
stated rather than worked around: the table has **no typed related-object column** (so the
supporting review is named in text), the writer does **not expose `evidence_status`** (the row takes
the `collected` default), and the writer does **not persist `draft.reasons`** (so the limits live in
`normalized_summary` / `observed_condition`).

**The evidence scope is item-master source availability and data readiness only.** **No inventory
accuracy conclusion was made.** The table has **no `authoritative` column**, so that claim is
structurally impossible, and the writer server-stamps `needs_review` / `draft`. R1's location
dimension stays provisional pending R9, **R8 stays provisional** (`needs_review` / `draft` /
`authoritative=false`), **R3–R7 stay deferred**, and report drafting, capsule candidacy,
client-facing output, and **AgentNet resolver publication remain unauthorized** despite the live
public resolver.

**No artifact body was read, printed, committed, or stored.** See
[`PHASE67_FIRST_INTERNAL_TEST_EVIDENCE_REFERENCE.md`](PHASE67_FIRST_INTERNAL_TEST_EVIDENCE_REFERENCE.md).

## Phase 68 — the R2 evidence reference review decision

Phase 68 creates **one** `review_records` row in production (`rev_de2b6e73f6c94c67`) through the
unchanged Phase 22 review writer, recording the internal review decision on the Phase 67 **R2 evidence reference**
(`evid_56437d9b9c764560`). Head stays at `014_engagement_classification` with **14 migrations, 18
tables, and 12 writers**; no migration, model, writer, or allowlist pair is added.

**No field is overloaded.** The review writer separates the authorization anchor
(`request.subject`, required to be the engagement) from the reviewed target (`subject_record_id` /
`subject_record_type`, stored as `target_id`), and persists `draft.reasons` into `details_json`, so
the limits are stored as findings. `subject_record_type='evidence_reference'` is derived from the
reviewed table's name — the convention Phase 61 and Phase 66 used; the older fixtures' label
`normalized_evidence_record` names the Phase 14 *in-memory* output, which is never stored.

**The decision is `approve_internal` and non-authoritative**, authorizing only a future **internal
assessment finding** about item-master source availability and data readiness. **The evidence
remains low confidence and non-authoritative**, and **no inventory accuracy conclusion was made**.
The reviewed evidence row is **not modified** — the review writer has no `UPDATE` path. R1's
location dimension stays provisional pending **R9** (the likely Phase 69 collection), **R8 stays
provisional** (`needs_review` / `draft` / `authoritative=false`), **R3–R7 stay deferred**, and
report drafting, capsule publication, client-facing output, and **AgentNet resolver publication
remain unauthorized** despite the live public resolver.

**No artifact body was read, printed, committed, or stored.** See
[`PHASE68_R2_EVIDENCE_REFERENCE_REVIEW_DECISION.md`](PHASE68_R2_EVIDENCE_REFERENCE_REVIEW_DECISION.md).

## Phase 69 — the R9 location/bin naming model source ingestion

Phase 69 creates **one** `source_ingestion_records` row in production (`ing_64b2e2648ac1402b`) through
the unchanged **Phase 24** writer, registering the internal test **R9 location/bin naming model**
artifact under the stored `internal_test_001` / `99999` / `internal_peak_only` anchor. **No
migration, no migration 015, no model, no writer, and no allowlist pair** — head stays
`014_engagement_classification` with 14 migrations, 18 tables, and 12 writers.

**Metadata only, as the writer requires.** The row stores the packet reference
(`pkt_internal_test_r9_location_bin_model_001`, persisted as `source_reference_id`), schema name and
version, source type, the **logical** location reference
`internal-test-artifact://phase69/r9-location-bin-naming-model-v1`, and the `packet_hash` — a
SHA-256 over the exact artifact bytes. **The artifact body lives outside the repository** and never
enters the database, the repository, or the operator's output. The artifact itself is a field-level
and concept-level description of location hierarchy, naming, type/status, availability treatment,
and virtual/staging/hold/damaged/unavailable concepts, with **no location identifiers, item values,
quantities, or row-like export data** of any kind.

**Collection, not review or validation.** R9 was collected to unblock a future **R1
location-dimension review**. It **does not validate inventory quantities**, is not an inventory
accuracy finding, **does not make R1 evidence-ready by itself**, and **must be reviewed before use
in evidence references**. It landed `needs_review` / `draft` / `active`, `authoritative=false`.

**No evidence reference, no review record, no report, no capsule, no client-facing output, and no
AgentNet publication record was created.** R1's location dimension stays provisional, **R8 stays
provisional** (`needs_review` / `draft` / `authoritative=false`, precedence unconfirmed), **R3–R7
stay deferred**, and report drafting, capsule publication, client-facing output, and **AgentNet
resolver publication remain unauthorized** despite the live public resolver.

**No artifact body was read into memory as text, printed, committed, or stored.** See
[`PHASE69_R9_LOCATION_BIN_MODEL_SOURCE_INGESTION.md`](PHASE69_R9_LOCATION_BIN_MODEL_SOURCE_INGESTION.md).

## Phase 70 — the R9 source ingestion review decision

Phase 70 creates **one** `review_records` row in production (`rev_3ecc0891f4fe48ce`) through the
unchanged **Phase 22** writer, recording the internal review decision on the Phase 69 **R9 source
ingestion record** (`ing_64b2e2648ac1402b`) under the stored `internal_test_001` / `99999` /
`internal_peak_only` anchor. **No migration, no migration 015, no model, no writer, and no allowlist
pair** — head stays `014_engagement_classification` with 14 migrations, 18 tables, and 12 writers.

**No field is overloaded.** The review writer separates the authorization anchor (`request.subject`,
required to be the engagement) from the reviewed target (`subject_record_id` /
`subject_record_type`, stored as `target_id`), and persists `draft.reasons` into `details_json`, so
the limits are stored as findings. `subject_record_type='source_ingestion_record'` is the same value
**Phase 66** used for the R2 source-ingestion review — the reviewed target is the same class of
record.

**The decision is `approve_internal` and non-authoritative**, approving R9 **only for future
evidence work about R1 location-dimension readiness**. The recorded central limit is that **R9 is a
question set, not an answered model**: every hierarchy level and type/status field is
presence-unknown, so R9 defines what must be measured rather than reporting what is true.

**No evidence reference was created.** **R1's location dimension remains provisional**, **R9 does
not validate inventory quantities**, **R8 authority precedence is not resolved**, **R5 WMS scope is
not resolved**, **R3–R7 stay deferred**, and report drafting, capsule publication, client-facing
output, and **AgentNet resolver publication remain unauthorized** despite the live public resolver.
The reviewed R9 row is **not modified** — the review writer has no `UPDATE` path.

**No artifact body was read, printed, committed, or stored.** See
[`PHASE70_R9_SOURCE_INGESTION_REVIEW_DECISION.md`](PHASE70_R9_SOURCE_INGESTION_REVIEW_DECISION.md).

## Phase 71 — the R1/R9 evidence-readiness plan (planning-only)

Phase 71 creates **no database record at all**. It is a planning phase: no production access, no
production write, **no `evidence_reference`, no `review_record`, no `source_ingestion_record`**, no
report, no capsule, no client-facing output, and no AgentNet or resolver publication. **No
migration, no migration 015, no model, no writer, no allowlist pair, and no operator utility** —
head stays `014_engagement_classification` with 14 migrations, 18 tables, and 12 writers.

**The finding:** R1 cannot yet support a location-dimension evidence reference because the collected
R9 artifact **defines the questions that must be answered but does not answer them**. The gap is
concrete — R1 carries one required location identifier plus one *optional* level marker, both marked
provisional, against R9's six-level hierarchy, and location is a **grain key** in R1's declared
grain. The plan lists **15 required measured answers** as the gate, including both the "readable"
and the "not reliable enough" thresholds, fixed in advance.

**R1 remains provisional**; **R9 is reviewed but non-authoritative and remains a question set, not
an answered model**; R8 and R5 remain unresolved; **R3–R7 remain deferred**. The next useful
production step is likely **R10 — a measured location model answer set source ingestion** (Phase
72), through the unchanged Phase 24 writer, landing `draft` / `needs_review` / `authoritative=false`
and non-authoritative until reviewed. That is a **recommendation only**; report drafting, capsule
publication, client-facing output, and **AgentNet resolver publication remain unauthorized**.

**No artifact body was read into the repository, printed, or committed.** See
[`PHASE71_R1_R9_EVIDENCE_READINESS_PLAN.md`](PHASE71_R1_R9_EVIDENCE_READINESS_PLAN.md).

## Phase 72 — the R10 location model answer set source ingestion

Phase 72 creates **one** `source_ingestion_records` row in production (`ing_b26d137a0a334ee9`) through
the unchanged **Phase 24** writer, registering the internal test **R10 measured location model
answer set** under the stored `internal_test_001` / `99999` / `internal_peak_only` anchor. **No
migration, no migration 015, no model, no writer, and no allowlist pair** — head stays
`014_engagement_classification` with 14 migrations, 18 tables, and 12 writers.

**Metadata only, as the writer requires.** The row stores the packet reference
(`pkt_internal_test_r10_location_model_answer_set_001`, persisted as `source_reference_id`), schema
name and version, source type, the **logical** location reference
`internal-test-artifact://phase72/r10-location-model-answer-set-v1`, and the `packet_hash` — a
SHA-256 over the exact artifact bytes. **The artifact body lives outside the repository** and never
enters the database, the repository, or the operator's output.

**R9 defines the questions; R10 supplies the measured answers.** All 15 Phase 71 checklist items
carry an explicit answer state, and **R10 includes negative and unknown answers** — none of the 15
was dropped or softened, and 11 of 15 are negative, unknown, or blocked. The honest measurement
basis is the registered artifact descriptions only; no live ERP, WMS, or client system exists in this
internal_test engagement. The headline finding is that **R1's location dimension is not currently
readable**.

**Collection, not review or validation.** R10 landed `needs_review` / `draft` /
`authoritative=false` and **must be reviewed before use in evidence references**. It **does not
validate inventory quantities**, **does not lift R1's provisional location marking**, **does not
resolve R8 authority precedence**, and **does not resolve R5 WMS scope**.

**No evidence reference, no review record, no report, no capsule, no client-facing output, and no
AgentNet publication record was created.** **R1 remains provisional**, **R3–R7 stay deferred**, and
report drafting, capsule publication, client-facing output, and **AgentNet resolver publication
remain unauthorized** despite the live public resolver. Likely **Phase 73** is the R10
source-ingestion review decision.

**No artifact body was read into memory as text, printed, committed, or stored.** See
[`PHASE72_R10_LOCATION_MODEL_ANSWER_SET_SOURCE_INGESTION.md`](PHASE72_R10_LOCATION_MODEL_ANSWER_SET_SOURCE_INGESTION.md).

## Phase 73 — the R10 review and the location-readiness evidence

Phase 73 creates **two** rows in production through unchanged writers: one `review_records` row
(`rev_9b6b0a67bae54a51`, Phase 22 writer) reviewing the R10 source ingestion
(`ing_b26d137a0a334ee9`), and one `evidence_references` row (`evid_f26c5f8fc0aa44d4`, Phase 21
writer) recording the location-readiness finding — both under the stored `internal_test_001` /
`99999` / `internal_peak_only` anchor. **No migration, no migration 015, no model, no writer, no
allowlist pair, and no new operator or harness** — head stays `014_engagement_classification` with
14 migrations, 18 tables, and 12 writers.

**No field is overloaded.** The review writer separates the authorization anchor from the reviewed
target (`subject_record_type='source_ingestion_record'`, the Phase 66/70 convention). The evidence
writer has no typed related-object slots, so the supporting R1/R9/R10 record ids live in the
`summary` and `observed_condition` text as concise sanitized references — the Phase 67 pattern.

**The review is `approve_internal` and non-authoritative**, approving R10 only for
location-dimension data-readiness evidence and accepting its unfavourable answer set (11 of 15
items negative, unknown, or blocked) as a valid input. **The evidence finding is unfavourable**:
R1's location dimension is **not currently readable** and **not reliable enough** for
location-attributed evidence under thresholds fixed in advance — a **data-readiness and reliability
finding, not an inventory accuracy finding**.

**R1 remains provisional**, **R8 and R5 remain unresolved**, **R3–R7 stay deferred**, and report
drafting, capsule publication, client-facing output, and **AgentNet resolver publication remain
unauthorized** despite the live public resolver. **No artifact body was read, printed, committed, or
stored.** See
[`PHASE73_R10_REVIEW_LOCATION_READINESS_EVIDENCE.md`](PHASE73_R10_REVIEW_LOCATION_READINESS_EVIDENCE.md).

---

## Phase 74 — the location-readiness evidence review and the minimal internal assessment outline

Phase 74 creates **two** rows in production through unchanged writers: one `review_records` row
(`rev_d94d4711ac12420b`, Phase 22 writer) reviewing the Phase 73 location-readiness evidence
reference (`evid_f26c5f8fc0aa44d4`), and one `internal_assessment_report_drafts` row
(`iard_50814a78a44243c2`, Phase 37 writer, planned by the DB-free Phase 36 planner) — both under the
stored `internal_test_001` / `99999` / `internal_peak_only` anchor. **No migration, no model, no
writer, no allowlist pair, and no new operator or harness** — head stays
`014_engagement_classification` with 14 migrations, 18 tables, and 12 writers. This is the first use
of `internal_assessment_report_drafts` (the sixteenth table, added by migration
`010_internal_assessment_report_drafts`) in the internal_test chain.

**No field is overloaded.** The review writer keeps the authorization anchor (`request.subject`, the
engagement) apart from the reviewed target (`subject_record_type='evidence_reference'`, the Phase 68
convention), and the finding text lives in `draft.reasons` → `details_json`. The report-draft writer
stores **structure and reference ids only**: `output_status` is fixed at `plan_persisted` precisely
so a row can never be misread as report prose, `audience` is forced to `internal`, and every
approval / financial / capsule / publication / execution flag is hard-coded `false` with
`requires_human_review=true`.

**The row is an outline, not a report:** five sections (`evidence_summary`, `operational_findings`,
`system_data_readiness`, `evidence_gaps`, `next_steps_internal`), one finding candidate anchored to
`evid_f26c5f8fc0aa44d4`, zero recommendation candidates, zero open gaps. `inventory_risk_areas` was
excluded deliberately. The single finding candidate is honestly `blocked_no_review_support` — this
chain has `review_records`, not `review_bundle_records` — and no id was forced into
`review_bundle_record_ids` to clear it. `future_capsule_candidate_items_json` lists the three source
ingestion ids as a **named future gate**; no capsule candidate was created and
`capsule_candidate_ready` / `publication_allowed` are `false`.

**The assessment finding:** R1's location dimension is **not currently readable or reliable enough**
to carry location-attributed evidence under thresholds fixed in advance — a **data-readiness and
reliability finding, not an inventory accuracy finding**. **R1 remains provisional**, **R8 and R5
remain unresolved**, **R3–R7 stay deferred**, and report finalization, capsule publication,
client-facing output, and **AgentNet resolver publication remain unauthorized** despite the live
public resolver. **No artifact body was read, printed, committed, or stored.** See
[`PHASE74_LOCATION_READINESS_INTERNAL_ASSESSMENT.md`](PHASE74_LOCATION_READINESS_INTERNAL_ASSESSMENT.md).

---

## Phase 75 — the location assessment review support decision (no rows written)

Phase 75 creates **no production rows**. It evaluated whether the existing Phase 30
`review_bundle_records` writer could honestly supply the review support that Phase 74's finding
candidate `fnd_000` reports missing, and **declined the path**. Head stays
`014_engagement_classification` with 14 migrations, 18 tables, and 12 writers — **no migration,
model, writer, allowlist pair, schema, operator, or harness added**.

**Why `review_bundle_records` is the wrong table for this.** A bundle is the persistence counterpart
to the Phase 29 packet review orchestration boundary: subjects gathered from one processed packet and
queued **for** a human reviewer, readiness `ready_for_human_review`, with Phase 29's own warning that
"ready for human review does not mean approved". Phase 30 hard-stamps every row `needs_review` /
`draft` / `draft`, `authoritative=false`, `approval_allowed=false`, `requires_human_review=true`. It
is an **inbox item, not an attestation** — so satisfying a check named "review support" with one
would clear the block using a record whose stored meaning is that nothing has been reviewed yet.

**And it cannot hold the support that exists.** `ReviewBundleDraft` carries
`source_ingestion_record_ids`, `evidence_reference_ids`, `agent_task_queue_record_ids`, and
`subject_refs` — **no review-record field** — and `review_bundle_records` has no such column, the
model noting `details_json` holds safe references "never raw payload/content **or a final review
decision**". The declared `subject_refs` types are `source_ingestion_record`, `evidence_reference`,
`agent_task_queue_record`, `packet_processing_receipt`; there is no `review_record` type, and forcing
`rev_d94d4711ac12420b` into that free string is the exact misuse Phase 74 already refused in the
other direction. A Phase 75 bundle would also have been the first in the system with no
packet-processing run behind it.

**`fnd_000`'s `blocked_no_review_support` is a false negative from a vocabulary gap, not a governance
block** — the corroboration exists as `review_records`, which the Phase 36 planner has no reference
category for. The recommended fix is to leave the state as written; clearing it honestly is a
**Phase 36 planner contract change** requiring its own approved phase.

**Nothing moved.** The Phase 74 outline stays `plan_persisted` / `needs_review` / `draft`; the finding
stays **data-readiness / reliability only and must not be restated as inventory accuracy**; **R1
remains provisional**, **R8 and R5 remain unresolved**, **R3–R7 stay deferred**; and report
finalization, capsule publication, client-facing output, and **AgentNet resolver publication remain
unauthorized**. See
[`PHASE75_LOCATION_ASSESSMENT_REVIEW_SUPPORT.md`](PHASE75_LOCATION_ASSESSMENT_REVIEW_SUPPORT.md).

---

## Phase 76 — the R8 authority review and the R5 WMS scope clarification

Phase 76 creates **two** rows in production through unchanged writers: one `review_records` row
(`rev_1d9696e9218b4e35`, Phase 22 writer) reviewing the R8 source ingestion
(`ing_4fb70519cbf84401`), and one `source_ingestion_records` row (`ing_f7a4cc20f1f148c7`, Phase 24
writer) registering the **R5 WMS scope clarification** — both under the stored `internal_test_001` /
`99999` / `internal_peak_only` anchor. **No migration, model, writer, allowlist pair, schema,
operator, or harness** — head stays `014_engagement_classification` with 14 migrations, 18 tables,
and 12 writers.

**No field is overloaded.** The review writer separates the authorization anchor from the reviewed
target (`subject_record_type='source_ingestion_record'`, the Phase 66/70/73 convention), and the
finding text lives in `draft.reasons` → `details_json`. The source ingestion writer stores **packet
metadata only** — reference id, schema name and version, source type, the logical
`internal-test-artifact://phase76/…` location reference, and the SHA-256 `packet_hash`. The artifact
body stays outside the repository and out of the database.

**The R8 review approves framing, not precedence.** `approve_internal` / `authoritative=false`:
R8 is approved as a source-map and authority-precedence *framing* artifact. It **does not confirm
authority precedence**, because R8's own `authority_precedence_rule` carries status
`provisional_unconfirmed` with 2 items requiring confirmation first. R8 maps 7 exports (2 `expected`,
4 `uncertain`, 1 `partial`) with 5 of 7 blocked and 4 open questions left open. **Registration
integrity was deliberately not re-verified** — no `packet_hash` is committed to the repo and reading
the stored row would exceed this phase's permitted lookups.

**The R5 row is a blocker enumeration, not an answer.** It is **not** the Phase 64 "R5 receiving and
putaway" export, which remains uncollected under its own packet reference. 15 scope items resolve as
0 `answered_yes`, 1 `answered_no`, 3 `unknown`, 9 `not_measured`, 2 `blocked_by_r8` — unmeasured by
necessity, since this engagement has no live warehouse management, ERP, production, or client system,
and the artifact asserts no system landscape and carries no organisation or system names, item or SKU
values, quantities, or location, bin, aisle, rack, warehouse or site identifiers.

**Clarified, not resolved.** **R8 authority precedence and R5 WMS scope both remain unresolved**;
R5 stays `needs_review` / `draft` / `authoritative=false`. **No inventory accuracy conclusion** was
made, **R1 remains provisional**, **R3–R7 stay deferred**, the Phase 74 outline is unmodified, and
report finalization, capsule publication, client-facing output, and **AgentNet resolver publication
remain unauthorized**. See
[`PHASE76_R8_R5_BLOCKER_CLARIFICATION.md`](PHASE76_R8_R5_BLOCKER_CLARIFICATION.md).

---

## Phase 77 — parallel prep for the R5 clarification review and R8 prerequisites (no rows written)

Phase 77 creates **no production rows** and contacts no database. It is a preparation phase: three
read-only workstreams mapped (a) the exact review posture for the R5 WMS scope clarification
(`ing_f7a4cc20f1f148c7`), (b) R8's confirmation prerequisites, and (c) the remaining R3–R7 dependency
order. **No migration, model, writer, allowlist pair, schema, operator, or harness** — head stays
`014_engagement_classification` with 14 migrations, 18 tables, and 12 writers.

**Analysis was parallelized; production writes were not**, because none were performed. No writer was
invoked, no environment file sourced, no connection opened, and no artifact body read, printed, or
stored — artifact contact was limited to structural shape only.

**The proposed Phase 78 write is one row, fixed in advance:** a single `review_records` row against
`ing_f7a4cc20f1f148c7` through the unchanged Phase 22 writer — `approve_internal`,
`authoritative=false`, `approved_internal` / `draft` / `active`, both publication flags false —
approving the artifact as a **scope-blocker enumeration only**. Three fields must be carried that a
condensed reading omits, each of which otherwise denies **before any connection is opened**:
`subject.stored_authorization_scope` (blank is a denial reason in
`peak/persistence/governance.py:192-198`), the `draft.owner_id` / `client_id` / `engagement_id`
triple (`peak/db/review_writer.py:120-127`), and `draft.requested_by` / `draft.reviewer_role`.
Note also that the payload fingerprint (`peak/db/review_writer.py:87-109`) **excludes**
`source_phase`, so an idempotency rehearsal must vary a fingerprinted field to prove conflict
detection. Note that `authoritative=true` *is*
permitted by the writer for `approve_internal`; the non-authoritative posture is a **reviewer
decision, not a writer constraint**, and must be recorded as such.

**The content of R8's two confirmation prerequisites is not recorded anywhere in this repository.**
Only the shape is known — `authority_precedence_rule.confirmation_required_before` is an array of
length 2, a count already on record in Phase 76. **The two strings themselves were never read.** The
Phase 77 doc reconstructs their likely content by inference from downstream blocked items and labels
it as inference. This makes Phase 76's recommended next step unactionable from the
repo alone, and it is the largest remaining unknown in the dependency graph.

**A second label collision was identified.** Phase 62 defines **R10** as a target metric, baseline,
and deadline statement (priority *optional*, still uncollected), while Phase 71 onward uses **R10**
for the location model answer set (`ing_b26d137a0a334ee9`) — the same hazard Phase 76 wrote a naming
rule for in the R5 case, with no equivalent rule yet written for R10.

**Scoping recorded.** R4 is the only item inside R3–R7 that Phase 62 marks *required* — a priority
marking, not a dependency. **R4 is conditionally required / scope-dependent**, becoming required only
if a refreshed assessment's scope includes count or variance reconciliation; for the current narrow
location-dimension data-readiness track it is **not** required, and R3, R4, R6, R7, and the Phase 64
R5 export may all remain deferred for Internal MVP. Widening to R4 would widen the finding into
inventory accuracy or variance, which this chain does not claim. *(An earlier Phase 77 revision
overstated R4 as automatically required; corrected in Phase 78.)* A second label collision was also
recorded: Phase 62's **R10**
(target metric/baseline/deadline, *optional*, uncollected) is a different artifact from Phase 71+'s
**R10** (location model answer set), documented without rewriting either record.

**Nothing moved.** **R8 authority precedence and R5 WMS scope both remain unresolved**; the R5 WMS
scope clarification stays `needs_review` / `draft` / `authoritative=false`; the **Phase 64 R5
receiving/putaway export remains uncollected**; **R1 remains provisional**; **R3–R7 stay deferred**;
the Phase 74 outline is unmodified with `fnd_000` still `blocked_no_review_support`; **no inventory
accuracy conclusion** was made; and report finalization, capsule publication, client-facing output,
and **AgentNet resolver publication remain unauthorized**. See
[`PHASE77_PARALLEL_PREP_R8_R5.md`](PHASE77_PARALLEL_PREP_R8_R5.md).

---

## Phase 78 — the R5 WMS scope clarification review and the R4 scope correction

Phase 78 creates **one** row in production through an unchanged writer: a `review_records` row
(`rev_e283136f679a46dd`, Phase 22 writer) reviewing the R5 WMS scope clarification source ingestion
(`ing_f7a4cc20f1f148c7`), under the stored `internal_test_001` / `99999` / `internal_peak_only`
anchor. **No migration, model, writer, allowlist pair, schema, operator, or harness** — head stays
`014_engagement_classification` with 14 migrations, 18 tables, and 12 writers. Execution used a
temporary scratchpad executor outside the repository; nothing persistent was added.

**Approved as an enumeration, not an answer.** `approve_internal` / `authoritative=false` /
`approved_internal` / `draft` / `active`, both publication flags false. The artifact still resolves
**0 of 15 items favourably**. `authoritative=false` is a **reviewer decision, not a writer
constraint** — the writer's `approve_internal` validation never inspects the field.

**Registration integrity is not claimed.** The review writer has no path that reads or compares
`packet_hash`, so the review evaluates the artifact **as registered** and makes no hash or integrity
confirmation.

**Idempotency was rehearsed correctly.** Off-production against temporary SQLite, varying `reasons` —
a field the payload fingerprint covers — yielded `idempotency_conflict`; varying only `source_phase`
yielded `idempotent_replay`, since `_payload_fingerprint` excludes it. The production write returned
`created`; an identical replay returned `idempotent_replay` with `database_write_made=false`,
confirming exactly one row.

**R8's prerequisites are now known rather than inferred, and Phase 77's inference was wrong.** Read
from the local artifact after a safety screen and recorded as **sanitized concepts only**:
**quantitative findings**, and **an evidence reliability rating**. Phase 77 had inferred a
system-of-record designation and a tie-break rule; neither is what the artifact records. The
precedence rule already states a direction — an ERP-class source over a spreadsheet-class source for
item-master and balance data — so what is missing is its *confirmation*, not its content, and the two
gates are **evidentiary-quality gates**, meaning confirmation is **measurement work, not
documentation work**. **R8 authority precedence remains unresolved** and R8 remains non-authoritative;
no production row was read and no R8 integrity check is claimed.

**R4 corrected to conditionally required.** R4 is the only Phase 62-*required* item inside R3–R7 — a
priority marking, not a dependency — and it is **required only if a refreshed assessment's scope
includes count or variance reconciliation**. The current location-dimension data-readiness track is
not so scoped, so R4 stays deferred; widening to it would widen the finding into inventory accuracy
or variance, which this chain does not claim.

**Nothing else moved.** **R5 WMS scope remains unresolved**; the **Phase 64 R5 receiving/putaway
export remains uncollected**; **R1 remains provisional**; **R3, R4, R6, R7 stay deferred**; the Phase
74 outline is unmodified with `fnd_000` still `blocked_no_review_support`; **no inventory accuracy
conclusion** was made; and report finalization, capsule publication, client-facing output, and
**AgentNet resolver publication remain unauthorized**. See
[`PHASE78_R5_WMS_SCOPE_REVIEW.md`](PHASE78_R5_WMS_SCOPE_REVIEW.md).

---

## Phase 79 — the R8 measurement-feasibility source ingestion

Phase 79 creates **one** row in production through an unchanged writer: a `source_ingestion_records`
row (`ing_0d671226f2ba4760`, Phase 24 writer) registering an **R8 authority-precedence
measurement-feasibility assessment**, under the stored `internal_test_001` / `99999` /
`internal_peak_only` anchor. **No migration, model, writer, allowlist pair, schema, operator, or
harness** — head stays `014_engagement_classification` with 14 migrations, 18 tables, and 12 writers.
Execution used a temporary scratchpad executor outside the repository.

**The row stores packet metadata only.** Reference id, schema name and version, source type, the
logical `internal-test-artifact://phase79/…` location reference, and the SHA-256 `packet_hash`. The
artifact body stays outside the repository and out of the database, and the hash value is not
disclosed in the docs. The posture is **server-stamped, not chosen** — the writer hard-requires
`draft` / `needs_review` / `active` and denies any draft arriving authoritative or
publication-flagged.

**The feasibility answer is a clean negative.** The internal_test scenario **cannot produce** either
of R8's two confirmation prerequisites — quantitative findings, or an evidence reliability rating.
Both are recorded `blocked_by_missing_measurement`. Every collected source in this engagement records
its basis as registered artifact descriptions only, with no live system access; the location-model
answer set states outright that an artifact-level assertion may not be upgraded into a measured fact,
and R8's own readiness records its rule as not machine-checkable because no measured claim can be
attributed to a system of record.

**This is a measurement gap, not a collection gap.** Collecting the remaining uncollected requests
would not resolve either prerequisite — those requests describe exports from a system that does not
exist in this scenario. **Nothing was fabricated:** no quantitative finding was computed or estimated
and no reliability rating was assigned. **Absence of a measurement basis is a negative feasibility
result and must not be read as favourable, nor restated as inventory accuracy.**

**Idempotency was rehearsed correctly.** Off-production against temporary SQLite, varying the packet
location reference and the packet hash — both fingerprinted — each yielded `idempotency_conflict`.
Note this writer's fingerprint covers packet **metadata only**: `reasons` and `warnings` do not
participate, unlike the review writer, so only a metadata field proves conflict detection here.

**Registration is collection, not review.** The row is `needs_review` and **is not evidence**. **R8
authority precedence remains unresolved** and R8 remains non-authoritative — recording that a
question cannot be answered in this scenario is not closing it; a negative closure would need its own
reviewed decision in a separately approved phase.

**Nothing else moved.** The **R5 WMS scope clarification remains a reviewed scope-blocker enumeration
only**; **R5 WMS scope remains unresolved**; the **Phase 64 R5 receiving/putaway export remains
uncollected**; **R1 remains provisional**; **R3–R7 stay deferred** with the count/variance request
**conditionally required / scope-dependent**; the Phase 74 outline is unmodified with `fnd_000` still
`blocked_no_review_support`; **no inventory accuracy conclusion** was made; and report finalization,
capsule publication, client-facing output, and **AgentNet resolver publication remain unauthorized**.
See
[`PHASE79_R8_MEASUREMENT_FEASIBILITY_SOURCE_INGESTION.md`](PHASE79_R8_MEASUREMENT_FEASIBILITY_SOURCE_INGESTION.md).

---

## Phase 80 — the R8 measurement-feasibility review and the scenario-specific closure

Phase 80 creates **one** row in production through an unchanged writer: a `review_records` row
(`rev_4208b1882d044069`, Phase 22 writer) reviewing the R8 measurement-feasibility source ingestion
(`ing_0d671226f2ba4760`), under the stored `internal_test_001` / `99999` / `internal_peak_only`
anchor. **No migration, model, writer, allowlist pair, schema, operator, or harness** — head stays
`014_engagement_classification` with 14 migrations, 18 tables, and 12 writers. Execution used a
temporary scratchpad executor outside the repository.

**`approve_internal` / `authoritative=false`.** The feasibility assessment accurately states what
this engagement can and cannot produce, so it is approved for internal reliance. It **remains
source-only and is not evidence**. `authoritative=false` is a **reviewer decision, not a writer
constraint** — the writer's `approve_internal` validation never inspects the field.

**Registration integrity is not claimed.** The review writer has no `packet_hash` path, so the Phase
79 source is evaluated **as registered**, with no hash or integrity confirmation.

**The closure is a recorded decision, not a database state change.** There is no closure decision in
the writer's vocabulary and none was simulated. The recorded conclusion is that **this internal_test
scenario cannot confirm R8 authority precedence**, because it cannot produce measured quantitative
findings or a reliability rating for the underlying evidence. **No R8 row was modified** — the R8
source ingestion (`ing_4fb70519cbf84401`) and the earlier R8 review (`rev_1d9696e9218b4e35`) are
untouched, since this writer has no `UPDATE` path. R8 still reads exactly as before:
non-authoritative, precedence rule unconfirmed.

**The closure is narrow and scenario-specific.** It does **not** mean R8 precedence is false —
nothing evaluated whether the precedence direction is correct, and an unconfirmable claim is not a
refuted one. It does **not** mean real client data could not confirm R8 in a future engagement; the
limitation is a property of *this scenario*, not of the question.

**Idempotency was rehearsed correctly.** Off-production against temporary SQLite, varying `reasons` —
fingerprinted here — yielded `idempotency_conflict`; varying only `source_phase` yielded
`idempotent_replay`, since the fingerprint excludes it. Production returned `created` with exactly
one row.

**Nothing else moved.** **R1 remains provisional** and the location finding stays **data-readiness
and reliability only, never inventory accuracy**; the **R5 WMS scope clarification remains a reviewed
scope-blocker enumeration only** and R5 WMS scope is unresolved; the **Phase 64 R5 receiving/putaway
export remains uncollected**; **R3–R7 stay deferred** with the count/variance request **conditionally
required / scope-dependent**; the Phase 74 outline is unmodified with `fnd_000` still
`blocked_no_review_support`; and report finalization, capsule publication, client-facing output, and
**AgentNet resolver publication remain unauthorized**.

**The artifact-only internal_test chain has reached its measurement limit.** The next useful step is
**production-parity staging or lab database planning**, where measured data exists — a change in kind
rather than another increment of the same kind. See
[`PHASE80_R8_MEASUREMENT_FEASIBILITY_REVIEW_CLOSURE.md`](PHASE80_R8_MEASUREMENT_FEASIBILITY_REVIEW_CLOSURE.md).
