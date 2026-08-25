# Phase 70 — The R9 Source Ingestion Review Decision

**Status:** production-sensitive phase — **one application record written**. Exactly **one
`review_records` row was created**, recording the internal review decision on the Phase 69 **R9
source ingestion record** (the location/bin naming model). No evidence reference, no source
ingestion record, no Client record, no additional Engagement, no intake note, no report, and no
capsule record.
**Baseline:** `608bf4e` — Add Phase 69 R9 location bin model source ingestion
**Alembic head:** unchanged at `014_engagement_classification` (14 migrations, 18 tables, 12
writers) — Phase 70 adds no migration, no model, no writer, and no allowlist pair
**Writer:** [`peak/db/review_writer.py`](../peak/db/review_writer.py) (Phase 22, unchanged)
**Operator utility:** [`tools/create_internal_test_r9_source_review_decision.py`](../tools/create_internal_test_r9_source_review_decision.py)
**Harness:** [`tests/validate_phase70_r9_source_ingestion_review_decision.py`](../tests/validate_phase70_r9_source_ingestion_review_decision.py)
(`make validate-phase70`, in `make validate`; offline, temp-SQLite only, contacts no production)

---

## 1. What was written

**One `review_records` row was created for the R9 source ingestion record.**

| Field | Value |
| --- | --- |
| stored record id | `rev_3ecc0891f4fe48ce` |
| target table / action | `review_records` / `create_review_record` |
| authorization anchor | `internal_test_001` (engagement) |
| reviewed target (`target_id`) | `ing_64b2e2648ac1402b` — the Phase 69 R9 source ingestion record |
| `subject_record_type` | `source_ingestion_record` |
| `source_reference_id` | `pkt_internal_test_r9_location_bin_model_001` |
| `client_id` / `owner_id` | `99999` / `peak_internal_admin` |
| `authorization_scope` | `internal_peak_only` |
| `decision` | `approve_internal` |
| `authoritative` | `false` |
| `review_status` (new) | `approved_internal` |
| `output_status` / `lifecycle_status` | `draft` / `active` |
| `client_facing_approved` / `capsule_candidate_ready` | `false` / `false` |
| reviewer / reviewer role | `peak_internal_admin` / `internal_admin` |
| `idempotency_key` | `phase70_internal_test_r9_source_ingestion_review_001` |

## 2. What the decision approves

**R9 is internally approved only for future evidence work about R1 location-dimension readiness.**
That is the whole of the grant. `approve_internal` in this writer's vocabulary means internal
reliance only and never client-facing approval, so the scope is narrow by construction as well as by
the findings recorded on the row.

**R9 remains non-authoritative.** `authoritative` was left `false` deliberately: R9 answers none of
its own questions, its ownership is undetermined, and its upstream map (R8) is itself unreviewed.
The writer would have permitted `true` for an `approve_internal` decision; this review declines it.

## 3. Why `review_records`, and why no field was overloaded

The Phase 22 review writer keeps apart the two things this review needs kept apart: the
**authorization anchor** (`request.subject`, which the writer *requires* to be the `engagement`) and
the **reviewed target** (`draft.subject_record_id` / `draft.subject_record_type`, stored as
`target_id`). `subject_record_type='source_ingestion_record'` is the same honest value **Phase 66**
used when reviewing the R2 source ingestion record — the reviewed target here is the same class of
record. `draft.source_reference_id` carries the reviewed packet reference, and `draft.reasons` is a
free findings list the writer persists into `details_json`, so the limits are stored **as findings**
rather than squeezed into a field meant for something else.

## 4. Review findings, sanitized

The reviewed artifact's hash still matches the `packet_hash` registered in Phase 69 — **the
registration is intact and the artifact is unchanged**.

R9 is a concept/field-level location model in 17 top-level sections: 6 hierarchy levels from site
down to bin, 5 naming fields plus 3 normalization questions, 3 location type/status fields, 4
inventory availability treatment concepts including the status-bucket versus physical-position
distinction, 6 virtual/non-physical concepts (virtual/logical, staging, hold, damaged,
quarantine/inspection, unavailable inventory), 4 candidate ownership postures (ERP, WMS, manual,
unknown) each stated as an open question, and 8 explicit non-validation statements carried on the
artifact itself. Every "contains instance data" flag on the artifact is false.

**The central limit: R9 is a question set, not an answered model.** All 6 hierarchy levels and all 3
type/status fields are marked presence-unknown, and roughly 53 structural questions are posed
without any being answered. That is appropriate for a collected source and is not a defect — but it
means R9 **defines what must be measured** rather than reporting what is true. It therefore cannot
by itself lift R1's provisional location marking; only measured answers could. R9 likewise supplies
no basis for choosing among the four candidate ownership postures, so location attribution to a
system of record remains unavailable.

**No artifact body was copied.** The findings are structural counts, posture flags, and named gaps
— no artifact text, field values, item or SKU values, quantities, or location, bin, aisle, rack,
warehouse, or site identifiers. The operator itself opens no file at all: it reviews a *registered
record*, not an artifact.

## 5. What this decision does not do

- **No `evidence_reference` was created.** A narrow R9 evidence reference remains a separately
  approved phase.
- **R1's location dimension remains provisional.** This decision does not lift that marking.
- **R9 does not validate inventory quantities.** It contains no instance data and can support no
  count, rate, or total. No inventory accuracy conclusion exists.
- **R9 does not resolve R8 authority precedence.** R8 stays `needs_review` / `draft` /
  `authoritative=false` with its precedence rule unconfirmed, so no measure may yet be attributed
  to a system of record.
- **R9 does not resolve R5 WMS scope uncertainty.** R9 records the shared dependency but is not
  evidence about WMS scope.
- **R3–R7 remain deferred** behind their unresolved blockers.
- **No report, no capsule, no client-facing output, and no AgentNet publication** was created or
  authorized. `ReviewRecordDraft` has no `publication_allowed` field to set false — the prohibition
  is structural and stronger: the writer refuses `publish_capsule` at the vocabulary level and
  forces `client_facing_approved=false` and `capsule_candidate_ready=false`.
- **The reviewed R9 record was not modified.** A review records a decision *about* a target; the
  review writer has no `UPDATE` path, so R9's own row still reads `needs_review` / `draft`.

## 6. Idempotency and the no-overwrite rule

The record carries its own Phase 70 idempotency key on the owner / client / engagement / key
boundary. An exact replay returns the existing row unmodified; a **changed payload fingerprint under
the same key is refused as an `idempotency_conflict`** — never an overwrite. The operator has no
`UPDATE`, `DELETE`, or cleanup path.

## 7. Posture after Phase 70

- **R9** — reviewed, `approve_internal`, **non-authoritative**, approved only for future evidence
  work about R1 location-dimension readiness.
- **R1** — location dimension **remains provisional**.
- **R2** — unchanged: approved only for future internal assessment use about item-master source
  availability and data readiness.
- **R8** — unchanged: provisional, `needs_review` / `draft` / `authoritative=false`, precedence
  unconfirmed.
- **R5** — WMS scope **remains unresolved**.
- **R3–R7** — remain **deferred**.
- **No inventory accuracy conclusion exists.** Report drafting, capsule publication, and
  client-facing output remain unauthorized. The AgentNet public resolver is live; **publication
  remains gated and unauthorized**.
- `subject_record_type` vocabulary cleanup remains deferred.

## 8. Next steps, still gated

**Phase 71 likely creates a narrow R9 `evidence_reference`** scoped to location-model availability
and readiness — or, alternatively, begins a **combined R1/R9 evidence-readiness planning step**,
which may be the better fit given that R9's value is the question set it defines rather than any
answer it supplies. Either path is a **separately approved phase**, as are R8 review, R3–R7
collection, report drafting, capsule publication, and AgentNet resolver publication.

## 9. What Phase 71 planned from this decision

**Phase 71 took the alternative §8 named** — a **combined R1/R9 evidence-readiness planning step**
rather than a narrow R9 evidence reference — and is **planning-only**: no production access, no
production write, and **no `evidence_reference`, `review_record`, or `source_ingestion_record`
created**. **No production record of any kind was
created.**

It carried this decision's central finding forward as its own premise: **R9 is a question set, not
an answered model**, so R1 cannot yet support a location-dimension evidence reference. Phase 71 made
that gap concrete — R1 carries one required location identifier plus one *optional* level marker,
both marked provisional, against R9's six-level hierarchy — and listed **15 required measured
answers** as the gate before any R1/R9 evidence reference, including both success and failure
thresholds fixed in advance.

**The narrow R9 evidence reference is deferred, not foreclosed.** It would mostly establish that
Peak holds a reviewed question set, which does not materially advance R1 location readiness; it
remains available if later wanted for audit completeness.

**Nothing this decision established was changed.** **R1 remains provisional**, **R9 remains
non-authoritative**, R8 authority precedence and R5 WMS scope remain unresolved, R3–R7 remain
deferred, and no inventory accuracy conclusion, report, capsule, client-facing output, or AgentNet
resolver publication was created or authorized. The recommended next production step is **R10 — a
measured location model answer set source ingestion** (Phase 72), a **separately approved phase**.
See [`PHASE71_R1_R9_EVIDENCE_READINESS_PLAN.md`](PHASE71_R1_R9_EVIDENCE_READINESS_PLAN.md).

## 10. What Phase 72 collected against this decision

**Phase 72 collected R10**, the measured location model answer set, as one
`source_ingestion_records` row (`ing_b26d137a0a334ee9`) through the unchanged Phase 24 writer under this
same `internal_test_001` / `internal_peak_only` anchor.

R10 is the direct consequence of this decision's central finding. **This review recorded that R9 is
a question set, not an answered model**; R10 is the answer set for those questions, covering all 15
Phase 71 checklist items with explicit answer states. **It includes negative and unknown answers** —
11 of 15 resolve to a negative, unknown, or blocked state — and its headline finding is that **R1's
location dimension is not currently readable**.

**Nothing this decision established was changed.** R9's own row and this review record are untouched
— the source ingestion writer has no `UPDATE` path. **R1 remains provisional**, and this decision's
scope (R9 approved only for future evidence work about R1 location-dimension readiness) is exactly
what R10 serves. **No evidence reference, no review record**, no report, no capsule, no
client-facing output, and no AgentNet publication was created. **R10 itself remains `needs_review` /
`draft` / `authoritative=false`** and must be reviewed before evidence use; **R8 precedence and R5
WMS scope remain unresolved**, recorded on R10 as `blocked_by_r8` and `blocked_by_r5`. See
[`PHASE72_R10_LOCATION_MODEL_ANSWER_SET_SOURCE_INGESTION.md`](PHASE72_R10_LOCATION_MODEL_ANSWER_SET_SOURCE_INGESTION.md).
