# Production-Parity DB Validation (Phase 34)

How Peak validates DB-backed functionality so that "the tests pass" means "it works in the managed
MySQL environment," not merely "it works in local SQLite."

## Two validation layers

1. **Fast local structural smoke (SQLite).** The existing DB-backed validators (Phases 20–34) run
   against a temporary local SQLite database for schema shape, migration upgrade/downgrade/re-upgrade
   reversibility, writer governance/authorization logic, idempotency, and content-safety behavior.
   This layer is fast, credential-free, and runs in `make validate` / CI.

   **SQLite is not the production-readiness proof path.** It is a structural smoke path only. MySQL
   and SQLite differ in column types, constraint/collation enforcement, and concurrency, so a green
   SQLite run is necessary but not sufficient.

2. **Managed MySQL production-parity validation (test/staging).** Before treating DB-backed
   functionality as production-ready, run the managed MySQL rubric against a managed **test** or
   **staging** database (see [`MANAGED_MYSQL_PERSISTENCE_RUBRIC.md`](MANAGED_MYSQL_PERSISTENCE_RUBRIC.md)):
   apply migrations to head, verify the governed tables/columns and single Alembic head, and
   exercise each narrow controlled writer's authorized-create + idempotent-replay + conflict paths.
   **Managed MySQL test/staging validation is required for production readiness.**

## Production vs. test DB policy

- **Full smoke tests run against managed MySQL test/staging databases**, not production.
- **The production DB is not the main smoke-test target.**
- **No broad production delete/cleanup path** is added — tests must not delete production rows to
  "clean up." There is no such path in the repo.
- **Migration downgrade/re-upgrade is never run against the production client-data DB.** Full
  negative-path and migration reversibility testing belongs in managed non-production MySQL.
- **Future production canaries**, if added, must use a **dedicated synthetic smoke tenant** with
  tightly scoped writes and an explicit retention policy — never broad deletes, never real client
  data.

## Opt-in commands (credential-free, skip-safe)

`tools/managed_mysql_check.py` and its Makefile wrappers (`db-check-managed-test`,
`managed-mysql-smoke`, `managed-mysql-migration-check`) are opt-in. With no DSN set they **skip with
clear guidance and exit 0**; they **never print DSNs**, accept only `test`/`staging` (production is
refused — fail closed), perform **no writes / seed / delete / downgrade against production**, and
require **no live network for `make validate`**. A real read-only `SELECT 1` runs only under the
explicit `--connect` flag with a DSN present.

DSNs are provided only via environment variables (`PEAK_MANAGED_MYSQL_TEST_DSN`,
`PEAK_MANAGED_MYSQL_STAGING_DSN`, `PEAK_MANAGED_MYSQL_PROD_DSN`) — **never committed, never in
`.env`, never printed**.
