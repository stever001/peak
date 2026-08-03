# Internal Report Review Packet Decision Controlled Writer (Phase 39)

The **eleventh** narrow live DB writer. It persists **exactly one**
`internal_report_review_packet_decisions` row — a Peak human reviewer's **internal-only decision**
on a Phase 38 `internal_report_review_packets` row — through the Phase 17 `ControlledWriteRequest`
boundary, allowing only `internal_report_review_packet_decisions` /
`create_internal_report_review_packet_decision`.

Implementation: [`peak/db/internal_report_review_packet_decision_writer.py`](../peak/db/internal_report_review_packet_decision_writer.py).
Idempotency: [`INTERNAL_REPORT_REVIEW_PACKET_DECISION_IDEMPOTENCY_POLICY.md`](INTERNAL_REPORT_REVIEW_PACKET_DECISION_IDEMPOTENCY_POLICY.md).

---

## Why a new table rather than reusing Phase 33

Phase 39 was first specified as a *bridge* over the existing Phase 33
[`internal_reviewer_decision_records`](INTERNAL_REVIEWER_DECISION_CONTROLLED_WRITER.md) writer. That
was verified empirically and **does not work**. Three concrete blockers:

1. **The honest shape is rejected.** The Phase 33 writer hard-requires `review_bundle_ref` or
   `review_bundle_record_id`. A packet decision has neither — the packet references a *report
   draft*, not a review bundle, and `internal_report_review_packets` has no bundle column at all.
   Running it returns `denied / missing_review_bundle_ref`.
2. **Packet linkage cannot be persisted.** Phase 33's `_build_record` is an explicit field mapping
   with a **closed** `details_json` key set. Packet / report-draft / plan / fingerprint refs
   attached to the draft are **silently dropped** — verified: none of them appear in the stored row.
3. **The audit question becomes unanswerable.** A decision written that way could not answer *which
   review packet was this decision about?* — the entire point of the phase.

The only workarounds were to write a packet id into `review_bundle_record_id` (a column named,
documented, and **indexed** as a `review_bundle_records` reference — semantic corruption of an
existing audit column) or to drop the linkage entirely. Neither is safe representation, so a
separate narrow table was approved.

**Phase 33 is untouched.** It remains the writer for review-bundle reviewer decisions.

---

## Public entry point

```python
from peak.db.internal_report_review_packet_decision_writer import (
    build_packet_decision_write_request,
    persist_internal_report_review_packet_decision,
)

cwr = build_packet_decision_write_request(
    draft, requested_by="consultant_a", requester_role="consultant",
    idempotency_key="idem-decision-1")
receipt = persist_internal_report_review_packet_decision(cwr, session_factory=None)
# -> InternalReportReviewPacketDecisionWriteReceipt
```

Expected governance failures are **typed denials, not exceptions**.

---

## Decision intent vocabulary

The writer reuses the **closed Phase 32 vocabulary** (`ALLOWED_DECISION_INTENTS`) verbatim — it
invents nothing:

`needs_more_evidence` · `return_for_revision` · `ready_for_internal_use` · `blocked_by_scope` ·
`blocked_by_quality` · `blocked_by_missing_source` · `rejected_for_policy` · `defer_review`

**`ready_for_internal_use` is internal readiness, not client-facing approval.** Because the
vocabulary is a closed set, approval-like and external-facing intents (`approve_client_facing`,
`approve_internal`, `send_to_client`, `publish_report`, `final_client_report`,
`approve_financial_claims`, `publish_capsule`, `agentnet_publish`, `execute_agent`, `call_llm`,
`resolver_lookup`) are denied automatically with `disallowed_decision_intent`.

### `decision_status` is server-derived

`decision_status` is derived deterministically from `decision_intent` and is **never**
caller-supplied:

| Intent | `decision_status` |
|---|---|
| `needs_more_evidence`, `return_for_revision`, `blocked_by_scope`, `blocked_by_quality`, `blocked_by_missing_source`, `defer_review` | `needs_followup` |
| `ready_for_internal_use`, `rejected_for_policy` | `decision_recorded` |

**Why a separate column.** `review_status` and `lifecycle_status` are universal governance axes
whose canonical source is the Phase 9 schemas. Writing `decision_recorded` / `needs_followup` into
`review_status` would put non-vocabulary values on a governed axis. So the governed axes stay
`needs_review` / `draft` (matching Phase 33's decision records), and the decision-specific state
lives on its own `decision_status` column.

---

## Write-time authorization

The stored `Engagement` row is the authorization subject. The gate loads it and requires **all** of:

- the engagement exists;
- `engagement.authorization_scope` is present;
- `request.authorization_scope == engagement.authorization_scope`;
- `engagement.owner_id` / `client_id` / `id` match the request;
- `engagement.lifecycle_status` is not `revoked` / `archived` / `deleted_reference_only`.

**The stored engagement is authoritative** and **identity matching is necessary but not
sufficient** — the scope comparison is the gate.

### Stored packet validation (read-only)

The referenced `InternalReportReviewPacketRecord` is **loaded and verified**, never trusted from the
ref alone:

| Check | Requirement |
|---|---|
| existence | the row exists (`missing_packet` otherwise) |
| tenant / scope | `owner_id` / `client_id` / `engagement_id` / `authorization_scope` match the request |
| linkage | `internal_assessment_report_draft_id`, `report_plan_id`, `plan_fingerprint` match the decision draft; a supplied `packet_payload_fingerprint` matches the stored `payload_fingerprint` |
| audience | `internal` |
| packet status | `ready_for_internal_review` |
| review / lifecycle | `needs_review` / `draft` |
| pre-decision | `reviewer_decision_status == not_decided` **and** `reviewer_decision_record_id IS NULL` |
| posture | `client_facing_approved` / `review_approval_made` / `financial_verified` / `capsule_candidate_ready` / `publication_allowed` / `execution_allowed` all false |
| human review | `requires_human_review` is true |

### Stored report-draft validation (read-only)

The Phase 37 `InternalAssessmentReportDraftRecord` the packet points at is **also** loaded and
verified — defence in depth, and cheap since the session is already open: existence, id matching the
packet's reference, tenant/scope, `report_plan_id` / `plan_fingerprint` matching the decision draft,
a supplied `report_draft_payload_fingerprint` matching the stored one, `audience=internal`,
`output_status=plan_persisted`, `review_status=needs_review`, `lifecycle_status=draft`, every
non-elevated posture flag, and `requires_human_review=true`.

Both `packet_payload_fingerprint` and `report_draft_payload_fingerprint` are then copied **from the
stored rows**, so the decision records the exact artifacts it was made against.

### Exact write-time sequence

1. **Pre-DB (no connection opened on denial):** request type → Phase 17 revalidation → table/action
   allowlist → `record_draft` type → no caller-supplied server-controlled fields → prohibited draft
   attribute names → internal-only posture → structural bounds → reference/action/summary safety →
   closed decision-intent vocabulary → required audit-chain refs and fingerprint shapes →
   idempotency key → required identity fields → subject → request↔draft↔subject consistency.
2. **DB (read):** stored `Engagement` → scope, identity, lifecycle.
3. **DB (read):** stored packet → tenant, scope, linkage, pre-decision posture.
4. **DB (read):** stored report draft → tenant, scope, linkage, posture.
5. **Idempotency pre-check** on `(owner_id, client_id, engagement_id, idempotency_key)`.
6. **Insert exactly one row**, then commit; an `IntegrityError` re-queries inline to classify the
   race as replay / conflict / uncertain.
7. **Typed receipt.** No other row is written **or updated**.

---

## The packet and report-draft rows are never updated

Phase 39 is insert-only. It performs three reads and one insert. It does **not** set the packet's
`reviewer_decision_record_id`, does not advance `reviewer_decision_status`, and does not touch the
report draft. Linking a packet back to its decision is deliberately left to a later controlled path;
the receipt reports `packet_row_updated=false` and `report_draft_row_updated=false`, and the tests
assert both rows are byte-for-byte unchanged after a decision is written.

---

## Internal-only posture

Every stored decision is **review-gated** and carries no authority of its own. These values are
**server-stamped**, never copied from the caller:

| Column | Stored value |
|---|---|
| `audience` | `internal` |
| `decision_scope` | `internal_report_review_packet` |
| `decision_status` | derived from `decision_intent` (see above) |
| `review_status` | `needs_review` |
| `lifecycle_status` | `draft` |
| `client_facing_approved` | `false` |
| `review_approval_made` | `false` |
| `financial_verified` | `false` |
| `capsule_candidate_ready` | `false` |
| `publication_allowed` | `false` |
| `execution_allowed` | `false` |
| `requires_human_review` | `true` |

The writer denies a caller-supplied `decision_record_id` / `created_at`, a non-internal `audience`,
any elevated posture flag, or `requires_human_review=false`.

---

## What the row persists

| Column | Content |
|---|---|
| `internal_report_review_packet_id`, `source_packet_table` | Phase 38 linkage (verified against the stored row) |
| `internal_assessment_report_draft_id`, `source_report_draft_table` | Phase 37 linkage (verified) |
| `report_plan_id`, `plan_fingerprint` | Phase 36 provenance |
| `packet_payload_fingerprint`, `report_draft_payload_fingerprint` | copied from the stored rows |
| `requested_by`, `requester_role`, `reviewer_ref` | requester and reviewer labels |
| `decision_intent` | closed Phase 32 vocabulary |
| `safe_decision_summary` | one short single-line internal note (optional) |
| `requested_followup_actions_json` | `{action_id, status}` items |
| `decision_status`, `decision_scope`, `audience` | server-stamped |
| `reasons_json`, `warnings_json` | sanitized, bounded, single-line notes |
| `idempotency_key`, `payload_fingerprint` | replay/conflict detection |
| `details_json` | source phase + safe action count |

Follow-up actions are **strict dicts** — any key outside `{action_id, status}` is denied — with a
closed status allowlist: `open`, `in_progress`, `blocked`, `done`. Nothing in that vocabulary
implies approval, publication, or financial verification.

**Bounds:** `requested_followup_actions` ≤ 200, `reasons` ≤ 100, `warnings` ≤ 100,
`safe_decision_summary` ≤ 240 chars single-line, notes ≤ 500 chars.

**Never stored:** final client-facing report prose, final recommendation prose, raw intake note
text, raw packet payload, raw evidence text, raw interview text, source bytes, generated agent
output, LLM prompts, credentials or secrets, DSNs, raw SQL, stack traces, client-facing approvals,
ROI or savings calculations, capsule payloads, AgentNet publish payloads, or resolver credentials.

---

## Content and leakage safety

Every persisted reference and label must be a short safe id (`^[A-Za-z0-9_.:/-]{1,128}$`) carrying
no credential / DSN / raw-SQL / raw-content / stack-trace / JSON-dump marker, classified with the
public, DB-free Phase 32 `classify_prohibited_value_marker` plus a local stack-trace matcher.
**Unexpected** draft attributes are name-scanned against prohibited raw-content, DB-artifact,
credential, and approval/publication/client-facing/financial intent markers.

`safe_decision_summary`, `reasons`, and `warnings` get an extra **intent scan**: a note containing
client-facing, approval, publication, financial, or execution language (`send to client`,
`final report`, `approve for client`, `sign off`, `publish capsule`, `roi of`, `verified savings`,
`run the agent`, `call the llm`, `resolver lookup`, …) is denied with
`prohibited_decision_intent_language`.

**Receipts and denial reasons never echo a value** — only a field name, an item position, or a
marker category.

---

## Receipt

`InternalReportReviewPacketDecisionWriteReceipt` reports `outcome` (`created` /
`idempotent_replay` / `denied` / `failed_before_write` / `write_outcome_uncertain`), `permitted`,
`reason_code`, `target_table`, `target_action`, `stored_record_id`, the full audit chain
(`internal_report_review_packet_id`, `internal_assessment_report_draft_id`, `report_plan_id`,
`plan_fingerprint`), `decision_intent`, `idempotency_key`, `audit_trace_ref`, the actual-behavior
flags, the posture labels (`audience`, `decision_scope`, `decision_status`, `review_status`,
`lifecycle_status`), `requested_followup_action_count`, `created_at` / `database_write_at`,
`reasons`, and `warnings`.

The following are **always false**: `packet_row_updated`, `report_draft_row_updated`,
`review_records_write_made`, `agent_run_records_write_made`, `review_approval_made`,
`client_facing_output_created`, `client_facing_approval_made`, `financial_verification_made`,
`capsule_candidate_created`, `capsule_publication_made`, `agentnet_publication_made`,
`agent_execution_made`, `mock_agent_execution_made`, `llm_call_made`, `agentnet_call_made`,
`resolver_call_made`, `network_call_made`.

---

## Schema

Migration [`012_internal_report_review_packet_decisions`](../alembic/versions/012_internal_report_review_packet_decisions.py)
(`down_revision = 011_internal_report_review_packets`) creates exactly one table with **no INSERT
and no seed data**; the full downgrade drops only that table and its indexes/constraint. The Alembic
head stays single and linear, and `make db-check` now expects exactly **18 tables**.

**Index-name note.** The table name is 39 characters, so the convention-derived
`ix_internal_report_review_packet_decisions_<col>` would reach **78** characters for the longest
columns — over MySQL's 64-character identifier limit. Every index therefore uses the short explicit
`ix_irrpd_<col>` prefix (max 44). This applies the Phase 38 finding proactively rather than
discovering it in managed MySQL, and the harness asserts every identifier fits.

This table is an operational table: **managed remote MySQL is the operational data store**, with
**Client Isolation Option A** as the default — every row carries `owner_id`, `client_id`,
`engagement_id`, and `authorization_scope`. Managed MySQL test/staging validation is required before
treating this writer as production-ready; the production DB is not the main smoke-test target. See
[`PRODUCTION_PARITY_DB_VALIDATION.md`](PRODUCTION_PARITY_DB_VALIDATION.md) and
[`MANAGED_MYSQL_PERSISTENCE_RUBRIC.md`](MANAGED_MYSQL_PERSISTENCE_RUBRIC.md).

---

## Phase 17 allowlist

Phase 39 adds exactly **one** table/action pair: `internal_report_review_packet_decisions` /
`create_internal_report_review_packet_decision` (13 tables / 15 actions). No update, delete, upsert,
or raw-SQL action. See [`CONTROLLED_WRITE_ALLOWLIST.md`](CONTROLLED_WRITE_ALLOWLIST.md).

---

## What this writer never does

No final client report, client-facing deliverable, client-facing approval, `approve_client_facing`,
`send_to_client`, `publish_report`, report export, PDF/DOCX generation, financial verification,
ROI/savings verification, capsule candidate persistence, capsule publication, AgentNet publish
operation, AgentNet resolver call, MCP call, live or mock LLM call, agent or mock-agent execution,
generic CRUD, generic decision system, update/delete/upsert path, arbitrary SQL executor, broad
repository, API, frontend, production DB write path, or cleanup/delete path. It calls **no Phase 22
review writer** and creates **no `review_records` or `agent_run_records` row**.

**AgentNet publication remains Peak-operated and deferred** — see
[`PEAK_OPERATED_AGENTNET_PUBLICATION_POLICY.md`](PEAK_OPERATED_AGENTNET_PUBLICATION_POLICY.md).

---

## Validation

```bash
make validate-phase39   # DB-backed via .venv (temporary SQLite structural smoke)
```

---

## Phase 40 — how the insert-only packet-row gap is closed

This writer is insert-only: it records *which* review packet was decided but deliberately never
updates the Phase 38 packet row's `reviewer_decision_status` / `reviewer_decision_record_id`. That
is intentional, and it stays that way.

Phase 40 closes the resulting operational gap by **derivation, not mutation**: the read-only
`summarize_internal_report_review_workflow` entry point computes the current internal review state
from the rows in this table, and never writes to the packet row, this table, or anything else. A
stored packet row whose decision columns the located decision records cannot explain is reported as
a blocker rather than repaired. See
[`INTERNAL_REPORT_REVIEW_WORKFLOW_INTEGRATION.md`](INTERNAL_REPORT_REVIEW_WORKFLOW_INTEGRATION.md).
