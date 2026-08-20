# Phase 54 — Controlled Engagement Authorization Anchor Writer

**Status:** implementation phase — code path only. **No production engagement record was created,
no intake note record was created, no synthetic smoke record was created, and no writer enablement
occurred.** No production database was contacted; no application row was read, counted, or probed.
**Baseline commit:** `4e20e73bc4022dd02f368393d7d3e9da4e6ca67b` — *Document Phase 53 authorized
engagement intake path*
**Alembic head:** unchanged at `013_governed_identifier_collation_policy` (13 migrations, 18 tables,
**no migration 014**)
**Writer:** [`peak/db/engagement_authorization_anchor_writer.py`](../peak/db/engagement_authorization_anchor_writer.py)
**Harness:** [`tests/validate_phase54_engagement_authorization_anchor_writer.py`](../tests/validate_phase54_engagement_authorization_anchor_writer.py)
(`make validate-phase54`, included in `make validate`; offline, exercised only against throwaway
temporary SQLite databases)
**Related:** [`PHASE53_AUTHORIZED_ENGAGEMENT_INTAKE_PATH.md`](PHASE53_AUTHORIZED_ENGAGEMENT_INTAKE_PATH.md),
[`PHASE51_WRITER_ENABLEMENT_DECISION_GATE.md`](PHASE51_WRITER_ENABLEMENT_DECISION_GATE.md),
[`CONTROLLED_WRITE_ALLOWLIST.md`](CONTROLLED_WRITE_ALLOWLIST.md),
[`INTAKE_NOTE_CONTROLLED_WRITER.md`](INTAKE_NOTE_CONTROLLED_WRITER.md)

---

## 1. What this phase adds, and why

Phase 53 established the blocker precisely: every controlled writer loads a stored `Engagement`
row at write time and requires the request's `authorization_scope` to equal that row's stored
scope. The anchor is what every governed write descends from — and nothing in Peak could create
one, because `engagements` sits on `PROHIBITED_TABLES`, deliberately, as a root/identity table.

Phase 54 adds the one governed code path that resolves that, and nothing else:

> **A create-only controlled writer for engagement authorization anchors.**

It creates no record. Adding the path and using it are two different phases, and the second one
has not happened.

## 2. The narrow governance exception

The obvious fix — removing `engagements` from `PROHIBITED_TABLES` — is the wrong one. It would
open generic Engagement CRUD to every caller travelling the generic Phase 17 path, in exchange for
a single writer's needs.

Instead the grant is a **second, deliberately tiny gate** beside the first:

| | Generic Phase 17 path | Phase 54 anchor path |
| --- | --- | --- |
| gate | `ALLOWED_TABLES` × `ALLOWED_ACTIONS` | `ALLOWED_ANCHOR_CREATION_PAIRS` |
| size | 13 tables, 15 actions | **exactly one (table, action) pair** |
| `engagements` | **still prohibited** | `engagements` / `create_engagement_authorization_anchor` |
| `clients` | prohibited | **never writable by any path** (`NEVER_WRITABLE_TABLES`) |

Consequences, each covered by a test:

- `engagements` **remains on `PROHIBITED_TABLES`**, so the generic evaluator still refuses it and
  generic Engagement CRUD remains impossible.
- The generic allowlist is **numerically and materially unchanged** — still 13 tables and 15
  actions. The anchor action is *not* on `ALLOWED_ACTIONS`.
- **`clients` and broad root-table writes remain prohibited.** `clients` is additionally listed in
  `NEVER_WRITABLE_TABLES`, so it is refused by the anchor predicate as well as the generic one.
- The exception cannot be widened by recombination: the predicate is **pair-wise**. The allowed
  action aimed at another table is refused, and another action aimed at `engagements` is refused.

**This is a narrow governance exception, not generic Engagement CRUD.** Expanding
`ALLOWED_ANCHOR_CREATION_PAIRS` is a governance change of the same weight as expanding
`ALLOWED_TABLES`, and it must not be used as an escape hatch for root tables.

## 3. The exact target / action pair

| Field | Value |
| --- | --- |
| writer | `peak/db/engagement_authorization_anchor_writer.py` |
| entry point | `persist_engagement_authorization_anchor(...)` |
| target table | `engagements` |
| action | `create_engagement_authorization_anchor` |
| allowlist pair | **engagements/create_engagement_authorization_anchor** — the only member of `ALLOWED_ANCHOR_CREATION_PAIRS` |

## 4. The stored-subject check is replaced, not weakened

The generic path's decisive gate compares the request scope to the **stored** subject's scope. That
check cannot apply here: the row being created *is* that subject, so requiring it would be
circular, and manufacturing a fake subject to satisfy it would hollow out the invariant everywhere
else in the system.

So it is replaced by a set of gates that are strictly checkable *without* a prior row, in
`evaluate_engagement_anchor_creation_request` and re-enforced at the writer's own boundary:

1. the **exact single pair**, checked pair-wise — never a table-wide or action-wide grant;
2. **`subject` must be absent**, so this path can never be confused with, or used to smuggle a
   request through, the subject-bearing generic path;
3. every governed identity field (`owner_id`, `client_id`, `engagement_id`) **present, non-blank,
   governed-charset, and within its column bound** — a malformed identifier on the anchor would
   poison every later scope comparison;
4. an explicit **`authorization_scope`** that is a canonical governance scope value and is not
   `revoked` — a typo'd scope would produce an anchor nothing could ever be written under;
5. an **allowed initial lifecycle only** (`active` / `pending` / `draft`; `revoked`, `archived`,
   `deleted_reference_only`, and `superseded` are all refused);
6. an **allowed initial engagement status only** (`prospective` / `active`) — an authorization
   anchor is created at the *start* of an engagement;
7. an **idempotency key**, present and bounded;
8. a **record draft** to persist, of the concrete anchor draft type, whose identity matches the
   request;
9. **no `fixture_test` scope** mixed with live client/engagement identity;
10. **value-marker screening** on the free-text label — credential, DSN, raw-SQL, and raw-content
    shapes are refused, and only the marker *category* is ever reported.

Every one of these fails **closed, before any database connection is opened**.

## 5. Create-only, and `SELECT` + `INSERT` remains sufficient

The writer performs exactly one `session.add` and one commit. It has **no `UPDATE`, no `DELETE`,
no `merge`, no bulk operation, no raw SQL, and no schema operation**; it opens no network, LLM,
AgentNet, MCP, or resolver path; it writes **no table other than `engagements`**; and it never
creates or touches a `Client` row.

The only database verbs on the path are a primary-key read, one insert, one commit, and a read-back.
**`SELECT` + `INSERT` remains sufficient** — the Phase 48/50 runtime posture already covers it, and
**no privilege change is required**.

## 6. Idempotency without new columns — and why no migration was needed

`engagements` has no `idempotency_key` / `payload_fingerprint` column, and Phase 54 adds **no
migration and no model change**. It does not need them:

- the anchor's **primary key is its identity**, so the caller-supplied `engagement_id` is the
  idempotency boundary — a replay names the same anchor rather than minting a second one;
- the fingerprint is **recomputed from the stored row's own governed fields** on replay, rather
  than compared against a stored hash.

Behaviour:

| Situation | Result |
| --- | --- |
| no anchor with that id | one row created; `database_write_made = true` |
| same id, identical governed definition | `idempotent_replay`; **no second write**; existing row returned unmodified |
| same id, different governed definition | **denied** `idempotency_conflict`; the stored row is **not** modified |

There is no overwrite path. A conflicting anchor definition is refused, never silently applied.

## 7. Leak-free receipt

Receipts and denial reasons carry no credentials, DSN, host, username, database name, connection
URL, SQL string, stack trace, environment value, raw grant, or raw payload. Infrastructure failures
report the **exception type only**.

They also never carry the **`engagement_label`** — a label can carry a client organisation name, so
it is stored in the row but never echoed. Only governed identifiers, safe status labels, and marker
*categories* appear.

## 8. What still has to happen before a production anchor exists

**The first production engagement anchor creation remains separately approved future work.** This
phase authorizes nothing. Before any production anchor is created, a future phase must provide, in
advance and explicitly:

| Item | Must be named |
| --- | --- |
| exact `owner_id` source | where the owner identity comes from |
| exact `client_id` source | where the client identity comes from |
| exact `engagement_id` source | the anchor id is caller-supplied and is the idempotency boundary |
| exact `authorization_scope` source | every later writer matches against this exact value |
| approval authority | who authorized it, and as what role |
| idempotency key pattern | chosen deliberately, not ad hoc |
| retention/cleanup posture | decided before the write; see §9 |
| record classification | **real client, internal/admin, or separately approved durable admin smoke** |

It must also re-run the three gates first — the read-only production verifier, the runtime
connectivity gate, and the writer-enablement decision gate — since posture drifts and all three are
cheap and non-mutating.

## 9. Standing decisions, unchanged

- **Phase 51 no-write / no-enablement remains in force.** Phase 54 adds a code path;
  it flips no field in that decision record, and the decision gate still reports
  `production_write_authorized=false` and `writer_enablement_authorized=false`.
- **Phase 50 runtime connectivity remains prerequisite evidence, not write permission.**
- **A synthetic smoke write remains disallowed** unless separately approved, with its permanence
  understood up front.
- **Runtime holds no `DELETE`**, so **cleanup cannot be assumed**: an anchor written by runtime
  cannot be removed by runtime. Removing one would require the migration credential under separate
  approval. Any anchor created in production must therefore be treated as durable, which is exactly
  why the retention posture belongs in the authorization decision rather than after it.

## 10. What this phase does not do

- **It creates no engagement record**, no intake note record, and no synthetic smoke record.
- **It enables no writers** and invokes none against production.
- **It contacts no production database**, writes no production data, mutates no schema, and runs no
  migration.
- **It reads, counts, and probes no production application table row.**
- **It adds no table, no model, and no migration 014**, and modifies no `alembic/versions` file.
- **It adds no generic SQL/CRUD path**, no `UPDATE`/`DELETE` behaviour, no client-facing
  functionality, and no AgentNet/LLM/MCP/resolver/network workflow.

## 11. Security confirmations

- **No DSNs, hosts, usernames, passwords, tokens, certificate paths, database names, connection
  URLs, environment values, raw grant lines, row values, client data, pseudo-client data, or
  example records** are recorded in this document or added to source or tests.
- The writer reads no environment variable directly; its session factory is injectable, and the
  harness supplies throwaway temporary SQLite databases that are deleted when it exits.
- No `~/.peak` operator credential file was sourced or read; `.env` was not read; no secret store
  was searched; the migration credential was not used.
- `make validate` stays offline and credential-free; the live gates remain opt-in.
