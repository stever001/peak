# Controlled DB Writer Boundary (Phase 17)

The policy and validation boundary that every *future* controlled database write must pass
through — defined precisely, but **not executed**. Phase 17 is a controlled DB write
boundary scaffold: **DB-aware but not DB-writing**. **AgentNet integration is not complete.**

## Purpose

Phases 14–16 produced review-gated worker output, decided whether it may be relied on
internally, and prepared a review-record write plan — all with no side effects. Each of
those still needs an actual, governed path to the controlled engagement database. Phase 17
defines that path's **front door**: what a future DB writer may write, which
tables/actions are allowed, which governance checks are required, and how no-op write plans
are validated — without writing anything.

## How Phase 17 follows Phase 16

- **Phase 16** ([`REVIEW_PERSISTENCE_BOUNDARY.md`](REVIEW_PERSISTENCE_BOUNDARY.md)) prepares
  a *review-specific* persistence write plan (a `ReviewRecordDraft` + `ReviewWritePlan`).
- **Phase 17** generalizes that idea into a **generic controlled writer boundary** any
  future persistence phase routes through: a `ControlledWriteRequest` → allowlist +
  governance checks → a no-op `ControlledWritePlan` and an in-memory
  `ControlledWriteAuditDraft`.
- **Phase 17 does not write to the database.** A future controlled DB writer executes the
  plan.

The package lives in `peak/persistence/`, deliberately **not** in `peak/db/`: it stays
stdlib-only and imports no SQLAlchemy, no Alembic, and no `peak.db` session/model modules.
A future live writer may bridge these contracts to `peak.db` models.

## DB-aware but not DB-writing

The `ControlledWritePlan` is production-shaped — it names a real `target_table` and
`requested_action` — but nothing is persisted:

- **no live database connection** and no database read/write;
- **no SQL execution**;
- **no stored records** and no stored data;
- the plan reports `database_write_made = false`, `database_connection_made = false`,
  `sql_execution_made = false`, `stored_record_created = false`, and
  `requires_controlled_db_writer = true`;
- the `ControlledWriteAuditDraft` leaves `audit_record_id = None` and `created_at = None`
  for future controlled-DB assignment.

A **write plan is not a write**; **write plans are not writes**. A **future controlled DB
writer** performs the real write under [`DATABASE_ACCESS_AND_AUDIT.md`](DATABASE_ACCESS_AND_AUDIT.md).

## Table/action allowlist

Every request is checked against an explicit **table/action allowlist**
([`CONTROLLED_WRITE_ALLOWLIST.md`](CONTROLLED_WRITE_ALLOWLIST.md)): the `target_table` must
be allowlisted (and not prohibited) and the `requested_action` must be allowlisted (and not
match a prohibited pattern). Anything else is denied.

## Idempotency key requirement

Every request must carry an **idempotency key** (`idempotency_key`). It is required now for
future write safety — a future controlled writer uses it to dedupe and to make retries
replay-safe. A request without one is denied at the boundary, before any plan is built.

## Subject stored-scope comparison

A controlled write acts on a specific stored record, so the write must be authorized against
that record's own **stored authorization scope**. The boundary requires:

```
request.authorization_scope == subject.stored_authorization_scope
```

**Owner/client/engagement matching is necessary but not sufficient:** a request may match
the subject's identity yet carry a scope the record does not store. In Phase 17 the stored
scope is supplied in memory via `ControlledWriteSubject.stored_authorization_scope`; a
future controlled writer loads it from the controlled DB. See
[`DB_BACKED_REVIEW_SCOPE_POLICY.md`](DB_BACKED_REVIEW_SCOPE_POLICY.md).

## Prohibited effects (never planned here)

- **no client-facing approval** — a controlled write may never create it;
- **no financial verification** — the boundary never verifies financial impact;
- **no capsule publication** — no capsule is prepared or published;
- **no credentials/secrets storage** — such actions are rejected by pattern;
- **no deletes or migrations** — delete / hard_delete / migrate / seed actions are rejected;
- **raw SQL is prohibited** — a `raw_sql` action never reaches a plan;
- **no live LLM / AgentNet / MCP / resolver / network call.**

## Future controlled DB writer

When the controlled database integration lands, a governed writer will execute the
`ControlledWritePlan`: open a connection, run the mapped insert/update against the
allowlisted table, assign `audit_record_id` / `created_at`, and persist the
`ControlledWriteAuditDraft` for audit — under access control and enforcing the same stored
scope and allowlist checks. **That write does not happen in Phase 17.**
