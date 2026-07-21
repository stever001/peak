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
