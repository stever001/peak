# Review Persistence Boundary (Phase 16)

How Peak will convert a **permitted** Phase 15 review outcome into a future controlled-DB
`ReviewRecord` — described precisely, but **not executed**. Phase 16 is **DB-aware but not
DB-writing**. **AgentNet integration is not complete.**

## Purpose

Phase 15 decides *whether* a review outcome is permitted (approve for internal reliance,
reject, return for revision, supersede, keep under review) with **no side effects**
([`QA_REVIEW_GATE.md`](QA_REVIEW_GATE.md), [`REVIEW_DECISION_MODEL.md`](REVIEW_DECISION_MODEL.md)).
Phase 16 defines *how* such a permitted outcome would later be **persisted** as a
`ReviewRecord` in the controlled engagement database — the record shape, the scope checks,
and the write plan — while still writing nothing.

## How Phase 16 follows Phase 15

- **Phase 15 decides** whether a review outcome is permitted (no side effects).
- **Phase 16 prepares** a future review persistence plan for a permitted outcome.
- **Phase 16 does not persist records.** It produces an in-memory `ReviewWritePlan` and a
  `ReviewRecordDraft`; a **future controlled DB writer** is required to actually persist
  them under access control.

The persistence boundary consumes a Phase 15 `ReviewGateResult` and refuses to plan
anything unless that result was itself `permitted=true` and fully side-effect-free (all of
`database_write_made`, `client_facing_output_created`, `capsule_publication_made`,
`llm_call_made`, `agentnet_call_made`, `network_call_made` are `false`).

## DB-aware but not DB-writing

The `ReviewRecordDraft` is **production-shaped** — its fields line up with the
`review_records` table ([`DATABASE_RECORD_MODEL.md`](DATABASE_RECORD_MODEL.md)) — but
review records are **not persisted in this phase**:

- **no live database read/write**, no database connection, and **no stored review records**;
- `review_record_id` stays `None` — a future controlled-DB writer assigns it;
- `created_at` stays `None` — reserved for future controlled-DB assignment;
- the `ReviewWritePlan` reports `database_write_made = false`,
  `database_connection_made = false`, and `requires_controlled_db_writer = true`;
- the `ReviewPersistenceResult` reports `stored_review_record_created = false`.

Nothing here opens a SQLAlchemy session or imports `peak.db`; a **future controlled DB
writer** performs the real write under [`DATABASE_ACCESS_AND_AUDIT.md`](DATABASE_ACCESS_AND_AUDIT.md).

## Critical scope rule (stored scope, not request scope)

A DB-backed review must compare `request.authorization_scope` against the subject record's
**stored** scope — `subject_snapshot.stored_authorization_scope` — not rely only on the
request scope. **Owner/client/engagement matching is necessary but not sufficient:** the
request may claim the right identity yet carry a scope that no longer matches what the
subject record actually stores. Because Phase 16 is the first DB-backed-review-readiness
phase, this is implemented now using an in-memory `StoredReviewSubjectSnapshot` that
carries `stored_authorization_scope`; a future DB-backed review loads that value from the
controlled DB. Full rationale and denial behavior:
[`DB_BACKED_REVIEW_SCOPE_POLICY.md`](DB_BACKED_REVIEW_SCOPE_POLICY.md).

## What Phase 16 does not do

- **No live database read/write**, no database connection, **no stored review records**.
- **No live LLM / AgentNet / MCP / resolver / network call.**
- **No client-facing approval** — a persistence plan may never create it (and the boundary
  rejects a gate decision that claims it).
- **No financial verification** — the boundary never verifies financial impact.
- **No capsule publication** — `capsule_candidate_ready` stays `false`; no capsule is
  prepared or published.
- **No file write, no connector code, no credentials, no DB files.**

## Future controlled-DB writer

When the controlled database integration lands, a governed writer will execute the
`ReviewWritePlan`: assign `review_record_id` and `created_at`, insert a row into
`review_records`, and record the reviewer, authorization scope, decision, and audit trail
under access control. **That write does not happen in Phase 16.** The boundary's job today
is only to prepare a correct, scoped, side-effect-free plan.

## Generalized by Phase 17

The review-specific plan here is generalized by the **Phase 17 Controlled DB Writer
Boundary** ([`CONTROLLED_DB_WRITER_BOUNDARY.md`](CONTROLLED_DB_WRITER_BOUNDARY.md),
[`CONTROLLED_WRITE_ALLOWLIST.md`](CONTROLLED_WRITE_ALLOWLIST.md)): the front door **all**
future controlled writes route through, enforcing a **table/action allowlist**, an
`idempotency_key`, and the same subject stored-scope check before any no-op write plan is
produced. `review_records` is one allowlisted target among several; the future controlled DB
writer is shared. Phase 17 is likewise **DB-aware but not DB-writing** and does not write to
the database.

## Realized by Phase 22

The plan this boundary prepares is executed by the **Phase 22 Review Record Controlled
Writer** ([`REVIEW_CONTROLLED_WRITER.md`](REVIEW_CONTROLLED_WRITER.md),
[`REVIEW_IDEMPOTENCY_POLICY.md`](REVIEW_IDEMPOTENCY_POLICY.md)) — the third real DB-backed
persistence path. Phase 16 stays DB-free (this mapper imports no SQLAlchemy / `peak.db`);
Phase 22 lives in the DB layer and re-loads the authoritative stored `Engagement` scope at
write-time rather than trusting the snapshot here, then creates one `review_records` row under
DB-enforced idempotency. `approve_internal` may set `authoritative=true` (internal reliance
only) and never creates client-facing approval.
