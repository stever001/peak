# Controlled Engagement Packet Processing Orchestrator (Phase 25)

A **controlled sequencing layer** over the existing narrow boundaries. It accepts an
engagement packet ingestion request, routes it through the Phase 23 ingestion boundary,
exposes the derived plan, and — only when explicitly requested and a `session_factory` is
supplied — persists through the existing narrow DB writers. It is **not** a generic importer,
workflow engine, CRUD layer, or write dispatcher. **AgentNet integration is not complete.**

## What it is (and is not)

The orchestrator only *sequences* boundaries that already exist and already enforce their own
governance:

- **Phase 23** ([`ENGAGEMENT_PACKET_INGESTION_BOUNDARY.md`](ENGAGEMENT_PACKET_INGESTION_BOUNDARY.md))
  validates the packet and derives a `SourceIngestionDraft`, a plan-only source
  `ControlledWriteRequest`, Phase 14 `EvidenceNormalizationRequest` objects, and Phase 13
  `AgentTaskRequest` objects — DB-free.
- **Phase 14** normalizes evidence deterministically (DB-free, no LLM).
- **Phase 24** ([`SOURCE_INGESTION_CONTROLLED_WRITER.md`](SOURCE_INGESTION_CONTROLLED_WRITER.md))
  persists exactly one `source_ingestion_records` row.
- **Phase 18 → 21** ([`EVIDENCE_PERSISTENCE_MAPPING.md`](EVIDENCE_PERSISTENCE_MAPPING.md),
  [`EVIDENCE_CONTROLLED_WRITER.md`](EVIDENCE_CONTROLLED_WRITER.md)) persist review-gated
  `evidence_references` rows.

It adds **no** new table, no migration, no generic writer, no arbitrary SQL, no importer, and
no workflow engine.

## Modes

### Plan-only (default) — no side effects

The default `plan_only=true` mode is **no-side-effect**. It:

- calls Phase 23 `prepare_packet_ingestion` and returns the `PacketIngestionResult`;
- exposes the derived `SourceIngestionDraft`;
- exposes the plan-only `ControlledWriteRequest` for `source_ingestion_records`;
- exposes derived Phase 14 `EvidenceNormalizationRequest` objects;
- exposes derived Phase 13 `AgentTaskRequest` objects (known registry agents only);
- calls **no** DB writer, **no** agent executor, **no live LLM**, **no AgentNet**/MCP/resolver,
  **no** network; stores no packet payload.

In plan-only mode every side-effect flag on the receipt is `false`.

### Controlled persistence — only when explicitly requested

Controlled persistence runs **only** when `plan_only=false`, the specific stage is included,
**and** a `session_factory` is supplied. It then calls only the existing narrow DB writers:

- the **Phase 24** source-ingestion writer for the source ingestion record;
- the **Phase 21** evidence writer (via Phase 18 mapping) for evidence records.

It must not invent a generic writer dispatcher, write any table other than those already
supported by existing narrow writers, bypass existing controlled write contracts, execute
agents or LLMs, create client-facing output, verify financial impact, or publish capsules.

**No stage may silently escalate from plan-only to persistence.** A persistence stage that is
not explicitly included, or that is requested while `plan_only=true`, or that has no
`session_factory`, is *skipped* with a specific reason — never executed.

## Stage selection and defaults

| Option | Default | Stage |
| --- | --- | --- |
| `plan_only` | `true` | gates all persistence |
| `include_evidence_normalization` | `true` | run Phase 14 worker (DB-free) |
| `include_agent_task_planning` | `true` | expose Phase 13 task requests (DB-free) |
| `include_source_ingestion_persistence` | `false` | Phase 24 writer |
| `include_evidence_persistence` | `false` | Phase 18 → 21 writer |
| `include_agent_run_record_planning` | `false` | *deferred (see below)* |
| `include_agent_run_record_persistence` | `false` | *deferred (see below)* |

### Agent-run persistence is intentionally left plan-only

Agent-run persistence (Phase 19/20) is **not wired** here. Wiring it would require running the
Phase 13 mock executor — which consults the disabled `MockLLM` interface — and synthesizing a
run subject. That is breadth this narrow orchestrator declines, per *partial safe orchestration
is preferable to unsafe breadth*. When requested, `agent_run_record_planning` /
`agent_run_record_persistence` are reported as `skipped_no_safe_contract_path` with a clear
reason. The derived Phase 13 `AgentTaskRequest` objects are still exposed (agent task planning);
no agent is ever executed.

## Authorization and identity model

The orchestrator performs deterministic **preflight** identity/consistency checks — request
`owner_id`/`client_id`/`engagement_id`/`authorization_scope`, the packet reference's identity
and authorization scope, and the derived source/evidence/agent identities. But **orchestrator
preflight checks are helpful but not authoritative**: **stored Engagement authorization remains
authoritative** for any DB write and is enforced inside the existing narrow DB writers, which
re-load the stored `Engagement` row at write-time. **Identity matching is necessary but not
sufficient** — a scope mismatch against the stored engagement is denied by the writer even when
every identity matches. The orchestrator does not replace writer authorization.

## Packet-content safety

The orchestrator **never stores or echoes raw packet payload content** — not in receipts,
logs, docs, exceptions, or persistence receipts. It may return counts, ids, stage names, safe
metadata, warnings, and reason codes. Forbidden in returned receipts: the full `packet_payload`,
raw interview text, raw evidence text, raw source file bytes, arbitrary packet JSON,
credentials/secrets, stack traces, DB URLs, and raw SQL. (Derived Phase 14 requests carry only
Phase 23's short, bounded, non-sensitive `raw_text_preview` — never full raw content.)

## Orchestration receipt

`process_engagement_packet` returns a `PacketProcessingReceipt` carrying: `orchestration_outcome`,
`permitted`, `reason_code`, `plan_only`; `stages_requested` / `stages_completed` /
`stages_skipped` / `stages_failed` and per-stage `stage_results`; the plan payload
(`packet_ingestion_result`, `source_ingestion_draft`, `source_controlled_write_request`,
`evidence_normalization_requests`, `agent_task_requests`); persistence receipts
(`source_ingestion_persistence_receipt`, `evidence_normalization_count`,
`evidence_persistence_receipts`, `agent_task_count`, `agent_run_persistence_receipts`); the
aggregate side-effect flags (`database_connection_made`, `sql_execution_made`,
`database_write_made`, `stored_record_created`, `llm_call_made`, `agentnet_call_made`,
`network_call_made`, `client_facing_output_created`, `financial_verification_made`,
`capsule_publication_made`); and `reasons` / `warnings`.

In plan-only mode all side-effect flags are `false`. In controlled persistence mode the DB
flags reflect **only** actual narrow-writer calls.

## Stage outcomes

Deterministic per-stage outcomes: `completed`, `skipped_not_requested`, `skipped_plan_only`,
`skipped_missing_session_factory`, `skipped_no_safe_contract_path`, `denied`,
`failed_before_write`, `write_outcome_uncertain`. A **persistence** stage is reported
`completed` only when a narrow DB writer actually created or replayed a row — never for merely
producing a plan. (The DB-free derivation stages — evidence normalization and agent task
planning — complete by producing their derived objects.)

## Boundaries

- **No new table, no migration** — Alembic head remains `005_source_ingestion_idem`.
- **No generic writer / dispatcher / CRUD / importer / workflow engine / raw SQL.**
- **No live LLM / AgentNet / MCP / resolver / network call**; no agent or LLM execution.
- **No client-facing approval, no financial verification, no capsule publication.**
- The Phase 23 ingestion package stays DB-free; the orchestrator imports the DB writers
  **lazily** so plan-only mode runs without SQLAlchemy.

## Handoff to Phase 26 (agent task queue / execution readiness)

The orchestrator's `agent_task_planning` stage exposes derived Phase 13 `AgentTaskRequest`
objects on `PacketProcessingReceipt.agent_task_requests` (it never executes them). The **Phase 26
Controlled Agent Task Queue / Execution Readiness Boundary**
([`AGENT_TASK_QUEUE_READINESS_BOUNDARY.md`](AGENT_TASK_QUEUE_READINESS_BOUNDARY.md)) is the DB-free
boundary that turns exactly those objects into review-gated, **not-executed** queue drafts and
readiness assessments. **Phase 28** wired this handoff directly into the orchestrator (see
[`PACKET_TO_TASK_QUEUE_ORCHESTRATION_INTEGRATION.md`](PACKET_TO_TASK_QUEUE_ORCHESTRATION_INTEGRATION.md)):
the `agent_task_queue_readiness` stage (DB-free, default-on) runs Phase 26
`prepare_agent_task_queue_plan` over those derived tasks and exposes queue drafts, readiness
assessments, and plan-only write requests on the receipt; the `agent_task_queue_persistence` stage
(off by default) persists them through **Phase 27** `persist_agent_task_queue_record` only when
`plan_only=false`, the option is on, and a `session_factory` is supplied. Persisting a queue record
is **not execution** — nothing here executes an agent, and no `agent_run_records` row is created.

Downstream, the **Phase 29 Packet-Derived Review Orchestration Boundary**
([`PACKET_DERIVED_REVIEW_ORCHESTRATION_BOUNDARY.md`](PACKET_DERIVED_REVIEW_ORCHESTRATION_BOUNDARY.md))
can consume this receipt's **safe references** (the packet-processing receipt ref, source-ingestion
/ evidence / agent-task-queue ids) to plan human review — a DB-free, no-approval boundary. The
handoff is by contract only; Phase 29 does not run inside this orchestrator.
