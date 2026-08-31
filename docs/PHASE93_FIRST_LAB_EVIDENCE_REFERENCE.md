# Phase 93 — First Lab Evidence Reference

**Type:** Controlled lab writer rehearsal. One durable lab record.

**Baseline:** the committed Phase 92 commit `9ece39b` — *Document Phase 92 lab source ingestion*.

**What this phase did.** It created **exactly one** `evidence_references` row in `peak_lab`, derived
from the Phase 92 source-ingestion record — which in turn derived from the Phase 88 lab scenario
measurement — using the existing Phase 89 lab writer-enablement gate as-is and the existing Phase 21
evidence writer. Nothing else was written.

**What this phase did not do.** No production access and no production credential read. No provider
or cloud command. No Alembic `upgrade`, `downgrade`, or `stamp`, and **no migration 015**. No schema,
model, enum, allowlist, writer, or gate was changed. **No new test harness was added** — no defect
required one. No source-ingestion, review, intake, client, or engagement record was created, and
none of those writers was invoked. `peak_lab_scenario` was never opened, read, or written.
`docs/Peak_Investor_Overview_AI.docx` was not touched.

---

## 1. The gate, used as-is

The Phase 89 gate was evaluated **before any connection existed** and the run refuses without writing
unless it grants exactly the one requested target.

| Gate field | Value |
|---|---|
| `outcome` / `reason` | `lab_write_authorized` / `lab_target_confirmed_and_scoped` |
| `authorized_writer_targets` | `evidence_references/create_draft` |
| `anchor_bootstrap_authorized` | false |
| `target_user_class` / `target_schema_class` | `lab_marked_user` / `expected_lab_schema` |
| `production_write_authorized` / `safe_to_write_production_now` / `production_writer_enablement_authorized` | false / false / false |

The Phase 90 anchor-bootstrap confirmation was **not set and not needed**. This is the second use of
the ordinary lab data-record path Phase 89 built, after Phase 92.

## 2. The credential, checked value-free

Structural checks only, no value printed: file present, mode `600`, outside the repo, **exactly one**
variable named `PEAK_RUNTIME_DATABASE_URL`, scheme `mysql+pymysql`, user `peak_lab_runtime`, database
`peak_lab`, password/host/port/`ssl_ca` present, not the provider default, not the scenario schema, no
production marker.

Read back as the credential itself: `SELECT` and `INSERT` only — **no `UPDATE`, `DELETE`, `DROP`,
`CREATE`, `ALTER`, or `GRANT OPTION`** — and **no visibility into `peak_lab_scenario`**.

## 3. Before the write

`peak_lab` reachable, current database `peak_lab`, current user the lab runtime role,
`alembic_version` one row at `014_engagement_classification`, 18 controlled tables and no extras.
`engagements` = 1 and `source_ingestion_records` = 1 — both verified field-by-field, including that
the Phase 92 record is `ing_d67b76327aba4add`, scoped `internal_peak_only`, review-gated at
`needs_review` / `draft` / `active`, with `authoritative`, `client_facing_approved`, and
`capsule_candidate_ready` all false. `evidence_references` = 0. Every other controlled table = 0.
Exactly one anchor and exactly one source-ingestion record existed; no others.

## 4. The record

| Field | Value |
|---|---|
| `id` | `evid_f094cbe4b47d4048` (server-controlled) |
| `owner_id` / `client_id` / `engagement_id` | `peak_internal_admin` / `99999` / `lab_internal_test_001` |
| `authorization_scope` | `internal_peak_only` |
| `source_reference_id` (in `details_json`) | `ing_d67b76327aba4add` — the Phase 92 record |
| `source_location` | `peak-lab-measurement://phase88/...` (logical, not a filesystem path) |
| `evidence_type` / `source_type` / `reliability` | `other` / `other` / `low` |
| `evidence_status` | `collected` (model default; not caller-settable) |
| `sensitive_data_flag` | false |
| `review_status` / `output_status` / `lifecycle_status` | `needs_review` / `draft` / `active` |
| `operational_area` / `inventory_process_area` | `unspecified` / `unspecified` |
| `idempotency_key` | `phase93_lab_evidence_reference_phase92_source_ingestion_001` |
| `payload_fingerprint` | present, 64 characters |

Receipt: `outcome=created`, `stored_record_created=true`, `transaction_committed=true`,
`existing_record_returned=false`, `outcome_uncertain=false`.

## 5. The claim boundary

The stored summary supports **exactly one statement**: a Phase 88 lab scenario measurement exists as
a controlled Peak source-ingestion record in the lab, namely `ing_d67b76327aba4add`, locatable at
`peak-record://source_ingestion_records/ing_d67b76327aba4add`. It records, in the record itself, that
it does **not** support an inventory accuracy conclusion, does **not** assert source-system truth,
is **not reviewed**, is **not authoritative**, is **not client-facing**, is **not capsule-ready**, and
that report drafting and AgentNet resolver publication remain unauthorized. It restates that the
underlying Phase 88 measurement is internal synthetic lab-scenario data — partial and
readiness-oriented, **not client evidence and not production evidence**.

**Content rule.** The row stores record ids, posture flags, and logical locators only. **No scenario
row body, artifact body text, field value, item or SKU value, quantity, or location identifier** is
stored on it or reproduced here.

## 6. Three contract differences worth recording

These are differences between the requested shape and what the existing contract and schema actually
permit. In each case the contract was followed and nothing was changed to accommodate the request.

1. **`evidence_type` and `source_type` are schema-bounded.** `schemas/evidence-reference.schema.json`
   defines closed vocabularies — `evidence_type` ∈ {`interview_statement`, `visual_observation`,
   `workflow_observation`, `document`, `system_export`, `photograph`, `measurement`,
   `consultant_note`, `other`} and `source_type` ∈ {`stakeholder`, `site_walk`, `system`, `document`,
   `consultant`, `other`}. The proposed `lab_source_ingestion_readiness_reference` and
   `source_ingestion_records` are not members, so **`other` was used for both**. The subject is an
   internal Peak controlled record, which no other listed category names; `system_export` would have
   over-claimed an export of rows that does not exist. The descriptive intent is carried in the title
   and summary instead. Note the vocabulary is advisory at the DB layer — the columns are plain
   strings with no enum or check constraint — so this was voluntary conformance, as in Phase 67.
2. **There is no typed link column.** `evidence_references` has no related-object join. The link to
   the Phase 92 record is carried three redundant, free-form ways: `source_reference_id`, the
   `peak-record://` locator inside the summary, and the record id named in the summary text. Phase 67
   documented this same limit rather than working around it.
3. **The row has no `authoritative` column.** The writer enforces `authoritative`,
   `client_facing_approved`, and `capsule_candidate_ready` as false **before** the connection opens,
   but does not persist them on an evidence row — unlike `source_ingestion_records`, which records
   them in `details_json`. The non-authoritative posture is therefore enforced at write time and
   stated in the summary text, but is not independently readable as a stored flag.

A convention divergence, deliberate and minor: Phase 67 put the packet reference in
`source_reference_id` and the `peak-record://` pointer in `source_location`. Here
`source_reference_id` names the Phase 92 record id directly — a more direct link, given this phase's
purpose — and `source_location` names the Phase 88 measurement origin, so both ends of the chain are
recorded.

## 7. After the write

`peak_lab` still at head `014_engagement_classification` with one `alembic_version` row.
`engagements` = 1 and `source_ingestion_records` = 1, both unchanged. `evidence_references` = **1**.
`review_records`, `intake_note_records`, `clients`, and every other controlled table = 0.

**`peak_lab` now holds exactly three application rows: the Phase 90 `engagements` anchor, the
Phase 92 `source_ingestion_records` row, and this Phase 93 `evidence_references` row.**

The DB-enforced idempotency boundary `uq_evidence_references_idem` is present over four columns.
Idempotency was verified **structurally** rather than by a second invocation, because this phase
authorized exactly one writer call; a replay would return `idempotent_replay` without writing.

## 8. Durability and correction posture

The record is **durable**. No cleanup was attempted and none is available: the runtime role holds no
`DELETE`, so removal is impossible on this path by construction, not by policy. A correction requires
explicit later append-only or versioned handling — a successor record — never a runtime deletion or
in-place rewrite. Removal would require the migration credential, a separate approval not authorized
here.

## 9. Next

The next useful step is a **first review record**, which would let a reviewer decision act on this
evidence reference and move it off `needs_review`. It is not approved by this phase. The pair is
already *enableable* by the Phase 89 gate; that is reachability, not approval. It needs its own phase
naming writer, records, expected count, scope, idempotency key, receipts, verification, and cleanup
posture.

## 10. Baseline at the end of this phase

| Property | Value |
|---|---|
| Alembic head | `014_engagement_classification` (repo and `peak_lab`) |
| Migrations / migration 015 | 14 / does not exist |
| Controlled Peak tables / writers | 18 / 12 |
| Production write enablement | None standing; gate reports false |
| `peak_lab` application rows | **3** — Phases 90, 92, 93, one each |
| `peak_lab_scenario` | Not opened, not read, not written |
| New harnesses added | None |
