# Agent Run Records (Phase 13)

The **future** provenance record for a Peak internal agent run. **No agent run records are
stored in this phase** — this documents the intended shape and the
[`AgentRunDraft`](../peak/agents/contracts.py) in-memory helper. Persisting a record
requires the controlled-database integration (the `agent_run_records` table already exists
as a Phase 11 scaffold; **no writes happen yet**). **AgentNet integration is not complete.**

## Purpose

Every future agent run should be **attributable and reviewable**: who/what ran, for which
client/engagement, over what inputs, using which prompt contract, whether resolver context
or an LLM was involved, what it produced, and in what governance state. This makes agent
work auditable and keeps human-review gates enforceable (see
[`DATABASE_ACCESS_AND_AUDIT.md`](DATABASE_ACCESS_AND_AUDIT.md)).

## Fields to capture

| Field | Meaning |
| --- | --- |
| `agent_run_id` | Unique id for the run (assigned by a future controlled-DB writer). |
| `agent_name` | The registered agent/worker that ran. |
| `workflow` | The workflow the run served (intake, discovery, evidence, …). |
| `owner_id` | Accountable Peak owner/role for the run. |
| `client_id` | Client the run pertains to (where applicable). |
| `engagement_id` | Engagement the run pertains to (where applicable). |
| `input_record_ids` | Ids of the records the run read as input. |
| `prompt_contract_path` | The prompt-contract file used (reference only). |
| `resolver_context_requested` | Whether resolver context was requested. |
| `resolver_context_used` | Whether resolver context was actually used. |
| `llm_call_made` | Whether a live LLM call was made. |
| `agentnet_call_made` | Whether a live AgentNet/MCP/resolver call was made. |
| `database_write_made` | Whether the run wrote to the controlled database. |
| `output_record_ids` | Ids of records the run produced. |
| `output_status` | Output governance status (defaults to `draft`). |
| `review_status` | Review status (defaults to `needs_review`). |
| `lifecycle_status` | Lifecycle status of the produced work. |
| `warnings` | Non-blocking governance warnings surfaced by the run. |
| `reasons` | Blocking reasons if the run was not permitted. |
| `created_at` | When the record was created. |
| `created_by` | Who/what created the record. |

## Phase 13 posture (defaults)

For any Phase 13 mock run, the draft always reflects:

- `llm_call_made = False`, `agentnet_call_made = False`, `database_write_made = False`.
- `output_status = draft`, `review_status = needs_review`.
- `agent_run_id`, `created_at`, `created_by` left unset — a future controlled-DB writer
  assigns them.
- `output_record_ids = []` — nothing is produced or stored.

## Storage (future)

No agent run record is created, written, or stored in this phase. Future DB writes require
the **controlled database integration** — the `agent_run_records` table (Phase 11
scaffold, [`DATABASE_RECORD_MODEL.md`](DATABASE_RECORD_MODEL.md)) plus a governed writer
under access control ([`DATABASE_ACCESS_AND_AUDIT.md`](DATABASE_ACCESS_AND_AUDIT.md)). The
[`AgentRunDraft`](../peak/agents/contracts.py) here is an **in-memory shape only**; it is
never persisted and holds no client data.

The **QA / Review Gate** (Phase 15, [`QA_REVIEW_GATE.md`](QA_REVIEW_GATE.md)) applies the
same posture to *review* decisions on those outputs: its `ReviewDecision` is an in-memory
shape only, with **no stored review records** in this phase. A future governed writer would
persist it as a `ReviewRecord` under the same access and audit rules.

The step that prepares this `AgentRunRecord` persistence — without performing it — is the
**Phase 19 Agent Run Persistence Mapping**
([`AGENT_RUN_PERSISTENCE_MAPPING.md`](AGENT_RUN_PERSISTENCE_MAPPING.md),
[`AGENT_RUN_WRITE_PLAN_POLICY.md`](AGENT_RUN_WRITE_PLAN_POLICY.md)): it maps an
`AgentTaskResult` + `AgentRunDraft` into an `AgentRunPersistenceDraft` and routes it through
the Phase 17 controlled writer boundary as a no-op plan targeting `agent_run_records` /
`create_agent_run_record`. It is **DB-aware but not DB-writing** — `agent_run_record_id` /
`created_at` stay unset for a future controlled DB writer, the review gate is preserved, and
write authority is anchored to the stored engagement/client/subject
(`request.authorization_scope == subject_snapshot.stored_authorization_scope`; identity
matching necessary but not sufficient). Agent execution still does not write directly to the
DB.
