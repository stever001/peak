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
