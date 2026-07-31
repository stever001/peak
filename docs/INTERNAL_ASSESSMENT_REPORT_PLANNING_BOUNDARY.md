# Internal Assessment Report Assembly Planning Boundary (Phase 36)

A **DB-free planning layer** that assembles an internal assessment report **plan** from governed
record references and reviewer decisions.

The output is an **internal report assembly plan** — structure, traceability, and readiness. It is
**not** a report draft record and **not** a client-facing deliverable.

Implementation: [`peak/reports/`](../peak/reports/) —
[`contracts.py`](../peak/reports/contracts.py),
[`governance.py`](../peak/reports/governance.py),
[`internal_assessment_planner.py`](../peak/reports/internal_assessment_planner.py).
Governance rules: [`INTERNAL_REPORT_ASSEMBLY_GOVERNANCE_POLICY.md`](INTERNAL_REPORT_ASSEMBLY_GOVERNANCE_POLICY.md).

---

## What it is — and is not

**Is:** a deterministic planner that answers, from references alone —

- What sections should an internal assessment report contain?
- Which governed records support each section?
- Which evidence / review / reviewer-decision references are available?
- Which evidence gaps remain?
- Which recommendations are internal-only candidates?
- Which items are blocked from client-facing use?
- Which items would require **future** financial verification before any ROI/savings claim?
- Which items might **later** become capsule candidates, but are not publication-ready now?

**Is not:** a new DB table, model, or migration; a DB writer or report writer; generic CRUD; an
arbitrary SQL executor; a broad read/write repository; an API; a frontend; report-draft persistence;
client-facing report output; client-facing approval; final deliverable generation; financial or
ROI/savings verification; capsule publication or capsule-candidate persistence; an AgentNet publish
operation; an AgentNet resolver call; an MCP call; a live or mock LLM call; agent or mock-agent
execution; a production DB write path; or a cleanup/delete path.

**It generates no prose.** Section titles are fixed internal planning labels defined in
`contracts.py` — not generated narrative and never client-facing language.

---

## Public entry point

```python
from peak.reports import (
    InternalAssessmentReportPlanRequest, prepare_internal_assessment_report_plan,
)

result = prepare_internal_assessment_report_plan(request)
# -> InternalAssessmentReportPlanningResult
```

Expected governance failures are **typed denials, not exceptions**. The boundary opens no database
connection, makes no network call, and reads no database — every reference is caller-supplied.

### `InternalAssessmentReportPlanRequest`

| Field | Meaning |
|---|---|
| `owner_id`, `client_id`, `engagement_id` | tenant identity; required |
| `authorization_scope` | required; `revoked` is refused |
| `requested_by`, `requester_role` | requester traceability; required |
| `report_plan_id` / `idempotency_key` | at least one required; backs the fingerprint |
| `intake_note_refs` | → `intake_note_records` |
| `source_ingestion_refs` | → `source_ingestion_records` |
| `evidence_reference_ids` | → `evidence_references` |
| `agent_task_queue_record_ids` | → `agent_task_queue_records` |
| `review_bundle_record_ids` | → `review_bundle_records` |
| `internal_reviewer_decision_record_ids` | → `internal_reviewer_decision_records` |
| `workflow_id`, `managed_record_workflow_ref` | optional Phase 35 provenance |
| `requested_sections` | optional; empty means all supported sections |
| `report_purpose` | optional short safe internal label |
| `audience` | `"internal"` only |
| `allow_empty_reference_plan` | opt in to a skeletal plan (emits a warning) |
| `strict_mode` | warnings must be resolved by a human before drafting |
| posture flags | must stay at their safe defaults |

References may be plain short id strings **or** typed `GovernedRecordReference` objects. The typed
form additionally lets the boundary verify tenant/engagement/scope consistency.

**The request never accepts** raw intake note text, raw packet payload, raw evidence/interview text,
source bytes, generated agent output, credentials/secrets, DSNs, raw SQL, stack traces, final
client-facing language, approval decisions, LLM prompts, AgentNet publish payloads, resolver
credentials, or arbitrary report JSON blobs.

---

## Report sections

Fourteen supported internal planning sections, always emitted in this **canonical order** (never the
caller's order):

| # | Section | Supporting reference categories |
|---|---|---|
| 0 | `executive_overview` | *(synthesis)* |
| 1 | `engagement_context` | `intake_note_refs` |
| 2 | `intake_summary` | `intake_note_refs` |
| 3 | `source_inventory` | `source_ingestion_refs` |
| 4 | `evidence_summary` | `evidence_reference_ids` |
| 5 | `operational_findings` | `evidence_reference_ids` |
| 6 | `inventory_risk_areas` | `evidence_reference_ids` |
| 7 | `process_improvement_candidates` | `evidence_reference_ids` |
| 8 | `system_data_readiness` | `source_ingestion_refs` |
| 9 | `ai_agent_readiness` | `agent_task_queue_record_ids` |
| 10 | `internal_recommendations` | `internal_reviewer_decision_record_ids`, `review_bundle_record_ids` |
| 11 | `evidence_gaps` | *(synthesis)* |
| 12 | `review_status` | `review_bundle_record_ids` |
| 13 | `next_steps_internal` | *(synthesis)* |

Each section plan carries a deterministic readiness state:

- `ready_for_internal_drafting` — every supporting category has at least one reference
- `partial_supporting_references` — some supporting categories are empty
- `blocked_no_supporting_references` — the section has requirements and none are satisfied
- `synthesis_only` — no direct references required; structured from the other sections

---

## Evidence trace map

`evidence_trace_map` maps each section id to an `InternalReportEvidenceTrace` holding **record ids
only** — the supporting references per category, the supporting reference count, and the missing
categories. It never holds record content.

---

## Finding and recommendation candidates

**Finding candidates** are structured placeholders tied to references, never generated narrative:
one slot per evidence reference (in sorted order), with `evidence_support_refs`,
`review_support_refs`, and a readiness state. A finding with no supporting review bundle is blocked.

**Recommendation candidates** are **internal-only** slots: one per reviewer-decision reference,
carrying `reviewer_decision_refs`, `evidence_support_refs`, `review_support_refs`, a readiness state,
and `blocked_reason` when not ready. Every recommendation candidate carries
`audience="internal"`, `requires_human_review=True`, and `client_facing_approved` /
`financial_verified` / `capsule_candidate_ready` / `publication_allowed` / `execution_allowed` all
false. **No candidate is ever marked final or client-facing.**

Both families are bounded at 200 slots; truncation is always reported as a warning, never silently.

---

## Open gaps

For every requested section, each unsatisfied supporting category becomes an `InternalReportGap`
with a deterministic `gap_id` (`gap_<section>_<category>`), the missing category, the missing record
type, and whether it blocks the section. Gaps are how the plan surfaces missing evidence for human
follow-up.

---

## Financial verification posture

The plan may **identify** items that would need future financial verification:
`future_financial_verification_items` lists the recommendation candidate ids that would require a
financial gate before any ROI or savings claim.

It does **not** calculate ROI, verify savings, mark financial impact verified, generate ROI claims,
or approve financial statements for client use. **`financial_verified` remains false** on the plan
and on every candidate.

---

## Capsule / AgentNet readiness posture

The plan may **identify** items that might later become capsule candidates:
`future_capsule_candidate_items` lists the source-ingestion references (the documented
source-system capsulization path — see [`SOURCE_SYSTEM_CAPSULIZATION.md`](SOURCE_SYSTEM_CAPSULIZATION.md)).

It does **not** create capsule candidates, persist capsule candidates, publish capsules, or call
AgentNet / resolver / MCP. **`capsule_candidate_ready` and `publication_allowed` remain false.**

---

## Client-facing posture

The plan is **internal only**. `audience` must be `internal`; `client`, `external`, and anything else
are denied. `client_facing_approved` is always false. No final client-facing language appears in the
plan, and there is **no send / share / export / client-approval path**.

Denied outright: `audience=client`, `audience=external`, `client_facing_approved=true`,
`final_client_report`, `client_facing_output`, `send_to_client`, `approve_client_facing`,
`publish_report`, `export_client_deliverable`.

---

## Determinism

The plan is a **pure function of the request**. `plan_fingerprint` is a SHA-256 over the safe request
fields, the section selection, and the normalized references. Determinism comes from:

- canonical section order (never caller order);
- references normalized to **sorted, de-duplicated** id lists, so ordering and repeats do not change
  the plan;
- positional candidate ids (`fnd_000`, `rec_000`, `gap_<section>_<category>`);
- **no random ids and no timestamps** anywhere in the package.

The same request always produces the same plan and the same fingerprint.

---

## Result contract

`InternalAssessmentReportPlanningResult` reports `outcome` (`planned` / `denied`), `permitted`,
`reason_code`, `status`, the `validation_result`, the `report_plan`, `plan_fingerprint`, the section
/ finding / recommendation / gap / blocked-item counts, `controlled_write_request_count` (always 0),
`reasons`, and `warnings`.

Side-effect flags are **all false**: `direct_database_write_made`, `database_connection_made`,
`sql_execution_made`, `stored_record_created`, `report_draft_persisted`, `review_records_write_made`,
`agent_run_records_write_made`, `review_approval_made`, `client_facing_output_created`,
`client_facing_approval_made`, `financial_verification_made`, `capsule_publication_made`,
`capsule_candidate_created`, `agentnet_publication_made`, `agent_execution_made`,
`mock_agent_execution_made`, `llm_call_made`, `agentnet_call_made`, `resolver_call_made`,
`network_call_made`.

Results carry only field names, reference ids, counts, and marker categories — **never** the
offending value.

---

## Managed MySQL posture

Phase 36 is **DB-free**: it adds no table, model, migration, writer, or read path, and reads no
database. The persistence rubric is unchanged — **managed remote MySQL is the operational data
store**, **Client Isolation Option A** is the default, **SQLite is not the production-readiness proof
path**, managed MySQL test/staging validation is required before treating DB-backed functionality as
production-ready, and the **production DB is not the main smoke-test target**. Standard `make
validate` requires **no live database credentials and no network**, and Phase 36 adds no DSN, no
production DB write path, and no cleanup/delete path.

See [`MANAGED_MYSQL_PERSISTENCE_RUBRIC.md`](MANAGED_MYSQL_PERSISTENCE_RUBRIC.md),
[`CLIENT_ISOLATION_MODEL.md`](CLIENT_ISOLATION_MODEL.md), and
[`PRODUCTION_PARITY_DB_VALIDATION.md`](PRODUCTION_PARITY_DB_VALIDATION.md).

---

## AgentNet publication policy

Phase 36 **does not alter the Peak-operated AgentNet publication policy** and adds no publishing
code. Clients do not operate any AgentNet publishing tools; the client authorizes Peak in the
consulting agreement to act as authorized capsule/node publisher; Peak operates all publishing
workflows as a managed service. No client-facing AgentNet publisher UI, no client-held publishing
credentials, no client-operated resolver publication tools, no direct client publication path.
**AgentNet publication remains deferred.**

See [`PEAK_OPERATED_AGENTNET_PUBLICATION_POLICY.md`](PEAK_OPERATED_AGENTNET_PUBLICATION_POLICY.md).

---

## Where it sits

```
… → review bundle persistence → internal reviewer decision planning
  → internal reviewer decision persistence → managed record workflow integration (P35)
  → internal assessment report assembly planning (P36)
```

Phase 35 persists the durable records and returns safe record refs; Phase 36 consumes those refs
(and reviewer decisions) to plan an internal report. Phase 36 never calls Phase 35, never calls a
writer, and never reads back a record — the caller passes the references.

---

## Validation

```bash
make validate-phase36   # stdlib-only; DB-free and network-free
```
