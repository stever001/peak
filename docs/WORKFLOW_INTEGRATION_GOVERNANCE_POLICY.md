# Workflow Integration Governance Policy (Phase 35)

The governance rules that bind the managed-record workflow integration layer
([`peak/workflows/`](../peak/workflows/)). The layer's shape, contracts, and stage table are
documented in [`MANAGED_RECORD_WORKFLOW_INTEGRATION.md`](MANAGED_RECORD_WORKFLOW_INTEGRATION.md);
this file is the **policy** — what the layer may do, must never do, and how it fails.

---

## 1. Scope: integration only

Phase 35 is a **workflow integration phase, not a new persistence primitive phase**.

**No new persistence primitive.** No DB table, no DB model, no Alembic migration, no new Phase 17
allowlist pair. The Alembic head remains `009_intake_note_records`; `make db-check` still expects
exactly **15 tables**.

**No generic data path.** No generic CRUD, no generic DB writer, no arbitrary SQL executor, no broad
read/write repository, no ORM of its own, no API, no frontend.

**No new authority.** No report drafting, no report persistence, no client-facing report output, no
client-facing approval, no financial verification, no capsule publication, no AgentNet publish
operation, no AgentNet resolver call, no MCP call, no live LLM call, no MockLLM call, no agent
execution, no mock agent execution.

**No production or data-destroying path.** No production DB write path, no production data
cleanup/delete path, no runtime migrations from agents or workers, no seed data, no `examples/`, no
sample packets, no pseudo-client data, no client data, no local DB dumps, no committed credentials,
no committed `.env`.

---

## 2. Allowed calls

The layer may call **only** these six existing narrow writers, each through its own explicit API and
only under its own stage gate:

`persist_intake_note_record` · `persist_source_ingestion_record` · `persist_evidence_reference` ·
`persist_agent_task_queue_record` · `persist_review_bundle_record` ·
`persist_internal_reviewer_decision_record`

It must **not** import or call the Phase 22 `review_records` writer, any generic writer, any raw SQL
executor, any AgentNet / MCP / resolver connector, any LLM / mock-LLM / agent executor, or any
publication code. `review_records` and `agent_run_records` are never written by this layer.

The writers (which use SQLAlchemy) are imported **lazily** inside the persistence step. The
`peak.workflows` package imports no SQLAlchemy, no Alembic, no DB model, and no migration at module
scope, and runs plan-only without a database driver installed.

---

## 3. Gating

Persistence gates are **explicit and per-stage** (`persistence_gates: {stage: bool}`).

- **Plan-only is the default and is no-side-effect.** A missing or `False` gate means the stage is
  planned; no writer is called and no connection is opened.
- **No silent escalation.** A stage persists only when its gate is explicitly `True`, its payload is
  present and safe, and a `session_factory` is injected.
- **No ambient DSN fallback.** A gated stage with no injected `session_factory` is denied
  (`missing_session_factory`) before any connection is opened. Standard validation therefore needs
  **no live database credentials and no network**.
- **Unknown gate keys fail closed.** A `persistence_gates` entry naming an unknown stage, or a
  non-boolean value, denies the whole workflow before any stage runs.
- Payload safety and identity checks run in **plan-only mode too**, so an unsafe payload is reported
  before anyone turns its gate on.

---

## 4. Halt and denial semantics

The six stages are **linearly dependent**. When a stage produces `denied`, `conflicted`,
`failed_before_write`, or `write_outcome_uncertain`, the workflow records `halted_after_stage` and
every later stage is marked `halted` without being attempted.

- **`strict_mode = True`** — any stage warning halts the workflow after that stage.
- **`strict_mode = False`** — non-dependent warnings are collected into `result.warnings` and the
  workflow continues. A warning creates **no approval, client-facing, publication, financial, or
  execution effect** in either mode.
- Aggregate outcome: `denied` (pre-flight, nothing ran) · `planned` (nothing persisted) ·
  `persisted` (every gated stage persisted or replayed) · `partial` (some rows written, then
  halted) · `halted` (halted with nothing written).

---

## 5. Authorization

**The stored Engagement remains the authorization anchor.** Each narrow writer still loads the
stored `Engagement` and compares `request.authorization_scope` against the stored
`authorization_scope` at write time. **Identity matching is necessary but not sufficient.**

This layer **must not weaken writer authorization**. Its pre-flight checks are defense in depth:

- required identity/traceability fields (`owner_id`, `client_id`, `engagement_id`,
  `authorization_scope`, `requested_by`, `requester_role`) must all be present and bounded;
- `authorization_scope = revoked` is refused outright;
- every stage payload must match the workflow's `owner_id` / `client_id` / `engagement_id`;
- every payload carrying `authorization_scope` must match the workflow's;
- **cross-tenant and cross-engagement payloads are denied before any write.**

---

## 6. Content and leakage safety

**The workflow layer must not log or return raw payload bodies.**

**Prohibited keys.** A stage payload carrying an attribute whose name matches a prohibited marker is
denied **before** any writer is invoked — `credential`/`credentials`/secret and key names,
`database_url`, `db_url`, `dsn`, `connection_string`, `raw_sql`, `source_bytes`, `file_bytes`,
`generated_output`, `agent_output`, `llm_output`, `llm_prompt`, `prompt_text`, `raw_evidence_text`,
`raw_interview_text`, `raw_content`, `raw_text`, `packet_payload`, `raw_packet`, `payload`,
`final_client_report`, `client_facing_output`, `approve_internal`, `approve_client_facing`,
`publish_capsule`, `agentnet_publish`, `publish`, `resolver_credentials`, `stack_trace`,
`traceback`. Declared draft posture fields (`client_facing_approved`, `publication_allowed`,
`capsule_candidate_ready`, `execution_allowed`, `agentnet_context_allowed`, …) are known-safe and
are never name-scanned; only *unexpected* attributes are.

**Prohibited values.** Declared string fields are scanned with the public, DB-free Phase 32
`classify_prohibited_value_marker`. A credential/secret, DB-URL/DSN, raw-SQL, or raw-content marker
denies the stage. Only the **field name and the marker category** are reported — never the value. On
prose-ish (non-ref) fields a bare `JSON/object` verdict is narrowed to values that genuinely look
like a dumped object/array, so a legitimate worker-generated title such as
`"[draft] visual_observation — receiving_dock"` passes while an actual JSON dump still fails.

**Refs.** Stage id/ref fields must be short safe refs/IDs (bounded, no whitespace, no quotes).

**Prose exemption.** `note_text` is the one long-form field that legitimately carries authorized
operational prose destined for the managed DB. It is **never** scanned by this layer (ordinary prose
must pass) and **never** echoed in any result — content safety for it is enforced by Phase 34's
hardened credential-disclosure scanner. The orchestrator **may pass `note_text` to the intake
writer, but must never echo `note_text` in its own result.**

**Result sanitization.** Results carry only stage names, safe record refs, counts, reason codes, and
marker categories. They never echo the intake note body, raw packet payload, raw evidence or
interview text, source bytes, generated agent output, credentials or secrets, DSNs, raw SQL, stack
traces, final client-facing language, or approval decisions. Writer reasons and warnings are
re-scanned and replaced with a category-only placeholder if they would ever carry an unsafe marker.

---

## 7. Idempotency

Every key is **stage-namespaced** `wf35::<stage>::…`, so one string can never be reused across two
tables/actions. An explicit `stage_idempotency_keys[stage]` is respected as the stage-local
component; otherwise the key is derived deterministically from `workflow_id` plus a SHA-256 prefix
over the stage's safe, stable, **non-content** fields. With neither a `workflow_id` nor an explicit
key the stage is denied rather than given a random key. Keys exceeding the writers' 128-character
bound are denied. See the derivation table in
[`MANAGED_RECORD_WORKFLOW_INTEGRATION.md`](MANAGED_RECORD_WORKFLOW_INTEGRATION.md).

A replayed workflow returns each writer's `idempotent_replay` and creates **no duplicate row**. An
explicit stage key reused with a changed payload produces the writer's `idempotency_conflict`, which
halts the dependent stages.

---

## 8. Managed MySQL posture

Phase 35 orchestrates durable records intended for **managed remote MySQL** environments and changes
none of the rubric: **managed remote MySQL is the operational data store**; **Client Isolation
Option A is the default**; **SQLite is not the production-readiness proof path**; **managed MySQL
test/staging validation is required** before treating DB-backed functionality as production-ready;
the **production DB is not the main smoke-test target**. No DSN, no production DB test, and no
managed target is added to `make validate`. See
[`MANAGED_MYSQL_PERSISTENCE_RUBRIC.md`](MANAGED_MYSQL_PERSISTENCE_RUBRIC.md).

---

## 9. AgentNet publication policy

Unchanged and not implemented here. Clients do not operate any AgentNet publishing tools; the client
authorizes Peak in the consulting agreement to act as authorized capsule/node publisher; Peak
operates all publishing workflows as a managed service. No client-facing AgentNet publisher UI, no
client-held publishing credentials, no client-operated resolver publication tools, no direct client
publication path. **AgentNet publication remains deferred in Phase 35** — this phase preserves the
policy and implements no publishing. See
[`PEAK_OPERATED_AGENTNET_PUBLICATION_POLICY.md`](PEAK_OPERATED_AGENTNET_PUBLICATION_POLICY.md).

---

## 10. Enforcement

[`tests/validate_phase35_managed_record_workflow.py`](../tests/validate_phase35_managed_record_workflow.py)
enforces this policy: structural import bans, plan-only behavior, gate behavior, a fully persisted
gated workflow against a temporary SQLite database, stage denial/halt semantics, idempotency
derivation and replay/conflict behavior, content/leak safety with canary values, and the managed
MySQL / AgentNet publication policy regressions. It runs as part of `make validate`.

---

## Phase 36 — report planning stays outside this boundary

The Phase 36 internal assessment report planning boundary is DB-free and calls **no** writer, so it
adds no stage to this workflow and no table/action pair to the allowlist. Report planning consumes
this workflow's safe record refs; it never persists a report draft and never produces a
client-facing deliverable. See
[`INTERNAL_REPORT_ASSEMBLY_GOVERNANCE_POLICY.md`](INTERNAL_REPORT_ASSEMBLY_GOVERNANCE_POLICY.md).

---

## Phase 40 — the read-only workflow integration layer

`peak/workflows` now hosts a second integration layer with a different posture from the Phase 35
gated write path: the Phase 40 end-to-end internal report review workflow is **read-only**. The
governance rules carry over unchanged, with three additions specific to a read path:

1. **No gate exists, because nothing can be persisted.** There is no `persistence_gates` map, no
   writer call, and no idempotency key — only `session.get` and ORM `session.query`. Every
   side-effect flag on the result is a permanent `False` except `database_connection_made` and
   `sql_execution_made`.
2. **No ambient DSN, same as Phase 35.** A missing `session_factory` is a denial, not a fallback,
   so standard validation still needs no live credentials and no network.
3. **Derived state is labelled as derived.** A computed state never overwrites, and is never
   confused with, a stored column: the result reports the packet row's own stored decision columns
   alongside the computed state so the difference stays auditable. Stored values are never echoed —
   a blocker names the field and the expected value, never what was found.

The internal-only rule is unchanged: `ready_for_internal_use` is internal readiness and is **not**
client-facing approval, and no computed state may use approval, publication, or verification
vocabulary. See
[`INTERNAL_REPORT_REVIEW_WORKFLOW_INTEGRATION.md`](INTERNAL_REPORT_REVIEW_WORKFLOW_INTEGRATION.md).
