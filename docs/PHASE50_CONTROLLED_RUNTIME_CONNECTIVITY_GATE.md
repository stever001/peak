# Phase 50 — Controlled Runtime Connectivity Gate

**Status:** read-only connectivity gate plus a reusable tool. **No production write. No application
row read. No schema change. No migration. No writer enabled or invoked. No deployment change.**
**Baseline commit:** `432fefb3cdcf7ba46400c397169ed9867532da82` — *Add Phase 49 runtime database URL
separation*
**Alembic head:** unchanged at `013_governed_identifier_collation_policy`
**Tool:** [`tools/production_runtime_connectivity_gate.py`](../tools/production_runtime_connectivity_gate.py)
(`make runtime-connectivity-gate` — opt-in, deliberately **not** part of `make validate`)
**Harness:** [`tests/validate_phase50_controlled_runtime_connectivity_gate.py`](../tests/validate_phase50_controlled_runtime_connectivity_gate.py)
(`make validate-phase50`, included in `make validate`)
**Related:** [`PHASE48_PRODUCTION_RUNTIME_READINESS_GATE.md`](PHASE48_PRODUCTION_RUNTIME_READINESS_GATE.md),
[`PHASE49_RUNTIME_DATABASE_URL_SEPARATION.md`](PHASE49_RUNTIME_DATABASE_URL_SEPARATION.md)

---

## 1. Purpose

Prove that the Phase 49 runtime session path can **actually reach the database** on the
least-privileged runtime credential, and that the credential still holds the Phase 48 grant posture
— while remaining structurally incapable of writing, of reading an application table, or of
revealing a connection detail.

Phase 48 checked grants but predated any runtime wiring. Phase 49 built the wiring but never
exercised it against a real credential. Phase 50 closes that loop, and makes the check **reusable**
so it can be re-run before any future enablement step.

## 2. What the gate does

| Aspect | Detail |
| --- | --- |
| URL source | `PEAK_RUNTIME_DATABASE_URL` only |
| Connection path | `peak.db.session.create_runtime_engine` — the application's own path, not a hand-built engine |
| Statements issued | exactly two: `SELECT 1` and `SHOW GRANTS FOR CURRENT_USER` |
| Grant handling | parsed in memory; **booleans only** leave the process |
| Output | sanitized `key=value` lines, machine-checkable |
| Exit codes | `0` pass · `1` fail · `2` refused (missing runtime URL, or unsafe invocation) |

**It cannot read the other roles' variables.** `PEAK_DATABASE_URL`,
`PEAK_PRODUCTION_DB_URL`, and the read-only affirmation are **removed from the tool's own process**
before anything else runs. So a successful connection is *evidence* that the runtime variable alone
sufficed, not merely an assertion that it did. There is no fallback path; a missing runtime URL
fails closed.

**It cannot mutate or read data.** Both statements are hard-coded and checked for identity — not
resemblance — immediately before execution, then re-checked for a `SELECT`/`SHOW` opener, the
absence of a statement separator, and the absence of any mutating verb. Neither statement contains a
`FROM` clause or a `COUNT(`, and no application table name appears anywhere in the tool.

**It cannot leak a deployment detail.** Failures are reported by exception *type* only, because
driver messages routinely embed the connection string. The grant parser discards the user, host, and
database names in every grant line; only privilege names — vocabulary defined in the tool itself —
and the global/schema scope distinction survive.

## 3. Grant policy

**Required:** `SELECT`, `INSERT` — all the create-only controlled writers need.

**Forbidden:** `UPDATE`, `DELETE`, `CREATE`, `ALTER`, `DROP`, `INDEX`, `REFERENCES`,
`CREATE TEMPORARY TABLES`, `LOCK TABLES`, `EXECUTE`, `CREATE VIEW`, `SHOW VIEW`, `CREATE ROUTINE`,
`ALTER ROUTINE`, `EVENT`, `TRIGGER`, `PROCESS`, `RELOAD`, `FILE`, `SHUTDOWN`, `SUPER`,
`CREATE USER`, `ROLE_ADMIN`, `CREATE TABLESPACE`, replication privileges, `ALL PRIVILEGES`,
`WITH GRANT OPTION`, and any global `*.*` privilege other than harmless `USAGE`.

The gate passes only on an **exact** match: zero missing required grants and zero excess. A
credential that is too broad *or* too narrow fails.

## 4. Self-test mode

`--self-test` exercises the parsing and policy logic against a fixed in-memory stand-in, contacting
no database, so the tool's own logic is covered by offline validation.

Two properties keep it from ever masking a live result:

- it **refuses** (exit 2) if `PEAK_RUNTIME_DATABASE_URL` is set, so it cannot be run "instead of" a
  real check in a configured environment; and
- it can **never** report `ready_for_later_writer_enablement=True` — readiness requires a live run.

It is a CLI flag, not an environment switch, so no environment variable can turn it on.

## 5. Result contract

`runtime_url_present` · `used_runtime_session_path` · `fallback_to_migration_url` ·
`connectivity_succeeded` · `grants_checked` · `required_grants_present` · `excess_grants_present` ·
`global_privileges_present` · `grant_option_present` · `schema_mutation_made` · `data_write_made` ·
`app_table_read_made` · `writer_invoked` · `secrets_printed` ·
`ready_for_later_writer_enablement`, plus `statements_issued`.

The five mutation/read/writer/secret fields are **structural**: the tool contains no code path that
could set any of them `True`.

## 6. What this phase does not do

- **It does not enable writers.** No controlled writer was run or wired, and no deployment or
  environment configuration was changed.
- **It does not write production data**, mutate schema, or run a migration.
- **It does not read, count, or probe application table rows.**
- **It does not use the migration credential.** `~/.peak/peak-prod-migrate.env` was not sourced.
- The read-only production verifier remains separate, unmodified, and gated on its own explicit
  read-only affirmation.

## 7. Required next step — writer enablement is a separate approved phase

A passing gate means the *connection and privilege posture* are right. It does not mean writers
should start. Before any application writer points at production, a separately approved enablement
phase must decide, explicitly, which of these it is authorising:

1. **No production smoke-write at all** — enable writers only under real engagement traffic, with
   the first write being genuine work.
2. **A single approved synthetic/administrative smoke-write** — one record, pre-agreed shape,
   pre-agreed cleanup posture. Note that the runtime credential holds **no `DELETE`**, so a
   synthetic row cannot be removed by runtime; removing it would require the migration credential,
   which is itself a decision to be taken deliberately rather than discovered afterwards.
3. **A real engagement-only write after client authorization exists** — no write until a governed
   engagement and its authorization scope are in place.

That phase should re-run this gate first: the grant posture can drift, and the gate is cheap.

## 8. Security confirmations

- **No DSNs, hosts, usernames, passwords, tokens, certificate paths, database names, connection
  URLs, environment values, raw grant lines, or row values** are recorded in this document, printed
  by the tool, or added to source, tests, or docs.
- Operator credential files were **sourced without output** and never displayed, copied, catted,
  grepped, or searched. `.env` was not read; no secret store was searched.
- The offline harness contacts no database and scrubs all role variables from every child process it
  starts, so `make validate` remains credential-free.

---

**Follow-up:** the enablement decision this phase deferred is now recorded by **Phase 51** — see
[`PHASE51_WRITER_ENABLEMENT_DECISION_GATE.md`](PHASE51_WRITER_ENABLEMENT_DECISION_GATE.md). The
recorded decision is **no production smoke-write and no writer enablement**, and the gate refuses
any request to authorize one. The warning stated in §7 above is preserved there as an enforced
field: a passing runtime connectivity gate is prerequisite evidence, not write permission.
