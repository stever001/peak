# Phase 68 — The R2 Evidence Reference Review Decision

**Status:** production-sensitive phase — **one application record written**. Exactly **one
`review_records` row was created**, recording the internal review decision on the Phase 67 **R2
evidence reference**. No evidence reference, no source ingestion record, no Client record, no
additional Engagement, no intake note, no report, and no capsule record.
**Baseline:** `69c7041` — Add Phase 67 first internal test evidence reference
**Alembic head:** unchanged at `014_engagement_classification` (14 migrations, 18 tables, 12
writers) — Phase 68 adds no migration, no model, no writer, and no allowlist pair
**Writer:** [`peak/db/review_writer.py`](../peak/db/review_writer.py) (Phase 22, unchanged)
**Operator utility:** [`tools/create_internal_test_r2_evidence_review_decision.py`](../tools/create_internal_test_r2_evidence_review_decision.py)
**Harness:** [`tests/validate_phase68_r2_evidence_reference_review_decision.py`](../tests/validate_phase68_r2_evidence_reference_review_decision.py)
(`make validate-phase68`, in `make validate`; offline, temp-SQLite only, contacts no production)

---

## 1. What was written

**One review_records row was created for the R2 evidence reference.**

| Field | Value |
| --- | --- |
| stored record id | `rev_de2b6e73f6c94c67` |
| target table / action | `review_records` / `create_review_record` |
| authorization anchor | `internal_test_001` (engagement) |
| reviewed target (`target_id`) | `evid_56437d9b9c764560` — the Phase 67 R2 evidence reference |
| `subject_record_type` | `evidence_reference` |
| `source_reference_id` | `pkt_internal_test_r2_sku_item_master_001` |
| `client_id` / `owner_id` | `99999` / `peak_internal_admin` |
| `authorization_scope` | `internal_peak_only` |
| `decision` | `approve_internal` |
| `authoritative` | `false` |
| `review_status` (new) | `approved_internal` |
| `output_status` / `lifecycle_status` | `draft` / `active` |
| `client_facing_approved` / `capsule_candidate_ready` | `false` / `false` |
| reviewer / reviewer role | `peak_internal_admin` / `internal_admin` |
| `idempotency_key` | `phase68_internal_test_r2_evidence_review_001` |

## 2. Why `review_records`, and why no field was overloaded

The Phase 22 review writer keeps apart the two things this review needs kept apart:

- the **authorization anchor** — `request.subject`, which the writer *requires* to be the
  `engagement`; and
- the **reviewed target** — `draft.subject_record_id` / `draft.subject_record_type`, stored as
  `target_id` and documented in the model as the column that "disambiguates the reviewed target".

`draft.source_reference_id` is the honest home for the reviewed packet reference, and
`draft.reasons` is a free findings list the writer persists into `details_json` — so the limits are
stored **as findings**, not squeezed into a field meant for something else. **Phase 61 used this
same shape** with `subject_record_type='intake_note'`, and **Phase 66** with
`'source_ingestion_record'`.

### Why `subject_record_type='evidence_reference'`

The reviewed target is a **stored `evidence_references` row**, so the value is derived from that
table's name — the same convention Phase 61 and Phase 66 used. Some older harness fixtures
(Phases 15/16/17/22) label an `evid_` target `normalized_evidence_record`; that name belongs to the
Phase 14 **in-memory** normalization output, which is never stored, so using it here would point at
the wrong artifact class. `subject_record_type` is a free `GovernedString(48)` with no closed
vocabulary, so this is a deliberate, documented naming choice rather than a constraint.

`approve_internal` means **internal reliance only and never client-facing approval**. The writer
refuses `client_facing_approve`, `verify_financial_impact`, and `publish_capsule` at the vocabulary
level, and forces `client_facing_approved=false` and `capsule_candidate_ready=false`.

**`authoritative` was left `false`** deliberately. The writer would permit `true` for
`approve_internal`, but the reviewed evidence carries `reliability='low'` and rests on a source
whose upstream map (R8) is itself unreviewed, so nothing downstream should treat it as settled.
**The evidence remains low confidence and non-authoritative.**

## 3. What the review found

Findings were recorded as concise sanitized entries in the row's `reasons` list — structural counts,
posture flags, and named gaps. **No artifact body text, no field values, no item or SKU values, no
quantities, and no location identifiers were stored.**

- **Chain.** Phase 66 approved the R2 source ingestion record internally for exactly this narrow
  downstream evidence use, and Phase 67 created the evidence reference inside that scope.
- **Scope check.** The evidence reference claims item-master source availability and data readiness
  only — it does not exceed the scope Phase 66 approved.
- **Structure.** The evidence rests on an artifact describing 10 item-master fields (6 required, 4
  optional), each carrying an interpretation note and a named risk. The artifact is a field-level
  export *description*, not an export; it carries no rows, so **no measured quantity is in
  evidence**.
- **Confidence.** `reliability` remains `low`, and `evidence_references` carries no `authoritative`
  column, so nothing downstream can treat the evidence as settled.
- **Posture check.** The reviewed evidence reference is `needs_review` / `draft`, with
  `client_facing_approved=false` and `capsule_candidate_ready=false`.
- **Gaps.** Unit-of-measure posture unconfirmed; item-status posture unconfirmed; 6
  duplicate/normalization risks remain future review topics; whether R1 draws item identifiers from
  the same identifier domain is unconfirmed.
- **Provenance note.** `evidence_references` has no typed related-object column, so the source
  ingestion and supporting review links live in the evidence record's own text. Machine-joinable
  provenance remains a future consideration, not a blocker here.

## 4. What this decision authorizes — and what it does not

**Authorized:** the evidence reference is internally approved for use in a **future internal
assessment finding about item-master source availability and data readiness**, as a separately
approved phase.

**Not authorized, and recorded as such on the row:**

- **No inventory accuracy conclusion.** The evidence describes an item master, not measured on-hand
  quantity. **No inventory accuracy conclusion was made in this phase.**
- **No SKU or location quantity reliability claim.**
- **R1 location claims are not validated.** That dimension remains **provisional** pending **R9**.
- **R8 authority precedence is not confirmed.** R8 remains `needs_review` / `draft` /
  `authoritative=false`, so no measure may yet be attributed to a system of record.
- **R3–R7 remain deferred** behind their unresolved R8 blockers.
- **No report drafting, no capsule publication, no client-facing output.**
- **No AgentNet publication.** The public resolver is live, and **publication remains
  unauthorized** — that the resolver is a real production target is why the gate stays shut rather
  than relaxed.

`ReviewRecordDraft` has no `publication_allowed` field to set false. The prohibition is structural
instead, and stronger: the writer refuses `publish_capsule` at the vocabulary level and forces the
client-facing and capsule flags to false. The limits are additionally written into the row's own
findings text.

## 5. The reviewed record was not modified

A review **records a decision about** a target; it does not mutate it. The Phase 67 evidence
reference remains `needs_review` / `draft` with `reliability='low'` — the review writer has no
`UPDATE` path at all, and the harness asserts the reviewed row is unchanged after the write.

## 6. The artifact body was never read

The Phase 68 operator **opens no file and computes no hash** — it reads no artifact at all. The R2
artifact body remains outside the repository, uncommitted, unprinted, and absent from the database.
The structural findings restate what Phase 66 and Phase 67 already recorded.

## 7. What Phase 68 did not do

- **No evidence reference**, no source ingestion record, no Client, no additional Engagement, no
  intake note, no report draft, no review packet, no capsule candidate, no client-facing output.
- **No AgentNet publication.**
- **No migration, no migration 015, no model, no writer, no allowlist pair.**
- **No `UPDATE`, `DELETE`, manual SQL, cleanup path, app scan, or app row count** beyond the
  writer's own stored-engagement load and idempotency lookup.

## 8. Idempotency and the no-overwrite rule

The record carries its own Phase 68 idempotency key on the owner / client / engagement / key
boundary. An exact replay returns the existing row unmodified; a **changed payload fingerprint under
the same key is refused as an `idempotency_conflict`** — never an overwrite. The operator has no
`UPDATE`, `DELETE`, or cleanup path.

## 9. Next steps, still gated

**Phase 69 should likely collect R9 — the location/bin naming model** — which is what unblocks R1's
location dimension. A future internal assessment finding about item-master source availability and
data readiness is the other step this decision supports. Both remain **separately approved phases**,
as do R8 review, R3–R7, report drafting, capsule publication, and AgentNet resolver publication.

## 10. What Phase 69 did with this decision's next step

**Phase 69 collected R9** — the location/bin naming model §9 named as the likely next step — as one
`source_ingestion_records` row (`ing_64b2e2648ac1402b`) through the unchanged Phase 24 writer, under
this same `internal_test_001` / `internal_peak_only` anchor. **Metadata, a SHA-256 `packet_hash`,
and the logical reference** `internal-test-artifact://phase69/r9-location-bin-naming-model-v1` were
persisted; the **artifact body lives outside the repository**.

**R9 was collected to unblock a future R1 location-dimension review.** It **does not validate
inventory quantities**, **does not make R1 evidence-ready by itself**, and **must be reviewed before
use in evidence references** — it landed `needs_review` / `draft` / `authoritative=false`.

Phase 69 changed nothing this decision established. The R2 evidence reference and this review record
are untouched — the source ingestion writer has no `UPDATE` path. **No evidence reference, no review
record**, no report, no capsule, no client-facing output, and no AgentNet publication record was
created. **R8 remains provisional** (`needs_review` / `draft` / `authoritative=false`, precedence
unconfirmed), **R3–R7 remain deferred**, and the AgentNet resolver is live but **publication remains
gated and unauthorized**. The other step this decision supports — a future internal assessment
finding about item-master source availability and data readiness — **remains a separately approved
phase**. See
[`PHASE69_R9_LOCATION_BIN_MODEL_SOURCE_INGESTION.md`](PHASE69_R9_LOCATION_BIN_MODEL_SOURCE_INGESTION.md).
