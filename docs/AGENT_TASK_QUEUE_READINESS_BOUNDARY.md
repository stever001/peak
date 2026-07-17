# Controlled Agent Task Queue / Execution Readiness Boundary (Phase 26)

A **readiness/queue-planning boundary** over derived Phase 13 `AgentTaskRequest` objects. It
turns them into governed, **review-gated**, **not executed** Agent Task Queue drafts and
Execution Readiness assessments — and, optionally, plan-only Phase 17 controlled write requests
for a *future* writer. It is **not** an executor, task runner, job queue, workflow engine, or
DB writer.

This phase is deliberately analogous to Phase 23
([`ENGAGEMENT_PACKET_INGESTION_BOUNDARY.md`](ENGAGEMENT_PACKET_INGESTION_BOUNDARY.md)):

- Phase 23 prepared source-ingestion / packet-derived plans **without DB writes**.
- Phase 26 prepares task-queue / execution-readiness plans **without DB writes**.

## What it is (and is not)

The boundary only *plans*. It accepts an `AgentTaskQueueRequest` carrying Phase 13
`AgentTaskRequest` objects (typically derived by Phase 23 and surfaced by the Phase 25
orchestrator) and produces:

- `AgentTaskQueueDraft[]` — production-shaped but **review-gated** queue drafts, never persisted;
- `AgentExecutionReadinessAssessment[]` — a deterministic readiness state per task;
- `ControlledWriteRequest[]` — plan-only Phase 17 requests for a future
  `agent_task_queue_records` writer (a write plan is not a write).

It executes **no agent** (live or mock), makes **no live LLM** call, **no MockLLM** call, **no
AgentNet**/MCP/resolver call, and **no** network call; it opens **no DB** connection, runs no
SQL, and writes no row; it creates no client-facing output, verifies no financial impact, and
publishes no capsule. Every derived draft stays `draft` / `needs_review` / `not_executed` with
`execution_allowed=false`.

## Public entry point

```
prepare_agent_task_queue_plan(request: AgentTaskQueueRequest) -> AgentTaskQueueReadinessResult
```

## Inputs — `AgentTaskQueueRequest`

`owner_id`, `client_id`, `engagement_id`, `requested_by`, `requester_role`,
`authorization_scope`, `idempotency_key`, `agent_task_requests` (Phase 13 `AgentTaskRequest[]`),
optional `source_ingestion_record_id`, optional `evidence_reference_ids`, optional
`packet_processing_run_ref` / `orchestration_ref`, optional safe `context` metadata and
`reason`. **No raw packet payload, raw evidence/interview text, source bytes, credentials, or
arbitrary client data may be supplied** — only ids/references and safe metadata.

## Outputs

`AgentTaskQueueDraft` is review-gated and non-executed: `agent_task_queue_record_id=None`,
`created_at=None`, `output_status=draft`, `review_status=needs_review`, `lifecycle_status=draft`,
`authoritative=false`, `client_facing_approved=false`, `capsule_candidate_ready=false`,
`execution_status=not_executed`, `execution_allowed=false`, `llm_execution_allowed=false`,
`agentnet_context_allowed=false`, `resolver_context_allowed=false`, `network_allowed=false`,
`requires_human_review=true`. It carries only ids/references (`task_input_ref`,
`evidence_reference_ids`, `source_ingestion_record_id`) and a safe `task_input_summary` — never
raw content. Its `idempotency_key` is derived deterministically per task
(`<idempotency_key>::taskq::<index>::<agent_name>`) so queue drafts do not collide.

## Execution readiness states

Deterministic, one per task: `queued_for_review`, `blocked_by_policy`,
`blocked_missing_evidence`, `blocked_unknown_agent`, `blocked_invalid_scope`,
`blocked_lifecycle`, and `ready_for_future_controlled_execution`.

**For Phase 26, "ready" never means "execute now".** `ready_for_future_controlled_execution`
means a task is *structurally ready for a later controlled execution phase after human review*
— inputs are wired and every check passed — but `execution_allowed` stays `false` and
`requires_human_review` stays `true`. A task with no wired input that otherwise passes is
`queued_for_review`.

## Classification precedence

unknown agent → invalid scope → blocked lifecycle → policy violation → missing evidence →
(`ready_for_future_controlled_execution` if an evidence/source input is wired, else
`queued_for_review`). Evidence-dependent workflows (`reporting`, `proposal`, `qa`) with no wired
evidence input are `blocked_missing_evidence`.

## Authorization and identity

The request must be authorized and scoped, and each task's `owner_id`/`client_id`/
`engagement_id` **and** `authorization_scope` must match the request. **Identity matching is
necessary but not sufficient** — a scope mismatch blocks the task even when identities match.
Phase 26 stores nothing, so there is no stored-record authorization here; a *future* writer
(Phase 27) would re-load and re-check the stored `Engagement` scope at write time, exactly as
Phases 20–22/24 do.

## Controlled write planning (plan-only)

Each valid queue draft yields a Phase 17 `ControlledWriteRequest` with
`target_table="agent_task_queue_records"`, `requested_action="create_agent_task_queue_record"`,
the engagement as subject, and the draft as `record_draft`. This is a **plan only**: no DB
writer is called, `peak.db` is not imported, no migration or table is added, and no stored row
is claimed. The `agent_task_queue_records` table is **not yet** on the Phase 17 allowlist and
has no writer — **a future Phase 27** would add both. See
[`CONTROLLED_WRITE_ALLOWLIST.md`](CONTROLLED_WRITE_ALLOWLIST.md).

## Integration with Phase 25

The Phase 25 orchestrator currently plans agent tasks through Phase 13 (its
`agent_task_planning` stage exposes derived `AgentTaskRequest` objects). Phase 26 adds the
DB-free readiness/queue planning boundary for exactly those objects. To avoid scope creep,
**Phase 25 code is left unchanged**: the handoff is by contract — the Phase 26
`AgentTaskQueueRequest.agent_task_requests` field consumes the same Phase 13 objects Phase 25
surfaces on `PacketProcessingReceipt.agent_task_requests`. The Phase 26 validator exercises this
end-to-end in plan-only mode with no side effects. A later phase may wire Phase 25 to call
Phase 26 directly once a narrow, safe integration is warranted. See
[`CONTROLLED_PACKET_PROCESSING_ORCHESTRATOR.md`](CONTROLLED_PACKET_PROCESSING_ORCHESTRATOR.md).

## Result and side-effect flags

`AgentTaskQueueReadinessResult` reports `outcome` (`denied` / `planned` / `partial` /
`blocked`), `permitted`, `reason_code`, `task_count_received`, `queue_draft_count`,
`readiness_assessment_count`, `controlled_write_request_count`, `blocked_task_count`,
`stages_completed` / `stages_skipped`, `reasons`, `warnings`, and the aggregate side-effect
flags — all of which stay `false` in Phase 26: `direct_database_write_made`,
`database_connection_made`, `sql_execution_made`, `stored_record_created`,
`agent_execution_made`, `mock_agent_execution_made`, `llm_call_made`, `agentnet_call_made`,
`resolver_call_made`, `network_call_made`, `client_facing_output_created`,
`financial_verification_made`, `capsule_publication_made`.

## Boundaries

- **No new table, no migration** — Alembic head remains `005_source_ingestion_idem`.
- **No agent / mock-agent / LLM / MockLLM / AgentNet / MCP / resolver / network call.**
- **No DB** connection, SQL, or stored record; **no** generic workflow engine / task runner /
  job queue / CRUD / raw SQL.
- **No client-facing approval, no financial verification, no capsule publication.**
- The package imports only stdlib plus the DB-free Phase 13 registry and Phase 17 controlled-
  write contracts.
