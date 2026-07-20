# Packet Processing Orchestration Policy (Phase 25)

The governance contract for the Phase 25 **controlled sequencing layer**
([`CONTROLLED_PACKET_PROCESSING_ORCHESTRATOR.md`](CONTROLLED_PACKET_PROCESSING_ORCHESTRATOR.md)).
It sequences existing narrow boundaries; it does not add write authority, tables, migrations,
or a generic pipeline.

## Allowed orchestration outputs

- The Phase 23 `PacketIngestionResult` and its derived plan (source ingestion draft, plan-only
  source `ControlledWriteRequest`, Phase 14 evidence requests, Phase 13 agent task requests).
- Phase 14 normalized evidence records (deterministic, DB-free).
- When explicitly requested with a `session_factory` and `plan_only=false`: narrow-writer
  receipts from the **Phase 24** source-ingestion writer and the **Phase 21** evidence writer.
- A typed `PacketProcessingReceipt` with counts, ids, stage names, safe metadata, warnings, and
  reason codes.

## Prohibited orchestration effects

The orchestrator may never: invent a generic writer dispatcher or CRUD layer; write a table
other than those already supported by existing narrow writers; bypass an existing controlled
write contract; run arbitrary SQL; import arbitrary files or store a packet payload; execute an
agent or **no live LLM** / **no AgentNet** / MCP / resolver / network call; create a
client-facing output (**no client-facing approval**); perform **no financial verification**; or
do **no capsule publication**. Adding a migration or new table is out of scope.

## Modes and the no-escalation rule

- **Plan-only is the default and no-side-effect.** Every side-effect flag is `false`.
- Controlled persistence runs only when `plan_only=false`, the stage is included, **and** a
  `session_factory` is supplied.
- **No stage may silently escalate from plan-only to persistence.** Absent inclusion,
  `plan_only=true`, or a missing `session_factory` each *skips* the persistence stage with a
  specific reason (`skipped_not_requested` / `skipped_plan_only` /
  `skipped_missing_session_factory`), never a silent write. A missing `session_factory` skips
  the stage; it does not fail the whole orchestration.

## Stage selection defaults

`plan_only=true`, `include_source_ingestion_persistence=false`,
`include_evidence_normalization=true`, `include_evidence_persistence=false`,
`include_agent_task_planning=true`, `include_agent_run_record_planning=false`,
`include_agent_run_record_persistence=false`.

## Authorization and identity

- Orchestrator **preflight checks are helpful but not authoritative**: they confirm request
  identity/scope, the packet reference's identity and authorization scope, and the derived
  source/evidence/agent identities.
- **Stored Engagement authorization remains authoritative** for every DB write and is enforced
  inside the existing narrow DB writers, which re-load the stored `Engagement` row at
  write-time and require `request.authorization_scope == engagement.authorization_scope`.
- **Identity matching is necessary but not sufficient.** The orchestrator does not replace or
  weaken writer authorization; a scope mismatch is denied by the writer even when identities
  match.

## Idempotency

Each narrow writer enforces its own DB-level idempotency over
`(owner_id, client_id, engagement_id, idempotency_key)`. The orchestrator passes the request's
`idempotency_key` to the source-ingestion writer, and derives a distinct per-record key
(`<idempotency_key>::evid::<i>`) for each evidence write so evidence records do not collide on
the shared boundary. Replay returns the existing row; a conflicting key is denied by the writer.

## Packet-content rule

The orchestrator **never stores or echoes raw packet payload content** in receipts, logs,
docs, exceptions, or persistence receipts. Forbidden in returned receipts: full `packet_payload`,
raw interview text, raw evidence text, raw source file bytes, arbitrary packet JSON,
credentials/secrets, stack traces, DB URLs, raw SQL. Only counts, ids, stage names, safe
metadata, warnings, and reason codes are returned. Derived Phase 14 requests carry only the
short, bounded, non-sensitive `raw_text_preview` produced by Phase 23.

## Deferred: agent-run persistence

Agent-run persistence (Phase 19/20) is intentionally **not** wired: it would require running
the Phase 13 mock executor (which consults the disabled `MockLLM` interface) and synthesizing a
run subject. When requested it is reported `skipped_no_safe_contract_path` with a clear reason.
Partial safe orchestration is preferable to unsafe breadth; a future phase may wire it through
Phase 19/20 only, tested for table/action safety.

Separately, the derived Phase 13 `AgentTaskRequest` objects surfaced by the agent task planning
stage are consumed by the **Phase 26 Controlled Agent Task Queue / Execution Readiness Boundary**
([`AGENT_TASK_QUEUE_READINESS_BOUNDARY.md`](AGENT_TASK_QUEUE_READINESS_BOUNDARY.md)) — a DB-free
boundary that plans review-gated, not-executed queue drafts. **Phase 28** wired this into the
orchestrator as the `agent_task_queue_readiness` (plan-only, default-on) and
`agent_task_queue_persistence` (opt-in) stages, the latter calling **Phase 27**
`persist_agent_task_queue_record` only under the same no-escalation gates as every other
persistence stage (`plan_only=false` + option on + `session_factory`). See
[`PACKET_TO_TASK_QUEUE_ORCHESTRATION_INTEGRATION.md`](PACKET_TO_TASK_QUEUE_ORCHESTRATION_INTEGRATION.md).
Persisting a queue record is not execution — no agent runs and no `agent_run_records` row is created.

The packet-processing receipt and task queue outputs (safe references) may also be handed to the
**Phase 29 Packet-Derived Review Orchestration Boundary**
([`PACKET_DERIVED_REVIEW_ORCHESTRATION_BOUNDARY.md`](PACKET_DERIVED_REVIEW_ORCHESTRATION_BOUNDARY.md))
for DB-free human-review planning. Phase 29 approves nothing and writes nothing; the handoff is by
contract only. **Phase 30** persists the resulting review bundle drafts into `review_bundle_records`
via a narrow DB writer — review-gated, **not-approved**, and never a `review_records` write.
**Phase 31** wired this into the orchestrator as the `review_orchestration` (plan-only, default-on)
and `review_bundle_persistence` (opt-in) stages, under the same no-escalation gates as every other
persistence stage; it approves nothing and never calls Phase 22. See
[`PACKET_TO_REVIEW_BUNDLE_ORCHESTRATION_INTEGRATION.md`](PACKET_TO_REVIEW_BUNDLE_ORCHESTRATION_INTEGRATION.md).
The **Phase 32** reviewer-decision boundary consumes the resulting review bundle refs separately
(DB-free, no approval); it is not invoked from packet processing.
