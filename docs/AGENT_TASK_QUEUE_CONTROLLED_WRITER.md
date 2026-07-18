# Agent Task Queue Controlled Writer (Phase 27)

The **fifth** narrow live DB writer in Peak (after the Phase 20 `agent_run_records`, Phase 21
`evidence_references`, Phase 22 `review_records`, and Phase 24 `source_ingestion_records`
writers). It persists **exactly one** `agent_task_queue_records` row from a Phase 26
`AgentTaskQueueDraft` routed through the Phase 17 `ControlledWriteRequest` boundary — allowing
only `agent_task_queue_records` / `create_agent_task_queue_record`. It is a narrow internal
persistence boundary, **not** a generic task runner, job queue, workflow engine, generic writer,
or CRUD repository.

Public entry point:

```
persist_agent_task_queue_record(controlled_write_request, *, session_factory=None,
                                readiness_request=None) -> AgentTaskQueueWriteReceipt
```

## No execution — review-gated queue records only

This writer **never executes an agent**. It does not call the Phase 13 executor, MockLLM, a
live LLM, AgentNet, MCP, a resolver, a connector, or the network, and it **never creates an
`agent_run_records` row**. It stores **review-gated, not-executed** queue records: every stored
row has `output_status=draft`, `review_status=needs_review`, `lifecycle_status=draft`,
`execution_status=not_executed`, `execution_allowed=false`, `llm_execution_allowed=false`,
`agentnet_context_allowed=false`, `resolver_context_allowed=false`, `network_allowed=false`,
`requires_human_review=true`, and `authoritative=false` / `client_facing_approved=false` /
`capsule_candidate_ready=false`. This does **not** authorize execution and does **not** authorize
`agent_run_records` creation — those remain out of scope for a later phase.

## Write-time authorization (stored Engagement is authoritative)

The writer does **not** trust the Phase 26 queue request or draft as proof of authorization. At
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

## Identity / registry gate (pre-DB)

Before any DB connection: the Phase 17 plan must be permitted; the target must be exactly
`agent_task_queue_records` / `create_agent_task_queue_record`; the `record_draft` must be an
`AgentTaskQueueDraft`; `agent_name` must be present **and in the Phase 13 registry** (unknown
agents are never persisted); `task_type` or `requested_action` must be present; and the draft's
owner/client/engagement **and** `authorization_scope` must match the request (and the subject).

## Content safety — safe references and summaries only

Only safe references/summaries are persisted: owner/client/engagement, `agent_name`,
`task_type`/`requested_action`, `task_input_ref`, `safe_input_summary`,
`source_ingestion_record_id`, `evidence_reference_ids`, `packet_processing_run_ref` /
`orchestration_ref`, `authorization_scope`, `readiness_state`, the statuses and posture
booleans, `reasons`/`warnings`, `idempotency_key`, and `payload_fingerprint`. Governance and
execution-posture fields are **real columns**; the reference/summary bag lives in `details_json`.

**Never persisted:** the raw `packet_payload`, raw evidence text, raw interview text, raw source
file bytes, arbitrary client data, credentials/secrets, LLM prompts containing raw content,
generated agent output, stack traces, DB URLs, or raw SQL. A draft carrying a `packet_payload` /
`raw_packet_content` / `raw_evidence_text` / `raw_interview_text` / `source_bytes` / `api_key` /
`connection_string` / `token` (or similar) attribute is rejected **without echoing the value**.

## Readiness state

Only the two non-blocked readiness states are persistable: `queued_for_review` and
`ready_for_future_controlled_execution` (which means *structurally ready for a later controlled
execution phase after review* — never "execute now"). Blocked states
(`blocked_invalid_scope`, `blocked_lifecycle`, `blocked_unknown_agent`, `blocked_by_policy`,
`blocked_missing_evidence`) have no queue draft in Phase 26 and are rejected here if presented.

## Idempotency

See [`AGENT_TASK_QUEUE_IDEMPOTENCY_POLICY.md`](AGENT_TASK_QUEUE_IDEMPOTENCY_POLICY.md). The
DB-enforced uniqueness boundary is `(owner_id, client_id, engagement_id, idempotency_key)`, with
a deterministic `payload_fingerprint` distinguishing an exact `idempotent_replay` from a
conflicting `idempotency_conflict`. A uniqueness race is resolved by an `IntegrityError`
re-query, mirroring Phases 20–24.

## Receipt and outcomes

`AgentTaskQueueWriteReceipt` reports `outcome` (`created` / `idempotent_replay` / `denied` /
`failed_before_write` / `write_outcome_uncertain`), `permitted`, `reason_code`, `target_table`,
`target_action`, `stored_record_id`, `idempotency_key`, `audit_trace_ref`, the actual-behavior
flags (`database_connection_made`, `sql_execution_made`, `database_write_made`,
`stored_record_created`, `existing_record_returned`, `transaction_committed`,
`outcome_uncertain`), the posture (`review_status`, `output_status`, `execution_status`,
`readiness_state`), and server-stamped `created_at` / `database_write_at`. It contains no
credentials, DB URL, raw SQL, raw content, generated output, or stack trace. An **uncertain**
commit never falsely claims no record exists.

## Migration and table

Migration `006_agent_task_queue_records` (`down_revision = 005_source_ingestion_idem`) creates
the single new `agent_task_queue_records` table (governance/audit columns + execution-posture
columns + idempotency columns + the unique index). It is additive and non-destructive, contains
**no INSERT and no seed data**, and its downgrade drops only the new table/indexes/constraint.
Alembic remains single-head; `make db-check` now expects **exactly 12 tables**.

## Boundaries

- **One table/action only:** `agent_task_queue_records` / `create_agent_task_queue_record`. Any
  other table or action (update / delete / upsert / publish / execute / client-facing approval /
  financial verification / raw SQL, or an `agent_run_records` target) is denied.
- **No agent / mock-agent / LLM / MockLLM / AgentNet / MCP / resolver / connector / network
  call**; **no `agent_run_records` write**; no client-facing approval, financial verification, or
  capsule publication; never updates or deletes.
- The Phase 26 `peak/task_queue` package stays **DB-free**; this writer lives in the DB layer.

## Invoked by the Phase 25 orchestrator (Phase 28)

**Phase 28** calls this writer from the Phase 25 packet processor's `agent_task_queue_persistence`
stage — and only when `plan_only=false`, `include_agent_task_queue_persistence=true`, and a
`session_factory` is supplied. The orchestrator calls **only** `persist_agent_task_queue_record`
(never a dynamically-dispatched writer), passes the request's `idempotency_key` through Phase 26's
per-task derivation, and surfaces this writer's outcomes (created / idempotent_replay / conflict /
denial) on the packet receipt. Write-time stored-`Engagement` authorization stays authoritative
here — a stored-scope mismatch is denied even when the orchestrator's preflight identity checks
pass. See
[`PACKET_TO_TASK_QUEUE_ORCHESTRATION_INTEGRATION.md`](PACKET_TO_TASK_QUEUE_ORCHESTRATION_INTEGRATION.md).

The `agent_task_queue_records` ids this writer creates are safe references that a human-review plan
may cite: the **Phase 29 Packet-Derived Review Orchestration Boundary**
([`PACKET_DERIVED_REVIEW_ORCHESTRATION_BOUNDARY.md`](PACKET_DERIVED_REVIEW_ORCHESTRATION_BOUNDARY.md))
consumes those ids (DB-free, no approval, no DB read) to build `agent_task_queue_review` items.
