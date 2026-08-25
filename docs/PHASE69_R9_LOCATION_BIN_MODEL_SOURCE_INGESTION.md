# Phase 69 — The R9 Location/Bin Naming Model Source Ingestion

**Status:** production-sensitive phase — **one application record written**. Exactly **one
`source_ingestion_records` row was created**, registering the internal test **R9 location/bin
naming model** artifact. No evidence reference, no review record, no Client record, no additional
Engagement, no intake note, no report, and no capsule record.
**Baseline:** `8be7893` — Add Phase 68 R2 evidence reference review decision
**Alembic head:** unchanged at `014_engagement_classification` (14 migrations, 18 tables, 12
writers) — Phase 69 adds no migration, no model, no writer, and no allowlist pair
**Writer:** [`peak/db/source_ingestion_writer.py`](../peak/db/source_ingestion_writer.py) (Phase 24, unchanged)
**Operator utility:** [`tools/create_internal_test_r9_source_ingestion_record.py`](../tools/create_internal_test_r9_source_ingestion_record.py)
**Harness:** [`tests/validate_phase69_r9_location_bin_model_source_ingestion.py`](../tests/validate_phase69_r9_location_bin_model_source_ingestion.py)
(`make validate-phase69`, in `make validate`; offline, temp-SQLite only, contacts no production)

---

## 1. What was written

**One R9 source ingestion record was created.** It registers the R9 location/bin naming model
artifact as a collected source. Registration is **collection, not review and not validation**.

| Field | Value |
| --- | --- |
| stored record id | `ing_64b2e2648ac1402b` |
| target table / action | `source_ingestion_records` / `create_source_ingestion_record` |
| authorization anchor | `internal_test_001` (engagement, loaded from the DB at write time) |
| `client_id` / `owner_id` | `99999` / `peak_internal_admin` |
| `authorization_scope` | `internal_peak_only` |
| `source_reference_id` (`packet_reference_id`) | `pkt_internal_test_r9_location_bin_model_001` |
| `packet_schema_name` / version | `engagement_packet` / `v0` |
| `packet_source_type` | `internal_test_export` |
| `packet_location_reference` | `internal-test-artifact://phase69/r9-location-bin-naming-model-v1` |
| `packet_hash` | SHA-256 over the exact artifact bytes |
| `output_status` / `review_status` / `lifecycle_status` | `draft` / `needs_review` / `active` |
| `authoritative` | `false` |
| `client_facing_approved` / `capsule_candidate_ready` | `false` / `false` |
| requested by / requester role | `peak_internal_admin` / `internal_admin` |
| `idempotency_key` | `phase69_internal_test_source_ingestion_r9_001` |

## 2. What R9 is

**R9 is a location/bin naming model artifact.** It is a *structural* description of what a location
model would have to define before the word "location" can be read as a measured dimension. It
describes, at field and concept level only:

- **location hierarchy fields** — site, warehouse, zone, aisle, rack/bay, bin, and the questions of
  whether each level is present, stored separately, or embedded in a composite code;
- **bin/location naming fields** — identifier, code format, display label, alias/legacy code,
  parent reference, and the normalization questions that determine whether two values can be
  compared at all;
- **location type and status fields** — what a position is for, whether it is active, and whether
  stock at it may be allocated;
- **inventory availability treatment** — on-hand versus available, allocated/reserved, in transit,
  and the distinction between a **status bucket** and a **physical position**;
- **virtual, staging, hold, damaged, quarantine, and unavailable-inventory concepts** — the values
  that may appear as locations without denoting a physical place;
- **ownership/authority posture** — ERP, WMS, manual, or unknown, each recorded **cautiously as an
  open question**, never as an established ownership claim.

**The artifact body lives outside the repository**, in the operator's external internal-test
artifact directory. It is not committed, not printed, and not stored in the database.

## 3. What was persisted, and what was not

**Only metadata, the hash, and the logical location reference were persisted.** The stored row
carries the packet reference id, schema name and version, source type, the logical
`internal-test-artifact://` location reference, the `packet_hash`, the posture flags, and the
provenance notes. It carries **no artifact body, no filesystem path, no export row, no item or SKU
value, no quantity, and no location identifier, bin code, aisle name, rack name, warehouse name, or
site name**.

The artifact itself contains none of those values either — it is a field-level and concept-level
description with **no instance data of any kind**, and therefore cannot support any count, rate, or
total.

## 4. Why R9 was collected

**R9 is collected to unblock the future R1 location-dimension review.** Phase 65 registered R1 with
its **location dimension explicitly provisional**: R8 flags the location/bin naming model as
unconfirmed, and per-location quantity is precisely what R1 supplies. Phase 62 named R9 as the
location model itself; Phase 64 named R9 as the unblocker for R1's location dimension and for R5.
Collecting it gives a future R1 location review something defined to review against.

## 5. What R9 does not do

- **R9 does not validate inventory quantities.** It contains no quantity and asserts none. It is
  not an inventory accuracy finding and must not be presented as one.
- **R9 does not make R1 evidence-ready by itself.** It does not lift R1's provisional location
  marking; that is a review decision, not a property of a collected artifact.
- **R9 must be reviewed before use in evidence references.** It was registered
  `needs_review` / `draft` / `authoritative=false`, and no `evidence_reference` may cite it until a
  review record says otherwise.
- **R9 does not confirm R8 authority precedence.** R8 remains **provisional**, `needs_review`,
  `draft`, `authoritative=false`, with an unconfirmed precedence rule. Nothing here validates,
  extends, or overrides R8.
- **R9 does not settle R5's WMS scope uncertainty.** The same unconfirmed WMS scope that blocks R5
  determines who owns the fine-grained bin model, so the two questions move together — but R9 is
  not evidence about WMS scope.

## 6. Downstream evidence implications

If the location model proves defined and consistent, location-attributed R1 claims could become
assessable rather than provisional, and a stable vocabulary would exist for machine attribution. If
it proves absent, inconsistent, or undocumented, the finding available is a **data-readiness or
reliability observation about the location model itself** — not an inventory accuracy finding. Any
future evidence derived from R9 carries the reliability its own review assigns and inherits none
from R1, R2, or R8.

## 7. What was explicitly not created

**No evidence reference** was created. **No review record** was created — R9 has not been reviewed.
**No report** record and **no capsule** record were created. **No client-facing output** was
produced. **No AgentNet publication** was made: the public resolver is live, but **publication
remains unauthorized** and gated. No Client row, no additional Engagement, and no intake note were
created. No `UPDATE`, `DELETE`, cleanup, manual SQL, app-table scan, or app-row count was issued.

## 8. Posture after Phase 69

- **R9** — collected; `needs_review` / `draft` / `authoritative=false`; not yet reviewed, not yet
  citable.
- **R1** — location dimension **remains provisional**. R9 is a necessary input to resolving it, not
  a sufficient one.
- **R2** — unchanged: approved only for future internal assessment use about item-master source
  availability and data readiness.
- **R8** — unchanged: **provisional**, `needs_review`, `draft`, `authoritative=false`, precedence
  unconfirmed. Not authoritative.
- **R3–R7** — remain **deferred**.
- **No inventory accuracy conclusion exists.** Report drafting and capsule publication remain
  unauthorized. The AgentNet resolver is live; **publication remains unauthorized**.
- `subject_record_type` vocabulary cleanup remains deferred.

## 9. Why a new operator utility rather than a flag

The Phase 63 and Phase 65 operator utilities each state as a safety property that they can express
exactly the records they were written for and that **no flag can retarget them**. Parameterising
either to accept a substitute or additional packet would delete that property from a tool that has
already written production rows. Phase 69 leaves both untouched and states the same property for
its own single fixed packet: identity, idempotency key, packet reference, and logical location
reference are module constants, and the only flags are the run mode and the artifact path — which
is itself refused unless it is the one approved external artifact.

## 10. What Phase 70 decided about this record

**Phase 70 reviewed this R9 source ingestion record** and created one `review_records` row
(`rev_3ecc0891f4fe48ce`) through the unchanged Phase 22 review writer, under this same
`internal_test_001` / `internal_peak_only` anchor, with `subject_record_type =
'source_ingestion_record'` and `target_id = ing_64b2e2648ac1402b`.

**The decision is `approve_internal` and non-authoritative**, approving R9 **only for future
evidence work about R1 location-dimension readiness** — the §4 purpose this record was collected
for, and nothing wider. The review confirmed **registration integrity**: the artifact's hash still
matches the `packet_hash` registered here.

**The review recorded one central limit.** R9 is a **question set, not an answered model** — every
hierarchy level and type/status field is presence-unknown, and the structural questions are posed
without being answered. That is appropriate for a collected source, but it confirms §5's statement
directly: **R9 cannot by itself lift R1's provisional location marking**, because only measured
answers could.

**This record was not modified.** A review records a decision about a target, and the review writer
has no `UPDATE` path, so this row still reads `needs_review` / `draft` / `authoritative=false`.
**No evidence reference was created**; R1's location dimension **remains provisional**; R9 **does
not validate inventory quantities**; **R8 authority precedence and R5 WMS scope remain unresolved**;
**R3–R7 remain deferred**; and report, capsule, client-facing output, and **AgentNet resolver
publication remain unauthorized** despite the live public resolver. See
[`PHASE70_R9_SOURCE_INGESTION_REVIEW_DECISION.md`](PHASE70_R9_SOURCE_INGESTION_REVIEW_DECISION.md).

## 11. What Phase 71 planned around this record

**Phase 71 is planning-only** — no production access, no production write, and **no
`evidence_reference`, `review_record`, or `source_ingestion_record` created**. **No production record of any kind was
created.** It planned what must
happen before this record can support evidence about R1's location dimension.

Its premise is §10's confirmed finding: **R9 is reviewed but is a question set, not an answered
model**. Phase 71 made the gap concrete against R1 — R1 carries one required location identifier
plus one *optional* level marker, both marked provisional in the R1 artifact, against the six-level
hierarchy this record describes — and listed **15 required measured answers** as the gate before any
R1/R9 evidence reference.

**This record was not modified and its posture is unchanged**: `needs_review` / `draft` /
`authoritative=false`. **R1's location dimension remains provisional.** The recommended next
production step is **R10 — a measured location model answer set** that answers this record's
question set, registered as its own source ingestion (Phase 72) and non-authoritative until
reviewed. That is a **recommendation only**; report drafting, capsule publication, client-facing
output, and **AgentNet resolver publication remain unauthorized**. See
[`PHASE71_R1_R9_EVIDENCE_READINESS_PLAN.md`](PHASE71_R1_R9_EVIDENCE_READINESS_PLAN.md).
