# Client Isolation Model — Option A (Phase 34)

Peak stores operational client/engagement data in managed remote MySQL. This document records the
default tenant-isolation model.

## Option A is the default

**Client Isolation Option A: a shared managed MySQL database per environment, with strict tenant
columns and authorization gates.** Tenants (clients/engagements) share a managed database within an
environment and are isolated by columns and governed write paths rather than by a separate physical
database per client.

Rationale: it keeps the governed-writer surface uniform, keeps migrations and validation tractable,
and still enforces strict per-tenant authorization on every write. A stronger physical-isolation
option (database-per-client) may be designed later for specific clients, but Option A is the
default unless a stronger stored subject/isolation is explicitly designed.

## Mandatory tenant columns

Every operational table carries the universal governance axes:

- `owner_id`
- `client_id`
- `engagement_id`
- `authorization_scope`
- review/lifecycle status where applicable
- `idempotency_key` / `payload_fingerprint` where applicable

## The stored Engagement is the authorization anchor

The stored `Engagement` row is the authorization anchor for controlled writes. At write time each
controlled writer:

1. loads the stored `Engagement` from the DB (never trusting caller-supplied scope alone);
2. requires `engagement.authorization_scope` present and
   `request.authorization_scope == engagement.authorization_scope`;
3. requires `engagement.owner_id / client_id / id` to match the request;
4. requires `engagement.lifecycle_status` not to be `revoked` / `archived` /
   `deleted_reference_only`.

**Identity matching is necessary but not sufficient** — a stored-scope mismatch is denied even when
every identity field matches. This is the same anchor used by all eight narrow writers (Phases 20,
21, 22, 24, 27, 30, 33, and the Phase 34 intake-note writer).

## Isolation invariants

- No cross-tenant read/write path exists through the controlled writers; each write is scoped to a
  single `(owner_id, client_id, engagement_id)` and its stored `Engagement`.
- The idempotency uniqueness boundary always includes the tenant identity
  `(owner_id, client_id, engagement_id, idempotency_key)` so a key cannot collide across tenants.
- Client data is never committed to Git; it lives only in the managed MySQL environment databases.
