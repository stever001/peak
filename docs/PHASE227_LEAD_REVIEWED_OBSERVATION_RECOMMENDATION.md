# Phase 227 — Lead-Reviewed Observation Recommendation

Back to [`PHASE_INDEX.md`](PHASE_INDEX.md). Baseline `ea1a629`.

**Status: implemented in the repository; not deployed.** Production stays on Phase 226 (`55e0dd2`,
head `026`). No migration.

## Purpose

One business outcome: **a consultant observation that has passed the Phase 226 Lead-review rule gets
the same bounded recommendation Phase 118 gives an eligible evidence-backed finding, and that
recommendation flows through the existing assessment, Final Report and package pipeline.** There is
no second recommendation architecture.

## Exact gap

| Step | Before Phase 227 |
|---|---|
| Phase 117 eligibility | Evidence-backed findings only (`recommendation_block_reasons`) |
| Phase 118 recommendation | `_recommendation_for(AssessmentFinding)`: `RECOMMENDATION_TEMPLATE` around the persisted statement, id `rec_<finding>`, evidence/source/review provenance |
| Phase 226 eligibility | Derived per discovery finding in `DiscoveryAssessmentContext.recommendation_eligibility`, but `build_internal_assessment` attached discovery last and **never read it** |
| Final Report (208/209), packages (212/213) | Carry `assessment.recommendations`, filtered to Phase 117-eligible findings |

Phase 118 is not sufficient on its own: it reads only `AssessmentFinding`, which is evidence-shaped
(an evidence id, source ids and review-record ids). An observation has none of them, and must not be
given any. **The missing piece is one adapter**: Phase 226 eligibility in, a Phase 118 recommendation
out, with the observation's own provenance.

## Selected mechanism

`build_internal_assessment` adds, after the evidence-backed recommendations, one recommendation per
discovery finding whose Phase 226 eligibility has **no blocker**
(`_observation_recommendations`):

- the same `RECOMMENDATION_TEMPLATE`, quoting the persisted statement exactly;
- the same id rule, `rec_<finding_id>` (`recommendation_id_for`), so `rec_disc_<observation>`;
- `internal_only` and `requires_human_review` true, as before.

It is derived on every read. A declined, low, unspecified, stale (edited), missing, wrong-engagement
or wrong-observation review gives none, because Phase 226 already blocks each of those. An edit makes
the recommendation disappear; a new qualifying review of the revised text brings it back with the same
id, the new text and the new review id. No stale recommendation object exists anywhere.

The assessment's recommendation status becomes `internal_draft` when any recommendation exists, as in
Phase 118. Evidence-backed recommendations come first and are unchanged.

## Provenance

`InternalRecommendation` gains two lists, empty for evidence: `supporting_observation_ids` and
`supporting_lead_review_ids`. An observation recommendation has **no evidence, source or review-record
id**. Reviewer and reliability resolve through the Lead review it names (append-only, Phase 226), and
the assessment shows them beside the finding. The discovery finding and the Lead review row are
unchanged. The observation never becomes an evidence-backed finding.

## Authority

None added. The consultant authors the observation; the engagement Lead owns the Phase 226 review;
package Lead and Final Approver authority (Phase 213) is unchanged. Recommendation construction is
deterministic and grants nothing. There is no recommendation approval action.

## Persistence and schema

**None.** No migration, table, grant, eligibility state or source record. The Phase 226 review is the
only persisted judgement. Stored canonical content omits the two new fields when empty
(`final_report_content`), so evidence-backed content, and every version stored before this phase,
keeps its exact bytes and still rebuilds (`final_report_from_content`). A version's source references
gain `lead_review_ids` only when a recommendation names one.

## Internal assessment

For an eligible observation: the review and eligibility lines (Phase 226), an evidence-status line
saying it is not evidence but is eligible for one bounded internal recommendation, and the
recommendation's id. In the recommendations section the recommendation names the consultant
observation "(not evidence)" and the Lead review instead of evidence, source and reviews. Blocked
observations keep their blocker reasons and get nothing. An assessment with no eligible observation is
byte-identical to the baseline's (pinned).

## Final Report

The recommendation appears in the existing recommendations section, named as resting on a consultant
observation (not evidence) and a Lead review. The content hash changes normally. The report stays an
internal draft, not client-facing.

**Wording corrections, only when the report holds such a recommendation** (otherwise every sentence
and the hash are unchanged):

| Wording | Was | Becomes |
|---|---|---|
| Recommendations heading | "Internal recommendations (evidence-backed only)" | "Internal recommendations (evidence-backed or Lead-reviewed)"; client: "Recommendations (evidence-backed or lead-reviewed)" |
| Recommendations material | `evidence_backed_governed` | `evidence_backed_or_lead_reviewed` ("governed — evidence-backed, or a Lead-reviewed consultant observation that is not evidence") |
| Boundary 1 (discovery) | "…carries no review status, reliability rating, or recommendation eligibility." | "It is not reviewed evidence. Only an observation the engagement's Lead approved, exactly as worded, at medium or high reliability is eligible to support a recommendation, and it remains an observation, not evidence." |
| Boundary 3 (recommendations) | "…only for evidence-backed findings already eligible under the Phase 117/118 rules." | adds "and for consultant observations eligible under the Phase 226 Lead-review rule, which use the same bounded wording"; client wording to match |
| Discovery sentence | "…no reliability rating, and no recommendation eligibility…" | `RECOMMENDED_TAIL`: only an approved observation has a reliability rating and can be eligible; it supports only the fixed, bounded wording and never becomes evidence |

The assessment uses `RECOMMENDED_TAIL` on the same condition; with Lead reviews but no eligible one it
keeps the Phase 226 sentence. The no-recommendation sentence is unchanged: when nothing is
recommended, no discovery item produced one. Headings for discovery and evidence are not changed.

## Artifacts and packages

No stored package, version or rendition is rewritten. When an eligible observation adds a
recommendation, the live draft's hash changes, so the existing Phase 213 check reports it no longer
matches the latest package. Approvals are tied to a package hash and do not carry over. A new
package holds the recommendation, starts unapproved, and its client renditions pass the client check:
the client line reads "For a consultant observation approved by the engagement lead; not evidence",
with no identifiers.

## Web

Types gain the two optional fields. The assessment and report views name an observation-based
recommendation as "a Lead-reviewed consultant observation, not evidence" and label the section
"Governed · evidence-backed or Lead-reviewed" only then. The report view's discovery note and the Lead
review panel no longer say no recommendation is drafted.

## Non-goals

Free-form, edited, LLM-generated, ranked, scored or prioritised recommendations; cost, ROI or
implementation plans; client acceptance; roadmap or task creation; automatic Lead review; OCR or
document inference; AgentNet publication; a recommendation table, approval or framework.

## Validation

`tests/validate_phase227_lead_reviewed_recommendation.py` (`make validate-phase227`, in
`make validate`):
- **eligibility**: unreviewed, declined, low, edited and wrong-engagement/observation give none;
  medium and high give one; re-review of the revised text gives one; a later decline removes it;
- **recommendation**: one per eligible finding, deterministic id and content, the unchanged Phase 118
  template, no prescriptive wording, no model client;
- **provenance**: observation and Lead review ids; reviewer and reliability resolve; no evidence,
  source or review-record id; the finding unchanged;
- **evidence path**: the Phase 117 rule byte-identical; evidence-only and evidence-with-declined
  output pinned to the `ea1a629` code; mixed recommendations keep separate provenance;
- **report and artifacts**: no Lead review pinned to the Phase 226 baseline; the corrected wording;
  internal and client renditions; round-trip of stored content; in the app, the stored package
  unchanged, the draft stale, nothing approved or released, a new package unapproved and client-clean,
  reads write nothing, and the observation, review row, readiness, tasks and phases unchanged.

Phase 225's renderer check accepts `report_discovery_text`. Phase 226's harness now asserts that only
an eligible review changes the report and packages, and that Phase 226 itself changed none of its
pinned modules.

## Production sequencing (proposed, not performed)

1. The commit is `[skip render]`. Vercel may build the web first; against the Phase 226 API the new
   optional fields are absent and the views read as before. Only the Lead review panel's wording runs
   ahead of the API until step 3.
2. Read-only preflight: head 026, 39 base tables, verifier, Phase 50 gate, baseline counts, and the
   `observation_lead_reviews` count (0 at the Phase 226 closure). At 0, no live draft changes on deploy.
3. Deploy the API manually on Render, with Auto-Deploy off. No migration, grant or pin change.
4. Read-only checks: `/healthz` 200; protected routes 401 logged out; preservation unchanged.

No synthetic observation or review is created for acceptance. The first live observation
recommendation is deferred until a Lead approves a real observation at medium or high reliability.
