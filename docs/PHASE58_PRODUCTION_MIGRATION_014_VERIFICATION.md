# Phase 58 — Migration 014 Applied to Production, and Verified

**Status:** production-sensitive phase — **schema change only**. Migration
`014_engagement_classification` was applied to production. **No production application record was
created, read, updated, or deleted**, no writer was invoked, and no runtime credential was used.
**Baseline:** `38616268119ff099b9fcf05cdd7582f25d60e21c`
**Alembic head:** `014_engagement_classification` (14 migrations, 18 tables, 12 writers) — now the
head **in production as well as in the repository**
**Migration:** [`alembic/versions/014_engagement_classification.py`](../alembic/versions/014_engagement_classification.py)
**Verifier:** [`tools/production_mysql_collation_verify.py`](../tools/production_mysql_collation_verify.py)
**Harness:** [`tests/validate_phase58_production_014_verification.py`](../tests/validate_phase58_production_014_verification.py)
(`make validate-phase58`, in `make validate`; offline, contacts no database)

---

## 1. What changed

Phases 55–57 built engagement classification as **repository-only** work: migration `014` was
written, the model metadata was pinned, and the read-side isolation primitive was added — but
production remained at `013_governed_identifier_collation_policy`. The classification columns were a
contract production could not yet hold.

Phase 58 closes exactly that gap and nothing else. **Migration 014 was applied to production in
Phase 58**, so **production schema now supports the Engagement classification fields**:

| Column | Type | Default | Purpose |
| --- | --- | --- | --- |
| `engagement_category` | governed `VARCHAR(24)` (`utf8mb4_bin`) | `real_client` | `real_client` / `internal_test`; byte-exact so a case variant can never read as the same category |
| `real_client_data` | `BOOLEAN` | `true` | whether the engagement may hold real client data |
| `client_accessible` | `BOOLEAN` | `true` | whether the engagement is reachable by a real client |
| `capsule_publication_authorized` | `BOOLEAN` | `false` | publication is never granted by default |

plus the index `ix_engagements_engagement_category`. The migration is additive and non-destructive:
no table dropped, no column removed, **no INSERT, no seed data, no row touched**. The defaults are
chosen so an unclassified pre-existing row reads as `real_client` — an unclassified row can never be
mistaken for a hidden internal test record.

## 2. The three authorized production actions

Phase 58 was authorized to perform these and only these against production:

1. **Pre-migration read-only verification** with the read-only verifier credential.
2. **`alembic upgrade 014_engagement_classification`** with the production migration credential —
   an explicit revision, never an open-ended `upgrade head`.
3. **Post-migration read-only verification** with the read-only verifier credential.

The only permitted production mutation was migration 014's own schema change plus Alembic's own
`alembic_version` update to `014_engagement_classification`. No downgrade, no manual `ALTER`, no
migration `015`, no cleanup or delete path, and no `INSERT`/`UPDATE`/`DELETE` against application
records. Environment files were sourced inside subshells only; **no credential, DSN, or environment
value was printed or committed**.

## 3. Verifier posture — expected production head is now 014

`tools/production_mysql_collation_verify.py` deliberately tracks the **live production head**, not
the repository head, so that it reports the real posture rather than an aspirational one. Through
Phases 56–57 it was pinned at `013` precisely because 014 had been written but not applied.

**The production verifier's expected head is now `014_engagement_classification`.** The pin moves
only when a migration has genuinely been applied to production — never merely when it is written.
Three harnesses assert this pin so it cannot drift silently: the Phase 43 fake-cursor harness (which
simulates production and therefore reports the production head), and the Phase 56 and Phase 57
regression checks.

The new column is covered by the same governed-collation posture as the rest of the schema:
`engagement_category` classifies as `governed_scope`, so the verifier requires it to carry a
deterministic collation, and the governed-column count observed in production moves from **211 to
212** accordingly. Governed identifier collation posture remains safe: every governed column in
production uses a deterministic collation, and all 11 controlled-writer idempotency boundaries
remain case-sensitive.

## 4. What Phase 58 did **not** do

- **No production application records were created.** Schema only.
- **No internal test engagement was created.** The first internal test engagement anchor remains a
  **separately approved** future phase; migration 014 makes it *representable*, not *authorized*.
- **No writer was invoked** against production or anywhere else. All 12 controlled writers remain
  create-only and unenabled; the writer-enablement decision gate still returns a no-write decision.
- **No runtime credential was used.** Only the read-only verifier credential and the migration
  credential were used, each for its one authorized purpose.
- **No production app table rows were read, counted, or probed.** Verification touched
  `INFORMATION_SCHEMA` metadata and `alembic_version` only; the collision probe stayed opt-in and
  was not run.

## 5. Read-side isolation is a primitive, not yet a guarantee

The read-side isolation primitive from Phase 57
([`peak/db/engagement_read_isolation.py`](../peak/db/engagement_read_isolation.py)) **exists, but
future client-facing paths must actually use it.** Classification columns in production do not
filter anything by themselves. A read path that bypasses `apply_read_isolation` is not protected by
it; the default mode excludes internal test engagements, and internal/admin visibility must be an
explicit opt-in. Publication eligibility is a separate compound predicate from client visibility.

## 6. Properly gated production test records — allowed later, under these terms

Production test records remain allowed **later**, and only when properly gated. Such a record must
carry:

- `engagement_category = internal_test`,
- `real_client_data = false`,
- `client_accessible = false`,
- and a **reserved test namespace/value** for its client and engagement identifiers.

They are **durable internal/admin records**, not disposable smoke records: runtime holds no
`DELETE`, so cleanup posture must be decided **before** any such write, not after. Creating one
still requires separate approval, a named writer, table, action scope, idempotency key, and cleanup
posture. Nothing in Phase 58 grants that approval.

---

## 7. Phase 59 update — the classification columns now hold a record

§4's "no internal test engagement was created" and §6's "allowed later, under these terms" describe
Phase 58, which applied schema only. **Phase 59 met those terms**: one durable anchor was created
in production with `engagement_category=internal_test`, `real_client_data=false`,
`client_accessible=false`, and the reserved `99999` client namespace — the separately approved
first internal test engagement anchor this section anticipated.

It is a **durable internal/admin record, not disposable smoke**; disposable production smoke
records remain disallowed, and no writer was enabled. See
[`PHASE59_FIRST_INTERNAL_TEST_ENGAGEMENT_ANCHOR.md`](PHASE59_FIRST_INTERNAL_TEST_ENGAGEMENT_ANCHOR.md).
