# Phase 65 — The R2 and R1 Internal Test Source Ingestion Records

**Status:** production-sensitive phase — **two application records written**. Exactly **two
`source_ingestion_records` rows were created** in production: **R2 first** (the SKU/item master
export), then **R1** (the current inventory export by SKU and location). No Client record, no
additional Engagement, no intake note, no review record, **no evidence reference**, no report, and
no capsule record.
**Baseline:** `65e8fb8` — Add Phase 64 internal test R1-R7 source artifact plan
**Alembic head:** unchanged at `014_engagement_classification` (14 migrations, 18 tables, 12
writers) — Phase 65 adds no migration, no model, no writer, and no allowlist pair
**Writer:** [`peak/db/source_ingestion_writer.py`](../peak/db/source_ingestion_writer.py)
(Phase 24, unchanged)
**Operator utility:** [`tools/create_internal_test_r1_r2_source_ingestion_records.py`](../tools/create_internal_test_r1_r2_source_ingestion_records.py)
**Harness:** [`tests/validate_phase65_r1_r2_source_ingestion_records.py`](../tests/validate_phase65_r1_r2_source_ingestion_records.py)
(`make validate-phase65`, in `make validate`; offline, temp-SQLite only, contacts no production)

---

## 1. What was written

**Two source ingestion records were created: R2 first, then R1.**

| Field | R2 — SKU / item master export | R1 — current inventory by SKU / location |
| --- | --- | --- |
| stored record id | `ing_884c94df03c34908` | `ing_a2abb497f471458e` |
| order | **first** | **second** |
| target table / action | `source_ingestion_records` / `create_source_ingestion_record` | same |
| authorization anchor | `internal_test_001` (engagement) | `internal_test_001` (engagement) |
| `client_id` / `owner_id` | `99999` / `peak_internal_admin` | `99999` / `peak_internal_admin` |
| `authorization_scope` | `internal_peak_only` | `internal_peak_only` |
| `source_reference_id` | `pkt_internal_test_r2_sku_item_master_001` | `pkt_internal_test_r1_inventory_sku_location_001` |
| `packet_schema_name` / `version` | `engagement_packet` / `v0` | `engagement_packet` / `v0` |
| `packet_source_type` | `internal_test_export` | `internal_test_export` |
| `packet_location_reference` | `internal-test-artifact://phase65/r2-sku-item-master-export-v1` | `internal-test-artifact://phase65/r1-current-inventory-sku-location-v1` |
| `packet_hash` | SHA-256 of the external artifact | SHA-256 of the external artifact |
| `review_status` / `output_status` | `needs_review` / `draft` | `needs_review` / `draft` |
| `authoritative` | `false` | `false` |
| `client_facing_approved` / `capsule_candidate_ready` | `false` / `false` | `false` / `false` |
| `idempotency_key` | `phase65_internal_test_source_ingestion_r2_001` | `phase65_internal_test_source_ingestion_r1_001` |

## 2. Why R2 first, then R1

Phase 64 (`docs/PHASE64_INTERNAL_TEST_R1_R7_SOURCE_ARTIFACT_COLLECTION_PLAN.md`) recorded the order
and the reasons, and Phase 65 executed it unchanged:

1. **R2 is the only request the Phase 63 R8 map shows as unblocked.** R1 is *expected* but blocked
   on the unconfirmed location model.
2. **R1 is not interpretable without R2.** R1's item identifiers cannot be assessed for duplication
   or unit-of-measure consistency without the item master, so the pair only becomes meaningful once
   the master is registered.
3. **R2 first within the batch** means a partial Phase 65 would still have landed the unblocked
   artifact. The order is fixed in the operator utility's packet table; no flag can reverse it.
4. **R1 registers with its location dimension explicitly provisional**, recorded now rather than
   discovered later at evidence time.

## 3. R1's location dimension remains provisional

**The location dimension of R1 is provisional and is recorded as such on the row.** R8 flags the
location/bin naming model as **unconfirmed**, and per-location quantity is precisely what R1 exists
to supply. The R1 row's provenance notes state, in the record itself:

- the location dimension is provisional because the R8 location/bin naming model is unconfirmed;
- any future evidence derived from R1 must carry **degraded reliability for location-attributed
  claims** until that model is confirmed, while **SKU-level claims are not similarly limited**;
- the R8 location/WMS posture and the authority precedence rule both remain unconfirmed, so **no R1
  measure may yet be attributed to a system of record**;
- **R9** — the location/bin naming model from the Phase 62 plan — remains uncollected and is the
  natural follow-on request that unblocks this dimension.

## 4. The artifact bodies live outside the repository

Both artifacts are durable internal-test files held **outside the repository**, under the approved
internal-test artifact directory. They are **not committed**, not printed, and not readable from the
repository. The operator utility opens each in binary solely to compute its byte length and SHA-256;
their bytes are never decoded, logged, or placed on a draft.

**Only metadata was persisted** — the packet reference id, schema name and version, source type, a
**logical** location reference, and the `packet_hash`. No raw artifact payload, no export rows, no
item values, no quantities, no location identifiers, and no filesystem path reached the database.
The stored location references are deliberately logical (`internal-test-artifact://…`) so the rows
leak no operator home directory or machine layout. The writer independently refuses any draft
carrying `packet_payload`, `raw_packet_content`, `raw_content`, `payload`, or a secret-named
attribute, so the metadata-only rule is enforced on both sides of the boundary.

**Both artifacts are Peak-authored internal test data, not client-supplied exports.** That is
recorded on each row's provenance notes so nothing downstream can later mistake them for
client-provided evidence. They hold **no real client data and no pseudo-client data**; the parent
engagement is `internal_test`, excluded from client-facing reads by the Phase 57 isolation
primitive. Each artifact describes the *shape* of an export — a field-level description — and
carries no example rows.

## 5. Naming deviation from the Phase 64 plan

The Phase 65 sprint brief named artifact filenames, packet reference ids, and logical location
references that differ from the placeholders sketched in Phase 64 for R2 (and for R1's packet
reference id). **The Phase 65 brief's names were used**, and they are the values recorded in
Section 1 and persisted on the rows. The Phase 64 plan document has been annotated so the two
records do not contradict each other. Nothing else about the plan changed: the order, the posture,
the metadata-only rule, and the exclusions are all as Phase 64 specified.

## 6. What Phase 65 did not do

- **No `evidence_reference`.** Registration asserts only that an artifact exists under this
  engagement — no claim about contents, no reliability rating, no characterization. R8 review
  remains a precondition for evidence, not for collection.
- **No report draft, no review packet, no capsule candidate, no client-facing output.**
- **No Client record, no additional Engagement, no intake note, no review record.**
- **No AgentNet publication.** The public resolver is live and reachable; that is precisely why the
  gate stays shut. **Resolver publication remains unauthorized** and nothing here was published.
- **R3–R7 remain deferred.** Each carries an unresolved R8 blocker — reason-code discipline,
  count-programme existence, WMS scope, exception definition, and the documented-versus-practiced
  gap. **R9**, the location/bin naming model, remains the natural next request.
- **No migration, no migration 015, no model, no writer, no allowlist pair.**
- **No `UPDATE`, `DELETE`, manual SQL, cleanup path, app scan, or app row count.**
- **No artifact body printed, committed, or stored in the database**, and no fixture, example, or
  sample packet committed.

## 7. Idempotency and the no-overwrite rule

Each record carries its own Phase 65 idempotency key. An exact replay returns the existing row
unmodified. A **changed artifact hash under the same key is refused as an `idempotency_conflict`** —
never an overwrite. An artifact that is regenerated rather than corrected gets a new version slug
(`-v2`), not a silent rewrite of `-v1`. The operator utility has no `UPDATE`, `DELETE`, or cleanup
path, and on a partial failure it stops and reports rather than retrying with changed packet data.
