# Phase 94 — First Lab Review Record

**Type:** Controlled lab writer rehearsal. One durable lab record.

**Baseline:** the committed Phase 93 commit `9bdbbda` — *Document Phase 93 lab evidence reference*.

**What this phase did.** It created **exactly one** `review_records` row in `peak_lab`, recording an
internal review decision on the Phase 93 evidence reference — which referenced the Phase 92
source-ingestion record, which derived from the Phase 88 lab scenario measurement. It used the
existing Phase 89 lab writer-enablement gate as-is and the existing Phase 22 review writer. Nothing
else was written.

**What this phase did not do.** No production access and no production credential read. No provider
or cloud command. No Alembic `upgrade`, `downgrade`, or `stamp`, and **no migration 015**. No schema,
model, enum, allowlist, writer, or gate was changed. **No new test harness was added** — no defect
required one. No engagement, source-ingestion, evidence, intake, or client record was created, and
none of those writers was invoked. `peak_lab_scenario` was never opened, read, or written.
`docs/Peak_Investor_Overview_AI.docx` was not touched.

---

## 1. The gate, used as-is

Evaluated before any connection existed; the run refuses without writing unless it grants exactly the
one requested target.

| Gate field | Value |
|---|---|
| `outcome` / `reason` | `lab_write_authorized` / `lab_target_confirmed_and_scoped` |
| `authorized_writer_targets` | `review_records/create_review_record` |
| `anchor_bootstrap_authorized` | false |
| `production_write_authorized` / `safe_to_write_production_now` / `production_writer_enablement_authorized` | false / false / false |

The Phase 90 bootstrap confirmation was **not set and not needed**. This is the third and final use
of the ordinary lab data-record path Phase 89 built; all three enableable pairs have now been
exercised once each.

## 2. The credential, checked value-free

No value printed: file present, mode `600`, outside the repo, **exactly one** variable named
`PEAK_RUNTIME_DATABASE_URL`, expected scheme, user `peak_lab_runtime`, database `peak_lab`,
password/host/port/`ssl_ca` present, not the provider default, not the scenario schema, no production
marker. Read back as the credential itself: `SELECT` and `INSERT` only — **no `UPDATE`, `DELETE`,
`DROP`, `CREATE`, `ALTER`, or `GRANT OPTION`** — and **no visibility into `peak_lab_scenario`**.

**The absent `UPDATE` grant matters here.** A review that mutated its target would have needed one.
This writer does not, so the phase ran within the existing grant set and no grant was altered.

## 3. Before the write

Reachable, database `peak_lab`, lab runtime role, `alembic_version` one row at
`014_engagement_classification`, 18 controlled tables and no extras. `engagements` = 1,
`source_ingestion_records` = 1, `evidence_references` = 1, `review_records` = 0, every other
controlled table = 0, total 3. All three prior rows were verified field-by-field, and the Phase 93
evidence claim boundary was re-verified **as booleans only** — source-availability-only scope
present; inventory accuracy, client evidence, production evidence, reviewed status, authoritative
status, and publication readiness each denied — **without printing any evidence body text**.

## 4. The record

| Field | Value |
|---|---|
| `id` | `rev_70b5da9f14d54488` (server-controlled) |
| `owner_id` / `client_id` / `engagement_id` | `peak_internal_admin` / `99999` / `lab_internal_test_001` |
| `authorization_scope` | `internal_peak_only` |
| `target_id` | `evid_f094cbe4b47d4048` — the reviewed Phase 93 evidence reference |
| `subject_record_type` | `evidence_reference` (Phase 68 convention) |
| `decision` | `approve_internal` |
| `authoritative` | **false** (a real, stored column) |
| `previous_status` / `new_status` | null / `approved_internal` |
| `review_status` / `output_status` / `lifecycle_status` | `approved_internal` / `draft` / `active` |
| `reviewer` / `created_by` | `peak_internal_admin` |
| `source_reference_id` (in `details_json`) | `ing_d67b76327aba4add` — the Phase 92 record |
| `idempotency_key` | `phase94_lab_review_phase93_evidence_reference_001` |
| `payload_fingerprint` | present, 64 characters |

Receipt: `outcome=created`, `stored_record_created=true`, `transaction_committed=true`,
`existing_record_returned=false`, `outcome_uncertain=false`.

## 5. What this decision approves — and what it does not

The decision approves, for **internal lab reliance only**, that a Phase 88 lab scenario measurement
exists as a controlled Peak source-ingestion record, and that the Phase 93 evidence reference
describing that fact is well formed and correctly scoped.

It establishes **none** of: inventory accuracy, source-system truth, client evidence, production
evidence, or authoritative status. Client-facing approval, capsule candidacy, report drafting, and
AgentNet resolver publication all remain unauthorized.

**`authoritative` was left false deliberately.** The writer would have permitted `true` here —
`approve_internal` is the one decision for which it is allowed — and it was not taken. The reviewed
evidence carries `reliability=low` and its upstream measurement is partial and readiness-oriented.

**The Phase 93 asymmetry was respected.** `evidence_references` has no `authoritative` column, and
this phase confirmed that directly rather than assuming it. **No `authoritative=false` flag was read
from the evidence row**, because none exists. The non-authoritative posture rests on three other
things: the evidence writer's pre-connection enforcement, the row's governed state
(`review_status=needs_review`, `reliability=low`), and its claim-boundary summary — the last verified
as booleans only. The review record itself **does** carry a stored `authoritative` column, so from
Phase 94 onward that posture is independently readable for the review, if not for the evidence.

## 6. A review records a decision; it does not mutate its target

The writer is **INSERT-only** — one `session.add`, no `UPDATE` or `DELETE` path anywhere — so the
Phase 93 evidence row was not touched. Verified after the write: the evidence row is unchanged, still
`needs_review` / `draft` / `active`, with `updated_at` still equal to `created_at`.

**Two consequences worth carrying forward.**

1. **The approval is recorded, not propagated.** `review_status=approved_internal` lives on the
   *review record*. Anything reading `evidence_references` alone still sees `needs_review`. The
   evidence is internally approved only in the sense that a review record says so; joining the two is
   the reader's job, and there is no typed join to help.
2. **The writer never loads the reviewed target.** Its only DB reads are the `Engagement`
   authorization anchor and the idempotency lookup. `target_id` is a free-form `GovernedString(64)`
   with no foreign key, never existence-checked at write time — a wrong or dangling id would be
   accepted. This phase compensated by verifying the target row itself before writing, but that is an
   operator discipline, not a contract guarantee.

## 7. Contract differences worth recording

- **There is no free-text review summary field.** `ReviewRecordDraft` has no summary or rationale
  field, and the writer does not populate the row's `reason` column, which stays null. The claim
  boundary therefore lives in `details_json.reasons` as nine prefixed lines — the slot the contract
  actually provides — following the Phase 68 convention.
- **`previous_status` is null.** It is populated only from an optional in-memory
  `persistence_request.subject_snapshot`, which was not supplied, as in Phase 68. The reviewed row's
  actual prior status was verified out of band instead.
- **Minor convention divergences from Phase 68, both free-form fields:** `reviewer_role` is
  `peak_internal_admin` here rather than `internal_admin`, matching Phases 92–93 in this lab chain;
  and `source_reference_id` names the Phase 92 source-ingestion record rather than a packet
  reference, which keeps the chain link explicit.

## 8. After the write

Head still `014_engagement_classification` with one `alembic_version` row. `engagements` = 1,
`source_ingestion_records` = 1, `evidence_references` = 1 — all unchanged — and `review_records` = 1.
`intake_note_records`, `clients`, and every other controlled table = 0.

**`peak_lab` now holds exactly four application rows: the Phase 90 `engagements` anchor, the Phase 92
`source_ingestion_records` row, the Phase 93 `evidence_references` row, and this Phase 94
`review_records` row.**

The DB-enforced boundary `uq_review_records_idem` is present over four columns. Idempotency was
verified **structurally** rather than by a second invocation, because this phase authorized exactly
one writer call.

## 9. Durability and correction posture

The record is **durable**. No cleanup was attempted and none is available: the runtime role holds no
`DELETE`, so removal is impossible on this path by construction, not by policy. A correction requires
explicit later append-only or versioned handling — a superseding review record — never a runtime
deletion or in-place rewrite. Removal would require the migration credential, a separate approval not
authorized here.

## 10. Next

The lab chain is now complete end to end at depth one: anchor → source ingestion → evidence reference
→ review decision. **The next step is a decision, not another guardrail phase**: whether this chain
is sufficient to attempt a minimal internal lab assessment or report draft, or whether the chain
needs more breadth first. Adding another gate or harness by default is explicitly not the
recommendation — Phase 91 recorded why.

Worth weighing in that decision: the measurement underneath is partial and readiness-oriented, the
evidence is `reliability=low` and non-authoritative, and the approval is internal-only and not
propagated to the evidence row.

## 11. Baseline at the end of this phase

| Property | Value |
|---|---|
| Alembic head | `014_engagement_classification` (repo and `peak_lab`) |
| Migrations / migration 015 | 14 / does not exist |
| Controlled Peak tables / writers | 18 / 12 |
| Production write enablement | None standing; gate reports false |
| `peak_lab` application rows | **4** — Phases 90, 92, 93, 94, one each |
| `peak_lab_scenario` | Not opened, not read, not written |
| New harnesses added | None |
