# Agent Run Write Plan Policy (Phase 19)

The rules that govern how a Phase 13 agent run output becomes a *future* controlled write.
This is a governance **contract** enforced by the Phase 19 mapping
([`AGENT_RUN_PERSISTENCE_MAPPING.md`](AGENT_RUN_PERSISTENCE_MAPPING.md)) on top of the
Phase 17 boundary. It is **DB-aware but not DB-writing**: **write plans are not writes**, and
nothing is persisted here.

## Why agent run outputs must pass through controlled write planning

An `AgentRunRecord` is provenance for engagement work — what an agent produced, from which
inputs, under which prompt contract. It must not reach the database by an ad-hoc path.
Routing every agent run persistence attempt through the Phase 17 controlled writer boundary
means the same **table/action allowlist**, `idempotency_key`, and stored-scope checks apply
to agent runs as to any other record. **Agent execution still does not write directly to the
DB** — the harness governs and drafts, the mapper plans, and a future controlled DB writer
executes.

## Why `idempotency_key` is required

Every request must carry an `idempotency_key`. It is required now for future write safety: a
future controlled writer uses it to dedupe and to make retries replay-safe, so a repeated
agent run persistence attempt cannot create duplicate `agent_run_records` rows. A request
without one is denied before any draft or plan is built.

## Why `request.authorization_scope` must match `subject_snapshot.stored_authorization_scope`

Authority to write an agent run record depends on the governance state of the stored
engagement/client/subject it belongs to, not on whatever scope a request presents. The
mapping therefore requires
`request.authorization_scope == subject_snapshot.stored_authorization_scope`.
**Owner/client/engagement matching is necessary but not sufficient:** a request may match
identity yet carry a scope the subject does not store. The request scope alone is
insufficient.

## Why the stored subject snapshot is the authorization anchor

A new agent run record has **no stored DB row yet** — there is no persisted agent run record
to check a scope against. So the authorization anchor is the **stored
engagement/client/subject** (`AgentRunPersistenceSubjectSnapshot`), whose
`stored_authorization_scope` and `stored_lifecycle_status` are loaded (in future) from the
controlled DB. The new run record inherits its write authority from that stored subject,
which is why the snapshot — not the new record — carries the stored scope.

## Target table / action

- `target_table = agent_run_records`
- `requested_action = create_agent_run_record`

Both are on the Phase 17 allowlist ([`CONTROLLED_WRITE_ALLOWLIST.md`](CONTROLLED_WRITE_ALLOWLIST.md)).
The only Phase 19 persistence action is `prepare_agent_run_record_write_plan`.

## Review-gated defaults

The `AgentRunPersistenceDraft` preserves the gate — the mapper stamps these, never inheriting
a claim from the input:

- `output_status = draft`
- `review_status = needs_review`
- every "a call was made" flag (`database_write_made`, `llm_call_made`, `agentnet_call_made`,
  `network_call_made`, `client_facing_output_created`, `capsule_publication_made`) `false`

## What this phase does not do

- **No DB write in this phase** — no live database connection, no SQL execution, no stored
  records.
- **No direct writes from the agent execution harness.**
- **No live LLM/AgentNet execution in this phase** — the mapper maps an already-produced,
  no-op agent output; it never runs an agent, model, or resolver.
- **No client-facing output, no financial verification, no capsule publication.**

## Future controlled DB writer requirement

Executing the plan — opening a connection, inserting the `agent_run_records` row, assigning
`agent_run_record_id` / `created_at`, and recording an audit entry — requires a **future
controlled DB writer** under access control
([`DATABASE_ACCESS_AND_AUDIT.md`](DATABASE_ACCESS_AND_AUDIT.md)). **That write does not
happen in Phase 19.**
