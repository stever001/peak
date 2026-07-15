# Evidence Persistence Mapping (Phase 18)

How a Phase 14 normalized evidence output becomes a *future* controlled write plan for the
`evidence_references` table — mapped precisely, but **not executed**. Phase 18 is
**DB-aware but not DB-writing**. **AgentNet integration is not complete.**

## Purpose

Phase 14 produces review-gated `NormalizedEvidenceRecord`s; Phase 17 defines the generic
controlled writer boundary. Neither one, on its own, connects evidence to persistence.
Phase 18 is that connective tissue: it maps a normalized evidence output into a
production-shaped `EvidencePersistenceDraft` and routes it through the Phase 17 boundary as a
no-op write plan — so the path from "normalized evidence" to "a governed future DB row" is
defined and testable without any database.

## How Phase 18 follows Phases 14 and 17

- **Phase 14** ([`EVIDENCE_NORMALIZATION_WORKER.md`](EVIDENCE_NORMALIZATION_WORKER.md))
  normalizes raw evidence into a review-gated record — no side effects.
- **Phase 17** ([`CONTROLLED_DB_WRITER_BOUNDARY.md`](CONTROLLED_DB_WRITER_BOUNDARY.md))
  defines the generic controlled writer boundary: a **table/action allowlist**, an
  `idempotency_key` requirement, and a subject stored-scope check.
- **Phase 18** maps evidence drafts into controlled write plans. **Evidence workers still
  do not write directly to the DB** — normalization and persistence-planning are separate,
  and every future write goes through Phase 17.

## Core flow

```
NormalizedEvidenceRecord / EvidenceNormalizationResult
  -> EvidencePersistenceDraft        (production-shaped, review-gated)
  -> ControlledWriteSubject          (Phase 17, from the parent subject snapshot)
  -> ControlledWriteRequest          (target evidence_references / create_draft)
  -> ControlledWritePlan             (Phase 17 no-op plan)
  -> no DB write
```

## DB-aware but not DB-writing

The `EvidencePersistenceDraft` is **production-shaped** — its fields line up with the
`evidence_references` table — but nothing is persisted:

- **no live database connection** and no database read/write;
- **no SQL execution**;
- **no stored records** and no stored data;
- the mapping result reports `database_write_made = false`, `database_connection_made =
  false`, `sql_execution_made = false`, `stored_record_created = false`, and the Phase 17
  plan's `requires_controlled_db_writer = true`;
- `evidence_record_id` and `created_at` are left `None` — **future controlled DB writer**
  assignments.

A **write plan is not a write**; **write plans are not writes**. The mapping also makes
**no live LLM/AgentNet/network call**, and produces **no client-facing approval**, **no
financial verification**, and **no capsule publication**.

## Production-shaped but still review-gated

The draft is ready in *shape* for controlled storage, but its *status* stays gated — the
mapping never advances authority:

- `output_status = draft`
- `review_status = needs_review`
- `authoritative = false`
- `client_facing_approved = false`
- `capsule_candidate_ready = false`

These are **stamped** by the mapper, never inherited from a claim on the input; and
governance rejects any normalized record that arrives already `authoritative`,
`client_facing_approved`, or `capsule_candidate_ready`.

## Subject stored-scope comparison

Because a freshly normalized evidence record may have **no stored DB row yet**, the write is
authorized against the stored parent/source/engagement subject. The mapping requires:

```
request.authorization_scope == subject_snapshot.stored_authorization_scope
```

**Owner/client/engagement matching is necessary but not sufficient:** the request must match
the subject snapshot's identity *and* the normalized record's identity, and the request
scope must equal the subject's stored scope. In Phase 18 the stored scope is supplied in
memory via `EvidencePersistenceSubjectSnapshot.stored_authorization_scope`; a future
controlled writer loads it from the controlled DB. See
[`EVIDENCE_WRITE_PLAN_POLICY.md`](EVIDENCE_WRITE_PLAN_POLICY.md) and
[`DB_BACKED_REVIEW_SCOPE_POLICY.md`](DB_BACKED_REVIEW_SCOPE_POLICY.md).

## Boundaries

- **No live database connection**, no database read/write, **no SQL execution**, **no stored
  records**.
- **No live LLM / AgentNet / MCP / resolver / network call.**
- **No client-facing approval**, **no financial verification**, **no capsule publication.**
- **No direct writes from the evidence worker** — persistence is always planned, never
  executed, in this phase, and always routed through the Phase 17 boundary. A **future
  controlled DB writer** performs the real write under
  [`DATABASE_ACCESS_AND_AUDIT.md`](DATABASE_ACCESS_AND_AUDIT.md).
