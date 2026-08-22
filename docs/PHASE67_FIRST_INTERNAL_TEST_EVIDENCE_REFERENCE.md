# Phase 67 — The First Internal Test Evidence Reference (R2 Source Availability)

**Status:** production-sensitive phase — **one application record written**. Exactly **one
`evidence_references` row was created**, scoped to **item-master source availability and data
readiness only**, for the Phase 65 **R2 source ingestion record** approved by the Phase 66 review.
No source ingestion record, no Client record, no additional Engagement, no intake note, no review
record, no report, and no capsule record.
**Baseline:** `5c537d4` — Add Phase 66 R2 source ingestion review decision
**Alembic head:** unchanged at `014_engagement_classification` (14 migrations, 18 tables, 12
writers) — Phase 67 adds no migration, no model, no writer, and no allowlist pair
**Writer:** [`peak/db/evidence_writer.py`](../peak/db/evidence_writer.py) (Phase 21, unchanged)
**Operator utility:** [`tools/create_internal_test_r2_evidence_reference.py`](../tools/create_internal_test_r2_evidence_reference.py)
**Harness:** [`tests/validate_phase67_first_internal_test_evidence_reference.py`](../tests/validate_phase67_first_internal_test_evidence_reference.py)
(`make validate-phase67`, in `make validate`; offline, temp-SQLite only, contacts no production)

---

## 1. What was written

**Exactly one evidence_reference was created for the approved R2 source-ingestion chain.**

| Field | Value |
| --- | --- |
| stored record id | `evid_56437d9b9c764560` |
| target table / action | `evidence_references` / `create_draft` |
| authorization anchor | `internal_test_001` (engagement) |
| evidenced source | `ing_884c94df03c34908` — the Phase 65 R2 source ingestion record |
| supporting review | `rev_bf7f18a13d8f461c` — the Phase 66 `approve_internal` decision |
| `source_reference_id` | `pkt_internal_test_r2_sku_item_master_001` |
| `source_location` | `peak-record://source_ingestion_records/ing_884c94df03c34908` (logical) |
| `client_id` / `owner_id` | `99999` / `peak_internal_admin` |
| `authorization_scope` | `internal_peak_only` |
| `evidence_type` / `source_type` | `document` / `document` |
| `reliability` | `low` |
| `evidence_status` | `collected` (model default; the writer sets none) |
| `review_status` / `output_status` / `lifecycle_status` | `needs_review` / `draft` / `active` |
| `operational_area` / `inventory_process_area` | `back_office` / `inventory_control` |
| `sensitive_data_flag` | `false` |
| captured by / role | `peak_internal_admin` / `internal_admin` |
| `idempotency_key` | `phase67_internal_test_r2_evidence_reference_001` |

## 2. Why the existing evidence writer, and why no field was overloaded

`peak/db/evidence_writer.py` is the only writer for `evidence_references`, and its Phase 18 draft
has an honest slot for every part of this narrow claim:

- **`evidence_type` / `source_type` = `document`.** The R2 artifact is a field-level export
  *description*. `system_export` would have been the overload — it asserts an export of rows
  exists, and the artifact carries none. `document` is the schema-valid value
  (`schemas/evidence-reference.schema.json`) that states exactly what was collected.
- **`source_reference_id`** carries the registered packet reference — the field's exact declared
  meaning, and the same value the R2 source ingestion row itself carries.
- **`source_location`** carries a *pointer* to where this evidence originated, which is the field's
  declared meaning in `EvidenceSourceReference`. Here it is a logical in-Peak locator for the R2
  record, in the same `scheme://` style Phase 65 used for packet locations. **No filesystem path.**
- **`normalized_title` / `observed_condition` / `normalized_summary`** are free descriptive text and
  carry the claim, the supporting review record, and every limit in the row's own words.
- **`operational_area` = `back_office`, `inventory_process_area` = `inventory_control`** are both
  values the repository's own deterministic vocabularies derive for a system/item-master artifact
  (`peak/workers/evidence_normalization.py`). They are coarse areas, not location identifiers.
- **`confidence_level` = `low`** is the cautious end of the schema's `low|medium|high` reliability
  vocabulary, matching a source whose upstream map is itself unreviewed.

**No new writer was added, and no field is used against its declared meaning.**

### Three contract limits, stated rather than worked around

1. **No typed related-object column.** The Phase 9 schema has `related_object_ids`; the table does
   not. The supporting review record `rev_bf7f18a13d8f461c` is therefore named in the row's
   descriptive text, not in a join column. A future phase may want that column; Phase 67 did not add
   one.
2. **`evidence_status` is not caller-settable.** The writer sets none, so the row takes the model
   default `collected`. That is honest here — the artifact *was* collected — and the review gate is
   carried on the real `review_status` / `output_status` columns instead of on this field.
3. **`draft.reasons` is not persisted** by the evidence writer. The limits therefore live in
   `normalized_summary` and `observed_condition`, which *are* written to the row.

## 3. What this evidence reference claims

**Scope: item-master source availability and data readiness only.**

- The R2 SKU / item master source artifact is **available and registered** as source ingestion
  record `ing_884c94df03c34908` under packet `pkt_internal_test_r2_sku_item_master_001`.
- Its field-level structure is **sufficient to proceed to an item-master data-readiness review**:
  10 described fields, 6 required and 4 optional, each carrying an explicit interpretation note and
  a named risk; the join key to the inventory export is the item identifier.
- It is an **export description, not an export**, and carries no rows.

**Open questions recorded on the row:** unit-of-measure posture unconfirmed; item-status posture
unconfirmed; 6 duplicate and normalization risks remain review topics; whether the inventory export
draws item identifiers from the same identifier domain is unconfirmed and must be checked at
reconciliation time.

## 4. What it does not claim, and does not authorize

Recorded on the row, in its own text:

- **No inventory accuracy conclusion.** R2 describes an item master, not measured on-hand quantity.
  **No inventory accuracy conclusion was made in this phase.**
- **No reliance on R1 location claims.** R1's location dimension remains **provisional** pending
  **R9**, the location and bin naming model.
- **R8 is not treated as authoritative.** R8 remains `needs_review` / `draft` /
  `authoritative=false`, with an unconfirmed authority precedence rule, so no measure may yet be
  attributed to a system of record.
- **R3–R7 remain deferred** behind their unresolved R8 blockers.
- **No report drafting, no capsule candidacy, no client-facing output.**
- **No AgentNet publication.** The public resolver is live, and **publication remains
  unauthorized** — that the resolver is a real production target is why the gate stays shut rather
  than relaxed.

`evidence_references` has **no `authoritative` column**, so that claim is structurally impossible.
The writer additionally *refuses* any draft asserting `authoritative`, `client_facing_approved`, or
`capsule_candidate_ready`, and server-stamps `review_status='needs_review'` and
`output_status='draft'` itself rather than trusting the caller.

## 5. The artifact body was never read, printed, or stored

The Phase 67 operator **opens no file and computes no hash** — it reads no artifact at all. The R2
artifact body remains outside the repository, uncommitted, unprinted, and absent from the database.
The stored text carries structural counts, posture flags, named gaps, and record ids only: **no
artifact body text, no field values, no item or SKU values, no quantities, and no location
identifiers**.

## 6. What Phase 67 did not do

- **No source ingestion record**, no Client, no additional Engagement, no intake note, no review
  record, no report draft, no review packet, no capsule candidate, no client-facing output.
- **No AgentNet publication.**
- **No migration, no migration 015, no model, no writer, no allowlist pair.**
- **No `UPDATE`, `DELETE`, manual SQL, cleanup path, app scan, or app row count** beyond the
  writer's own stored-engagement load and idempotency lookup.

## 7. Idempotency and the no-overwrite rule

The record carries its own Phase 67 idempotency key on the
owner / client / engagement / key boundary. An exact replay returns the existing row unmodified; a
**changed payload fingerprint under the same key is refused as an `idempotency_conflict`** — never
an overwrite. The operator has no `UPDATE`, `DELETE`, or cleanup path.

## 8. Next steps, still gated

An item-master **data-readiness review** of R2 is the natural next step this evidence reference
supports. It remains a **separately approved phase**, as do R9 collection (which unblocks R1's
location dimension), R8 review, R3–R7, report drafting, capsule candidacy, and AgentNet resolver
publication.
