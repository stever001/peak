# Implementation Plan

A phased plan that goes from today's scaffolding to a working internal operating
system, without overbuilding. Each phase is shippable and de-risks the next.

**Guiding rule:** prove the workflow with the lightest possible machinery before
adding structure, storage, or automation.

---

## Phase 0 — Scaffolding *(this phase)*

**Goal:** a clean, understandable repository that defines the operating model,
workflows, data objects, and plan.

- [x] Repository structure (`agents/`, `schemas/`, `prompts/`, `tests/`, `tools/`,
  `docs/`). *(An early `examples/` tree was later removed — the repo stores no data
  artifacts; see the repo-cleanup note under the first-workflow phase.)*
- [x] `README.md` — purpose, internal-vs-client-facing distinction, first workflow.
- [x] `docs/OPERATING_MODEL.md`
- [x] `docs/AGENT_WORKFLOWS.md`
- [x] `docs/DATA_OBJECTS.md`
- [x] `docs/IMPLEMENTATION_PLAN.md`

**Exit criteria:** a developer, consultant, and investor can each read the repo and
understand what Peak is building and why. No agent logic yet.

---

## Phase 1 — Data object schemas & examples

**Goal:** turn the candidate data objects into concrete, portable schemas with
worked examples.

- [x] Define schemas under `schemas/` (portable, serialization-neutral JSON Schema
  draft 2020-12, no vendor lock-in).
- [x] First-thread objects defined: `ClientIntake`, `EvidenceReference`,
  `StakeholderInterview`, `VisualObservation`, `WorkflowObservation`,
  `InventorySystemProfile`.
- [x] Validation harness added under `tests/` (`validate_phase1.py`): schema
  self-check, fixture conformance, and prefix lint. Dev dependency pinned in
  `requirements-dev.txt`. (Originally validated committed example records; those were
  later removed and replaced with **synthetic fixtures generated at runtime** — see the
  repo-cleanup note below.)

**Exit criteria:** every first-thread object has a schema and a passing validation test
against a representative (now synthetic) instance. Still no live agents. — **Met.** Run
`make validate`
(or `python3 tests/validate_phase1.py`); exits 0 on pass, and unresolved
cross-references are non-blocking warnings in Phase 1.

---

## Phase 2 — First workflow, human-in-the-loop

**Goal:** prove the end-to-end thread with agent-assisted drafting, run manually.

**Groundwork done — the operating unit:**

- [x] `EngagementPacket` schema ([`schemas/engagement-packet.schema.json`](../schemas/engagement-packet.schema.json))
  and worked example: one self-contained bundle of an engagement's first-thread
  assessment (intake, system profile, evidence, interviews, observations), composing
  the Phase 1 objects by local relative `$ref`. This is the practical unit future
  agents will read from and write to.
- [x] Packet-level validation ([`tests/validate_phase2.py`](../tests/validate_phase2.py)):
  offline `$ref` resolution, packet conformance, and **blocking** referential
  integrity (evidence resolves within the packet; nested `related_intake_id`s match
  the packet's intake). Run via `make validate`.

No agent logic yet — the packet is the data contract that agent work will build on.

**Prompt contracts done — the operating instructions:**

- [x] Reusable **prompt contracts** in [`../prompts/`](../prompts/) for the whole
  first thread — intake, discovery planning, evidence findings, initial report,
  next-phase proposal, QA review, and engagement lessons. Each is a markdown contract
  (purpose, inputs, grounding/evidence rules, non-goals, output format, quality
  checks, reusable body) that a consultant copies into an LLM. Most operate on an
  `EngagementPacket` and require citing packet `evid_` ids.
- [x] Prompt-inventory check ([`tests/validate_phase3_prompts.py`](../tests/validate_phase3_prompts.py),
  stdlib-only) wired into `make validate`.

These are **human-run prompt contracts, not autonomous agents**, and are internal-only.

**Output structure contract (no committed samples):**

- [x] Each contract's expected output structure is exercised by
  [`../tests/validate_phase4_outputs.py`](../tests/validate_phase4_outputs.py),
  stdlib-only, which **generates a synthetic document at runtime** and checks its
  sections. No sample outputs are committed — real work product lives in controlled
  engagement storage.

**Local runner — human-in-the-loop helper:**

- [x] [`../tools/packet_runner.py`](../tools/packet_runner.py) requires an explicit
  `--packet` path (a real packet from controlled storage; no demo/sample mode): a
  read-only helper that summarizes an `EngagementPacket` and points a consultant at the
  right prompt contract. Makes **no** LLM/API/database/AgentNet/network call and
  **stores nothing** — deliberately not an agent runtime. Smoke-tested by
  [`../tests/validate_phase5_runner.py`](../tests/validate_phase5_runner.py) (which
  passes a temporary synthetic fixture via `--packet`, then deletes it) in
  `make validate`.

**Consultant operating guide:**

- [x] [`CONSULTANT_WORKFLOW.md`](CONSULTANT_WORKFLOW.md): the end-to-end
  human-in-the-loop process a consultant follows (notes → intake → evidence/profile/
  interviews/observations → packet → summary → prompt contract → QA → save → lessons),
  with consultant rules, the QA readiness ladder, the command reference, a file map,
  and an explicit statement of the current phase boundary. Doc-checked by
  [`../tests/validate_phase6_docs.py`](../tests/validate_phase6_docs.py) in
  `make validate`. Documentation only — no new runtime.

**Data-handling policy + repo cleanup (source assets only):**

- [x] [`DATA_HANDLING_POLICY.md`](DATA_HANDLING_POLICY.md) and
  [`FIXTURE_STRATEGY.md`](FIXTURE_STRATEGY.md): a policy for a **private, internal**
  (not open-source) project. The repo holds **source assets only** and stores **no data
  artifacts**; client data is never committed and lives in controlled engagement
  storage / private resolver capsules; real client data may be used only for authorized
  live engagements and never for fixtures/tests/demos. No external publication,
  cross-client reuse, or AgentNet publication without governance approval.
- [x] **Cleanup:** the former `examples/` tree (sample packets, sample outputs, and the
  old redaction guide) was **removed**. Validation now generates **synthetic fixtures at
  runtime** in temp directories; the packet runner requires an explicit `--packet`
  (no demo/sample mode). Enforced
  by [`../tests/validate_phase7_policy.py`](../tests/validate_phase7_policy.py), which
  fails if data artifacts reappear. Operational first policy, later legal review — does
  **not** claim legal compliance.

**Still to do:**

- Implement lightweight agents in `agents/intake/`, `agents/discovery/`,
  `agents/evidence/`, `agents/reporting/`, `agents/proposal/` that take structured
  input and produce structured output conforming to the schemas (the prompt contracts
  above are the specification for that behavior). The runner is the manual precursor: it
  orients the consultant without automating the LLM step.
- Keep everything file-based and consultant-run; **no database, no frontend.**
- Enforce evidence-first: agent outputs must cite `EvidenceReference`s.

**Exit criteria:** a consultant can run one real (anonymized) engagement through the
thread end-to-end and get a reviewable draft report and proposal.

---

## Phase 3 — QA / governance and learning capture

**Goal:** close the loop with quality gating and reusable knowledge.

**Prompt contracts done (groundwork):**

- [x] `prompts/qa/review-assessment-packet.prompt.md` — strict QA of a packet and any
  draft report/proposal (unsupported claims, missing evidence, contradictions,
  readiness score, required fixes).
- [x] `prompts/learning/extract-engagement-lessons.prompt.md` — reusable lessons and
  **draft** candidate knowledge capsules (explicitly not yet grounded/published to
  AgentNet).

**Still to do:**

- Implement `agents/qa/`: checks for evidence traceability, consistency, and
  completeness; produces QA findings and a sign-off record.
- Implement `agents/learning/`: capture reusable knowledge from each engagement.
- Define how learning entries feed back into future runs.

**Exit criteria:** no client-facing artifact is produced without a QA record, and
each engagement yields at least one reusable knowledge entry.

---

## Phase 4 — AgentNet grounding integration

**Goal:** move AgentNet from *intended architecture* to *live grounding*.

- Integrate AgentNet as the grounding/resolution layer for agent outputs.
- Reconcile outputs against Peak methodology and prior engagements.
- Update docs to reflect what is genuinely live (and only what is live).

**Exit criteria:** agent outputs are demonstrably grounded/resolved via AgentNet,
and documentation accurately states integration status.

> Until this phase is complete, no file may claim AgentNet integration is done.

---

## Phase 5 — Hardening & scale (internal)

**Goal:** make the internal system robust enough for routine use across consultants.

**Controlled data architecture defined (groundwork — docs/schemas only):**

- [x] The target data layer that lives **outside** the repo is documented:
  [`CONTROLLED_DATA_ARCHITECTURE.md`](CONTROLLED_DATA_ARCHITECTURE.md) (repo-vs-data
  lanes, classification model, diagram), [`ENGAGEMENT_DATA_MODEL.md`](ENGAGEMENT_DATA_MODEL.md)
  (conceptual model incl. `FinancialImpactEstimate`),
  [`RESOLVER_CAPSULE_ARCHITECTURE.md`](RESOLVER_CAPSULE_ARCHITECTURE.md) (private resolver
  capsules), and [`SOURCE_SYSTEM_CAPSULIZATION.md`](SOURCE_SYSTEM_CAPSULIZATION.md)
  (source→capsule path). Architecture-contract schemas (`engagement-record`,
  `financial-impact-estimate`, `source-system-reference`, `resolver-capsule-record`) are
  added as shapes only — **no instances committed**. Doc-checked by
  [`../tests/validate_phase8_architecture.py`](../tests/validate_phase8_architecture.py).
  **Architecture/docs/schemas only** — no database, API, resolver, ingestion pipeline, or
  AgentNet integration is implemented.

**Governance state contracts defined (groundwork — docs/enum-schemas only):**

- [x] The allowed statuses, transitions, and human-review gates are documented in
  [`GOVERNANCE_STATES.md`](GOVERNANCE_STATES.md) (eight state families) and
  [`STATE_TRANSITIONS.md`](STATE_TRANSITIONS.md) (transitions + agent guardrails), with
  enum contracts `governance-state` (master), `authorization-scope`, `review-status`,
  `lifecycle-status`. The Phase 8 schemas now `$ref` these canonical enums. Contract-only
  (no instances, no engine); agent output defaults to `draft`/`needs_review` and agents
  may never set `client_facing_approved`. Checked by
  [`../tests/validate_phase9_governance.py`](../tests/validate_phase9_governance.py).

**Controlled database plan defined (groundwork — docs only):**

- [x] The staged plan for the controlled engagement database is documented:
  [`DATABASE_IMPLEMENTATION_PLAN.md`](DATABASE_IMPLEMENTATION_PLAN.md) (Phase 10 plan →
  11 minimal scaffold → 12 resolver/capsule adapter → 13 agent harness → later controlled
  ingestion; no vendor/SQL yet), [`DATABASE_RECORD_MODEL.md`](DATABASE_RECORD_MODEL.md)
  (planned record groups), [`DATABASE_ACCESS_AND_AUDIT.md`](DATABASE_ACCESS_AND_AUDIT.md)
  (roles, audit fields, agent permission limits), and
  [`DATABASE_TO_RESOLVER_MAPPING.md`](DATABASE_TO_RESOLVER_MAPPING.md) (capsule readiness;
  public-but-segregated vs. private resolver). The database is a **pre-capsulization
  staging layer** serving immediate consulting delivery and future AI-readiness in
  parallel. **Planning only** — no database, migrations, DB config, API, resolver, or
  ingestion code. Checked by
  [`../tests/validate_phase10_database_plan.py`](../tests/validate_phase10_database_plan.py).

**Controlled database scaffold (Phase 11 — source assets only):**

- [x] MySQL chosen as the controlled engagement database; Python tooling layer is
  SQLAlchemy + Alembic + PyMySQL. Added [`../peak/db/`](../peak/db/) (base, enums,
  models, session), [`../alembic/`](../alembic/) with an initial migration that defines
  **schema only** (no inserts, no data), `.env.example` (placeholders), and
  [`DATABASE_SCAFFOLD.md`](DATABASE_SCAFFOLD.md). Enum values mirror the Phase 9 schema
  contracts (the source of truth). **No client data, seed data, fixtures, dumps, DB
  files, or credentials** are committed; `.env` is gitignored. Checked by
  [`../tests/validate_phase11_db_scaffold.py`](../tests/validate_phase11_db_scaffold.py)
  (`make db-check`). Local scaffold only — no production deployment, API, resolver,
  ingestion, agent runtime, or AgentNet integration.

**AgentNet MCP boundary (Phase 12 — governance wrapper scaffold):**

- [x] Peak-side **governance wrapper** for future use of the **existing AgentNet MCP
  connector** (a separate repo; not reimplemented or copied here). Added
  [`../peak/agentnet/`](../peak/agentnet/) — request/response contracts
  (`contracts.py`), deterministic guard checks (`governance.py`:
  `evaluate_resolve_request`, `evaluate_history_request`,
  `evaluate_capsule_validation_request`, `build_tool_call_plan`), and a **no-network mock
  boundary** (`mock_mcp.py`) — plus [`AGENTNET_MCP_BOUNDARY.md`](AGENTNET_MCP_BOUNDARY.md)
  and [`PEAK_RESOLVER_ACCESS_POLICY.md`](PEAK_RESOLVER_ACCESS_POLICY.md). The known tool
  surface is exactly `agentnet.resolve` / `agentnet.resolve_history` /
  `agentnet.validate_capsule`; publication tools are rejected. **Contracts/scaffold only —
  no live MCP/resolver/AgentNet/network call, no credentials, no stored data; AgentNet
  integration is not complete and capsule publication is deferred.** Checked by
  [`../tests/validate_phase12_agentnet_mcp_boundary.py`](../tests/validate_phase12_agentnet_mcp_boundary.py)
  (`make validate-phase12`).

**Agent execution harness (Phase 13 — scaffold only):**

- [x] Scaffold for how future Peak internal agents/workers are **invoked, governed, and
  recorded**, with **no live execution**. Added [`../peak/agents/`](../peak/agents/) —
  task/result/context/run-draft contracts (`contracts.py`), a static registry of the 10
  known agents/workers (`registry.py`), deterministic pre-execution governance
  (`governance.py`), a **no-op mock executor** (`executor.py`) that routes any resolver
  context through the Phase 12 mock boundary, and a **mock LLM** (`mock_llm.py`) — plus
  [`AGENT_EXECUTION_HARNESS.md`](AGENT_EXECUTION_HARNESS.md) and
  [`AGENT_RUN_RECORDS.md`](AGENT_RUN_RECORDS.md). Output defaults to `draft`/`needs_review`;
  agents cannot self-approve, create client-facing output, publish capsules, or verify
  financial impact. **No live LLM/AgentNet/MCP/resolver/database/network call, no stored
  data, no client-facing output; AgentNet integration is not complete.** Checked by
  [`../tests/validate_phase13_agent_harness.py`](../tests/validate_phase13_agent_harness.py)
  (`make validate-phase13`).

**First production-shaped worker — Evidence Normalization (Phase 14):**

- [x] The first real worker: [`../peak/workers/`](../peak/workers/) — worker contracts
  (`contracts.py`), deterministic normalization helpers (`evidence_normalization.py`), and
  governance guards (`governance.py`) — plus
  [`EVIDENCE_NORMALIZATION_WORKER.md`](EVIDENCE_NORMALIZATION_WORKER.md) and
  [`EVIDENCE_RECORD_LIFECYCLE.md`](EVIDENCE_RECORD_LIFECYCLE.md). It turns a raw evidence
  reference into a **production-shaped but review-gated** `NormalizedEvidenceRecord`
  (`output_status=draft`, `review_status=needs_review`, `authoritative=false`,
  `client_facing_approved=false`, `capsule_candidate_ready=false`). Normalization is fully
  deterministic — **no live LLM/AgentNet/MCP/resolver/database/network call, no file write,
  no client-facing output, no capsule publication, no stored data**. A record is not
  authoritative merely because a worker created it. Checked by
  [`../tests/validate_phase14_evidence_worker.py`](../tests/validate_phase14_evidence_worker.py)
  (`make validate-phase14`).

**QA / Review Gate (Phase 15 — scaffold only):**

- [x] The decision layer over worker/agent outputs: [`../peak/review/`](../peak/review/) —
  review contracts (`contracts.py`), deterministic governance guards (`governance.py`:
  `evaluate_review_request`, `validate_requested_decision`, `build_review_checklist`), and a
  no-side-effect review-gate evaluator (`review_gate.py`: `evaluate_review_gate`,
  `derive_next_state`, `build_action_plan`) — plus
  [`QA_REVIEW_GATE.md`](QA_REVIEW_GATE.md) and [`REVIEW_DECISION_MODEL.md`](REVIEW_DECISION_MODEL.md).
  It evaluates a review request into a **production-shaped but no-side-effect**
  `ReviewGateResult`: allowed decisions are `approve_internal` (**internal reliance only** —
  `review_status=approved_internal`, `authoritative=true` for internal use), `reject`,
  `return_for_revision` (→ `needs_review`), `supersede` (→ `superseded`), and
  `keep_needs_review`; prohibited decisions (`client_facing_approve`, `publish_capsule`,
  `verify_financial_impact`, `approve_authoritative_external`) are rejected. `client_facing_approved`
  and `capsule_candidate_ready` stay `false` in every case. **No live LLM/AgentNet/MCP/resolver/
  database/network call, no file write, no client-facing output, no capsule publication, no
  stored review records.** A future governed writer would persist the decision as a
  `ReviewRecord`. Checked by
  [`../tests/validate_phase15_review_gate.py`](../tests/validate_phase15_review_gate.py)
  (`make validate-phase15`).

**Review Persistence Boundary (Phase 16 — DB-aware, not DB-writing):**

- [x] The readiness boundary for persisting a permitted review outcome as a controlled-DB
  `ReviewRecord`: [`../peak/review/`](../peak/review/) adds persistence contracts
  (`persistence_contracts.py`: `StoredReviewSubjectSnapshot`, `ReviewPersistenceRequest`,
  `ReviewRecordDraft`, `ReviewWritePlan`, `ReviewPersistenceResult`), deterministic
  persistence-readiness governance (`persistence_governance.py`:
  `evaluate_review_persistence_request`, `validate_subject_scope_against_request`,
  `validate_gate_result_for_persistence`, `build_persistence_decision`), and mapping helpers
  (`review_record_mapper.py`: `build_review_record_draft`, `build_review_write_plan`,
  `prepare_review_persistence`) — plus
  [`REVIEW_PERSISTENCE_BOUNDARY.md`](REVIEW_PERSISTENCE_BOUNDARY.md) and
  [`DB_BACKED_REVIEW_SCOPE_POLICY.md`](DB_BACKED_REVIEW_SCOPE_POLICY.md). It maps a permitted
  Phase 15 `ReviewGateResult` into a production-shaped `ReviewRecordDraft` and a no-op
  `ReviewWritePlan` (target `review_records`). **DB-aware but not DB-writing:**
  `review_record_id` / `created_at` stay `None`, `requires_controlled_db_writer=true`, and
  every flag (`database_write_made`, `database_connection_made`, `stored_review_record_created`,
  `llm_call_made`, `agentnet_call_made`, `network_call_made`, `capsule_publication_made`,
  `client_facing_output_created`) is `false`. **Critical scope rule:** a DB-backed review
  compares `request.authorization_scope` against the subject's stored
  `stored_authorization_scope` (implemented now via an in-memory `StoredReviewSubjectSnapshot`);
  owner/client/engagement matching is necessary but not sufficient. **No live database
  read/write, no SQLAlchemy/`peak.db` import, no LLM/AgentNet/MCP/resolver/network call, no
  client-facing approval, no financial verification, no capsule publication, no stored review
  records.** Checked by
  [`../tests/validate_phase16_review_persistence.py`](../tests/validate_phase16_review_persistence.py)
  (`make validate-phase16`).

**Controlled DB Writer Boundary (Phase 17 — DB-aware, not DB-writing):**

- [x] The generic policy/validation boundary every future controlled write routes through:
  [`../peak/persistence/`](../peak/persistence/) (deliberately **not** `peak/db/`, kept
  stdlib-only) adds controlled-write contracts (`contracts.py`: `ControlledWriteSubject`,
  `ControlledWriteRequest`, `ControlledWriteDecision`, `ControlledWritePlan`,
  `ControlledWriteResult`, `ControlledWriteAuditDraft`), a **table/action allowlist**
  (`allowlist.py`: `ALLOWED_TABLES`, `ALLOWED_ACTIONS`, `PROHIBITED_TABLES`,
  prohibited-action patterns, `is_allowed_table` / `is_allowed_action` / `is_prohibited_table`
  / `is_prohibited_action`), deterministic write governance (`governance.py`:
  `evaluate_controlled_write_request`, `validate_write_subject_scope`,
  `validate_table_action_allowlist`, `build_controlled_write_decision`), and no-op write
  planning (`write_plan.py`: `build_controlled_write_plan`,
  `build_controlled_write_audit_draft`, `prepare_controlled_write`) — plus
  [`CONTROLLED_DB_WRITER_BOUNDARY.md`](CONTROLLED_DB_WRITER_BOUNDARY.md) and
  [`CONTROLLED_WRITE_ALLOWLIST.md`](CONTROLLED_WRITE_ALLOWLIST.md). A permitted request yields
  a no-op `ControlledWritePlan` (`requires_controlled_db_writer=true`) and an in-memory
  `ControlledWriteAuditDraft` (`audit_record_id` / `created_at` left `None`). **DB-aware but
  not DB-writing:** `database_write_made`, `database_connection_made`, `sql_execution_made`,
  `stored_record_created` all `false`; no SQLAlchemy / Alembic / `peak.db` import. Enforces
  the **table/action allowlist** (only `evidence_references`, `engagement_records`,
  `review_records`, `agent_run_records`, `source_ingestion_records`,
  `capsule_publication_candidates`; never `clients` / `engagements` /
  `financial_impact_estimates` / `resolver_capsule_records`), an `idempotency_key`, and
  `request.authorization_scope == subject.stored_authorization_scope` (identity matching
  necessary but not sufficient); rejects publish / client-facing-approve / verify-financial /
  delete / migrate / seed / raw_sql actions. **No live DB connection/read/write, no SQL, no
  stored records, no migrations/seeds/deletes, no credentials, no LLM/AgentNet/MCP/resolver/
  network call, no client-facing approval, no financial verification, no capsule
  publication.** Checked by
  [`../tests/validate_phase17_controlled_db_writer.py`](../tests/validate_phase17_controlled_db_writer.py)
  (`make validate-phase17`).

**Evidence Persistence Mapping (Phase 18 — DB-aware, not DB-writing):**

- [x] The first domain to route through the Phase 17 boundary — connecting Phase 14 evidence
  output to controlled write planning: [`../peak/evidence/`](../peak/evidence/) (kept out of
  `peak/db/`, stdlib-only apart from importing the Phase 17 `peak.persistence` contracts/
  planner) adds evidence persistence contracts (`persistence_contracts.py`:
  `EvidencePersistenceSubjectSnapshot`, `EvidencePersistenceRequest`,
  `EvidencePersistenceDraft`, `EvidencePersistenceDecision`,
  `EvidencePersistenceMappingResult`), deterministic mapping governance
  (`persistence_governance.py`: `evaluate_evidence_persistence_request`,
  `validate_evidence_subject_scope`, `validate_normalization_result_for_persistence`,
  `build_evidence_persistence_decision`), and mapping helpers (`evidence_record_mapper.py`:
  `build_evidence_persistence_draft`, `build_controlled_write_subject`,
  `build_controlled_write_request`, `prepare_evidence_persistence`) — plus
  [`EVIDENCE_PERSISTENCE_MAPPING.md`](EVIDENCE_PERSISTENCE_MAPPING.md) and
  [`EVIDENCE_WRITE_PLAN_POLICY.md`](EVIDENCE_WRITE_PLAN_POLICY.md). It maps a
  `NormalizedEvidenceRecord` → `EvidencePersistenceDraft` → Phase 17 `ControlledWriteSubject`
  → `ControlledWriteRequest` (target `evidence_references` / `create_draft`) →
  `ControlledWritePlan` → no DB write. The review gate is preserved (`draft`/`needs_review`,
  `authoritative=false`, `client_facing_approved=false`, `capsule_candidate_ready=false`) and
  `evidence_record_id` / `created_at` stay `None`. Governance requires an `idempotency_key`,
  `request.authorization_scope == subject_snapshot.stored_authorization_scope` (identity
  matching necessary but not sufficient, anchored on the stored parent subject since the
  evidence has no stored row yet), and a permitted, side-effect-free, still-review-gated
  normalization output. **No live DB connection/read/write, no SQL, no stored records, no
  SQLAlchemy/Alembic/`peak.db` import, no LLM/AgentNet/MCP/resolver/network call, no
  client-facing approval, no financial verification, no capsule publication; evidence workers
  still do not write directly to the DB.** Checked by
  [`../tests/validate_phase18_evidence_persistence.py`](../tests/validate_phase18_evidence_persistence.py)
  (`make validate-phase18`).

**Agent Run Persistence Mapping (Phase 19 — DB-aware, not DB-writing):**

- [x] The second domain to route through the Phase 17 boundary — connecting Phase 13 agent
  run output to controlled write planning: [`../peak/agents/`](../peak/agents/) adds agent
  run persistence contracts (`persistence_contracts.py`:
  `AgentRunPersistenceSubjectSnapshot`, `AgentRunPersistenceRequest`,
  `AgentRunPersistenceDraft`, `AgentRunPersistenceDecision`,
  `AgentRunPersistenceMappingResult`), deterministic mapping governance
  (`persistence_governance.py`: `evaluate_agent_run_persistence_request`,
  `validate_agent_run_subject_scope`, `validate_agent_task_result_for_persistence`,
  `build_agent_run_persistence_decision`), and mapping helpers (`agent_run_mapper.py`:
  `build_agent_run_persistence_draft`, `build_controlled_write_subject`,
  `build_controlled_write_request`, `prepare_agent_run_persistence`) — plus
  [`AGENT_RUN_PERSISTENCE_MAPPING.md`](AGENT_RUN_PERSISTENCE_MAPPING.md) and
  [`AGENT_RUN_WRITE_PLAN_POLICY.md`](AGENT_RUN_WRITE_PLAN_POLICY.md). It maps an
  `AgentTaskResult` + `AgentRunDraft` → `AgentRunPersistenceDraft` → Phase 17
  `ControlledWriteSubject` → `ControlledWriteRequest` (target `agent_run_records` /
  `create_agent_run_record`) → `ControlledWritePlan` → no DB write. The review gate is
  preserved (`draft`/`needs_review`, every "a call was made" flag `false`) and
  `agent_run_record_id` / `created_at` stay `None`. Governance requires an `idempotency_key`,
  `request.authorization_scope == subject_snapshot.stored_authorization_scope` (identity
  matching necessary but not sufficient, anchored on the stored engagement/client/subject
  since the run record has no stored row yet), and a permitted, side-effect-free,
  still-review-gated agent output. The Phase 13 `AgentTaskResult` has no `network_call_made` /
  `capsule_publication_made` field, so those are not invented on the input and are set `false`
  on the draft and result. `peak/agents/__init__.py` re-exports the Phase 19 surface. **No
  live DB connection/read/write, no SQL, no stored records, no SQLAlchemy/Alembic/`peak.db`
  import, no LLM/AgentNet/MCP/resolver/network call, no client-facing output, no financial
  verification, no capsule publication; agent execution still does not write directly to the
  DB.** Checked by
  [`../tests/validate_phase19_agent_run_persistence.py`](../tests/validate_phase19_agent_run_persistence.py)
  (`make validate-phase19`).

**Agent Run Controlled Writer (Phase 20 — first real DB-backed persistence path):**

- [x] The first phase that actually **writes to the controlled database**: a narrow
  controlled writer for `agent_run_records`, [`../peak/db/agent_run_writer.py`](../peak/db/agent_run_writer.py)
  (+ typed receipt/outcomes in [`../peak/db/writer_contracts.py`](../peak/db/writer_contracts.py)),
  plus the additive migration
  [`../alembic/versions/002_agent_run_idempotency.py`](../alembic/versions/002_agent_run_idempotency.py)
  and docs [`AGENT_RUN_CONTROLLED_WRITER.md`](AGENT_RUN_CONTROLLED_WRITER.md) /
  [`AGENT_RUN_IDEMPOTENCY_POLICY.md`](AGENT_RUN_IDEMPOTENCY_POLICY.md). It consumes the
  Phase 17/19 `ControlledWriteRequest` (record_draft = a Phase 19 `AgentRunPersistenceDraft`)
  and creates **exactly one** review-gated row (`output_status=draft`,
  `review_status=needs_review`) with server-controlled id/timestamps. **Write-time DB-backed
  authorization:** the writer loads the authoritative stored subject (the `Engagement` row)
  from the DB and requires `request.authorization_scope == engagement.authorization_scope` —
  it does **not** trust the Phase 19 snapshot; identity matching is necessary but not
  sufficient; missing stored/request scope is denied. **DB-enforced idempotency** via a
  unique index over `(owner_id, client_id, engagement_id, idempotency_key)` plus a
  `payload_fingerprint`, distinguishing `created` / `idempotent_replay` / `denied` /
  `failed_before_write` / `write_outcome_uncertain`. The writer allows only
  `agent_run_records` / `create_agent_run_record`; rejects duck-typed inputs, caller-supplied
  ids/timestamps, and prohibited draft posture; and performs **no LLM/AgentNet/MCP/resolver/
  connector/network/client-facing/financial/capsule side effect** and never updates or
  deletes. The Phase 19 agent-domain mapper stays **DB-free** (regression-guarded). Checked by
  [`../tests/validate_phase20_agent_run_writer.py`](../tests/validate_phase20_agent_run_writer.py)
  (`make validate-phase20 PYTHON=.venv/bin/python` for the DB-backed suite; structural checks
  run on plain `python3`).

**Evidence Controlled Writer (Phase 21 — second DB-backed writer):**

- [x] The second narrow live DB writer, applying the Phase 20 pattern to
  `evidence_references`: [`../peak/db/evidence_writer.py`](../peak/db/evidence_writer.py)
  (+ `EvidenceWriteReceipt`/`EvidenceWriteOutcome` added to
  [`../peak/db/writer_contracts.py`](../peak/db/writer_contracts.py)), the additive migration
  [`../alembic/versions/003_evidence_idempotency.py`](../alembic/versions/003_evidence_idempotency.py)
  (down_revision `002_agent_run_idem`; single linear head `003_evidence_idem`), and docs
  [`EVIDENCE_CONTROLLED_WRITER.md`](EVIDENCE_CONTROLLED_WRITER.md) /
  [`EVIDENCE_IDEMPOTENCY_POLICY.md`](EVIDENCE_IDEMPOTENCY_POLICY.md). It consumes the
  Phase 17/18 `ControlledWriteRequest` (record_draft = a Phase 18 `EvidencePersistenceDraft`)
  and creates **exactly one** review-gated row (`output_status=draft`,
  `review_status=needs_review`, `lifecycle_status=active`, non-authoritative,
  non-client-facing, non-capsule) with server-controlled id/timestamps. **Write-time DB-backed
  authorization:** loads the authoritative stored `Engagement` row and requires
  `request.authorization_scope == engagement.authorization_scope` (does **not** trust the
  Phase 18 snapshot; identity matching necessary but not sufficient; missing stored/request
  scope denied). **DB-enforced idempotency** via a unique index over
  `(owner_id, client_id, engagement_id, idempotency_key)` + a `payload_fingerprint`,
  distinguishing `created` / `idempotent_replay` / `denied` / `failed_before_write` /
  `write_outcome_uncertain`. The writer allows only `evidence_references` / `create_draft`;
  rejects duck-typed inputs, caller-supplied ids/timestamps, and prohibited posture; and
  performs **no LLM/AgentNet/MCP/resolver/connector/network/client-facing/financial/capsule
  side effect** and never updates or deletes. The Phase 18 evidence-domain mapper stays
  **DB-free** (regression-guarded). Checked by
  [`../tests/validate_phase21_evidence_writer.py`](../tests/validate_phase21_evidence_writer.py)
  (`make validate-phase21 PYTHON=.venv/bin/python` for the DB-backed suite; structural checks
  run on plain `python3`).

**Review Record Controlled Writer (Phase 22 — third DB-backed writer):**

- [x] The third narrow live DB writer, applying the Phase 20/21 pattern to `review_records`:
  [`../peak/db/review_writer.py`](../peak/db/review_writer.py) (+ `ReviewWriteReceipt`/
  `ReviewWriteOutcome` added to [`../peak/db/writer_contracts.py`](../peak/db/writer_contracts.py)),
  the additive migration
  [`../alembic/versions/004_review_idempotency.py`](../alembic/versions/004_review_idempotency.py)
  (down_revision `003_evidence_idem`; single linear head `004_review_idem`), and docs
  [`REVIEW_CONTROLLED_WRITER.md`](REVIEW_CONTROLLED_WRITER.md) /
  [`REVIEW_IDEMPOTENCY_POLICY.md`](REVIEW_IDEMPOTENCY_POLICY.md). It consumes a Phase 17
  `ControlledWriteRequest` whose `record_draft` is a Phase 16 `ReviewRecordDraft` and creates
  **exactly one** `review_records` row with server-controlled id/timestamps. **Write-time
  DB-backed authorization:** loads the authoritative stored `Engagement` row and requires
  `request.authorization_scope == engagement.authorization_scope` (does **not** trust the
  Phase 16 snapshot; identity matching necessary but not sufficient; missing stored/request
  scope denied). Note the review record has two subjects — the engagement authorization anchor
  (`ControlledWriteRequest.subject`) and the reviewed target (`draft.subject_record_id`,
  persisted as `target_id`). **Decision posture:** `approve_internal` means internal reliance
  only (may set `authoritative=true` only with `next_review_status=approved_internal`, never
  client-facing); other decisions must be non-authoritative; `client_facing_approve` /
  `verify_financial_impact` / `publish_capsule` are rejected. **DB-enforced idempotency** via a
  unique index over `(owner_id, client_id, engagement_id, idempotency_key)` + a
  `payload_fingerprint`, distinguishing `created` / `idempotent_replay` / `denied` /
  `failed_before_write` / `write_outcome_uncertain`. The writer allows only `review_records` /
  `create_review_record`; rejects duck-typed inputs, caller-supplied ids/timestamps, and
  prohibited posture; and performs **no LLM/AgentNet/MCP/resolver/connector/network/
  client-facing/financial/capsule side effect** and never updates or deletes. The Phase 16
  review-domain mapper stays **DB-free** (regression-guarded). Checked by
  [`../tests/validate_phase22_review_writer.py`](../tests/validate_phase22_review_writer.py)
  (`make validate-phase22 PYTHON=.venv/bin/python` for the DB-backed suite; structural checks
  run on plain `python3`).

**Engagement Packet Ingestion Boundary (Phase 23 — an ingestion boundary, not a writer):**

- [x] The controlled front door for external `EngagementPacket` material, sitting *upstream*
  of the Phase 20–22 writers: [`../peak/ingestion/`](../peak/ingestion/) adds ingestion
  contracts (`contracts.py`: `EngagementPacketReference`, `PacketIngestionRequest`,
  `PacketValidationResult`, `SourceIngestionDraft`, `PacketDerivedEvidencePlan`,
  `PacketDerivedAgentTaskPlan`, `PacketIngestionPlan`, `PacketIngestionResult`), deterministic
  ingestion governance (`governance.py`: `evaluate_packet_ingestion_request`,
  `validate_packet_reference_scope`, `validate_packet_payload_shape`,
  `build_packet_validation_result` — including a nested credential/secret-key guard), and
  packet-to-request mapping (`packet_mapper.py`: `validate_packet`,
  `build_source_ingestion_draft`, `derive_evidence_normalization_requests`,
  `derive_agent_task_requests`, `build_packet_ingestion_plan`, `prepare_packet_ingestion`) —
  plus [`ENGAGEMENT_PACKET_INGESTION_BOUNDARY.md`](ENGAGEMENT_PACKET_INGESTION_BOUNDARY.md) and
  [`PACKET_TO_CONTROLLED_WORKFLOW_POLICY.md`](PACKET_TO_CONTROLLED_WORKFLOW_POLICY.md). It maps
  a validated packet into a review-gated `SourceIngestionDraft`, Phase 14
  `EvidenceNormalizationRequest` objects (from present sections), Phase 13 `AgentTaskRequest`
  objects (known registry agents only, never executed, `llm_execution_allowed=false`), and a
  no-op Phase 17 `ControlledWriteRequest` for `source_ingestion_records` /
  `create_source_ingestion_record` (plan only). Requires an `idempotency_key` and
  `request.authorization_scope == packet_reference.authorization_scope` (identity matching
  necessary but not sufficient); rejects credential/secret payload keys (never echoing secret
  values). **It is a boundary, not a direct importer:** no direct DB write, no DB connection,
  no SQL, no stored packet, no call to any Phase 20/21/22 writer, no LLM/AgentNet/MCP/resolver/
  network call, no client-facing approval, no financial verification, no capsule publication.
  Source ingestion records await a future narrow writer before persistence. `peak/ingestion/`
  imports no SQLAlchemy/Alembic/`peak.db` (bridges only the DB-free Phase 13/14/17 contracts).
  Checked by
  [`../tests/validate_phase23_packet_ingestion.py`](../tests/validate_phase23_packet_ingestion.py)
  (`make validate-phase23`).

**Source Ingestion Record Controlled Writer (Phase 24 — fourth DB-backed writer):**

- [x] The fourth narrow live DB writer, applying the Phase 20–22 pattern to
  `source_ingestion_records` and completing the Phase 23 ingestion path:
  [`../peak/db/source_ingestion_writer.py`](../peak/db/source_ingestion_writer.py) (+
  `SourceIngestionWriteReceipt`/`SourceIngestionWriteOutcome` added to
  [`../peak/db/writer_contracts.py`](../peak/db/writer_contracts.py)), the additive migration
  [`../alembic/versions/005_source_ingestion_idempotency.py`](../alembic/versions/005_source_ingestion_idempotency.py)
  (down_revision `004_review_idem`; single linear head `005_source_ingestion_idem`), and docs
  [`SOURCE_INGESTION_CONTROLLED_WRITER.md`](SOURCE_INGESTION_CONTROLLED_WRITER.md) /
  [`SOURCE_INGESTION_IDEMPOTENCY_POLICY.md`](SOURCE_INGESTION_IDEMPOTENCY_POLICY.md). It consumes
  a Phase 17 `ControlledWriteRequest` whose `record_draft` is a Phase 23 `SourceIngestionDraft`
  and creates **exactly one** `source_ingestion_records` row with server-controlled
  id/timestamps. **Write-time DB-backed authorization:** loads the authoritative stored
  `Engagement` row and requires `request.authorization_scope == engagement.authorization_scope`
  (does **not** trust the Phase 23 packet reference/draft; identity matching necessary but not
  sufficient; missing stored/request scope denied). **Packet metadata only** is persisted
  (reference id → `source_reference_id`; schema/source/location/hash → `details_json`) — the
  full packet payload, raw content, and secrets are never stored, and a draft carrying
  `packet_payload` / `raw_packet_content` / a secret-like attribute is rejected without echoing
  values. **DB-enforced idempotency** via a unique index over
  `(owner_id, client_id, engagement_id, idempotency_key)` + a metadata-only `payload_fingerprint`,
  distinguishing `created` / `idempotent_replay` / `denied` / `failed_before_write` /
  `write_outcome_uncertain`. The writer allows only `source_ingestion_records` /
  `create_source_ingestion_record`; rejects duck-typed inputs, caller-supplied ids/timestamps,
  and prohibited posture; and performs **no LLM/AgentNet/MCP/resolver/connector/network/
  client-facing/financial/capsule side effect** and never updates or deletes. The Phase 23
  ingestion package stays **DB-free** (regression-guarded). Checked by
  [`../tests/validate_phase24_source_ingestion_writer.py`](../tests/validate_phase24_source_ingestion_writer.py)
  (`make validate-phase24 PYTHON=.venv/bin/python` for the DB-backed suite; structural checks
  run on plain `python3`).

**Controlled Engagement Packet Processing Orchestrator (Phase 25 — controlled sequencing layer):**

- [x] A **controlled sequencing layer** over the existing narrow boundaries — **not** a generic
  importer, workflow engine, CRUD layer, or write dispatcher, and adding **no** new table, no
  migration (Alembic head stays `005_source_ingestion_idem`), no generic writer, and no raw SQL:
  [`../peak/orchestration/`](../peak/orchestration/) (`contracts.py`, `governance.py`,
  `packet_processor.py`) and docs
  [`CONTROLLED_PACKET_PROCESSING_ORCHESTRATOR.md`](CONTROLLED_PACKET_PROCESSING_ORCHESTRATOR.md) /
  [`PACKET_PROCESSING_ORCHESTRATION_POLICY.md`](PACKET_PROCESSING_ORCHESTRATION_POLICY.md).
  `process_engagement_packet` accepts a Phase 23 `PacketIngestionRequest`, routes it through the
  Phase 23 ingestion boundary, exposes the derived plan (source ingestion draft, plan-only source
  `ControlledWriteRequest`, Phase 14 `EvidenceNormalizationRequest` objects, Phase 13
  `AgentTaskRequest` objects), and returns a typed `PacketProcessingReceipt`. **Plan-only is the
  default and is no-side-effect** (every side-effect flag false; no DB writer, no agent/LLM, no
  AgentNet/MCP/resolver, no network). **Controlled persistence** runs only when `plan_only=false`,
  the specific stage is included, **and** a `session_factory` is supplied — and then only through
  the existing narrow writers (Phase 24 source-ingestion, Phase 21 evidence via Phase 18 mapping);
  DB writers are **lazy-imported** so plan-only runs without SQLAlchemy. **No stage may silently
  escalate** — a persistence stage absent inclusion / under `plan_only=true` / without a
  `session_factory` is *skipped* with a specific reason (`skipped_not_requested` /
  `skipped_plan_only` / `skipped_missing_session_factory`), never a silent write; a missing
  `session_factory` skips the stage, it does not fail the orchestration. **Orchestrator preflight
  checks are helpful but not authoritative:** stored `Engagement` authorization remains
  authoritative for every DB write and is enforced inside the narrow writers at write-time
  (identity matching necessary but not sufficient — a stored-scope mismatch is denied by the
  writer even when identities match, surfacing as an orchestration `partial`). It **never stores
  or echoes raw packet payload content** in receipts/logs/exceptions — only counts, ids, stage
  names, safe metadata, warnings, reason codes. Deterministic per-stage outcomes: `completed`,
  `skipped_not_requested`, `skipped_plan_only`, `skipped_missing_session_factory`,
  `skipped_no_safe_contract_path`, `denied`, `failed_before_write`, `write_outcome_uncertain` — a
  persistence stage reports `completed` only when a narrow writer actually created or replayed a
  row. **Agent-run persistence (Phase 19/20) is intentionally deferred** as
  `skipped_no_safe_contract_path` (it would require running the Phase 13 mock executor, which
  consults the disabled `MockLLM` interface); partial safe orchestration is preferable to unsafe
  breadth. Checked by
  [`../tests/validate_phase25_packet_processing_orchestrator.py`](../tests/validate_phase25_packet_processing_orchestrator.py)
  (`make validate-phase25 PYTHON=.venv/bin/python` for the DB-backed layer; structural + plan-only
  checks run on plain `python3`).

**Controlled Agent Task Queue / Execution Readiness Boundary (Phase 26 — DB-free readiness planning):**

- [x] A **readiness/queue-planning boundary** over derived Phase 13 `AgentTaskRequest` objects —
  **not** an executor, task runner, job queue, workflow engine, or DB writer — analogous to
  Phase 23 (which prepared source ingestion plans without DB writes):
  [`../peak/task_queue/`](../peak/task_queue/) (`contracts.py`, `governance.py`,
  `task_queue_mapper.py`) and docs
  [`AGENT_TASK_QUEUE_READINESS_BOUNDARY.md`](AGENT_TASK_QUEUE_READINESS_BOUNDARY.md) /
  [`AGENT_TASK_QUEUE_GOVERNANCE_POLICY.md`](AGENT_TASK_QUEUE_GOVERNANCE_POLICY.md).
  `prepare_agent_task_queue_plan(request)` maps derived Phase 13 tasks into **review-gated,
  not-executed** `AgentTaskQueueDraft` objects (`agent_task_queue_record_id=None`,
  `output_status=draft`, `review_status=needs_review`, `execution_status=not_executed`,
  `execution_allowed=false`, `requires_human_review=true`, ids/references only — never raw
  payload/text), deterministic `AgentExecutionReadinessAssessment` objects, and plan-only Phase 17
  `ControlledWriteRequest` objects targeting `agent_task_queue_records` /
  `create_agent_task_queue_record`. It **adds no table and no migration** (Alembic head stays
  `005_source_ingestion_idem`), executes **no agent (live or mock)**, and makes **no LLM / MockLLM
  / AgentNet / MCP / resolver / network call**, opens no DB connection, writes no row, and creates
  no client-facing output / financial verification / capsule publication — every side-effect flag
  stays `false`. Readiness states: `queued_for_review`, `blocked_by_policy`,
  `blocked_missing_evidence`, `blocked_unknown_agent`, `blocked_invalid_scope`,
  `blocked_lifecycle`, `ready_for_future_controlled_execution` — where **"ready" never means
  "execute now"** (structurally ready for a later controlled execution phase after review).
  Governance requires request identity/scope/idempotency + ≥1 task, matches each task's identity
  **and** scope (identity necessary but not sufficient), rejects unknown agents and live/LLM/
  resolver/client-facing requests, and rejects any raw-content / secret / execution-intent field
  (reporting key names only, never values). **Phase 25 integration is by documented handoff**
  (Phase 25 code unchanged): Phase 26 consumes the same Phase 13 objects Phase 25 surfaces on
  `PacketProcessingReceipt.agent_task_requests`. **A future Phase 27** may add the narrow
  `agent_task_queue_records` DB writer (re-loading stored `Engagement` scope at write time,
  DB-level idempotency), mirroring Phases 20–22/24. Checked by
  [`../tests/validate_phase26_agent_task_queue_readiness.py`](../tests/validate_phase26_agent_task_queue_readiness.py)
  (`make validate-phase26`; stdlib-only, DB-free).

**Agent Task Queue Controlled Writer (Phase 27 — fifth DB-backed writer):**

- [x] The fifth narrow live DB writer, applying the Phase 20–24 pattern to
  `agent_task_queue_records` — the first live persistence for the Phase 26 readiness/queue
  boundary: [`../peak/db/agent_task_queue_writer.py`](../peak/db/agent_task_queue_writer.py) (+
  `AgentTaskQueueWriteReceipt` / `AgentTaskQueueWriteOutcome` added to
  [`../peak/db/writer_contracts.py`](../peak/db/writer_contracts.py) and `AgentTaskQueueRecord`
  added to [`../peak/db/models.py`](../peak/db/models.py)), the additive migration
  [`../alembic/versions/006_agent_task_queue_records.py`](../alembic/versions/006_agent_task_queue_records.py)
  (down_revision `005_source_ingestion_idem`; single linear head `006_agent_task_queue_records`;
  creates one table only, no data), and docs
  [`AGENT_TASK_QUEUE_CONTROLLED_WRITER.md`](AGENT_TASK_QUEUE_CONTROLLED_WRITER.md) /
  [`AGENT_TASK_QUEUE_IDEMPOTENCY_POLICY.md`](AGENT_TASK_QUEUE_IDEMPOTENCY_POLICY.md). It consumes a
  Phase 17 `ControlledWriteRequest` whose `record_draft` is a Phase 26 `AgentTaskQueueDraft` and
  creates **exactly one** review-gated, **not-executed** `agent_task_queue_records` row with
  server-controlled id/timestamps. **Write-time DB-backed authorization:** loads the authoritative
  stored `Engagement` row and requires `request.authorization_scope ==
  engagement.authorization_scope` (identity necessary but not sufficient; missing stored/request
  scope denied). **No execution:** executes no agent (live or mock), makes no LLM/MockLLM/AgentNet/
  MCP/resolver/connector/network call, and **never creates an `agent_run_records` row**. Stores
  **safe references only** (agent_name, task_type/requested_action, task_input_ref,
  safe_input_summary, source_ingestion_record_id, evidence_reference_ids, run/orchestration refs,
  readiness_state, statuses, posture booleans) — never raw packet/evidence/interview content,
  source bytes, generated output, or secrets; a draft carrying such an attribute is rejected
  without echoing values. Agent identity is gated against the Phase 13 registry (unknown agents
  rejected). **DB-enforced idempotency** via a unique index over
  `(owner_id, client_id, engagement_id, idempotency_key)` + `payload_fingerprint`, distinguishing
  `created` / `idempotent_replay` / `denied` / `failed_before_write` / `write_outcome_uncertain`
  (with an `IntegrityError` re-query race branch). Allows only `agent_task_queue_records` /
  `create_agent_task_queue_record`; the Phase 17 allowlist gained exactly that one table/action.
  Never updates or deletes; no client-facing approval, financial verification, or capsule
  publication. The Phase 26 `peak/task_queue` package stays **DB-free** (regression-guarded).
  `make db-check` now reports **exactly 12 tables**. Checked by
  [`../tests/validate_phase27_agent_task_queue_writer.py`](../tests/validate_phase27_agent_task_queue_writer.py)
  (`make validate-phase27 PYTHON=.venv/bin/python` for the DB-backed suite; structural checks run
  on plain `python3`).

**Packet → Task Queue Orchestration Integration (Phase 28 — orchestration integration, not a new writer):**

- [x] Wired the Phase 26 task queue / execution readiness boundary and the Phase 27 narrow writer
  into the Phase 25 packet processor — **no new table, no migration** (Alembic head stays
  `006_agent_task_queue_records`; still 12 tables), no new writer:
  [`../peak/orchestration/packet_processor.py`](../peak/orchestration/packet_processor.py),
  [`../peak/orchestration/contracts.py`](../peak/orchestration/contracts.py) and doc
  [`PACKET_TO_TASK_QUEUE_ORCHESTRATION_INTEGRATION.md`](PACKET_TO_TASK_QUEUE_ORCHESTRATION_INTEGRATION.md).
  Two new stages consume the Phase 13 `AgentTaskRequest` objects the orchestrator already derives:
  `agent_task_queue_readiness` (DB-free, execution-free — runs Phase 26
  `prepare_agent_task_queue_plan`, exposing review-gated / not-executed queue drafts, readiness
  assessments, and plan-only Phase 17 write requests + counts) and `agent_task_queue_persistence`
  (calls **only** the Phase 27 `persist_agent_task_queue_record`). New options
  `include_agent_task_queue_readiness` (default **true**) and
  `include_agent_task_queue_persistence` (default **false**); persistence runs only when
  `plan_only=false`, the option is on, a `session_factory` is supplied, and Phase 26 produced valid
  write requests — otherwise `skipped_plan_only` / `skipped_missing_session_factory` /
  `skipped_not_requested` / `skipped_no_safe_contract_path` (**no silent escalation**). In plan-only
  mode every side-effect flag stays `false`. It **executes no agent**, calls no
  executor/MockLLM/LLM/AgentNet/MCP/resolver/connector/network, and **creates no `agent_run_records`
  row** — agent task queue persistence is not execution. **Stored `Engagement` authorization stays
  authoritative** inside the Phase 27 writer (orchestrator preflight is advisory; identity necessary
  but not sufficient); a stored-scope mismatch is denied by the writer and surfaced as a `partial`
  outcome. New receipt fields: `task_queue_readiness_result`, `task_queue_drafts`,
  `task_queue_readiness_assessments`, `task_queue_controlled_write_requests`,
  `task_queue_write_receipts`, and the `task_queue_*_count` / `task_queue_persistence_*` fields;
  new stage outcome `partial`. Source-ingestion (Phase 24) and evidence (Phase 18/21) persistence
  are regression-checked. Checked by
  [`../tests/validate_phase28_packet_task_queue_integration.py`](../tests/validate_phase28_packet_task_queue_integration.py)
  (`make validate-phase28 PYTHON=.venv/bin/python` for the DB-backed layer; structural + plan-only
  checks run on plain `python3`).

**Packet-Derived Review Orchestration Boundary (Phase 29 — DB-free review planning):**

- [x] A **DB-free review-planning boundary** that organizes packet-derived outputs (safe
  references, receipts, metadata) into **review-ready** plans for human reviewers — **not** a
  review-approval phase, review engine, workflow engine, or DB writer; analogous to Phase 26:
  [`../peak/review_orchestration/`](../peak/review_orchestration/) (`contracts.py`,
  `governance.py`, `review_planner.py`) and docs
  [`PACKET_DERIVED_REVIEW_ORCHESTRATION_BOUNDARY.md`](PACKET_DERIVED_REVIEW_ORCHESTRATION_BOUNDARY.md) /
  [`REVIEW_ORCHESTRATION_GOVERNANCE_POLICY.md`](REVIEW_ORCHESTRATION_GOVERNANCE_POLICY.md).
  `prepare_packet_review_plan(request)` maps safe references (source-ingestion / evidence /
  agent-task-queue ids, packet-processing + receipt refs) into review-gated `ReviewBundleDraft`
  objects (`review_bundle_id=None`, `output_status=draft`, `review_status=needs_review`,
  `lifecycle_status=draft`, `approval_allowed=false`, `execution_allowed=false`,
  `publication_allowed=false`, `financial_verified=false`, `requires_human_review=true`),
  deterministic `ReviewPlanItem` objects (source_ingestion / evidence_reference / agent_task_queue
  / packet_processing / cross_stage_consistency / missing_evidence / readiness_exception), and
  `ReviewReadinessAssessment` objects. Readiness states: `ready_for_human_review` plus the
  `blocked_*` family (no_subjects / invalid_scope / lifecycle / raw_content / secret_like_content /
  execution_intent / approval_intent / publication_intent / financial_verification_intent). **It is
  DB-free** (adds no table, no migration — Alembic head stays `006_agent_task_queue_records`; still
  12 tables — and produces **no** `ControlledWriteRequest` objects; future persistence deferred),
  **approves nothing** (**"ready for human review" never means approved**), executes nothing, calls
  no LLM/MockLLM/AgentNet/MCP/resolver/connector/network, does not call or change the Phase 22
  review writer, and creates **no `review_records` or `agent_run_records` row**. Every side-effect
  flag stays `false`. Governance requires identity/scope/idempotency + (in strict_mode) ≥1 safe
  subject, matches structured subject-ref identity **and** scope (necessary but not sufficient), and
  rejects raw-content / secret-like / approval / execution / client-facing / publication /
  financial-verification content by key name (values never echoed). **Phase 25/28 integration is a
  documented handoff** (safe references only; Phase 29 does not run inside Phase 25/28 and imports
  no `peak.db` / Phase 27 writer / Phase 22 writer). Checked by
  [`../tests/validate_phase29_review_orchestration_boundary.py`](../tests/validate_phase29_review_orchestration_boundary.py)
  (`make validate-phase29`; stdlib-only, DB-free).

**Review Bundle Controlled Writer (Phase 30 — sixth DB-backed writer):**

- [x] The sixth narrow live DB writer, the persistence counterpart to Phase 29, applying the
  Phase 20–24/27 pattern to `review_bundle_records`:
  [`../peak/db/review_bundle_writer.py`](../peak/db/review_bundle_writer.py) (+
  `ReviewBundleWriteReceipt` / `ReviewBundleWriteOutcome` in
  [`../peak/db/writer_contracts.py`](../peak/db/writer_contracts.py) and `ReviewBundleRecord` in
  [`../peak/db/models.py`](../peak/db/models.py)), the additive migration
  [`../alembic/versions/007_review_bundle_records.py`](../alembic/versions/007_review_bundle_records.py)
  (down_revision `006_agent_task_queue_records`; single linear head `007_review_bundle_records`;
  creates one table only, no data), and docs
  [`REVIEW_BUNDLE_CONTROLLED_WRITER.md`](REVIEW_BUNDLE_CONTROLLED_WRITER.md) /
  [`REVIEW_BUNDLE_IDEMPOTENCY_POLICY.md`](REVIEW_BUNDLE_IDEMPOTENCY_POLICY.md). It consumes a
  Phase 17 `ControlledWriteRequest` whose `record_draft` is a Phase 29 `ReviewBundleDraft` and
  creates **exactly one** review-gated, **not-approved** `review_bundle_records` row with
  server-controlled id/timestamps. **Write-time DB-backed authorization:** loads the authoritative
  stored `Engagement` row and requires `request.authorization_scope ==
  engagement.authorization_scope` (identity necessary but not sufficient; missing stored/request
  scope denied). **No approval:** approves nothing (no `approve_internal`), **calls no Phase 22
  review writer, creates no `review_records` row**, executes no agent, makes no
  LLM/MockLLM/AgentNet/MCP/resolver/connector/network call, creates no `agent_run_records` row, and
  performs no client-facing output / financial verification / capsule publication. Stores **safe
  references only** (packet-processing receipt ref, source/evidence/task-queue ids, subject id+type,
  reviewer_role, review_reason, review_scope, statuses, posture booleans) — never raw
  packet/evidence/interview content, source bytes, generated output, secrets, or a **final review
  decision**; a draft carrying such an attribute is rejected without echoing values. Required
  posture: `output_status=draft`, `review_status=needs_review`, `lifecycle_status=draft`, and all of
  `authoritative` / `client_facing_approved` / `capsule_candidate_ready` / `financial_verified` /
  `execution_allowed` / `approval_allowed` / `publication_allowed` false with
  `requires_human_review=true`. **DB-enforced idempotency** via a unique index over
  `(owner_id, client_id, engagement_id, idempotency_key)` + `payload_fingerprint`, distinguishing
  `created` / `idempotent_replay` / `denied` / `failed_before_write` / `write_outcome_uncertain`
  (with an `IntegrityError` re-query race branch). Allows only `review_bundle_records` /
  `create_review_bundle_record`; the Phase 17 allowlist gained exactly that one table/action. Never
  updates or deletes. The Phase 29 `peak/review_orchestration` package stays **DB-free** (the
  optional Phase 29 CWR helper was **skipped** — the Phase 30 tests construct the
  `ControlledWriteRequest` directly, leaving Phase 29 untouched). `make db-check` now reports
  **exactly 13 tables**. Checked by
  [`../tests/validate_phase30_review_bundle_writer.py`](../tests/validate_phase30_review_bundle_writer.py)
  (`make validate-phase30 PYTHON=.venv/bin/python` for the DB-backed suite; structural checks run on
  plain `python3`).

**Packet → Review Bundle Orchestration Integration (Phase 31 — orchestration integration, not a new writer):**

- [x] Wired the Phase 29 review orchestration boundary and the Phase 30 narrow writer into the
  Phase 25/28 packet processor — **no new table, no migration** (Alembic head stays
  `007_review_bundle_records`; still 13 tables), no new writer:
  [`../peak/orchestration/packet_processor.py`](../peak/orchestration/packet_processor.py),
  [`../peak/orchestration/contracts.py`](../peak/orchestration/contracts.py) and doc
  [`PACKET_TO_REVIEW_BUNDLE_ORCHESTRATION_INTEGRATION.md`](PACKET_TO_REVIEW_BUNDLE_ORCHESTRATION_INTEGRATION.md).
  After the existing Phase 23/24/14/18/21/13/26/27 path, the orchestrator gathers **safe references**
  (persisted source/evidence/task-queue ids when persistence ran, else safe queue-draft refs, plus a
  deterministic packet-processing receipt ref) and adds two stages: `review_orchestration` (DB-free,
  approval-free — runs Phase 29 `prepare_packet_review_plan`, exposing review-gated, **not-approved**
  review bundle drafts, review plan items, and readiness assessments + counts) and
  `review_bundle_persistence` (builds a Phase 17 request per draft and calls **only** the Phase 30
  `persist_review_bundle_record`). New options `include_review_orchestration` (default **true**) and
  `include_review_bundle_persistence` (default **false**); persistence runs only when
  `plan_only=false`, the option is on, a `session_factory` is supplied, and Phase 29 produced drafts —
  otherwise `skipped_plan_only` / `skipped_missing_session_factory` / `skipped_not_requested` /
  `skipped_no_safe_contract_path` (**no silent escalation**). In plan-only mode every side-effect flag
  stays `false`. It **approves nothing** (no `approve_internal`, **no Phase 22 review writer call, no
  `review_records` row**, `review_approval_made=false`, `ready_for_human_review` is not approval),
  **executes nothing** (no agent/LLM/MockLLM/AgentNet/MCP/resolver/network, **no `agent_run_records`
  row**), and creates no client-facing output / financial verification / capsule publication. **Stored
  `Engagement` authorization stays authoritative** inside the Phase 30 writer (orchestrator preflight
  is advisory; identity necessary but not sufficient); a stored-scope mismatch is denied by the writer
  and surfaced as `partial`. New receipt fields: `review_orchestration_result`, `review_bundle_drafts`,
  `review_plan_items`, `review_readiness_assessments`, `review_bundle_write_receipts`, and the
  `review_bundle_*` / `review_*_count` fields; plus the `review_approval_made` flag. Source-ingestion
  (Phase 24), evidence (Phase 18/21), and task-queue (Phase 27) persistence are regression-checked.
  Checked by
  [`../tests/validate_phase31_packet_review_bundle_integration.py`](../tests/validate_phase31_packet_review_bundle_integration.py)
  (`make validate-phase31 PYTHON=.venv/bin/python` for the DB-backed layer; structural + plan-only
  checks run on plain `python3`).

**Still to do:**

- Persistence model and data retention/privacy strategy (prerequisite for storing
  real client data) — implementing the controlled storage described above.
- Access control appropriate to client confidentiality.
- Observability: what each agent produced, from what evidence, reviewed by whom.
- Broaden coverage across all ten workflows.

**Exit criteria:** multiple consultants run real engagements on the system with
governed, auditable output.

---

## Explicitly out of scope (for now)

Deferred until the internal core is proven:

- **Client-facing frontend / portal.**
- **Database / persistence layer** (Phase 5 prerequisite before real client data).
- **Automated client deliverables** without consultant review.
- **Vendor-specific lock-in** — keep schemas, prompts, and interfaces portable.

## Dependencies & sequencing

```
Phase 0 (scaffold) → Phase 1 (schemas) → Phase 2 (first workflow)
                                              ↓
                              Phase 3 (QA + learning)
                                              ↓
                              Phase 4 (AgentNet grounding)
                                              ↓
                              Phase 5 (hardening & scale)
```

Each phase depends on the one before it. Do not start client-facing work until the
internal operating system is proven through at least Phase 3.
