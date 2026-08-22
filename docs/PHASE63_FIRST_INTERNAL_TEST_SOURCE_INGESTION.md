# Phase 63 — The First Internal Test Source Ingestion Record

**Status:** production-sensitive phase — **one application record written**. Exactly **one
`source_ingestion_records` row was created** in production, registering the R8 system-of-record and
data-export map artifact. No Client record, no additional Engagement, no intake note, no review
record, **no evidence reference**, no report, and no capsule record.
**Baseline:** `da75af6` — Add Phase 62 internal test source evidence plan
**Alembic head:** unchanged at `014_engagement_classification` (14 migrations, 18 tables, 12
writers) — Phase 63 adds no migration, no model, no writer, and no allowlist pair
**Writer:** [`peak/db/source_ingestion_writer.py`](../peak/db/source_ingestion_writer.py)
(Phase 24, unchanged)
**Operator utility:** [`tools/create_internal_test_source_ingestion_record.py`](../tools/create_internal_test_source_ingestion_record.py)
**Harness:** [`tests/validate_phase63_first_internal_test_source_ingestion.py`](../tests/validate_phase63_first_internal_test_source_ingestion.py)
(`make validate-phase63`, in `make validate`; offline, temp-SQLite only, contacts no production)

---

## 1. What was written

**One R8 system-of-record and data-export map source ingestion record was created.**

| Field | Value |
| --- | --- |
| stored record id | `ing_4fb70519cbf84401` |
| target table / action | `source_ingestion_records` / `create_source_ingestion_record` |
| authorization anchor | `internal_test_001` (engagement) |
| `client_id` / `owner_id` | `99999` / `peak_internal_admin` |
| `authorization_scope` | `internal_peak_only` |
| `source_reference_id` | `pkt_internal_test_r8_system_record_map_001` |
| `packet_schema_name` / `version` | `engagement_packet` / `v0` |
| `packet_source_type` | `internal_test_export` |
| `packet_location_reference` | `internal-test-artifact://phase63/r8-system-of-record-data-export-map-v1` |
| `packet_hash` | SHA-256 of the external artifact |
| `review_status` / `output_status` | `needs_review` / `draft` |
| `authoritative` | `false` |
| `client_facing_approved` / `capsule_candidate_ready` | `false` / `false` |
| `idempotency_key` | `phase63_internal_test_source_ingestion_r8_001` |

## 2. Why R8 first

Phase 62 ranked the system-of-record and data-export map ahead of R1–R7 because it **determines
whether the other requests are fulfillable at all** — it names the systems, fixes the authority
precedence rule, and enumerates which exports exist, in what format, at what cadence, and owned by
whom. Registering it first means the remaining requests can be scoped against something real
instead of assumed.

## 3. The artifact body lives outside the repository

The R8 artifact is a durable internal-test file held **outside the repository**, under the approved
internal-test artifact directory. It is **not committed**, not printed, and not readable from the
repository. The operator utility opens it in binary solely to compute its byte length and SHA-256;
its bytes are never decoded, logged, or placed on the draft.

**Only metadata was persisted** — the packet reference id, schema name and version, source type, a
**logical** location reference, and the `packet_hash`. No raw artifact payload, no export rows, no
document text, and no filesystem path reached the database. The stored location reference is
deliberately logical (`internal-test-artifact://…`) so the row leaks no operator home directory or
machine layout. The writer independently refuses any draft carrying `packet_payload`,
`raw_packet_content`, `raw_content`, `payload`, or a secret-named attribute, so the metadata-only
rule is enforced on both sides of the boundary.

**The artifact is Peak-authored internal test data, not a client-supplied export.** That is recorded
on the row's provenance notes so nothing downstream can later mistake it for client-provided
evidence. It holds **no real client data**; the parent engagement is `internal_test`, excluded from
client-facing reads by the Phase 57 isolation primitive.

## 4. Why `source_ingestion_records` was the honest fit

Phase 62 concluded that this writer is the only allowlisted, writer-backed path that **registers an
inbound artifact against an engagement**, and that it is metadata-only by contract. That is exactly
the claim R8 needs to make: *this artifact exists and is registered under this engagement* — with no
claim about its contents.

The write is anchored the same way as Phases 20–22 and 59–61: `request.subject` must be the
`engagement`, and at write time the writer loads the stored `Engagement` row and requires
`request.authorization_scope == engagement.authorization_scope`. Identity matching is necessary but
not sufficient.

**Phase 62's precondition was honoured.** That plan recorded that a row pointing at a nonexistent
packet would be dishonest. No internal_test artifact existed at the start of this phase, so the
durable R8 artifact was created outside the repository **first**, and only then was its metadata
registered. The operator utility refuses to run when the artifact is missing, refuses any path
inside the repository working tree, and refuses any path other than the approved artifact.

## 5. What was not written

- **No evidence reference.** `evidence_references` remains empty for this chain. Its columns assert
  `evidence_status`, `reliability`, and characterization that presuppose a registered source, so
  **evidence_references still come after source ingestion**, never before it.
- **No Client record** — `clients` remains never-writable.
- **No additional Engagement** — the Phase 59 anchor was loaded as the authorization subject and
  left untouched.
- **No intake note and no review record.**
- **No report record**, no review packet, no agent run, and no task queue record.
- **No capsule** and no AgentNet publication.
- **No client-facing output**, approval, or financial verification.
- **No `UPDATE`, `DELETE`, manual SQL, cleanup, or stamp.**
- **No app table scan, count, or probe** beyond the writer's own stored-engagement load and its
  idempotency lookup.

## 6. What this unlocks

**This closes the first Phase 62 precondition for later R1–R7 evidence collection.** R8 was the
request that scoped the others; with the map registered, R1–R7 can be requested against named
systems and enumerated exports rather than against assumptions.

It does **not** authorize the next step by itself. Report drafting, capsule candidacy, and
publication remain unauthorized, and evidence normalization and `evidence_references` remain a
separately approved later phase. The record is `needs_review` / `draft` and `authoritative=false`:
nothing downstream should yet treat it as settled.

## 7. Verification posture

The read-only verifier was run **before and after** the write and reported
`verified_safe_no_remediation_required` both times: production head
`014_engagement_classification`, 212 governed columns all deterministic, 11 idempotency boundaries
none at risk, `schema_mutation_made=False`, `data_write_made=False`. The runtime connectivity gate
reported `required_grants_present=True`, `excess_grants_present=False`,
`global_privileges_present=False`, `grant_option_present=False`, and `app_table_read_made=False`.

Replay behaviour is covered offline against temporary SQLite: an identical payload under the same
idempotency key returns `idempotent_replay` without a second write, and a **changed artifact hash**
under the same key is denied as `idempotency_conflict` with the existing record left untouched.

---

## 8. Phase 64 — the map becomes a collection plan

**Phase 63 registered R8; Phase 64 defines the R1–R7 artifact collection** it scopes. Each request
now has an artifact type, minimum expected fields or document sections, an external filename, a
logical `internal-test-artifact://phase65/…` reference, a `packet_reference_id`, schema and source
type, and a SHA-256 hash requirement. **Phase 64 creates no production record.**

Read as a work-list, this record's map is not uniform: **R2 is the only request it shows as
unblocked**, while R1 is blocked on the unconfirmed location model and R3–R7 each carry an open
question. That is the map doing its job — it was registered first precisely so the other requests
could be scoped against something real.

**Phase 65 should create the external artifact(s) and register `source_ingestion_records`, not
`evidence_references` yet** — recommended batch R2 then R1. This record staying `needs_review` /
`draft` / `authoritative=false` does not block collection, but its provisional authority rule does
block *attribution*: no reliability may be asserted until it is confirmed. **Artifact bodies remain
outside the repository, and capsule publication remains unauthorized despite the live AgentNet
resolver.** See
[`PHASE64_INTERNAL_TEST_R1_R7_SOURCE_ARTIFACT_COLLECTION_PLAN.md`](PHASE64_INTERNAL_TEST_R1_R7_SOURCE_ARTIFACT_COLLECTION_PLAN.md).

---

## What followed in Phase 65

**Phase 65 registered the next two artifacts: R2 (SKU/item master export) first, then R1 (current
inventory by SKU and location)** — two more `source_ingestion_records` rows through this same
unchanged Phase 24 writer, under this same `internal_test_001` anchor. R2 went first because this
R8 map records it as the only unblocked request and because it is the interpretive key for R1.

**R8 remains `needs_review` / `draft` / `authoritative=false`.** Nothing in Phase 65 treated the map
as settled: its location/bin model and its authority precedence rule are still unconfirmed, which is
why **R1's location dimension was registered as explicitly provisional** and why **no evidence
reference was created yet**. R8 review remains a precondition for attribution, not for collection.

Artifact bodies still live outside the repository; only metadata, logical
`internal-test-artifact://phase65/…` references, and SHA-256 hashes were persisted. **R3–R7 remain
deferred**, and **AgentNet resolver publication remains unauthorized** despite the live public
resolver. See [`PHASE65_R1_R2_INTERNAL_TEST_SOURCE_INGESTION.md`](PHASE65_R1_R2_INTERNAL_TEST_SOURCE_INGESTION.md).
