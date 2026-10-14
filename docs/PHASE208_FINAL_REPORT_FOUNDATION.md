# Phase 208 — Final Report foundation

Phase 206 gave the internal assessment its discovery side; Phase 207 put it in production. Phase
208 adds the first **Final Report** composition layer: the same assessment, rearranged into the
sections a final report will eventually carry, so a consultant can read it as a report and review
it internally.

It is a foundation, and deliberately small. It is **deterministic, internal, and derived**: no LLM,
no client-facing approval, no export, no stored report, and no production deploy.

Baseline `cf1eab9` — *Record Phase 207 assessment production cutover*.
Index: [`PHASE_INDEX.md`](PHASE_INDEX.md).

**Status: built and validated locally. Not deployed.** Production stays at Phase 207, schema
`017_discovery_workflow`, and Render Auto-Deploy remains **OFF**.

> **OPEN ITEM, carried forward and still open: production Admin acceptance is pending provisioning
> of `admin@peakinventorysolutions.com`.** Authenticated production discovery and assessment
> acceptance remain pending for the same reason. No temporary Admin may be created. The Phase 208
> report has, like the assessment it is built from, never been produced against production data.

## What was built

| Piece | Where |
|---|---|
| Pure composer + Markdown renderer | `peak/reports/final_report.py` — `compose_final_report`, `render_final_report_markdown` |
| Read-only endpoint | `GET /engagements/{id}/final-report` in `peak/consultant_api/app.py` |
| Consultant page | `/engagements/[id]/final-report` (`web/app/(workspace)/engagements/[id]/final-report/page.tsx`, `web/components/final-report-view.tsx`) |
| Links | "Final report" from the engagement page and from the assessment page |
| Validation | `tests/validate_phase208_final_report_foundation.py` (`make validate-phase208`) |

```
engagement_id
  -> build_consultant_internal_assessment   (Phase 119/206, unchanged)
  -> compose_final_report(assessment, engagement)   (Phase 208, pure)
  -> render_final_report_markdown(report)           (Phase 208, pure)
```

The composer's inputs are the assessment the existing workflow already built and the workspace
engagement dict the route already fetched (label and client name only). It imports nothing from
`peak.db`, opens no connection, and does not re-query anything.

## Report structure

Six sections, always in this order (`SECTION_ORDER`):

| # | Section | Material | Content |
|---|---|---|---|
| 1 | Executive overview | report | engagement, client, North Star (+ context), summary lines that are **counts only** |
| 2 | Discovery summary | consultant working material | interview coverage (counts), discovery-derived findings quoted exactly, discovery limitations |
| 3 | Low-hanging-fruit opportunities | consultant working material | consultant-flagged items with entered effort/value, in the Phase 206 display grouping |
| 4 | Evidence-backed findings | evidence-backed, governed | the assessment's findings with review status, reliability, claim scope, eligibility; confidence notes |
| 5 | Internal recommendations | evidence-backed, governed | only the Phase 118 recommendations for Phase 117-eligible findings |
| 6 | Limitations and human review | report | fixed boundary statements, the assessment's evidence limitations, discovery limitations |

The report carries `status: internal_draft`, `client_facing: false`, `approved_for_client: false`,
and `requires_human_review: true`, and its Markdown says so at the top.

**No prose that requires interpretation.** Every line is a fixed label, a stored value quoted
exactly, or a count. The executive summary reads like "3 consultant observation(s), of which 2
flagged as low-hanging fruit" — it never characterises what the observations mean.

## The evidence / discovery boundary

Carried through from Phase 206, unchanged:

- Discovery material appears only in sections 1 (North Star), 2 and 3, each labelled
  *consultant working material*, on screen with a pill and in Markdown in the heading.
- Evidence-backed findings and recommendations appear only in sections 4 and 5, labelled
  *governed material*.
- Section 6 states the distinction in fixed wording: discovery is not reviewed evidence and has no
  review status, reliability or recommendation eligibility; evidence is shown with its recorded
  review status and reliability; the report is internal and requires consultant review.
- **Recommendations are never created here.** The composer passes through the assessment's
  recommendations and defensively drops any whose finding is not eligible. A
  low-hanging-fruit flag is never turned into a recommendation.

## Low-hanging fruit: grouping, not ranking

Candidates arrive in the Phase 206 display order (entered value high → low, then entered effort
low → high, unstated last). The composer only splits that order into labelled groups of
consecutive equal (value, effort) pairs — e.g. *Value High · Effort Low*. It never reorders, never
numbers, and no group or candidate has a rank, score, priority, tier, or ROI field. The section
repeats the Phase 206 grouping text and adds: *not approved recommendations, not a formal ranking,
and not a return-on-investment estimate*.

## API and UI

- `GET /engagements/{id}/final-report` → `{engagement, report, markdown}`. Authenticated consultant
  required (401 otherwise); unknown or not-visible engagement → 404, via the same Phase 57
  visibility path the assessment uses. POST/PATCH/PUT/DELETE → 405. Repeated reads are identical.
- `/engagements/[id]/final-report` — internal-draft banner, a wrapping section nav, the six
  sections (reusing the assessment page's cards, coverage tiles and trace lines), and a collapsed
  *Markdown source* block for copying. Single column on phone, two-column card grids from `lg`,
  touch-sized targets, no horizontal scroll. No save, approve or export control exists.

## What was not built, and why not

- **No persistence, no migration 018, no new table, no cached report.** The report is recomputed
  from the assessment on every request, so it cannot drift from the records behind it.
- **No LLM synthesis.** Everything is deterministic.
- **No PDF/DOCX export, proposal, billing/quote, signatures, or AgentNet publication.**
- **No client-facing approval.** There is no approval state, and `approved_for_client` is always false.
- **No production deploy.** Schema, grants and data untouched.

## Validation

Run for this phase: `tests/validate_phase208_final_report_foundation.py` (PASS), `npm run build`
(clean, `/engagements/[id]/final-report` in the route table), `npm run lint` (clean). `make validate` (exit 0, 81 harness runs, all PASS)
was also run because several older harnesses scan `docs/IMPLEMENTATION_PLAN.md`, which this phase
edits.

The harness covers: composition from the existing assessment (API report equals the assessment's
discovery findings, coverage, evidence findings and limitations); North Star present; discovery and
evidence sections distinct (no discovery statement in the evidence or recommendation sections);
low-hanging-fruit grouping preserves order and carries no ranking field; only eligible
recommendations appear (a hand-built recommendation for a blocked finding is dropped); no-discovery
and North-Star-only engagements render; the endpoint refuses every write method and repeated reads
are identical; no migration 018, composer imports only its sibling report modules.

**Next:** internal review of the report shape; export and client-facing approval are later,
separately approved phases. Deploying Phase 208 is its own cutover.
