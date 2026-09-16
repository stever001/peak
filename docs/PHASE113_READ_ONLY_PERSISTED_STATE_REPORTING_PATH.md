# Phase 113 — Read-Only Persisted-State Reporting Path

**Baseline:** `2fd729e` — *Fix Phase 112 target-specific review support*.

## 1. Status

**Product functionality phase. Read-only persisted-state fetch. No writes.** Phase 113 adds a
reusable read-only fetch layer and a persisted-state adapter, so the Phase 110–112 packet-view and
reporting route now starts from **actual stored Peak state** instead of record identity, statuses,
source links, and review relationships transcribed out of phase documents.

It connected to `peak_lab` **read-only** under explicit user approval, using the established lab
read-only role. **It performed no write, invoked no writer, enabled no writer, and created, updated,
or deleted no record.** It did not connect to production and did not connect to `peak_lab_scenario`.
`peak_lab` remains at **five application rows**, re-counted before and after the read.

No schema, model, enum, migration, writer, writer allowlist, writer gate, or prompt was changed. No
migration `015` exists. The only non-source change is one `make validate` entry for the new test.

## 2. What was added

| File | What it is |
| --- | --- |
| `peak/db/engagement_packet_reader.py` | The read-only fetch layer. Explicit `select()` statements over a whitelisted column list for `engagements`, `source_ingestion_records`, `evidence_references`, and `review_records`, returning plain dicts in the shape `assemble_packet_view` already consumes |
| `peak/reports/persisted_packet_view.py` | The pure adapter. Applies the caller-supplied claim-scope policy, then composes `assemble_packet_view` → `build_report_inputs_from_packet_view`, and builds the matching Phase 112 planner references |
| `tests/validate_phase113_persisted_state_reporting_path.py` | 49 checks, passing; database-free |

**The split is deliberate.** `peak/reports` stays DB-free — it imports no SQLAlchemy and no
`peak.db`, as every phase since 36 has asserted — because the adapter operates on plain dicts and
never knows where they came from. The DB-touching module sits in `peak/db`, next to the models and
the Phase 57 read-isolation primitive it reuses. **No repository framework, no data-access layer, no
CLI, and no workflow framework was added**; the fetch layer is six functions over existing models.

**Connection ownership stays outside the code.** Every fetch function takes an already-established
connection. The module creates no engine and no session, reads no environment variable, and holds no
credential, so the privilege lives with the caller and never in the repository.

## 3. Exactly what is fetched

Whitelisted columns, named one at a time. **No row body is ever selected.**

| Table | Columns selected |
| --- | --- |
| `engagements` | `id`, `client_id`, `owner_id`, `authorization_scope`, `engagement_category`, `real_client_data`, `client_accessible`, `capsule_publication_authorized`, `status`, `review_status`, `lifecycle_status` |
| `source_ingestion_records` | `id`, identity (`owner_id`, `client_id`, `engagement_id`, `authorization_scope`), `source_reference_id`, `review_status`, `output_status`, `lifecycle_status` |
| `evidence_references` | `id`, identity, `evidence_type`, `source_type`, `reliability`, `evidence_status`, `review_status`, `output_status`, `lifecycle_status`, `sensitive_data_flag` |
| `review_records` | `id`, identity, `target_id`, `subject_record_type`, `decision`, `review_status`, `new_status`, `authoritative`, `output_status`, `lifecycle_status` |

**Three `details_json` keys, extracted server-side, one key at a time:** `source_reference_id` —
the evidence → source link, which has no column of its own — plus `operational_area` and
`inventory_process_area`. The JSON body itself is never transferred, never printed, and appears
nowhere in this repository.

**Never selected:** `evidence_references.summary`, `review_records.reason`,
`engagements.engagement_label`, and every other narrative column; packet bodies; note bodies; report
bodies; external artifact bodies; unrestricted `details_json`; anything from `peak_lab_scenario`.

**Visibility uses the Phase 57 primitive, not a new filter.** The engagement must be visible in the
requested `ReadMode` or the read is refused before any record query runs, and the default is the
Phase 57 default — client-facing. Reading the internal test engagement therefore requires asking for
it explicitly. **Identity is reported, not silently filtered:** records are fetched by
`engagement_id`, and the packet view independently compares each record's owner / client /
engagement / scope and excludes any mismatch visibly.

## 4. `claim_scope` and summary provenance — stated honestly

**`claim_scope` is not a stored field, and Phase 113 did not invent one.** What an evidence item is
entitled to claim is controlled workflow semantics; the database holds no column for it. It is
supplied by the caller through an explicit `ClaimScopePolicy` — a map from evidence id to scope. It
is never derived from an evidence id, a phase label, or narrative text.

**Persisted areas are used in one direction only.** `operational_area` and
`inventory_process_area` can **refuse** a claim, never grant one: an evidence row whose areas are
both unspecified records no operational subject, so `operational_finding` is refused for it and the
reason is recorded on the view. Naming an area does **not** make a row an operational finding — a
row may name an area and still attest only that a record exists. This is a guard, and calling it an
evidence classifier would be false. An unrecognised scope is refused the same way.

Live state matches that direction: of the two lab evidence rows, the Phase 107 row has a specified
area and the Phase 93 row does not.

**Finding summary text is not read.** The fetch never selects `summary`, so a caller wanting summary
text in the schema-shaped evidence item supplies it through the same policy. With nothing supplied,
the view reports evidence summary text as not supplied rather than inventing any.

**This is therefore not an autonomous evidence-classification path.** Persisted state supplies
relationships and posture; claim classification and summary text still come from controlled workflow
semantics outside the database. That is the phase's main remaining product gap (§8).

## 5. Offline test

`tests/validate_phase113_persisted_state_reporting_path.py` — **49 checks, all passing**,
database-free, using in-memory summaries shaped as the whitelisted `SELECT`s return them. No DB
fixture, SQLite harness, JSON fixture file, or scenario extract was created. It proves that
fetched-shaped summaries assemble; that the Phase 94 review links only to the Phase 93 evidence
while the Phase 107 evidence stays `unreviewed` with its stored `needs_review` reported separately;
that report inputs cite the Phase 107 finding and its source only; that planner references carry the
same single target and the planner agrees; that the claim-scope policy is refused when unrecognised
or when the persisted areas are unspecified; that recommendations, client-facing output, and strict
`EngagementPacket` validity stay blocked; and that the read module selects no narrative column,
issues no write, and hard-codes no record id. Wired into `make validate` as `validate-phase113`.

**No phase-specific id is hard-coded in either source module.** The live exercise asks for
`lab_internal_test_001`; the code operates on any authorized engagement id.

## 6. Live read-only `peak_lab` exercise

Approved by the user for this phase. The lab read-only env file was checked value-safely
(present, mode `600`, owned by the operator, outside the repository) and sourced **inside a subshell
only**; no `set -x`, `env`, or `printenv` was used and no value was printed. **The Phase 82/88
naming seam applies again** — that file sets the production-named read-only variable while pointing
at the lab — so the destination was parsed in memory and the connection refused unless the driver,
the user (the lab read-only verifier role), and the database (`peak_lab`) all matched, with no
production marker and no scenario marker. It also confirmed that no runtime, migration, scenario, or
writer-target variable was set in that shell. The session ran as a **read-only transaction** and was
rolled back. Output passed through a filter dropping URL-shaped lines.

| Check | Result |
| --- | --- |
| Current database / current role | `peak_lab` / the lab read-only verifier role |
| Effective grants | `SELECT`, `USAGE` only; no `GRANT OPTION`; no grant names `peak_lab_scenario` |
| `peak_lab_scenario` visible to this role | no |
| Alembic head | `014_engagement_classification`, one row |
| Controlled tables counted | 18 |
| **Application rows, before and after** | **5** — `engagements` 1, `source_ingestion_records` 1, `evidence_references` 2, `review_records` 1; every other table 0; **unchanged** |
| Client-facing read of the internal test engagement | **refused** by the Phase 57 predicate |
| Fetched counts | 1 engagement, 1 source, 2 evidence, 1 review |
| Engagement identity / classification | `lab_internal_test_001`, client `99999`, owner `peak_internal_admin`, scope `internal_peak_only`; `internal_test`, not real client data, not client accessible, capsule publication not authorized |

**Relationships, read live rather than taken from documentation:**

| Relationship | Result |
| --- | --- |
| Both evidence rows → `ing_d67b76327aba4add` | resolves |
| `rev_70b5da9f14d54488` target | `evid_f094cbe4b47d4048` only, `subject_record_type=evidence_reference` |
| Reviews targeting `evid_8151dad609974ea0` | **none** |
| Stored `review_status` on both evidence rows | `needs_review` — unchanged by this phase |
| Effective review status of `evid_8151dad609974ea0` | **`unreviewed`** |
| Records excluded for identity mismatch / unresolved links | none / none |

**Packet view from persisted records.** `evid_f094cbe4b47d4048`: stored `needs_review`, effective
`approved_internal` from its one linked review, `source_availability_only`, **not** a finding
candidate. `evid_8151dad609974ea0`: stored `needs_review`, effective **`unreviewed`**, no linked
review, `operational_finding`, the single finding candidate. Strict `EngagementPacket` reported not
valid.

**Reporting bridge from persisted records.** Exactly one internal finding input, citing
`evid_8151dad609974ea0`, referencing `ing_d67b76327aba4add`, `unreviewed`, reliability `low`, with
**no review support from the Phase 94 review**. `evid_f094cbe4b47d4048` excluded as source
availability only. The `AgentTaskRequest` for the existing `initial_report_generation_agent` carried
only the finding-backed ids — the cited evidence and its source. Recommendations empty and blocked;
client-facing false. The existing mock executor returned `permitted`,
`planned_mock_no_execution`, with **no DB write, no LLM call, no AgentNet call, no resolver context,
and no client-facing output**.

**Planner references from the same summaries.** The review reference carried `target_record_ids`
naming only `evid_f094cbe4b47d4048`; evidence references carried only the policy's claim scopes. The
planner returned `planned` with **one** finding slot, for `evid_8151dad609974ea0`, with **no review
support** — agreeing with the packet-view bridge — and no recommendation slot. No report writer was
invoked.

**40 live checks, all passing, zero failures.**

## 7. What this does not establish

- No evidence was produced, no review decision was made, and no record changed.
- Nothing became client-facing, publishable, financially verified, or authoritative.
- The finding remains an **internal draft backed by one unreviewed, low-reliability evidence item**
  in a synthetic internal lab scenario. No real client is described.
- A strict `EngagementPacket` still cannot be assembled from `peak_lab`: `client_intake` is required
  and absent, and the schema has no section for source or review records.
- No cycle-count evidence, inventory accuracy figure, source-of-record authority, review decision,
  or operational recommendation was invented.

## 8. Remaining functional blockers

1. **`claim_scope` has no persisted home.** The path works, but classification enters from the
   caller. A durable fix means either a governed column or a controlled workflow step that records
   it — a schema or writer change, and therefore its own approved phase.
2. **Finding summary text likewise.** Either an approved read of the stored `summary`, or a
   structured stored summary field, is needed before a report can carry claim text from persisted
   state.
3. **Recommendations stay blocked** because no substantive evidence is internally approved, and
   **client-facing output stays blocked** by classification. Both are correct, not defects.
4. **`intake_note_records` is empty in `peak_lab`**, so the strict packet's required `client_intake`
   has no safe source.

## 9. Validation

`make validate` (78 PASS, 0 failures, including Phases 110–113; 75 harness targets), `make db-check`,
`make mysql-parity-static`, `make mysql-collation-audit`, `make writer-enablement-decision-gate`,
`make lab-writer-enablement-decision-gate`, and both production-runtime-connectivity-gate self-tests
were run. Alembic head `014_engagement_classification`; 14 migrations; no migration `015`; 18
controlled Peak tables; 12 writers; production writer enablement false; no standing lab writer
enablement. No Alembic `upgrade`, `downgrade`, or `stamp` was run.

**No secret, DSN, host, port, certificate path, environment value, local credential path, SQL
statement, raw row body, `details_json` body, scenario body, model transcript, or planner dump
appears in this document or anywhere in this repository.**
