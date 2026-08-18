# Phase 45 — Production Collation Verification

**Status:** operational record of a **read-only** production verification attempt. **No source
change. No schema change. No migration executed. Result: inconclusive.**
**Baseline commit:** `8e76c885efd0bf9cbab79e48a0e5bc13802813e3` — *Add Phase 44 governed identifier
collation migration*
**Date of verification:** 2026-08-17
**Tool:** [`tools/production_mysql_collation_verify.py`](../tools/production_mysql_collation_verify.py)
(`make production-mysql-collation-verify`)
**Related:** [`GOVERNED_MYSQL_COLLATION_POLICY.md`](GOVERNED_MYSQL_COLLATION_POLICY.md),
[`PRODUCTION_MYSQL_COLLATION_VERIFICATION.md`](PRODUCTION_MYSQL_COLLATION_VERIFICATION.md)

This phase produced **no code, model, migration, or writer change**. It is recorded here because the
operational outcome — and the reason it was inconclusive — is the direct input to the next phase.

---

## 1. Purpose

Phase 44 pinned a deterministic collation on every governed column **in source control**, and the
offline audit accordingly reports `MODEL_POLICY_SATISFIED_PRODUCTION_UNVERIFIED`: source is correct,
the deployed database is unproven. Phase 45 attempted to close that gap by answering the one
question the repository cannot answer on its own:

> Is the governed-column collation risk **live in production** after Phase 44's source remediation?

The answer determines whether migration `013` is a required remediation, an unnecessary one, or
premature.

## 2. Source status at the time of verification

Verified from the repository at the baseline commit, offline and credential-free:

| Property | Value |
| --- | --- |
| Alembic head | `013_governed_identifier_collation_policy` (single head) |
| Expected Peak tables in the source model | **18** |
| Governed deterministic columns pinned to `utf8mb4_bin` in source | **211** |
| `make mysql-collation-audit` (venv, model tier) | `MODEL_POLICY_SATISFIED_PRODUCTION_UNVERIFIED` |
| Unpinned governed columns in source | **0** |

## 3. Production verifier result

The read-only verifier was gated on an out-of-band connection setting plus an explicit read-only
affirmation, both supplied from an operator-local file **outside the repository**. It connected and
completed. It did not skip, refuse, or fail.

**Sanitized finding**

- The verifier **connected** to production under the read-only boundary.
- Outcome: **`verified_inconclusive`**
- Reason code: **`no_governed_columns_readable`**
- **Server and database-level metadata were readable** — the server reported its version family and
  the database reported its default character set and collation.
- The **database default collation was case-insensitive**. The server confirmed this empirically
  rather than by name inference: it evaluated `'a'` and `'A'` as equal under that collation.
- **Zero of the 18 expected governed tables were visible** to the verifier.
- **`alembic_version` was unreadable** (the driver error type was recorded; its detail was withheld
  because driver messages embed connection strings).
- `governed_columns_checked`: **0**
- `idempotency_boundaries_checked`: **0**
- **No collision probe was run** (`collision_probe_status: not_run_opt_in`) — it is opt-in and was
  deliberately left off.

**Result contract as reported**

| Field | Value |
| --- | --- |
| `outcome` | `verified_inconclusive` |
| `reason_code` | `no_governed_columns_readable` |
| `production_connection_attempted` | `True` |
| `production_connection_made` | `True` |
| `readonly_queries_only` | `True` |
| `schema_mutation_made` | `False` |
| `data_write_made` | `False` |
| `migration_executed` | `False` |
| `cleanup_delete_made` | `False` |
| `secrets_printed` | `False` |
| `governed_columns_checked` | `0` |
| `governed_columns_at_risk` | `0` |
| `idempotency_boundaries_checked` | `0` |
| `idempotency_boundaries_at_risk` | `0` |
| `collision_probe_status` | `not_run_opt_in` |

Only allowlisted read-only metadata statements were issued: server version, database charset and
collation, `alembic_version`, table collations, column collations, and the collation case probe.

## 4. Interpretation

- **This does not prove production safe.** No governed column was inspected, so no column can be
  said to hold a deterministic collation.
- **This does not prove production risk is live at the column level.** The database *default*
  collation is case-insensitive, which is the hazard Phase 42 described — but a default is not
  evidence about any specific governed column.
- **The result is inconclusive precisely because zero governed production columns were inspected.**
  The reported `governed_columns_at_risk: 0` and `idempotency_boundaries_at_risk: 0` are `0 of 0`.
  They mean *nothing was examined*, not *nothing is wrong*, and must never be read as a clean bill
  of health.
- **Most likely explanation: the production schema has not been bootstrapped yet.** This is a **new
  production MySQL instance**. Zero visible Peak tables plus an unreadable `alembic_version` is the
  expected signature of a database that has never had the Peak schema created, rather than of a
  migrated database with a collation problem. (A privilege-filtered view of `INFORMATION_SCHEMA`
  would present the same symptoms, so the next phase must confirm rather than assume.)

## 5. Decision

- **NO-GO for executing migration `013` as a standalone remediation against existing tables.** There
  are no existing governed tables to remediate, and no evidence justifying a migration run.
- **No production migration was run.**
- **No production write, `ALTER`, cleanup, or delete occurred.** The verification path is read-only
  by construction: a hard-coded statement allowlist, checked immediately before execution and again
  at the driver boundary.
- Migration `013` remains implemented in source control and **not executed** against production.

## 6. Next recommended phase

**Production schema bootstrap from an empty/new database to Alembic head `013`**, followed by
re-running the read-only verifier.

Because the database is empty, `013` is not applied as a corrective `ALTER` over populated tables.
It is applied as the final step of an ordinary migration chain against an empty schema — no data
rewrite, no index rebuild on populated tables, and none of the maintenance-window pressure that
retrofitting a live schema would carry.

**Expected post-bootstrap success threshold**, all of which must hold before the collation question
is considered closed:

| Signal | Required value |
| --- | --- |
| Expected Peak tables visible | **18** |
| `alembic_version` | **readable**, at head `013_governed_identifier_collation_policy` |
| `governed_columns_checked` | **211** |
| `governed_columns_at_risk` | **0** |
| `idempotency_boundaries_checked` | **11** |
| `idempotency_boundaries_at_risk` | **0** |
| Outcome | `verified_safe_no_remediation_required` |

Anything short of that is another inconclusive result and must be treated as such.

## 7. Security confirmations

- **No connection strings, hosts, usernames, passwords, tokens, certificate paths, database names,
  environment values, or production row values are recorded in this document** or were printed
  during the verification.
- **No operator environment file was read into documentation.** The operator-local settings file
  lives outside the repository, is not tracked by git, and was never displayed, copied, or searched;
  it was checked only for existence, readability, permissions, and location. `.env` was not read and
  no secret store was searched.
- **No source files were changed during the operational verification.** The working tree was clean
  at the baseline commit before the verification and clean and identical afterwards.
- The verifier emits only sanitized output by design: failures report the exception *type*, never
  driver text, because driver messages routinely embed the connection string.

## 8. Warning — read before the bootstrap phase

- **Production schema bootstrap is a schema-changing operation.** It creates tables in the real
  deployed database. It requires **separate explicit approval** and a **dedicated migration
  credential**, and it is out of scope for every read-only verification path.
- **The read-only verifier credential must not be upgraded.** Its value is that it *cannot* write.
  Granting it schema-change privileges would destroy the guarantee that verification can never
  mutate production, and would make every future verification run a potential write path. The
  bootstrap credential must be separate, used only for the bootstrap, and never substituted into
  the verifier.
- After bootstrap, **re-run the read-only verifier**. Bootstrapping is not self-verifying: only an
  independent read of the deployed schema closes the question.
