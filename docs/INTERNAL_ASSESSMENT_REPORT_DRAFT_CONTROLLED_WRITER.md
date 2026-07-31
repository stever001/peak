# Internal Assessment Report Draft Controlled Writer (Phase 37)

The **ninth** narrow live DB writer and the persistence counterpart to the Phase 36 DB-free
[internal assessment report planning boundary](INTERNAL_ASSESSMENT_REPORT_PLANNING_BOUNDARY.md).

It persists **exactly one** `internal_assessment_report_drafts` row from a Phase 36
`InternalAssessmentReportPlan`, through the Phase 17 `ControlledWriteRequest` boundary, allowing
only `internal_assessment_report_drafts` / `create_internal_assessment_report_draft`.

Implementation: [`peak/db/internal_assessment_report_draft_writer.py`](../peak/db/internal_assessment_report_draft_writer.py).
Idempotency: [`INTERNAL_ASSESSMENT_REPORT_DRAFT_IDEMPOTENCY_POLICY.md`](INTERNAL_ASSESSMENT_REPORT_DRAFT_IDEMPOTENCY_POLICY.md).

---

## What is stored: a persisted *plan*, not a drafted report

This is the single most important property of the table. A row holds the **structure and
traceability** of an internal assessment report — section metadata, reference-only evidence traces,
finding and recommendation candidate slots, open gaps, blocked items, and future-gate placeholders.

`output_status` is fixed at **`plan_persisted`** — a deliberate, documented choice so that a stored
row can never be misread as report prose. The Phase 36 plan's own `output_status` is `plan`; the
stored row records that this plan has been persisted, and nothing more.

**Never stored:** final client-facing report prose, final recommendation prose, raw intake note
text, raw packet payload, raw evidence text, raw interview text, source bytes, generated agent
output, LLM prompts, credentials or secrets, DSNs, raw SQL, stack traces, approval decisions, ROI or
savings calculations or verified financial claims, capsule payloads, AgentNet publish payloads, or
resolver credentials.

---

## Public entry point

```python
from peak.db.internal_assessment_report_draft_writer import (
    build_internal_assessment_report_draft_write_request,
    persist_internal_assessment_report_draft,
)

cwr = build_internal_assessment_report_draft_write_request(
    plan, requested_by="consultant_a", requester_role="consultant",
    idempotency_key="idem-rpt-1")
receipt = persist_internal_assessment_report_draft(
    cwr, session_factory=None, report_request=None)
# -> InternalAssessmentReportDraftWriteReceipt
```

`session_factory` is a zero-arg callable returning a SQLAlchemy `Session` (defaults to the
controlled-DB session factory from the environment URL). `report_request` is an optional Phase 36
`InternalAssessmentReportPlanRequest`, accepted **only** for cross-checking — the write-time
authorization gate never trusts it.

When supplied, it must agree with the write request on `owner_id`, `client_id`, `engagement_id`, and
`authorization_scope`, **and it must describe this plan**: its effective report id (
`report_plan_id or idempotency_key`, mirroring Phase 36's own derivation) must equal
`plan.report_plan_id`. A cross-check request describing a different report plan is denied with
`identity_mismatch` before any connection is opened. Only field names are reported — neither
`report_plan_id` value is ever echoed.

Expected governance failures are **typed denials, not exceptions**.

### The CWR bridge lives in the DB layer, by design

`build_internal_assessment_report_draft_write_request` is defined in the **Phase 37 DB module**, not
in `peak/reports`. This mirrors the Phase 33/34 precedent and keeps the Phase 36 `peak.reports`
package strictly **DB-free**: Phase 36 imports no `peak.db`, calls no writer, and remains a pure
planning boundary.

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
sufficient** — the scope comparison is the gate. The Phase 36 plan and request are never the
authorization source.

### Exact write-time sequence

1. **Pre-DB (no connection opened on denial):** request type → Phase 17 `prepare_controlled_write`
   revalidation → table/action allowlist → `record_draft` is an `InternalAssessmentReportPlan` →
   optional `report_request` identity **and provenance** cross-check → no caller-supplied
   server-controlled fields →
   prohibited plan attribute names → internal-only posture → reference/value safety → plan
   identity refs and labels → structural bounds → idempotency key → required identity fields →
   subject present and supported → request↔plan↔subject identity consistency.
2. **DB:** load stored `Engagement` → stored-scope comparison → stored identity comparison →
   stored lifecycle check.
3. **Idempotency pre-check** on `(owner_id, client_id, engagement_id, idempotency_key)`.
4. **Insert exactly one row**, then commit; an `IntegrityError` re-queries inline to classify the
   race as replay / conflict / uncertain.
5. **Typed receipt.** No other table is written.

---

## Internal-only posture

The stored row is review-gated, non-final, and internal only. These are **server-stamped**, never
copied from the caller:

| Column | Stored value |
|---|---|
| `audience` | `internal` |
| `output_status` | `plan_persisted` |
| `review_status` | `needs_review` |
| `lifecycle_status` | `draft` |
| `client_facing_approved` | `false` |
| `financial_verified` | `false` |
| `capsule_candidate_ready` | `false` |
| `publication_allowed` | `false` |
| `execution_allowed` | `false` |
| `requires_human_review` | `true` |

The writer independently re-verifies the Phase 36 posture before writing and denies a caller-supplied
`report_draft_id` / `created_at` / `id`, a non-internal `audience`, a plan `output_status` other than
`plan`, a `review_status` other than `needs_review`, a `lifecycle_status` other than `draft`, any
elevated posture flag, or `requires_human_review=false`. Every recommendation and finding candidate
inside the plan must itself carry the internal-only posture.

---

## What the row persists

| Column | Content |
|---|---|
| `report_plan_id`, `plan_fingerprint` | Phase 36 provenance (safe refs) |
| `requested_by`, `requester_role` | requester traceability |
| `report_purpose` | short safe internal label (optional) |
| `sections_json` | section id, fixed title, order, readiness, ref categories, counts, blocked reason |
| `evidence_trace_map_json` | per-section supporting **record ids only** + missing categories |
| `finding_candidates_json` | candidate id, section, evidence/review **refs**, readiness, blocked reason |
| `recommendation_candidates_json` | candidate id, section, decision/review/evidence **refs**, readiness, internal-only posture |
| `open_gaps_json` | gap id, kind, section, missing category, missing record type, note |
| `blocked_items_json` | safe item ids |
| `future_financial_verification_items_json` | recommendation ids naming a **future** gate |
| `future_capsule_candidate_items_json` | refs naming a **future** gate |
| `reasons_json`, `warnings_json` | sanitized, bounded, single-line notes |
| `idempotency_key`, `payload_fingerprint` | replay/conflict detection |
| `details_json` | source phase + safe structural counts |

Every reference persisted into a JSON column is verified to be a short safe id
(`^[A-Za-z0-9_.:/-]{1,128}$`, no whitespace, no newline, no quotes) carrying no credential / DSN /
raw-SQL / raw-content / stack-trace / JSON-dump marker. Free-text-ish fields (fixed section titles,
gap notes, blocked reasons, reasons, warnings) are bounded to 500 characters, single-line, and
marker-scanned. Structural bounds cap the plan at 64 sections, 500 candidates per family, and 500
gaps so a JSON column cannot grow unbounded.

---

## Content and leakage safety

The writer scans **unexpected** plan attributes (anything bolted on beyond the declared dataclass
fields) against prohibited name markers: raw note/packet/evidence/interview/source/generated-output
terms, DB-URL/DSN/raw-SQL/stack-trace terms, credential/secret terms, and approval / publication /
client-facing / financial-verification intent terms. Declared plan fields are known-safe structural
fields whose values are validated explicitly.

Values are classified with the public, DB-free Phase 32 `classify_prohibited_value_marker` plus a
local stack-trace matcher. On prose-ish fields a bare `JSON/object` verdict is narrowed to values
that genuinely look like a dumped object/array, so a legitimate worker-generated title such as
`"[draft] visual_observation"` passes while an actual JSON dump fails.

**Receipts and denial reasons never echo a value** — only a field name, a reference position, or a
marker category.

---

## Receipt

`InternalAssessmentReportDraftWriteReceipt` reports `outcome` (`created` / `idempotent_replay` /
`denied` / `failed_before_write` / `write_outcome_uncertain`), `permitted`, `reason_code`,
`target_table`, `target_action`, `stored_record_id`, `report_plan_id`, `plan_fingerprint`,
`idempotency_key`, `audit_trace_ref`, the actual-behavior flags
(`database_connection_made`, `sql_execution_made`, `database_write_made`, `stored_record_created`,
`existing_record_returned`, `transaction_committed`, `outcome_uncertain`), the posture labels
(`audience`, `output_status`, `review_status`, `lifecycle_status`), the safe structural counts
(`section_count`, `finding_candidate_count`, `recommendation_candidate_count`, `open_gap_count`),
`created_at` / `database_write_at`, `reasons`, and `warnings`.

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

Migration [`010_internal_assessment_report_drafts`](../alembic/versions/010_internal_assessment_report_drafts.py)
(`down_revision = 009_intake_note_records`) creates exactly one table with **no INSERT and no seed
data**; the full downgrade drops only that table and its indexes/constraint. The Alembic head stays
single and linear, and `make db-check` now expects exactly **16 tables**.

Indexes cover `client_id`, `engagement_id`, `report_plan_id`, `plan_fingerprint`, `audience`,
`output_status`, `idempotency_key`, plus the universal governance/audit indexes. The DB-enforced
idempotency boundary is a UNIQUE index over
`(owner_id, client_id, engagement_id, idempotency_key)`.

This table is an operational table: **managed remote MySQL is the operational data store**, with
**Client Isolation Option A** (a shared managed database per environment plus strict tenant columns
and authorization gates) as the default — every row carries `owner_id`, `client_id`,
`engagement_id`, and `authorization_scope`.

**SQLite is only a fast local structural smoke path — not the production-readiness proof path.**
Managed MySQL test/staging validation is required before treating this writer as production-ready,
and the production DB is not the main smoke-test target.
See [`PRODUCTION_PARITY_DB_VALIDATION.md`](PRODUCTION_PARITY_DB_VALIDATION.md) and
[`MANAGED_MYSQL_PERSISTENCE_RUBRIC.md`](MANAGED_MYSQL_PERSISTENCE_RUBRIC.md).

---

## Phase 17 allowlist

Phase 37 adds exactly **one** table/action pair:
`internal_assessment_report_drafts` / `create_internal_assessment_report_draft`. No update, delete,
upsert, or raw-SQL action is added. See
[`CONTROLLED_WRITE_ALLOWLIST.md`](CONTROLLED_WRITE_ALLOWLIST.md).

---

## What this writer never does

No final client report, client-facing deliverable, client-facing approval, `approve_client_facing`,
`send_to_client`, `publish_report`, report export, PDF/DOCX generation, financial verification,
ROI/savings verification, capsule candidate persistence, capsule publication, AgentNet publish
operation, AgentNet resolver call, MCP call, live or mock LLM call, agent or mock-agent execution,
generic CRUD, generic DB writer, arbitrary SQL executor, broad repository, API, frontend, production
DB write path, or cleanup/delete path. It calls **no Phase 22 review writer** and creates **no
`review_records` or `agent_run_records` row**.

**AgentNet publication remains Peak-operated and deferred** — see
[`PEAK_OPERATED_AGENTNET_PUBLICATION_POLICY.md`](PEAK_OPERATED_AGENTNET_PUBLICATION_POLICY.md).

---

## Validation

```bash
make validate-phase37   # DB-backed via .venv (temporary SQLite structural smoke)
```
