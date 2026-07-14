# Database Implementation Plan

**Planning document only — this is a plan, not an implementation.** No database, schema
migration, DB config, API, resolver integration, or ingestion pipeline is created in this
phase. AgentNet grounding/resolution is **intended future architecture, not implemented**.

## 1. Purpose and scope

Define how Peak will stand up a **controlled engagement database** — the system of record
for live engagement data — that serves two goals at once:

1. **Immediate consulting delivery** — hold the intake, evidence, interviews,
   observations, findings, and estimates a consultant needs to assess a client's current
   inventory/warehouse operations and recommend improvements.
2. **Future AI-readiness** — progressively refine that messy client data, workflows, and
   operational knowledge into a state ready for **capsulization** and eventual
   **AgentNet-based agentic AI operations** in warehouse/inventory workflows.

These are **parallel goals**: every engagement phase should produce immediate value *and*
prepare the client for the next phase toward AI usage. The database is a
**pre-capsulization staging layer** — see
[`DATABASE_TO_RESOLVER_MAPPING.md`](DATABASE_TO_RESOLVER_MAPPING.md).

## 2. Repo stays source-only

The Peak repository contains **source assets only** (docs, schemas, prompt contracts,
tools, validation, policy). **Client data must never be stored in Git.** Live engagement
data lives in the controlled database/storage, is used **only for authorized live client
engagement work**, and is **never used for examples, fixtures, demos, training, tests, or
any non-engagement use**. Runtime synthetic fixtures used for validation are test-only and
are never committed. See [`DATA_HANDLING_POLICY.md`](DATA_HANDLING_POLICY.md) and
[`FIXTURE_STRATEGY.md`](FIXTURE_STRATEGY.md).

## 3. No vendor choice yet, no SQL yet

- **Vendor decision (as of Phase 11): MySQL.** The controlled engagement database is
  **MySQL** (InnoDB/utf8mb4); the Python tooling layer is **SQLAlchemy + Alembic +
  PyMySQL**. Not SQLite; not PostgreSQL (unless later justified). The Phase 10 record
  model remains storage-agnostic in concept; Phase 11 realizes it against MySQL.
- **Phase 10 itself writes no SQL/DDL/migrations.** From **Phase 11**, migrations are
  source assets that define **schema structure only** (no data) — see
  [`DATABASE_SCAFFOLD.md`](DATABASE_SCAFFOLD.md).

## 4. Relationships

- **To the record model.** The database realizes the concepts in
  [`ENGAGEMENT_DATA_MODEL.md`](ENGAGEMENT_DATA_MODEL.md) and the record groups in
  [`DATABASE_RECORD_MODEL.md`](DATABASE_RECORD_MODEL.md), carrying the governance states
  from [`GOVERNANCE_STATES.md`](GOVERNANCE_STATES.md).
- **To resolver capsules.** The database is the source from which governed
  **private resolver capsules** are prepared; the mapping and readiness criteria are in
  [`DATABASE_TO_RESOLVER_MAPPING.md`](DATABASE_TO_RESOLVER_MAPPING.md). Capsules are the
  future governed grounding/resolution layer.
- **To the future agent runtime.** No agent runtime exists. When one is built (later
  phase), it reads authorized data through controlled access paths and writes records
  that **default to `draft`/`needs_review`**; agents may never set
  `client_facing_approved`, verify financial impact, or publish capsules (see
  [`DATABASE_ACCESS_AND_AUDIT.md`](DATABASE_ACCESS_AND_AUDIT.md) and
  [`STATE_TRANSITIONS.md`](STATE_TRANSITIONS.md)).
- **To live consulting delivery and AI-readiness.** The same records that power a
  consultant's assessment become the substrate for capsulization — so consulting work and
  AI-readiness advance together.

## 5. Staged implementation plan

Each stage is a separate future phase; only **Phase 10 (this document)** is delivered here.

| Phase | Deliverable | Notes |
| --- | --- | --- |
| **Phase 10** | **Database plan** (this doc set) | Architecture/planning only; no code, no vendor. |
| **Phase 11** | **Minimal local database scaffold** (done) | MySQL chosen; SQLAlchemy models, enum contracts, and Alembic migration (**schema only, no data**). Source assets only — see [`DATABASE_SCAFFOLD.md`](DATABASE_SCAFFOLD.md). |
| **Phase 12** | Resolver/capsule adapter scaffold | An adapter shape that maps eligible records to `ResolverCapsuleRecord` candidates under governance — no live resolver, no publication. |
| **Phase 13** | Agent execution harness | A guarded harness where agents draft records under the permission limits — no autonomous client-facing action. |
| **Later** | Controlled ingestion from client source systems | Capsulization of ERP/WMS/reports/telemetry/logs under authorization — see [`SOURCE_SYSTEM_CAPSULIZATION.md`](SOURCE_SYSTEM_CAPSULIZATION.md). |

## 6. Out of scope for Phase 10

No database, migrations, DB config, API, resolver integration, ingestion pipeline, agent
runtime, LLM integration, or client-facing functionality. No stored data, sample records,
seed data, or fixtures are committed. This phase is planning documentation only.
