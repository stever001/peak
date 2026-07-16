# Evidence Record Lifecycle (Phase 14)

The stages an evidence record moves through, from a raw reference to (eventually)
governed, review-approved evidence. This is a **governance/architecture description**;
Phase 14 stores nothing and approves nothing automatically. Evidence records are **not
authoritative merely because a worker created them**.

## Stages

1. **Raw evidence reference** — a `RawEvidenceReference` pointing at a source (interview,
   walk-around, photo, source-system observation, report) with a short, non-sensitive
   preview and capture metadata. Not yet normalized.
2. **Normalized draft evidence record** — the Evidence Normalization Worker produces a
   `NormalizedEvidenceRecord`: production-shaped structure (`evidence_type`,
   `operational_area`, `inventory_process_area`, title, summary, quality signals) stamped
   with the review gate — `output_status = draft`, `review_status = needs_review`,
   `authoritative = false`, `client_facing_approved = false`.
3. **needs_review** — the record awaits human/QA review. Nothing advances it automatically.
4. **approved_internal** *(future)* — a human/QA reviewer may advance the record to
   `approved_internal` after checking traceability, consistency, and completeness. Only
   then is it treated as authoritative for internal use. The **QA / Review Gate**
   ([`QA_REVIEW_GATE.md`](QA_REVIEW_GATE.md), Phase 15) is the production-shaped but
   **no-side-effect** scaffold that computes this decision — `approve_internal` means
   internal reliance only, and it stores nothing.
5. **client_facing_approved** *(future)* — becoming client-facing requires an **explicit**
   further human approval gate; a worker or agent may never set it.
6. **rejected / superseded / archived** — a reviewer may reject, supersede (replace with a
   better record), or archive evidence. These follow the `EvidenceStatus` /
   `ReviewStatus` families in [`GOVERNANCE_STATES.md`](GOVERNANCE_STATES.md) and
   [`STATE_TRANSITIONS.md`](STATE_TRANSITIONS.md).

## Relationship to future controlled DB storage

Normalized records are shaped to fit the controlled engagement database (the
`evidence_references` / `engagement_records` tables and audit fields — see
[`DATABASE_RECORD_MODEL.md`](DATABASE_RECORD_MODEL.md) and
[`DATABASE_ACCESS_AND_AUDIT.md`](DATABASE_ACCESS_AND_AUDIT.md)). **No database write
happens in this phase**; a future governed writer assigns ids and persists records under
access control, carrying an `agent_run_id` for provenance.

The step that prepares this persistence — without performing it — is the **Phase 18 Evidence
Persistence Mapping** ([`EVIDENCE_PERSISTENCE_MAPPING.md`](EVIDENCE_PERSISTENCE_MAPPING.md),
[`EVIDENCE_WRITE_PLAN_POLICY.md`](EVIDENCE_WRITE_PLAN_POLICY.md)): it maps a normalized
record into an `EvidencePersistenceDraft` and routes it through the Phase 17 controlled
writer boundary as a no-op plan targeting `evidence_references` / `create_draft`. It is
**DB-aware but not DB-writing** — `evidence_record_id` / `created_at` stay unset for a future
controlled DB writer, and the review gate is preserved.

That future write is now performed by the **Phase 21 Evidence Controlled Writer**
([`EVIDENCE_CONTROLLED_WRITER.md`](EVIDENCE_CONTROLLED_WRITER.md)): it creates exactly one
review-gated `evidence_references` row, stamping the server-controlled `id` and `created_at`
the draft left unset, after re-loading the authoritative stored `Engagement` scope from the
database (the Phase 18 snapshot is not trusted) and enforcing DB-level idempotency. A retried
write returns an `idempotent_replay` rather than a duplicate; a conflicting key is denied.

## Relationship to future capsule candidate preparation

Only after evidence is review-approved, well-scoped, and source-labeled can it feed
**capsule candidate** preparation
([`DATABASE_TO_RESOLVER_MAPPING.md`](DATABASE_TO_RESOLVER_MAPPING.md),
[`RESOLVER_CAPSULE_ARCHITECTURE.md`](RESOLVER_CAPSULE_ARCHITECTURE.md)). The worker sets
`capsule_candidate_ready = false`; capsule readiness is a later governed decision, and no
capsule publication is designed or implemented here.

## Authority principle

A normalized record is a **draft**. Structure and confidence signals help reviewers, but
they never substitute for review: evidence records are **not authoritative merely because
a worker created them**.
