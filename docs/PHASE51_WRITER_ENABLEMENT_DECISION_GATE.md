# Phase 51 — Writer Enablement Decision Gate

**Status:** governance decision gate. **Current decision: NO production smoke-write, NO writer
enablement, NO synthetic production write, NO real engagement write until authorized engagement data
exists.** No writer was enabled or invoked; no production data was written; no application row was
read.
**Baseline commit:** `dcaa536c91dc50e6f03df9abca0af8e137031707` — *Add Phase 50 controlled runtime
connectivity gate*
**Alembic head:** unchanged at `013_governed_identifier_collation_policy`
**Tool:** [`tools/production_writer_enablement_decision_gate.py`](../tools/production_writer_enablement_decision_gate.py)
(`make writer-enablement-decision-gate` — opt-in; **offline**, contacts no database)
**Harness:** [`tests/validate_phase51_writer_enablement_decision_gate.py`](../tests/validate_phase51_writer_enablement_decision_gate.py)
(`make validate-phase51`, included in `make validate`)
**Related:** [`PHASE48_PRODUCTION_RUNTIME_READINESS_GATE.md`](PHASE48_PRODUCTION_RUNTIME_READINESS_GATE.md),
[`PHASE49_RUNTIME_DATABASE_URL_SEPARATION.md`](PHASE49_RUNTIME_DATABASE_URL_SEPARATION.md),
[`PHASE50_CONTROLLED_RUNTIME_CONNECTIVITY_GATE.md`](PHASE50_CONTROLLED_RUNTIME_CONNECTIVITY_GATE.md)

---

## 1. Purpose

Phases 48–50 answered technical questions: are the grants right, is the wiring right, does the
connection work. All three passed. **None of them answered whether anything should be written.**

That is a governance question, not a plumbing question, and it deserves its own gate rather than
being settled implicitly by the first phase that happens to have a working connection. Phase 51 adds
that gate and records the current answer.

## 2. The decision, as recorded

| Field | Value |
| --- | --- |
| `selected_path` | `no_production_smoke_write_yet` |
| `production_write_authorized` | **false** |
| `writer_enablement_authorized` | **false** |
| `synthetic_write_authorized` | **false** |
| `real_engagement_write_authorized` | **false** |
| `safe_to_run_writers_now` | **false** |
| `safe_to_write_production_now` | **false** |
| `requires_authorized_engagement_before_real_write` | **true** |
| `requires_explicit_cleanup_plan_before_synthetic_write` | **true** |
| `runtime_delete_available` | **false** |
| `migration_credential_cleanup_requires_separate_approval` | **true** |
| `runtime_connectivity_gate_required_before_future_write` | **true** |
| `read_only_production_verifier_required_before_future_write` | **true** |
| `production_migration_required` | **false** |
| `schema_change_required` | **false** |
| `recommended_next_path` | `wait_for_authorized_engagement_or_separately_approve_no_cleanup_admin_smoke_record` |

The gate exits `0` for the no-write path and refuses with exit `3` if asked to record any
write-authorizing path. Requesting a write path is how a *future* phase asks; asking is not being
granted, and no field flips when it is asked.

## 3. Runtime connectivity is proven, and it is not sufficient

Phase 50 established that the runtime credential connects through the application's own session path
and holds exactly `SELECT` + `INSERT`. That is **prerequisite evidence**: it says the plumbing and
privileges are correct.

It does not say there is anything that ought to be written, or who authorised writing it. Treating a
green connectivity check as permission to start writing would collapse a governance decision into a
technical one. The gate records this explicitly as
`phase50_pass_is_prerequisite_evidence_not_write_permission = true`.

## 4. Runtime has no DELETE — so cleanup is decided *before* the write

The runtime credential deliberately holds no `DELETE`. The consequence is easy to overlook and
expensive to discover late:

> **A synthetic or administrative record written by runtime cannot be removed by runtime.**

Removing it would require the migration credential — a separate approval, a separate risk, and a
credential that can also change schema. So the honest default is to treat **any** synthetic record
as **durable**: it will remain in the governed audit history unless someone later takes a deliberate,
separately approved action to remove it.

This is why `requires_explicit_cleanup_plan_before_synthetic_write` is `true`. The cleanup posture is
part of the authorization decision, not a follow-up task.

## 5. The three future paths

A future enablement phase must pick one **explicitly**. They are not interchangeable, and the gate
names all three so the choice cannot be made by default:

1. **No production smoke-write.** Writers are enabled only under real engagement traffic; the first
   write is genuine work. Nothing synthetic ever enters the audit history. *(Current path.)*
2. **One approved synthetic/administrative smoke-write.** A single record of pre-agreed shape.
   Because runtime cannot delete it, it **remains as a durable audit/administrative record** unless
   separately cleaned under explicit approval using the migration credential. Choosing this path is
   choosing to accept that record permanently, absent that separate action.
3. **Real engagement-only write after client authorization exists.** No write until a governed
   engagement and its authorization scope are in place, so the first row is authorized by
   construction.

**Recommended next path:** wait for authorized engagement/intake data, *or* separately approve a
no-cleanup administrative smoke record with eyes open about its permanence.

## 6. What a future write enablement phase must do

**Re-run all three gates first** — posture drifts, and all three are cheap and non-mutating:

- the read-only production verifier — `make production-mysql-collation-verify PYTHON=.venv/bin/python`
- the runtime connectivity gate — `make runtime-connectivity-gate PYTHON=.venv/bin/python`
- this decision gate — `make writer-enablement-decision-gate` (no driver needed; it is offline)

> **Pass `PYTHON=.venv/bin/python` to the two live gates.** `PYTHON` defaults to `python3`, which on
> this machine has no database driver installed. Run without the override, the connectivity gate
> fails closed and — since Phase 52A — says so plainly: `failure_category=local_driver_unavailable`,
> `production_connectivity_result=not_tested_due_to_local_driver_unavailable`, plus a `FIX:` line
> naming the venv invocation. **That is a local interpreter problem, not a production connectivity
> failure**, and it authorizes nothing either way. The same override applies to the read-only
> verifier.

**And it must name, explicitly and in advance:**

| Item | Why it must be named before the write |
| --- | --- |
| the writer to be invoked | narrows the blast radius to one known code path |
| the target table | the allowlist and idempotency boundary differ per table |
| the exact allowed action | the allowlist is per-action, not per-writer |
| the expected authorization scope | governance records are scoped; an unscoped row is unauditable |
| the idempotency key design | the `UNIQUE (owner_id, client_id, engagement_id, idempotency_key)` boundary is case-sensitive by Phase 44; a key chosen ad hoc cannot be replayed safely |
| the rollback/cleanup posture | runtime cannot delete; see §4 |
| whether any durable synthetic/admin record will remain | this is the decision people forget to make |

## 7. What this phase does not do

- **It enables no writers** and invokes none.
- **It writes no production data**, mutates no schema, and runs no migration.
- **It reads, counts, and probes no application table row.**
- **It does not use the migration credential.**
- **It contacts no database at all.** The decision gate has no database code path: no engine,
  session, writer, or driver import; no environment read; no statement of any kind; no file access.
  It cannot touch production by construction, not merely by policy.

## 8. Security confirmations

- **No DSNs, hosts, usernames, passwords, tokens, certificate paths, database names, connection
  URLs, environment values, raw grant lines, or row values** are recorded in this document, emitted
  by the gate, or added to source or tests.
- The decision gate reads no environment variable — not the runtime, migration, or verifier one.
- Operator credential files used for the live re-checks in this phase were **sourced without output**
  and never displayed, copied, catted, grepped, or searched. `.env` was not read; no secret store was
  searched. The migration credential was not sourced or used.
- `make validate` stays offline and credential-free; the live gates remain opt-in.

---

## 9. Phase 53 update — the recommended path, made concrete (still no write)

Phase 53 took the recommended path of §5 — *wait for authorized engagement/intake data* — and worked
out what it concretely requires, by reading source only. **The Phase 51 decision is unchanged: no
production write, no writer enablement, no synthetic smoke write. No field in §2 flips.** The first
production write remains deferred.

What Phase 53 established:

- **The authorization anchor is a stored `Engagement` row with a populated `authorization_scope`.**
  Every controlled writer loads it at write time and requires the request scope to equal the stored
  scope; identity matching alone is not sufficient.
- **The `Engagement` model/table exists**, so no schema work is needed — but **no controlled
  Engagement writer exists**, and `engagements` sits in `PROHIBITED_TABLES` with no
  engagement-creating action on the allowlist.
- **The intake note writer exists and requires that stored authorization**, so the first intake note
  cannot be written without the anchor. It is the recommended first real operational writer once the
  anchor exists.
- **Recommended next phase: Phase 54 should add a create-only controlled Engagement authorization
  anchor writer** — and create no engagement record.

Path 2 of §5 (a synthetic/administrative smoke-write) remains unchosen and disallowed unless
separately approved; §4 still applies to it in full — runtime holds no `DELETE`, so such a record is
durable. See [`PHASE53_AUTHORIZED_ENGAGEMENT_INTAKE_PATH.md`](PHASE53_AUTHORIZED_ENGAGEMENT_INTAKE_PATH.md).

---

## 10. Phase 55 update — a third future path, and the decision still stands

§5 named three future paths. Phase 55 adds a fourth, and **changes no field in §2**: **no production
write, no writer enablement, no synthetic smoke write.**

4. **Durable internal test / training engagement.** A deliberately retained internal record used for
   training, live testing, and demonstration — never client-accessible, carrying no real client data
   unless separately and explicitly authorized, and optionally authorized for capsule publication
   when explicitly classified.

This is **not** path 2 renamed. Path 2 is a smoke record written to prove plumbing, ideally removed
afterwards, and disallowed precisely because §4 means it cannot be. A durable internal test
engagement is written *because Peak intends to keep it*, so the absence of a runtime `DELETE` fits
its intent rather than defeating it. Classifying a record as internal test is **not** a route to
retroactively justify a smoke write; path 2 remains disallowed unless separately approved with its
permanence understood.

Phase 55 also records that the Phase 54 anchor writer now exists — and that **existing is not
permission to write**, exactly as a passing connectivity gate is not. Neither the model nor that
writer can yet classify an internal test engagement, so **Phase 56 should add classification support
and create no records**. See
[`PHASE55_INTERNAL_TEST_ENGAGEMENT_CLASSIFICATION.md`](PHASE55_INTERNAL_TEST_ENGAGEMENT_CLASSIFICATION.md).
