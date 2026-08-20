# Phase 56 — Internal Test Engagement Schema and Writer Classification Support

**Status:** implementation phase — code path only. **Phase 56 creates no records:** no engagement,
no intake note, no synthetic smoke record, no capsule published, no writer enabled. No production
database was contacted and no production migration was run.
**Baseline commit:** `4fa31a3d2775de6f0203a8464054cec9a10a3458`
**Alembic head:** `014_engagement_classification` (14 migrations, **18 tables**, **12 writers** —
no table and no writer added)
**Harness:** [`tests/validate_phase56_internal_test_engagement_support.py`](../tests/validate_phase56_internal_test_engagement_support.py)
(`make validate-phase56`, in `make validate`; offline, temp-SQLite only)
**Related:** [`PHASE55_INTERNAL_TEST_ENGAGEMENT_CLASSIFICATION.md`](PHASE55_INTERNAL_TEST_ENGAGEMENT_CLASSIFICATION.md),
[`PHASE54_CONTROLLED_ENGAGEMENT_AUTHORIZATION_ANCHOR_WRITER.md`](PHASE54_CONTROLLED_ENGAGEMENT_AUTHORIZATION_ANCHOR_WRITER.md)

---

## 1. Policy encoded

**Properly gated production test records are allowed later.** They are **durable internal/admin
test engagements** — used to speed development, training, live testing, and demonstration — and
they are **not disposable smoke data**.

A reserved value such as `client_id="99999"` is one **visible marker**, and it is deliberately
**not the whole control**. An internal test engagement must additionally be explicitly classified,
hold no real client data, and be non-client-accessible.

## 2. Schema — migration `014_engagement_classification`

Four real columns on `engagements` (never JSON, label, scope, or id-prefix):

| Column | Type | Default | Meaning |
| --- | --- | --- | --- |
| `engagement_category` | governed string(24), indexed, NOT NULL | `real_client` | `real_client` / `internal_test` |
| `real_client_data` | boolean, NOT NULL | `true` | may hold real client data |
| `client_accessible` | boolean, NOT NULL | `true` | reachable by a real client |
| `capsule_publication_authorized` | boolean, NOT NULL | `false` | capsules may be published |

`engagement_category` is **governed** (byte-exact) so a case variant can never read as the same
category. Defaults point the safe way: an unclassified row is a **real client** engagement, never a
hidden internal test record. Publication is never granted by default.

Additive and reversible: no table created or dropped, no column removed, **no INSERT and no seed
data of any kind**. The migration round-trips (upgrade → downgrade → upgrade) on a local database.

## 3. Writer rules (Phase 54 anchor writer, extended)

`internal_test` requires **all** of:

- `engagement_category=internal_test`
- **`real_client_data=false`**
- **`client_accessible=false`** — excluded from real-client access paths by default
- a **reserved internal-test `client_id` namespace** (`99999`, or a `99999_` / `internal_test_`
  prefix)
- `capsule_publication_authorized` may be `true` or `false`, decided deliberately

`real_client` requires:

- `engagement_category=real_client`, `client_accessible=true`
- it may **not** use the reserved namespace — the rule is bidirectional, so the two namespaces
  cannot bleed together and a test record cannot mix into real-client workflows
- it may **not** authorize capsule publication; no real-client publication authority is designed yet

**Capsule publication requires explicit authorization *and* no real client data** — plus
`client_accessible=false`. All conditions are checked together, for every category.

Every violation is denied with `invalid_classification` **before any database connection is
opened**. The classification is part of the replay fingerprint, so a changed classification on the
same anchor id is an `idempotency_conflict`, never a silent overwrite.

The writer remains **create-only**: one `session.add`, one commit, writes only `engagements`, never
touches `Client`, and uses no `UPDATE` / `DELETE` / `merge` / bulk operation / raw SQL / schema
operation. **Runtime `SELECT` + `INSERT` remains sufficient.** Receipts report the classification as
closed-vocabulary labels and booleans and still never echo the `engagement_label`.

## 4. Retention

**Runtime holds no `DELETE`, so cleanup is not assumed.** These records are durable by design —
that suits their intent, and it is why disposable synthetic smoke records remain disallowed.

## 5. What is still required

**Phase 56 creates no records.** The first internal test engagement creation remains a **separately
approved future phase**, which must supply the Phase 55 §8 creation packet in full and re-run the
three gates. The Phase 51 no-write / no-enablement decision remains in force.

**Not yet built:** read-side isolation. `client_accessible=false` is now recorded on the row, but no
client-facing read path exists to enforce it. Whatever read path is eventually built must filter on
this column explicitly — the flag is the contract, not the enforcement.

**Production is still at migration 013.** Migration 014 exists in the repository and has **not**
been applied to production; the production verifier still expects 013 deliberately. Applying it is a
separately approved operation.

---

## 6. Phase 57 update — the contract now has enforcement

§5 noted that `client_accessible=false` was recorded but unenforced, because no read path existed.
Phase 57 added the primitive: [`peak/db/engagement_read_isolation.py`](../peak/db/engagement_read_isolation.py)
supplies row predicates and SQLAlchemy filter clauses whose **default mode excludes internal test
engagements**, with internal/admin visibility available only on explicit opt-in, and a separate
compound predicate for publication eligibility. **Phase 57 creates no records** and applies no
migration to production. See
[`PHASE57_INTERNAL_TEST_READ_ISOLATION.md`](PHASE57_INTERNAL_TEST_READ_ISOLATION.md).

---

## 7. Phase 58 update — migration 014 is now applied to production

§5's statement that "production is still at migration 013" is **superseded**. In Phase 58, migration
`014_engagement_classification` was applied to production using the production migration credential.
Production now carries `engagement_category`, `real_client_data`, `client_accessible`, and
`capsule_publication_authorized` on `engagements`, and the production verifier's expected production
head moved from `013` to `014`.

Phase 58 applied **schema only**: no production application record was created, read, updated, or
deleted; no writer was invoked; no runtime credential was used; and **no internal test engagement
was created**. The first internal test engagement anchor remains a separately approved future phase.
See [`PHASE58_PRODUCTION_MIGRATION_014_VERIFICATION.md`](PHASE58_PRODUCTION_MIGRATION_014_VERIFICATION.md).
