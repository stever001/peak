# Agent Run Persistence Mapping (Phase 19)

How a Phase 13 agent run output becomes a *future* controlled write plan for the
`agent_run_records` table — mapped precisely, but **not executed**. Phase 19 is
**DB-aware but not DB-writing**. **AgentNet integration is not complete.**

## Purpose

Phase 13 produces governed, no-op agent run outputs (`AgentTaskResult` + `AgentRunDraft`);
Phase 17 defines the generic controlled writer boundary. Neither, on its own, connects an
agent run to persistence. Phase 19 is that connective tissue: it maps an agent run output
into a production-shaped `AgentRunPersistenceDraft` and routes it through the Phase 17
boundary as a no-op write plan — so the path from "agent run" to "a governed future DB row"
is defined and testable without any database.

## How Phase 19 follows Phases 13 and 17

- **Phase 13** ([`AGENT_EXECUTION_HARNESS.md`](AGENT_EXECUTION_HARNESS.md),
  [`AGENT_RUN_RECORDS.md`](AGENT_RUN_RECORDS.md)) governs and records a (mock, non-executing)
  agent run — no side effects.
- **Phase 17** ([`CONTROLLED_DB_WRITER_BOUNDARY.md`](CONTROLLED_DB_WRITER_BOUNDARY.md))
  defines the generic controlled writer boundary: a **table/action allowlist**, an
  `idempotency_key` requirement, and a subject stored-scope check.
- **Phase 19** maps agent task results and agent run drafts into controlled write plans.
  **Agent execution still does not write directly to the DB** — running and
  persistence-planning are separate, and every future write goes through Phase 17.

## Core flow

```
AgentTaskResult / AgentRunDraft
  -> AgentRunPersistenceDraft        (production-shaped, review-gated)
  -> ControlledWriteSubject          (Phase 17, from the stored subject snapshot)
  -> ControlledWriteRequest          (target agent_run_records / create_agent_run_record)
  -> ControlledWritePlan             (Phase 17 no-op plan)
  -> no DB write
```

## DB-aware but not DB-writing

The `AgentRunPersistenceDraft` is **production-shaped** — its fields line up with the
`agent_run_records` table — but nothing is persisted:

- **no live database connection** and no database read/write;
- **no SQL execution**;
- **no stored records** and no stored data;
- the mapping result reports `database_write_made = false`, `database_connection_made =
  false`, `sql_execution_made = false`, `stored_record_created = false`, and the Phase 17
  plan's `requires_controlled_db_writer = true`;
- `agent_run_record_id` and `created_at` are left `None` — **future controlled DB writer**
  assignments.

A **write plan is not a write**; **write plans are not writes**. The mapping also makes
**no live LLM/AgentNet/network call**, produces **no client-facing output**, performs **no
financial verification**, and does **no capsule publication**.

## Production-shaped but still review-gated

The draft is ready in *shape* for controlled storage, but its *status* stays gated — the
mapping never advances authority:

- `output_status = draft`
- `review_status = needs_review`
- `database_write_made = false`, `llm_call_made = false`, `agentnet_call_made = false`,
  `network_call_made = false`, `client_facing_output_created = false`,
  `capsule_publication_made = false`

These are **stamped** by the mapper, never inherited from a claim on the input; and
governance rejects any `AgentTaskResult` that arrives with a side-effect flag set, off the
`draft` / `needs_review` gate, or not `permitted`.

The Phase 13 `AgentTaskResult` has no `network_call_made` or `capsule_publication_made`
field; those are **not** invented on the input — they are set `false` on the draft and the
mapping result.

## Subject stored-scope comparison

Because a new agent run record has **no stored DB row yet**, the write is authorized against
the stored engagement/client/subject. The mapping requires:

```
request.authorization_scope == subject_snapshot.stored_authorization_scope
```

**Owner/client/engagement matching is necessary but not sufficient:** the request must match
the subject snapshot's identity *and* the agent task request's identity (and the run draft's,
where present), and the request scope must equal the subject's stored scope. In Phase 19 the
stored scope is supplied in memory via
`AgentRunPersistenceSubjectSnapshot.stored_authorization_scope`; a future controlled writer
loads it from the controlled DB. See
[`AGENT_RUN_WRITE_PLAN_POLICY.md`](AGENT_RUN_WRITE_PLAN_POLICY.md) and
[`DB_BACKED_REVIEW_SCOPE_POLICY.md`](DB_BACKED_REVIEW_SCOPE_POLICY.md).

## Boundaries

- **No live database connection**, no database read/write, **no SQL execution**, **no stored
  records**.
- **No live LLM / AgentNet / MCP / resolver / network call.**
- **No client-facing output**, **no financial verification**, **no capsule publication.**
- **No direct writes from the agent execution harness** — persistence is always planned,
  never executed, in this phase, and always routed through the Phase 17 boundary. A **future
  controlled DB writer** performs the real write under
  [`DATABASE_ACCESS_AND_AUDIT.md`](DATABASE_ACCESS_AND_AUDIT.md).

## Realized by Phase 20

The plan this mapping produces is executed by the **Phase 20 Agent Run Controlled Writer**
([`AGENT_RUN_CONTROLLED_WRITER.md`](AGENT_RUN_CONTROLLED_WRITER.md)) — the first real
DB-backed persistence path. Phase 19 stays DB-free (this mapper imports no SQLAlchemy /
`peak.db`); Phase 20 lives in the DB layer and re-loads the authoritative stored
`Engagement` scope at write-time rather than trusting the snapshot here, then creates one
review-gated `agent_run_records` row under DB-enforced idempotency.

Note the distinct table: this mapping targets `agent_run_records` (the *output* of an executed
agent run). The **Phase 26 Controlled Agent Task Queue / Execution Readiness Boundary**
([`AGENT_TASK_QUEUE_READINESS_BOUNDARY.md`](AGENT_TASK_QUEUE_READINESS_BOUNDARY.md)) is upstream
and different: it plans review-gated, **not-executed** queue drafts (the
`agent_task_queue_records` table, persisted by the **Phase 27** writer
[`AGENT_TASK_QUEUE_CONTROLLED_WRITER.md`](AGENT_TASK_QUEUE_CONTROLLED_WRITER.md)) from derived
Phase 13 `AgentTaskRequest` objects, before any run exists. Phase 26 is DB-free and executes
nothing; neither Phase 26 nor the Phase 27 queue writer creates an `agent_run_records` row.
