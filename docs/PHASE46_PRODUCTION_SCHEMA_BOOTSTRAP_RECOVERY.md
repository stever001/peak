# Phase 46 — Production Schema Bootstrap Recovery

**Status:** operational record of a **production schema bootstrap that failed partway, was
recovered under explicit approval, and now verifies safe**. **No source change. No migration added
or modified. Result: production at Alembic head `013`, verifier `verified_safe_no_remediation_required`.**
**Baseline commit:** `75084b4c3f55aa6894e77cf63157a2882bf58839` — *Document Phase 45 production
collation verification*
**Date of bootstrap and recovery:** 2026-08-18
**Tool (verification):** [`tools/production_mysql_collation_verify.py`](../tools/production_mysql_collation_verify.py)
(`make production-mysql-collation-verify`)
**Related:** [`PHASE45_PRODUCTION_COLLATION_VERIFICATION.md`](PHASE45_PRODUCTION_COLLATION_VERIFICATION.md),
[`GOVERNED_MYSQL_COLLATION_POLICY.md`](GOVERNED_MYSQL_COLLATION_POLICY.md),
[`PRODUCTION_MYSQL_COLLATION_VERIFICATION.md`](PRODUCTION_MYSQL_COLLATION_VERIFICATION.md)

This phase produced **no code, model, migration, or writer change**. It is recorded here because the
bootstrap did not succeed on the first attempt, and both the failure mode and the recovery are
operationally significant: the root cause is still present in source and will recur on the next
fresh bootstrap.

---

## 1. Purpose

Bootstrap the new production MySQL schema to Alembic head `013` and verify governed
deterministic-column collation.

Phase 45 closed with an inconclusive read: the verifier connected but found no expected Peak tables,
so `governed_columns_checked` was `0 of 0`. Phase 46 was the bootstrap that Phase 45 identified as
the necessary next step, plus the independent re-verification that alone can close the collation
question.

## 2. Initial production condition

- **New production MySQL instance.**
- The Phase 45 read-only verifier had **connected** but found **no expected Peak tables**.
- Production was therefore **treated as empty/new**.
- **Alembic bootstrap was authorized as a production schema-changing operation**, using a **separate
  migration credential**. The read-only verifier credential was not upgraded.

A pre-bootstrap read-only run reconfirmed the empty condition immediately before any schema change:
connection made, **0 base tables**, all 18 expected tables absent, `alembic_version` unreadable,
outcome `verified_inconclusive`.

> The verifier reports `verified_inconclusive` unconditionally whenever `governed_columns_checked`
> is `0`, which an empty database always satisfies. On a new instance this is the expected signature
> of an unbootstrapped schema, not evidence of a connection or privilege fault.

## 3. Bootstrap failure

- `alembic upgrade head` ran **exactly once**, beginning from the empty/new schema.
- Migrations **`001` through `007` recorded successfully**.
- Migration **`008` physically completed its DDL**, but Alembic **failed while updating
  `alembic_version`**.
- **Root cause:** `alembic_version.version_num` was the Alembic default **`VARCHAR(32)`**, while the
  revision id `008_internal_reviewer_decision_records` is **longer than 32 characters**. The
  bookkeeping write was rejected as too long for the column.
- Production became **partially bootstrapped**.
- **No second schema-changing command was run before approval.** The failure was reported and the
  phase halted.

**Revision identifiers exceeding the default column width**

| Revision | Length |
| --- | --- |
| `011_internal_report_review_packets` | 34 |
| `010_internal_assessment_report_drafts` | 37 |
| `008_internal_reviewer_decision_records` | 38 |
| `013_governed_identifier_collation_policy` | 40 |
| `012_internal_report_review_packet_decisions` | 43 |

Every revision through `007` is at most 28 characters, which is exactly why the chain advanced that
far and stopped where it did.

## 4. Partial-state finding before recovery

Established by a read-only verifier run plus a read-only Alembic revision query:

| Signal | Value |
| --- | --- |
| `alembic_version` recorded revision | `007_review_bundle_records` |
| `008` table | **physically present but not recorded** |
| Base tables visible (including `alembic_version`) | **15** |
| `governed_columns_checked` | **141** |
| `governed_columns_at_risk` | **141** |
| `idempotency_boundaries_checked` | **7** |
| `idempotency_boundaries_at_risk` | **7** |
| Outcome | `verified_risk_live_remediation_required` |
| Reason code | `governed_columns_non_deterministic` |

Four expected tables were absent — those created by migrations `009` through `012`. The governed
columns then present had inherited the **case-insensitive database default**, because migration
`013`, which pins deterministic collations, had not yet run.

**No application writers were enabled** at any point, and the database held no data, so the
case-insensitivity exposure was latent rather than realized: no idempotency-key collision could have
occurred.

## 5. Approved recovery

**Option A** was selected as the smallest-blast-radius recovery. Three actions were authorized and
exactly three were performed:

1. **One exact manual SQL statement:**
   `ALTER TABLE alembic_version MODIFY COLUMN version_num VARCHAR(255) NOT NULL`
2. **One Alembic stamp** to `008_internal_reviewer_decision_records`.
3. **One Alembic upgrade to head**, carrying `008` → `013`.

All three ran under the **migration credential**, never the verifier credential.

**No downgrade, `DROP`, `DELETE`, `TRUNCATE`, cleanup, arbitrary SQL, second `ALTER`, or second
upgrade was run.** The single `ALTER` was the only manual SQL of the phase.

Options considered and rejected: shortening the five long revision identifiers in source (rewrites
migration history and still requires reconciling the already-recorded `007`), and dropping and
re-bootstrapping (viable only because the database was empty, but hits the same wall at `008`
without one of the other fixes first).

## 6. Why stamping `008` was acceptable

- Source migration `008` declares `revision = "008_internal_reviewer_decision_records"` and
  `down_revision = "007_review_bundle_records"`, with no branch labels or dependencies.
- Its `upgrade()` body creates **one table and its indexes**, and touches no other table and writes
  no data.
- **Alembic updates `alembic_version` only after the migration body returns.** In
  `alembic/runtime/migration.py`, `step.migration_fn(**kw)` runs the entire `upgrade()` body, and
  only afterwards does `head_maintainer.update_to_step(step)` issue the version-table write.
- The **failure occurred on the version-table update**, therefore **after `008`'s DDL had physically
  completed**.
- **MySQL DDL is non-transactional** — Alembic itself logs `Will assume non-transactional DDL` — so
  each statement in the body was committed and could not be rolled back.
- The stamp therefore **reconciled Alembic bookkeeping with physical state**. It asserted nothing
  that was not already true of the deployed schema.

## 7. Final production state

| Signal | Required | Observed |
| --- | --- | --- |
| Alembic head | `013_governed_identifier_collation_policy` | **matched** |
| `alembic_version` | readable | **readable** |
| `alembic_version` recorded revision | `013_governed_identifier_collation_policy` | **matched** |
| Expected Peak base tables (plus `alembic_version`) | 18 (+1) | **18 (+1) = 19** |
| `governed_columns_checked` | 211 | **211** |
| `governed_columns_at_risk` | 0 | **0** |
| `idempotency_boundaries_checked` | 11 | **11** |
| `idempotency_boundaries_at_risk` | 0 | **0** |
| `collision_probe_status` | — | `not_run_opt_in` |
| Outcome | `verified_safe_no_remediation_required` | **matched** |

Reason code: `all_governed_columns_deterministic`. The verifier's own recommendation is **NO-GO for
migration `013`: no remediation required.**

**Final finding: safe. No further migration `013` action is needed.** The Phase 45 success threshold
is met in full.

The post-recovery verifier run reported `readonly_queries_only: True` with `schema_mutation_made`,
`data_write_made`, `migration_executed`, `cleanup_delete_made`, and `secrets_printed` all `False` —
the verification path remained read-only, as it is by construction.

## 8. Security and hygiene confirmations

- **Separate read-only and migration credentials were used**, sourced from operator-local files
  outside the repository, untracked by git, owner-only permissions.
- **The read-only credential was not upgraded.** The two credentials were confirmed distinct before
  any production action, and all three recovery actions used the migration credential only.
- **No DSNs, hosts, usernames, passwords, tokens, certificate paths, database names, connection
  URLs, environment values, or production row values are recorded in this document** or were printed
  during the phase. Credential checks emitted existence, readability, permission, location, and
  variable-name presence only.
- **No environment file was read into documentation.** Neither operator-local file was displayed,
  copied, or searched. `.env` was not read and no secret store was searched.
- **No client data, pseudo-client data, seed data, examples, database dumps, or sample packets were
  introduced.**
- **No source files changed during the bootstrap or the recovery.** The working tree was clean at
  the baseline commit before the phase and clean and identical afterwards.

## 9. Residual risks and required follow-up

- **The root cause is not fixed in source.** Alembic hard-codes `String(32)` for the version column
  and `alembic/env.py` passes no override to `context.configure()`.
- **The production database was manually repaired** by widening `alembic_version.version_num`. That
  repair is scoped to this one database and is not represented anywhere in source control.
- **Future fresh MySQL bootstraps will hit the same `VARCHAR(32)` failure** unless source is
  hardened — this includes any new environment, staging rebuild, restore drill, CI database built
  from scratch, or disaster-recovery exercise.
- **Phase 47 should address Alembic version-table hardening before any new environment, staging
  rebuild, restore drill, or fresh bootstrap.** Treat this as a prerequisite, not a cleanup task:
  the next environment stood up without it repeats this phase's failure.
- **The database default collation remains case-insensitive.** Governed columns are individually
  pinned deterministic, so the idempotency boundary is correct today, but any future governed column
  added without an explicit collation would silently inherit the case-insensitive default. Continued
  use of `GovernedString` and the audit enforcement described in
  [`GOVERNED_MYSQL_COLLATION_POLICY.md`](GOVERNED_MYSQL_COLLATION_POLICY.md) remains required.
- **An optional read-only index inventory could confirm `008`'s indexes directly.** The stamp
  rationale rests on Alembic's execution order and MySQL's non-transactional DDL rather than on a
  direct index-by-index read, because enumerating indexes would have exceeded the single authorized
  statement. The post-recovery verifier corroborates the outcome — 11 of 11 idempotency boundaries
  check clean, which includes the `008` table — so this is confirmatory rather than outstanding.

## 10. Gate on enabling application writers

The stated gate for application writers was head `013` with `governed_columns_at_risk: 0`. That gate
is now **satisfied**. Enabling writers remains a separate decision and is not part of this phase.
