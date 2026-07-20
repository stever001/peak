# Review Orchestration Governance Policy (Phase 29)

The governance contract for the Phase 29 **review-planning** boundary
([`PACKET_DERIVED_REVIEW_ORCHESTRATION_BOUNDARY.md`](PACKET_DERIVED_REVIEW_ORCHESTRATION_BOUNDARY.md)).
It plans review-ready, **not-approved** bundles and plan items from safe packet-derived
references. It adds no approval authority, no table, no migration, and no writer.

## Allowed outputs

- Review-gated `ReviewBundleDraft` objects (never persisted, never approved).
- Deterministic `ReviewPlanItem` objects (safe references only).
- Deterministic `ReviewReadinessAssessment` objects.
- A typed `PacketReviewOrchestrationResult` with counts, stage names, safe reasons, and warnings.

Phase 29 produces **no** `ControlledWriteRequest` objects — it is **DB-free**. Persistence of a
review bundle draft is provided by the **Phase 30** narrow review-bundle writer
([`REVIEW_BUNDLE_CONTROLLED_WRITER.md`](REVIEW_BUNDLE_CONTROLLED_WRITER.md)), which persists a
review-gated, **not-approved** `review_bundle_records` row and creates no `review_records` row.
Phase 29 stays DB-free and unchanged.

## Prohibited effects

The boundary may never: approve anything (no `approve_internal`, no final QA signoff); create
client-facing output; verify financial impact; publish a capsule; execute an agent (live or mock);
call a live LLM / MockLLM / AgentNet / MCP / resolver / connector / network; open a DB connection,
run SQL, or write a row; call or change the Phase 22 review writer; or create a `review_records` or
`agent_run_records` row. **"Ready for human review" never means approved.**

## Request-level requirements

- `owner_id`, `client_id`, `engagement_id`, `requested_by`, `requester_role`,
  `authorization_scope`, and `idempotency_key` present.
- `requested_action` is `prepare_packet_review_plan`.
- `authorization_scope` is not `revoked`; `lifecycle_status` is not `revoked` / `archived` /
  `deleted_reference_only`.
- At least one safe subject reference in `strict_mode` (else denied). With `strict_mode=false`
  and no subjects, the request is permitted but reported `blocked_no_subjects` — no side effects
  and no false claim that a stored review exists.
- `reviewer_role`, if supplied, is a **short role label** — never an email, credential, or
  PII-like value.
- **No raw-content fields** (`packet_payload`, `raw_evidence`, `interview_text`, `source_bytes`,
  `generated_output`, … / any `payload`), **no secret-like fields** (`password`, `secret`,
  `api_key`, `token`, `private_key`, `credential`, `connection_string`, `access_key`), and **no
  approval / execution / client-facing / publication / financial-verification intent keys**
  (`approve`, `sign_off`, `client_facing`, `execute`, `run_agent`, `publish`, `capsule`,
  `verify_financial`, …) anywhere in the request or its `context`. Only **key names** are ever
  reported — secret and raw **values are never echoed**.
- Every id/reference must be a **short string** (≤128 chars, single line). Non-string entries
  (arbitrary JSON/objects) and over-long/multiline values are rejected as raw/arbitrary content.

A request-level failure denies the whole request (`outcome=denied`), side-effect free, and the
result still carries a `blocked_*` readiness assessment (e.g. `blocked_secret_like_content`,
`blocked_raw_content`, `blocked_approval_intent`, `blocked_lifecycle`, `blocked_invalid_scope`).

## Identity and scope (necessary but not sufficient)

Plain id-list entries carry no identity and are trusted as belonging to the request's authorized
scope (the caller supplied them under the authorized request). Any **structured** subject
reference (e.g. in `context['subject_refs']`) that carries owner/client/engagement/scope must
match the request; owner/client/engagement matching is necessary but **not sufficient** — the
authorization scope must match too. A mismatch is `blocked_invalid_scope`.

## No persistence, no approval

Phase 29 is a planning boundary. It stores nothing, approves nothing, and calls no writer. A human
reviewer acts on these plans; a separate, existing gate (Phase 15/22) governs any actual review
decision — Phase 29 does not change those and does not pre-empt them. **Phase 31** invokes this
planner (and, opt-in, the Phase 30 writer) from the Phase 25/28 orchestrator without relaxing any
rule here — it approves nothing and never calls Phase 22. **Phase 32**
([`INTERNAL_REVIEWER_DECISION_GOVERNANCE_POLICY.md`](INTERNAL_REVIEWER_DECISION_GOVERNANCE_POLICY.md))
plans a structured reviewer decision over the resulting bundle refs — still DB-free, still no
approval, still no `review_records` write.
