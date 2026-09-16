# Phase 116 — Consultant-Usable Internal Assessment

**Baseline:** `315cd57` — *Add Phase 115 persisted finding statement*.

## 1. Status

**Small product-functionality phase. No database access, no persistence, no writer, no migration, no
LLM.** Phase 116 produces the **first consultant-usable internal assessment** from persisted state:
a readable document assembled from stored records, at the end of the route Phases 113–115 built.

It is **internal-only and deterministic**. It creates no recommendation, no client-facing output, and
no prose of its own.

## 2. What was added

One small pure module, `peak/reports/internal_assessment.py`:

- `build_internal_assessment(report_inputs)` — turns the Phase 111
  `PacketViewReportInputs` into an `InternalAssessment` object;
- `render_internal_assessment_markdown(assessment)` — renders it as Markdown a consultant can read
  or copy directly.

**Why not reuse the Phase 36 plan object.** `InternalAssessmentReportPlan` is a *plan*: section
readiness, gaps, and candidate slots, explicitly carrying no prose, and reachable only through the
planner's own request boundary. Feeding it from the packet-view route would reintroduce exactly the
planner assumptions Phase 111 set aside. No renderer existed anywhere in the repo. So one small
composer was added instead of refactoring two boundaries together.

`peak/reports` stays free of SQLAlchemy and `peak.db`; the module is not exported from
`__init__.py`, following the Phase 110–115 precedent.

## 3. Structure

`InternalAssessment` carries engagement identity, `audience=internal`, `status=internal_draft`,
`client_facing=False`, `requires_human_review=True`, and:

| Section | Content |
|---|---|
| Operational findings | One entry per finding: persisted statement, evidence id, source id(s), effective **and** stored review status, supporting review ids, reliability, claim scope |
| Evidence and confidence | Counts of findings whose evidence is unreviewed, low reliability, or has no statement |
| Open limitations and unresolved questions | Strict `EngagementPacket` reasons, sections not supplied, unreviewed findings, missing statements, excluded evidence with reasons |
| Recommendations | Status `blocked`, plus the reasons the reporting bridge already computed |

**Every line is either a fixed label from this module or a value from a stored record.** Nothing is
generated, paraphrased, or inferred. A finding with no persisted statement says so and stays in the
document. There is no severity, priority, ranking, root cause, ROI, inventory-accuracy figure,
source-of-record claim, or operational prescription — none of those are supported by the current
evidence, so none appear.

## 4. Current output, in shape

For the documented lab engagement the assessment renders one finding: the Phase 107 evidence, with
its persisted statement verbatim, citing its source, **review status `unreviewed`** with the stored
`needs_review` shown separately, **no supporting reviews** (the Phase 94 review targets different
evidence), and **reliability `low`**. The source-availability evidence appears only under
limitations, as backing no finding. Recommendations render as **Blocked**, with reasons and no
drafted language. The footer states the document is internal, unapproved, and not a deliverable.

**The finding is usable for internal assessment, but it is not recommendation-grade.** It is
readable and traceable; it is unreviewed and low-reliability.

## 5. Proof

The existing Phase 113 harness was extended again rather than a new one added: **78 checks, passing**
(was 67). It proves one persisted finding appears, its statement appears **verbatim**, evidence and
source ids are present, review status is `unreviewed` with the stored status separate, reliability is
`low`, the Phase 94 review supports nothing, recommendations report blocked with nothing drafted, no
recommendation or analysis language appears, client-facing stays false, a missing statement is
declared rather than invented, and the rendered document is deterministic. The whole document is not
snapshot-tested.

## 6. Next product step

The persisted route now ends in something a consultant can read. The open question is no longer
plumbing but **what evidence and review state is required to earn a recommendation** — what a
reviewer must confirm, and what raises reliability above `low` — so that a finding can move from
readable to actionable.
