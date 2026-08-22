# Phase 66 — The Internal Test Source Ingestion Review Decision (R2)

**Status:** production-sensitive phase — **one application record written**. Exactly **one
`review_records` row was created**, recording the internal review decision on the Phase 65 **R2
source ingestion record**. No evidence reference, no source ingestion record, no Client record, no
additional Engagement, no intake note, no report, and no capsule record.
**Baseline:** `c0f3bd7` — Add Phase 65 R1 R2 internal test source ingestion
**Alembic head:** unchanged at `014_engagement_classification` (14 migrations, 18 tables, 12
writers) — Phase 66 adds no migration, no model, no writer, and no allowlist pair
**Writer:** [`peak/db/review_writer.py`](../peak/db/review_writer.py) (Phase 22, unchanged)
**Operator utility:** [`tools/create_internal_test_r2_source_review_decision.py`](../tools/create_internal_test_r2_source_review_decision.py)
**Harness:** [`tests/validate_phase66_internal_test_source_ingestion_review_decision.py`](../tests/validate_phase66_internal_test_source_ingestion_review_decision.py)
(`make validate-phase66`, in `make validate`; offline, temp-SQLite only, contacts no production)

---

## 1. What was written

**One internal review record was created for the R2 source ingestion record.**

| Field | Value |
| --- | --- |
| stored record id | `rev_bf7f18a13d8f461c` |
| target table / action | `review_records` / `create_review_record` |
| authorization anchor | `internal_test_001` (engagement) |
| reviewed target (`target_id`) | `ing_884c94df03c34908` — the Phase 65 R2 source ingestion record |
| `subject_record_type` | `source_ingestion_record` |
| `source_reference_id` | `pkt_internal_test_r2_sku_item_master_001` |
| `client_id` / `owner_id` | `99999` / `peak_internal_admin` |
| `authorization_scope` | `internal_peak_only` |
| `decision` | `approve_internal` |
| `authoritative` | `false` |
| `review_status` (new) | `approved_internal` |
| `output_status` / `lifecycle_status` | `draft` / `active` |
| `client_facing_approved` / `capsule_candidate_ready` | `false` / `false` |
| reviewer / reviewer role | `peak_internal_admin` / `internal_admin` |
| `idempotency_key` | `phase66_internal_test_r2_source_ingestion_review_001` |

## 2. Why `review_records`, and why no field was overloaded

The Phase 22 review writer keeps apart the two things this review needs kept apart:

- the **authorization anchor** — `request.subject`, which the writer *requires* to be the
  `engagement`; and
- the **reviewed target** — `draft.subject_record_id` / `draft.subject_record_type`, stored as
  `target_id` and documented in the model as the column that "disambiguates the reviewed target".

So `source_ingestion_record` is an honest value in `subject_record_type`, not a reuse of a field
meant for something else, and `draft.source_reference_id` is the honest home for the reviewed packet
reference. **Phase 61 used this same shape** with `subject_record_type='intake_note'`.

The alternative, `internal_reviewer_decision_records`, is shaped around a **review bundle** and has
no single reviewed-target field, so representing one source ingestion record there would have meant
misusing a bundle reference. `review_records` is the narrower honest fit, and **no new writer was
added**.

`approve_internal` means **internal reliance only and never client-facing approval**. The writer
refuses `client_facing_approve`, `verify_financial_impact`, and `publish_capsule` at the vocabulary
level, and forces `client_facing_approved=false` and `capsule_candidate_ready=false`.

**`authoritative` was left `false`** deliberately. The writer would permit `true` for
`approve_internal`, but this decision reviews a source registration whose upstream map (R8) is
itself unreviewed, so nothing downstream should treat it as settled.

## 3. What the review found

Findings were recorded as concise sanitized entries in the row's `reasons` list — structural counts,
posture flags, and named gaps. **No artifact body text, no field values, no item or SKU values, no
quantities, and no location identifiers were stored.**

- **Registration integrity.** The reviewed artifact's SHA-256 matches the `packet_hash` registered
  in Phase 65 — the artifact registered then is unchanged.
- **Structure.** The artifact describes 10 item-master fields (6 required, 4 optional); every field
  carries an explicit interpretation note and a named risk. The join key to R1 is the item
  identifier, and 5 fields are required to interpret R1.
- **Readiness.** R8 records no blocker for R2 — it is the first unblocked source artifact. The
  artifact is a field-level export *description*, not an export; it carries no rows.
- **Gaps.** Unit-of-measure posture unconfirmed; item-status posture unconfirmed; 6
  duplicate/normalization risks recorded; and whether R1 draws item identifiers from the same
  identifier domain is unconfirmed and must be checked at reconciliation time.

## 4. What this decision authorizes — and what it does not

**Authorized:** R2 is sufficient to proceed to a **future `evidence_reference` about item-master
source availability and data readiness**, as a separately approved phase.

**Not authorized, and recorded as such on the row:**

- **No inventory accuracy conclusion.** R2 describes an item master, not measured on-hand quantity.
- **R1 remains provisional.** Its location dimension depends on an unconfirmed location/bin model.
- **R8 remains provisional** — `needs_review` / `draft` / `authoritative=false`, with an unconfirmed
  authority precedence rule, so no measure may yet be attributed to a system of record.
- **R3–R7 remain deferred** behind their unresolved R8 blockers.
- **No report drafting, no capsule candidacy, no client-facing output.**
- **No AgentNet resolver publication.** The public resolver is live, and **publication remains
  unauthorized** — that the resolver is a real production target is why the gate stays shut rather
  than relaxed.

`ReviewRecordDraft` has no `publication_allowed` or `execution_allowed` field to set false. The
prohibition is structural instead, and stronger: the writer refuses `publish_capsule` at the
vocabulary level and forces the client-facing and capsule flags to false. The limits are
additionally written into the row's own findings text.

## 5. The artifact body was never read

The Phase 66 operator **opens no file and computes no hash** — it reads no artifact at all. The R2
artifact body remains outside the repository, uncommitted, unprinted, and absent from the database.
The hash comparison recorded in the findings was made against the `packet_hash` already registered
in Phase 65.

## 6. What Phase 66 did not do

- **No `evidence_reference`** — that remains the next separately approved step, scoped narrowly.
- **No source ingestion record**, no Client, no additional Engagement, no intake note, no report
  draft, no review packet, no capsule candidate, no client-facing output.
- **No AgentNet publication.**
- **No migration, no migration 015, no model, no writer, no allowlist pair.**
- **No `UPDATE`, `DELETE`, manual SQL, cleanup path, app scan, or app row count** beyond the
  writer's own stored-engagement load and idempotency lookup.

## 7. Idempotency and the no-overwrite rule

The record carries its own Phase 66 idempotency key. An exact replay returns the existing row
unmodified; a **changed payload fingerprint under the same key is refused as an
`idempotency_conflict`** — never an overwrite. The operator has no `UPDATE`, `DELETE`, or cleanup
path.
