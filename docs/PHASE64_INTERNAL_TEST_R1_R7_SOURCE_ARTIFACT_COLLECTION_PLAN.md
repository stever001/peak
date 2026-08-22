# Phase 64 — The Internal Test R1–R7 Source Artifact Collection Plan

**Status:** **planning-only — no production write.** Phase 64 contacts no database, invokes no
writer, reads no environment file, and creates **no production record**. It specifies the R1–R7
internal_test source artifacts that follow the Phase 63 R8 map, and names what Phase 65 should
register first.
**Baseline:** `2569f38` — Add Phase 63 first internal test source ingestion record
**Alembic head:** unchanged at `014_engagement_classification` (14 migrations, 18 tables, 12
writers) — Phase 64 adds no migration, no model, no writer, no allowlist pair, and no operator
utility
**Harness:** [`tests/validate_phase64_internal_test_r1_r7_source_artifact_collection_plan.py`](../tests/validate_phase64_internal_test_r1_r7_source_artifact_collection_plan.py)
(`make validate-phase64`, in `make validate`; offline, contacts no production)

---

## 1. The phase decision

- **Phase 64 is planning-only. No production record was created**, and no artifact body was created
  or committed.
- **R1–R7 are internal_test artifacts only.** No real client data, in any of them, ever.
- **Source ingestion records persist metadata only** — packet reference id, schema name and version,
  source type, a **logical** location reference, and a hash. Never a payload, an export row, or a
  filesystem path.
- **Artifact bodies live outside the repository**, under the approved internal-test artifact
  directory, exactly as the Phase 63 R8 artifact does.
- **`evidence_references` come after source ingestion**, never before.
- **Report drafting and capsule publication are not authorized** by this plan.
- **The AgentNet public resolver is live** — a real production publication target, not a
  hypothetical future dependency. That makes the publication gate matter more, not less:
  **publication remains gated and unauthorized for this phase**, and nothing here may be published.
- **R8 remains `needs_review` / `draft` / `authoritative=false`.** Nothing downstream may treat the
  map as settled.

## 2. Chain state entering Phase 64

| Record | Id | Phase |
| --- | --- | --- |
| Engagement anchor | `internal_test_001` (client `99999`, owner `peak_internal_admin`, scope `internal_peak_only`) | 59 |
| Intake note | `intn_b8b86b8c196c4595` | 60 |
| Review decision | `rev_b82ff6f00790418f` | 61 |
| R8 source ingestion | `ing_4fb70519cbf84401` — `internal-test-artifact://phase63/r8-system-of-record-data-export-map-v1` | 63 |
| R1–R7 source ingestion | **none** | — |
| Evidence reference | **none** | — |
| Report / capsule / publication | **none** | — |

## 3. What the R8 map actually says about R1–R7

The Phase 63 map does not treat the seven requests as equally available. Read as a work-list:

| Request | Availability per R8 | Blockers recorded in R8 |
| --- | --- | --- |
| R1 | expected | location/bin model unconfirmed |
| **R2** | **expected** | **none** |
| R3 | uncertain | reason-code discipline unknown; retention window unknown |
| R4 | uncertain | count-programme existence unconfirmed |
| R5 | uncertain | WMS scope unconfirmed |
| R6 | uncertain | exception definition undocumented |
| R7 | partial | documented-vs-practiced gap unassessed |

**R2 is the only request the map shows as unblocked.** R1 is *expected* but blocked on the
unconfirmed location model — and per-location quantity is precisely what R1 exists to supply.

### Does anything require R8 to be *reviewed* first?

Two things must be kept apart:

- **Collection does not require R8 review.** Registering an artifact's metadata asserts only that
  the artifact exists under this engagement. That claim does not depend on the map being settled,
  so R1–R7 may be collected and registered while R8 stays `needs_review`.
- **Attribution does.** R8's `authority_precedence_rule` is recorded as *provisional and
  unconfirmed*. Until it is confirmed, no measured claim may be attributed to a system of record —
  which is exactly what an `evidence_reference` does when it sets `reliability` and
  `evidence_status`. **R8 review is a precondition for evidence, not for collection.**

That split is why Phase 65 is a source-ingestion phase and not an evidence phase.

## 4. Shared conventions for every R1–R7 artifact

| Convention | Value |
| --- | --- |
| external directory | `~/.peak/peak-internal-test-artifacts/phase65/` (outside the repository) |
| logical location reference | `internal-test-artifact://phase65/<slug>-v1` |
| `packet_schema_name` / `version` | `engagement_packet` / `v0` (as R8) |
| anchor | engagement `internal_test_001`, scope `internal_peak_only` |
| posture on registration | `draft` / `needs_review` / `active`, `authoritative=false`, `client_facing_approved=false`, `capsule_candidate_ready=false` |

**Hash requirement, applying to all seven.** The operator computes a **SHA-256 over the artifact's
exact bytes**, read in binary, outside the repository. The digest goes into `packet_hash`; the bytes
are never decoded, printed, logged, or placed on the draft. Recomputing the hash on the unchanged
file must reproduce it, and a **changed hash under the same idempotency key must be refused as an
`idempotency_conflict`** — never an overwrite. An artifact that is regenerated rather than corrected
gets a new version slug (`-v2`), not a silent rewrite of `-v1`.

**What must stay out of the repository and out of DB payload fields, for all seven.** Artifact
bodies, export rows, item or SKU values, quantities, location or bin identifiers, document text,
screenshots, credentials, connection strings, and filesystem paths. The writer independently refuses
any draft attribute named `packet_payload`, `raw_packet_content`, `raw_content`, `payload`, or
containing a secret term, so the rule is enforced on both sides.

---

## 5. The seven artifact specifications

### R1 — Current inventory export by SKU and location

- **Purpose:** establish the measured on-hand baseline per item and per location.
- **Dependency on R8:** R8 names the ERP as the provisional source and flags the **location model as
  unconfirmed**. The SKU dimension is collectable now; the **location dimension is provisional** until
  the location/bin naming model lands.
- **Minimum expected fields:** item identifier, location identifier, quantity on hand, unit of
  measure, as-of timestamp, source system reference.
- **Artifact type:** structured export.
- **External filename:** `r1_current_inventory_sku_location_v1.json`
- **Logical location reference:** `internal-test-artifact://phase65/r1-current-inventory-sku-location-v1`
- **`packet_reference_id`:** `pkt_internal_test_r1_current_inventory_001`
- **`packet_schema_name` / version:** `engagement_packet` / `v0`
- **`packet_source_type`:** `internal_test_export`
- **Hash requirement:** SHA-256 over exact bytes; conflict on change, never overwrite.
- **Taxonomy categories:** 03 item/SKU master · 04 location structure · 07 stockouts and overstocks ·
  09 data exports and reporting
- **Downstream deliverable:** inventory accuracy assessment; the quantitative baseline for
  working-capital and service-level findings.
- **Future `evidence_reference` implications:** any evidence derived from R1 must carry a **degraded
  reliability for location-attributed claims** until the location model is confirmed. SKU-level
  claims are not similarly limited.
- **Internal_test-only safety:** internal_test engagement only; **must contain no real client data**;
  **must not be committed to the repository**.

### R2 — SKU / item master export

- **Purpose:** quantify identifier discipline — duplicate rate, master size, units of measure,
  attribute completeness, and item-master ownership.
- **Dependency on R8:** R8 names the ERP as the provisional item-master source and records **no
  blockers**. This is the one request the map shows as fully available.
- **Minimum expected fields:** item identifier, description, unit of measure, status or lifecycle
  flag, attribute-completeness indicators, owning system reference.
- **Artifact type:** structured export.
- **External filename:** `r2_item_master_full_v1.json`
- **Logical location reference:** `internal-test-artifact://phase65/r2-item-master-full-v1`
- **`packet_reference_id`:** `pkt_internal_test_r2_item_master_001`
- **`packet_schema_name` / version:** `engagement_packet` / `v0`
- **`packet_source_type`:** `internal_test_export`
- **Hash requirement:** SHA-256 over exact bytes; conflict on change, never overwrite.
- **Taxonomy categories:** 03 item/SKU master · 09 data exports and reporting · 12 AI/AgentNet
  readiness
- **Downstream deliverable:** data-readiness finding; closes the Phase 61 gap that duplicate rate and
  master size are unquantified.
- **Future `evidence_reference` implications:** R2 is the **interpretive key** for R1 — without it,
  R1's item identifiers cannot be assessed for duplication or unit consistency, so evidence derived
  from R1 alone would overstate its own reliability.
- **Internal_test-only safety:** internal_test engagement only; **must contain no real client data**;
  **must not be committed to the repository**.

### R3 — Inventory adjustment history with reason codes

- **Purpose:** measure adjustment volume, reason-code discipline, adjustment authority, and shrink
  visibility.
- **Dependency on R8:** R8 marks this **uncertain**, blocked on unknown reason-code discipline and an
  unknown retention window. Both must be answered before the export can be scoped, and R8's
  provisional authority rule decides which system's history counts.
- **Minimum expected fields:** adjustment identifier, item identifier, location identifier, quantity
  delta, reason code, reason-code vocabulary reference, approver or authority reference, timestamp.
- **Artifact type:** structured export.
- **External filename:** `r3_inventory_adjustment_history_v1.json`
- **Logical location reference:** `internal-test-artifact://phase65/r3-inventory-adjustment-history-v1`
- **`packet_reference_id`:** `pkt_internal_test_r3_adjustment_history_001`
- **`packet_schema_name` / version:** `engagement_packet` / `v0`
- **`packet_source_type`:** `internal_test_export`
- **Hash requirement:** SHA-256 over exact bytes; conflict on change, never overwrite.
- **Taxonomy categories:** 06 counts, adjustments, shrink · 08 systems of record · 10 SOPs,
  approvals, exceptions
- **Downstream deliverable:** control-risk and accuracy assessment — the fastest read on whether
  recorded inventory can be trusted.
- **Future `evidence_reference` implications:** reliability depends on whether reason codes are
  **coded values or free text**. If free text, evidence from R3 supports a qualitative finding only,
  and must say so rather than implying a measured rate.
- **Internal_test-only safety:** internal_test engagement only; **must contain no real client data**;
  **must not be committed to the repository**.

### R4 — Cycle count or physical count results

- **Purpose:** measure count cadence and coverage, and the variance between counted and recorded
  inventory.
- **Dependency on R8:** R8 marks this **uncertain**, blocked on whether a count programme exists at
  all. If none does, the honest outcome is to record its absence — which is itself a finding — not to
  synthesise a count.
- **Minimum expected fields:** count event identifier, count date, scope or coverage descriptor,
  item identifier, location identifier, counted quantity, recorded quantity, variance, recount flag.
- **Artifact type:** structured export.
- **External filename:** `r4_cycle_count_variance_results_v1.json`
- **Logical location reference:** `internal-test-artifact://phase65/r4-cycle-count-variance-results-v1`
- **`packet_reference_id`:** `pkt_internal_test_r4_count_results_001`
- **`packet_schema_name` / version:** `engagement_packet` / `v0`
- **`packet_source_type`:** `internal_test_export`
- **Hash requirement:** SHA-256 over exact bytes; conflict on change, never overwrite.
- **Taxonomy categories:** 06 counts, adjustments, shrink · 04 location structure · 14 success
  metrics and urgency
- **Downstream deliverable:** inventory accuracy assessment; supplies the baseline metric a success
  measure can be stated against.
- **Future `evidence_reference` implications:** variance is the most directly capsule-shaped
  measurement in the set, which is exactly why its reliability must not be asserted before R8's
  precedence rule is confirmed.
- **Internal_test-only safety:** internal_test engagement only; **must contain no real client data**;
  **must not be committed to the repository**.

### R5 — Receiving and putaway records

- **Purpose:** observe the actual inbound flow and where it deviates from the documented flow.
- **Dependency on R8:** R8 marks this **uncertain**, blocked on unconfirmed WMS scope — the same
  unconfirmed system that limits R1's location dimension.
- **Minimum expected fields:** receipt identifier, item identifier, quantity received, receiving
  timestamp, putaway location identifier, putaway timestamp, handler or role reference, exception
  flag.
- **Artifact type:** structured export.
- **External filename:** `r5_receiving_putaway_transactions_v1.json`
- **Logical location reference:** `internal-test-artifact://phase65/r5-receiving-putaway-transactions-v1`
- **`packet_reference_id`:** `pkt_internal_test_r5_receiving_putaway_001`
- **`packet_schema_name` / version:** `engagement_packet` / `v0`
- **`packet_source_type`:** `internal_test_export`
- **Hash requirement:** SHA-256 over exact bytes; conflict on change, never overwrite.
- **Taxonomy categories:** 05 receiving through shipping · 04 location structure · 10 SOPs,
  approvals, exceptions
- **Downstream deliverable:** workflow and process evaluation — where most improvement-plan items
  originate.
- **Future `evidence_reference` implications:** the transactional records are machine-readable, but
  *deviation from documented flow* is a human judgement and must be evidenced against R7, not
  asserted from R5 alone.
- **Internal_test-only safety:** internal_test engagement only; **must contain no real client data**;
  **must not be committed to the repository**.

### R6 — Stockout, backorder, or fulfillment exception data

- **Purpose:** quantify service-level failures and connect operational symptoms to cost.
- **Dependency on R8:** R8 marks this **uncertain**, blocked on an undocumented exception definition.
  A rate computed over an undefined denominator is not a measurement, so the definition must be
  captured with the export.
- **Minimum expected fields:** exception identifier, exception type, item identifier, requested
  quantity, fulfilled quantity, shortfall, event timestamp, resolution state, exception-definition
  reference.
- **Artifact type:** structured export.
- **External filename:** `r6_stockout_backorder_exceptions_v1.json`
- **Logical location reference:** `internal-test-artifact://phase65/r6-stockout-backorder-exceptions-v1`
- **`packet_reference_id`:** `pkt_internal_test_r6_fulfillment_exceptions_001`
- **`packet_schema_name` / version:** `engagement_packet` / `v0`
- **`packet_source_type`:** `internal_test_export`
- **Hash requirement:** SHA-256 over exact bytes; conflict on change, never overwrite.
- **Taxonomy categories:** 07 stockouts and overstocks · 02 current pain points · 14 success metrics
  and urgency
- **Downstream deliverable:** service-level and working-capital findings.
- **Future `evidence_reference` implications:** any exception *rate* derived from R6 must cite the
  captured exception definition; without it the evidence supports a count, not a rate.
- **Internal_test-only safety:** internal_test engagement only; **must contain no real client data**;
  **must not be committed to the repository**.

### R7 — SOP and process documentation

- **Purpose:** establish the documented procedure so it can be compared against the practiced one.
- **Dependency on R8:** R8 marks this **partial**, sourced from the supplemental spreadsheet system
  rather than the ERP, and blocked on the documented-versus-practiced gap being unassessed.
- **Minimum expected document sections:** process scope, step sequence, roles and approvals,
  exception and escalation handling, known workarounds, document owner, version and effective date.
- **Artifact type:** process document (semi-structured; a manifest of document sections and
  references, not the document text).
- **External filename:** `r7_sop_process_documentation_v1.json`
- **Logical location reference:** `internal-test-artifact://phase65/r7-sop-process-documentation-v1`
- **`packet_reference_id`:** `pkt_internal_test_r7_sop_documentation_001`
- **`packet_schema_name` / version:** `engagement_packet` / `v0`
- **`packet_source_type`:** `internal_test_document`
- **Hash requirement:** SHA-256 over exact bytes; conflict on change, never overwrite.
- **Taxonomy categories:** 10 SOPs, approvals, exceptions · 05 receiving through shipping ·
  11 evidence availability
- **Downstream deliverable:** process maturity and governance findings — the gap between documented
  and practiced is itself a finding.
- **Future `evidence_reference` implications:** R7 is the **comparison baseline** for R5. Evidence
  asserting a process gap must reference both; neither alone supports the claim.
- **Internal_test-only safety:** internal_test engagement only; **must contain no real client data**;
  **must not be committed to the repository**.

---

## 6. Recommended Phase 65 execution order

**Recommendation: register R1 and R2 together as a small batch — R2 first within the batch, then
R1 — and no further requests in Phase 65.**

Why this rather than R1 alone:

1. **R2 is the only unblocked request in the R8 map.** R1 is blocked on the unconfirmed location
   model. Registering R1 alone would lead with the request whose primary dimension is provisional.
2. **R1 is not interpretable without R2.** R1's item identifiers cannot be assessed for duplication
   or unit-of-measure consistency without the item master. Inventory records only become meaningful
   as a pair, which is exactly the batch condition the sprint brief names.
3. **R2 first *within* the batch** so the item master is registered before the inventory export that
   depends on it, and so a partial Phase 65 still lands the unblocked artifact.
4. **R1 registers with its location dimension explicitly provisional.** That limitation is recorded
   now, in the provenance notes, rather than discovered later at evidence time.

**R3–R7 are deliberately not in Phase 65.** Each carries an unresolved R8 blocker — reason-code
discipline, count-programme existence, WMS scope, exception definition, and the documented-versus-
practiced gap. Registering them before those are answered would produce artifacts nobody can size or
scope. **R9, the location/bin naming model from the Phase 62 plan, is the unblocker for R1's location
dimension and for R5**, and remains the natural follow-on.

**Phase 65 creates source ingestion records only.** Two artifacts, two
`source_ingestion_records` rows through the unchanged Phase 24 writer, metadata only. **No
`evidence_reference`**, no report, no capsule, and no AgentNet publication.

## 7. What Phase 64 did not do

- **No source ingestion record**, and no artifact body created or committed.
- **No evidence reference**, no report draft, no review packet, no capsule candidate.
- **No AgentNet publication.** The resolver is live and reachable; that is precisely why the gate
  stays shut until publication is separately authorized.
- **No Client, Engagement, intake, or review record.**
- **No database connection, no SQL, no writer invocation, no environment read.**
- **No migration, no migration 015, no model, no writer, no allowlist pair, no operator utility.**
- **No example rows.** Field names and document section names appear throughout; **no SKU values, no
  quantities, no location identifiers, and no sample export rows** do.
