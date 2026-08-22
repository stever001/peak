# Phase 62 — The Internal Test Source/Evidence Request Plan

**Status:** **planning-only — no production write.** Phase 62 contacts no database, invokes no
writer, reads no environment file, and creates **no production record**. It translates the Phase 61
review decision into a concrete source/evidence request plan and names the writer Phase 63 should
exercise.
**Baseline:** `227c1196a799cf4bc4827cda0c3bc6fc88398ebe`
**Alembic head:** unchanged at `014_engagement_classification` (14 migrations, 18 tables, 12
writers) — Phase 62 adds no migration, no model, no writer, and no allowlist pair
**Inspected writer:** [`peak/db/source_ingestion_writer.py`](../peak/db/source_ingestion_writer.py)
(Phase 24, unchanged — inspected, not invoked)
**Harness:** [`tests/validate_phase62_internal_test_source_evidence_request_plan.py`](../tests/validate_phase62_internal_test_source_evidence_request_plan.py)
(`make validate-phase62`, in `make validate`; offline, contacts no production)

---

## 1. The phase decision

- **Phase 62 is planning-only. No production write is authorized and none was performed.**
- **Source/evidence collection is the next step after Phase 61.** The Phase 61 decision
  (`rev_b82ff6f00790418f`, `approve_internal`, `authoritative=false`) authorizes moving *toward*
  collection — it does not skip it.
- **Report drafting and capsule publication are not yet authorized.** No internal assessment report
  draft, review packet, capsule candidate, or publication is in scope, and none becomes authorized
  by this plan.
- **This request plan is internal/admin only.** It is an internal working document, not a client
  deliverable and not an intake form to be sent anywhere.
- **No real client data.** The engagement is `internal_test_001` under reserved client `99999`,
  scope `internal_peak_only`. Nothing in this plan names, describes, or implies a real client.
- **No client-facing output** was created, and none is created by executing this plan.

## 2. Chain state entering Phase 62

| Record | Id | Phase |
| --- | --- | --- |
| Engagement authorization anchor | `internal_test_001` (client `99999`, owner `peak_internal_admin`, scope `internal_peak_only`) | 59 |
| Intake note | `intn_b8b86b8c196c4595` | 60 |
| Review decision | `rev_b82ff6f00790418f` (`approve_internal`) | 61 |
| Source ingestion record | **none** | — |
| Evidence reference | **none** | — |
| Report draft / review packet / capsule | **none** | — |

## 3. Findings from inspecting the existing source/evidence writers

### 3.1 `source_ingestion_records` is the right next record

`peak/db/source_ingestion_writer.py` is the only writer-backed, allowlisted path that **registers an
inbound artifact against an engagement**. It is metadata-only by contract: it persists a packet
reference id, schema name/version, source type, location reference, and hash, and it **rejects** any
draft carrying `packet_payload`, `raw_packet_content`, `raw_content`, `payload`, or a secret-like
attribute name. That is exactly the claim the internal test needs to make first — *this artifact
exists and is registered under this engagement* — with no claim about its contents.

The write is anchored the same way as Phases 20–22 and 59–61: `request.subject` must be the
`engagement`, and at write time the writer loads the stored `Engagement` row and requires
`request.authorization_scope == engagement.authorization_scope`. Identity matching is necessary but
not sufficient. The Phase 59 anchor already satisfies this.

### 3.2 `evidence_references` should come **after** source ingestion, not before

`evidence_references` is not a neutral container. Its columns assert characterization:
`evidence_type`, `source_type`, `reliability`, `evidence_status` (default `collected`),
`sensitive_data_flag`, and a non-sensitive `summary`. Writing one before any source is registered
would assert that evidence was *collected* and assess its *reliability* with no registered artifact
to attribute it to.

The Phase 23 ingestion boundary already encodes this ordering: evidence normalization requests are
**derived from an ingested packet** (`PacketDerivedEvidencePlan`), not authored independently. So the
order is: **register the source → normalize → write the evidence reference.** Phase 63 is the first
half of that; evidence writing is Phase 64 or later.

### 3.3 The gap — a *pending request* has no writable representation

The honest limit of the current contracts: **a source/evidence request that has been made but not
yet fulfilled cannot be represented by any enabled writer.** `SourceIngestionDraft` requires a
`packet_reference_id` and the record means *an artifact was referenced*, not *an artifact was asked
for*.

The model that would represent it already exists — `source_system_references`, whose
`source_system_access_status` enum is precisely
`not_requested / requested / granted / partial / denied / expired / revoked` — but it has **no
writer, no draft contract, and no allowlist pair**, so it is unreachable by any controlled path.

**Recommendation (not implemented in Phase 62):** do **not** add a writer now. Track the request
state in this document, and write a `source_ingestion_records` row only when an artifact actually
arrives. If request-state tracking later becomes load-bearing, the narrowest future change is a
single `(source_system_references, create_source_system_reference)` allowlist pair plus one narrow
writer following the Phase 24 pattern — a governance change of the same weight as any other
allowlist expansion, and out of scope here.

### 3.4 What would make a Phase 63 write dishonest

The writer contract supports the next step **only if a real internal_test artifact exists at write
time.** If nothing has actually been produced or gathered by Phase 63, a `source_ingestion_records`
row would reference a packet that does not exist. In that case Phase 63 must **not** write, and must
say so — the correct outcome is to defer, not to fabricate a packet reference.

## 4. The prioritized source/evidence requests

Ten requests. Categories are from
[`PEAK_INTAKE_QUESTION_TAXONOMY_V0.md`](PEAK_INTAKE_QUESTION_TAXONOMY_V0.md); the eight
quantitative gaps recorded in Phase 61 are cited where a request closes one.

| # | Request | Priority | Closes Phase 61 gap |
| --- | --- | --- | --- |
| R1 | Current inventory export by SKU/location | required | 03, 04, 07 |
| R2 | SKU/item master export | required | 03 |
| R3 | Inventory adjustment history with reason codes | important | 06 |
| R4 | Recent cycle count or physical count results | required | 06, 14 |
| R5 | Receiving and putaway records | important | — |
| R6 | Stockout/backorder or fulfillment exception data | important | 07 |
| R7 | SOP and process documentation | important | — |
| R8 | System-of-record and data-export map | required | 08, 09 |
| R9 | Location/bin naming model and site structure | important | 04 |
| R10 | Target metric, baseline, and deadline statement | optional | 14 |

### R1 — Current inventory export by SKU and location

- **Purpose:** establish the measured on-hand baseline by item and by location, so later findings
  can be quantified rather than described.
- **Taxonomy V0 categories:** 03 item/SKU master · 04 location structure · 07 stockouts and
  overstocks · 09 data exports and reporting
- **Downstream deliverable:** inventory accuracy assessment; the quantitative baseline for
  working-capital and service-level findings.
- **Priority:** required
- **Expected evidence type:** structured tabular export (CSV/XLSX), quantitative
- **AI/AgentNet/capsule readiness:** yes — machine-readable on-hand quantities are the core input a
  future capsule would need.
- **Safe for internal_test only:** yes — internal/synthetic data only; no real client export.

### R2 — SKU/item master export

- **Purpose:** quantify identifier discipline — duplicate rate, master size, units of measure,
  attribute completeness, and item-master ownership.
- **Taxonomy V0 categories:** 03 item/SKU master · 09 data exports and reporting · 12 AI/AgentNet
  readiness
- **Downstream deliverable:** data-readiness finding; closes the Phase 61 gap that duplicate rate
  and master size are unquantified.
- **Priority:** required
- **Expected evidence type:** structured tabular export, quantitative
- **AI/AgentNet/capsule readiness:** yes — product data inconsistent for humans is unusable for
  machines; this is the readiness measurement itself.
- **Safe for internal_test only:** yes — internal/synthetic data only.

### R3 — Inventory adjustment history with reason codes, if available

- **Purpose:** measure adjustment volume, reason-code discipline, adjustment authority, and shrink
  visibility.
- **Taxonomy V0 categories:** 06 counts, adjustments, shrink · 08 systems of record · 10 SOPs,
  approvals, exceptions
- **Downstream deliverable:** control-risk and accuracy assessment; closes the Phase 61 gap that
  adjustment volume is unquantified. Adjustment practice is the fastest read on whether recorded
  inventory can be trusted.
- **Priority:** important
- **Expected evidence type:** structured transactional export; may legitimately be partial or absent
- **AI/AgentNet/capsule readiness:** partial — reason codes are machine-readable only where they are
  coded; free-text reasons are not.
- **Safe for internal_test only:** yes — internal/synthetic data only.

### R4 — Recent cycle count or physical count results

- **Purpose:** measure count cadence and coverage, and the variance between counted and recorded
  inventory.
- **Taxonomy V0 categories:** 06 counts, adjustments, shrink · 04 location structure · 14 success
  metrics and urgency
- **Downstream deliverable:** inventory accuracy assessment; supplies the baseline metric a success
  measure can be stated against.
- **Priority:** required
- **Expected evidence type:** structured count results with variance, quantitative
- **AI/AgentNet/capsule readiness:** yes — variance is a directly capsule-shaped measurement.
- **Safe for internal_test only:** yes — internal/synthetic data only.

### R5 — Receiving and putaway records

- **Purpose:** observe the actual inbound flow of goods and where it deviates from the documented
  flow.
- **Taxonomy V0 categories:** 05 receiving through shipping · 04 location structure · 10 SOPs,
  approvals, exceptions
- **Downstream deliverable:** workflow and process evaluation; this is where most improvement-plan
  items originate.
- **Priority:** important
- **Expected evidence type:** transactional records and/or system screenshots; mixed structured and
  unstructured
- **AI/AgentNet/capsule readiness:** partial — transactional records are machine-readable;
  deviation from documented flow is a human judgement.
- **Safe for internal_test only:** yes — internal/synthetic data only.

### R6 — Stockout, backorder, or fulfillment exception data

- **Purpose:** quantify service-level failures and connect operational symptoms to cost.
- **Taxonomy V0 categories:** 07 stockouts and overstocks · 02 current pain points · 14 success
  metrics and urgency
- **Downstream deliverable:** service-level and working-capital findings; closes the Phase 61 gap
  that stockout frequency and carrying cost are unquantified.
- **Priority:** important
- **Expected evidence type:** structured exception export, quantitative
- **AI/AgentNet/capsule readiness:** yes — exception rates are a capsule-ready metric.
- **Safe for internal_test only:** yes — internal/synthetic data only.

### R7 — SOP and process documentation

- **Purpose:** establish the documented procedure so it can be compared against the practiced one.
- **Taxonomy V0 categories:** 10 SOPs, approvals, exceptions · 05 receiving through shipping ·
  11 evidence availability
- **Downstream deliverable:** process maturity and governance findings — the gap between documented
  and practiced is itself a finding.
- **Priority:** important
- **Expected evidence type:** documents (PDF/DOCX/wiki export), unstructured
- **AI/AgentNet/capsule readiness:** partial — documents are ingestible, but the
  documented-versus-practiced gap is not machine-derivable.
- **Safe for internal_test only:** yes — internal documentation only.

### R8 — System-of-record and data-export map

- **Purpose:** name the systems, fix the authority precedence rule, and enumerate what can be
  exported, in what format, at what cadence, by whom.
- **Taxonomy V0 categories:** 08 systems of record · 09 data exports and reporting · 11 evidence
  availability · 12 AI/AgentNet readiness
- **Downstream deliverable:** source-of-truth decisions on which every later evidence claim depends;
  closes the Phase 61 gaps that systems are unnamed and exports unenumerated. It also determines
  whether R1–R7 are fulfillable at all.
- **Priority:** required — this is the request that should be answered first, because it scopes the
  others.
- **Expected evidence type:** structured map or questionnaire response, plus access confirmation
- **AI/AgentNet/capsule readiness:** yes — a prerequisite for any capsule readiness claim.
- **Safe for internal_test only:** yes — internal systems only; no credentials are requested or
  stored by this plan.

### R9 — Location and bin naming model, and site structure

- **Purpose:** obtain the location model so evidence can be attributed to a place.
- **Taxonomy V0 categories:** 04 location structure · 05 receiving through shipping · 11 evidence
  availability
- **Downstream deliverable:** evidence normalization and operational assessment; closes the Phase 61
  gap that no location/bin naming model was supplied. Without a location model, R1's per-location
  quantities cannot be interpreted.
- **Priority:** important
- **Expected evidence type:** structured reference list or diagram; mixed
- **AI/AgentNet/capsule readiness:** yes — a stable location vocabulary is required for machine
  attribution.
- **Safe for internal_test only:** yes — internal/synthetic structure only.

### R10 — Target metric, baseline, and deadline statement

- **Purpose:** record how the engagement will be judged, against what baseline, by when.
- **Taxonomy V0 categories:** 14 success metrics and urgency · 02 current pain points · 13
  publication and capsule boundaries
- **Downstream deliverable:** improvement-plan prioritization and engagement outcomes; closes the
  Phase 61 gap that no target metric, baseline, or deadline exists.
- **Priority:** optional — for *source/evidence collection*. It is an intake clarification rather
  than an evidence artifact, and collection is not blocked on it; it becomes required before an
  improvement plan is prioritized.
- **Expected evidence type:** written statement, unstructured
- **AI/AgentNet/capsule readiness:** partial — a stated target metric is machine-checkable; the
  judgement behind it is not.
- **Safe for internal_test only:** yes — internal statement only.

## 5. The recommended Phase 63 writer and path

| | |
| --- | --- |
| **Writer** | [`peak/db/source_ingestion_writer.py`](../peak/db/source_ingestion_writer.py) — `persist_source_ingestion_record()` (Phase 24, unchanged) |
| **Target table** | `source_ingestion_records` |
| **Target action** | `create_source_ingestion_record` |
| **Authorization anchor** | `Engagement` `internal_test_001`, loaded from the DB at write time |
| **Scope** | `internal_peak_only` — must equal the stored `engagement.authorization_scope` |
| **Posture** | `output_status=draft`, `review_status=needs_review`, `lifecycle_status=active`, `authoritative=false`, `client_facing_approved=false`, `capsule_candidate_ready=false` |
| **Records written** | exactly **one** row, and nothing else |
| **Precondition** | at least one real internal_test artifact exists at write time; otherwise Phase 63 defers and writes nothing |

No new writer, model, migration, or allowlist pair is required for this path. **Evidence writing is
not Phase 63** — `evidence_references` follows source ingestion, per §3.2.

## 6. Proposed first source-ingestion packet shape (sanitized)

Prepared, **not executed**. All values below are placeholders; nothing here was submitted to any
writer, and no packet payload is persisted by the writer under any circumstances.

**Phase 17 `ControlledWriteRequest`**

```
owner_id             : peak_internal_admin
client_id            : 99999
engagement_id        : internal_test_001
requested_by         : peak_internal_admin
requester_role       : internal_admin
authorization_scope  : internal_peak_only
target_table         : source_ingestion_records
requested_action     : create_source_ingestion_record
idempotency_key      : phase63_internal_test_source_ingestion_001
source_phase         : phase63_internal_test_source_ingestion
subject              : { subject_record_type: engagement,
                         subject_record_id  : internal_test_001,
                         owner_id/client_id/engagement_id identical to the request }
record_draft         : <the SourceIngestionDraft below>
```

**Phase 23 `SourceIngestionDraft` — metadata only**

```
source_ingestion_record_id : None            # server-controlled; the writer assigns ing_<slug>
created_at                 : None            # server-stamped
owner_id / client_id / engagement_id : identical to the request
packet_reference_id        : pkt_internal_test_<request_slug>_001   # required -> source_reference_id
packet_schema_name         : engagement_packet
packet_schema_version      : v0
packet_source_type         : internal_test_export
packet_location_reference  : <managed internal reference; a pointer, never a live path read>
packet_hash                : <sha256 of the artifact, computed outside the repository>
output_status              : draft
review_status              : needs_review
lifecycle_status           : active
authoritative              : false
client_facing_approved     : false
capsule_candidate_ready    : false
reasons                    : ["phase62 request plan R<n>", "internal test only"]
warnings                   : []
```

**Fields the draft must never carry.** `packet_payload`, `raw_packet_content`, `raw_content`,
`payload`, or any attribute whose name contains `password`, `secret`, `api_key`, `token`,
`private_key`, `credential`, `connection_string`, or `access_key` — the writer refuses the draft
outright on the attribute *name*, and never inspects or echoes a value.

**Where the packet hash and location come from.** Outside the repository, exactly as the Phase 60
intake-note body did. No artifact content, export row, or packet payload is committed here, and none
should be committed in Phase 63.

## 7. What Phase 62 did not do

- **No source ingestion record was created.** `source_ingestion_records` remains empty for this
  chain.
- **No evidence reference was created**, and no evidence was normalized.
- **No report draft, review packet, capsule candidate, or publication.**
- **No Client record, no Engagement, no intake note, no review record.**
- **No database connection, no SQL, no writer invocation, no environment read.**
- **No migration, no migration 015, no model, no writer, no allowlist pair.**
- **No client-facing output, approval, or financial verification.**
- **No fixture, example, or sample packet** was added to the repository.

## 8. Future real-client intake

**A future real-client intake form should produce this same evidence request structure.** The route
from a taxonomy category to a request is the same one used here: a category names the deliverable it
feeds, the deliverable names the measurable input it needs, and that input is the request. A form
built that way yields R1–R10's shape without a reviewer reconstructing it from memory — which is the
derivation rule from
[`PEAK_INTAKE_QUESTION_TAXONOMY_V0.md`](PEAK_INTAKE_QUESTION_TAXONOMY_V0.md) doing its job a second
time.

**Evidence and source collection precede analysis, report drafting, and capsule publication.** That
ordering is not a formality: a report drafted before R1–R10 land would describe what the intake note
already says, and Phase 61 established that the note supports narrative, not measurement.

---

## 9. Phase 63 — the plan's first execution

**Phase 63 registered R8 as the first internal test source ingestion record**
(`ing_4fb70519cbf84401`), through exactly the writer and path §5 recommended:
`source_ingestion_records` / `create_source_ingestion_record`, anchored on the stored
`internal_test_001` engagement, metadata only.

**The §3.4 precondition held.** No internal_test artifact existed when Phase 63 began, so rather
than write a row pointing at a nonexistent packet, a durable R8 artifact was created **outside the
repository** first and only its metadata — packet reference, schema, source type, a logical
`internal-test-artifact://` location reference, and a SHA-256 hash — was registered. The artifact
body was not committed and never entered the database.

**This closes the first precondition for R1–R7.** R8 was ranked ahead of them in §4 because it
determines whether they are fulfillable; with the map registered, they can be requested against
named systems and enumerated exports.

**No evidence reference was created**, and none is yet authorized — §3.2's ordering stands:
`evidence_references` come **after** source ingestion. Report drafting and capsule publication
remain unauthorized. See
[`PHASE63_FIRST_INTERNAL_TEST_SOURCE_INGESTION.md`](PHASE63_FIRST_INTERNAL_TEST_SOURCE_INGESTION.md).

---

## 10. Phase 64 — R1–R7 specified against the registered map

**Phase 63 registered R8**, and **Phase 64 defines the R1–R7 artifact collection** this plan's §4
called for — turning each request into a concrete artifact specification: type, minimum expected
fields or document sections, external filename, logical `internal-test-artifact://phase65/…`
reference, `packet_reference_id`, schema and source type, SHA-256 hash requirement, taxonomy
categories, and downstream deliverable. **Phase 64 creates no production record.**

§4 ranked R8 ahead of R1–R7 on the argument that it determines whether they are fulfillable. The
registered map bears that out: it records **R2 as the only unblocked request**, R1 as blocked on the
location model, and R3–R7 as uncertain or partial. The ordering argument was not decorative.

**Phase 65 should create the external artifact(s) and register `source_ingestion_records`, not
`evidence_references` yet** — recommended batch R2 then R1. **Artifact bodies remain outside the
repository**, and **capsule publication remains unauthorized despite the live AgentNet resolver**.
See
[`PHASE64_INTERNAL_TEST_R1_R7_SOURCE_ARTIFACT_COLLECTION_PLAN.md`](PHASE64_INTERNAL_TEST_R1_R7_SOURCE_ARTIFACT_COLLECTION_PLAN.md).
