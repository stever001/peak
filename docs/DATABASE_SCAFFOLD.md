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
creates no records**, and production is still at 013: migration 014 has not been applied there. See
[`PHASE56_INTERNAL_TEST_ENGAGEMENT_SUPPORT.md`](PHASE56_INTERNAL_TEST_ENGAGEMENT_SUPPORT.md).
