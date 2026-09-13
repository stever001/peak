# Phase 109 — Read-Only Lab EngagementPacket Assembly

**Baseline:** `01e5898` — *Exercise Phase 108 narrow reporting*.

## 1. Status

**Read-only lab functionality phase. No writes, no records, no source change.** Internal-only. Not
client-facing, not production evidence, not publication-ready. The engagement is the synthetic
internal lab scenario used since Phase 85; no client, real or invented, is described.

Phase 109 read `peak_lab` **read-only** under the lab read-only verifier role, and ran existing
packet and planner code **offline** against the ids it found. It invoked no writer, created no
record, and changed no schema, model, enum, writer, allowlist, gate, harness, prompt, test, tool,
Makefile, or source file. **No source prototype was added** (§8 says why). One scratch probe and one
scratch check script ran from outside the repository and are not product behaviour.

## 2. Decision

**Phase 109 pursued read-only packet assembly instead of the review row Phase 108 recommended.**

Phase 108 showed reporting can carry one finding, but its input was assembled by hand from docs.
Another review row would not change that. Phase 94 already proved the review writer works. A
review row does not update its evidence row. And, as §5.4 shows, the existing read path cannot
tell which evidence a review is about. A second review would be one more isolated record, not
functionality. The real product question is whether stored records can become a packet a workflow
can consume. This phase answered that question, and what it found changes the order of the next
steps (§9).

## 3. Workflow and packet surface inspected

| Surface | What it is | What it means for assembly |
|---|---|---|
| `schemas/engagement-packet.schema.json` | The `EngagementPacket` contract. Requires `packet_id`, `packet_version`, `created_at`, `engagement_label`, `assessment_stage`, **`client_intake`**; `additionalProperties: false` at the root | The only packet shape defined. It has no section for source records or review records |
| `schemas/evidence-reference.schema.json` | Evidence item: requires `evidence_id`, `evidence_type`, `source_type`, `summary`; `additionalProperties: false` | **No field for review status**, and no field for an authoritative flag |
| `peak/ingestion/packet_mapper.py` | Inbound path: packet → `SourceIngestionDraft` + evidence normalization requests + agent task requests + a **source-ingestion write plan** | Runs the **opposite direction** from what this phase needs. Nothing in the repo turns stored records into a packet |
| `peak/reports/internal_assessment_planner.py` | DB-free planner over caller-supplied record ids (Phase 36, Phase 96 review category) | The closest existing consumer of stored-record ids. Review support is **category-level** |
| `prompts/reporting/draft-initial-assessment-report.prompt.md` | Takes an `EngagementPacket` (plus optional findings). Every finding and risk cites an `evid_` id; recommendations must link to findings | Needs citable evidence ids with their claim boundaries. **Says nothing about the review status of cited evidence** |
| `prompts/evidence/extract-evidence-findings.prompt.md` | Takes a packet whose `evidence_references[]` are populated. Every finding cites an `evid_` id that exists in the packet; thin or single-source evidence lowers confidence | Same need: ids, reliability, and what each item may support |
| `peak/agents/registry.py`, `executor.py`, `mock_llm.py` | Catalog plus an inert executor: `planned_mock_no_execution`, and it reads no record | Unchanged since Phase 108. The executor records intent only, so it has no part in assembly |
| `peak/db/engagement_read_isolation.py` | Phase 57 read-side predicates over engagement classification | **Reusable today** for the posture section of a packet |

## 4. Read-only lab verification

**Access posture, value-free.** The phase used the lab read-only verifier env file, outside the
repository, mode `600`. It was sourced inside a subshell only, and no value was printed. That file
sets the **production-named** read-only variable, the Phase 82/88 naming seam. The ambiguity was
closed **before any connection opened**: the probe parsed the variable in memory and refused to
connect unless the driver was `mysql+pymysql`, the user `peak_lab_verify_ro`, and the database
`peak_lab`, with no production or scenario marker. It also confirmed that no runtime, migration,
scenario, or writer-target variable was set in that shell. The session ran as a **read-only
transaction**. Queries projected **only** ids, statuses, posture flags, JSON key names, and counts,
all computed server-side. **No `summary`, no `details_json` body, and no reasons text was
retrieved.** Output passed through a filter that dropped any URL-shaped line.

| Check | Result |
|---|---|
| Current database / current user | `peak_lab` / `peak_lab_verify_ro` |
| Grants | `SELECT`, `USAGE` only, on `peak_lab` only; no `GRANT OPTION` |
| `peak_lab_scenario` visible to this role | no |
| `alembic_version` | 1 row, `014_engagement_classification` |
| Controlled tables | 18 in models; 19 base tables in the schema (18 + `alembic_version`); no extras |
| **Application rows** | **5** — `engagements` 1, `source_ingestion_records` 1, `evidence_references` 2, `review_records` 1 |
| Every other controlled table | 0 |
| Identity across all five rows | one `client_id`/`owner_id` pair — `99999` / `peak_internal_admin`; one scope — `internal_peak_only` |
| Writes issued | none |

### 4.1 The records

| Record | Value-safe fields read |
|---|---|
| `engagements` `lab_internal_test_001` | client `99999`, owner `peak_internal_admin`, scope `internal_peak_only`, `engagement_category=internal_test`, `real_client_data=false`, `client_accessible=false`, `capsule_publication_authorized=false`, `needs_review`/`active`, label present (not retrieved). Phase 57 predicates: **client-visible false, internal-test true, publication-eligible false** |
| `source_ingestion_records` `ing_d67b76327aba4add` | `source_reference_id=pkt_lab_phase88_scenario_measurement_001`; packet schema `lab_scenario_measurement` `v1`; source type `lab_scenario_measurement`; locator scheme `peak-lab-measurement`; packet hash present; stored `authoritative` / `client_facing_approved` / `capsule_candidate_ready` all false; `needs_review`/`draft`/`active`; `source_phase=phase92`; never updated |
| `evidence_references` `evid_f094cbe4b47d4048` | `other`/`other`, reliability `low`, `collected`, not sensitive, `needs_review`/`draft`/`active`, areas `unspecified`/`unspecified`, source `ing_d67b76327aba4add`, `source_phase=phase93`; summary, title, and observed condition present (not retrieved); never updated |
| `evidence_references` `evid_8151dad609974ea0` | `other`/`other`, reliability `low`, `collected`, not sensitive, **`needs_review`/`draft`/`active`**, areas `inventory`/`on_hand_attribution`, **source `ing_d67b76327aba4add`**, `source_phase=phase107`; summary, title, and observed condition present (not retrieved); never updated |
| `review_records` `rev_70b5da9f14d54488` | **target `evid_f094cbe4b47d4048`**, `subject_record_type=evidence_reference`, `approve_internal`, **`authoritative=false`**, previous status null, new status `approved_internal`, `approved_internal`/`draft`/`active`, `reason` null, 9 reasons lines (count only), `client_facing_approved`/`capsule_candidate_ready` false, source `ing_d67b76327aba4add`, `source_phase=phase94` |

### 4.2 Relationships

| Relationship | Result |
|---|---|
| Both evidence rows → `ing_d67b76327aba4add` | resolves |
| Source, both evidence rows, review → `lab_internal_test_001` | resolves |
| `rev_70b5da9f14d54488` target → `evid_f094cbe4b47d4048` | resolves |
| Reviews targeting `evid_f094cbe4b47d4048` | `rev_70b5da9f14d54488` |
| **Reviews targeting `evid_8151dad609974ea0`** | **none** |
| Reviews targeting `ing_d67b76327aba4add` | none |

**`evid_8151dad609974ea0` remains unreviewed**, confirmed live rather than by documented state. No
row was created by this phase, and `peak_lab` remains at **5 application rows**.

## 5. Minimal packet assembly

Classifications: **DB** = read from a stored field. **Derived** = computed from DB relationships.
**Docs** = available only from committed phase docs. **Missing** = nowhere. **Unsafe** = must not
be inferred.

### 5.1 Section map

| Packet section | Content | Class |
|---|---|---|
| **Engagement identity** | `lab_internal_test_001`, `99999`, `peak_internal_admin`, `internal_peak_only` | DB |
| Engagement classification | `internal_test`; not real client data; not client accessible; capsule publication not authorized | DB |
| Visibility / publication posture | Not client-visible, not publication-eligible | Derived (Phase 57 predicates) |
| Scenario identity (`internal_test_inventory_ops_v1` `v1`) | Names the synthetic scenario | Docs (the source row stores the measurement schema, locator scheme, and hash; the scenario name comes from Phases 85–88) |
| `packet_id` / `packet_version` / `created_at` | Packet envelope | Missing — no stored packet; an assembler would have to mint them |
| `assessment_stage` | `reporting` | Docs (Phases 105/108) |
| **`client_intake`** (schema-required) | Intake id, client profile, stated pain points | Missing from DB (`intake_note_records` = 0 in `peak_lab`); prose only in the Phase 101 brief; **unsafe** to turn that prose into structured `ClientIntake` fields |
| `inventory_system_profile` | Systems, system of record | Missing; **unsafe** — R8 precedence unconfirmed |
| **Source references** | `ing_d67b76327aba4add` with measurement metadata and stored false posture flags | DB |
| Source review posture | Unreviewed | Derived (no review targets it) |
| **Evidence references** | Both rows: id, type, source type, reliability, sensitivity, stored statuses, areas, source link | DB |
| Evidence `summary` (schema-required) | The stored claim text | DB-held, **not retrieved in this phase**; figures used here come from Phase 107 docs |
| Evidence claim boundary | `f094…` supports record existence only; `8151…` supports R1 coverage/readiness only | Docs (also written into stored text, not retrieved) |
| `collected_at` / `collection_method` | — | Missing. `created_at` is record creation, not collection; **unsafe** to relabel. `measurement` was deliberately declined in Phase 106 |
| Evidence `authoritative` | — | Missing (no column); non-authority is enforced at write time only |
| **Review references** | `rev_70b5da9f14d54488` with decision, authority flag, target, statuses | DB |
| **Evidence–review association** | Per target, §5.3 | Derived |
| Finding candidate | One, §6 | DB ids + posture; wording and figures from Docs |
| Unsupported findings | Accuracy, variance, source-of-record truth, R8, root cause, … | Docs; **unsafe** to infer |
| Recommendation posture | Blocked | Derived (no reviewed substantive evidence) + reporting contract rule |
| Client-facing posture | Blocked | **DB-enforced** — classification columns and Phase 57 predicates |
| Capsule / AgentNet posture | Blocked | DB (`capsule_publication_authorized=false`) + Docs |

### 5.2 How `evid_8151dad609974ea0` enters the packet

As one evidence item in two parts, kept separate:

- **Schema-shaped part:** `evidence_id=evid_8151dad609974ea0`, `evidence_type=other`,
  `source_type=other`, `reliability=low`, `sensitive_data_flag=false`,
  `related_object_ids=[ing_d67b76327aba4add]`, and `summary` from the stored row when a later phase
  approves reading it.
- **Assembly sidecar:** `stored_review_status=needs_review`, `output_status=draft`,
  `lifecycle_status=active`, `review_ids=[]`, **`effective_review_posture=unreviewed`**, and
  `claim_scope=coverage_readiness_only`.

**Unreviewed is the default.** An evidence item is `unreviewed` unless a review record targets
**that item's id**. A shared source, engagement, or phase never counts.

### 5.3 How the Phase 94 review enters without mutating anything

The review is carried as its own record and **joined** to its target. It is never copied onto the
evidence row:

| Evidence | Stored `review_status` | Reviews targeting it | Effective posture in packet |
|---|---|---|---|
| `evid_f094cbe4b47d4048` | `needs_review` (unchanged) | `rev_70b5da9f14d54488` — `approve_internal`, `authoritative=false` | `reviewed_internal_non_authoritative` |
| `evid_8151dad609974ea0` | `needs_review` | none | **`unreviewed`** |

The stored status and the effective posture are **two fields, never one**. That way the packet never
claims the evidence row changed, and a reader can see why the two differ. The join key is
`review_records.target_id` = evidence id, with `subject_record_type=evidence_reference` and matching
engagement, client, owner, and scope. `target_id` has no foreign key, so an assembler must report a
target that does not resolve instead of dropping it. Here, every target resolves.

### 5.4 What the existing code does with these ids (offline, scratch)

**Strict schema.** A packet built only from DB-available fields was validated against
`engagement-packet.schema.json`:

| Variant | Result |
|---|---|
| DB fields only | fails: `client_intake` is required |
| `review_status` added to an evidence item | fails: additional property not allowed |
| Top-level review section added | fails: additional property not allowed |
| Review association expressed only as a `validation_notes` string | passes review-wise (still fails on `client_intake`), but free text is not a workflow-consumable association |

**A schema-valid `EngagementPacket` cannot be assembled from `peak_lab` today**, and even a valid
one could not carry review status as data. The practical target is a **packet view**: schema-shaped
evidence items plus sidecar sections for sources, reviews, associations, posture, and missing
fields. A schema extension may come later; it is not needed for the next step, and none was made.

**The existing planner mis-associates the review.** Run with the five ids, the Phase 36 planner
returns `planned` with 7 ready, 1 partial, 3 blocked, and 3 synthesis-only sections, and **two**
finding candidates:

| Candidate | Evidence | Review support the planner attaches |
|---|---|---|
| `fnd_000` | `evid_8151dad609974ea0` | **`rev_70b5da9f14d54488`** — which reviewed a *different* evidence row |
| `fnd_001` | `evid_f094cbe4b47d4048` | `rev_70b5da9f14d54488` |

The planner is explicit that its support is category-level, and it warns about that. The effect is
still concrete: **a consumer of the current plan would present the unreviewed Phase 107 finding as
review-supported.** It also counts the record-existence row as a finding slot, the
presence-versus-sufficiency problem Phase 97 named. This is the best evidence that review semantics
belong in assembly, not in more review rows.

**`packet_mapper` is not the bridge.** Fed a packet-like payload carrying the two evidence ids, it
prepared an ingestion plan with two evidence normalization requests, both reset to `needs_review`,
**and a write plan for a new `source_ingestion_records` row**. It ran with no connection and no
write. Routing stored records back through it would plan a duplicate source registration and erase
review context. Assembly needs its own, read-only direction.

## 6. What reporting can consume

From the assembled view, the reporting contract gets exactly what Phase 108 hand-built, and now
the posture fields come from stored records:

- **One evidence-backed internal finding candidate:** R1 on-hand attribution coverage is incomplete
  in the synthetic lab scenario (`evid_8151dad609974ea0`, source `ing_d67b76327aba4add`). The figures
  (14 of 32 attributable; 7 / 11 / 3 blockers) are taken from the Phase 107 document, not re-read.
- **Effective review posture `unreviewed`**, derived per target, not asserted by hand.
- **Reliability `low`**, from the stored row.
- **Coverage is not accuracy.** The claim scope is coverage/readiness only.
- **Recommendations, quick wins, and risk severity blocked.** No reviewed substantive evidence
  exists, and the contract requires recommendations to link to findings.
- **Client-facing output blocked by the DB**, not just by convention: the engagement is not
  client-visible under the Phase 57 predicates.
- `evid_f094cbe4b47d4048` is carried as reviewed but supports **no finding**, only the statement
  that the source record exists.

The prompt contract can consume this without change, **as long as the sidecar posture is passed
alongside the packet**. The contract does not ask for review status, so a packet that leaves it out
would silently lose it.

## 7. What remains missing

- **An automated assembler.** This phase proved the mapping by hand plus a scratch probe; nothing in
  the repository does it yet.
- **Review-status semantics in code.** The per-target rule in §5.3 is defined here; the planner
  still uses category-level support.
- **A structured `client_intake`** for a schema-valid packet (none in `peak_lab`; unsafe to
  synthesize from prose).
- **Cycle-count or variance evidence.** None exists; inventory accuracy stays unanswered.
- **Source-of-record authority resolution** (R8 precedence unconfirmed).
- **Recommendation support.** Needs reviewed, substantive, sufficient evidence.
- **A client-facing approval path.** None exists, and the engagement is internal-test by classification.
- **Capsule and publication readiness.** Shut.

## 8. Product observations

**Does DB-backed read-only assembly beat doc-only hand assembly?** Yes, in the places Phase 108
flagged as hand-added. Identity, classification, visibility, reliability, stored statuses, source
links, and review association all came from stored records and relationships. The claim wording
and figures still come from docs, and that is the one piece this phase deliberately did not read.

**It also caught something hand assembly and the planner both obscure.** Phase 108's recommended
review would have landed in a read path that already treats the Phase 94 review as supporting the
Phase 107 finding. Assembly done per target makes the gap visible and fixable. Assembly done by
category hides it.

**Why no source prototype in this phase.** The prototype criteria were checked; the blocker was the
**output shape**, not the effort. The strict `EngagementPacket` cannot hold what the DB provides, so
any code first has to settle on a packet view with sidecar sections. And its core rule, per-target
effective review posture, is the product semantic this phase set out to define. Writing both into
source in the same phase that discovered them would lock in an unreviewed design. §5 is now specific
enough to implement directly.

**The smallest source-level implementation**, proposed and not built:

- One pure function, e.g. `assemble_engagement_packet_view(engagement, sources, evidence, reviews)`,
  taking **already-fetched, value-safe summaries** (the §4.1 fields) and returning a dict with:
  `engagement`, `sources`, `evidence` (schema-shaped item + sidecar), `reviews`, `associations`,
  `unresolved_links`, `posture`, and `missing`.
- Rules: per-target association only; `unreviewed` by default; `approve_internal` with
  `authoritative=false` → `reviewed_internal_non_authoritative`; stored and effective status always
  both shown; client-facing and publication posture taken from the Phase 57 predicates and never
  raised; refuse mixed identity or scope; deterministic ordering; `summary` passed through only if
  the caller supplied it.
- No DB connection, env handling, CLI, writer, or live query. Fetching stays a separate read-only
  step.
- One behavioural test over in-memory summaries, asserting on outputs, not doc prose (Phase 99).

**Should review wait?** Yes, until the assembler exists. Then a review of `evid_8151dad609974ea0`
becomes a visible change in the packet (`unreviewed` → `reviewed_internal_non_authoritative`),
not another record nothing reads correctly.

**Should more evidence wait?** Yes. Every added item makes hand assembly slower and the
category-level planner more misleading. The next piece of evidence is worth more once the assembler
exists.

## 9. Recommended next step

**Phase 110 — implement the small read-only packet-view assembler described in §8**, as a pure
function over value-safe fetched summaries, with one behavioural test. Then re-run reporting
through that path.

This comes before reviewing `evid_8151dad609974ea0` and before collecting new evidence, for the
reasons in §8. A per-target correction of the planner's category-level review support is a natural
follow-on, not part of that step. It is recorded here as a warning, and the planner was not
changed. Phase 110 is **not approved by this phase**.

**This supersedes Phase 108's review-first recommendation.** Warnings carried forward: planner review
support must be target-specific; the read-only lab env file still uses a production-named variable;
the prompt-note batch carried since Phases 101, 102, 104, and 108 remains open.

## 10. Stop conditions and non-claims

- **No writes.** No record created, no writer invoked, no DB write; read-only transaction under a
  `SELECT`-only role.
- **No production connection or write. No `peak_lab_scenario` connection.**
- **No row body or scenario row body read or printed** — no summary, `details_json` body, reasons
  text, SQL, env value, DSN, host, port, or local path.
- **No client-facing output** and **no operational recommendation**.
- **No inventory accuracy claim** and **no source-of-record truth claim**.
- **No migration `015`**; head `014_engagement_classification`, 14 migrations, 18 tables, 12 writers.
- **No AgentNet publication** and no capsule readiness.
- **No generated packet, fixture, or extract committed.** The scratch outputs stayed outside the
  repository.

---

**Provenance.** Phase 109 read `peak_lab` read-only, as `peak_lab_verify_ro`, with the env sourced
in a subshell and the target asserted before connecting. It ran the existing planner, packet mapper,
and packet schema offline against the ids it found. **No record was created; no writer was invoked;
no DB write was made; no production or `peak_lab_scenario` connection was made; no row body, secret,
DSN, host, env value, or SQL was printed or committed; no migration `015`; no schema, model, enum,
writer, allowlist, gate, harness, prompt, test, tool, Makefile, or source file changed.** `peak_lab`
remains at **5 application rows**, verified live. `evid_8151dad609974ea0` **remains unreviewed.**
Review status remains a packet and product semantics issue, and the next step should move toward
product functionality, not record-chain ceremony.
