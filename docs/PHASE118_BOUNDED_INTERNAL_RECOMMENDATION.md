# Phase 118 — Bounded Internal Recommendation

**Baseline:** `e604b90` — *Add Phase 117 recommendation eligibility*. Back to the
[phase index](PHASE_INDEX.md).

## 1. Status

**Small product-functionality phase. No database access, no persistence, no writer, no migration, no
LLM, no client-facing output.** Peak now generates **one bounded internal recommendation per
recommendation-eligible finding**, and none for a blocked finding.

## 2. Shape

`InternalRecommendation` in `peak/reports/internal_assessment.py`, attached to `InternalAssessment.recommendations`:

| Field | Value |
|---|---|
| `recommendation_id` | `rec_<finding_id>` — deterministic |
| `finding_id` | the finding it comes from |
| `text` | the bounded template below |
| `supporting_evidence_ids` / `supporting_source_ids` / `supporting_review_ids` | carried from the finding |
| `internal_only` | always `True` |
| `requires_human_review` | always `True` |

No ROI, severity, ranking, priority, cost, timeline, or client-facing language. The Phase 36
`InternalReportRecommendationCandidate` was **not reused**: it is a planner slot that carries no text
and is tied to reviewer-decision references on the planner path Phase 111 set aside.

## 3. Generation rule

Deterministic, not LLM-based. A finding receives a recommendation only when Phase 117 marked it
`recommendation_eligible` (which already requires a persisted statement). The text is the fixed
`RECOMMENDATION_TEMPLATE`:

> Investigate and validate corrective action for the finding: "<persisted finding statement>"

The statement is quoted verbatim; the recommendation asks for investigation and validation and names
no root cause and no prescribed fix. **Blocked findings receive no recommendation** and keep their
blocker reasons. Eligibility rules are unchanged.

## 4. Internal assessment

An eligible finding shows `Internal recommendation: <id>`. The Recommendations section lists only the
recommendations actually generated — text, evidence, source, supporting reviews, internal-only, and
human review required — with status `internal_draft`. With none generated it still renders **Blocked**
with the bridge's reasons. `client_facing` stays false and `requires_human_review` stays true. The
Phase 111 bridge's own `recommendations` list stays empty. When findings exist but carry no
confidence caveat, the Evidence and confidence section now reads "No additional evidence-confidence
caveats." rather than "No findings to assess."

## 5. Results

- **Phase 107 finding:** blocked; **no recommendation**.
- **Synthetic eligible finding** (targeted approving review, `medium` reliability, persisted statement):
  exactly one recommendation, `rec_fnd_000`, citing `evid_8151dad609974ea0`,
  `ing_d67b76327aba4add`, and its review.
- Fallback-statement, missing-statement, and non-approving-review cases: no recommendation.

## 6. Proof

The Phase 113 harness was extended again, 88 → **97 checks, passing**. One Phase 117 check that
expected "none was drafted" for the eligible document was narrowed to the bridge's empty
`recommendations`. No new test file, no Makefile change.

## 7. Next product step

**An end-to-end internal engagement exercise** — run the route on a real internal engagement and
judge whether the output is useful — not more recommendation infrastructure. Not approved by Phase 118.
