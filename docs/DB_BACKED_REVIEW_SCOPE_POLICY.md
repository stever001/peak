# DB-Backed Review Scope Policy (Phase 16)

The scope rule every future DB-backed review must obey: compare the request's authorization
scope against the subject record's **stored** authorization scope. This is a governance
**contract**; Phase 16 is **DB-aware but not DB-writing** and stores nothing.

## Why subject-level stored authorization scope is required

A review decision authorizes something to happen to a *specific stored record*. The
authority to act on that record depends on the record's **own** governance state — including
the `authorization_scope` it actually stores — not on whatever scope a request happens to
present. Scopes change: a record may be re-scoped, narrowed, or `revoked` after a request
was drafted. Only the **stored** scope reflects the record's current governance reality.

## Why request scope alone is insufficient

Trusting `request.authorization_scope` by itself lets a caller assert a broader (or simply
different) scope than the subject record permits. Identity is not authority:
**owner/client/engagement matching is necessary but not sufficient.** A request can match
the subject's owner, client, and engagement and still carry a mismatched scope — for
example a `fixture_test` request pointed at a live client record, or an
`internal_peak_only` request against a record stored as `client_private`. The stored scope
is the authoritative gate.

## Required comparison

```
request.authorization_scope == subject_snapshot.stored_authorization_scope
```

Both conditions must hold:

1. **Identity match (necessary):** request `owner_id` / `client_id` / `engagement_id` equal
   the subject snapshot's — necessary but **not sufficient** on its own.
2. **Stored-scope match (sufficient gate):** `request.authorization_scope` equals
   `subject_snapshot.stored_authorization_scope`. If the stored scope is missing or differs,
   the request is denied.

In Phase 16 the stored scope is supplied in memory via
`StoredReviewSubjectSnapshot.stored_authorization_scope`. **Future DB-backed review must
load the subject record scope from the controlled DB** (never from the request) before
comparing.

## Fixture/test scope must not mix with live client scope

`fixture_test` scope must not be mixed with live client/engagement scope. If either the
request scope or the subject's `stored_authorization_scope` is `fixture_test` while live
`client_id` / `engagement_id` values are present, the request is denied. This keeps
synthetic/test review flows from ever touching real engagement records.

## Denial behavior on scope mismatch

On any of the following the persistence request is **denied** (`permitted = false`) with an
explicit reason, and **no plan, draft, or record is produced**:

- `subject_snapshot.stored_authorization_scope` is missing;
- `request.authorization_scope` differs from `subject_snapshot.stored_authorization_scope`;
- request owner/client/engagement do not match the subject snapshot;
- the subject's `stored_lifecycle_status` is `revoked` / `archived` /
  `deleted_reference_only`;
- `fixture_test` scope is mixed with live client/engagement scope.

Denial is side-effect-free: **no live database read/write**, **no stored review records**,
**no client-facing approval**, **no financial verification**, and **no capsule
publication**.

## Audit expectations for the future `ReviewRecord` write

When a future controlled DB writer executes the plan, the persisted `ReviewRecord` must
capture — for audit — the subject record id, the **stored** authorization scope that was
matched, the request scope presented, the reviewer identity and role, the decision and its
next states, and timestamps ([`DATABASE_ACCESS_AND_AUDIT.md`](DATABASE_ACCESS_AND_AUDIT.md),
[`DATABASE_RECORD_MODEL.md`](DATABASE_RECORD_MODEL.md)). Recording *both* the stored scope
and the presented request scope makes the scope check itself auditable. **No such write
happens in Phase 16.**

## Generalized by the Phase 17 writer boundary

This stored-scope comparison is not review-specific: the **Phase 17 Controlled DB Writer
Boundary** ([`CONTROLLED_DB_WRITER_BOUNDARY.md`](CONTROLLED_DB_WRITER_BOUNDARY.md)) applies
the **same** rule — `request.authorization_scope == subject.stored_authorization_scope`,
with owner/client/engagement matching necessary but not sufficient — to every future
controlled write, alongside a table/action allowlist and an idempotency key. Any future
DB-backed persistence loads the subject's stored scope from the controlled DB and denies on
mismatch, exactly as described here.
