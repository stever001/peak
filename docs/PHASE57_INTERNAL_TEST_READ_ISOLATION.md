# Phase 57 — Read-Side Isolation for Internal Test Engagements

**Status:** implementation phase — enforcement primitive only. **Phase 57 creates no records**, adds
no client-facing route or UI, enables no writer, and applies no migration to production.
**Baseline:** `2956e9c8b94a7fbf2aaea043ca43e443489f5558`
**Alembic head:** unchanged at `014_engagement_classification` (14 migrations, 18 tables, 12 writers)
**Module:** [`peak/db/engagement_read_isolation.py`](../peak/db/engagement_read_isolation.py)
**Harness:** [`tests/validate_phase57_internal_test_read_isolation.py`](../tests/validate_phase57_internal_test_read_isolation.py)
(`make validate-phase57`, in `make validate`; offline, temp-SQLite only)

---

## 1. The gap this closes

Phase 56 recorded `engagement_category`, `real_client_data`, `client_accessible`, and
`capsule_publication_authorized` on the row — and nothing consumed them. They were **a contract with
no enforcement**, because no read path existed yet.

Phase 57 adds the enforcement primitive **before** the first read path, so that path has a correct
thing to reach for instead of hand-rolling a filter and getting it subtly wrong. **Internal_test
classification is now backed by a read-side isolation primitive**, and **future real-client read
paths must use it.**

## 2. Read modes — exclusion is the default

| Mode | Admits | Internal test |
| --- | --- | --- |
| `CLIENT_FACING` *(default)* | `real_client` **and** `client_accessible` **and** `real_client_data` | **never**, under any argument |
| `INTERNAL_ADMIN` | real client engagements | **only** on explicit `include_internal_test=True` |

`CLIENT_FACING` is the default mode, so a caller that says nothing gets the excluding behaviour.
It ignores `include_internal_test` entirely — a client-facing read cannot be widened into showing
internal test data by passing a flag. **Internal/admin views must explicitly opt in.** An
unrecognised mode is refused (predicate) or raises (filter builder); it is never treated as
permissive.

## 3. `client_id` is not the access control

**`client_id=99999` is not sufficient by itself**, in either direction:

- A **reserved** id is rejected from client-facing reads even if `client_accessible` were somehow
  `true` — but this is **defence in depth, not the mechanism**.
- An **ordinary** id does not make a record visible: a row categorised `internal_test` with a normal
  `client_id` is still excluded.
- Narrowing a query by `client_id` cannot resurrect an excluded row; the classification clause is
  applied first and independently.

The mechanism is the classification columns. The reserved namespace stays a visible marker.

## 4. Publication eligibility is a separate question

`is_publication_eligible` requires the full compound rule — `internal_test` **and**
`real_client_data=false` **and** `client_accessible=false` **and**
`capsule_publication_authorized=true`. Flipping any one condition fails it.

This is **separate from client visibility**, and deliberately so: a publication-eligible engagement
is, by construction, invisible to every client. Being publishable is not being visible, and neither
implies the other.

## 5. Boundaries

The module **opens no database connection**, creates or modifies no record, imports and invokes no
writer, executes no raw SQL, reads no environment variable, and opens no file. It returns predicates
and SQLAlchemy filter clauses; the caller owns the session and query. Every predicate also works on
a plain row-like object, so it is usable without SQLAlchemy.

Disposable synthetic smoke records remain disallowed. Runtime still holds no `DELETE`.

## 6. Still outstanding

- **No client-facing read path exists yet.** This phase supplies the primitive; the first read path
  must actually call it. A read that bypasses `apply_read_isolation` is not protected by it.
- **Migration 014 was applied to production in Phase 58** (superseding this section's original
  statement that it had not been). The production verifier's expected production head moved from
  `013` to `014` at the same time. See
  [PHASE58_PRODUCTION_MIGRATION_014_VERIFICATION.md](PHASE58_PRODUCTION_MIGRATION_014_VERIFICATION.md).
- The first internal test engagement creation remains a separately approved future phase. Phase 58
  applied schema only and **created no production application record**.
