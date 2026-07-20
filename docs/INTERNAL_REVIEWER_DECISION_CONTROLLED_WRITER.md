# Internal Reviewer Decision Controlled Writer (Phase 33)

The **seventh** narrow live DB writer in Peak (after the Phase 20 `agent_run_records`, Phase 21
`evidence_references`, Phase 22 `review_records`, Phase 24 `source_ingestion_records`, Phase 27
`agent_task_queue_records`, and Phase 30 `review_bundle_records` writers). It persists **exactly
one** `internal_reviewer_decision_records` row from a Phase 32 `InternalReviewerDecisionDraft`
routed through the Phase 17 `ControlledWriteRequest` boundary — allowing only
`internal_reviewer_decision_records` / `create_internal_reviewer_decision_record`. It is the
**persistence counterpart to Phase 32**, not a review-approval phase; it is a narrow internal
persistence boundary, not a generic decision engine, review engine, workflow engine, or CRUD
repository.

Public entry point:

```
persist_internal_reviewer_decision_record(controlled_write_request, *, session_factory=None,
                                          decision_request=None) -> InternalReviewerDecisionWriteReceipt
```

An optional Phase-33 (DB-layer) planning helper,
`build_decision_controlled_write_request(draft, *, requested_by, requester_role, idempotency_key, ...)`,
wraps a Phase 32 draft in the Phase 17 `ControlledWriteRequest` for this exact table/action. It
lives in the DB layer — **not** in Phase 32 — so the reviewer-decision boundary stays strictly
DB-free; it opens no database connection and persists nothing.

## Non-approval — review-gated decision records only

This writer **approves nothing**. It never performs `approve_internal`, never calls the **Phase 22
review writer**, and **never creates a `review_records` row**. It never executes an agent (live or
mock), never calls the Phase 13 executor / MockLLM / a live LLM / AgentNet / MCP / resolver /
connector / network, never creates an `agent_run_records` row, and produces no client-facing
output, financial verification, or capsule publication. Every stored row is **review-gated and
non-approval**: `output_status=draft`, `review_status=needs_review`, `lifecycle_status=draft`,
`authoritative=false`, `client_facing_approved=false`, `capsule_candidate_ready=false`,
`financial_verified=false`, `execution_allowed=false`, `approval_allowed=false`,
`publication_allowed=false`, `requires_human_review=true`, `client_facing_output_created=false`,
`review_approval_made=false`.

- **Phase 32** creates internal reviewer decision drafts only (DB-free).
- **Phase 33** is the first phase where `internal_reviewer_decision_records` has a live narrow DB
  writer. This does **not** authorize approval, `review_records` creation, `approve_internal`,
  client-facing output, financial verification, capsule publication, or execution.

**`ready_for_internal_use` is not approval.** It records internal reliance readiness only — it does
not authorize client-facing output, financial verification, capsule publication, agent execution,
or a `review_records` write.

## Decision-intent rule

Only the eight Phase 32 internal-review intents may be persisted: `needs_more_evidence`,
`return_for_revision`, `ready_for_internal_use`, `blocked_by_scope`, `blocked_by_quality`,
`blocked_by_missing_source`, `rejected_for_policy`, `defer_review`. Any approval / publication /
execution / financial / client-facing intent (`approve_internal`, `approve_client_facing`,
`final_approval`, `publish_capsule`, `verify_financial_impact`, `execute_agent`,
`create_report_for_client`, `send_to_client`, …) is denied.

The writer also stores a deterministic **routing recommendation** (`route_to`, refined for
`return_for_revision` by a safe `return_to_stage` into `"<stage>_revision"`). Routing is a
recommendation only; no action is taken.

## Write-time authorization (stored Engagement is authoritative)

The writer does **not** trust the Phase 32 request or draft as proof of authorization. At
**write-time** it loads the authoritative stored authorization subject — the `Engagement` row —
from the database and requires, in order:

1. the `Engagement` row exists (subject `subject_record_type="engagement"`, id present);
2. `engagement.authorization_scope` is present;
3. `request.authorization_scope == engagement.authorization_scope`;
4. `engagement.owner_id == request.owner_id`, `engagement.client_id == request.client_id`,
   `engagement.id == request.engagement_id`;
5. `engagement.lifecycle_status` is not `revoked` / `archived` / `deleted_reference_only`.

**Identity matching is necessary but not sufficient** — a stored-scope mismatch is denied even
when every identity matches. Missing stored scope and missing request scope are denied.

## Identity checks (pre-DB)

Before any DB connection: the Phase 17 plan must be permitted; the target must be exactly
`internal_reviewer_decision_records` / `create_internal_reviewer_decision_record`; the
`record_draft` must be an `InternalReviewerDecisionDraft`; and the draft's owner/client/engagement
**and `authorization_scope`** must match the request (and the subject).

## Content safety — safe references, summaries, and metadata only

Only safe references/labels/metadata are persisted: owner/client/engagement, `review_bundle_ref` /
`review_bundle_record_id` / `review_bundle_draft_ref`, `review_plan_item_refs` /
`evidence_reference_ids` / `source_ingestion_record_ids` / `agent_task_queue_record_ids` (safe
ids), `reviewer_role`, `decision_intent`, `decision_reason_code`, `safe_decision_summary`,
`return_to_stage`, `route_to`, `requested_followup_actions` (safe labels), `authorization_scope`,
the statuses and posture booleans, `reasons`/`warnings`, `idempotency_key`, and
`payload_fingerprint`. Governance and decision-posture fields are **real columns**; the
reference/followup/reasons/warnings bag lives in `details_json`.

**Never persisted:** the raw `packet_payload`, raw evidence text, raw interview text, raw source
file bytes, generated agent output, arbitrary client content, credentials/secrets, LLM prompts with
raw content, a **final review approval / decision / client-facing language**, stack traces, DB
URLs, or raw SQL. A draft carrying a `packet_payload` / `raw_evidence_text` / `raw_interview_text` /
`source_bytes` / `generated_output` / `database_url` / `raw_sql` / `approval_decision` / `api_key` /
`connection_string` / `token` / `credential` (or similar) attribute is rejected **without echoing
the value**. A `safe_decision_summary` or `requested_followup_actions` label carrying a
credential/DB-URL/raw-SQL/raw-content marker (e.g. a `postgres://` DSN, `SELECT * FROM …`,
`UPDATE … SET …`) is rejected — only the marker **category** is reported, never the value — while a
harmless note like "please update the review note" is allowed (the Phase 32 value-safety hardening
is preserved).

## Idempotency

See [`INTERNAL_REVIEWER_DECISION_IDEMPOTENCY_POLICY.md`](INTERNAL_REVIEWER_DECISION_IDEMPOTENCY_POLICY.md).
The DB-enforced uniqueness boundary is `(owner_id, client_id, engagement_id, idempotency_key)`, with
a deterministic `payload_fingerprint` distinguishing an exact `idempotent_replay` from a conflicting
`idempotency_conflict`. A uniqueness race is resolved by an `IntegrityError` re-query, mirroring
Phases 20–24, 27, and 30.

## Receipt and outcomes

`InternalReviewerDecisionWriteReceipt` reports `outcome` (`created` / `idempotent_replay` /
`denied` / `failed_before_write` / `write_outcome_uncertain`), `permitted`, `reason_code`,
`target_table`, `target_action`, `stored_record_id`, `idempotency_key`, `audit_trace_ref`, the
actual-behavior flags (`database_connection_made`, `sql_execution_made`, `database_write_made`,
`stored_record_created`, `existing_record_returned`, `transaction_committed`, `outcome_uncertain`),
the decision posture (`decision_intent`, `route_to`, `review_status`, `output_status`,
`lifecycle_status`), the always-false non-effect flags (`review_records_write_made`,
`review_approval_made`, `client_facing_output_created`, `financial_verification_made`,
`capsule_publication_made`, `agent_execution_made`, `llm_call_made`, `agentnet_call_made`,
`resolver_call_made`, `network_call_made`), and server-stamped `created_at` / `database_write_at`.
It contains no credentials, DB URL, raw SQL, raw content, generated output, final review approval/
decision, or stack trace. An **uncertain** commit never falsely claims no record exists.

## Migration and table

Migration `008_internal_reviewer_decision_records` (`down_revision = 007_review_bundle_records`)
creates the single new `internal_reviewer_decision_records` table (governance/audit columns +
decision-posture columns + routing columns + idempotency columns + the unique index). It is
additive and non-destructive, contains **no INSERT and no seed data**, and its downgrade drops only
the new table/indexes/constraint. Alembic remains single-head; `make db-check` now expects
**exactly 14 tables**.

## Boundaries

- **One table/action only:** `internal_reviewer_decision_records` /
  `create_internal_reviewer_decision_record`. Any other table or action (update / delete / upsert /
  approve / publish / execute / client-facing approval / financial verification / raw SQL, or a
  `review_records` / `agent_run_records` target) is denied.
- **No approval, no `approve_internal`, no Phase 22 writer call, no `review_records` write.**
- **No agent / mock-agent / LLM / MockLLM / AgentNet / MCP / resolver / connector / network call;
  no `agent_run_records` write; no client-facing output, financial verification, or capsule
  publication; never updates or deletes.**
- The Phase 32 `peak/reviewer_decisions` package stays **DB-free**; this writer lives in the DB
  layer and consumes only its DB-free contracts + non-echoing value scanner.
