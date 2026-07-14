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
    models.py     # 11 controlled-database models (schema only)
    session.py    # engine/session from PEAK_DATABASE_URL (no credentials in repo)
alembic.ini       # Alembic config; URL comes from the environment, not this file
alembic/
  env.py          # reads PEAK_DATABASE_URL; target_metadata = Base.metadata
  versions/
    001_initial_controlled_database_schema.py   # tables only, no inserts
.env.example      # placeholders only (PEAK_DATABASE_URL=...); .env is gitignored
requirements.txt  # SQLAlchemy / alembic / PyMySQL (runtime tooling)
```

## Models & governance

The models cover: `Client`, `Engagement`, `EngagementRecord`, `EvidenceReference`,
`SourceSystemReference`, `FinancialImpactEstimate`, `ResolverCapsuleRecord`,
`ReviewRecord`, `AgentRunRecord`, `CapsulePublicationCandidate`, `SourceIngestionRecord`
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

# dependency-backed scaffold check (imports models, verifies the 11 tables and columns)
.venv/bin/python tests/validate_phase11_db_scaffold.py

# or run the whole validation suite through the venv interpreter
make validate PYTHON=.venv/bin/python
```

When SQLAlchemy/Alembic are installed, the Phase 11 check additionally imports
`peak.db.models`, confirms `Base.metadata` defines **exactly** the 11 expected tables with
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
