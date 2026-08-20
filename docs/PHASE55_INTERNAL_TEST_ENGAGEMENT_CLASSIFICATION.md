# Phase 55 — Internal Test Engagement Classification and Creation Decision

**Status:** planning and classification phase. **Decision: NO production write, NO writer
enablement, NO internal test engagement creation, NO real client engagement creation, NO synthetic
smoke record, NO intake note creation. PLAN AND CLASSIFICATION ONLY.**
No writer was enabled or invoked; no production database was contacted; no application row was
read, counted, or probed; no capsule was published.
**Baseline commit:** `a9786555230913ca26479f73f44277633fa4d906` — *Add Phase 54 engagement
authorization anchor writer*
**Alembic head:** unchanged at `013_governed_identifier_collation_policy` (13 migrations, 18 tables,
12 writers, **no migration 014**)
**Harness:** [`tests/validate_phase55_internal_test_engagement_classification.py`](../tests/validate_phase55_internal_test_engagement_classification.py)
(`make validate-phase55`, included in `make validate`; offline and credential-free)
**Related:** [`PHASE54_CONTROLLED_ENGAGEMENT_AUTHORIZATION_ANCHOR_WRITER.md`](PHASE54_CONTROLLED_ENGAGEMENT_AUTHORIZATION_ANCHOR_WRITER.md),
[`PHASE53_AUTHORIZED_ENGAGEMENT_INTAKE_PATH.md`](PHASE53_AUTHORIZED_ENGAGEMENT_INTAKE_PATH.md),
[`PHASE51_WRITER_ENABLEMENT_DECISION_GATE.md`](PHASE51_WRITER_ENABLEMENT_DECISION_GATE.md),
[`CLIENT_ISOLATION_MODEL.md`](CLIENT_ISOLATION_MODEL.md),
[`DATA_HANDLING_POLICY.md`](DATA_HANDLING_POLICY.md),
[`FIXTURE_STRATEGY.md`](FIXTURE_STRATEGY.md)

---

## 1. Purpose

Peak should eventually support a small number of **durable internal sample / training / live-test
engagements**, once the application is ready for production. This phase decides what they are, how
they must be distinguished and isolated, and what has to exist before the first one can be created.

It creates nothing. Defining the category and creating a record in it are separate phases, and the
second has not happened.

## 2. Phase 55 decision

| Field | Value |
| --- | --- |
| production write | **not performed, not authorized** |
| writer enablement | **not performed, not authorized** |
| internal test engagement creation | **not performed, not authorized** |
| real client engagement creation | **not performed, not authorized** |
| synthetic smoke record | **not performed, still disallowed** |
| intake note creation | **not performed, not authorized** |
| capsule publication | **none; nothing published** |
| schema / model / writer / allowlist change | **none in this phase** |

## 3. Four categories, deliberately distinguished

The repository already had three categories and no name for the fourth. Naming all four is the
substance of this phase, because the failure mode is a record drifting between them unnoticed.

| # | Category | Lives in | Real client data | Client-accessible | Retention |
| --- | --- | --- | --- | --- | --- |
| 1 | **Real client engagement** | managed DB | yes, authorized | yes, to that client | per engagement terms |
| 2 | **Durable internal test / training engagement** | managed DB | **no**, unless separately and explicitly authorized | **never** | **durable; deliberately retained** |
| 3 | **Disposable synthetic production smoke record** | — | no | no | **disallowed** |
| 4 | **In-memory synthetic fixture** | test process only | no | no | never persisted, never committed |

**Category 2 is the new, allowed category.** It is a deliberate, first-class kind of record — used
for training, live testing, and demonstration — and it is **not** a disposable smoke record.

**Category 2 is not category 3.** A smoke record is written to prove the plumbing works and would
ideally be removed afterwards; it stays disallowed precisely because runtime cannot remove it (§7).
A durable internal test engagement is written *because Peak wants to keep it*. The distinction is
intent and classification, and it must be recorded on the row rather than inferred later.

**Category 2 is not category 4.** Synthetic fixtures are built in memory by the test harnesses,
carry a `synthetic` marker, and are never persisted or committed
([`FIXTURE_STRATEGY.md`](FIXTURE_STRATEGY.md)). Internal test engagements are persisted governed
records in the managed database.

**Category 2 must be retained** unless removal is separately approved. It is not cleanup debt.

## 4. Source inspection findings

### 4.1 The current `Engagement` model does **not** support classification cleanly

`Engagement` carries exactly: `id`, `client_id`, `engagement_label`, `status`, plus the
`GovernanceMixin` axes (`owner_id`, `authorization_scope`, `review_status`, `lifecycle_status`) and
the `AuditMixin` columns. **There is no field for record category, client visibility, real-client-data
posture, or capsule publication authorization.**

This is notable against the repository's own house pattern: eight other record tables carry
governance posture as **real boolean columns** — `client_facing_approved`, `capsule_candidate_ready`,
`publication_allowed`, `execution_allowed`, `requires_human_review`. `Engagement`, the anchor every
governed write descends from, carries **none of them**.

Each candidate for encoding classification without a schema change was examined and rejected:

- **`authorization_scope` would be overloaded.** It is the single value every controlled writer
  matches its request scope against at write time. It answers *who may see this*; classification
  answers *what kind of record this is*. They are orthogonal, and conflating them means an internal
  test engagement can no longer exercise the real scope path it exists to test. `internal_peak_only`
  is a real scope value, but choosing it as the classification marker permanently couples the two
  axes.
- **`fixture_test` scope is unusable here, and this was verified rather than assumed.** An anchor
  requires `client_id` and `engagement_id`, and the governance gate refuses `fixture_test` mixed
  with live client/engagement identity — the request is denied before any connection is opened.
- **`engagement_label` is too fragile.** It is an ungoverned `String(255)` free-text field, never
  validated for any prefix, and deliberately **never echoed in a receipt** because a label can carry
  a client organisation name. Classification must not depend on parsing it.
- **An `id` prefix convention is also too fragile.** It has no database enforcement, requires a
  `LIKE` scan to query, and — under the Phase 44 byte-exact collation — a single typo silently
  produces an *unclassified* record that reads as a real client engagement.
- **`details_json` is prohibited for this.** `peak/db/base.py` states it is for non-governance
  detail only: *"Do NOT store governance fields here."* Category, visibility, real-client-data
  posture, and publication authorization are all governance fields. (Phase 54 does place a
  non-authoritative copy of the idempotency key there as audit provenance; the authoritative replay
  boundary remains the primary key plus the recomputed stored-field fingerprint. That is provenance,
  not governance state, and it is not a precedent for putting classification there.)
- **`review_status` / `lifecycle_status` / `status`** are closed, already-meaningful vocabularies
  with no room for an orthogonal axis.

### 4.2 The Phase 54 writer does **not** support classification cleanly

The anchor draft accepts exactly `owner_id`, `client_id`, `engagement_id`, `authorization_scope`,
`engagement_label`, `status`, `review_status`, `lifecycle_status`. **There is no classification
input, so there is nothing for the writer to validate or refuse.** The writer is correct as built;
it simply has no such concept yet.

### 4.3 A future schema/model change **is** required

Yes. Clean classification needs governed attributes as **real columns**, following the pattern the
rest of the schema already uses. Phase 55 documents this and **implements none of it**.

### 4.4 A future writer validation change **is** required

Yes. The anchor writer must accept the classification fields, enforce their invariants (§8), and
report the safe classification labels on the receipt.

### 4.5 Isolation today is write-side only

[`CLIENT_ISOLATION_MODEL.md`](CLIENT_ISOLATION_MODEL.md) records Option A: a shared managed database
with strict tenant columns and governed write paths. Isolation is enforced **on writes**, scoped to
`(owner_id, client_id, engagement_id)` and the stored anchor.

**No client-facing read or query path exists in the repository at all**, so no current path can leak
an internal test engagement to a real client. The exposure is entirely prospective: the isolation
must be built into the read path when that path is built, and it must not rely on `client_id`
convention alone.

One concrete gap follows from Phase 54: `clients` is **never writable** by any controlled path, so
there is **no governed registry from which to reserve an internal-test `client_id`**. Collision
avoidance therefore cannot currently be enforced by the database, and the future creation packet
must state how it is guaranteed (§8).

### 4.6 Repo data policy is intact and constrains this

[`DATA_HANDLING_POLICY.md`](DATA_HANDLING_POLICY.md) prohibits client data in the repository in any
form, and prohibits using client data for examples, fixtures, demos, **training**, or tests.
[`FIXTURE_STRATEGY.md`](FIXTURE_STRATEGY.md) keeps synthetic fixtures in memory, never committed.

These remain fully in force and are consistent with category 2: an internal test engagement lives in
the **managed database, never in Git**, and **contains no real client data** unless separately and
explicitly authorized. Nothing about this category loosens the repository prohibition.

## 5. Isolation requirements for internal test engagements

Internal test engagements must be isolated from real clients on **classification**, not on naming
convention:

- **Real clients must not be able to query, view, list, infer, or join into internal test
  engagements.** Aggregates, counts, search results, exports, and error messages count as exposure.
- Isolation must be enforced by an explicit classification predicate in whatever read/query path is
  eventually built — not by a client_id prefix, not by a label, and not by convention.
- The internal-test `client_id` and `engagement_id` must be guaranteed non-colliding with any real
  client record (§8), since `clients` has no governed registry to reserve from.
- An internal test engagement must never be reachable from a real client's authorization scope.

## 6. Capsule publication for internal test engagements

Internal test engagements **may** be authorized for capsule publication — but only under an explicit
rule:

> **An internal test capsule may be published only if the engagement is explicitly classified as
> authorized for publication *and* contains no real client data.**

Both conditions, checked together, at publication time. Classification alone is not sufficient, and
absence of real client data alone is not sufficient.

This changes nothing today: no capsule publication path exists, publication remains deferred, and
[`PEAK_OPERATED_AGENTNET_PUBLICATION_POLICY.md`](PEAK_OPERATED_AGENTNET_PUBLICATION_POLICY.md)
continues to hold — Peak is the only authorized publisher, there is no client-facing publisher path,
and publication/approval flags are stored false by every writer.

## 7. Runtime has no `DELETE` — cleanup cannot be assumed

The runtime credential deliberately holds `SELECT` + `INSERT` and **no `DELETE`**. Anything runtime
writes **cannot be removed by runtime**; removal would require the migration credential under
separate approval.

For category 2 this is not a problem but a design fit: internal test engagements are **meant** to be
durable, so the absence of a delete path matches their intent. For category 3 it is exactly why
synthetic smoke records remain disallowed — they would be permanent whether or not anyone intended
that.

**Synthetic smoke records remain disallowed unless separately approved**, with their permanence
understood up front. Classifying a record as an internal test engagement is **not** a way to
retroactively justify a smoke write.

## 8. Minimum required fields for a future internal test engagement creation packet

A future phase proposing the first internal test engagement must state every one of these **in
advance**, and it remains subject to explicit approval:

| Item | Must be specified |
| --- | --- |
| record category / `internal_test` classification | the explicit governed category value |
| non-client visibility / access restriction | how the read path will exclude it from every client |
| `real_client_data=false` | asserted explicitly; `true` requires separate explicit authorization |
| `capsule_publication_authorized` | `true` or `false`, decided deliberately, not defaulted |
| owner / admin authority | the internal owner of the record |
| `client_id` strategy | how collision with any real client record is **guaranteed** impossible |
| `engagement_id` strategy | how collision with any real client record is **guaranteed** impossible |
| `authorization_scope` source and intended meaning | and how it stays orthogonal to classification |
| idempotency / anchor identity boundary | the anchor id is the boundary; the fingerprint is recomputed from stored governed fields |
| retention posture | expected to be **durable and retained** |
| approval authority | who authorized it, and as what role |
| durability statement | an explicit statement that the record is durable and **not expected to be deleted** |

## 9. What must be true before the first record of each kind

**Before the first internal test engagement anchor:**

1. governed classification columns exist (schema change, its own phase);
2. the anchor writer accepts and validates them, and refuses an internal test record that claims
   real client data without separate authorization;
3. the non-collision strategy for `client_id` / `engagement_id` is stated and enforceable;
4. the read-path isolation rule is defined, even if the read path does not exist yet;
5. the three gates are re-run — read-only verifier, runtime connectivity gate, writer-enablement
   decision gate — and a write-authorizing path is explicitly chosen;
6. the §8 packet is complete and explicitly approved.

**Before the first real client engagement anchor:** all of the above that apply, plus a real client
authorization actually existing — a signed engagement and a real `authorization_scope` — and the
record classified as a real client engagement rather than defaulting into it.

## 10. Recommended next phase

Source inspection resolved the conditional: **the current model and writer do not support
classification cleanly.** Therefore:

> **Phase 56 should add internal-test classification support — schema, model, and writer validation
> — and create no records.**

That phase must, at minimum: add the governed classification columns as real columns (with the
migration that implies), extend the anchor draft and writer to accept and validate them, default
every record to the safest posture (not internal test, no publication authorization, not
client-accessible), and **create no engagement record of any kind**.

Preparing the first durable internal test engagement creation packet is the phase *after* that, and
executing it remains separately approved work.

## 11. Standing decisions preserved

- **Phase 51 no-write / no-enablement remains in force.** Phase 55 records a classification; it
  flips no field in that decision record.
- **The Phase 54 writer exists, and existing is not permission to write.** A code path is not an
  authorization, exactly as a passing connectivity gate is not one.
- **Phase 50 runtime connectivity remains prerequisite evidence, not write permission.**
- **`engagements` remains prohibited on the generic write path**, reachable only through the single
  anchor pair; **`clients` remains never writable by any path.**
- **The first production engagement anchor creation — internal test or real client — remains
  separately approved future work.**

## 12. What this phase does not do

- **It creates no engagement record** of any kind, no intake note, and no synthetic smoke record.
- **It publishes no capsule.**
- **It enables no writers** and invokes none.
- **It contacts no production database**, writes no production data, mutates no schema, runs no
  migration, and reads/counts/probes no application row.
- **It adds no table, model field, writer, allowlist pair, or migration 014**, and modifies no
  `alembic/versions` file.
- **It adds no generic SQL/CRUD path**, no `UPDATE`/`DELETE` behaviour, no client-facing
  functionality, and no AgentNet/LLM/MCP/resolver/network workflow.

## 13. Security confirmations

- **No DSNs, hosts, usernames, passwords, tokens, certificate paths, database names, connection
  URLs, environment values, raw grant lines, row values, client data, pseudo-client data, or example
  records** are recorded in this document or added to source or tests. No production values of any
  kind appear here.
- No `~/.peak` operator credential file was sourced or read; `.env` was not read; no secret store was
  searched; the migration credential was not used.
- `make validate` stays offline and credential-free; the live gates remain opt-in.
