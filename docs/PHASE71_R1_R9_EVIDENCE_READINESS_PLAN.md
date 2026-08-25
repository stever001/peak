# Phase 71 — The R1/R9 Evidence-Readiness Plan

**Status: planning-only.** This phase contacted **no production database**, sourced **no environment
file**, invoked **no writer**, and created **no production record of any kind** — no
`evidence_reference`, no `review_record`, no `source_ingestion_record`, no Client, no Engagement, no
intake note, no report, no capsule, and no AgentNet or resolver publication. It adds one planning
document and one offline validation harness. Nothing here authorizes a write; it recommends one.
**Baseline:** `d177c5f` — Add Phase 70 R9 source ingestion review decision
**Alembic head:** unchanged at `014_engagement_classification` (14 migrations, 18 tables, 12
writers) — Phase 71 adds no migration, no model, no writer, no allowlist pair, and no operator
utility
**Harness:** [`tests/validate_phase71_r1_r9_evidence_readiness_plan.py`](../tests/validate_phase71_r1_r9_evidence_readiness_plan.py)
(`make validate-phase71`, in `make validate`; offline, no DB, contacts no production)

---

## 1. Planning-only status

| | |
| --- | --- |
| production access | **none** — no env file sourced, no connection opened |
| production writes | **none** |
| `evidence_reference` created | **no** |
| `review_record` created | **no** |
| `source_ingestion_record` created | **no** |
| Client / Engagement / intake record created | **no** |
| report / capsule / client-facing output created | **no** |
| AgentNet or resolver publication | **no** |
| migration / model / writer / allowlist change | **none** |
| operator utility added | **none** |

## 2. The chain and posture this plan starts from

| link | record |
| --- | --- |
| Engagement (authorization anchor) | `internal_test_001` / `99999` / `peak_internal_admin` / `internal_peak_only` |
| Intake note | `intn_b8b86b8c196c4595` |
| Intake review | `rev_b82ff6f00790418f` |
| R8 source ingestion | `ing_4fb70519cbf84401` |
| R2 source ingestion | `ing_884c94df03c34908` |
| R1 source ingestion | `ing_a2abb497f471458e` |
| R2 source-ingestion review | `rev_bf7f18a13d8f461c` |
| R2 evidence reference | `evid_56437d9b9c764560` |
| R2 evidence-reference review | `rev_de2b6e73f6c94c67` |
| R9 source ingestion | `ing_64b2e2648ac1402b` |
| R9 source-ingestion review | `rev_3ecc0891f4fe48ce` |

**Posture carried into this plan:**

- **R1's location dimension remains provisional.** Nothing since Phase 65 has lifted that marking.
- **R9 is reviewed but remains non-authoritative** (`approve_internal`, `authoritative=false`),
  approved only for future evidence work about R1 location-dimension readiness.
- **R9 is a question set, not an answered model** — Phase 70's central recorded finding.
- **R8 remains unresolved:** `needs_review` / `draft` / `authoritative=false`, authority precedence
  unconfirmed.
- **R5 WMS scope remains unresolved.**
- **R3–R7 remain deferred.**
- **R2** is approved only for future internal assessment use about item-master source availability
  and data readiness.
- **No inventory accuracy conclusion exists.** Report drafting, capsule publication, client-facing
  output, and AgentNet resolver publication all remain unauthorized. The public resolver is live,
  which is why the gate stays shut rather than relaxed.
- `subject_record_type` vocabulary cleanup remains deferred.

## 3. Core planning finding

> **R1 cannot yet support a location-dimension `evidence_reference` because the collected R9 artifact
> defines the questions that must be answered, but does not answer them. The next operational need is
> a measured location-model answer set, not another evidence reference.**

## 4. The concrete structural gap

Both registered artifacts were re-read for **structure only** — field names, roles, and counts. No
body was printed, copied into this repository, or committed, and no location, bin, aisle, rack,
warehouse, or site **values** were read or recorded. The names below are **schema field names**, not
data.

**R1 declares 10 fields, of which exactly two carry the location dimension**, and both are marked
provisional in the artifact itself:

| R1 field | role | required? |
| --- | --- | --- |
| `location_identifier` | location dimension (provisional) | **required** |
| `location_level` | location dimension (provisional) | *optional* |

**R9 describes a six-level hierarchy and five naming fields.** The gap is therefore precise and
measurable:

1. **One required identifier must map onto a six-level model, and that mapping is unknown.** R9
   names six candidate levels; R1 supplies one required identifier field. Which level (or levels) it
   denotes is exactly what is unmeasured.
2. **`location_level` is optional, which is a first-order readability problem.** If the level marker
   may be absent per row, location values can sit at mixed granularity with nothing on the row to
   say so. A total over such a column is not a total over a consistent thing.
3. **Location is a grain key.** R1's declared grain is one row per item identifier per location
   identifier as of a single timestamp — so any ambiguity in the location dimension is ambiguity in
   the grain itself, not merely in one attribute.
4. **Availability treatment is only partly present.** R1 carries `inventory_status` and
   `quantity_allocated`, both optional. R9's status-bucket-versus-physical-position distinction may
   therefore be unanswerable from R1 alone.
5. **A temporal anchor exists on one side only.** R1 requires `as_of_timestamp`; the location model
   carries no effective-dating concept, so time-alignment between quantities and the location
   structure is unestablished.
6. **A reconciliation path to R2 exists but is unverified.** R1 requires `item_identifier` and R2 is
   the declared join key; whether the two draw on the same identifier domain is still unchecked.

## 5. Required measured answers before any R1/R9 evidence reference

Each item below must be **measured and recorded**, not assumed. Until they are, no
`evidence_reference` about R1's location dimension should be created.

| # | Required measured answer |
| --- | --- |
| 1 | **Which hierarchy levels actually exist** in the client/system context — which of the six candidate levels are real, which are absent, and which are naming convention only. |
| 2 | **Which R1 field or fields map to each hierarchy level** — the explicit mapping from R1's location fields onto the levels that exist. |
| 3 | **What `location_identifier` actually represents** — a physical bin, a logical bucket, a site, a warehouse, a zone, a status, a virtual location, or a **mixed** field carrying more than one of these. |
| 4 | **Whether R1 carries inventory availability status or only physical position** — and if both, which field governs when they disagree. |
| 5 | **Whether hold, damaged, quarantine, unavailable, staging, in-transit, virtual, and non-nettable inventory are represented** — and whether as a location value, a status value, a separate row, or not at all. |
| 6 | **Which system owns the location model** — ERP, WMS, manual process, hybrid, or unknown. |
| 7 | **Whether ERP and WMS location identifiers align or diverge** — and if they diverge, on which levels and by what rule. |
| 8 | **Which names or codes require normalization, aliasing, or a crosswalk** — case, padding, delimiter, legacy scheme, and whether any mapping is one-to-one. |
| 9 | **Whether location names are stable enough for evidence use** — whether identifiers are reissued on reorganization, and whether history is retained. |
| 10 | **Whether R1 quantities are time-aligned with the location model** — whether the location structure has an effective date, and how it relates to `as_of_timestamp`. |
| 11 | **Whether R1 item identifiers are reconcilable to R2** — same identifier domain, same normalization, measured rather than assumed. |
| 12 | **What would count as sufficient evidence that the location dimension IS readable** — the positive threshold, stated in advance. |
| 13 | **What would count as sufficient evidence that it is NOT reliable enough** — the negative threshold, stated in advance, so a null result is a finding rather than a stall. |
| 14 | **What remains dependent on R8 authority-precedence review** — which answers cannot be settled until R8 is reviewed. |
| 15 | **What remains dependent on R5 WMS scope clarification** — which answers move only when WMS scope is settled. |

**Items 12 and 13 are stated in advance deliberately.** Fixing both thresholds before measurement is
what keeps a disappointing answer from being re-litigated into a favourable one, and it means "the
location dimension is not reliable enough" is a legitimate, reportable outcome rather than a failure
of the phase.

## 6. Non-claims and exclusions

This plan makes, and authorizes, **none** of the following:

- **No inventory accuracy conclusion.**
- **No quantity reliability conclusion.**
- **No R1 location validation** — the provisional marking stands.
- **No R8 authority-precedence conclusion.**
- **No R5 WMS scope conclusion.**
- **No report drafting.**
- **No capsule publication.**
- **No client-facing output.**
- **No AgentNet resolver publication.**

It also creates no production record, and it does not pre-approve the phases it recommends.

## 7. Recommended next phase

**Phase 72 — R10 Location Model Answer Set Source Ingestion**, unless a re-read of the existing
artifacts shows they already contain measured answers. They do not: R9 is a question set by Phase
70's finding, and R1 marks both of its location fields provisional in the artifact itself.

| | suggested value |
| --- | --- |
| external artifact | `~/.peak/peak-internal-test-artifacts/phase72/r10_location_model_answer_set_v1.json` |
| `packet_reference_id` | `pkt_internal_test_r10_location_model_answer_set_001` |
| `packet_location_reference` | `internal-test-artifact://phase72/r10-location-model-answer-set-v1` |
| `packet_schema_name` / version | `engagement_packet` / `v0` |
| `packet_source_type` | `internal_test_export` — the Phase 63/65/69 convention |
| writer | the existing Phase 24 source ingestion writer, unchanged |
| posture | `draft` / `needs_review` / `active` |
| `authoritative` | `false` |
| `client_facing_approved` / `capsule_candidate_ready` | `false` / `false` |

**R10 is the artifact that answers R9's question set** sufficiently to make future R1/R9 evidence
possible. Like every collected source before it, **it remains non-authoritative until reviewed** —
collection is not review, and an answer set is not a finding.

A caution worth carrying into Phase 72: R10 must record **measured answers, including negative and
unknown ones**. An answer set that quietly omits the questions that came back unfavourable would be
worse than no answer set, because it would look like readiness.

## 8. The alternative path, and why it is deferred

A **narrow R9 `evidence_reference` could be created now**. Phase 70 approved R9 for exactly this
kind of use, so the path is open and would be legitimate.

It is deferred because of what it would actually establish: **that Peak holds a reviewed question
set**. That is true and auditable, but it does not materially advance R1 location readiness — it
adds a link to the chain without moving the dimension any closer to readable. Collecting measured
answers does move it.

**Defer the narrow R9 evidence reference unless it is later wanted for audit completeness** — for
instance to show an unbroken source → review → evidence chain for R9 specifically. That remains
available at any time; nothing about deferring it now forecloses it.

## 9. Recommended sequence — a recommendation, not an authorization

| phase | step |
| --- | --- |
| **Phase 72** | R10 location model answer set **source ingestion** (one `source_ingestion_records` row) |
| **Phase 73** | R10 **source-ingestion review decision** (one `review_records` row) |
| **Phase 74** | R1/R9/R10 **evidence reference** for location-dimension readability or readiness |
| **Phase 75** | **Review** of that evidence reference |
| later | only then, consider a narrow **internal assessment finding** |

**Each phase above is separately approved.** Listing them here authorizes none of them. The sequence
may also terminate early and legitimately: if R10's measured answers show the location dimension is
not reliable enough, Phase 74's honest evidence is a **data-readiness or reliability finding about
the location model**, not an inventory accuracy finding — and no amount of further collection would
change that.

R8 review, R5 WMS scope clarification, and R3–R7 collection remain outstanding alongside this
sequence, and report drafting, capsule publication, client-facing output, and **AgentNet resolver
publication remain gated and unauthorized** throughout.

## 10. What Phase 72 collected against this plan

**Phase 72 collected R10**, the measured location model answer set this plan recommended in §7, as
one `source_ingestion_records` row (`ing_b26d137a0a334ee9`) through the unchanged Phase 24 writer under
the same `internal_test_001` / `internal_peak_only` anchor. Metadata, a SHA-256 `packet_hash`, and
the logical reference `internal-test-artifact://phase72/r10-location-model-answer-set-v1` were
persisted; the **artifact body lives outside the repository**.

**All 15 §5 checklist items were answered**, each with an explicit answer state. The §7 caution was
honoured: **R10 includes negative and unknown answers**, none of the 15 was dropped, merged, or
softened, and **11 of 15 resolve to a negative, unknown, or blocked state**.

**The thresholds this plan fixed in advance did their job.** All six §5-item-12 "readable"
conditions are unmet and five §5-item-13 "not reliable enough" conditions are met, so the honest
present reading — **R1's location dimension is not currently readable** — is a reportable outcome
rather than a stall, exactly as §5 anticipated. Items 6, 7, 14, and 15 are recorded `blocked_by_r8`
or `blocked_by_r5`, confirming this plan's §5 reading that some answers cannot move until those
phases run.

**Nothing in §6 was violated.** **No `evidence_reference` was created**; **R1's location dimension
remains provisional**; no inventory accuracy or quantity reliability conclusion was made; and no
report, capsule, client-facing output, or AgentNet publication was created or authorized. **R10 is
`needs_review` / `draft` / `authoritative=false` and must be reviewed before evidence use.** The §9
sequence continues at **Phase 73 — the R10 source-ingestion review decision**, still separately
approved. See
[`PHASE72_R10_LOCATION_MODEL_ANSWER_SET_SOURCE_INGESTION.md`](PHASE72_R10_LOCATION_MODEL_ANSWER_SET_SOURCE_INGESTION.md).

## 11. Where the §9 sequence actually went

The §9 sequence anticipated Phase 73 as an R10 review and Phase 74 as a separate evidence
reference. **Phase 73 did both**, as two writes in one phase — the review
(`rev_9b6b0a67bae54a51`) and the location-readiness evidence reference (`evid_f26c5f8fc0aa44d4`) —
rather than splitting a bounded pair across two phases.

**The §5 thresholds decided the outcome, as intended.** 0 of 6 "readable" conditions met, 5
"not reliable enough" conditions met, so the recorded finding is the **negative** one this plan
fixed in advance: **R1's location dimension is not currently readable**. §9's caveat that the
sequence "may legitimately end early" is what happened — the honest result is a **data-readiness and
reliability finding, not an inventory accuracy finding**, and further source collection would not
change it.

**Phase 74/75 as sketched are therefore superseded.** The likely next useful step is a minimal
internal assessment finding or report-outline step, or first addressing **R8 precedence** or **R5
WMS scope**, on which four of R10's fifteen items are blocked. **R1 remains provisional**, R3–R7
remain deferred, and report drafting, capsule publication, client-facing output, and AgentNet
resolver publication remain unauthorized. See
[`PHASE73_R10_REVIEW_LOCATION_READINESS_EVIDENCE.md`](PHASE73_R10_REVIEW_LOCATION_READINESS_EVIDENCE.md).
