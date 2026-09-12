# Phase 107 — One Durable Lab Evidence Reference: R1 On-Hand Attribution Coverage

**Type:** Approved lab durable record write. Exactly one record. No migration.

**Baseline:** the committed Phase 106 commit `1e2da39` — *Decide Phase 106 evidence production*.

**What this phase did.** It created **exactly one** `evidence_references` row in `peak_lab`, using
the existing `evidence_references/create_draft` writer (the unchanged Phase 21 evidence writer) under
the existing Phase 89 lab writer-enablement gate, enabled for this phase only. The row carries the
bounded R1 on-hand attribution coverage claim decided in Phase 106 §5. Nothing else was written.

**Why it matters.** Phase 105 settled that the workflow chain is *contract-complete and
evidence-empty*: every contract ran correctly, and findings were blocked for want of an `evid_`
citation. Phase 93's evidence row is real but supports only a record-*existence* statement. This row
is the first evidence reference in the lab that carries a **substantive** statement about inventory
data, so the chain now holds **one evidence-backed internal finding candidate**.

**What this phase did not do.** No production access, no production connection, and no production
write. No `peak_lab_scenario` connection; no scenario row body was read or printed. No
`source_ingestion_records` row and no `review_records` row were created, and neither of those
writers was invoked. No cycle-count evidence was created, seeded, inferred, or invented. No Alembic
`upgrade`, `downgrade`, or `stamp`, and **no migration 015**. No schema, model, enum, writer,
writer allowlist, lab writer enablement policy, gate, prompt, test, tool, Makefile, schema file,
agent, or harness was changed. No new harness and no new framework was added.
`docs/Peak_Investor_Overview_AI.docx` was not touched.

---

## 1. The gate, used as-is

The Phase 89 lab writer-enablement gate was evaluated **before any connection existed**, with exactly
one target requested.

| Gate field | Value |
|---|---|
| `outcome` / `reason` | `lab_write_authorized` / `lab_target_confirmed_and_scoped` |
| `writer_target` | `lab` |
| `requested_writer_targets` / `authorized_writer_targets` | `evidence_references/create_draft` (both) |
| `anchor_bootstrap_authorized` | false |
| `target_user_class` / `target_schema_class` | `lab_marked_user` / `expected_lab_schema` |
| `production_write_authorized` / `safe_to_write_production_now` / `production_writer_enablement_authorized` | false / false / false |
| `database_contacted` / `sql_issued` / `writer_invoked` / `credential_file_read` / `secrets_printed` | false (all) |

Enablement was for **this phase only**. It is not standing authority: the gate itself records that a
future write needs its own phase approval. No production target was enabled, and no additional
target/action pair was requested.

## 2. The credential, checked value-free

Structural checks only, **no value printed**: file present, mode `600`, outside the repository,
**exactly one** variable line and that variable is `PEAK_RUNTIME_DATABASE_URL`, scheme
`mysql+pymysql`, user `peak_lab_runtime`, database `peak_lab`, not the scenario schema, no production
marker, `ssl_ca` present. Env files were sourced **inside a subshell only**; no env value, DSN, host,
port, credential, or path was printed or committed.

The Phase 90 caveat still holds: the **gate** reads `PEAK_LAB_WRITER_TARGET_URL` while the **writer**
connects via `PEAK_RUNTIME_DATABASE_URL`. Both were derived from the same single-variable lab runtime
file, and post-write verification confirmed the row landed in `peak_lab` under the lab runtime role.

## 3. Before the write

`peak_lab` reachable, current database `peak_lab`, current user the lab runtime role,
`alembic_version` one row at `014_engagement_classification`. Application rows: `engagements` = 1,
`source_ingestion_records` = 1, `evidence_references` = 1, `review_records` = 1 — **4 total**, the
documented state. No row carried the Phase 107 idempotency key.

## 4. The record

| Field | Value |
|---|---|
| `id` | `evid_8151dad609974ea0` (server-controlled) |
| `owner_id` / `client_id` / `engagement_id` | `peak_internal_admin` / `99999` / `lab_internal_test_001` |
| `authorization_scope` | `internal_peak_only` |
| target table / action | `evidence_references` / `create_draft` |
| `source_reference_id` (in `details_json`) | `ing_d67b76327aba4add` — the Phase 92 source-ingestion record |
| `source_location` | a `peak-lab-measurement://` logical locator for the Phase 88 R1 measurement (logical reference, never a filesystem path) |
| `evidence_type` / `source_type` / `reliability` | `other` / `other` / `low` |
| `evidence_status` | `collected` (model default; not caller-settable) |
| `operational_area` / `inventory_process_area` | `inventory` / `on_hand_attribution` |
| `review_status` / `output_status` / `lifecycle_status` | `needs_review` / `draft` / `active` |
| `sensitive_data_flag` | false |
| `created_by` | `peak_internal_admin` (requester role `internal_admin`) |
| `idempotency_key` | `phase107_lab_evidence_reference_phase88_r1_coverage_001` |
| `payload_fingerprint` | present, 64 characters |
| `source_phase` | `phase107` |

Receipt: `outcome=created`, `permitted=true`, `stored_record_created=true`,
`transaction_committed=true`, `existing_record_returned=false`, `outcome_uncertain=false`,
`review_status=needs_review`, `output_status=draft`. The writer was invoked **once**.

**`other` / `other` was used deliberately.** `schemas/evidence-reference.schema.json` defines closed
vocabularies, and `measurement`/`system` was considered and declined in Phase 106 §5.2:
`source_type=system` risks being read as a client system export and therefore as an implicit
authority claim, which is exactly what this row must not carry. `other`/`other` is the conservative
member of both vocabularies; the descriptive intent lives in the title and summary. This matches the
Phase 93 precedent and required no schema, enum, or writer change.

## 5. The claim boundary stored on the record

The row supports **one** statement:

> In the internal synthetic lab scenario `internal_test_inventory_ops_v1` version `v1`, on-hand rows
> are attributable to **both** a resolvable item **and** a resolvable location in **14 of 32 cases
> (43.8%)**, with the shortfall attributable to named structural blockers.

Named blockers, as stored: unresolvable locations (7 of 32 — 3 with no location code, 4 naming a
location code absent from the location model), item-master gaps (11 of 32), and absent quantities
(3 of 32). Source-of-record precedence is recorded as **unconfirmed**, so no measure may be
attributed to a system of record.

### The explicit non-claim, stored in the record's own text

**Coverage is not accuracy.** The record states that it does **not** establish inventory accuracy;
that **inventory accuracy remains unanswered**, because no cycle-count population exists in the lab
scenario and none was created, seeded, or inferred; that it does **not** assert source-system truth
and does **not** resolve **R8 authority precedence**; that it does **not** describe a real client, a
real warehouse, or a real source system; and that it carries no benchmark, projection, or rate for
use outside the lab.

It is further stored as supporting a coverage/readiness finding candidate **only**, and **not**:
recommendation support, capsule candidacy, publication readiness, client-facing output, or AgentNet
resolver publication.

**Content rule.** The row stores aggregate figures, record ids, posture flags, and logical locators
only. **No scenario row body, source row body, artifact body text, item or SKU value, location
identifier, quantity value, or SQL/JSON/CSV extract** is stored on it or reproduced here.

## 6. Posture

Internal lab only. **Not real client data. Not pseudo-client data. Not client accessible. Not
client-facing. Not production evidence. Not authoritative.** No capsule readiness. No AgentNet
publication. `client_id` `99999` is the reserved internal-test namespace and a visible marker.

As in Phase 93, `evidence_references` has no `authoritative` column: the writer **refuses** a draft
claiming `authoritative`, `client_facing_approved`, or `capsule_candidate_ready` before the
connection opens, and server-stamps `review_status='needs_review'` and `output_status='draft'`
itself. The posture is therefore enforced at write time and additionally written into the stored
summary, but is not independently readable as a stored boolean.

## 7. After the write — bounded verification

Value-free: counts, ids, statuses, and posture flags only. No raw row body, SQL, env value, DSN,
host, local path, packet body, scenario body, or stack trace was printed.

| Check | Result |
|---|---|
| Current database / current user | `peak_lab` / lab runtime role |
| `alembic_version` | one row, `014_engagement_classification` (unchanged) |
| Rows matching the Phase 107 idempotency key | **exactly 1** — `evid_8151dad609974ea0` |
| `evidence_references` | 1 → **2** |
| `source_ingestion_records` | 1 → **1** (unchanged; **no row created by Phase 107**) |
| `review_records` | 1 → **1** (unchanged; **no row created by Phase 107**) |
| `engagements` | 1 → **1** (unchanged) |
| Every other controlled table | 0 (unchanged) |
| Application rows total | 4 → **5** |
| Production connection / write | none |
| `peak_lab_scenario` connection | none |

**`peak_lab` now holds exactly five application rows:** the Phase 90 `engagements` anchor, the
Phase 92 `source_ingestion_records` row, the Phase 93 `evidence_references` row, the Phase 94
`review_records` row, and this Phase 107 `evidence_references` row.

Idempotency was verified **structurally** — the DB-enforced boundary over
owner/client/engagement/key, plus a single matching row — not by a second invocation, because this
phase authorized exactly one writer call. A replay would return `idempotent_replay` without writing.

## 8. Durability and correction posture

The record is **durable**, with **no cleanup**. None was attempted and none is available: the lab
runtime role holds `SELECT` and `INSERT` only, so removal is impossible on this path by construction,
not by policy. A correction requires explicit later append-only or versioned handling — a successor
record — never a runtime deletion or an in-place rewrite. Removal would need the migration
credential, a separate approval not authorized here.

## 9. Method note

The one-time invocation ran from an **out-of-repo operator script**, under the Phase 91 policy that a
temporary out-of-repo script is acceptable when the durable result is documented and the script is
not product behaviour — the same method Phase 92 used. It added no repo surface, no tool, and no
harness. Every field needed to reconstruct the request is recorded in §4 and §5 above.

## 10. What remains blocked

- **Inventory accuracy.** Unanswered, and not answerable from this evidence. No cycle-count or
  accuracy-variance population exists in the lab scenario, and none may be seeded or invented to
  create one.
- **R8 authority precedence.** Unresolved. No measure may yet be attributed to a system of record.
- **Client-facing and production use.** This is lab evidence about synthetic scenario data. It is
  not client evidence and not production evidence.
- **Capsule candidacy and AgentNet publication.** Both remain shut. The public resolver is live,
  which is why that gate stays shut rather than relaxed.

## 11. Next

Reporting can now be **re-exercised against one evidence-backed finding candidate**, which Phase 105
could not do. Any such report must stay **narrow**: it may cite `evid_8151dad609974ea0` for R1
on-hand attribution coverage and nothing more, must repeat that coverage is not accuracy, must not
present the row as reviewed or authoritative, and must remain internal and non-client-facing. It is
not approved by this phase. Note also the Phase 106 finding that the automated packet path stays
blocked — nothing produces an `EngagementPacket` — so such a report would be hand-drafted citing a
real record id.

A review record acting on this evidence reference is **not** approved here either. Phase 94
established that review does not propagate; a reviewer decision would need its own phase naming
writer, records, expected count, scope, idempotency key, receipts, verification, and cleanup posture.

## 12. Baseline at the end of this phase

| Property | Value |
|---|---|
| Alembic head | `014_engagement_classification` (repo and `peak_lab`) |
| Migrations / migration 015 | 14 / does not exist |
| Controlled Peak tables / writers | 18 / 12 |
| Production write enablement | None standing; gate reports false |
| Lab write enablement | Granted for `evidence_references/create_draft` for this phase only; no standing authority |
| `peak_lab` application rows | **5** — Phases 90, 92, 93, 94, 107, one each |
| `peak_lab_scenario` | Not opened, not read, not written |
| New harnesses / frameworks added | None |
