# Phase 61 — The Internal Test Intake Review Decision

**Status:** production-sensitive phase — **one application record written**. Exactly **one internal
review decision record was created** in production for the Phase 60 intake note. No Client record,
no additional Engagement, no second intake note, no source, evidence, report, or capsule record.
**Baseline:** `3444376ff85b3fc8e80e5b07e1360a8be17f50fd`
**Alembic head:** unchanged at `014_engagement_classification` (14 migrations, 18 tables, 12
writers) — Phase 61 adds no migration, no writer, and no allowlist pair
**Writer:** [`peak/db/review_writer.py`](../peak/db/review_writer.py) (Phase 22, unchanged)
**Operator utility:** [`tools/create_internal_test_intake_review_decision.py`](../tools/create_internal_test_intake_review_decision.py)
**Harness:** [`tests/validate_phase61_internal_test_intake_review_decision.py`](../tests/validate_phase61_internal_test_intake_review_decision.py)
(`make validate-phase61`, in `make validate`; offline, temp-SQLite only, contacts no production)

---

## 1. Why `review_records` was the right writer

The Phase 22 writer keeps two things separate that this review needs kept apart:

- **the authorization anchor** — `request.subject`, which must be the `engagement`; and
- **the reviewed target** — `draft.subject_record_id` / `draft.subject_record_type`, stored as
  `target_id` and described in the writer as "distinct from the Engagement authorization anchor".

That is exactly the shape of this review: the Phase 60 intake note is the *target*, reviewed under
the Phase 59 anchor's *authority*. Neither field is overloaded.

The alternative, `internal_reviewer_decision_records`, was **rejected**: its draft is shaped around
a **review bundle** — bundle refs, review plan items, evidence and source-ingestion ids — and has no
reviewed-target field at all. Representing an intake note there would have meant misusing a bundle
reference to mean something it does not mean. `review_records` is the narrower honest fit, and no
new writer was added.

## 2. The decision

| Field | Value |
| --- | --- |
| reviewed target (`target_id`) | `intn_b8b86b8c196c4595` (the Phase 60 intake note) |
| `subject_record_type` | `intake_note` |
| authorization anchor | `internal_test_001` (engagement) |
| `client_id` / `owner_id` | `99999` / `peak_internal_admin` |
| `authorization_scope` | `internal_peak_only` |
| `decision` | `approve_internal` |
| `authoritative` | `false` |
| `review_status` / `output_status` | `approved_internal` / `draft` |
| `client_facing_approved` / `capsule_candidate_ready` | `false` / `false` |
| reviewer / role | `peak_internal_admin` / `internal_admin` |
| `idempotency_key` | `phase61_internal_test_intake_review_decision_001` |
| stored record id | `rev_b82ff6f00790418f` |

`approve_internal` is the writer's vocabulary for **internal reliance only, never client-facing
approval** — `client_facing_approve`, `verify_financial_impact`, and `publish_capsule` are refused
outright by the writer. **The decision authorizes moving toward source/evidence collection, not
report or capsule publication.** `authoritative` was left `false` deliberately: this records an
internal determination, and nothing downstream should yet treat it as settled.

## 3. Findings — covered and missing V0 taxonomy categories

Coverage was assessed against
[`PEAK_INTAKE_QUESTION_TAXONOMY_V0.md`](PEAK_INTAKE_QUESTION_TAXONOMY_V0.md). The finding splits
along an axis worth naming:

**Covered qualitatively — all 14 V0 categories have narrative coverage.** The note touches
engagement context, pain points, item/SKU master, location structure, receiving through shipping,
counts and adjustments, stockouts and overstocks, systems of record, exports and reporting, SOPs and
exceptions, evidence availability, AI/AgentNet readiness, publication boundaries, and success
metrics.

**Incomplete quantitatively — the note carries no counts, rates, cadences, or dates.** Narrative
coverage tells you what to ask for; it does not support a measured finding. Categories recorded as
incomplete:

| Category | What is missing |
| --- | --- |
| 03 item/SKU master | duplicate rate and master size unquantified |
| 04 location structure | no location/bin naming model supplied |
| 06 counts and adjustments | count cadence, coverage, adjustment volume unquantified |
| 07 stockouts / overstocks | frequency and carrying cost unquantified |
| 08 systems of record | systems unnamed; precedence rule informal |
| 09 exports and reporting | export inventory, formats, cadence not enumerated |
| 11 evidence availability | nothing collected or normalized yet |
| 14 metrics and urgency | no target metric, baseline, or deadline |

That gap is precisely why the next step is collection rather than analysis.

## 4. Next evidence requests

The decision records eight next evidence requests: current inventory export by SKU and location;
item/SKU master export; adjustment history with reason codes, if available; recent receiving and
putaway records; recent cycle count or physical count results; stockout/backorder or fulfilment
exception data; available SOP and process documentation; and a system-of-record and data-export map.

**Recommended next downstream work is a source/evidence request and source ingestion planning** —
the source ingestion or evidence writer is the sensible next path to exercise. Report drafting,
capsule candidacy, and publication are explicitly not authorized.

## 5. Posture — internal-only and non-client-facing

The intake note **remains internal-only and non-client-facing**, and so does this decision. The
parent engagement is `internal_test`, holds **no real client data**, and is excluded from
client-facing reads by the Phase 57 isolation primitive. Nothing in this phase produced client-facing
output.

**The findings carry no note prose.** They are category labels and gap descriptors — the reviewer's
analysis, not the note's text. The note body remains outside the repository, and this phase's tools
never read, print, or store it.

## 6. What was not written

- **No Client record** — `clients` remains never-writable.
- **No additional Engagement** — the Phase 59 anchor was loaded as the authorization subject and
  left untouched.
- **No second intake note.**
- **No source record, no evidence record, no report record**, and no review packet, agent run, or
  task queue record — specifically: no source ingestion row, no evidence reference, no report
  draft.
- **No capsule** and no AgentNet publication.
- **No client-facing output**, approval, or financial verification.
- **No UPDATE, DELETE, manual SQL, cleanup, or stamp.**
- **No app table scan, count, or probe** beyond the writer's own stored-engagement load and its
  idempotency lookup.

## 7. Future forms

**Future real-client intake forms should be taxonomy-derived, not guessed.** This review is the
first evidence that the derivation rule earns its place: the gaps it found are precisely the ones a
category-to-deliverable mapping predicts, and they were found by comparing a note against the
taxonomy rather than against a reviewer's memory.

## 8. Still outstanding

- Source/evidence collection has not started; the decision authorizes planning it, not skipping it.
- The first **client-facing read path** must call `apply_read_isolation`.
- No writer is enabled; this was one explicitly authorized invocation. Any further production record
  remains separately approved.

---

## 9. Phase 62 — the review decision becomes a request plan

**Phase 61's review now feeds a concrete source/evidence request plan.** Phase 62 turned §4's eight
next evidence requests into ten prioritized requests, each mapped to Intake Taxonomy V0 categories
and to the downstream deliverable it supports, and each marked required / important / optional.
**Phase 62 creates no production record** — it opens no connection, invokes no writer, and reads no
environment file.

Inspecting the source/evidence writers settled the sequencing question §4 left open: the recommended
next path is the **source ingestion writer, not the evidence writer**. `evidence_references` asserts
`evidence_status`, `reliability`, and characterization that presuppose a registered source, so
**evidence and source collection precede analysis**, and evidence writing follows source ingestion
rather than preceding it.

**Phase 63 should create the first internal_test source ingestion record** through the unchanged
Phase 24 writer — if the inspected writer contract supports it, meaning a real internal_test artifact
exists at write time. Report drafting and capsule publication remain unauthorized. See
[`PHASE62_INTERNAL_TEST_SOURCE_EVIDENCE_REQUEST_PLAN.md`](PHASE62_INTERNAL_TEST_SOURCE_EVIDENCE_REQUEST_PLAN.md).
