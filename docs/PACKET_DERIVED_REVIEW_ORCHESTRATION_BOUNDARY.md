# Packet-Derived Review Orchestration Boundary (Phase 29)

A **review-planning boundary** over packet-derived outputs. It organizes safe references,
receipts, and metadata from prior phases (packet processing, source ingestion, evidence, agent
task queue) into **review-ready** plans for human reviewers — review bundle drafts, review plan
items, and review readiness assessments. It is **not** a review-approval phase, a review engine, a
workflow engine, or a DB writer.

This phase is analogous to Phase 26
([`AGENT_TASK_QUEUE_READINESS_BOUNDARY.md`](AGENT_TASK_QUEUE_READINESS_BOUNDARY.md)): Phase 26
planned agent task queue readiness without DB writes; **Phase 29 plans human-review readiness
without DB writes.**

## DB-free; future persistence deferred

**Phase 29 is DB-free.** It produces **no** `ControlledWriteRequest` objects and writes nothing —
no new table, no migration, no writer. Future persistence of review plans (e.g. a
`review_bundle_records` table) is **deferred to a later phase**. The package imports only stdlib;
it imports no SQLAlchemy / Alembic / `peak.db`, no live/mock LLM, no AgentNet/MCP/resolver/
connector, and no network module.

## Not an approval phase

**"Ready for human review" never means approved.** This boundary never approves anything, never
performs `approve_internal`, never creates client-facing output, never verifies financial impact,
never publishes a capsule, never executes an agent (live or mock), and never calls an LLM /
AgentNet / MCP / resolver / network. It does **not** call or change the Phase 22 review writer and
creates **no `review_records` row**. Every draft stays `output_status=draft` /
`review_status=needs_review` / `lifecycle_status=draft` with `approval_allowed=false`,
`execution_allowed=false`, `publication_allowed=false`, `financial_verified=false`,
`authoritative=false`, `client_facing_approved=false`, `capsule_candidate_ready=false`, and
`requires_human_review=true`.

## Public entry point

```
prepare_packet_review_plan(request: PacketReviewOrchestrationRequest)
    -> PacketReviewOrchestrationResult
```

## Inputs — `PacketReviewOrchestrationRequest`

`owner_id`, `client_id`, `engagement_id`, `requested_by`, `requester_role`,
`authorization_scope`, `idempotency_key`; optional `packet_processing_receipt_ref`,
`source_ingestion_record_ids`, `evidence_reference_ids`, `agent_task_queue_record_ids`,
`agent_task_queue_draft_refs`, `source_ingestion_receipt_refs`, `evidence_receipt_refs`,
`task_queue_receipt_refs`, `reviewer_role`, `review_reason`, `strict_mode`, and safe `context`
metadata. **No raw `packet_payload`, raw evidence/interview text, source bytes, generated agent
output, arbitrary client content, credentials/secrets, DB URLs, raw SQL, or stack traces may be
supplied** — only short ids/references and safe metadata.

## Outputs

- **`ReviewBundleDraft`** — a single review-gated bundle for the packet review, carrying the safe
  reference lists and `ReviewSubjectReference` objects; `review_bundle_id=None` and
  `created_at=None` (nothing is stored).
- **`ReviewPlanItem[]`** — grouped safe references, each with `item_type`, `subject_refs` (ids
  only), `priority`, `required_reviewer_role`, and `status=needs_review`.
- **`ReviewReadinessAssessment`** — the deterministic readiness state (`ready_for_human_review` or
  a `blocked_*` state).

## Review plan item types

`source_ingestion_review`, `evidence_reference_review`, `agent_task_queue_review`,
`packet_processing_review`, `cross_stage_consistency_review` (only when more than one stage is
present), `missing_evidence_review` (source/task-queue subjects present but no evidence refs), and
`readiness_exception_review`.

## Review readiness states

`ready_for_human_review`, `blocked_no_subjects`, `blocked_invalid_scope`, `blocked_lifecycle`,
`blocked_raw_content`, `blocked_secret_like_content`, `blocked_execution_intent`,
`blocked_approval_intent`, `blocked_publication_intent`, `blocked_financial_verification_intent`.

## Governance

Required: `owner_id` / `client_id` / `engagement_id` / `requested_by` / `requester_role` /
`authorization_scope` / `idempotency_key`; `requested_action == prepare_packet_review_plan`;
lifecycle not `revoked` / `archived` / `deleted_reference_only`; at least one safe subject
reference in `strict_mode`; a `reviewer_role`, if supplied, that is a short role label (no
email/credential/PII-like value). Any structured subject reference that carries
owner/client/engagement/scope must match the request — **identity matching is necessary but not
sufficient**; scope must match too.

Denied / blocked: missing identity/scope/idempotency; subject identity or scope mismatch;
prohibited lifecycle; raw-content fields; secret-like fields; and approval / execution /
client-facing / publication / financial-verification intent (detected by key name — **values are
never echoed**). Non-string ref entries and over-long/multiline ref values are rejected as
raw/arbitrary content.

- `strict_mode=true` with no subjects → **denied**.
- `strict_mode=false` with no subjects → **permitted but `blocked_no_subjects`** (no side effects;
  no false claim that a stored review exists).

## Integration with Phase 25 / 28 (documented handoff)

The Phase 25 / 28 packet processor can hand its packet-processing receipt and task queue outputs
(all **safe references** — receipt refs, `source_ingestion_record_ids`, `evidence_reference_ids`,
`agent_task_queue_record_ids`) into Phase 29 for review planning. **Phase 29 does not run inside
Phase 25 / 28** — to avoid scope creep the handoff is by contract only: Phase 29 consumes safe
references shaped like Phase 25 / 28 outputs, with no DB access, no import of the Phase 27 writer,
and no call to the Phase 22 writer. A future phase may add a small DB-free integration point; it
would remain plan-only and no-side-effect.

## Result and side-effect flags

`PacketReviewOrchestrationResult` reports `outcome` (`denied` / `planned` / `blocked`),
`permitted`, `reason_code`, `review_bundle_count`, `review_plan_item_count`,
`readiness_assessment_count`, `subject_count`, `blocked_subject_count`,
`controlled_write_request_count` (always 0 in Phase 29), `stages_completed` / `stages_skipped`,
`reasons`, `warnings`, and the aggregate side-effect flags — all of which stay `false` in Phase 29:
`direct_database_write_made`, `database_connection_made`, `sql_execution_made`,
`stored_record_created`, `review_approval_made`, `client_facing_output_created`,
`financial_verification_made`, `capsule_publication_made`, `agent_execution_made`,
`mock_agent_execution_made`, `llm_call_made`, `agentnet_call_made`, `resolver_call_made`,
`network_call_made`.

## Boundaries

- **No new table, no migration** — Alembic head remains `006_agent_task_queue_records`; still 12
  tables.
- **No DB writer, no `ControlledWriteRequest`, no CRUD, no raw SQL, no DB connection.**
- **No approval, no client-facing output, no financial verification, no capsule publication.**
- **No agent / mock-agent / LLM / MockLLM / AgentNet / MCP / resolver / connector / network call**;
  **no `agent_run_records` and no `review_records` write.**
- The package imports only stdlib.
