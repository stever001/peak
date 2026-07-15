# QA / Review Gate (Phase 15)

How Peak evaluates worker/agent outputs for **internal** approval, rejection, return for
revision, supersession, or continued review. This is a **production-shaped** decision
scaffold that is **no-side-effect**: it persists nothing and confers no final authority.
**AgentNet integration is not complete.**

## Purpose

Phase 14 produced the first **production-shaped but review-gated** outputs — normalized
evidence drafts that default to `draft` / `needs_review` and are never authoritative on
their own ([`EVIDENCE_NORMALIZATION_WORKER.md`](EVIDENCE_NORMALIZATION_WORKER.md),
[`EVIDENCE_RECORD_LIFECYCLE.md`](EVIDENCE_RECORD_LIFECYCLE.md)). Something has to *decide*
what happens to those drafts. Phase 15 is that decision layer: a QA / Review Gate that
evaluates a worker or agent output and returns a structured decision — approve for internal
reliance, reject, return for revision, supersede, or keep under review.

## How Phase 15 complements Phase 14

Phase 14 **creates** review-gated drafts; Phase 15 **evaluates** them (and other future
agent/worker outputs) before Peak relies on them internally. The two are complementary
halves of the same governance posture:

- Phase 14 worker output → `draft` / `needs_review`, non-authoritative.
- Phase 15 review gate → a production-shaped decision about that output, still with **no
  side effects**.

The review gate evaluates worker/agent outputs **before internal reliance**. It does not
generate content and it does not store its verdict.

## Production-shaped but no-side-effect

The decision *shape* is ready for the future controlled database (a `ReviewRecord`), but
Phase 15 executes none of it:

- **no database write** — no review record is stored in this phase;
- **no live LLM call, no AgentNet call**, no MCP/resolver call, no network call;
- **no file write, no client-facing output, no capsule publication**;
- **no stored review records** — the result is an in-memory dataclass returned to the
  caller.

Every `ReviewGateResult` reports `database_write_made`, `llm_call_made`,
`agentnet_call_made`, `network_call_made`, `capsule_publication_made`, and
`client_facing_output_created` all `false`.

## `approve_internal` means internal reliance only

Put plainly: approve_internal means internal reliance only.

The strongest decision available in Phase 15 is `approve_internal`. It means Peak may rely
on the output **internally** — for its own assessment, drafting, and consulting work. It
sets `authoritative = true` **for internal use only**. It does **not** make the output
client-facing, and it does **not** verify financial impact or ready a capsule.

- **Client-facing approval remains separate** and future — a distinct human gate; a review
  decision may never create it, and `client_facing_approved` stays `false` in every case.
- **Financial impact verification remains separate** and future — the review gate never
  verifies financial impact.
- **Capsule publication remains separate** and future — `capsule_candidate_ready` stays
  `false`; no capsule is prepared or published here.

These prohibited decisions are rejected outright: `client_facing_approve`,
`publish_capsule`, `verify_financial_impact`, `approve_authoritative_external` (see
[`REVIEW_DECISION_MODEL.md`](REVIEW_DECISION_MODEL.md)).

## What Phase 15 does not do

- **No live LLM / AgentNet / MCP / resolver / network / database call** — the gate is
  deterministic and side-effect-free.
- **No stored review records** — nothing is persisted.
- **No authority creation** — a permitted request only means the gate *may derive* a
  production-shaped decision; a human still records the outcome later.

## Future relationship to `ReviewRecord` in the controlled DB

The controlled data architecture already anticipates a **`ReviewRecord`** written by a QA
reviewer under access control ([`DATABASE_ACCESS_AND_AUDIT.md`](DATABASE_ACCESS_AND_AUDIT.md),
[`DATABASE_RECORD_MODEL.md`](DATABASE_RECORD_MODEL.md)). When the controlled database
integration lands, a future governed writer will persist the `ReviewDecision` derived here
as a `ReviewRecord` — carrying `owner_id`, `authorization_scope`, reviewer identity, and an
audit trail. **That write does not happen in Phase 15.** The gate's job today is only to
compute the decision deterministically; storing it, and any real authority, remains future
work under human governance.

## Boundaries

- **No authority escalation to client-facing** — a review decision may never create
  client-facing approval.
- **No financial verification** — the gate never verifies financial impact.
- **No capsule publication** — deferred and not implemented here.
- **No stored review records / no database write in this phase.**
- **No AgentNet / LLM / network call in this phase.**
