# Phase 92 — First Lab Source-Ingestion Write

**Type:** Controlled lab writer rehearsal. One durable lab record.

**Baseline:** the committed Phase 91 commit `98629da` — *Document Phase 91 drift and workflow review*.

**What this phase did.** It created **exactly one** `source_ingestion_records` row in `peak_lab`,
derived from the Phase 88 read-only lab scenario measurement, using the existing Phase 89 lab
writer-enablement gate as-is and the existing Phase 24 source-ingestion writer. Nothing else was
written.

**What this phase did not do.** No production access of any kind, and no production credential was
read. No provider or cloud command. No Alembic `upgrade`, `downgrade`, or `stamp`, and **no
migration 015**. No schema, model, enum, allowlist, writer, or gate was changed. **No new test
harness was added** — no defect required one. No evidence, review, intake, client, or engagement
record was created, and the engagement-anchor writer was not invoked. `peak_lab_scenario` was never
opened, read, or written. `docs/Peak_Investor_Overview_AI.docx` was not touched.

---

## 1. The gate was the precondition, not a report

The Phase 89 gate was used **unmodified**. It was evaluated before any connection existed, and the
run refuses without writing unless the decision grants exactly the one requested target.

| Gate field | Value |
|---|---|
| `outcome` | `lab_write_authorized` |
| `reason` | `lab_target_confirmed_and_scoped` |
| `lab_write_authorized` | true |
| `authorized_writer_targets` | `source_ingestion_records/create_source_ingestion_record` |
| `anchor_bootstrap_authorized` | false |
| `target_user_class` / `target_schema_class` | `lab_marked_user` / `expected_lab_schema` |
| `production_write_authorized` | false |
| `safe_to_write_production_now` | false |
| `production_writer_enablement_authorized` | false |

The Phase 90 anchor-bootstrap confirmation was **not set and not needed**: the source-ingestion pair
is an ordinary member of the gate's enableable set, so the request never reaches the bootstrap
branch. This is the first use of the ordinary lab data-record path that Phase 89 built.

## 2. The runtime credential, checked value-free

Structural checks only, against the out-of-repo runtime env file — no value was printed, echoed, or
logged, and no production variable was read: file present and mode `600`, **exactly one** variable,
named `PEAK_RUNTIME_DATABASE_URL`, scheme `mysql+pymysql`, user `peak_lab_runtime`, database
`peak_lab`, password/host/port/`ssl_ca` all present, not the provider default database, not the
scenario schema, and no production marker.

Read back as the credential itself: `SELECT` and `INSERT` only — **no `UPDATE`, no `DELETE`, no
`DROP`, no `CREATE`, no `ALTER`, no `GRANT OPTION`** — and **no visibility into
`peak_lab_scenario`** (the schema is not in the role's visible set). Writing to the scenario schema
was structurally impossible on this path, not merely disallowed by policy.

## 3. Before the write

`peak_lab` reachable; current database `peak_lab`; current user the lab runtime role; `alembic_version`
holding exactly one row at `014_engagement_classification`; all 18 controlled tables present with no
extra tables. Application rows: `engagements` = 1 (the Phase 90 anchor, exactly one, matching on
every governed field), **every other controlled table = 0**, total 1.

## 4. The record

Derived from the Phase 88 measurement of scenario `internal_test_inventory_ops_v1` version `v1`,
whose conclusion is that the scenario is repeatably measurable read-only and **partial and
readiness-oriented — not client evidence and not production evidence**. Only the documented
measurement summary and the published scenario content hash were used. **No scenario row body, SQL
extract, JSON extract, or CSV extract was read into the request, the record, or this document.**

| Field | Value |
|---|---|
| `id` | `ing_d67b76327aba4add` (server-controlled) |
| `owner_id` | `peak_internal_admin` |
| `client_id` | `99999` (reserved internal-test marker, stored as a string) |
| `engagement_id` | `lab_internal_test_001` |
| `authorization_scope` | `internal_peak_only` |
| `source_reference_id` | `pkt_lab_phase88_scenario_measurement_001` |
| `review_status` / `output_status` / `lifecycle_status` | `needs_review` / `draft` / `active` |
| `idempotency_key` | `phase92_lab_source_ingestion_phase88_measurement_001` |
| `payload_fingerprint` | present, 64 characters |
| `captured_at` / `agent_run_id` | unset |

Packet **metadata only** is stored: schema name `lab_scenario_measurement` version `v1`, source type
`lab_scenario_measurement`, logical location `peak-lab-measurement://phase88/...` (a logical
reference, not a filesystem path), and the Phase 85 scenario content hash. `authoritative`,
`client_facing_approved`, and `capsule_candidate_ready` are all **false**. No payload, raw-content,
or secret-shaped key exists on the row.

Receipt: `outcome=created`, `permitted=true`, `stored_record_created=true`,
`transaction_committed=true`, `existing_record_returned=false`, `outcome_uncertain=false`.

## 5. After the write

`peak_lab` still at head `014_engagement_classification` with one `alembic_version` row.
`engagements` = 1 (unchanged), `source_ingestion_records` = **1**, and **every other controlled
table = 0** — `evidence_references`, `review_records`, `intake_note_records`, `clients` and the rest
all still empty.

**`peak_lab` now holds exactly two application rows: the Phase 90 `engagements` anchor and this
Phase 92 `source_ingestion_records` row.**

The DB-enforced idempotency boundary `uq_source_ingestion_records_idem` is present over four
columns, and the row carries both its idempotency key and a payload fingerprint. Idempotency was
verified **structurally** rather than by a second invocation, because this phase authorized exactly
one writer call; a replay would return `idempotent_replay` without writing.

## 6. Durability and correction posture

The record is **durable**. No cleanup was attempted and none is available: the runtime role holds no
`DELETE`, so removing the row is impossible on this path by construction, not by policy. A
correction requires explicit later append-only or versioned handling — a new record superseding this
one — never a runtime deletion or an in-place rewrite. Removal would require the migration
credential, which is a separate approval and a separate risk, not authorized here.

## 7. Method note

The one-time invocation ran from an **out-of-repo operator script**, under the Phase 91 policy that
a temporary out-of-repo script is acceptable when the durable result is documented and the script is
not product behaviour. It added no repo surface and no harness. Every field needed to reconstruct
the request is recorded in §4 above. The alternative — committing a per-phase tool as Phase 90 did —
was declined here specifically to avoid the per-phase artifact accumulation Phase 91 identified; if
a committed tool is wanted for reproducibility, that is a small, separate decision.

One carried-forward caveat from Phase 90 still holds: the **gate** reads `PEAK_LAB_WRITER_TARGET_URL`
while the **writer** connects via `PEAK_RUNTIME_DATABASE_URL`. Two variables must independently point
at the same lab target, and the gate cannot verify what the writer will actually connect to. Both
were sourced from the same single-variable lab runtime file here, and the post-write verification
confirms the row landed in `peak_lab`.

## 8. Next

The next useful step is **either** a first lab evidence reference **or** a first review record —
**not both**, and not without its own explicit approval naming writer, records, expected count,
scope, idempotency key, receipts, verification, and cleanup posture. Both pairs are already
*enableable* by the Phase 89 gate; that remains a statement about reachability, not approval.

## 9. Baseline at the end of this phase

| Property | Value |
|---|---|
| Alembic head | `014_engagement_classification` (repo and `peak_lab`) |
| Migrations | 14 |
| Migration 015 | Does not exist |
| Controlled Peak tables | 18 |
| Controlled writers | 12 |
| Production write enablement | None standing; gate reports false |
| `peak_lab` application rows | **2** — one `engagements` anchor (Phase 90), one `source_ingestion_records` row (Phase 92) |
| `peak_lab_scenario` | Not opened, not read, not written |
| New harnesses added | None |
