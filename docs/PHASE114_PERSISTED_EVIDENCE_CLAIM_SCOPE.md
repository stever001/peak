# Phase 114 — Persisted Evidence Claim Scope

**Baseline:** `1ab7122` — *Add Phase 113 persisted-state reporting path*.

## 1. Status

**Small product-functionality phase. No database access, no migration, no new writer.**
`claim_scope` now has a **governed persisted home**: the Phase 21 controlled evidence writer records
it on new `evidence_references` rows, and the Phase 113 read-only fetch reads it back. The
persisted-state reporting path therefore no longer needs caller-supplied claim classification for
evidence written from here on.

This phase solves `claim_scope` only. Finding-summary persistence remains **intentionally deferred**.

## 2. Where it is persisted, and why there

`claim_scope` is stored as **one governed key in `evidence_references.details_json`**, written by the
existing Phase 21 controlled writer alongside the structured fields it already owns
(`operational_area`, `inventory_process_area`, `source_reference_id`, …).

**No migration `015` was created and none is needed.** The writer already owns `details_json` and
builds it as an explicit literal field map, the value is validated against a closed vocabulary before
it is written, the Phase 113 reader extracts it server-side as one explicitly whitelisted key, and
rows written before this phase remain valid and readable without it.

`schemas/evidence-reference.schema.json` is unchanged: `claim_scope` belongs to the packet view's
sidecar, never to the strict schema-shaped evidence item.

## 3. Vocabulary

A **closed** vocabulary, declared in `peak/evidence/persistence_contracts.py` as
`ALLOWED_CLAIM_SCOPES`:

- `operational_finding`
- `source_availability_only`

Absent (`None`) is also valid and grants nothing. Any other value is **denied at write time** by the
controlled writer (`invalid_claim_scope`) rather than stored. No further categories were invented.

The claim scope joins the writer's payload fingerprint **only when present**, so a payload carrying no
scope fingerprints exactly as it did before the field existed and existing rows stay
replay-comparable.

## 4. How it is read and applied

| Situation | Behaviour |
|---|---|
| Row carries a valid persisted `claim_scope` | **Authoritative.** The caller policy is not consulted for that row and cannot override it |
| Row carries an unrecognised persisted value | **Refused**, with a recorded reason; the value is stripped and never reaches the view |
| Row carries no `claim_scope` (legacy) | Falls back to `ClaimScopePolicy`, which is now a **legacy fallback only** |
| No persisted scope and no policy | **No scope.** It is never guessed, and it cannot silently become an `operational_finding` |
| Scope is `operational_finding` but both persisted areas are unspecified | **Refused**, from either source |

`operational_area` and `inventory_process_area` remain exactly what Phase 113 made them: **refusal
guards, not classifiers.** They can refuse an operational-finding claim; naming an area never grants
one.

## 5. The existing Phase 107 evidence row

`evid_8151dad609974ea0` **remains a legacy row with no persisted `claim_scope`.** The field did not
exist when it was written, and the writer builds `details_json` as an explicit literal map, so the
key cannot be present. It was **not mutated**, no duplicate evidence row was created, and no database
was contacted in this phase.

**No mechanism to give it one exists today.** Every controlled writer is create-only; the Phase 21
evidence writer hard-requires `requested_action == "create_draft"`, and while
`update_review_status` / `update_lifecycle_status` / `mark_superseded` appear in the allowlist
vocabulary, **no writer implements any of them** and the lab enablement gate's only evidence pair is
`evidence_references/create_draft`. Until that changes, the Phase 107 row keeps reaching the
reporting path through the `ClaimScopePolicy` legacy fallback.

**Recommended next product step (not approved by this phase):** a narrow, governed
`evidence_references/update_claim_scope` writer — one field, closed vocabulary, review-gated,
idempotent, refusing every other column. That is also the mechanism a real engagement needs whenever
classification is decided after capture.

## 6. What is unchanged

- **Every controlled writer remains create-only.** This phase adds one validated field to the row the
  evidence writer already creates; it adds no `UPDATE`, `DELETE`, or merge. The unconditional
  create-only regression check still passes for all 12 writers.
- **Recommendations and client-facing output remain blocked** — no substantive evidence is internally
  approved, and classification still blocks client-facing output.
- **Finding summary text is still not persisted or read**, so the strict `EngagementPacket` remains
  insufficient. Deferred deliberately.
- No migration, model, enum, table, allowlist, gate, prompt, schema, tool, or Makefile change.

## 7. Proof

The existing Phase 113 harness was extended rather than a new one added:
`tests/validate_phase113_persisted_state_reporting_path.py`, **58 checks, passing** (was 49). It
proves that persisted `operational_finding` becomes the finding candidate **with no caller policy**,
that persisted `source_availability_only` backs no finding, that an unrecognised persisted scope is
refused, that a missing scope stays non-finding, that a legacy row still accepts the policy, that the
policy cannot override a persisted scope, that the Phase 94 review still supports no finding, and
that recommendations and client-facing output stay blocked.

## 8. Expected transient validation state

While `peak/db/evidence_writer.py` is uncommitted, four historical harnesses fail:

| Harness | Check |
|---|---|
| `validate_phase54_engagement_authorization_anchor_writer.py` | no controlled writer other than the anchor writer was modified |
| `validate_phase57_internal_test_read_isolation.py` | no controlled writer's code was modified |
| `validate_phase67_first_internal_test_evidence_reference.py` | no controlled writer was modified by this phase |
| `validate_phase68_r2_evidence_reference_review_decision.py` | no controlled writer was modified by this phase |

Each is an **authoring-time working-tree freeze** (`git diff … HEAD`) asserted by an earlier phase
about its own tree; each fires on any uncommitted writer edit by any later phase and **self-resolves
once the change is committed**. They were deliberately **not modified**. The substantive invariant
they exist to protect — every writer stays create-only — is asserted unconditionally elsewhere and
passes.
