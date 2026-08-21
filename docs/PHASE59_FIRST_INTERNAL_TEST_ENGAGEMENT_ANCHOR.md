# Phase 59 — The First Durable Internal Test Engagement Anchor

**Status:** production-sensitive phase — **one application record written**. Exactly **one durable
internal_test engagement anchor was created in production**, through the existing Phase 54/56
controlled writer. No Client record, no intake note, no downstream record, and no capsule.
**Baseline:** `870d8902cd7af8a8b83b8a5311f832d2f415905a`
**Alembic head:** unchanged at `014_engagement_classification` (14 migrations, 18 tables, 12
writers) — Phase 59 adds no migration, no writer, and no allowlist pair
**Writer:** [`peak/db/engagement_authorization_anchor_writer.py`](../peak/db/engagement_authorization_anchor_writer.py) (Phase 54, unchanged)
**Operator utility:** [`tools/create_internal_test_engagement_anchor.py`](../tools/create_internal_test_engagement_anchor.py)
**Harness:** [`tests/validate_phase59_first_internal_test_engagement_anchor.py`](../tests/validate_phase59_first_internal_test_engagement_anchor.py)
(`make validate-phase59`, in `make validate`; offline, temp-SQLite only, contacts no production)

---

## 1. What was written

Phase 54 built the anchor writer and created no anchor. Phase 56 added the classification columns
and created no record. Phase 58 applied migration 014 so production could hold them. Phase 59 is
the write those phases were building toward: Peak's **first production application record**.

| Field | Value | Why |
| --- | --- | --- |
| `engagement_id` | `internal_test_001` | the anchor's primary key, and its idempotency boundary |
| `client_id` | `99999` | the reserved internal/test namespace — a **visible marker**, not the control |
| `owner_id` | `peak_internal_admin` | a clearly internal owner; no repo convention existed to follow |
| `authorization_scope` | `internal_peak_only` | a canonical scope that does not overload classification |
| `engagement_category` | `internal_test` | **the actual control** |
| `real_client_data` | `false` | **the actual control** |
| `client_accessible` | `false` | **the actual control** |
| `capsule_publication_authorized` | `true` | permitted only by the compound rule below |
| `status` / `lifecycle_status` | `active` / `active` | the minimal valid values for a durable, active anchor |
| `review_status` | `needs_review` | server-stamped; a caller may not pre-advance it |
| `idempotency_key` | `phase59_internal_test_anchor_001` | deterministic and specific to this anchor, never random per run |

The `engagement_label` is stored but is **never echoed** — in the receipt, in the operator tool's
output, or here — because a label can carry a client organisation name.

**Classification lives in real columns.** It is not encoded in `details_json`, in the label, in the
`authorization_scope`, or in the id prefix. The descriptive `internal_test_001` id and the reserved
`99999` client id are conveniences for a human reading a row at a glance; **read isolation filters
on the columns**, and a record with an ordinary id would be excluded exactly the same way.

## 2. It is a durable internal/admin record, not disposable smoke

This record is retained **on purpose** — for development, live testing, training, and
demonstration. It is **not disposable smoke** data and there is no plan to remove it.

That distinction is load-bearing because **runtime DELETE is unavailable**: the runtime credential
holds `SELECT` + `INSERT` and nothing else, so nothing in the application can remove this row.
Deletion is therefore **not expected** and was never part of the plan. Cleanup posture was decided
*before* the write, not after — which is the standing rule for any production record.

Three postures that must not be collapsed into one:

| Posture | Status after Phase 59 |
| --- | --- |
| Approved **durable internal_test** production anchor | **now created** — this record |
| **Disposable** production smoke record | **still disallowed** — runtime cannot clean one up |
| Unauthorized **writer enablement** | **still disallowed** — no writer is enabled by this phase |

To say it without the formatting: a disposable production smoke record remains disallowed, and
unauthorized writer enablement remains disallowed. Phase 59 was one explicitly authorized writer
invocation, not a standing grant — the writer-enablement decision gate still returns a no-write
decision.

## 3. Publication eligibility follows from the compound rule

`capsule_publication_authorized=true` is permitted here **only** because the compound rule is
satisfied: the engagement is `internal_test`, holds **no real client data**, and is **not
client-accessible**. Publication authority is never granted by default and is never granted to a
real-client engagement — no real-client publication authority is designed yet.

Eligibility is not publication. **No capsule was created or published**, and
`capsule_publication_made` and `agentnet_publication_made` are both `false` on the receipt.

## 4. What was not written

- **No real client record was created.** `clients` remains on `NEVER_WRITABLE_TABLES` and is
  unreachable by every controlled path; `client_record_write_made=false`.
- **No intake note** and no downstream record of any kind — no evidence, review, bundle, report
  draft, review packet, agent run, or task queue row. `other_table_write_made=false`.
- **No capsule was published.** See §3.
- **No UPDATE, DELETE, manual SQL, cleanup, or stamp.** `update_made=false`, `delete_made=false`.
- **No app table scan, count, or probe.** The only reads were the writer's own single-primary-key
  existence check and the read-back of the row it created.
- **No approval, client-facing output, financial verification, agent execution, LLM, AgentNet,
  resolver, or network call.** All `false` on the receipt.

## 5. Credential boundary

The **runtime credential was used only through the controlled writer path** — resolved by
`peak.db.session.create_session_factory`, which reads `PEAK_RUNTIME_DATABASE_URL` and only that
variable, with no fallback to the migration credential. Before the write, the runtime connectivity
gate confirmed the credential connects with the required `SELECT` + `INSERT` grants and **no excess
grants, no global privileges, and no GRANT OPTION**.

The read-only verifier credential was used for schema posture only, before and after the write; it
read `INFORMATION_SCHEMA` and `alembic_version` and no application rows. **The migration credential
was not used** and no migration was run. No credential, DSN, environment value, or raw grant was
printed or committed.

## 6. The operator utility

[`tools/create_internal_test_engagement_anchor.py`](../tools/create_internal_test_engagement_anchor.py)
exists because there was no safe existing way to invoke the anchor writer. It is deliberately not a
general-purpose record creator:

- **The packet is a hard-coded constant.** It accepts `--dry-run` / `--execute` and **no record
  field**. A tool taking `--client-id` / `--category` would be a generic `engagements` writer
  wearing a phase name, and `engagements` stays on `PROHIBITED_TABLES` so that no such thing exists.
- **Dry-run is the default.** With no flag it runs the writer's own pre-DB governance gate and
  stops before any connection is opened. The harness proves this by running it with every role
  variable scrubbed from the environment.
- **It invokes only the existing controlled writer.** No raw SQL, no Alembic import, no
  `UPDATE`/`DELETE`/cleanup/stamp path, and it reads no environment variable itself.
- **Replay is safe.** The same anchor with the same fingerprint is an idempotent success that
  writes nothing; the same anchor id with a *changed* definition is an `idempotency_conflict`
  denial that stops and modifies nothing.

## 7. Read isolation — the primitive is not automatic

The anchor is excluded from client-facing reads by the Phase 57 primitive
([`peak/db/engagement_read_isolation.py`](../peak/db/engagement_read_isolation.py)): the default
mode returns it not at all, and internal/admin views see it only on explicit opt-in.

That protection is **not automatic**. **Future real-client read paths must use Phase 57 read
isolation** — a query that bypasses `apply_read_isolation` is not protected by it, and now that a
real internal_test row exists in production, an unfiltered client-facing query would surface it.
This is the first phase where that stops being hypothetical.

## 8. Still outstanding

- The first **client-facing read path** must actually call `apply_read_isolation`.
- **No writer is enabled.** The writer-enablement decision gate still returns a no-write decision;
  this phase was a single explicitly authorized invocation, not an enablement.
- Any further production record — including a second internal test anchor — remains separately
  approved, and must name its writer, table, action, scope, idempotency key, and cleanup posture
  before the write.
