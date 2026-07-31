# Internal Report Assembly Governance Policy (Phase 36)

The governance rules that bind the internal assessment report planning boundary
([`peak/reports/`](../peak/reports/)). The boundary's shape, contracts, and section table are
documented in
[`INTERNAL_ASSESSMENT_REPORT_PLANNING_BOUNDARY.md`](INTERNAL_ASSESSMENT_REPORT_PLANNING_BOUNDARY.md);
this file is the **policy** — what the boundary may do, must never do, and how it fails.

---

## 1. Scope: planning only

Phase 36 is a **report planning boundary only**. It assembles structure, traceability, and
readiness. It never produces a report.

**No persistence.** No DB table, no DB model, no Alembic migration, no DB writer, no report writer,
no report table, no report-draft persistence, no capsule-candidate persistence. Phase 36 produces
**no** `ControlledWriteRequest` objects and adds **no** Phase 17 allowlist pair.

**No generic data path.** No generic CRUD, no arbitrary SQL executor, no broad read/write
repository, no API, no frontend, no broadened DB access. The boundary **reads no database**.

**No new authority.** No client-facing report output, no client-facing approval, no final deliverable
generation, no financial or ROI/savings verification, no capsule publication, no AgentNet publish
operation, no AgentNet resolver call, no MCP call, no live LLM call, no MockLLM call, no agent
execution, no mock agent execution.

**No production or data-destroying path.** No production DB write path, no production data
cleanup/delete path, no runtime migrations from agents or workers, no seed data, no `examples/`, no
sample packets, no pseudo-client data, no client data, no local DB dumps, no committed credentials,
no committed `.env`.

---

## 2. Import discipline

`peak/reports/` imports **only stdlib** plus the public, DB-free Phase 32 value classifier
(`classify_prohibited_value_marker`). It must **not** import SQLAlchemy, Alembic, `peak.db`, any DB
writer, any AgentNet / MCP / resolver / connector module, any LLM / MockLLM / agent-executor module,
any network client, or any API/frontend module.

The package is **DB-free and network-free**.

---

## 3. Required inputs

A request is denied unless it carries all of:

`owner_id` · `client_id` · `engagement_id` · `authorization_scope` · `requested_by` ·
`requester_role` · one of `report_plan_id` / `idempotency_key`

and at least one governed record reference — unless `allow_empty_reference_plan=True` is set
explicitly, which produces a **skeletal plan with a warning** (every section unsupported, every
required category an open gap).

`authorization_scope="revoked"` is refused outright, as is a blocked `lifecycle_status`
(`revoked` / `archived` / `deleted_reference_only`).

---

## 4. Reference rules

Every reference must be **short, single-line, and safe**: bounded length (≤128), no newlines, no
whitespace, no quotes, matching `^[A-Za-z0-9_.:/-]{1,128}$`. Anything longer or multiline is treated
as raw content and denied.

References may be plain id strings or typed `GovernedRecordReference` objects. When a structured
reference carries `owner_id` / `client_id` / `engagement_id` / `authorization_scope`, each must match
the request. **Cross-tenant and cross-engagement references are denied**, and a scope mismatch is
denied even when the identity fields match — identity matching is necessary but **not sufficient**.

References are normalized to **sorted, de-duplicated** id lists, so caller ordering and repeats
cannot change the plan.

---

## 5. Section rules

Only the fourteen supported section ids are accepted. An unsupported section id is denied
(`unsupported_section`); a repeated section id is denied (`duplicate_section`). Sections are always
emitted in the module's canonical order, never the caller's.

---

## 6. Posture rules

The plan never advances authority. On both the request and the produced plan:

- `audience` must be `internal`; `client`, `external`, and anything else are denied.
- `client_facing_approved`, `financial_verified`, `capsule_candidate_ready`, `publication_allowed`,
  and `execution_allowed` must all be **false**.
- `requires_human_review` must be **true**.
- The plan is fixed at `output_status="plan"`, `review_status="needs_review"`,
  `lifecycle_status="draft"`.

A request that flips any of these is denied with `prohibited_posture`. There is **no send, share,
export, or client-approval path** anywhere in the package.

---

## 7. Financial verification

The plan may **name** items that would need a future financial gate
(`future_financial_verification_items`). It must never calculate ROI, verify savings, mark financial
impact verified, generate ROI claims, or approve financial statements for client use.
`financial_verified` stays false on the plan and on every candidate.

---

## 8. Capsule / AgentNet readiness

The plan may **name** items that might later become capsule candidates
(`future_capsule_candidate_items`). It must never create capsule candidates, persist capsule
candidates, publish capsules, or call AgentNet / resolver / MCP. `capsule_candidate_ready` and
`publication_allowed` stay false.

---

## 9. Content and leakage safety

**The boundary accepts references and safe labels only, never raw content.**

**Prohibited keys.** A request carrying an unexpected attribute (or a `context` key) whose name
matches a prohibited term is denied *before* any plan is assembled:

- credential/secret — `password`, `secret`, `api_key`, `apikey`, `token`, `private_key`,
  `credential(s)`, `connection_string`, `access_key`, `resolver_credentials`
- raw content — `note_text`, `raw_note_text`, `packet_payload`, `raw_packet`, `raw_evidence_text`,
  `raw_interview_text`, `raw_text`, `raw_content`, `evidence_text`, `interview_text`,
  `source_bytes`, `file_bytes`, `generated_output`, `agent_output`, `llm_output`, `llm_prompt`,
  `prompt_text`
- DB artifact — `database_url`, `db_url`, `dsn`, `raw_sql`, `sql_statement`, `stack_trace`,
  `traceback`
- disallowed intent — `final_client_report`, `client_facing_output`, `approval_decision`,
  `approve_internal`, `approve_client_facing`, `sign_off`, `publish_capsule`, `agentnet_publish`,
  `publish_report`, `send_to_client`, `export_client_deliverable`, `verify_financial`,
  `roi_verified`, `savings_verified`

Declared request fields are known-safe posture/identity/reference fields whose *values* are validated
explicitly, so only **unexpected** attributes and `context` keys are name-scanned. That is what stops
a smuggled `note_text` or `approve_client_facing` attribute.

**Prohibited values.** Reference and label values are scanned with the public Phase 32
`classify_prohibited_value_marker` plus a local stack-trace matcher. A credential/secret, DB-URL/DSN,
raw-SQL, raw-content, or stack-trace marker denies the request.

**Non-echoing.** Denials report only **field names, reference categories/positions, and marker
categories** — never the offending value. Reasons, warnings, and results never echo intake note text,
raw packet/evidence/interview text, source bytes, generated agent output, credentials, DSNs, raw
SQL, stack traces, final client-facing language, or approval decisions.

---

## 10. Determinism

The boundary is DB-free but must be **deterministic**: the same request always produces the same
plan. `plan_fingerprint` is a SHA-256 over the safe request fields, the section selection, and the
normalized references. **No random ids and no timestamps** are used anywhere in the package.

Candidate ids are positional and stable (`fnd_000`, `rec_000`, `gap_<section>_<category>`). Candidate
families are bounded at 200 slots and any truncation is reported as a warning — never silently.

---

## 11. Denial vocabulary

`missing_identity_field` · `invalid_identity_field` · `blocked_authorization_scope` ·
`blocked_lifecycle_status` · `missing_report_plan_id` · `invalid_report_plan_id` ·
`unsupported_audience` · `prohibited_posture` · `unsupported_section` · `duplicate_section` ·
`prohibited_content` · `reference_identity_mismatch` · `no_governed_references` ·
`unsupported_action` · `invalid_request_type`

---

## 12. Managed MySQL and AgentNet policies

Unchanged by this phase. **Managed remote MySQL is the operational data store**, **Client Isolation
Option A is the default**, **SQLite is not the production-readiness proof path**, and managed MySQL
test/staging validation is required before treating DB-backed functionality as production-ready. No
DSN, no production DB test, and no managed target is added to `make validate`.

The Peak-operated AgentNet publication policy is preserved and not implemented here: clients do not
operate any AgentNet publishing tools, the client authorizes Peak in the consulting agreement to act
as authorized capsule/node publisher, and there is no client-facing publisher UI, no client-held
publishing credentials, no client-operated resolver publication tools, and no direct client
publication path. See
[`PEAK_OPERATED_AGENTNET_PUBLICATION_POLICY.md`](PEAK_OPERATED_AGENTNET_PUBLICATION_POLICY.md).

---

## 13. Enforcement

[`tests/validate_phase36_internal_assessment_report_planning.py`](../tests/validate_phase36_internal_assessment_report_planning.py)
enforces this policy: structural import bans, successful deterministic planning, posture and section
behavior, evidence-trace and candidate behavior, gap behavior, the full denial matrix, content/leak
safety with canary values, and the managed MySQL / AgentNet publication policy regressions. It runs
as part of `make validate`.

---

## Phase 37 — persistence is a separate, narrow gate

Persisting a plan is Phase 37's job, not this boundary's. Phase 37 adds one narrow writer and one
allowlist pair (`internal_assessment_report_drafts` / `create_internal_assessment_report_draft`),
re-verifies this policy's internal-only posture at the write boundary, and stores structure and
references only. This package remains DB-free and produces no `ControlledWriteRequest`. See
[`INTERNAL_ASSESSMENT_REPORT_DRAFT_CONTROLLED_WRITER.md`](INTERNAL_ASSESSMENT_REPORT_DRAFT_CONTROLLED_WRITER.md).

---

## Phase 38 — review packets are a separate, narrow gate

Handing a persisted plan to a human reviewer is Phase 38's job. It adds one narrow writer and one
allowlist pair (`internal_report_review_packets` / `create_internal_report_review_packet`),
re-verifies the internal-only posture on both the packet and the stored report draft, and stores
labels, statuses, and references only. A packet is **pre-decision**: it carries no approval and no
reviewer outcome. See
[`INTERNAL_REPORT_REVIEW_PACKET_CONTROLLED_WRITER.md`](INTERNAL_REPORT_REVIEW_PACKET_CONTROLLED_WRITER.md).
