# Phase 47 — Alembic Version-Table Hardening

**Status:** source hardening. **No production command was run. No migration added. No model, table,
writer, or allowlist change.**
**Baseline commit:** `4d8a4e4a1e4ff6241fb00123c72a457c38105215` — *Document Phase 46 production
schema bootstrap recovery*
**Alembic head:** unchanged at `013_governed_identifier_collation_policy`
**Harness:** [`tests/validate_phase47_alembic_version_table_hardening.py`](../tests/validate_phase47_alembic_version_table_hardening.py)
(`make validate-phase47`, included in `make validate`)
**Related:** [`PHASE46_PRODUCTION_SCHEMA_BOOTSTRAP_RECOVERY.md`](PHASE46_PRODUCTION_SCHEMA_BOOTSTRAP_RECOVERY.md),
[`DATABASE_SCAFFOLD.md`](DATABASE_SCAFFOLD.md)

---

## 1. Purpose

Fix in source the defect that halted the Phase 46 production bootstrap, so that a **fresh
MySQL/MariaDB bootstrap from an empty database no longer requires a manual `alembic_version` repair**.

## 2. Root cause, from Phase 46

Alembic builds its bookkeeping table with `Column("version_num", String(32))`
(`alembic.ddl.impl.DefaultImpl.version_table_impl`). Five revision identifiers in this repository are
longer than 32 characters:

| Revision | Length |
| --- | --- |
| `011_internal_report_review_packets` | 34 |
| `010_internal_assessment_report_drafts` | 37 |
| `008_internal_reviewer_decision_records` | 38 |
| `013_governed_identifier_collation_policy` | 40 |
| `012_internal_report_review_packet_decisions` | 43 |

Everything through `007` is at most 28 characters. In Phase 46 the chain therefore advanced to `007`,
applied `008`'s DDL, and then failed on the bookkeeping write with *"Data too long for column
`version_num`"*, leaving production partially bootstrapped.

**Production was repaired by hand in Phase 46** with a one-off `ALTER`. That repair lives only in
that one database and is represented nowhere in source control, so every future fresh bootstrap —
new environment, staging rebuild, restore drill, CI database, disaster-recovery exercise — would hit
the identical failure. This phase closes that gap.

## 3. Approach, and why

**Alembic exposes no width parameter.** `context.configure()` accepts `version_table`,
`version_table_schema`, and `version_table_pk` — nothing governing the column's width.

**The one official extension point is `DefaultImpl.version_table_impl`** (added in Alembic 1.14),
documented for third-party *dialect* authors. It was considered and not used as the sole mechanism
for one decisive reason: it only governs the shape Alembic would `CREATE`. It does nothing for a
database whose `alembic_version` already exists at `VARCHAR(32)` — which is precisely the state
Phase 46 produced, and the state any half-bootstrapped environment will be in.

**Chosen: a deterministic preflight in `alembic/env.py`**, covering all three states with one
mechanism — absent, too narrow, already wide enough.

## 4. What changed

| File | Change |
| --- | --- |
| [`alembic/version_table_hardening.py`](../alembic/version_table_hardening.py) | New. Planner, source guard, and the two fixed statements. |
| [`alembic/env.py`](../alembic/env.py) | Loads the helper; runs the source guard in both modes and the preflight in online mode. |
| `tests/validate_phase47_alembic_version_table_hardening.py` | New harness. |
| `Makefile` | `validate-phase47`, wired into `make validate`. |

No migration was added, no revision identifier was rewritten, and no existing migration file was
edited.

## 5. Behaviour

| Situation | Result |
| --- | --- |
| MySQL/MariaDB, `alembic_version` absent | Created with `version_num VARCHAR(255) NOT NULL` and Alembic's usual `alembic_version_pkc` primary key |
| MySQL/MariaDB, `version_num` narrower than 255 | Widened to `VARCHAR(255) NOT NULL` |
| MySQL/MariaDB, `version_num` already 255 or wider | Nothing executed |
| SQLite or any other dialect | Skipped before inspection; nothing executed |
| Offline mode (`--sql`) | No connection opened; source guard only |

A **source-side guard** additionally runs in both modes: if any revision identifier ever exceeds the
configured width, Alembic fails immediately with a message naming the offenders, rather than failing
partway through a production bootstrap. That is the check that would have caught Phase 46 in CI.

## 6. Scope of the SQL surface

The helper's entire executable SQL surface is two fixed string literals:

```
CREATE TABLE alembic_version (version_num VARCHAR(255) NOT NULL,
    CONSTRAINT alembic_version_pkc PRIMARY KEY (version_num))
ALTER TABLE alembic_version MODIFY COLUMN version_num VARCHAR(255) NOT NULL
```

Neither is a template; nothing is composed from caller input; there is a single `execute()` call
site, and it can only run a statement the planner selected. **This is Alembic bookkeeping only** — it
touches no application table, writes no application row, and contains no `DROP`, `DELETE`,
`TRUNCATE`, `INSERT`, or `UPDATE`. The harness enforces each of those properties by tokenising the
statements and rejecting any identifier other than `alembic_version`, `alembic_version_pkc`, and
`version_num`.

The helper reads no environment variable, opens no connection of its own, and references no
credential file; the caller supplies an already-open connection.

## 7. Production is untouched

**This phase ran no production command.** Existing production remains at head `013` and
`verified_safe_no_remediation_required`, as recorded in Phase 46. No credential file was sourced or
read, and the hardening changes nothing about the deployed database — its `version_num` was already
widened by hand, so the preflight would find it wide enough and do nothing.

**Credential separation remains required.** The read-only verifier credential must never be upgraded
to a migration credential; bootstraps use the separate migration credential. This phase does not
change that boundary, and the preflight runs under whatever credential the migration is already
using — it grants nothing new.

## 8. Residual notes

- **The MySQL/MariaDB DDL path is proven by construction and by a stubbed dialect, not against a
  live MySQL server.** No MySQL server is reachable from the validation suite, by design. The
  statements are fixed literals asserted character-for-character, and the create/widen/no-op branches
  are each exercised; what is not exercised in CI is a real MySQL server accepting them. The widen
  statement is the same one that ran successfully against production in Phase 46.
- **`VARCHAR(255)` is a deliberate ceiling**, not a maximum. It leaves wide headroom over the current
  longest identifier (43) while staying far below any MySQL index-length limit.
- Shortening future revision identifiers is still good practice; the guard makes the constraint
  explicit rather than removing the need for judgement.
