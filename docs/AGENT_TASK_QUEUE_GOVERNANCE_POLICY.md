# Agent Task Queue Governance Policy (Phase 26)

The governance contract for the Phase 26 **execution readiness** / queue-planning boundary
([`AGENT_TASK_QUEUE_READINESS_BOUNDARY.md`](AGENT_TASK_QUEUE_READINESS_BOUNDARY.md)). It plans
review-gated, **not executed** agent task queue drafts from derived Phase 13 `AgentTaskRequest`
objects. It adds no execution authority, no table, no migration, and no writer.

## Allowed outputs

- Review-gated `AgentTaskQueueDraft` objects (never persisted, never executed).
- Deterministic `AgentExecutionReadinessAssessment` objects.
- Plan-only Phase 17 `ControlledWriteRequest` objects for a *future*
  `agent_task_queue_records` writer.
- A typed `AgentTaskQueueReadinessResult` with counts, stage names, safe reasons, and warnings.

## Prohibited effects

The boundary may never: execute an agent (live or mock); make a live LLM or MockLLM call; make
an AgentNet / MCP / resolver call; make a network call; open a **DB** connection, run SQL, or
write a row; create client-facing output; verify financial impact; or publish a capsule. It
invents no generic workflow engine, task runner, job queue, generic writer, or CRUD, and runs
no raw SQL. Adding a migration or table is out of scope.

## Request-level requirements

- `owner_id`, `client_id`, `engagement_id`, `requested_by`, `requester_role`,
  `authorization_scope`, and `idempotency_key` present.
- `requested_action` is `prepare_agent_task_queue_plan`.
- At least one `agent_task_request` supplied.
- `authorization_scope` is not `revoked`; `lifecycle_status` is not `revoked` / `archived` /
  `deleted_reference_only`.
- **No raw-content fields** (`packet_payload`, `raw_evidence`, `interview_text`, `source_bytes`,
  … / any `payload`), **no secret-like fields** (`password`, `secret`, `api_key`, `token`,
  `private_key`, `credential`, `connection_string`, `access_key`), and **no
  execution/network/financial/publication intent keys** (`*network*`, `verify_financial`,
  `publish_capsule`, `execute_now`, `run_agent`, `mock_agent`, …) anywhere in the request, its
  `context`, or its tasks. Only **key names** are ever reported — secret and raw **values are
  never echoed** in reasons, warnings, or receipts.

A request-level failure denies the whole request (`outcome=denied`), side-effect free.

## Per-task classification (necessary but not sufficient)

Each task is classified deterministically, in order:

1. **`blocked_unknown_agent`** — not in the Phase 13 registry.
2. **`blocked_invalid_scope`** — task `owner_id`/`client_id`/`engagement_id` or
   `authorization_scope` does not match the request. **Identity matching is necessary but not
   sufficient**; the scope must match too.
3. **`blocked_lifecycle`** — task lifecycle is `revoked` / `archived` /
   `deleted_reference_only`.
4. **`blocked_by_policy`** — the task requests live execution / LLM (`llm_execution_allowed`),
   resolver/AgentNet context (`resolver_context_allowed`), or client-facing output
   (`client_facing_output_requested`). These must be `false`; a derived packet task keeps them
   `false`.
5. **`blocked_missing_evidence`** — an evidence-dependent workflow (`reporting`, `proposal`,
   `qa`) with no wired evidence input.
6. **`ready_for_future_controlled_execution`** — all checks passed **and** an evidence/source
   input is wired. **"Ready" never means "execute now"**: `execution_allowed` stays `false` and
   `requires_human_review` stays `true`.
7. **`queued_for_review`** — all checks passed but no input is wired yet.

A task that is blocked produces an assessment but **no** queue draft. A mix of valid and blocked
tasks yields `outcome=partial`; all-blocked yields `outcome=blocked` (the request itself was
valid); all-valid yields `outcome=planned`.

## Idempotency

Each queue draft gets a deterministic per-task key
`<request.idempotency_key>::taskq::<index>::<agent_name>` so drafts do not collide on the shared
future-writer boundary. The plan-only Phase 17 `ControlledWriteRequest` carries the same key.

## No execution, no persistence

Phase 26 is a planning boundary. It never runs an agent and never writes a row. **Phase 27**
added the narrow DB-backed `agent_task_queue_records` writer
([`AGENT_TASK_QUEUE_CONTROLLED_WRITER.md`](AGENT_TASK_QUEUE_CONTROLLED_WRITER.md)) that re-loads
the stored `Engagement` authorization at write time (identity necessary but not sufficient) and
enforces DB-level idempotency — mirroring Phases 20–22/24 — persisting a review-gated,
not-executed row. Phase 26 itself still writes nothing; see
[`CONTROLLED_WRITE_ALLOWLIST.md`](CONTROLLED_WRITE_ALLOWLIST.md). **Phase 28** invokes this
readiness planner (and, opt-in, the Phase 27 writer) from the Phase 25 orchestrator without
relaxing any rule here — see
[`PACKET_TO_TASK_QUEUE_ORCHESTRATION_INTEGRATION.md`](PACKET_TO_TASK_QUEUE_ORCHESTRATION_INTEGRATION.md).
