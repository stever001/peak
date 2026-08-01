# Managed MySQL Persistence Rubric (Phase 34)

Peak's operational data — engagements, evidence, source ingestion, agent task queue, review
bundles, internal reviewer decisions, and now **intake notes** — lives in **managed remote MySQL**,
reached only through the repo's narrow, governed controlled writers. This rubric establishes the
production-parity persistence standard so future phases stop re-deriving it.

## Source of truth vs. operational store

- **The repo is the source of governed behavior.** All write paths are the narrow Phase 17-gated
  controlled writers; there is no generic CRUD, arbitrary SQL executor, or broad repository.
- **Managed remote MySQL is the operational data store.** Real client/engagement/operational data
  is stored **only** in the managed MySQL databases, never in Git.
- **Client data must never be committed to Git** — no fixtures, examples, sample packets, local DB
  dumps, seed data, logs, or pseudo-client data. Intake note text is authorized operational client
  content and belongs **only** in the managed DB.

## Client Isolation Option A (default)

**Client Isolation Option A is the default:** a shared managed MySQL database **per environment**
with strict tenant columns (`owner_id`, `client_id`, `engagement_id`, `authorization_scope`) and
authorization gates on every write. The stored `Engagement` row is the authorization anchor; every
write-time authorization loads it and compares `request.authorization_scope ==
engagement.authorization_scope` (identity matching is necessary but not sufficient). See
[`CLIENT_ISOLATION_MODEL.md`](CLIENT_ISOLATION_MODEL.md).

Every operational table carries `owner_id`, `client_id`, `engagement_id`, `authorization_scope`,
lifecycle/review status where applicable, and idempotency/fingerprint where applicable.

## Environment separation

Managed MySQL is separated by environment — **dev / test / staging / prod** — as distinct managed
databases. Non-production environments (test/staging) are where full validation runs; production is
never the smoke-test target.

Connection DSNs are supplied **only** through environment variables, never committed. The
documented variable names (values live out-of-band, never in Git, never in `.env`):

- `PEAK_MANAGED_MYSQL_TEST_DSN`
- `PEAK_MANAGED_MYSQL_STAGING_DSN`
- `PEAK_MANAGED_MYSQL_PROD_DSN` (operations only; **not** a smoke-test target)

The existing `PEAK_DATABASE_URL` remains the single runtime URL the app/session layer reads; the
`PEAK_MANAGED_MYSQL_*_DSN` names are the rubric's environment-scoped validation handles.

## SQLite is not the production-readiness proof path

Local temporary SQLite remains **only** a fast local **structural smoke path** for the existing
DB-backed validators (schema shape, migration reversibility, writer governance logic). **SQLite is
not the production-readiness proof path.** Because MySQL and SQLite differ in types, constraint
enforcement, collation, and concurrency, **managed MySQL test/staging validation is required before
treating any DB-backed functionality as production-ready.**

## Opt-in, credential-free validation targets

Phase 34 adds safe, opt-in Makefile targets that **skip with clear guidance when no DSN is set**,
**never print DSNs**, **never write to production**, and accept only `test`/`staging` (production is
refused, i.e. fail closed). They are **not** part of `make validate`, so standard validation and CI
stay green with **no credentials and no live network**:

- `make db-check-managed-test` — managed test-env schema/head rubric check
- `make managed-mysql-smoke` — managed test-env writer smoke runbook
- `make managed-mysql-migration-check` — managed test-env migration reversibility runbook

They delegate to `tools/managed_mysql_check.py`, which reads the DSN only from the environment,
hides its value, performs **no writes / no seed / no delete-cleanup / no migration downgrade against
production**, and only attempts a read-only `SELECT 1` under an explicit opt-in `--connect` flag.

## Production vs. test DB policy

See [`PRODUCTION_PARITY_DB_VALIDATION.md`](PRODUCTION_PARITY_DB_VALIDATION.md). In short: full smoke
and negative-path/migration testing run against managed **test/staging** MySQL; the **production DB
is not the main smoke-test target**; there is **no broad production delete/cleanup path**; and
migration downgrade/re-upgrade is never run against the production client-data DB. Future production
canaries, if added, must use a dedicated synthetic smoke tenant with tightly scoped writes and a
retention policy — never broad deletes.

## What this rubric does not do

This is a documentation-and-scaffolding consolidation phase. It adds **no** live DB write path for
tests, no production write path, no generic CRUD, no arbitrary SQL, no credentials, and no network
requirement for `make validate`.

---

## Phase 35 — workflow integration under this rubric

The Phase 35 managed-record workflow layer orchestrates durable records intended for these managed
remote MySQL environments and changes **nothing** in this rubric. It adds no DSN, no production DB
write path, no cleanup/delete path, and no managed target to `make validate`; a gated stage with no
injected `session_factory` is denied rather than falling back to an ambient environment database URL,
so standard validation needs **no live database credentials and no network**. Its temporary SQLite
test path remains a local structural smoke path only — **SQLite is not the production-readiness proof
path**. See [`MANAGED_RECORD_WORKFLOW_INTEGRATION.md`](MANAGED_RECORD_WORKFLOW_INTEGRATION.md).

---

## Phase 36 — DB-free, rubric unchanged

The Phase 36 internal assessment report planning boundary adds no table, model, migration, writer,
read path, or DSN, and reads no database. This rubric is unchanged, and standard `make validate`
still requires **no live database credentials and no network**. See
[`INTERNAL_ASSESSMENT_REPORT_PLANNING_BOUNDARY.md`](INTERNAL_ASSESSMENT_REPORT_PLANNING_BOUNDARY.md).

---

## Phase 37 — one new operational table under this rubric

`internal_assessment_report_drafts` (Phase 37) is an operational table and follows this rubric in
full: managed remote MySQL is its operational store, Client Isolation Option A applies (it carries
`owner_id`, `client_id`, `engagement_id`, `authorization_scope`), and the temporary SQLite path used
by its harness is a structural smoke path only — **not** production proof. Managed MySQL
test/staging validation is required before treating the writer as production-ready. The controlled
DB now has **16 tables**. No DSN, production write path, or cleanup/delete path was added.

---

## Phase 38 — one new operational table, and a concrete SQLite-parity lesson

`internal_report_review_packets` (Phase 38) is an operational table and follows this rubric in full:
managed remote MySQL is its operational store, Client Isolation Option A applies, and its temporary
SQLite harness is a structural smoke path only. The controlled DB now has **17 tables**.

Phase 38 also produced a concrete example of why **SQLite is not the production-readiness proof
path**: the convention-derived index name
`ix_internal_report_review_packets_internal_assessment_report_draft_id` is 69 characters, over
MySQL's 64-character identifier limit. SQLite accepts it silently; managed MySQL would reject the
DDL. The short name is pinned in both the model and the migration, and the Phase 38 harness asserts
every index/constraint name fits the limit.

---

## Phase 39 — one new operational table; the identifier-length check applied proactively

`internal_report_review_packet_decisions` (Phase 39) is an operational table and follows this rubric
in full. The controlled DB now has **18 tables**.

The Phase 38 identifier-length lesson was applied **before** writing the migration rather than
discovered afterwards: the table name is 39 characters, so convention-derived index names would have
reached **78** characters, over MySQL's 64-character limit. Every index uses a short explicit
`ix_irrpd_` prefix, and the harness asserts the limit for the model, the migration source, and the
indexes actually applied.
