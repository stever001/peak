# Internal Reviewer Decision Governance Policy (Phase 32)

The governance contract for the Phase 32 **decision-planning** boundary
([`INTERNAL_REVIEWER_DECISION_BOUNDARY.md`](INTERNAL_REVIEWER_DECISION_BOUNDARY.md)). It plans
review-gated, **not-approved** internal reviewer decision drafts and routing recommendations from
safe review-bundle references and safe reviewer selections. It adds no approval authority, no table,
no migration, and no writer.

## Allowed outputs

- A review-gated `InternalReviewerDecisionDraft` (never persisted, never approved).
- A deterministic `ReviewerDecisionRoutingPlan` (recommendation only).
- A `ReviewerDecisionReadinessAssessment`.
- A typed `InternalReviewerDecisionResult` with counts, stage names, safe reasons, and warnings.

Phase 32 produces **no** `ControlledWriteRequest` objects — it is **DB-free**; persistence is owned
by the separate **Phase 33** controlled writer
([`INTERNAL_REVIEWER_DECISION_CONTROLLED_WRITER.md`](INTERNAL_REVIEWER_DECISION_CONTROLLED_WRITER.md)).

## Prohibited effects

The boundary may never: persist a reviewer decision; call the **Phase 22** review writer; create a
`review_records` row; call `approve_internal`; approve anything; create client-facing output; verify
financial impact; publish a capsule; execute an agent (live or mock); or call an LLM / MockLLM /
AgentNet / MCP / resolver / connector / network. **`ready_for_internal_use` is not approval.**

## Request-level requirements

- `owner_id`, `client_id`, `engagement_id`, `requested_by`, `requester_role`,
  `authorization_scope`, and `idempotency_key` present.
- `requested_action` is `prepare_internal_reviewer_decision`.
- A `review_bundle_ref` **or** `review_bundle_record_id` is present.
- `reviewer_role` is a **short safe role label** (no email/credential/PII-like value).
- `decision_intent` is one of the allowed intents (see below).
- `decision_reason_code` is a short safe reason code.
- `safe_decision_summary`, if supplied, is a short single-line note (no raw content).
- `requested_followup_actions` are short safe labels only.
- `return_to_stage`, if supplied, is one of `packet_processing` / `source_ingestion` / `evidence`
  / `task_queue`.
- `authorization_scope` is not `revoked`; `lifecycle_status` is not `revoked` / `archived` /
  `deleted_reference_only`.
- **No raw-content fields** (`packet_payload`, `raw_evidence`, `interview_text`, `source_bytes`,
  `generated_output`, … / any `payload`), **no secret-like fields** (`password`, `secret`,
  `api_key`, `token`, `private_key`, `credential`, `connection_string`, `access_key`), and **no
  DB-URL / raw-SQL / stack-trace fields** (`database_url`, `raw_sql`, `stack_trace`, …) anywhere in
  the request or its `context`. Only **key names** are ever reported — secret and raw **values are
  never echoed**.
- Every id/reference/label must be a **short single-line string**; non-string entries and
  over-long/multiline values are rejected as raw/arbitrary content.

A request-level failure denies the whole request (`outcome=denied`), side-effect free, and the
result still carries a `blocked_*` readiness assessment (e.g. `blocked_secret_like_content`,
`blocked_raw_content`, `blocked_disallowed_intent`, `blocked_unsupported_intent`,
`blocked_lifecycle`, `blocked_invalid_scope`, `blocked_missing_review_bundle`).

## Allowed vs. disallowed decision intents

**Allowed:** `needs_more_evidence`, `return_for_revision`, `ready_for_internal_use`,
`blocked_by_scope`, `blocked_by_quality`, `blocked_by_missing_source`, `rejected_for_policy`,
`defer_review`.

**Disallowed (denied as `blocked_disallowed_intent`):** any intent implying approval
(`approve_internal`, `approve_client_facing`, `final_approval`, `sign_off`), publication
(`publish_capsule`, `capsule…`), execution (`execute_agent`, `run_agent`), financial verification
(`verify_financial_impact`), or client-facing output (`create_report_for_client`, `send_to_client`,
`client_facing…`). Any other unrecognized intent is denied as `blocked_unsupported_intent`.

Crucially: **`ready_for_internal_use` is not approval** — it does not authorize client-facing
output, financial verification, capsule publication, agent execution, or a `review_records` write.

## Identity and scope (necessary but not sufficient)

Plain id-list entries carry no identity and are trusted as belonging to the request's authorized
scope. Any **structured** reference (e.g. in `context['subject_refs']`) that carries
owner/client/engagement/scope must match the request; owner/client/engagement matching is necessary
but **not sufficient** — the authorization scope must match too. A mismatch is
`blocked_invalid_scope`.

## No persistence, no approval

Phase 32 is a planning boundary. It stores nothing, approves nothing, and calls no writer. A human
reviewer acts on these drafts; a separate, existing gate (Phase 15/22) governs any actual review
record — Phase 32 does not change those and does not pre-empt them. Persistence of reviewer
decisions is owned by the **Phase 33** controlled writer, which stores review-gated, **non-approval**
`internal_reviewer_decision_records` only (still no approval, no `review_records` write).
