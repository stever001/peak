# Phase 48 — Production Runtime Readiness Gate

**Status:** read-only readiness gate. **No production write. No application row was read. No schema
change. No migration. No writer enabled.** Decision: **READY**, with one wiring precondition named
in §8.
**Baseline commit:** `3ab1a0db7fe14972c23762841c504ac82c03bf4a` — *Add Phase 47 Alembic version
table hardening*
**Date of gate:** 2026-08-18
**Related:** [`PHASE46_PRODUCTION_SCHEMA_BOOTSTRAP_RECOVERY.md`](PHASE46_PRODUCTION_SCHEMA_BOOTSTRAP_RECOVERY.md),
[`PHASE47_ALEMBIC_VERSION_TABLE_HARDENING.md`](PHASE47_ALEMBIC_VERSION_TABLE_HARDENING.md),
[`CONTROLLED_DB_WRITER_BOUNDARY.md`](CONTROLLED_DB_WRITER_BOUNDARY.md)

This phase produced **no code, model, migration, or writer change**. It answers one question and
stops there.

---

## 1. Purpose

Decide whether production is ready for **controlled application/runtime writer connectivity**.

Phase 46 bootstrapped and repaired the production schema; Phase 47 hardened the cause in source.
Neither established whether a *runtime* credential exists, is properly separated from the
verification and migration credentials, and carries the least privilege the application actually
needs. That is this gate, and only that.

**A READY verdict here does not enable writers.** Enablement is a separately approved phase.

## 2. Production schema and collation confirmation

Re-verified through the read-only verifier immediately before the grant check:

| Signal | Required | Observed |
| --- | --- | --- |
| Alembic head | `013_governed_identifier_collation_policy` | **matched** |
| `alembic_version` | readable, at head | **readable, head matches** |
| Base tables | 18 expected + `alembic_version` | **19** |
| `governed_columns_checked` | 211 | **211** (211 deterministic) |
| `governed_columns_at_risk` | 0 | **0** |
| `idempotency_boundaries_checked` | 11 | **11** |
| `idempotency_boundaries_at_risk` | 0 | **0** |
| Outcome | safe | **`verified_safe_no_remediation_required`** |

`readonly_queries_only: True`; `schema_mutation_made`, `data_write_made`, `migration_executed`,
`cleanup_delete_made`, and `secrets_printed` all `False`.

## 3. Runtime source inspection

Established from repository source only:

- **Eleven controlled writers exist**, and **every one is create-only**. The sole persistence call in
  each is `session.add(record)`. There is no `session.delete`, no `session.merge`, no `update()`, no
  bulk operation, and no raw-SQL execution path in any writer.
- **The replay path reads but never mutates.** On an idempotency hit the writer returns a receipt
  built from the existing row and records `database_write_made=False`,
  `existing_record_returned=True`, "existing record returned, not modified". No attribute of a
  loaded row is ever assigned, so no ORM flush can emit an `UPDATE`.
- **Runtime needs `SELECT`** for the idempotency/replay lookup on
  `(owner_id, client_id, engagement_id, idempotency_key)`, and **`INSERT`** to create records.
- **No writer requires schema privileges.** There is no `create_all`, `drop_all`, `DDL(`,
  `CreateTable`, or Alembic `op.` call anywhere under `peak/`.

**One nuance worth recording.** The allowlist vocabulary contains three update-shaped action names —
`update_review_status`, `update_lifecycle_status`, `mark_superseded`. They are **declared vocabulary
with no implementation anywhere in `peak/`**. No current writer issues them, so they impose no
privilege requirement today. Should any of them ever be implemented, this gate must be re-run:
they would introduce a genuine `UPDATE` requirement that the runtime credential deliberately does
not have.

**Conclusion: the runtime credential requires `SELECT` and `INSERT`, and nothing else.**

## 4. Credential separation

Three operator-local credential files, all outside the repository, all untracked by git, all
owner-only (`0600`), each defining only its own role's variable:

| Role | Variable | Purpose |
| --- | --- | --- |
| Read-only verifier | `PEAK_PRODUCTION_DB_URL` (+ explicit read-only affirmation) | verification only |
| Migration | `PEAK_DATABASE_URL` | Alembic/migration only |
| Runtime | `PEAK_RUNTIME_DATABASE_URL` | application connectivity |

Verified structurally without reading any value: all three address the same host, port, and
database; **all three usernames are distinct**; the runtime password differs from both the migration
and the read-only password. The runtime file defines **neither** `PEAK_DATABASE_URL` nor
`PEAK_PRODUCTION_DB_URL` nor the read-only affirmation, so it cannot silently stand in for either
other role.

**The read-only verifier credential was not upgraded**, and **the migration credential was not
reused for runtime**. All three boundaries hold.

## 5. Runtime grant finding

Established by connecting with the runtime credential and issuing **`SHOW GRANTS FOR CURRENT_USER`
only** — no application table was queried, counted, or probed, and no write or DDL was attempted.
Grants were parsed locally and only booleans were recorded.

| Property | Result |
| --- | --- |
| Connection made with runtime credential | **yes** |
| Holds `SELECT` | **yes** (required) |
| Holds `INSERT` | **yes** (required) |
| Holds `UPDATE` | **no** |
| Holds `DELETE` | **no** |
| Holds `CREATE` / `ALTER` / `DROP` | **no** |
| Holds `INDEX` / `REFERENCES` | **no** |
| Holds `ALL PRIVILEGES` | **no** |
| Holds any global (`*.*`) privilege | **no** |
| Holds `GRANT OPTION` | **no** |
| Holds `SUPER` or other admin privilege | **no** |
| Missing required privileges | **0** |
| Excess privileges | **0** |

The grant set is **exactly `SELECT` + `INSERT`, scoped to the application schema** — neither broader
nor narrower than the source requires. No grant was modified.

## 6. Decision

**READY** for controlled runtime writer connectivity, on the evidence above: the schema is verified
safe at head `013`, the credential roles are properly separated, and the runtime grant set matches
least privilege for create-only writers exactly.

**Phase 48 does not enable writers.** No deployment or environment configuration was changed, no
runtime connectivity was switched on, and no writer was executed against production.

## 7. Required next step

Enablement is a **separately approved phase**. Before it can wire runtime connectivity, one
precondition must be resolved:

- **`peak/db/session.py` reads `PEAK_DATABASE_URL`, not `PEAK_RUNTIME_DATABASE_URL`.** No source
  path consumes the runtime variable today, so the runtime credential cannot currently be used by
  the application as configured. Resolving this is a **source change and therefore out of scope for
  this gate**. It must not be resolved by exporting `PEAK_DATABASE_URL` from the runtime file: that
  would collapse the runtime and migration variables into one name and undermine the separation
  §4 establishes. The enablement phase should give runtime its own variable in source.

Re-run this gate if any of the following changes: a writer stops being create-only, any of the three
update-shaped allowlist actions gains an implementation, or the runtime grant set is altered.

## 8. Security confirmations

- **No DSNs, hosts, usernames, passwords, tokens, certificate paths, database names, connection
  URLs, environment values, or production row values are recorded in this document** or were printed
  during the gate. Credential checks emitted existence, readability, permission, location, and
  variable-name presence only; grant introspection emitted booleans only.
- **No application row was read, counted, or probed.** The only statement issued under the runtime
  credential was `SHOW GRANTS FOR CURRENT_USER`.
- **No production write, `INSERT`, `UPDATE`, `DELETE`, `ALTER`, `CREATE`, `DROP`, `TRUNCATE`,
  cleanup, or delete occurred**, and no migration was run.
- **No grant was created, modified, or revoked.**
- **No source code changed.** This phase's only repository change is documentation.
- No operator environment file was displayed, copied, or searched; `.env` was not read and no secret
  store was searched.
