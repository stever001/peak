# Phase 53 — Authorized Engagement / Intake Write Path Planning

**Status:** planning phase. **Decision: NO production write, NO writer enablement, NO synthetic
smoke write, NO engagement record creation, NO intake note creation. PLAN ONLY.**
No writer was enabled or invoked; no production data was written; no application row was read,
counted, or probed; no database was contacted.
**Baseline commit:** `6736fe07ef0492a5d2c90a1f056eae00854eb2f4` — *Clarify Phase 50 runtime gate
driver failures*
**Alembic head:** unchanged at `013_governed_identifier_collation_policy` (13 migrations, 18 tables)
**Harness:** [`tests/validate_phase53_authorized_engagement_intake_path.py`](../tests/validate_phase53_authorized_engagement_intake_path.py)
(`make validate-phase53`, included in `make validate`)
**Related:** [`PHASE48_PRODUCTION_RUNTIME_READINESS_GATE.md`](PHASE48_PRODUCTION_RUNTIME_READINESS_GATE.md),
[`PHASE49_RUNTIME_DATABASE_URL_SEPARATION.md`](PHASE49_RUNTIME_DATABASE_URL_SEPARATION.md),
[`PHASE50_CONTROLLED_RUNTIME_CONNECTIVITY_GATE.md`](PHASE50_CONTROLLED_RUNTIME_CONNECTIVITY_GATE.md),
[`PHASE51_WRITER_ENABLEMENT_DECISION_GATE.md`](PHASE51_WRITER_ENABLEMENT_DECISION_GATE.md),
[`INTAKE_NOTE_CONTROLLED_WRITER.md`](INTAKE_NOTE_CONTROLLED_WRITER.md),
[`CONTROLLED_WRITE_ALLOWLIST.md`](CONTROLLED_WRITE_ALLOWLIST.md)

---

## 1. Purpose

Phase 51 recorded *that* nothing should be written yet, and named waiting for authorized engagement
data as the recommended path. It did not establish what "waiting for authorized engagement data"
actually requires in this codebase.

Phase 53 answers that by reading source only. It plans the first authorized engagement/intake write
path and **executes no part of it**. Nothing here authorizes a write; this document is a map, not a
permission.

## 2. Phase 53 decision

| Field | Value |
| --- | --- |
| production write | **not performed, not authorized** |
| writer enablement | **not performed, not authorized** |
| synthetic smoke write | **not performed, not authorized** |
| engagement record creation | **not performed, not authorized** |
| intake note creation | **not performed, not authorized** |
| schema change / migration | **none; no migration 014** |
| database contacted | **no** |
| application rows read / counted / probed | **no** |

## 3. The required authorization anchor

**The authorization anchor is a stored `Engagement` row whose `authorization_scope` is populated.**

Every controlled writer in the repository resolves its authority from that row at write time. The
writer does not trust the caller-supplied scope: it loads the stored `Engagement` and requires
`request.authorization_scope == engagement.authorization_scope`. Identity matching (owner, client,
engagement) is necessary but **not sufficient** — a scope mismatch is denied even when every
identity matches, and both a missing stored scope and a missing request scope are denied.

Consequence: **no controlled write of any kind is possible before an authorized `Engagement` row
exists in the database.** That single row is the gate in front of the whole writer surface, not just
in front of intake notes.

## 4. Source inspection findings

### 4.1 Engagement model / table — **exists**

`Engagement` is declared in `peak/db/models.py` with `__tablename__ = "engagements"`, created by
migration `001_initial`, and is one of the 18 governed tables. It carries the governance/audit
column set including `authorization_scope` and `lifecycle_status`. **The schema side of the anchor
is already in place; nothing needs to be added to the schema.**

### 4.2 Controlled Engagement writer — **does not exist**

There is no `Engagement` writer in `peak/db/`. No controlled writer targets the `engagements` table,
and no `TARGET_TABLE` constant names it. Further, the write allowlist actively forbids it:

- `engagements` is listed in `PROHIBITED_TABLES` in `peak/persistence/allowlist.py`, alongside
  `clients`, described there as an identity/root record "not written through this generic path";
- `ALLOWED_ACTIONS` contains no engagement-creating action.

So the anchor is blocked twice: there is no code path, and the governance allowlist refuses the
table. **This is a deliberate code and governance block, not a privilege block** — the runtime
credential's `INSERT` is schema-wide, so the absence of a writer is what actually prevents an
engagement row from being created. That is worth stating plainly: the safety here comes from the
allowlist and the missing writer, and both must stay intact.

### 4.3 Intake note writer — **exists**

`peak/db/intake_note_writer.py` (Phase 34) is the controlled writer for `intake_note_records`. It is
create-only: it inserts exactly one row and performs no `UPDATE` and no `DELETE`. It targets table
`intake_note_records` with action `create_intake_note_record`; both are on the allowlist.

### 4.4 The intake writer requires the stored Engagement authorization — **confirmed**

The intake note writer loads the stored `Engagement` by the request's subject record id and denies
the write outright when it is absent (`missing_subject`), when the stored scope is blank
(`missing_stored_scope`), when the request scope differs from the stored scope
(`stored_scope_mismatch`), when stored owner/client/engagement identity disagrees with the request
(`identity_mismatch`), or when the stored engagement's lifecycle is `revoked`, `archived`, or
`deleted_reference_only` (`subject_lifecycle_blocked`).

**The first intake note write therefore cannot be performed without an existing stored `Engagement`
anchor.** There is no bypass, no override flag, and no self-anchoring path.

### 4.5 Preconditions the intake writer enforces

| Precondition | Enforced |
| --- | --- |
| `owner_id`, `client_id`, `engagement_id` present on the request | yes |
| `requested_by`, `requester_role` present | yes |
| `authorization_scope` present on the request | yes |
| draft identity fields match the request identity fields | yes |
| draft `authorization_scope` matches the request `authorization_scope` | yes |
| subject type is `engagement` and the subject record id is present | yes |
| stored `Engagement.authorization_scope` equals the request scope | yes — the decisive check |
| stored engagement lifecycle not `revoked` / `archived` / `deleted_reference_only` | yes |
| `idempotency_key` present, a string, at most 128 characters | yes |
| `payload_fingerprint` computed over identity + payload (note body hashed, never stored twice) | yes |
| stored row forced to `review_status=needs_review`, `lifecycle_status=draft`, all approval/publication/execution flags false, `requires_human_review=true` | yes |

### 4.6 Universality of the anchor

All eleven controlled writers load the stored `Engagement` the same way. Nine of them depend on the
engagement anchor **only**; two — the internal report review packet writer and the packet decision
writer — additionally require a stored parent draft or packet. That ordering is what makes the
intake note writer the cheapest genuinely-useful first write.

### 4.7 UPDATE / DELETE requirement — **none**

No part of the planned first write path requires `UPDATE` or `DELETE`. The writers are create-only.

### 4.8 Runtime privileges — **`SELECT` + `INSERT` remain sufficient**

The planned path needs `SELECT` (load the stored engagement, check idempotency, read the row back)
and `INSERT` (one row). The Phase 48/50 runtime credential holds exactly `SELECT` + `INSERT`, so
**no privilege change is required for the planned first write path.**

## 5. Recommended first real operational path

1. An authorized `Engagement` row exists, with a real `authorization_scope`, created under explicit
   approval with exact authorized values known in advance.
2. The read-only production verifier and the Phase 50 runtime connectivity gate are re-run and pass.
3. The Phase 51 decision gate is re-run and a write-authorizing path is explicitly chosen.
4. The **intake note writer** performs the first real write, anchored to that engagement.

The intake note writer is the recommended first real operational writer because it depends on the
engagement anchor alone, requires no agent execution, no LLM, no AgentNet, no resolver, no network,
and no prior stored artifact, and because a genuine intake note is real work rather than a synthetic
record. Source inspection surfaced no writer that is safer on those criteria.

## 6. Recommended next phase

Source inspection resolved the conditional: **no controlled Engagement writer exists.** Therefore:

> **Phase 54 should add a create-only controlled Engagement authorization anchor writer** — and
> nothing else.

That phase must, at minimum:

- add a narrow, create-only writer for `engagements` that inserts exactly one row and has no
  `UPDATE` and no `DELETE` path;
- pass an explicit governance gate to move `engagements` off `PROHIBITED_TABLES` and add the single
  corresponding create action to the allowlist — or, if that boundary is to be preserved, route the
  anchor through an explicitly separate identity/root writer path documented as such;
- carry its own idempotency boundary and review-gated defaults, consistent with the existing writers;
- **create no engagement record.** Adding the writer and running it are two different phases.

Had an Engagement writer existed, the recommendation would instead have been that Phase 54 create
the first authorized engagement record — and only after explicit approval and once the exact
authorized values are known. It does not exist, so that is not this recommendation.

## 7. Required pre-write decision fields for any future production write

A future write phase must name every one of these **before** the write, not after:

| Field | Must be named |
| --- | --- |
| writer name | the exact writer to be invoked |
| target table | the one table the row lands in |
| action allowlist pair | the `(table, action)` pair, since the allowlist is per-action |
| `owner_id` source | where the owner identity comes from |
| `client_id` source | where the client identity comes from |
| `engagement_id` source | where the engagement identity comes from |
| `authorization_scope` source | and that it matches the stored engagement's scope |
| approval authority | who authorized it, and as what role |
| idempotency key pattern | the key is unique per `(owner_id, client_id, engagement_id, idempotency_key)` and case-sensitive since Phase 44; an ad-hoc key cannot be replayed safely |
| payload fingerprint behavior | same key + same fingerprint replays; same key + different fingerprint conflicts and writes nothing |
| cleanup / retention posture | decided before the write; see §8 |
| record classification | real client, internal/administrative, or synthetic — stated explicitly |

## 8. Synthetic smoke writing stays disallowed, and runtime cannot clean up

**Synthetic production smoke-writing remains disallowed** unless separately and explicitly approved.
It is not implied by this plan, by a green connectivity gate, or by a future Engagement writer.

**The runtime credential holds no `DELETE`.** A synthetic or administrative record written by
runtime **cannot be removed by runtime**. Removing it would require the migration credential — a
separate approval, a separate risk, and a credential that can also change schema.

So the default posture for any synthetic or administrative record is **durable / no-cleanup**: it
remains in the governed audit history permanently unless someone later takes a deliberate,
separately approved action to remove it. If such a write is ever approved, it must be approved
either as a durable no-cleanup administrative record with that permanence understood up front, or
with an explicit cleanup plan agreed **before** the write. The cleanup posture is part of the
authorization decision, never a follow-up task.

## 9. Standing decisions preserved

- **Phase 50 runtime connectivity is prerequisite evidence, not write permission.** A passing
  connectivity gate says the plumbing and privileges are correct. It does not say anything ought to
  be written, or who authorized writing it.
- **The Phase 51 no-write / no-enablement decision remains in force, unchanged.** Phase 53 records a
  plan; it flips no field in the Phase 51 decision record.
- **The first production write remains deferred.**

## 10. What this phase does not do

- **It enables no writers** and invokes none.
- **It creates no engagement record and no intake note record.**
- **It creates no synthetic smoke record.**
- **It writes no production data**, mutates no schema, and runs no migration.
- **It reads, counts, and probes no application table row.**
- **It adds no model, table, writer, allowlist pair, or generic SQL/CRUD path**, and adds no
  migration 014.
- **It contacts no database at all**, and reads no environment variable.

## 11. Security confirmations

- **No DSNs, hosts, usernames, passwords, tokens, certificate paths, database names, connection
  URLs, environment values, raw grant lines, row values, client data, pseudo-client data, or example
  records** are recorded in this document or added to source or tests.
- No `~/.peak` operator credential file was sourced, read, catted, grepped, copied, or displayed;
  `.env` was not read; no secret store was searched.
- The migration credential was not sourced or used, and no production migration was run.
- `make validate` stays offline and credential-free; the live gates remain opt-in.

---

## 12. Phase 54 update — the recommended next phase was done (still no record created)

Phase 54 implemented §6's recommendation: it added a **create-only controlled Engagement
authorization anchor writer** and **created no engagement record**. The findings recorded above
were accurate when written; two of them have deliberately changed as a result, and are restated
here so this document does not misdescribe the code:

- **§4.2 is now historical.** A controlled Engagement writer **does exist** —
  `peak/db/engagement_authorization_anchor_writer.py`, targeting
  `engagements` / `create_engagement_authorization_anchor`. It is the only writer that may reach
  the table.
- **`engagements` still sits on `PROHIBITED_TABLES`.** Phase 54 did *not* remove it. The anchor
  writer travels a separate one-pair gate (`ALLOWED_ANCHOR_CREATION_PAIRS`), so the generic path
  still refuses the table and generic Engagement CRUD remains impossible. `clients` remains
  prohibited by every path.
- **Everything else in this document stands.** The authorization anchor is still a stored
  `Engagement` row with a populated `authorization_scope`; the intake note writer still requires
  it; the intake note writer is still the recommended first real operational writer; and
  `SELECT` + `INSERT` is still sufficient.

**No production write has occurred.** The Phase 51 no-write / no-enablement decision remains in
force, Phase 50 connectivity remains prerequisite evidence rather than write permission, synthetic
smoke-writing remains disallowed unless separately approved, and the first production anchor
creation — with the §7 fields named in advance — remains separately approved future work. See
[`PHASE54_CONTROLLED_ENGAGEMENT_AUTHORIZATION_ANCHOR_WRITER.md`](PHASE54_CONTROLLED_ENGAGEMENT_AUTHORIZATION_ANCHOR_WRITER.md).
