# Phase 226 — Lead Review of an Observation

Back to [`PHASE_INDEX.md`](PHASE_INDEX.md). Baseline `c18e317`.

**Status: implemented in the repository; not deployed.** Production stays on Phase 225 (`e86ae6f`,
head `025`). Migration 026 is not applied.

## Purpose

One governance outcome: **a consultant's observation can become eligible to support a
recommendation, but only when the engagement's Lead Consultant has reviewed it, exactly as worded,
and judged it reliable enough to rely on.** Nothing drafts a recommendation.

## Exact gap

Peak Method templates ask for recommended process changes, and since Phases 222–224 phase work
reaches the assessment as consultant observations. Following the path through the code:

| Step | Before Phase 226 |
|---|---|
| A consultant observation | A discovery-derived finding. `DiscoveryFinding` has no eligibility field at all (Phase 206) |
| Phase 117 eligibility | Applies only to evidence-backed findings: a targeted approving review, reliability medium or high, an `operational_finding` claim scope, a persisted statement, a resolved source |
| Reaching that rule from the product | **Impossible.** No consultant route writes `evidence_references`, `source_ingestion_records` or `review_records`. They are written only by the Phase 21/22/24 controlled writers in ops and lab paths |
| Result | No consultant engagement can ever have a recommendation-eligible finding. Production's 2 evidence rows and 9 review rows were not written by any consultant route |

Contract C4 says discovery "never becomes reviewed evidence or recommendation eligibility on its own;
only the governed evidence and review path can create those". The missing piece is not a rule that
blocks too much. **It is a fact Peak never records: a review of the observation by someone with
authority to stand behind it.**

## The missing fact

> The engagement's Lead Consultant has reviewed this observation, exactly as it reads, and approves it
> for internal reliance as an operational finding at a stated reliability, or declines it.

1. **What fact.** A judgement about one statement: that it is sound enough to rely on, and how
   reliable it is. Reliability is the Phase 117 vocabulary (`low`, `medium`, `high`).
2. **Who.** The engagement's Lead Consultant (`engagements.assigned_consultant_id`). This is the same
   holder as the Lead artifact approval (AL15), so no new role exists. An Admin who is not the Lead
   cannot review. The Lead may review their own observation, and the assessment says so ("who
   recorded it"). Production has one consultant, so requiring a second person would make the path
   unusable.
3. **Why it cannot be derived.** Basis, linked captures and task origins describe the footing. None
   of them is anyone's judgement that the statement is right. Deriving eligibility from them would
   remove the review control.
4. **Mutable or historical.** Historical. Each review is a new row, numbered per observation; the
   highest is current. A decline, or a new approval, supersedes it. Nothing is edited or deleted.
5. **Provenance.** Reviewer, observation, engagement, decision, reliability, the exact text reviewed,
   the review number and the time. The request must name the text's SHA-256 and the current review
   the Lead was shown, as an approval names its package hash.
6. **Effect on the finding.** None. The observation and its finding are unchanged. The review is a
   separate governed record, and eligibility is derived beside the finding.

## Selected mechanism

**One explicit human action, one small append-only record, and a derived rule** (C3, preference 3–4):

- `POST /observations/{id}/lead-review`: the Lead approves (`approve_internal`, with a reliability)
  or declines.
- `observation_lead_reviews`: one row per review, insert-only.
- `observation_recommendation_block_reasons` in `peak/reports/discovery_assessment.py`: a pure rule
  over the current review and the finding. Empty means eligible.

| Phase 117 control (evidence) | Phase 226 counterpart (observation) |
|---|---|
| A review targets the cited evidence | A Lead review targets this observation in this engagement. A review of another observation or engagement never counts |
| Every targeting review is an internal approval | The current review is `approve_internal`. A decline blocks |
| Reliability medium or high | The Lead's stated reliability is medium or high. Low, missing or unrecognised blocks |
| Claim scope `operational_finding` | The approval itself asserts it: "approve for internal reliance as an operational finding". A Lead who would not assert that declines |
| A persisted finding statement | The observation text is persisted, and it must equal the text the Lead approved. **An edit after review blocks** until the Lead reviews again |
| The source resolves | The reviewed observation is a stored record of this engagement, read through the assessment's own visibility path. No source ingestion record exists for an observation, and none is invented |

The Phase 117 rule itself is byte-identical to the baseline. Evidence-backed findings keep every
control exactly as before.

## Alternatives rejected

| Candidate | Why not |
|---|---|
| Derive eligibility from basis, captures or task origin | Removes the review control. Weakens C5 |
| Use `review_records` with an observation target | Written only by the Phase 22 controlled writer, whose subject is the engagement and whose reviewer is free text. A second writer on the same table would mix two authorities. The evidence reader would pick the rows up as unresolved links. Reliability has no column there |
| Write an `evidence_references` row (plus a source record and a review) from the observation | Turns consultant notes into governed evidence, which C4 forbids. Duplicates the finding. Phase 118 would immediately draft its template recommendation, and the Final Report, its content hash and every package for that engagement would change |
| A "promotion" workflow moving the finding to another section | Changes the finding and the report. The fact is a review, not a move |
| Any consultant may review | Authority must be someone accountable for the engagement's content. That is the Lead |
| Require a reviewer other than the author | Unusable with one consultant in production. Recorded and shown instead |
| Show eligibility in the Final Report | Report content would change, and packages would go stale. Not needed until recommendations from observations exist |

## Persistence and schema

Migration **`026_observation_lead_reviews`**: additive, creating one table and altering none. Not
applied to production.

- Columns: `id`, `client_id`, `engagement_id`, `observation_id`, `reviewer_consultant_id`,
  `decision`, `reliability`, `reviewed_statement`, `review_number`, plus the governance and audit
  mixin columns.
- Checks: the decision is `approve_internal` or `decline`; an approval has a reliability and a
  decline has none; `review_number >= 1`. `(observation_id, review_number)` is unique, so two
  concurrent reviews cannot both become current.
- **Append-only**: an ORM update or delete is refused, and `RUNTIME_TABLE_PERSISTENCE` is
  `append_only`. There is one create action in `WORKSPACE_WRITE_COLUMNS`.
- **Grants**: none to change. The runtime role already holds SELECT and INSERT schema-wide, and no
  UPDATE is needed. The Phase 50 gate would fail on one.
- **Collation**: the identifiers are `GovernedString` (`utf8mb4_bin` on MySQL), so the verifier's
  governed-column count rises once 026 is applied.
- **Verifier pin**: stays at `025`. It moves only after 026 is applied in production.

## Eligibility, recommendation and report impact

- **Eligibility**: `DiscoveryAssessmentContext.recommendation_eligibility`, one entry per finding,
  derived on each read. `DiscoveryFinding` still has no eligibility, review or reliability field.
- **Recommendations: none.** Phase 118 runs only on evidence-backed findings and is unchanged. No
  recommendation text is drafted, and the assessment's recommendations stay empty and `blocked`.
  Drafting a recommendation from an eligible observation is a separate decision.
- **Internal assessment**: a reviewed finding shows its Lead review and eligibility. Its discovery
  sentence then says that only an observation with an approving Lead review carries a reliability
  rating and can be eligible. **An assessment with no Lead review is byte-identical** to the
  baseline's (pinned).
- **Final Report: unchanged.** Its composers and renderers are byte-identical, a review leaves its
  content hash unchanged, and packages still match. **Known boundary:** the report's discovery
  sentence still says this material carries "no review status, no reliability rating, and no
  recommendation eligibility". After a Lead review that is inexact as a statement about Peak's
  records, though still true of what the report shows. The phase that lets an eligible observation
  support a recommendation in the report must change that sentence.
- **Artifacts**: no approval, release, package or rendition state changes.

## API and UI

- `GET /observations/{id}/lead-review`: any consultant. Returns the history (newest first), the Lead,
  whether you are the Lead, the text hash and the derived eligibility. Reads only.
- `POST /observations/{id}/lead-review`: `{decision, reliability, statement_hash,
  current_review_id}`. Refusals: `no_lead_consultant`, `not_lead_consultant`, `observation_changed`,
  `review_changed` (422, as the Lead approval's are), and 422 for an invalid body. Repeating the
  current decision on the same text writes nothing.
- **The observation page** gets a "Lead review" panel. It says what is reviewed (the text as it reads
  now), what an approval means, that **it does not create a recommendation and the Final Report does
  not change**, and that an edit voids the approval. Only the Lead sees the form, and nothing is
  prefilled.
- **The assessment page** shows one line on a reviewed finding: the review, and eligibility "(no
  recommendation is drafted from it)".
- **Degrade path**: before the API is deployed, the panel's read fails and the panel is not shown. The
  assessment line needs the new field, which an older API does not send.

## Readiness and status

No change to task, phase, readiness or completion. The harness compares whole-database snapshots.

## Advisory boundary (C21)

The new wording names no pass/fail, score, audit or compliance concept (harness scan). An approval
is "for internal reliance". It is not a client-facing approval and grants nothing outside Peak.

## Non-goals

No model use, recommendation prose, automatic review, promotion or derivation, inference from
captures or documents, OCR, scoring, client approval, billing, AgentNet publication, review console
or generalized approval framework. No change to Phase 117/118, evidence or review writers, or the
Final Report.

## Validation

`tests/validate_phase226_observation_lead_review.py` (`make validate-phase226`, in `make validate`):
- **Schema:** the migration; append-only in the model, allowlist and policy; the verifier pin.
- **Eligibility rule:** every control, target-specific review, the current review, determinism.
- **Baseline equality:** the Phase 117 rule, Phase 118, the report modules, the evidence reader and
  the approvals and artifacts modules are byte-identical to `c18e317`.
- **Unreviewed output:** with no review, the assessment and report are pinned to the baseline's
  output.
- **Authority:** logged out 401; no Lead, a non-Lead Admin, another consultant and another
  engagement's Lead refused; stale text and stale review refused.
- **Provenance:** every recorded field. A repeat writes nothing.
- **What does not change:** the observation; the evidence and review tables; tasks, phases,
  readiness and artifacts; the Final Report; packages. Reads write nothing.
- **Changes over time:** an edit blocks; re-review, decline and a low rating.
- **Static UI:** the panel's wording.

Phases 224 and 225 now accept a single later migration, Phase 226's 026. Phase 11 lists the new
table.

## Production sequencing (proposed, not performed)

1. The commit is `[skip render]`. Vercel may build the web first (degrade path above).
2. Read-only preflight: head 025, 38 base tables, the verifier, the Phase 50 gate and the 30-table
   baseline.
3. Apply **026** with the migration credential, under explicit approval. Verify 39 base tables,
   head 026, the new table empty, and no other table changed.
4. Move the verifier pin to 026 (a docs/tools commit) and rerun the verifier. Expect the governed
   column count to rise by the new table's identifiers, all deterministic.
5. Deploy the API manually on Render, with Auto-Deploy still off.
6. Read-only checks: `/healthz` 200; logged out, the new routes return 401; the preservation checks.
   The Phase 50 gate must still pass, with no UPDATE grant on the new table.

No synthetic review is created for acceptance. The first real Lead review is deferred until a Lead
reviews a real observation.
