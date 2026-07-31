# Internal Report Review Packet Controlled Writer (Phase 38)

The **tenth** narrow live DB writer. It persists **exactly one** `internal_report_review_packets`
row from an `InternalReportReviewPacketDraft`, through the Phase 17 `ControlledWriteRequest`
boundary, allowing only `internal_report_review_packets` /
`create_internal_report_review_packet`.

Implementation: [`peak/db/internal_report_review_packet_writer.py`](../peak/db/internal_report_review_packet_writer.py).
Idempotency: [`INTERNAL_REPORT_REVIEW_PACKET_IDEMPOTENCY_POLICY.md`](INTERNAL_REPORT_REVIEW_PACKET_IDEMPOTENCY_POLICY.md).

---

## What is stored: a reviewer packet, not a review outcome

A row is the **internal-only review packet** handed to a Peak human reviewer for a Phase 37
[`internal_assessment_report_drafts`](INTERNAL_ASSESSMENT_REPORT_DRAFT_CONTROLLED_WRITER.md) row. It
records *what the reviewer was shown and asked to evaluate*: a section review checklist,
reference-only evidence traces, open gaps, blocked items, short internal reviewer questions, a
readiness checklist, required follow-up actions, and future-gate placeholders.

**A packet is not a decision.** `packet_status` is fixed at **`ready_for_internal_review`** and
`reviewer_decision_status` at **`not_decided`**; `reviewer_decision_record_id` must be absent at
creation and is populated only by a later controlled path. A stored row can never be misread as a
review outcome.

**Never stored:** final client-facing report prose, final recommendation prose, raw intake note
text, raw packet payload, raw evidence text, raw interview text, source bytes, generated agent
output, LLM prompts, credentials or secrets, DSNs, raw SQL, stack traces, approval decisions, ROI or
savings calculations or verified financial claims, capsule payloads, AgentNet publish payloads, or
resolver credentials.

---

## Public entry point

```python
from peak.db.internal_report_review_packet_writer import (
    build_internal_report_review_packet_write_request,
    persist_internal_report_review_packet,
)

cwr = build_internal_report_review_packet_write_request(
    draft, requested_by="consultant_a", requester_role="consultant",
    idempotency_key="idem-packet-1")
receipt = persist_internal_report_review_packet(cwr, session_factory=None)
# -> InternalReportReviewPacketWriteReceipt
```

`session_factory` is a zero-arg callable returning a SQLAlchemy `Session` (defaults to the
controlled-DB session factory from the environment URL). Expected governance failures are **typed
denials, not exceptions**.

---

## Write-time authorization

The stored `Engagement` row is the authorization subject, exactly as in every prior DB-backed
writer. The gate loads it from the database and requires **all** of:

- the engagement exists;
- `engagement.authorization_scope` is present;
- `request.authorization_scope == engagement.authorization_scope`;
- `engagement.owner_id == request.owner_id`;
- `engagement.client_id == request.client_id`;
- `engagement.id == request.engagement_id`;
- `engagement.lifecycle_status` is not `revoked` / `archived` / `deleted_reference_only`.

**The stored engagement is authoritative** and **identity matching is necessary but not
sufficient** — the scope comparison is the gate. The packet draft is never the authorization source.

### Report-draft linkage: mode B (the stored row is read)

This writer uses **linkage mode B**: it loads the referenced
`InternalAssessmentReportDraftRecord` from the database and verifies it, rather than trusting a
caller-supplied reference. A plain ref proves nothing about stored posture, and the packet's whole
purpose is to describe a *real* report draft a reviewer will look at.

The stored draft must satisfy:

| Check | Requirement |
|---|---|
| existence | the row exists (`missing_report_draft` otherwise) |
| tenant | `owner_id` / `client_id` / `engagement_id` match the request |
| scope | `authorization_scope` matches the request |
| audience | `internal` |
| output status | `plan_persisted` |
| review status | `needs_review` |
| lifecycle status | `draft` |
| posture | `client_facing_approved` / `financial_verified` / `capsule_candidate_ready` / `publication_allowed` / `execution_allowed` all false |
| human review | `requires_human_review` is true |
| provenance | the draft's `report_plan_id` and `plan_fingerprint` match the packet's claims; a supplied `report_draft_payload_fingerprint` must match the stored `payload_fingerprint` |

`report_draft_payload_fingerprint` is then copied **from the stored row**, so the packet records the
report-draft payload it was actually built against.

### Exact write-time sequence

1. **Pre-DB (no connection opened on denial):** request type → Phase 17 `prepare_controlled_write`
   revalidation → table/action allowlist → `record_draft` is an `InternalReportReviewPacketDraft` →
   no caller-supplied server-controlled fields → prohibited draft attribute names → internal-only
   pre-decision posture → structural bounds → reference/value/checklist/question safety →
   report-draft linkage refs and fingerprints → short safe labels → idempotency key → required
   identity fields → subject present and supported → request↔draft↔subject identity consistency.
2. **DB:** load stored `Engagement` → stored-scope comparison → stored identity comparison →
   stored lifecycle check.
3. **DB:** load the stored Phase 37 report draft → tenant / scope / posture / provenance checks.
4. **Idempotency pre-check** on `(owner_id, client_id, engagement_id, idempotency_key)`.
5. **Insert exactly one row**, then commit; an `IntegrityError` re-queries inline to classify the
   race as replay / conflict / uncertain.
6. **Typed receipt.** No other table is written.

---

## Internal-only, pre-decision posture

Every stored packet is **review-gated**: it exists to be read by a human reviewer and carries no
authority of its own. These values are **server-stamped**, never copied from the caller:

| Column | Stored value |
|---|---|
| `audience` | `internal` |
| `packet_status` | `ready_for_internal_review` |
| `review_status` | `needs_review` |
| `lifecycle_status` | `draft` |
| `reviewer_decision_record_id` | `NULL` |
| `reviewer_decision_status` | `not_decided` |
| `client_facing_approved` | `false` |
| `review_approval_made` | `false` |
| `financial_verified` | `false` |
| `capsule_candidate_ready` | `false` |
| `publication_allowed` | `false` |
| `execution_allowed` | `false` |
| `requires_human_review` | `true` |

The writer denies a caller-supplied `review_packet_id` / `created_at`, a non-internal `audience`, a
`packet_status` other than `ready_for_internal_review`, a `review_status` other than
`needs_review`, a `lifecycle_status` other than `draft`, a `reviewer_decision_status` other than
`not_decided`, a supplied `reviewer_decision_record_id`, any elevated posture flag, or
`requires_human_review=false`.

---

## What the row persists

| Column | Content |
|---|---|
| `internal_assessment_report_draft_id`, `source_report_draft_table` | Phase 37 linkage (verified against the stored row) |
| `report_plan_id`, `plan_fingerprint`, `report_draft_payload_fingerprint` | provenance (safe refs / digests) |
| `requested_by`, `requester_role`, `assigned_reviewer` | requester and reviewer labels |
| `packet_purpose` | short safe internal label (optional) |
| `section_review_checklist_json` | `{section_id, check_id, status}` items |
| `evidence_trace_refs_json` | **record ids only** |
| `open_gaps_json`, `blocked_items_json` | safe item ids |
| `reviewer_questions_json` | short single-line internal prompts |
| `readiness_checklist_json` | `{check_id, status}` items |
| `required_followup_actions_json` | `{action_id, status}` items |
| `future_financial_verification_items_json` | ids naming a **future** gate |
| `future_capsule_candidate_items_json` | refs naming a **future** gate |
| `reasons_json`, `warnings_json` | sanitized, bounded, single-line notes |
| `idempotency_key`, `payload_fingerprint` | replay/conflict detection |
| `details_json` | source phase + safe structural counts |

### Checklist and status vocabularies

Checklist items are **strict dicts** — any key outside the declared set is denied. Statuses come
from a closed allowlist so an approval-flavoured status can never be stored:

- section review and readiness checks: `not_started`, `in_review`, `needs_followup`, `complete`
- follow-up actions: `open`, `in_progress`, `blocked`, `done`

Nothing in either vocabulary implies approval, sign-off, publication, financial verification, or a
client-facing outcome.

### Bounds

`section_review_checklist` ≤ 200 · `reviewer_questions` ≤ 100 · `readiness_checklist` ≤ 100 ·
`required_followup_actions` ≤ 200 · `open_gaps` ≤ 500 · `blocked_items` ≤ 500 ·
`evidence_trace_refs` ≤ 2000 · future-gate lists ≤ 500. Exceeding any bound denies the write
(`packet_too_large`) before a connection is opened.

---

## Content and leakage safety

Every persisted reference and label must be a short safe id (`^[A-Za-z0-9_.:/-]{1,128}$` — no
whitespace, no newline, no quotes) carrying no credential / DSN / raw-SQL / raw-content /
stack-trace / JSON-dump marker. Values are classified with the public, DB-free Phase 32
`classify_prohibited_value_marker` plus a local stack-trace matcher.

**Unexpected** draft attributes (anything bolted on beyond the declared dataclass fields) are
name-scanned against prohibited raw-content, DB-artifact, credential, and approval/publication/
client-facing/financial intent markers.

**Reviewer questions** are the only prose-ish list a packet carries, so they get an extra guard: at
most 240 characters, single-line, marker-scanned, **and** intent-scanned. A question containing
client-facing or approval language (`send to client`, `client deliverable`, `final report`,
`approve for client`, `sign off`, `publish capsule`, `roi of`, `verified savings`, …) is denied with
`prohibited_packet_intent`. `packet_purpose` and `assigned_reviewer` are scanned the same way.

**Receipts and denial reasons never echo a value** — only a field name, an item position, or a
marker category.

---

## Receipt

`InternalReportReviewPacketWriteReceipt` reports `outcome` (`created` / `idempotent_replay` /
`denied` / `failed_before_write` / `write_outcome_uncertain`), `permitted`, `reason_code`,
`target_table`, `target_action`, `stored_record_id`, `internal_assessment_report_draft_id`,
`report_plan_id`, `plan_fingerprint`, `idempotency_key`, `audit_trace_ref`, the actual-behavior
flags (`database_connection_made`, `sql_execution_made`, `database_write_made`,
`stored_record_created`, `existing_record_returned`, `transaction_committed`, `outcome_uncertain`),
the posture labels (`audience`, `packet_status`, `review_status`, `lifecycle_status`,
`reviewer_decision_status`), the safe structural counts (`section_review_item_count`,
`reviewer_question_count`, `readiness_check_item_count`, `required_followup_action_count`,
`open_gap_count`, `evidence_trace_ref_count`), `created_at` / `database_write_at`, `reasons`, and
`warnings`.

The following are **always false**: `review_records_write_made`, `agent_run_records_write_made`,
`review_approval_made`, `client_facing_output_created`, `client_facing_approval_made`,
`financial_verification_made`, `capsule_candidate_created`, `capsule_publication_made`,
`agentnet_publication_made`, `agent_execution_made`, `mock_agent_execution_made`, `llm_call_made`,
`agentnet_call_made`, `resolver_call_made`, `network_call_made`.

Every flag reports **actual** behavior: a denial before any connection reports no connection and no
SQL; an idempotent replay reports reads but no new record; an uncertain outcome never falsely claims
no record exists.

---

## Schema

Migration [`011_internal_report_review_packets`](../alembic/versions/011_internal_report_review_packets.py)
(`down_revision = 010_internal_assessment_report_drafts`) creates exactly one table with **no INSERT
and no seed data**; the full downgrade drops only that table and its indexes/constraint. The Alembic
head stays single and linear, and `make db-check` now expects exactly **17 tables**.

Indexes cover `client_id`, `engagement_id`, `report_plan_id`, `plan_fingerprint`, `audience`,
`packet_status`, `reviewer_decision_record_id`, `idempotency_key`, the report-draft reference, and
the universal governance/audit columns. The DB-enforced idempotency boundary is a UNIQUE index over
`(owner_id, client_id, engagement_id, idempotency_key)`.

**Index-name note.** The report-draft reference is indexed as
`ix_internal_report_review_packets_report_draft`, not the convention-derived
`ix_internal_report_review_packets_internal_assessment_report_draft_id` — that name is 69
characters, over MySQL's 64-character identifier limit. SQLite accepts the long name silently, so
the short name is pinned in both the model and the migration rather than discovered in managed
MySQL. This is a concrete example of why **SQLite is only a fast local structural smoke path — not
the production-readiness proof path**.

This table is an operational table: **managed remote MySQL is the operational data store**, with
**Client Isolation Option A** (a shared managed database per environment plus strict tenant columns
and authorization gates) as the default — every row carries `owner_id`, `client_id`,
`engagement_id`, and `authorization_scope`. Managed MySQL test/staging validation is required before
treating this writer as production-ready, and the production DB is not the main smoke-test target.
See [`PRODUCTION_PARITY_DB_VALIDATION.md`](PRODUCTION_PARITY_DB_VALIDATION.md) and
[`MANAGED_MYSQL_PERSISTENCE_RUBRIC.md`](MANAGED_MYSQL_PERSISTENCE_RUBRIC.md).

---

## Phase 17 allowlist

Phase 38 adds exactly **one** table/action pair: `internal_report_review_packets` /
`create_internal_report_review_packet`. No update, delete, upsert, or raw-SQL action is added. See
[`CONTROLLED_WRITE_ALLOWLIST.md`](CONTROLLED_WRITE_ALLOWLIST.md).

---

## What this writer never does

No final client report, client-facing deliverable, client-facing approval, `approve_internal`,
`approve_client_facing`, `send_to_client`, `publish_report`, report export, PDF/DOCX generation,
financial verification, ROI/savings verification, capsule candidate persistence, capsule
publication, AgentNet publish operation, AgentNet resolver call, MCP call, live or mock LLM call,
agent or mock-agent execution, generic CRUD, generic DB writer, arbitrary SQL executor, broad
repository, API, frontend, production DB write path, or cleanup/delete path. It calls **no Phase 22
review writer** and creates **no `review_records` or `agent_run_records` row**.

**AgentNet publication remains Peak-operated and deferred** — see
[`PEAK_OPERATED_AGENTNET_PUBLICATION_POLICY.md`](PEAK_OPERATED_AGENTNET_PUBLICATION_POLICY.md).

---

## Validation

```bash
make validate-phase38   # DB-backed via .venv (temporary SQLite structural smoke)
```
