# Phase 96 — Internal Assessment Planner: `review_records` Review-Support Path

**Baseline.** `e07e015` — *Draft Phase 95 minimal lab assessment*.

**Classification.** Planner path adaptation / workflow-execution unblock. **No DB record was
created. No writer was invoked. No database was contacted. No migration 015 was created.** No
schema, model, enum, writer, allowlist, or gate was changed.

## Why this phase existed

Phase 95 finished the depth-one controlled lab chain —

```
engagement anchor → source_ingestion_records → evidence_references → review_records
```

— and then found (F8) that the chain's review was **invisible** to the Phase 36 internal assessment
planner. The planner recognized six reference categories: `intake_note_refs`,
`source_ingestion_refs`, `evidence_reference_ids`, `agent_task_queue_record_ids`,
`review_bundle_record_ids`, `internal_reviewer_decision_record_ids`. **`review_records` was not
among them.** Adding more evidence would not have fixed that, because the gap was in what the
planner could *name*, not in what the chain had produced.

## Part A — What inspection found

**Reference categories, before this phase.** `REF_CATEGORY_RECORD_TYPES` in
`peak/reports/contracts.py` mapped six request fields to six durable record types. `REF_CATEGORIES`
is derived from that mapping, so the same six names drove reference normalization, the governance
identity/safety scan, the section requirement table, the candidate slots, the reference counts, and
the deterministic plan fingerprint.

**How a section becomes supplied, blocked, or not needed.** `SECTION_REF_REQUIREMENTS` maps each of
the fourteen sections to the categories that support it. A section with **no** requirement is
`synthesis_only` — structured from the other sections, needing no reference. Otherwise
`_plan_section` compares the requirement list against the supplied references: all present →
`ready_for_internal_drafting`; some present → `partial_supporting_references`; none present →
`blocked_no_supporting_references`, and the section id is added to `blocked_items`. Each missing
category also opens one `missing_supporting_references` gap.

**Why `review_records` was invisible.** Three linked reasons, all in the planning boundary and none
in the database:

1. `REF_CATEGORY_RECORD_TYPES` had no `review_records` entry, so no category named the table.
2. `InternalAssessmentReportPlanRequest` had no matching field, so a caller had no place to put the
   id. Because governance name-scans any attribute that is *not* a declared field, bolting one on
   would have been denied rather than ignored.
3. `_finding_candidates` and `_recommendation_candidates` read `refs["review_bundle_record_ids"]`
   literally as the sole review-support category, and `SECTION_REF_REQUIREMENTS` named only that
   category for `review_status` and `internal_recommendations`.

**Classification of the blockage: vocabulary plus request shape. Not schema-blocked.** The
`review_records` table already carries every field this path could need — `target_id`,
`subject_record_type`, `decision`, `authoritative`, `output_status`, plus the governance mixin's
`review_status`, `lifecycle_status`, `owner_id`, `client_id`, `engagement_id`,
`authorization_scope`, and the `idempotency_key` / `payload_fingerprint` pair backing replay
detection. Nothing needed to be added to the schema, so **migration 015 was not created and was not
needed** — the expected outcome held.

**Approval is recorded, not propagated.** The Phase 22 review writer records a decision *about* a
target; it does not load, mutate, FK-enforce, or approve that target. The planner had to be adapted
in a way that carries that distinction rather than erasing it.

## Part B — The adaptation

Three narrow changes, all inside the existing planning boundary:

1. **A new reference category.** `review_record_ids → review_records` was added to
   `REF_CATEGORY_RECORD_TYPES`, with a matching `review_record_ids` field on the request. Because
   `REF_CATEGORIES` is derived, the new category inherits normalization, sorting/de-duplication,
   the identity and safety scans, the reference counts, and the fingerprint automatically.

2. **An interchangeability declaration.** `REF_CATEGORY_ALTERNATIVES` records that
   `review_bundle_record_ids` is equally satisfied by `review_record_ids`, and
   `REVIEW_SUPPORT_CATEGORIES` names both in canonical order. `_plan_section` now resolves each
   required category through `_supplying_categories`, and the candidate builders take their review
   support from `_review_support`. **Nothing was removed:** `review_bundle_records` and
   `internal_reviewer_decision_records` keep their existing paths exactly.

3. **The caveat travels with the plan.** `REVIEW_RECORD_SUPPORT_CAVEAT` is appended to the plan's
   reasons, and to the notes of any section whose support came from a review record.

**What the support deliberately is not.** Support is **category-level**: a review record was named.
The planner sees record ids, not the stored `decision`, `review_status`, `subject_record_type`, or
`authoritative` flag — the boundary reads no database, and `GovernedRecordReference` carries only
identity and scope, so there is nothing to correlate against. The recommended field-level acceptance
semantics (`decision = approve_internal`, `review_status = approved_internal`, an internal-compatible
scope, a compatible subject type) would require the boundary to model detailed records, which it does
not do for any other category. Adding that machinery for one category alone would have been out of
proportion to the gap. **A consumer that needs a higher assurance than "a review record was named"
must correlate those stored fields deliberately, outside this boundary.**

The evidence trace attributes support to the category that actually supplied it, so a plan never
reports a `review_records` id under the `review_bundle_record_ids` name.

**Wording note.** The finding/recommendation block reason changed from "no review bundle
reference…" to "no review support reference (review_bundle_records or review_records)…". Phase 74
and Phase 78 quote the older wording; those quotes remain accurate as records of what those phases
saw.

## Part C — Tests

No new harness and no new test file. The checks were added to the existing planner test,
`tests/validate_phase36_internal_assessment_report_planning.py`, as section 21, and the later
section numbers were shifted. That file already owns every planner behavior these checks extend, so
a separate file would have duplicated its request builder, its side-effect helper, and its leak
scanner for no gain. It runs under `make validate` as it already did.

The added checks prove: the review-bundle path still satisfies sections and clears finding blocks;
the reviewer-decision path still drives recommendation slots; a `review_records` reference now
satisfies review support and is attributed to its own category; review support does **not**
manufacture breadth (intake, agent-task-queue, and reviewer-decision gaps stay open); and a review
record implies no client-facing, production, authoritative, capsule, publication, AgentNet,
financial, or execution posture, no approval, and no evidence-row mutation or approval propagation.
Determinism, ordering/duplicate insensitivity, and reference leak safety are covered for the new
category.

## Part C.1 — Eight ungated harness freezes had to be repaired first

The planner change is DB-free and touches no writer, model, enum, allowlist, or gate — yet it
failed **eight** existing harnesses, every one on the same check:

- Phases 65, 66, 67, 68, 69, 70, 72 each assert *"no file under `peak/` was modified by this phase
  at all"* against the **working tree**, with no authoring-time gate. That judges every later
  phase's uncommitted work against a past phase's allowlist.
- Phase 84 asserts *"no writer file was added or edited"* but passes the whole `peak` tree as the
  pathspec, so the check froze far more than its own label claims.

This is exactly the defect Phase 91 catalogued — *"ungated working-tree file freezes… 34 harnesses
assert a path has no pending diff, and only 5 use the authoring-time gate that makes such a claim
correct"* — and its recommendation 3 is to add that gate. Both repairs follow patterns already in
the repo:

- The seven blanket freezes now run under `phase_never_committed(HARNESS_REL)`, the same helper used
  in Phases 47, 49, 50, 51, 53, and 54. A harness only asserts its authoring-time scope while it has
  no commit of its own.
- Phase 84's pathspec was **narrowed to match its label** (`*_writer.py`), the same repair Phase 65
  already applied to its `alembic` pathspec, and a second unconditional check on `peak/db/models.py`
  and the controlled allowlist was added alongside it. Narrowing is stronger than gating here,
  because the stated invariant stays unconditional.

**No coverage was weakened.** Each of the eight keeps its substantive invariants unconditional: the
migration count and head, the table count, the writer count, "no controlled writer was modified",
"`models.py` was not modified", and "the allowlist was not modified" all still run on every phase.
Only the over-broad whole-package assertions were corrected. After the repair the full suite is
**72 harnesses, 0 failures**.

## Part D — Offline planner exercise (value-free)

Run offline against the depth-one chain **shape**, using the approved synthetic ids
(`lab_internal_test_001`, `ing_d67b76327aba4add`, `evid_f094cbe4b47d4048`, `rev_70b5da9f14d54488`).
No database was contacted, no row body was read, and no scenario data was used.

| Sections (of 14) | Without a review reference | With the `review_records` reference |
|---|---|---|
| ready for internal drafting | 6 | 7 |
| partial supporting references | 0 | 1 |
| blocked, no supporting references | 5 | 3 |
| synthesis only (no reference needed) | 3 | 3 |
| open gaps | 6 | 4 |
| blocked items | 6 | 3 |
| finding candidates | 1, blocked for want of review support | 1, internal draft candidate |
| recommendation candidates | 0 | 0 |

`review_status` moved from blocked to ready. `internal_recommendations` moved from blocked to
partial — the review half is now supplied, the reviewer-decision half is still missing.

**The three sections that remain blocked are blocked by real missing breadth, not by review
invisibility:** `engagement_context` and `intake_summary` want intake-note records, and
`ai_agent_readiness` wants agent-task-queue records. The chain has none of those. No recommendation
slot is created, because that family is driven by reviewer-decision references, which the chain also
does not have.

Posture in both runs is unchanged and internal-only: `output_status=plan`,
`review_status=needs_review`, `lifecycle_status=draft`, `requires_human_review=true`, and
`client_facing_approved`, `financial_verified`, `capsule_candidate_ready`, `publication_allowed`,
`execution_allowed` all false, with no side effect and no controlled write request.

## What this phase establishes — and does not

It establishes that the planner can now **name** the review the chain already produced.

It does **not** establish, and must not be read as establishing:

- inventory accuracy, or any conclusion about on-hand quantity
- client evidence, pseudo-client evidence, or production evidence
- authoritative evidence — the Phase 94 review recorded `authoritative=false` deliberately
- capsule readiness, publication readiness, or AgentNet readiness
- that approval propagated to `evidence_references` — **it did not**, and this change adds no such
  propagation
- that the review writer gained FK or target-load enforcement — **it did not**
- that a review record's stored decision or review status was read or verified by the planner

`peak_lab` remains at **four application rows by documented state**. This phase did not connect to
it to verify that, and does not claim to have.

## Recommended next step

The planner now has enough support to plan the chain, so the next step is the first of the three
Phase 95 branches: **attempt a DB-free internal assessment planner run, or a draft refinement, over
the depth-one chain.** Breadth remains the honest limit — three sections stay blocked for want of
intake notes and agent-task-queue records. If a later phase wants those sections, it should add one
additional evidence or reference chain **deliberately**, as its own phase, rather than widening the
planner further.
