# Production MySQL Collation Verification (Phase 43)

**Status:** read-only verification tooling and a go/no-go decision procedure. **No schema change.
No migration. Migration `013` is not implemented by this phase.**
**Tool:** [`tools/production_mysql_collation_verify.py`](../tools/production_mysql_collation_verify.py)
(`make production-mysql-collation-verify`)
**Harness:** [`tests/validate_phase43_production_mysql_collation_verification.py`](../tests/validate_phase43_production_mysql_collation_verification.py)
(`make validate-phase43`)

---

## Why this phase targets production, not disposable MySQL

Peak is now building on the **real deployed database**. Earlier phases framed managed MySQL
validation around a *disposable* test/staging schema, which was right while the schema was still
being designed. It is no longer sufficient for the open question.

Phase 42 established the shape of the risk precisely — 308 string columns, **211 governed**, **0
with a pinned collation** — but it could not establish whether the risk is *live*. That depends
entirely on the **effective collation of the running production server**, which cannot be read from
the repository. A disposable schema would only tell us about the disposable schema's server
defaults, not production's.

So Phase 43 reads production. Under a strict boundary:

| Operation | Phase 43 |
| --- | --- |
| Read-only metadata introspection | **Allowed** |
| `INFORMATION_SCHEMA` / `SELECT` / `SHOW` | **Allowed** |
| Bounded `COUNT`-only aggregates (opt-in) | **Allowed** |
| Schema mutation (`ALTER`, `CREATE`, `DROP`) | **Not allowed** |
| Data writes (`INSERT`, `UPDATE`, `DELETE`) | **Not allowed** |
| Migration execution | **Not allowed** |
| Cleanup / delete paths | **Not allowed** |
| Printing DSN, host, user, password, token, cert | **Not allowed** |
| Emitting production row values | **Not allowed** |

The disposable-staging language elsewhere in the docs is not wrong for its own purpose — parity
rehearsal of a migration still belongs on a throwaway schema. It is simply not the tool for
answering "what is production's collation right now?"

---

## What each layer proves

| | `make validate` (offline) | `make production-mysql-collation-verify` |
| --- | --- | --- |
| Runs in CI / on a laptop with no DB | Yes | **No** — opt-in, credentialed |
| Needs production credentials | **No** | Yes (out-of-band) |
| Proves identifier lengths fit MySQL | Yes (Phase 41) | — |
| Proves which columns are *governed* | Yes (Phase 42) | — |
| Proves the repo pins no collation | Yes (Phase 42) | — |
| Proves **production's effective collation** | **No** | **Yes** |
| Proves the risk is live or not | **No** | **Yes** |
| Proves production matches the expected schema/head | **No** | Yes (best-effort) |

### What production verification still does **not** prove

- That a future `ALTER` will complete within a given maintenance window.
- That no application code outside Peak's writers relies on case-insensitive matching.
- Concurrency, locking, or replication behavior under the change.
- Anything about environments other than the one whose connection setting was supplied.

`make validate` remains **fully offline** — no credentials, no network, no DNS, no TLS, no `.env`,
no DSN. The production target is deliberately **not** part of it.

---

## Running the verification safely

```bash
make production-mysql-collation-verify                          # skips safely if unconfigured
make production-mysql-collation-verify PYTHON=.venv/bin/python  # needs SQLAlchemy to connect
```

Two environment variables are required. **Names only appear here — never values, and never in tool
output.** Provide them out-of-band; do not commit them and do not place them in a file the repo
reads.

| Variable | Purpose |
| --- | --- |
| `PEAK_PRODUCTION_DB_URL` (or `PEAK_DATABASE_URL`) | Connection setting. Read, never printed. |
| `PEAK_PRODUCTION_DB_READONLY_CONFIRM=1` | Operator affirmation that this is a **read-only** inspection. |

Optional flags: `--collision-probe` (bounded `COUNT`-only aggregates on the idempotency boundary
tables) and `--verbose` (lists the *names* of the queries issued).

### Fail-closed gating

| Condition | Behavior | Exit |
| --- | --- | --- |
| Neither variable set | Sanitized skip; no driver import, no network, no `.env` read | 0 |
| Connection setting present, **no** read-only affirmation | **REFUSED** — will not connect | 2 |
| Affirmation present, no connection setting | Skip; nothing attempted | 0 |
| Both present | Connects read-only and verifies | 0 |
| Tool or query failure | Sanitized `failed_safely` | 1 |

The tool never reads `.env`. If no connection setting is available in the environment, it reports
the required variable **names** and stops — it does not go looking for credentials.

---

## Read-only by construction

This is enforced structurally, not by convention:

1. **A hard-coded query allowlist.** Every statement the tool can issue is a constant in
   `READ_ONLY_QUERIES`. There is no code path that accepts SQL from a CLI argument, an environment
   variable, a file, or any other caller-supplied source.
2. **A guard before every execution.** `assert_read_only()` requires three independent conditions:
   the statement must *be* one of the allowlisted constants (identity, not resemblance); it must
   begin with `SELECT` or `SHOW`; and it must contain no mutating verb and no statement separator.
   A read-only statement that is merely *not on the allowlist* is still refused.
3. **A second check at the driver boundary.** The cursor adapter re-runs the same guard immediately
   before handing the statement to the driver.
4. **Validated identifiers.** The two templated queries interpolate only a table name from the
   model metadata or a collation name read back from `INFORMATION_SCHEMA` — each re-validated
   against `^[A-Za-z0-9_]{1,64}$` before use.

Forbidden and refused: `INSERT`, `UPDATE`, `DELETE`, `ALTER`, `DROP`, `TRUNCATE`, `CREATE`,
`REPLACE`, `GRANT`, `REVOKE`, `LOCK`, `CALL`, `LOAD`, `OUTFILE`, `SET`, multi-statement execution,
and migration execution. There is no writer, no ORM session, no `create_all`, and no Alembic runner
anywhere in this tool.

## Production checks performed

- Server version **family** only (e.g. `8.0`) — never the full build string.
- Database default character set and collation.
- Table collations for every base table; missing expected tables and unexpected extras are reported
  by **name** (schema object names are not secrets; row values are).
- Column collations for every `char`/`varchar`/`text` column, classified through the **Phase 42
  governed-column classifier** — reused directly, not re-derived, so the two phases cannot drift.
- Whether each governed column uses a deterministic (`_bin` / `_as_cs` / `_cs`) collation.
- Whether the controlled-writer idempotency boundary is deterministic. A table counts as a boundary
  only if it actually carries `idempotency_key` — the 11 tables with the composite UNIQUE.
- An **empirical cross-check**: `SELECT ('a' COLLATE <c>) = ('A' COLLATE <c>)`, a pure literal
  comparison touching no table and no row, confirming the server really does compare
  case-insensitively rather than inferring it from the collation's name.
- Alembic head, compared against `012_internal_report_review_packet_decisions`.

### Collision probe — opt-in, counts only

`--collision-probe` runs one bounded aggregate per idempotency-boundary table and returns a single
`COUNT`. It **never** returns or prints an `owner_id`, `client_id`, `engagement_id`,
`idempotency_key`, row, or sample.

Its interpretive value is limited, and that is worth stating plainly: if production is already
case-insensitive, the unique index *prevents* case-variant rows from coexisting on those columns,
so the count is zero by construction. The probe is therefore a consistency check, not the primary
evidence. **The metadata read plus the literal cross-check are the primary evidence.** The probe is
off by default so it imposes no scan load on production unless explicitly requested.

## Result classification

`skipped_not_configured` · `refused_not_confirmed_readonly` ·
`verified_safe_no_remediation_required` · `verified_risk_live_remediation_required` ·
`verified_inconclusive` · `failed_safely`

Every result carries: `production_connection_attempted`, `production_connection_made`,
`readonly_queries_only`, `governed_columns_checked`, `governed_columns_at_risk`,
`idempotency_boundaries_checked`, `collision_probe_status`, `recommended_next_step`, and the
permanent falses `schema_mutation_made`, `data_write_made`, `migration_executed`,
`cleanup_delete_made`, `secrets_printed`.

---

## Go / no-go criteria for migration 013

| Verification outcome | Decision |
| --- | --- |
| `verified_risk_live_remediation_required` | **GO** — schedule migration `013` under the conditions below |
| `verified_safe_no_remediation_required` | **NO-GO** — no remediation needed; keep the Phase 42 policy rule for future columns |
| `verified_inconclusive` | **NO-GO for now** — fix access or evidence first; never migrate on inconclusive evidence |
| `skipped_not_configured` / `refused_not_confirmed_readonly` | **No decision** — verification did not run |

**GO does not mean proceed automatically.** Migration `013` still requires, in order:

1. Explicit user approval of the remediation *and* of the specific collation
   (`utf8mb4_bin` vs `utf8mb4_0900_as_cs` — Phase 42 deliberately deferred this; production's
   server version, now readable, informs it).
2. A verified backup with a **tested restore**, not merely a backup.
3. A maintenance window sized for index rebuilds on the affected tables.
4. A rehearsal on a disposable schema restored from a production-shaped backup.
5. A rollback plan (see the downgrade posture in
   [`GOVERNED_MYSQL_COLLATION_POLICY.md`](GOVERNED_MYSQL_COLLATION_POLICY.md)).

### One correction carried back to Phase 42

Phase 42 stated that tightening the collation could surface **new duplicate-key violations**. That
was wrong, and it has been corrected in
[`GOVERNED_MYSQL_COLLATION_POLICY.md`](GOVERNED_MYSQL_COLLATION_POLICY.md).

Moving from case-**insensitive** to case-**sensitive** makes a unique index *more* discriminating:
values that previously collided become distinct. Every existing row was already unique under the
looser rule, so it stays unique under the stricter one. **That direction cannot create duplicate-key
violations.** The reverse could — which is precisely why it is not the remediation.

The real behavioral change is that lookups become case-sensitive. Peak's writers persist and compare
these values verbatim, so no reliance on case-insensitive matching is expected — but that should be
confirmed against production, not assumed.

---

## Data and secret handling

- **No production row values are ever emitted** — not ids, not keys, not client identifiers, not
  samples. Aggregates return counts only.
- **No DSN, username, password, host, port, certificate, token, or environment value is printed.**
  Every output line passes through a sanitizer that replaces DSN-shaped strings, `password=` /
  `token=` / `api_key=` pairs, `user:pass@host` forms, and PEM blocks with `[secret withheld]`.
- **Failures are reported by exception *type* only.** Driver exception messages routinely embed the
  full connection string, so the raw text is never surfaced.
- **`.env` is never read**, by this tool or by `make validate`.
- **No credentials are committed**, and none appear in this document.

## Boundaries

Phase 43 adds no table, model, migration, allowlist pair, writer, generic CRUD, SQL executor, or
migration runner, and changes nothing under `peak/`, `alembic/`, or `schemas/`. It touches none of:
AgentNet publication, MCP/resolver calls, LLM or agent execution, client-facing output, approval
workflows, financial verification, or capsule publication.

Client Isolation Option A ([`CLIENT_ISOLATION_MODEL.md`](CLIENT_ISOLATION_MODEL.md)) and the
Peak-operated AgentNet publication policy
([`PEAK_OPERATED_AGENTNET_PUBLICATION_POLICY.md`](PEAK_OPERATED_AGENTNET_PUBLICATION_POLICY.md))
are unchanged.

## Related

- [GOVERNED_MYSQL_COLLATION_POLICY.md](GOVERNED_MYSQL_COLLATION_POLICY.md) — Phase 42 classification + migration `013` plan
- [MANAGED_MYSQL_PRODUCTION_PARITY_VALIDATION.md](MANAGED_MYSQL_PRODUCTION_PARITY_VALIDATION.md) — Phase 41 offline parity checks
- [PRODUCTION_PARITY_DB_VALIDATION.md](PRODUCTION_PARITY_DB_VALIDATION.md) — the validation-layer model
- [DATABASE_ACCESS_AND_AUDIT.md](DATABASE_ACCESS_AND_AUDIT.md) — access and audit posture

---

## Phase 44 — the remediation now exists; production still has not been migrated

Migration `013_governed_identifier_collation_policy` is committed, pinning `utf8mb4_bin` on all 211
governed columns. That changes what this verifier is *for*, without changing what it does:

- **Before execution** — it answers whether the risk is live in production, and therefore whether
  executing `013` is warranted.
- **After execution** — it is the only way to confirm the migration actually took effect on the
  deployed database.

Nothing about the read-only boundary changed: hard-coded query allowlist, guard before every
execution, fail-closed gating, no DSN or row value in output, and **no migration execution**. The
tool's expected Alembic head moved 012 → 013, so a production database still reporting 012 will now
be flagged — which is exactly the signal that the migration has not been run there yet.

**Phase 44 did not execute migration 013 against production.** See the production execution
checklist in [`GOVERNED_MYSQL_COLLATION_POLICY.md`](GOVERNED_MYSQL_COLLATION_POLICY.md).

---

## Phase 58 update — the expected production head is now `014`

Migration `014_engagement_classification` was **applied to production in Phase 58**, so
`EXPECTED_ALEMBIC_HEAD` moved `013` → `014_engagement_classification`. The pin tracks the **live
production head**, never the repository head: through Phases 56–57 it stayed at `013` precisely
because 014 had been written but not applied. Move it only when a migration has genuinely been
applied to production.

A production database still reporting `013` will now be flagged — exactly the signal that 014 has
not been run there. Nothing about the read-only boundary changed: hard-coded query allowlist, guard
before every execution, fail-closed gating, no DSN or row value in output, and **no migration
execution by this tool**.

`engagement_category` classifies as `governed_scope`, so it is subject to the same deterministic
collation requirement as every other governed identifier and the production governed-column count
moves from **211 to 212**. Verification read `INFORMATION_SCHEMA` metadata and `alembic_version`
only: **no production application records were read**, counted, or probed, and none were created,
updated, or deleted. See
[`PHASE58_PRODUCTION_MIGRATION_014_VERIFICATION.md`](PHASE58_PRODUCTION_MIGRATION_014_VERIFICATION.md).
