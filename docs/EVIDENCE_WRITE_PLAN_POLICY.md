# Evidence Write Plan Policy (Phase 18)

The rules that govern how normalized evidence becomes a *future* controlled write. This is a
governance **contract** enforced by the Phase 18 mapping
([`EVIDENCE_PERSISTENCE_MAPPING.md`](EVIDENCE_PERSISTENCE_MAPPING.md)) on top of the Phase 17
boundary. It is **DB-aware but not DB-writing**: **write plans are not writes**, and nothing
is persisted here.

## Why normalized evidence must pass through controlled write planning

Normalized evidence is high-quality but not authoritative, and it is client data destined
for controlled storage. It must not reach the database by an ad-hoc path. Routing every
evidence persistence attempt through the Phase 17 controlled writer boundary means the same
**table/action allowlist**, `idempotency_key`, and stored-scope checks apply to evidence as
to any other record. **Evidence workers still do not write directly to the DB** — the worker
normalizes, the mapper plans, and a future controlled DB writer executes.

## Why `idempotency_key` is required

Every request must carry an `idempotency_key`. It is required now for future write safety: a
future controlled writer uses it to dedupe and to make retries replay-safe, so a repeated
evidence persistence attempt cannot create duplicate `evidence_references` rows. A request
without one is denied before any draft or plan is built.

## Why `request.authorization_scope` must match `subject_snapshot.stored_authorization_scope`

Authority to write an evidence record depends on the governance state of the record it
belongs to — its stored parent/source/engagement subject — not on whatever scope a request
presents. The mapping therefore requires
`request.authorization_scope == subject_snapshot.stored_authorization_scope`.
**Owner/client/engagement matching is necessary but not sufficient:** a request may match
identity yet carry a scope the subject does not store. The request scope alone is
insufficient.

## Why the parent subject snapshot is the authorization anchor

A freshly normalized evidence record often has **no stored DB row yet** — there is no
persisted evidence record to check a scope against. So the authorization anchor is the
**stored parent/source/engagement subject** (`EvidencePersistenceSubjectSnapshot`), whose
`stored_authorization_scope` and `stored_lifecycle_status` are loaded (in future) from the
controlled DB. The new evidence inherits its write authority from that stored parent, which
is why the snapshot — not the new record — carries the stored scope.

## Target table / action

- `target_table = evidence_references`
- `requested_action = create_draft`

Both are on the Phase 17 allowlist ([`CONTROLLED_WRITE_ALLOWLIST.md`](CONTROLLED_WRITE_ALLOWLIST.md)).
The only Phase 18 persistence action is `prepare_evidence_reference_write_plan`.

## Review-gated defaults

The `EvidencePersistenceDraft` preserves the review gate — the mapper stamps these, never
inheriting a claim from the input:

- `output_status = draft`
- `review_status = needs_review`
- `authoritative = false`
- `client_facing_approved = false`
- `capsule_candidate_ready = false`

## What this phase does not do

- **No DB write in this phase** — no live database connection, no SQL execution, no stored
  records.
- **No direct writes from the evidence worker.**
- **No client-facing approval, no financial verification, no capsule publication.**
- **No live LLM / AgentNet / network call.**

## Future controlled DB writer requirement

Executing the plan — opening a connection, inserting the `evidence_references` draft row,
assigning `evidence_record_id` / `created_at`, and recording an audit entry — requires a
**future controlled DB writer** under access control
([`DATABASE_ACCESS_AND_AUDIT.md`](DATABASE_ACCESS_AND_AUDIT.md)). **That write does not
happen in Phase 18.**

That writer is delivered in **Phase 21**
([`EVIDENCE_CONTROLLED_WRITER.md`](EVIDENCE_CONTROLLED_WRITER.md),
[`EVIDENCE_IDEMPOTENCY_POLICY.md`](EVIDENCE_IDEMPOTENCY_POLICY.md)). It re-validates this same
policy at write-time against the *live* database — comparing `request.authorization_scope` to
the stored `Engagement.authorization_scope` (not the snapshot) and enforcing the idempotency
boundary with a DB unique constraint — before creating a single review-gated row.
