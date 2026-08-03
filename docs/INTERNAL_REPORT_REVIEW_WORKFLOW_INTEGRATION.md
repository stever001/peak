# End-to-End Internal Report Review Workflow Integration (Phase 40)

**Status:** implemented (read-only workflow integration layer).
**Module:** [`peak/workflows/internal_report_review_workflow.py`](../peak/workflows/internal_report_review_workflow.py)
**Harness:** [`tests/validate_phase40_internal_report_review_workflow.py`](../tests/validate_phase40_internal_report_review_workflow.py)
(`make validate-phase40`)

Phase 40 is a **workflow integration and consolidation** phase. It adds **no persistence
primitive**: no DB table, no model, no Alembic migration, no Phase 17 allowlist pair, no writer, no
update/delete/upsert path, no generic CRUD, no arbitrary SQL executor, and no broad repository. The
Alembic head stays `012_internal_report_review_packet_decisions` and `make db-check` still expects
exactly **18 tables**.

It answers one operational question over records Peak already stores:

```
internal_assessment_report_drafts        (Phase 37)
  -> internal_report_review_packets      (Phase 38)
    -> internal_report_review_packet_decisions (Phase 39)
```

> *Where is this internal report review right now — and what does the evidence in the database
> actually support?*

---

## The Phase 39 gap this closes

Phase 39 is **insert-only** by design. It records *which* review packet a Peak reviewer decided on,
preserving the audit chain packet → report draft → report plan. What it deliberately does **not**
do is update the Phase 38 packet row: `reviewer_decision_status` stays `not_decided` and
`reviewer_decision_record_id` stays null forever.

That is correct for a controlled insert-only writer, but it leaves an operational gap: reading the
packet row alone tells you nothing about whether a decision exists.

**Phase 40 closes that gap by derivation, not mutation.** The current decision state is *computed*
from the Phase 39 decision table. The packet row is **never updated**, the report-draft row is
**never updated**, and no new write path is introduced to "fix" the packet row. If a stored packet
row ever carries a decision status or decision ref that the located decision records cannot
explain, that is reported as a blocker — not silently repaired.

---

## What it is — and is not

| It is | It is not |
| --- | --- |
| A read-only consolidation over four existing tables | A new table / model / migration / allowlist pair |
| A deterministic computed workflow state | A packet-row or report-draft-row update path |
| A sanitized trace across draft → packet → decision | A report generator or client deliverable |
| An internal-only readiness signal | An approval, a client-facing gate, or a publication |
| A blocker reporter | An automatic conflict resolver |

Phase 40 approves nothing for client use, verifies no financial claim, produces no client-facing
output, publishes no capsule, and makes no AgentNet / MCP / resolver / LLM / mock-LLM / agent /
network call. Every result carries `requires_human_review=True` and `read_only=True`.

---

## Public entry point

```python
from peak.workflows import (
    InternalReportReviewWorkflowRequest,
    summarize_internal_report_review_workflow,
)

result = summarize_internal_report_review_workflow(request, session_factory=session_factory)
# -> InternalReportReviewWorkflowResult
```

`session_factory` is a zero-arg callable returning a SQLAlchemy `Session`. It is **required**, and
this layer never falls back to an ambient environment database URL — a call without one is denied
before any connection is opened, so `make validate` needs **no live database credentials and no
network**.

### `InternalReportReviewWorkflowRequest`

| Field | Meaning |
| --- | --- |
| `owner_id` / `client_id` / `engagement_id` | Tenant + engagement identity (all required) |
| `authorization_scope` | Compared against the **stored** `Engagement.authorization_scope` |
| `requested_by` / `requester_role` | Traceability (required) |
| `internal_assessment_report_draft_id` | The stored Phase 37 row to consolidate (required) |
| `internal_report_review_packet_id` | The stored Phase 38 row to consolidate (required) |
| `expected_report_plan_id` | Optional; a mismatch against the stored draft is a blocker |
| `expected_plan_fingerprint` | Optional sha256 hex; a mismatch is a blocker |
| `strict_mode` | Any warning makes the summary non-permitted (the state is still reported) |

The request accepts **no payload**: no prose, no file, no packet body, no DB URL, no credential, no
raw SQL, no LLM prompt, and no workflow JSON blob. Everything it needs is already durable.

---

## Read-only means read-only

The module never calls `session.add`, `session.delete`, `session.merge`, `session.flush`,
`session.commit`, `update()`, or raw SQL, and it imports **no writer function**. Records are loaded
with `session.get` and ORM `session.query` only, and no loaded ORM object is modified. The
SQLAlchemy models are imported **lazily** inside the load step, so `import peak.workflows` still
needs no database driver.

The four tables it reads — and nothing else:

```
engagements
internal_assessment_report_drafts
internal_report_review_packets
internal_report_review_packet_decisions
```

`review_records` and `agent_run_records` are never read *or* written here: no Phase 22 review
writer call and no agent-run writer call exists in this layer.

---

## Validation sequence

### 1. Request pre-flight (DB-free)

Concrete request type; prohibited *unexpected* attribute names (payload / prose / credential / SQL
markers); a non-echoing value scan over every declared field using the public Phase 32
`classify_prohibited_value_marker`; required identity and chain refs; short safe refs; a revoked
`authorization_scope` denied outright; a sha256-shaped `expected_plan_fingerprint`; a boolean
`strict_mode`. **A denial here means no database connection was ever opened.**

### 2. Stored `Engagement` — the authorization subject

**The stored engagement is authoritative.** The engagement must exist, carry a non-blank
`authorization_scope`, match `request.authorization_scope` exactly, match owner / client /
engagement identity, and not be `revoked` / `archived` / `deleted_reference_only`.

**Identity matching is necessary but not sufficient** — a caller who names the right
owner/client/engagement but the wrong scope is blocked with `authorization_scope_mismatch`.

### 3. Stored Phase 37 report draft

Blocked (never updated) when: missing; owner / client / engagement / scope mismatch;
`report_plan_id` or `plan_fingerprint` mismatch against a supplied caller expectation; `audience`
not `internal`; `output_status` not `plan_persisted`; `review_status` not `needs_review`;
`lifecycle_status` not `draft`; any of `client_facing_approved` / `financial_verified` /
`capsule_candidate_ready` / `publication_allowed` / `execution_allowed` true; or
`requires_human_review` false.

### 4. Stored Phase 38 review packet

Blocked (never updated) when: missing; owner / client / engagement / scope mismatch;
`internal_assessment_report_draft_id` not matching the request/draft; `report_plan_id` or
`plan_fingerprint` not matching the stored draft; `audience` not `internal`; `packet_status` not
`ready_for_internal_review`; `review_status` not `needs_review`; `lifecycle_status` not `draft`;
any of `client_facing_approved` / `review_approval_made` / `financial_verified` /
`capsule_candidate_ready` / `publication_allowed` / `execution_allowed` true; or
`requires_human_review` false.

The packet's own `reviewer_decision_status` / `reviewer_decision_record_id` columns are checked
**after** the decision rows are located — see step 6 — because Phase 39 never writes them, so they
are only explicable in light of the decision table.

### 5. Decision record loading

ORM query only (no raw SQL), pinned on every identity and linkage axis: `owner_id`, `client_id`,
`engagement_id`, `authorization_scope`, `internal_report_review_packet_id`,
`internal_assessment_report_draft_id`, `report_plan_id`, and `plan_fingerprint` (the last two taken
from the **stored** draft). Rows are ordered by `id` so the result is deterministic.

A located row is excluded from the effective set, with a warning, when its `decision_scope` is not
`internal_report_review_packet`, its `audience` is not `internal`, its `decision_intent` is outside
the closed Phase 32 vocabulary, or its `decision_status` is inconsistent with its `decision_intent`
under Phase 39's server-side derivation. Exclusions are counted, never echoed.

### 6. Packet-row reconciliation (still no write)

Phase 38 creates a packet pre-decision and Phase 39 never updates it, so `not_decided` / null is
the only stored pair Phase 40 can explain on its own. Any other stored value is accepted **only**
when the located decision records explain it (`reviewer_decision_status` equal to the single
computed decision status, `reviewer_decision_record_id` naming a located decision row), and is a
blocker otherwise (`review_packet_decision_status_unexplained` /
`review_packet_decision_ref_unexplained`). Phase 40 never repairs the row by writing.

---

## Computed state derivation

Distinct `(decision_intent, decision_status)` **positions** are taken in first-seen order:

| Located positions | `workflow_state` | `computed_packet_decision_state` |
| --- | --- | --- |
| none | `awaiting_reviewer_decision` | `awaiting_decision` |
| exactly one | from the intent map below | `decision_recorded` / `needs_followup` |
| more than one | `conflicting_decisions` | `conflicted` |

Because the Phase 39 uniqueness boundary is one row per idempotency key, several rows may exist for
one packet. Rows that express the **same** position (an idempotent duplicate/replay of the same
decision) collapse to that one decision state. Rows expressing **materially different** positions
produce `conflicting_decisions` — Phase 40 does **not** resolve competing decisions automatically,
and `requires_human_review` stays true.

### `decision_intent` → `workflow_state`

| Intent (closed Phase 32 vocabulary) | Computed workflow state |
| --- | --- |
| `ready_for_internal_use` | `decision_recorded_ready_for_internal_use` |
| `needs_more_evidence` | `decision_recorded_needs_followup` |
| `defer_review` | `decision_recorded_needs_followup` |
| `return_for_revision` | `decision_recorded_return_for_revision` |
| `rejected_for_policy` | `decision_recorded_rejected_for_policy` |
| `blocked_by_scope` | `decision_recorded_blocked` |
| `blocked_by_quality` | `decision_recorded_blocked` |
| `blocked_by_missing_source` | `decision_recorded_blocked` |

### The closed workflow-state vocabulary

```
blocked_missing_engagement
blocked_missing_report_draft
blocked_missing_review_packet
blocked_scope_mismatch
blocked_invalid_report_draft
blocked_invalid_review_packet
awaiting_reviewer_decision
decision_recorded_needs_followup
decision_recorded_ready_for_internal_use
decision_recorded_rejected_for_policy
decision_recorded_blocked
decision_recorded_return_for_revision
conflicting_decisions
```

There is **no** client-facing approval vocabulary here — no `approved`, `approved_for_client`,
`published`, or `verified` state exists. **`ready_for_internal_use` is internal readiness and is
not client-facing approval**: it means a Peak reviewer found the internal report draft usable
*inside Peak*, nothing more. Client-facing approval, financial verification, and capsule
publication remain future, separately governed gates.

---

## Result contract

`InternalReportReviewWorkflowResult` carries:

- `outcome` (`denied` / `blocked` / `summarized` / `failed`), `permitted`, `reason_code`
- `workflow_state`, `computed_packet_decision_state`
- `owner_id` / `client_id` / `engagement_id` / `authorization_scope`
- `internal_assessment_report_draft_id`, `internal_report_review_packet_id`
- `report_plan_id`, `plan_fingerprint`
- `decision_record_ids`, `decision_intents`, `decision_statuses`, `decision_record_count`
- `trace` — an `InternalReportReviewWorkflowTrace` of **refs only**: engagement / draft / packet
  refs, plan id + fingerprint, the two upstream payload fingerprints, decision record refs, found /
  considered / skipped counts, the distinct-position count, the packet row's own stored decision
  columns (so the derived-vs-stored difference is auditable), and the source table names
- `reasons`, `warnings`
- `requires_human_review=True`, `read_only=True`
- `database_connection_made`, `sql_execution_made` — the only flags that can ever be true

Everything else is a permanent `False`: `database_write_made`, `stored_record_created`,
`packet_row_updated`, `report_draft_row_updated`, `review_records_write_made`,
`agent_run_records_write_made`, `review_approval_made`, `client_facing_output_created`,
`financial_verification_made`, `capsule_publication_made`, `agent_execution_made`,
`mock_agent_execution_made`, `llm_call_made`, `agentnet_call_made`, `resolver_call_made`,
`network_call_made`.

### What a result never echoes

Results **never echo** raw note text, packet payloads, raw evidence text, raw interview text,
source bytes, generated agent output, final client-facing report prose, final recommendations
prose, LLM prompts, credentials or secrets, DSNs, raw SQL, stack traces, client-use approval
decisions, ROI / savings calculations or verified financial claims, AgentNet publish payloads,
resolver credentials, or capsule payloads.

Only refs, ids, closed-vocabulary statuses, counts, and safe reason codes are returned. Stored
values are never echoed: a blocker names the field and the **expected** value, not what was found.
Stored labels are echoed only when they fall inside a closed known-safe vocabulary; anything else
becomes `<unrecognized>`. Caller-supplied strings are scanned with the public Phase 32
`classify_prohibited_value_marker`, and only the marker *category* is ever reported.

---

## Determinism

Given the same database state and the same request, the result is identical: decision rows are
ordered by `id`, distinct positions are taken in first-seen order, no random id is generated, no
current timestamp is read, and nothing is mutated.

---

## Managed MySQL posture

The operational data store is **managed remote MySQL** under **Client Isolation Option A**; see
[MANAGED_MYSQL_PERSISTENCE_RUBRIC.md](MANAGED_MYSQL_PERSISTENCE_RUBRIC.md) and
[PRODUCTION_PARITY_DB_VALIDATION.md](PRODUCTION_PARITY_DB_VALIDATION.md). The temporary SQLite
database used by the Phase 40 harness is a fast local **structural smoke** path only — **SQLite is
not the production-readiness proof path**, and managed MySQL test/staging validation is required
before treating DB-backed functionality as production-ready. Phase 40 adds no migration, so it
introduces no new identifier-length or index-name risk in managed MySQL.

## AgentNet publication policy

Unchanged by Phase 40. The client authorizes **Peak** as the publisher through the consulting
agreement; **clients operate no AgentNet publishing tools**, hold no publishing credentials, and
have no direct publication path. See
[PEAK_OPERATED_AGENTNET_PUBLICATION_POLICY.md](PEAK_OPERATED_AGENTNET_PUBLICATION_POLICY.md). This
layer makes no AgentNet, MCP, or resolver call of any kind.

---

## Validation

```bash
make validate-phase40                            # structural + DB-free always
make validate-phase40 PYTHON=.venv/bin/python    # adds the temporary-SQLite behavior layer
```

The harness asserts the baseline (`012` head, 18 tables, 13 allowlist tables / 15 actions, no
migration `013`, no new table/model/writer/allowlist pair), the structural boundary (no writer
import or call, no `session.add`/`delete`/`merge`/`flush`/`commit`, no raw SQL, no
AgentNet/MCP/resolver/LLM/agent import), and real behavior against a temporary SQLite database over
a genuine Phase 37 → 38 → 39 chain — including **byte-for-byte proof that the packet and
report-draft rows are unchanged** after a summary, the awaiting-decision path, the
conflicting-decisions path, every stored-record blocker, and non-echoing content safety.

## Related

- [INTERNAL_ASSESSMENT_REPORT_DRAFT_CONTROLLED_WRITER.md](INTERNAL_ASSESSMENT_REPORT_DRAFT_CONTROLLED_WRITER.md) — Phase 37
- [INTERNAL_REPORT_REVIEW_PACKET_CONTROLLED_WRITER.md](INTERNAL_REPORT_REVIEW_PACKET_CONTROLLED_WRITER.md) — Phase 38
- [INTERNAL_REPORT_REVIEW_PACKET_DECISION_CONTROLLED_WRITER.md](INTERNAL_REPORT_REVIEW_PACKET_DECISION_CONTROLLED_WRITER.md) — Phase 39
- [MANAGED_RECORD_WORKFLOW_INTEGRATION.md](MANAGED_RECORD_WORKFLOW_INTEGRATION.md) — Phase 35 (the gated write-path sibling)
- [WORKFLOW_INTEGRATION_GOVERNANCE_POLICY.md](WORKFLOW_INTEGRATION_GOVERNANCE_POLICY.md)
- [CONTROLLED_DB_WRITER_BOUNDARY.md](CONTROLLED_DB_WRITER_BOUNDARY.md) and
  [CONTROLLED_WRITE_ALLOWLIST.md](CONTROLLED_WRITE_ALLOWLIST.md)
