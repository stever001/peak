# Phase 95 — Minimal Internal Lab Assessment Draft

**Type:** Workflow execution. **Docs-only.**

**Baseline:** the committed Phase 94 commit `a435772` — *Document Phase 94 lab review record*.

**What this phase did.** It produced a minimal internal lab assessment draft from the completed
depth-one controlled lab chain, in documentation. **No writer was invoked, no database record was
created, and no database was contacted.** No migration `015`, no schema, model, enum, allowlist,
writer, gate, or harness change. No production, cloud, or provider access. `peak_lab_scenario` was
not read or written. `docs/Peak_Investor_Overview_AI.docx` was not touched.

`peak_lab` remains at **exactly four application rows**, unchanged from Phase 94.

---

## 1. Purpose

Turn the completed depth-one lab chain into a minimal internal assessment — the first time the
Phase 88 measurement is carried all the way to a stated internal conclusion — and decide what comes
next.

## 2. Why this is docs-only, and not a database-backed report draft

**The lab gate refuses the report-draft writer.** This was verified rather than assumed. Evaluating
the existing Phase 89 gate against `internal_assessment_report_drafts/create_internal_assessment_report_draft`
returns `outcome=denied`, `reason=writer_target_not_lab_enableable`, `lab_write_authorized=false`.
The same denial applies to `internal_report_review_packets`. A control pair,
`evidence_references/create_draft`, authorizes in the same run — so the denial is specific to the
target, not an artifact of the check. The gate contacted no database; it is pure over its inputs.

The gate's enableable set is exactly three pairs — source ingestion, evidence reference, review
record — all exercised once each in Phases 92–94. **A report draft is outside it.** Creating one
would require a new authorization phase, which this phase deliberately does not open.

## 3. Chain basis

| Phase | Record | Id |
|---|---|---|
| 90 | `engagements` anchor | `lab_internal_test_001` |
| 92 | `source_ingestion_records` | `ing_d67b76327aba4add` |
| 93 | `evidence_references` | `evid_f094cbe4b47d4048` |
| 94 | `review_records` | `rev_70b5da9f14d54488` |

Measurement source: the Phase 88 read-only pass over lab scenario `internal_test_inventory_ops_v1`
version `v1`. Row-count posture is taken from the committed Phases 90–94 records; **no lab
verification connection was made in this phase**, because those records are sufficient and current.

---

# The Assessment

**Title.** Minimal internal lab assessment: controlled-chain viability on the Phase 88 lab scenario.

**Scope.** Internal Peak lab only. This assesses **whether Peak's controlled record chain works**,
using a synthetic lab scenario as the material. It does not assess an inventory operation, a client,
or a production system.

**Basis.** One Phase 88 measurement pass, and four controlled lab records — one anchor, one source
ingestion, one evidence reference, one review decision.

## Findings

**F1 — The controlled chain completes end to end at depth one.** A scenario measurement became a
source-ingestion record, then an evidence reference, then a reviewed decision, each through an
existing narrow writer under a gate that authorized exactly one target per phase. Nothing outside the
chain was written; every other controlled table remains empty.

**F2 — The narrow claim boundary survived three hand-offs.** The Phase 88 posture — internal
synthetic, partial, not client evidence, not production evidence — is restated in the evidence
reference's own summary and again in the review record's reasons. Phase 94 verified the Phase 93
boundary as booleans without reading body text. **This is the most useful thing the chain
demonstrated**: a claim did not silently widen as it moved between records.

**F3 — The scenario is repeatably measurable.** Phase 88 recorded that the content hash matched the
Phase 85 published value, that all 32 stored counts and sums were independently recomputed from rows
with **0 mismatches**, and that referential integrity held with 0 orphans and 0 contradictions.
Read-only posture was proven by measurement, not grant text: five deliberate write attempts were all
refused by the server.

**F4 — Readiness is partial across every dimension measured, by design.** Phase 88: *"No domain
measures 'yes' and none measures 'no.' Every domain is partial — which is the scenario behaving as
designed."* R1, R2, R5, R8, R9 and R10 each yielded deterministic coverage with named blockers.

**F5 — Location attribution, not SKU attribution, is the R1 constraint.** Every inventory row
resolves to an item, so SKU attribution is unblocked; 7 rows cannot be placed, and once item-master
quality and quantity presence are also required, Phase 88 records that *"fewer than half the rows
survive."* Coverage is not accuracy, and R1 accuracy was explicitly not addressed.

**F6 — A presence-only readiness rule would over-count.** Phase 88: *"A presence-only readiness rule
would over-count usable items by 1 in 10."* One item carries every required attribute yet remains
unusable because `ambiguous` encodes a semantic conflict rather than a missing value. **Any future
readiness rule must consult the completeness classification, not attribute presence alone.**

**F7 — The R5 population is too small to generalize from.** Phase 88 records 7 putaway events with 3
usable and states conclusions from it *"should be treated as directional even within the lab."*

**F8 — The chain's review record is invisible to the existing report planner.** This phase found it
by inspection. The Phase 36 planner recognizes six reference categories —
`intake_note_refs`, `source_ingestion_refs`, `evidence_reference_ids`,
`agent_task_queue_record_ids`, `review_bundle_record_ids`, `internal_reviewer_decision_record_ids`.
**`review_records` is not among them.** So of the planner's 14 sections, the depth-one chain
supplies references for 6 (source inventory, evidence summary, operational findings, inventory risk
areas, process improvement candidates, system data readiness), 3 need no references at all
(executive overview, evidence gaps, next steps), and **5 are blocked**: engagement context and intake
summary want intake notes, AI agent readiness wants task-queue records, and internal recommendations
and review status want review-bundle and reviewer-decision records. The Phase 94 review satisfies
none of the planner's review categories.

## Limitations

This assessment establishes **none** of the following, and must not be read as establishing them:

- inventory accuracy, or any conclusion about on-hand quantity
- source-system truth, or R8 authority precedence, which remains unconfirmed
- client evidence, or any real-client readiness
- production evidence
- authoritative evidence — the review recorded `authoritative=false` deliberately
- capsule readiness or AgentNet publication readiness
- that the evidence row was mutated to approved — **it was not**
- that the review approval propagated to the evidence row — **it did not**
- that the reviewed target was FK-enforced or loaded by the review writer — **it was neither**
- that idempotency replay was exercised for Phases 92–94 — it was verified structurally only

Every figure cited is an internal synthetic lab-scenario value. Per Phase 88, no measured rate may be
presented as a client finding, a benchmark, or a projection. R10 has no independent population and
should never be cited as a separate measurement. R3–R7 remain deferred as a program scope, and the
Phase 64 R5 export remains uncollected.

## Recommended next action

**Add breadth before depth.** One evidence reference over one measurement dimension is enough to show
the chain works; it is not enough to assess anything. The choice is between:

- **(a) a second evidence reference** from a distinct Phase 88 dimension on the existing
  source-ingestion record — cheapest, tests whether one source can carry more than one claim; or
- **(b) a second full chain** — source ingestion, evidence, review — for a different measurement
  basis, which also exercises whether two chains stay independent.

**(a) is the smaller next step and answers the narrower question first.** Either way, F8 is the more
consequential finding for planning: if a richer internal assessment is meant to use the existing
planner, the gap is not more evidence but the **record types the planner actually reads** — and
review-bundle and reviewer-decision writers are not lab-enabled either.

**This phase performs neither option.** Both need their own approval.

---

## 4. Explicit non-actions

- No writer invoked, and none enabled.
- No database record created; no database contacted, including for verification.
- No database-backed report draft created — the gate refuses it.
- No migration `015`, no live Alembic migration.
- No schema, model, enum, allowlist, writer, gate, or harness change.
- No production, cloud, or provider access; no environment value read.
- No scenario access; no row body of any controlled table read or reproduced.

## 5. Baseline at the end of this phase

| Property | Value |
|---|---|
| Alembic head | `014_engagement_classification` |
| Migrations / migration 015 | 14 / does not exist |
| Controlled Peak tables / writers | 18 / 12 |
| Production write enablement | None standing; gate reports false |
| `peak_lab` application rows | **4** — unchanged (Phases 90, 92, 93, 94) |
| `peak_lab_scenario` | Not read, not written |
| New harnesses added | None |
