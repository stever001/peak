# Review Bundle Controlled Writer (Phase 30)

The **sixth** narrow live DB writer in Peak (after the Phase 20 `agent_run_records`, Phase 21
`evidence_references`, Phase 22 `review_records`, Phase 24 `source_ingestion_records`, and Phase 27
`agent_task_queue_records` writers). It persists **exactly one** `review_bundle_records` row from a
Phase 29 `ReviewBundleDraft` routed through the Phase 17 `ControlledWriteRequest` boundary —
allowing only `review_bundle_records` / `create_review_bundle_record`. It is the **persistence
counterpart to Phase 29**, not a review-approval phase; it is a narrow internal persistence
boundary, not a generic review engine, workflow engine, or CRUD repository.

Public entry point:

```
persist_review_bundle_record(controlled_write_request, *, session_factory=None,
                             review_request=None) -> ReviewBundleWriteReceipt
```

## No approval — review-gated bundle records only

This writer **approves nothing**. It never performs `approve_internal`, never calls the **Phase 22
review writer**, and **never creates a `review_records` row**. It never executes an agent (live or
mock), never calls the Phase 13 executor / MockLLM / a live LLM / AgentNet / MCP / resolver /
connector / network, never creates an `agent_run_records` row, and produces no client-facing
output, financial verification, or capsule publication. Every stored row is **review-gated and
not-approved**: `output_status=draft`, `review_status=needs_review`, `lifecycle_status=draft`,
`authoritative=false`, `client_facing_approved=false`, `capsule_candidate_ready=false`,
`financial_verified=false`, `execution_allowed=false`, `approval_allowed=false`,
`publication_allowed=false`, `requires_human_review=true`.

- **Phase 29** creates review bundle drafts only (DB-free).
- **Phase 30** is the first phase where `review_bundle_records` has a live narrow DB writer. This
  does **not** authorize approval, `review_records` creation, client-facing output, financial
  verification, or capsule publication.

## Write-time authorization (stored Engagement is authoritative)

The writer does **not** trust the Phase 29 request or draft as proof of authorization. At
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
`review_bundle_records` / `create_review_bundle_record`; the `record_draft` must be a
`ReviewBundleDraft`; and the draft's owner/client/engagement must match the request (and the
subject).

## Content safety — safe references and metadata only

Only safe references/counts/metadata are persisted: owner/client/engagement, the packet-processing
receipt ref, `source_ingestion_record_ids` / `evidence_reference_ids` /
`agent_task_queue_record_ids` (safe ids), `subject_refs` (id + type), `reviewer_role`,
`review_reason`, `review_scope`, the statuses and posture booleans, `reasons`/`warnings`,
`idempotency_key`, and `payload_fingerprint`. Governance and review-posture fields are **real
columns**; the reference/subject/reasons/warnings bag lives in `details_json`.

**Never persisted:** the raw `packet_payload`, raw evidence text, raw interview text, raw source
file bytes, generated agent output, arbitrary client content, credentials/secrets, LLM prompts
with raw content, a **final review decision / approval note**, stack traces, DB URLs, or raw SQL.
A draft carrying a `packet_payload` / `raw_evidence_text` / `raw_interview_text` / `source_bytes` /
`generated_output` / `approval_decision` / `api_key` / `connection_string` / `token` / `credential`
(or similar) attribute is rejected **without echoing the value**.

## Idempotency

See [`REVIEW_BUNDLE_IDEMPOTENCY_POLICY.md`](REVIEW_BUNDLE_IDEMPOTENCY_POLICY.md). The DB-enforced
uniqueness boundary is `(owner_id, client_id, engagement_id, idempotency_key)`, with a
deterministic `payload_fingerprint` distinguishing an exact `idempotent_replay` from a conflicting
`idempotency_conflict`. A uniqueness race is resolved by an `IntegrityError` re-query, mirroring
Phases 20–24 and 27.

## Receipt and outcomes

`ReviewBundleWriteReceipt` reports `outcome` (`created` / `idempotent_replay` / `denied` /
`failed_before_write` / `write_outcome_uncertain`), `permitted`, `reason_code`, `target_table`,
`target_action`, `stored_record_id`, `idempotency_key`, `audit_trace_ref`, the actual-behavior
flags (`database_connection_made`, `sql_execution_made`, `database_write_made`,
`stored_record_created`, `existing_record_returned`, `transaction_committed`, `outcome_uncertain`),
the posture (`review_status`, `output_status`, `lifecycle_status`), the always-false non-effect
flags (`review_approval_made`, `client_facing_output_created`, `financial_verification_made`,
`capsule_publication_made`, `agent_execution_made`, `llm_call_made`, `agentnet_call_made`,
`resolver_call_made`, `network_call_made`), and server-stamped `created_at` / `database_write_at`.
It contains no credentials, DB URL, raw SQL, raw content, generated output, final review decision,
or stack trace. An **uncertain** commit never falsely claims no record exists.

## Migration and table

Migration `007_review_bundle_records` (`down_revision = 006_agent_task_queue_records`) creates the
single new `review_bundle_records` table (governance/audit columns + review-posture columns +
idempotency columns + the unique index). It is additive and non-destructive, contains **no INSERT
and no seed data**, and its downgrade drops only the new table/indexes/constraint. Alembic remains
single-head; `make db-check` now expects **exactly 13 tables**.

## Boundaries

- **One table/action only:** `review_bundle_records` / `create_review_bundle_record`. Any other
  table or action (update / delete / upsert / approve / publish / execute / client-facing approval
  / financial verification / raw SQL, or a `review_records` / `agent_run_records` target) is denied.
- **No approval, no Phase 22 writer call, no `review_records` write.**
- **No agent / mock-agent / LLM / MockLLM / AgentNet / MCP / resolver / connector / network call;
  no `agent_run_records` write; no client-facing output, financial verification, or capsule
  publication; never updates or deletes.**
- The Phase 29 `peak/review_orchestration` package stays **DB-free**; this writer lives in the DB
  layer.
