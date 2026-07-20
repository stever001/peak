# Internal Reviewer Decision Boundary (Phase 32)

A **decision-planning boundary** that lets Peak represent a **structured internal reviewer
decision** against a review bundle / review plan items. It produces a review-gated decision
*draft*, a decision-readiness assessment, and a deterministic **routing recommendation**. It is
**not** a review-approval phase and **not** a persistence phase.

This phase is analogous to Phase 29
([`PACKET_DERIVED_REVIEW_ORCHESTRATION_BOUNDARY.md`](PACKET_DERIVED_REVIEW_ORCHESTRATION_BOUNDARY.md)):
Phase 29 planned review bundles without DB writes; **Phase 32 plans reviewer decisions without DB
writes.**

## DB-free; does not persist reviewer decisions

**Phase 32 is DB-free.** It produces **no** `ControlledWriteRequest` objects and writes nothing —
no new table, no migration, no writer. **Phase 32 does not persist reviewer decisions**, **does not
call the Phase 22 review writer**, and creates **no `review_records` row**. Persistence of reviewer
decisions is owned by the separate **Phase 33** narrow DB-backed writer
([`INTERNAL_REVIEWER_DECISION_CONTROLLED_WRITER.md`](INTERNAL_REVIEWER_DECISION_CONTROLLED_WRITER.md)),
which stores review-gated, non-approval `internal_reviewer_decision_records` only. The package
imports only stdlib; it imports no SQLAlchemy / Alembic / `peak.db`,
no Phase 22 writer, no live/mock LLM, no AgentNet/MCP/resolver/connector, and no network module.

## Not an approval phase

It never approves anything, never calls `approve_internal`, never creates client-facing output,
never verifies financial impact, never publishes a capsule, never executes an agent (live or mock),
and never calls an LLM / AgentNet / MCP / resolver / network. Every draft stays
`output_status=draft` / `review_status=needs_review` / `lifecycle_status=draft` with
`approval_allowed=false`, `execution_allowed=false`, `publication_allowed=false`,
`financial_verified=false`, `authoritative=false`, `client_facing_approved=false`,
`capsule_candidate_ready=false`, `client_facing_output_created=false`, `review_approval_made=false`,
and `requires_human_review=true`.

**`ready_for_internal_use` is not approval.** It signals internal-reliance readiness only — it does
**not** authorize client-facing output, financial verification, capsule publication, agent
execution, or a `review_records` write.

## Public entry point

```
prepare_internal_reviewer_decision(request: InternalReviewerDecisionRequest)
    -> InternalReviewerDecisionResult
```

## Inputs — `InternalReviewerDecisionRequest`

`owner_id`, `client_id`, `engagement_id`, `requested_by`, `requester_role`, `authorization_scope`,
`idempotency_key`; `review_bundle_ref` **or** `review_bundle_record_id`; optional
`review_bundle_draft_ref`, `review_plan_item_refs`, `evidence_reference_ids`,
`source_ingestion_record_ids`, `agent_task_queue_record_ids`; `reviewer_role`, `decision_intent`,
`decision_reason_code`; optional `safe_decision_summary`, `return_to_stage`,
`requested_followup_actions`, `strict_mode`, safe `context`. **No raw `packet_payload`, raw
evidence/interview text, source bytes, generated agent output, arbitrary client content,
credentials/secrets, DB URLs, raw SQL, stack traces, or client-facing language may be supplied** —
only short ids/references, short safe labels, and a short safe summary.

## Decision intents

**Allowed:** `needs_more_evidence`, `return_for_revision`, `ready_for_internal_use`,
`blocked_by_scope`, `blocked_by_quality`, `blocked_by_missing_source`, `rejected_for_policy`,
`defer_review`.

**Disallowed (denied):** `approve_internal`, `approve_client_facing`, `final_approval`,
`publish_capsule`, `verify_financial_impact`, `execute_agent`, `create_report_for_client`,
`send_to_client`, and any freeform action implying approval, publication, execution, financial
verification, or client-facing output.

## Routing plan (recommendation only)

A deterministic routing recommendation per intent — a **recommendation only, not an action**:

| decision_intent | route_to |
| --- | --- |
| `needs_more_evidence` | `evidence_collection` |
| `return_for_revision` | `<return_to_stage>_revision` (else `packet_processing_revision`) |
| `ready_for_internal_use` | `internal_report_planning_candidate` |
| `blocked_by_scope` | `engagement_scope_review` |
| `blocked_by_quality` | `quality_remediation` |
| `blocked_by_missing_source` | `source_ingestion_followup` |
| `rejected_for_policy` | `governance_exception_review` |
| `defer_review` | `review_backlog` |

`return_to_stage` is refined to `<stage>_revision` only for the safe stages `packet_processing`,
`source_ingestion`, `evidence`, `task_queue`. **No routing step writes the DB, executes an agent,
calls an LLM, publishes a capsule, sends client-facing output, verifies financial impact, or
approves a review record.**

## Governance

Required: identity/scope/idempotency; a review-bundle reference; a short safe `reviewer_role`; an
allowed `decision_intent`; a short safe `decision_reason_code`; non-blocked lifecycle. A
`safe_decision_summary` must be a short single-line note; `requested_followup_actions` must be short
safe labels; any structured reference that carries owner/client/engagement/scope must match the
request — **identity matching is necessary but not sufficient**; scope must match too.

Denied / blocked: missing identity/scope/idempotency; missing review-bundle ref; missing
`reviewer_role` / `decision_intent` / `decision_reason_code`; prohibited lifecycle; identity or
scope mismatch; unsupported or disallowed (approval/publication/execution/financial/client-facing)
intent; raw-content / secret-like / DB-URL / raw-SQL fields; a `reviewer_role` that looks like an
email/credential; and multiline / over-long refs, labels, or summaries. Detection is by key name —
**values are never echoed**.

## Controlled write planning

**Phase 32 produces no `ControlledWriteRequest` objects** (`controlled_write_request_count == 0`).
It is DB-free; persistence is owned by the separate Phase 33 controlled writer, whose DB-layer
planner helper (`build_decision_controlled_write_request`) wraps a Phase 32 draft in a Phase 17
request — Phase 32 itself never builds one and never imports `peak.db`.

## Integration with Phase 31 (documented handoff)

Phase 31 packet processing can produce/persist `review_bundle_records`. Phase 32 consumes review
bundle references and safe reviewer selections to create internal decision drafts. **Phase 32 is
not automatically invoked from packet processing** — the handoff is by contract only: Phase 32
consumes safe references shaped like Phase 30 output (`review_bundle_record_id`) and Phase 29 output
(review plan item refs), with no DB access, no import of the Phase 30 writer, and no import of the
Phase 22 writer.

## Result and side-effect flags

`InternalReviewerDecisionResult` reports `outcome` (`denied` / `planned`), `permitted`,
`reason_code`, `decision_draft_count`, `routing_plan_count`, `readiness_assessment_count`,
`controlled_write_request_count` (always 0), `stages_completed` / `stages_skipped`, `reasons`,
`warnings`, and the aggregate side-effect flags — all of which stay `false`:
`direct_database_write_made`, `database_connection_made`, `sql_execution_made`,
`stored_record_created`, `review_records_write_made`, `review_approval_made`,
`client_facing_output_created`, `financial_verification_made`, `capsule_publication_made`,
`agent_execution_made`, `mock_agent_execution_made`, `llm_call_made`, `agentnet_call_made`,
`resolver_call_made`, `network_call_made`.

## Boundaries

- **No new table, no migration** — Alembic head remains `007_review_bundle_records`; still 13
  tables.
- **No DB writer, no `ControlledWriteRequest`, no CRUD, no raw SQL, no DB connection.**
- **No approval, no Phase 22 writer call, no `review_records` write, no client-facing output, no
  financial verification, no capsule publication.**
- **No agent / mock-agent / LLM / MockLLM / AgentNet / MCP / resolver / connector / network call**;
  **no `agent_run_records` write.**
- The package imports only stdlib.
