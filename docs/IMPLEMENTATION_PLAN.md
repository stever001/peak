# Implementation Plan

A phased plan that goes from today's scaffolding to a working internal operating
system, without overbuilding. Each phase is shippable and de-risks the next.

**Guiding rule:** prove the workflow with the lightest possible machinery before
adding structure, storage, or automation.

**Reader-facing phase navigation is maintained in [`PHASE_INDEX.md`](PHASE_INDEX.md).**
Note that this plan uses two numbering schemes: the `##` headings below are a strategic
Phase 0–5 sequence, while delivery Phases 11–85 appear as bold sub-entries inside
*Phase 5 — Hardening & scale (internal)*. Use the index to locate a specific phase.

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

**Internal Reviewer Decision Boundary (Phase 32 — DB-free decision planning):**

- [x] A **DB-free decision-planning boundary** that represents a structured internal reviewer
  decision against a review bundle / review plan items — **not** a review-approval phase, review
  engine, or DB writer; analogous to Phase 29:
  [`../peak/reviewer_decisions/`](../peak/reviewer_decisions/) (`contracts.py`, `governance.py`,
  `decision_mapper.py`) and docs
  [`INTERNAL_REVIEWER_DECISION_BOUNDARY.md`](INTERNAL_REVIEWER_DECISION_BOUNDARY.md) /
  [`INTERNAL_REVIEWER_DECISION_GOVERNANCE_POLICY.md`](INTERNAL_REVIEWER_DECISION_GOVERNANCE_POLICY.md).
  `prepare_internal_reviewer_decision(request)` maps safe review-bundle / review-plan-item
  references and safe reviewer selections into a review-gated `InternalReviewerDecisionDraft`
  (`reviewer_decision_id=None`, `output_status=draft`, `review_status=needs_review`,
  `lifecycle_status=draft`, `approval_allowed=false`, `execution_allowed=false`,
  `publication_allowed=false`, `financial_verified=false`, `requires_human_review=true`), a
  deterministic `ReviewerDecisionRoutingPlan` (recommendation only), and a
  `ReviewerDecisionReadinessAssessment`. Allowed intents: `needs_more_evidence`,
  `return_for_revision`, `ready_for_internal_use`, `blocked_by_scope`, `blocked_by_quality`,
  `blocked_by_missing_source`, `rejected_for_policy`, `defer_review` — each mapped to a route
  recommendation; approval/publication/execution/financial/client-facing intents are denied
  (`blocked_disallowed_intent`). **`ready_for_internal_use` is not approval.** It is **DB-free**
  (adds no table, no migration — Alembic head stays `007_review_bundle_records`; still 13 tables —
  and produces **no** `ControlledWriteRequest` objects; future persistence deferred to Phase 33),
  **persists nothing**, **does not call the Phase 22 review writer**, creates **no `review_records`
  row**, approves nothing, executes nothing, and makes no LLM/MockLLM/AgentNet/MCP/resolver/network
  call. Every side-effect flag stays `false`. Governance requires identity/scope/idempotency + a
  review-bundle ref + short safe reviewer_role/decision_reason_code + an allowed intent, matches
  structured subject-ref identity **and** scope (necessary but not sufficient), and rejects
  raw-content / secret-like / DB-URL / raw-SQL fields by key name (values never echoed).
  **Phase 31 integration is a documented handoff** (safe references only; Phase 32 does not run
  inside packet processing and imports no `peak.db` / Phase 30 writer / Phase 22 writer). Checked by
  [`../tests/validate_phase32_internal_reviewer_decision_boundary.py`](../tests/validate_phase32_internal_reviewer_decision_boundary.py)
  (`make validate-phase32`; stdlib-only, DB-free).

**Internal Reviewer Decision Controlled Writer (Phase 33 — seventh DB-backed writer):**

- [x] The **persistence counterpart to Phase 32**: a narrow live DB writer that persists **exactly
  one** `internal_reviewer_decision_records` row from a Phase 32 `InternalReviewerDecisionDraft`
  routed through the Phase 17 `ControlledWriteRequest` boundary — allowing only
  `internal_reviewer_decision_records` / `create_internal_reviewer_decision_record`.
  [`../peak/db/internal_reviewer_decision_writer.py`](../peak/db/internal_reviewer_decision_writer.py),
  migration [`../alembic/versions/008_internal_reviewer_decision_records.py`](../alembic/versions/008_internal_reviewer_decision_records.py),
  and docs
  [`INTERNAL_REVIEWER_DECISION_CONTROLLED_WRITER.md`](INTERNAL_REVIEWER_DECISION_CONTROLLED_WRITER.md) /
  [`INTERNAL_REVIEWER_DECISION_IDEMPOTENCY_POLICY.md`](INTERNAL_REVIEWER_DECISION_IDEMPOTENCY_POLICY.md).
  `persist_internal_reviewer_decision_record(controlled_write_request, *, session_factory=None,
  decision_request=None)` returns a typed `InternalReviewerDecisionWriteReceipt`. **Non-approval,
  review-gated records only:** every stored row is `output_status=draft`,
  `review_status=needs_review`, `lifecycle_status=draft`, with all approval/execution/publication
  posture booleans false, `client_facing_output_created=false`, `review_approval_made=false`, and
  `requires_human_review=true`. **`ready_for_internal_use` is not approval.** Only the eight Phase
  32 intents may be persisted; a deterministic `route_to` is stored (recommendation only).
  **Write-time authorization loads the stored `Engagement`** and requires
  `request.authorization_scope == engagement.authorization_scope` (identity necessary, not
  sufficient); missing stored/request scope, stored identity mismatch, and prohibited stored
  lifecycle are denied. **Content safety:** only safe references/summaries/labels are persisted
  (lists live in `details_json`); an injected raw-content/secret/DB-URL/raw-SQL/approval-decision
  attribute is rejected without echoing the value, and the Phase 32 summary/followup value-safety
  markers are re-enforced at write time. **Idempotency** boundary
  `(owner_id, client_id, engagement_id, idempotency_key)` + `payload_fingerprint` (`created` /
  `idempotent_replay` / `idempotency_conflict` / `failed_before_write` / `write_outcome_uncertain`;
  `IntegrityError` race re-query). Additive migration `008_internal_reviewer_decision_records`
  (`down_revision = 007_review_bundle_records`) creates one table, no INSERT/seed; Alembic stays
  single-head; the controlled DB now has **14 tables**. It approves nothing, never calls
  `approve_internal` or the Phase 22 review writer, creates no `review_records`/`agent_run_records`
  row, executes no agent, and makes no LLM/MockLLM/AgentNet/MCP/resolver/network call. An optional
  Phase-32-side CWR helper was **skipped** to keep Phase 32 strictly DB-free; the equivalent bridge
  (`build_decision_controlled_write_request`) lives in the Phase 33 DB layer. Checked by
  [`../tests/validate_phase33_internal_reviewer_decision_writer.py`](../tests/validate_phase33_internal_reviewer_decision_writer.py)
  (`make validate-phase33`; DB-backed via `.venv`).

**Intake Note Controlled Writer + Managed MySQL Rubric (Phase 34 — eighth DB-backed writer +
production-persistence consolidation):**

- [x] **First-class intake notes.** A narrow live DB writer that persists **exactly one**
  `intake_note_records` row from an `IntakeNoteDraft` through the Phase 17 `ControlledWriteRequest`
  boundary — allowing only `intake_note_records` / `create_intake_note_record`.
  [`../peak/db/intake_note_writer.py`](../peak/db/intake_note_writer.py), migration
  [`../alembic/versions/009_intake_note_records.py`](../alembic/versions/009_intake_note_records.py),
  and docs [`INTAKE_NOTE_CONTROLLED_WRITER.md`](INTAKE_NOTE_CONTROLLED_WRITER.md) /
  [`INTAKE_NOTE_IDEMPOTENCY_POLICY.md`](INTAKE_NOTE_IDEMPOTENCY_POLICY.md).
  `persist_intake_note_record(controlled_write_request, *, session_factory=None)` returns a typed
  `IntakeNoteWriteReceipt`. It is the first table to store authorized operational `note_text`
  (a `TEXT` column) — acceptable **only in the managed DB**, never in Git/fixtures/logs/receipts, and
  **never echoed** in a receipt or denial reason (only field names + marker categories). `note_text`
  accepts bounded ordinary prose (≤ 16,000 chars) but rejects credential assignments, DB URLs/DSNs,
  raw SQL, private keys, stack traces, raw-content tokens, and raw-JSON dumps; short label/ref fields
  and `note_summary` reuse the public `classify_prohibited_value_marker`. **Non-final posture:**
  `review_status=needs_review`, `lifecycle_status=draft`, all approval/publication/execution
  booleans false, `requires_human_review=true`. Write-time authorization loads the stored
  `Engagement` (`request.authorization_scope == engagement.authorization_scope`; identity necessary
  but not sufficient). Idempotency boundary `(owner_id, client_id, engagement_id, idempotency_key)` +
  `payload_fingerprint` (the note body participates as a SHA-256 hash). Additive migration
  `009_intake_note_records` (`down_revision = 008_internal_reviewer_decision_records`) creates one
  table, no INSERT/seed; single Alembic head; the controlled DB now has **15 tables**. It approves,
  publishes, and executes nothing; calls no Phase 22 writer / `approve_internal`; creates no
  `review_records` / `agent_run_records` row; and makes no LLM/MockLLM/AgentNet/AgentNet-publication/
  MCP/resolver/connector/network call.
- [x] **Managed MySQL persistence rubric** (docs + safe opt-in scaffolding): managed remote MySQL is
  the operational data store; **Client Isolation Option A** (shared managed DB per environment +
  strict tenant columns + stored-`Engagement` authorization) is the default; environments are
  separated (dev/test/staging/prod); **SQLite is only a fast local structural-smoke path, not the
  production-readiness proof path**; managed MySQL test/staging validation is required for production
  readiness; the production DB is not the main smoke-test target; and there is no broad production
  delete/cleanup path. Credential-free, skip-safe Makefile targets (`db-check-managed-test`,
  `managed-mysql-smoke`, `managed-mysql-migration-check`) delegate to
  [`../tools/managed_mysql_check.py`](../tools/managed_mysql_check.py), read the DSN only from
  `PEAK_MANAGED_MYSQL_{TEST,STAGING}_DSN` (never printed, never committed), refuse `prod` (fail
  closed), and are **not** part of `make validate`. Docs
  [`MANAGED_MYSQL_PERSISTENCE_RUBRIC.md`](MANAGED_MYSQL_PERSISTENCE_RUBRIC.md),
  [`CLIENT_ISOLATION_MODEL.md`](CLIENT_ISOLATION_MODEL.md),
  [`PRODUCTION_PARITY_DB_VALIDATION.md`](PRODUCTION_PARITY_DB_VALIDATION.md).
- [x] **Peak-operated AgentNet publication policy** (policy only; **no publish code**): the client
  authorizes Peak in the consulting agreement to act as the authorized capsule/node publisher;
  clients operate no AgentNet publishing tools, hold no publishing credentials, and have no
  client-facing publisher UI / resolver publication tools / direct publication path; publication
  remains disabled until future controlled gates.
  [`PEAK_OPERATED_AGENTNET_PUBLICATION_POLICY.md`](PEAK_OPERATED_AGENTNET_PUBLICATION_POLICY.md).
  Checked by
  [`../tests/validate_phase34_intake_note_writer.py`](../tests/validate_phase34_intake_note_writer.py)
  and
  [`../tests/validate_phase34_managed_mysql_rubric.py`](../tests/validate_phase34_managed_mysql_rubric.py)
  (`make validate-phase34`; DB-backed via `.venv`; rubric check is credential-free with no live
  network).

**Governed Managed Record Workflow Integration (Phase 35 — workflow integration over the existing
writers; no new persistence primitive):**

- [x] **Governed six-stage workflow.** A DB-free sequencing layer
  ([`../peak/workflows/`](../peak/workflows/)) that drives six already durable record types through
  the narrow controlled writers that already exist — `intake_note_records` (P34) →
  `source_ingestion_records` (P24) → `evidence_references` (P21) → `agent_task_queue_records` (P27)
  → `review_bundle_records` (P30) → `internal_reviewer_decision_records` (P33). Public entry point
  `run_managed_record_workflow(request, *, session_factory=None)` returns a typed
  `ManagedRecordWorkflowResult`. Docs
  [`MANAGED_RECORD_WORKFLOW_INTEGRATION.md`](MANAGED_RECORD_WORKFLOW_INTEGRATION.md) and
  [`WORKFLOW_INTEGRATION_GOVERNANCE_POLICY.md`](WORKFLOW_INTEGRATION_GOVERNANCE_POLICY.md).
- [x] **No new persistence primitive.** No DB table, model, or Alembic migration; **no new Phase 17
  allowlist pair**; no generic CRUD, generic writer, arbitrary SQL executor, or broad repository.
  Alembic head remains `009_intake_note_records` and `make db-check` still expects **15 tables**.
- [x] **Explicit per-stage gates; plan-only default.** A stage persists only when
  `persistence_gates[stage]` is `True`, its payload is present and safe, and a `session_factory` is
  injected — **no ambient-DSN fallback**, so `make validate` needs no live credentials and no
  network. Payload safety and identity checks also run in plan-only mode. No stage silently escalates.
- [x] **Linear halting.** A denied / conflicted / failed stage sets `halted_after_stage` and marks
  every later stage `halted`. `strict_mode=True` halts on any stage warning; non-strict collects the
  warning with no approval, client-facing, publication, financial, or execution effect.
- [x] **Authorization unchanged.** Each narrow writer still loads the stored `Engagement` and
  compares the stored `authorization_scope`; identity matching is necessary but not sufficient.
  Cross-tenant / cross-engagement payloads are denied before any write.
- [x] **Stage-namespaced idempotency.** Every key is `wf35::<stage>::…`. An explicit per-stage key is
  respected as the stage-local component; otherwise the key derives from `workflow_id` plus a
  SHA-256 prefix over safe, **non-content** stage fields. Replay returns the writers'
  `idempotent_replay` with no duplicate row; an explicit key reused with a changed payload yields
  `idempotency_conflict` and halts the dependent stages.
- [x] **Leak safety.** Results carry only stage names, safe record refs, counts, reason codes, and
  marker categories. `note_text` may be passed to the intake writer but is **never echoed**;
  prohibited keys/values are denied before any writer runs, reporting field name and category only.
- [x] **Nothing escalates.** No Phase 22 review-writer call and no `review_records` /
  `agent_run_records` row; no client-facing output, financial verification, capsule publication,
  AgentNet publish, resolver/MCP call, LLM/MockLLM call, agent or mock-agent execution, production DB
  write path, or cleanup/delete path. The managed-MySQL rubric and the Peak-operated AgentNet
  publication policy are unchanged. Checked by
  [`../tests/validate_phase35_managed_record_workflow.py`](../tests/validate_phase35_managed_record_workflow.py)
  (`make validate-phase35`; structural + plan-only always, DB-backed via `.venv`).

**Internal Assessment Report Assembly Planning Boundary (Phase 36 — DB-free report planning; no
report draft, no client-facing deliverable):**

- [x] **Report assembly planning.** A DB-free planning layer ([`../peak/reports/`](../peak/reports/))
  that turns governed record references and reviewer decisions into an internal assessment report
  *plan*: sections, evidence traceability, finding/recommendation candidate slots, gaps, and
  readiness. Public entry point `prepare_internal_assessment_report_plan(request)` returns a typed
  `InternalAssessmentReportPlanningResult`. Docs
  [`INTERNAL_ASSESSMENT_REPORT_PLANNING_BOUNDARY.md`](INTERNAL_ASSESSMENT_REPORT_PLANNING_BOUNDARY.md)
  and
  [`INTERNAL_REPORT_ASSEMBLY_GOVERNANCE_POLICY.md`](INTERNAL_REPORT_ASSEMBLY_GOVERNANCE_POLICY.md).
- [x] **Planning only — no persistence, no prose.** No DB table, model, or Alembic migration; **no
  new Phase 17 allowlist pair**; no DB writer, report writer, report table, report-draft
  persistence, generic CRUD, arbitrary SQL, broad repository, API, or frontend. It reads **no**
  database — every reference is caller-supplied — and generates no narrative: section titles are
  fixed internal planning labels, never client-facing language. Alembic head remains
  `009_intake_note_records` and `make db-check` still expects **15 tables**.
- [x] **Fourteen internal sections** in a fixed canonical order, each with a deterministic readiness
  state (`ready_for_internal_drafting` / `partial_supporting_references` /
  `blocked_no_supporting_references` / `synthesis_only`), an evidence trace holding **record ids
  only**, and an `InternalReportGap` for every unsatisfied supporting category.
- [x] **Internal-only posture.** `audience="internal"`, `output_status="plan"`,
  `review_status="needs_review"`, `lifecycle_status="draft"`, with `client_facing_approved` /
  `financial_verified` / `capsule_candidate_ready` / `publication_allowed` / `execution_allowed` all
  false and `requires_human_review=true`. `audience=client|external` and any elevated posture flag
  are denied; there is no send / share / export / client-approval path.
- [x] **Identify, never perform.** `future_financial_verification_items` names items that would need
  a future financial gate — **no ROI is calculated and no savings verified**.
  `future_capsule_candidate_items` names possible future capsule candidates — **nothing is created
  or published**, and no AgentNet / resolver / MCP / network / LLM / agent call is made.
- [x] **Deterministic.** Canonical section order, sorted de-duplicated references, positional
  candidate ids, and a SHA-256 `plan_fingerprint` — **no random ids and no timestamps**. The same
  request always yields the same plan; reference reordering and duplication do not change it.
- [x] **Leak safety.** References and short safe labels only. Prohibited keys/values (raw note text,
  packet payload, raw evidence/interview text, source bytes, generated output, credentials, DSNs,
  raw SQL, stack traces, approval/publication/client-facing intent) are denied before a plan is
  assembled, and denials report only field names, reference positions, and marker categories —
  never the value. Cross-tenant / cross-engagement / scope-mismatched structured references are
  denied. The managed-MySQL rubric and Peak-operated AgentNet publication policy are unchanged.
  Checked by
  [`../tests/validate_phase36_internal_assessment_report_planning.py`](../tests/validate_phase36_internal_assessment_report_planning.py)
  (`make validate-phase36`; stdlib-only, DB-free, network-free).

**Internal Assessment Report Draft Controlled Writer (Phase 37 — ninth DB-backed writer;
persistence counterpart to Phase 36):**

- [x] **A persisted plan, not a drafted report.** A narrow live DB writer that persists **exactly
  one** `internal_assessment_report_drafts` row from a Phase 36 `InternalAssessmentReportPlan`
  through the Phase 17 `ControlledWriteRequest` boundary — allowing only
  `internal_assessment_report_drafts` / `create_internal_assessment_report_draft`.
  [`../peak/db/internal_assessment_report_draft_writer.py`](../peak/db/internal_assessment_report_draft_writer.py),
  migration
  [`../alembic/versions/010_internal_assessment_report_drafts.py`](../alembic/versions/010_internal_assessment_report_drafts.py),
  docs [`INTERNAL_ASSESSMENT_REPORT_DRAFT_CONTROLLED_WRITER.md`](INTERNAL_ASSESSMENT_REPORT_DRAFT_CONTROLLED_WRITER.md)
  / [`INTERNAL_ASSESSMENT_REPORT_DRAFT_IDEMPOTENCY_POLICY.md`](INTERNAL_ASSESSMENT_REPORT_DRAFT_IDEMPOTENCY_POLICY.md).
  `output_status` is fixed at **`plan_persisted`** so a stored row can never be misread as report
  prose. The row stores section metadata, reference-only evidence traces, finding/recommendation
  candidate slots, open gaps, blocked items, and future-gate placeholders — and **no** final
  client-facing language, raw note/packet/evidence/interview text, source bytes, generated output,
  LLM prompt, credential, DSN, raw SQL, stack trace, approval decision, ROI/savings figure, or
  capsule/AgentNet publish payload.
- [x] **Internal-only, review-gated posture** (server-stamped, never copied from the caller):
  `audience=internal`, `review_status=needs_review`, `lifecycle_status=draft`, with
  `client_facing_approved` / `financial_verified` / `capsule_candidate_ready` /
  `publication_allowed` / `execution_allowed` false and `requires_human_review=true`. The writer
  independently re-verifies the Phase 36 posture — including on every nested finding and
  recommendation candidate — and denies caller-supplied ids/timestamps, a non-internal audience, a
  non-`plan` plan output status, an approved review status, a non-draft lifecycle, or any elevated
  flag.
- [x] **Write-time authorization.** Loads the stored `Engagement` and requires it to exist, to carry
  an `authorization_scope`, to match `request.authorization_scope`, to match owner/client/engagement
  identity, and to have a non-blocked lifecycle. **Identity matching is necessary but not
  sufficient**; the Phase 36 plan/request is never the authorization source.
- [x] **Idempotency.** Boundary `(owner_id, client_id, engagement_id, idempotency_key)` enforced by a
  real UNIQUE index, plus a canonical `payload_fingerprint` over identity, provenance, structure,
  references, and posture. Same key + same fingerprint → `idempotent_replay` (no mutation); same key
  + different fingerprint → `idempotency_conflict` (no mutation); `IntegrityError` re-queries inline
  to classify the race as replay / conflict / `write_outcome_uncertain`.
- [x] **Schema.** Migration `010_internal_assessment_report_drafts`
  (`down_revision = 009_intake_note_records`) creates one table with no INSERT/seed; the downgrade
  drops only that table; the head stays single and linear; the controlled DB now has **16 tables**.
  Exactly **one** new Phase 17 allowlist pair was added — no update/delete/upsert/raw-SQL action.
- [x] **Phase 36 stays DB-free.** The `ControlledWriteRequest` bridge
  (`build_internal_assessment_report_draft_write_request`) lives in the Phase 37 DB layer, mirroring
  the Phase 33/34 precedent, so `peak/reports` imports no `peak.db` and calls no writer (verified at
  runtime). Phase 37 approves nothing, verifies nothing financially, publishes nothing, executes
  nothing, calls no Phase 22 writer, creates no `review_records`/`agent_run_records` row, and makes
  no LLM/MockLLM/AgentNet/MCP/resolver/connector/network call. Checked by
  [`../tests/validate_phase37_internal_assessment_report_draft_writer.py`](../tests/validate_phase37_internal_assessment_report_draft_writer.py)
  (`make validate-phase37`; DB-backed via `.venv`).

**Internal Report Review Packet Controlled Writer (Phase 38 — tenth DB-backed writer):**

- [x] **A reviewer packet, not a review outcome.** A narrow live DB writer that persists **exactly
  one** `internal_report_review_packets` row from an `InternalReportReviewPacketDraft` through the
  Phase 17 `ControlledWriteRequest` boundary — allowing only `internal_report_review_packets` /
  `create_internal_report_review_packet`.
  [`../peak/db/internal_report_review_packet_writer.py`](../peak/db/internal_report_review_packet_writer.py),
  migration
  [`../alembic/versions/011_internal_report_review_packets.py`](../alembic/versions/011_internal_report_review_packets.py),
  docs [`INTERNAL_REPORT_REVIEW_PACKET_CONTROLLED_WRITER.md`](INTERNAL_REPORT_REVIEW_PACKET_CONTROLLED_WRITER.md)
  / [`INTERNAL_REPORT_REVIEW_PACKET_IDEMPOTENCY_POLICY.md`](INTERNAL_REPORT_REVIEW_PACKET_IDEMPOTENCY_POLICY.md).
  The row records what a Peak human reviewer was *shown and asked to evaluate* for a Phase 37 report
  draft: a section review checklist, reference-only evidence traces, open gaps, blocked items, short
  internal reviewer questions, a readiness checklist, required follow-up actions, and future-gate
  placeholders. It stores **no** report prose, raw note/packet/evidence/interview text, source bytes,
  generated output, LLM prompt, credential, DSN, raw SQL, stack trace, approval decision,
  ROI/savings figure, or capsule/AgentNet publish payload.
- [x] **Internal-only, pre-decision posture** (server-stamped): `audience=internal`,
  `packet_status=ready_for_internal_review`, `review_status=needs_review`,
  `lifecycle_status=draft`, `reviewer_decision_record_id=NULL`,
  `reviewer_decision_status=not_decided`, with `client_facing_approved` / `review_approval_made` /
  `financial_verified` / `capsule_candidate_ready` / `publication_allowed` / `execution_allowed`
  false and `requires_human_review=true`. A packet is created *before* any decision exists, so it
  can never be misread as a review outcome.
- [x] **Report-draft linkage mode B — the stored row is read, not trusted.** The writer loads the
  referenced `InternalAssessmentReportDraftRecord` and verifies tenant, scope, `audience=internal`,
  `output_status=plan_persisted`, `review_status=needs_review`, `lifecycle_status=draft`, every
  non-elevated posture flag, `requires_human_review=true`, and provenance (`report_plan_id` /
  `plan_fingerprint`), then copies `report_draft_payload_fingerprint` **from the stored row**. A
  plain reference never proves stored posture.
- [x] **Closed vocabularies and intent scanning.** Checklist items are strict dicts with a closed
  status allowlist so an approval-flavoured status can never be stored. Reviewer questions — the
  only prose-ish list — are bounded, single-line, marker-scanned **and** intent-scanned, so
  client-facing/approval language is denied (`prohibited_packet_intent`).
- [x] **Write-time authorization.** Loads the stored `Engagement` and requires it to exist, carry an
  `authorization_scope`, match `request.authorization_scope`, match owner/client/engagement identity,
  and have a non-blocked lifecycle. **Identity matching is necessary but not sufficient.**
- [x] **Idempotency.** Boundary `(owner_id, client_id, engagement_id, idempotency_key)` enforced by a
  real UNIQUE index, plus a canonical `payload_fingerprint` that binds the stored report-draft
  payload. Replay / conflict / `IntegrityError` race handled exactly as in the prior writers.
- [x] **Schema.** Migration `011_internal_report_review_packets`
  (`down_revision = 010_internal_assessment_report_drafts`) creates one table with no INSERT/seed;
  the downgrade drops only that table; the head stays single and linear; the controlled DB now has
  **17 tables**. Exactly **one** new Phase 17 allowlist pair — no update/delete/upsert/raw-SQL
  action. Index names are pinned short so every identifier fits MySQL's **64-character limit** (the
  convention-derived report-draft index name would have been 69 characters and SQLite would have
  accepted it silently).
- [x] **Nothing escalates.** Phase 38 approves nothing, verifies nothing financially, publishes
  nothing, executes nothing, calls no Phase 22 writer, creates no `review_records`/`agent_run_records`
  row, and makes no LLM/MockLLM/AgentNet/MCP/resolver/connector/network call. Checked by
  [`../tests/validate_phase38_internal_report_review_packet_writer.py`](../tests/validate_phase38_internal_report_review_packet_writer.py)
  (`make validate-phase38`; DB-backed via `.venv`).

**Internal Report Review Packet Decision Controlled Writer (Phase 39 — eleventh DB-backed writer;
closes the internal report review loop):**

- [x] **A justified new table, not drift.** Phase 39 was first specified as a *bridge* over the
  Phase 33 `internal_reviewer_decision_records` writer, to be used only if that writer could safely
  represent a packet decision. It was verified empirically that it **cannot**: the Phase 33 writer
  hard-requires `review_bundle_ref`/`review_bundle_record_id` (an honest packet decision has
  neither, and `internal_report_review_packets` has no bundle column), and its explicit record
  mapping has a closed `details_json` key set that **silently drops** packet / report-draft / plan
  linkage — so the row could not answer *which review packet was this decision about?* The only
  workarounds were to write a packet id into a column named and indexed as a review-bundle
  reference, or to lose the linkage. A separate narrow table was approved on that evidence.
  **Phase 33 is untouched** and remains the writer for review-bundle reviewer decisions.
- [x] **The narrow writer.** Persists **exactly one**
  `internal_report_review_packet_decisions` row through the Phase 17 boundary — allowing only
  `internal_report_review_packet_decisions` / `create_internal_report_review_packet_decision`.
  [`../peak/db/internal_report_review_packet_decision_writer.py`](../peak/db/internal_report_review_packet_decision_writer.py),
  migration
  [`../alembic/versions/012_internal_report_review_packet_decisions.py`](../alembic/versions/012_internal_report_review_packet_decisions.py),
  docs
  [`INTERNAL_REPORT_REVIEW_PACKET_DECISION_CONTROLLED_WRITER.md`](INTERNAL_REPORT_REVIEW_PACKET_DECISION_CONTROLLED_WRITER.md)
  / [`INTERNAL_REPORT_REVIEW_PACKET_DECISION_IDEMPOTENCY_POLICY.md`](INTERNAL_REPORT_REVIEW_PACKET_DECISION_IDEMPOTENCY_POLICY.md).
- [x] **Audit chain preserved.** The row stores `internal_report_review_packet_id`,
  `internal_assessment_report_draft_id`, `report_plan_id`, `plan_fingerprint`, both source-table
  labels, and both upstream payload fingerprints — the latter copied from the **stored** rows.
- [x] **Insert-only; nothing upstream is mutated.** Three reads (Engagement, packet, report draft)
  and one insert. The packet's `reviewer_decision_status` / `reviewer_decision_record_id` are **not**
  advanced; linking a packet back to its decision is deliberately left to a later controlled path.
  Tests assert both upstream rows are byte-for-byte unchanged.
- [x] **Closed decision vocabulary.** Reuses Phase 32 `ALLOWED_DECISION_INTENTS` verbatim, so
  approval-like and external-facing intents are denied automatically. **`ready_for_internal_use` is
  internal readiness, not client-facing approval.** `decision_status`
  (`decision_recorded` / `needs_followup`) is **server-derived** from the intent and participates in
  the fingerprint; the governed `review_status` / `lifecycle_status` axes stay inside the Phase 9
  vocabulary rather than absorbing decision-specific values.
- [x] **Write-time authorization and linkage.** Stored `Engagement` gate (scope, identity,
  lifecycle; identity necessary but not sufficient), then read-only verification of the stored
  packet (tenant, scope, linkage, `ready_for_internal_review`, pre-decision, non-elevated posture)
  and the stored report draft (tenant, scope, linkage, `plan_persisted`, non-elevated posture).
- [x] **Schema.** Migration `012` (`down_revision = 011_internal_report_review_packets`) creates one
  table with no INSERT/seed; the downgrade drops only that table; the head stays single and linear;
  the controlled DB now has **18 tables**; exactly **one** new allowlist pair (13 tables / 15
  actions). Index names use a short `ix_irrpd_` prefix because the convention-derived names would
  reach **78** characters — over MySQL's 64-char limit. This applies the Phase 38 finding
  proactively rather than discovering it in managed MySQL.
- [x] **Nothing escalates.** No approval for client use, client-facing output, financial/ROI
  verification, capsule publication, AgentNet publish, LLM/MockLLM, agent or mock-agent execution,
  MCP/resolver/network call, generic CRUD, or update/delete/upsert path; no Phase 22 writer call and
  no `review_records`/`agent_run_records` row. Checked by
  [`../tests/validate_phase39_internal_report_review_packet_decision_writer.py`](../tests/validate_phase39_internal_report_review_packet_decision_writer.py)
  (`make validate-phase39`; DB-backed via `.venv`).

**End-to-End Internal Report Review Workflow Integration (Phase 40 — read-only consolidation;
adds no persistence primitive):**

- [x] **Workflow integration, not a new primitive.** No DB table, model, or Alembic migration (head
  stays `012_internal_report_review_packet_decisions`; `make db-check` stays at **18 tables**); **no
  new Phase 17 allowlist pair** (13 tables / 15 actions); no writer, no update/delete/upsert path,
  no generic CRUD, no arbitrary SQL executor, no broad repository.
- [x] **Closes the Phase 39 gap by derivation, not mutation.** Phase 39 is insert-only and never
  advances the packet's `reviewer_decision_status` / `reviewer_decision_record_id`. Phase 40
  *computes* the current internal review state from the Phase 39 decision table. The packet row and
  the report-draft row are **never updated** — the harness asserts both are byte-for-byte unchanged
  and that no row is inserted, updated, or deleted. A packet row whose decision columns the located
  decision records cannot explain is a blocker, not something to repair.
- [x] **Public entry point.** `summarize_internal_report_review_workflow(request, *,
  session_factory=None) -> InternalReportReviewWorkflowResult`, with typed
  request / result / trace contracts. `session_factory` is required and there is **no ambient-DSN
  fallback**, so standard validation needs no live credentials and no network.
- [x] **Read-only enforcement.** `session.get` / ORM `session.query` only — no `session.add`,
  `delete`, `merge`, `flush`, `commit`, `update()`, or raw SQL, and no writer import. Checked
  against tokenized source so prose naming a forbidden call cannot mask a real one.
- [x] **Authorization unchanged.** The stored `Engagement` is the authorization subject and
  identity matching is necessary but not sufficient; the stored draft and packet must still carry
  their internal-only, non-elevated posture.
- [x] **Closed internal-only computed vocabulary** of thirteen states — six `blocked_*`,
  `awaiting_reviewer_decision`, five `decision_recorded_*`, and `conflicting_decisions`. No
  approval / published / verified state exists; **`ready_for_internal_use` is internal readiness,
  not client-facing approval.** The `decision_intent` → state map covers the whole Phase 32
  vocabulary and stays in lockstep with Phase 39's server-derived `decision_status`.
- [x] **Conflicts surfaced, never resolved.** Rows expressing the same decision collapse to one
  state; materially different decisions produce `conflicting_decisions` with
  `requires_human_review=true` and no automatic resolution.
- [x] **Nothing escalates.** No approval for client use, client-facing output, financial/ROI
  verification, capsule publication, AgentNet publish, LLM/MockLLM, agent or mock-agent execution,
  MCP/resolver/network call, or `review_records` / `agent_run_records` write. Checked by
  [`../tests/validate_phase40_internal_report_review_workflow.py`](../tests/validate_phase40_internal_report_review_workflow.py)
  (`make validate-phase40`; DB-backed via `.venv`).

**Managed MySQL Production-Parity Validation (Phase 41 — validation tooling and docs only;
no schema, no writer, no migration):**

- [x] **The Phase 38 lesson became a control.** MySQL limits identifiers to 64 characters and
  SQLite does not; Phase 38's convention-derived index name was **69** characters and Phase 39's
  would have been **78**. Both were caught by hand, which is not a control. Phase 41 adds
  [`../tools/managed_mysql_parity_check.py`](../tools/managed_mysql_parity_check.py), wired into
  `make validate` and available as `make mysql-parity-static`.
- [x] **Offline by default.** No credentials, no network, no DNS, no TLS, no `.env`, no DSN, no
  database. `make validate` and `make db-check` remain safe on a machine with no managed DB access.
- [x] **Runtime-built identifiers are resolved without a database.** Migrations build index names
  from f-strings over module constants, so source scanning cannot see what MySQL would receive. The
  checker simulates each `upgrade()`/`downgrade()` against a recording stand-in for `op` that
  executes no SQL and opens no connection — 657 identifiers across 12 migrations, all verified
  against the 64-character limit.
- [x] **It is a real control, not a green light.** The harness injects the actual 69-character
  Phase 38 index name into a throwaway copy of the migrations and asserts the checker **fails**
  with exit 1.
- [x] **Static checks:** model + migration identifier lengths; no reliance on convention-derived
  names that would overflow; `InnoDB` + `utf8mb4` pinned everywhere and no legacy 3-byte `utf8`;
  linear migration chain with one base and a pinned head; schema-only migrations with no
  `INSERT`/seed/`op.execute`/arbitrary SQL; every `downgrade()` scoped to what its own `upgrade()`
  created.
- [x] **Open finding, reported not patched.** No collation is pinned anywhere, so the managed
  server default decides case/accent sensitivity for identity, authorization, and idempotency
  columns — which could let `idem-key-1` and `idem-KEY-1` collapse into one idempotency key under
  MySQL 8's default. It cannot be settled by reading the repo, so it is a `WARN` plus
  documentation; **no migration is proposed**, and fixing it would be its own reviewed phase.
- [x] **Opt-in staging gate, fail-closed.** `make mysql-parity-staging` skips (exit 0) with no
  configuration, importing no DB driver and reading no `.env`; **refuses** `--env prod` and a
  configured-but-not-disposable target (exit 2); and **holds** rather than auto-running when fully
  configured. It is excluded from `make validate`. No live run was executed in this phase.
- [x] **No secret leakage.** Every emitted line is sanitized (DSN forms, `password=`/`token=`/
  `api_key=` pairs, `user:pass@host`, PEM blocks -> `[secret withheld]`); failures report the exception
  **type** only. A canary DSN/secret is asserted absent from every mode's output. Checked by
  [`../tests/validate_phase41_managed_mysql_production_parity.py`](../tests/validate_phase41_managed_mysql_production_parity.py)
  (`make validate-phase41`; offline).

**Governed MySQL Collation Policy (Phase 42 — policy, audit, and remediation plan; no schema
change, no migration):**

- [x] **The Phase 41 warning became a measurement.** Phase 41 reported the unpinned-collation gap
  over a hand-written column list. Phase 42 classifies **all 308 string columns across 18 tables**
  by what their comparisons decide, via
  [`../tools/governed_mysql_collation_audit.py`](../tools/governed_mysql_collation_audit.py)
  (`make mysql-collation-audit`, wired into `make validate`).
- [x] **Result: `NEEDS_REMEDIATION`.** **211 governed columns** (45 distinct names) require
  deterministic comparison; **none pins a collation**; **62 sit inside a UNIQUE constraint or
  primary key**. The rule adopted: *a column whose comparison decides identity, authorization,
  uniqueness, or integrity must not inherit its collation from the server* — and every future
  migration adding a governed string column must state its collation explicitly.
- [x] **Risk ranked honestly.** The `UNIQUE (owner_id, client_id, engagement_id, idempotency_key)`
  boundary on 11 tables is the top risk: writers persist the key **verbatim**, so a case-insensitive
  collation would collapse `idem-key-1` and `idem-KEY-1` into one key. Enum/status columns rank
  lower — controlled writers already gate them against closed vocabularies with case-sensitive
  Python membership tests, so a case variant cannot be persisted.
- [x] **Two Phase 41 corrections.** `packet_hash` is **not a column** (a Phase 23 ingestion-draft
  field folded into `details_json`), and enum/status columns were over-weighted. Both are now
  asserted by the audit rather than assumed.
- [x] **Migration `013` planned, not written.** `013_governed_identifier_collation_policy` is
  specified to affected tables/columns, index byte math (1536 of InnoDB's 3072 bytes — no index
  needs shortening), duplicate-key surfacing risk on populated tables, downgrade posture, and
  staging verification steps. **No `alembic/versions/013_*.py` exists** and the harness asserts its
  absence. Collation selection is deliberately deferred — the repo pins no MySQL major version, so
  `utf8mb4_bin` leads (governed values are ASCII by construction) without being declared final.
- [x] **Offline and self-checking.** The audit needs no credentials, network, `.env`, DSN, or DB
  driver; exits 0 while reporting `NEEDS_REMEDIATION`; and exits 1 only when the audit itself is
  broken — proven by a negative test that removes a required governed column. Checked by
  [`../tests/validate_phase42_governed_mysql_collation_policy.py`](../tests/validate_phase42_governed_mysql_collation_policy.py)
  (`make validate-phase42`; offline).

**Production MySQL Collation Verification (Phase 43 — read-only production verification and a
go/no-go decision; no schema change, no migration):**

- [x] **Production became the target.** Peak now builds on the real deployed database. Phase 42
  measured the collation risk offline but could not tell whether it is *live*, because that depends
  on the running production server's effective collation. Phase 43 reads it via
  [`../tools/production_mysql_collation_verify.py`](../tools/production_mysql_collation_verify.py)
  (`make production-mysql-collation-verify`), under a strict read-only boundary.
- [x] **Read-only by construction, not convention.** A hard-coded query allowlist; an
  `assert_read_only()` guard before every execution and again at the driver boundary, requiring the
  statement to *be* an allowlisted constant, begin with `SELECT`/`SHOW`, and contain no mutating
  verb or separator. No code path accepts SQL from argv, environment, or file. A read-only
  statement that is merely off-allowlist is still refused.
- [x] **Fails closed.** Unconfigured → skip (exit 0), no driver imported, no `.env` read. A
  connection setting without `PEAK_PRODUCTION_DB_READONLY_CONFIRM` → **REFUSED** (exit 2), no
  connection attempted. Deliberately excluded from `make validate`, which stays fully offline.
- [x] **Checks:** server version family, database charset/collation, table and column collations,
  governed-column determinism (reusing the **Phase 42 classifier**, so the two cannot drift), the
  11 idempotency-boundary tables, the Alembic head, and an **empirical cross-check**
  (`SELECT ('a' COLLATE <c>) = ('A' COLLATE <c>)`) that confirms behavior rather than inferring it
  from a collation name.
- [x] **No secrets, no client data.** No DSN, host, user, password, token, cert, or environment
  value is printed; no production row value is emitted; the opt-in collision probe returns counts
  only; failures report the exception *type*, because driver messages embed the DSN.
- [x] **Go/no-go, not action.** `verified_risk_live_remediation_required` → GO for migration `013`
  subject to approval, a tested restore, a maintenance window, and a rehearsal;
  `verified_safe…` → NO-GO; `verified_inconclusive` → never migrate on inconclusive evidence.
  **Migration `013` is not created, proposed as code, or executed.**
- [x] **A Phase 42 correction.** Phase 42 claimed tightening the collation could surface new
  duplicate-key violations. That was backwards — insensitive → sensitive makes a unique index more
  discriminating, so previously-colliding values become distinct and no new violations are
  possible. Corrected in the policy doc. Checked by
  [`../tests/validate_phase43_production_mysql_collation_verification.py`](../tests/validate_phase43_production_mysql_collation_verification.py)
  (`make validate-phase43`; offline).

**Governed Identifier Collation Migration (Phase 44 — migration 013 + model metadata; no
production execution):**

- [x] **The policy became code.** Migration `013_governed_identifier_collation_policy`
  (`down_revision = 012`) and the model metadata pin **`utf8mb4_bin`** on all **211 governed
  columns** across 18 tables. Head moved 012 → 013; table count, model entities, writers, and the
  allowlist are unchanged.
- [x] **Scope is exactly the deterministic-required classes** — identifier (156), scope (27),
  hash/fingerprint (17), idempotency (11). `ordinary_text` (9) and `json_or_details_text` (3) carry
  no equality boundary; `governed_enum_status` (85) is deterministic-*preferred* because controlled
  writers already gate it case-sensitively in Python, and was deliberately left out of scope.
- [x] **A repo-level blocker was found and solved.** `String(collation=...)` renders `COLLATE` on
  every dialect and SQLite rejects it (`no such collation sequence`), which would have broken a
  dozen structural-smoke harnesses. Models use `GovernedString`, attaching the collation through a
  MySQL `with_variant`: identical MySQL DDL, SQLite untouched.
- [x] **ALTER-only migration.** 211 `ALTER … MODIFY … COLLATE utf8mb4_bin` statements with lengths
  and nullability preserved; no CREATE/DROP, no data operation, no raw SQL, no index or constraint
  rename, no earlier migration edited. SQLite is a deliberate no-op. The mapping is a static
  literal — the harness parses it with `ast` rather than importing, proving it is reviewable and
  not built at runtime — and is compared **both ways** against the live models.
- [x] **Status is now `MODEL_POLICY_SATISFIED_PRODUCTION_UNVERIFIED`.** Source control is correct;
  the deployed database has **not** been migrated. Phase 44 executed nothing against production,
  and a production execution checklist (verify → approve → backup with tested restore → rehearse →
  window → execute → re-verify) is recorded in the policy doc. Checked by
  [`../tests/validate_phase44_governed_identifier_collation_migration.py`](../tests/validate_phase44_governed_identifier_collation_migration.py)
  (`make validate-phase44`; offline).

**Production Collation Verification (Phase 45 — operational read-only verification attempt; no
source, schema, or migration change):**

- [x] **Ran, connected, and returned `verified_inconclusive`** (`reason_code:
  no_governed_columns_readable`). Server and database-level metadata were readable and the database
  default collation was confirmed **case-insensitive** empirically, but **zero of the 18 expected
  tables were visible** and `alembic_version` was unreadable, so `governed_columns_checked` and
  `idempotency_boundaries_checked` were both **0**. The collision probe was not run.
- [x] **`0 at risk` here means `0 of 0`** — nothing was examined. It does not prove production safe,
  and it does not prove the risk live at the column level.
- [x] **NO-GO for migration `013` as a standalone remediation against existing tables**, since on a
  new production instance zero visible tables most likely means the schema was never bootstrapped.
  Nothing was executed, written, altered, cleaned up, or deleted in production; no source file
  changed; no connection or credential detail was recorded.
- [x] **Production schema bootstrap — completed by Phase 46.** Bootstrapped from an empty database
  to head `013` and re-verified: 18 tables, a readable `alembic_version`, 211 governed columns
  checked, and 0 at risk. Bootstrap was schema-changing and ran under separate approval with a
  dedicated migration credential; the read-only verifier credential was **not** upgraded. Recorded in
  [`PHASE45_PRODUCTION_COLLATION_VERIFICATION.md`](PHASE45_PRODUCTION_COLLATION_VERIFICATION.md) and
  [`PHASE46_PRODUCTION_SCHEMA_BOOTSTRAP_RECOVERY.md`](PHASE46_PRODUCTION_SCHEMA_BOOTSTRAP_RECOVERY.md).

**Production Schema Bootstrap Recovery (Phase 46 — operational bootstrap, partial failure, approved
recovery, and re-verification; no source, model, or migration change):**

- [x] **Bootstrap ran once from the empty/new production database and failed partway.** Migrations
  `001`–`007` recorded; migration `008` completed its DDL but Alembic could not record it, because
  `alembic_version.version_num` was the Alembic default `VARCHAR(32)` and five revision ids —
  including `008_internal_reviewer_decision_records` and `013_governed_identifier_collation_policy` —
  are longer than 32 characters. Production was left partially bootstrapped at recorded revision
  `007` with 15 base tables, 141 governed columns all at risk, and 7 idempotency boundaries all at
  risk (`verified_risk_live_remediation_required`). No second schema-changing command was run before
  approval.
- [x] **Recovery executed under explicit approval, limited to three actions:** one exact
  `ALTER TABLE alembic_version MODIFY COLUMN version_num VARCHAR(255) NOT NULL`, one Alembic stamp to
  `008_internal_reviewer_decision_records`, and one Alembic upgrade to head. Stamping `008` was safe
  because Alembic writes the version table only after the migration body returns and MySQL DDL is
  non-transactional, so `008`'s DDL was already committed. No downgrade, `DROP`, `DELETE`,
  `TRUNCATE`, cleanup, arbitrary SQL, second `ALTER`, or second upgrade.
- [x] **Production now verifies safe.** Head `013_governed_identifier_collation_policy`,
  `alembic_version` readable and at head, 18 expected tables plus `alembic_version`,
  `governed_columns_checked: 211`, `governed_columns_at_risk: 0`,
  `idempotency_boundaries_checked: 11`, `idempotency_boundaries_at_risk: 0`, outcome
  `verified_safe_no_remediation_required`. **No further migration `013` action is needed.** Separate
  read-only and migration credentials were used and the verifier credential was not upgraded; no
  connection or credential detail was recorded; no source file changed.
- [ ] **Next (Phase 47): Alembic version-table hardening in source.** The production database was
  repaired manually and that repair exists nowhere in source control, so any fresh MySQL bootstrap —
  new environment, staging rebuild, restore drill, CI database, disaster-recovery exercise — will
  hit the same `VARCHAR(32)` failure. Harden before standing up any new environment. Recorded in
  [`PHASE46_PRODUCTION_SCHEMA_BOOTSTRAP_RECOVERY.md`](PHASE46_PRODUCTION_SCHEMA_BOOTSTRAP_RECOVERY.md).

**Alembic Version-Table Hardening (Phase 47 — source hardening only; no production command, no
migration, no model/table/writer change):**

- [x] **Root cause fixed in source.** Alembic's bookkeeping column defaults to `VARCHAR(32)` while
  five revision ids here are longer (34–43 chars), which is what halted the Phase 46 bootstrap at
  `008`. `alembic/env.py` now runs a preflight that creates `alembic_version` at
  `version_num VARCHAR(255) NOT NULL` when absent, widens it when narrower, and does nothing when it
  is already wide enough or the dialect is not MySQL/MariaDB. SQLite smoke behaviour is unchanged and
  offline mode opens no connection.
- [x] **Alembic exposes no width parameter** on `context.configure()`; its one official hook,
  `DefaultImpl.version_table_impl`, governs only the `CREATE` shape and cannot widen an existing
  narrow column — so a preflight covers all three states with one deterministic mechanism.
- [x] **Bookkeeping only, and narrowly bounded.** The entire SQL surface is two fixed literals naming
  only `alembic_version` and `version_num`; no application-table DDL, no `DROP`/`DELETE`/`TRUNCATE`,
  no arbitrary SQL executor, no credential or `.env` access. A source-side guard fails loudly if any
  future revision id exceeds the configured width. Head stays `013`, migrations stay 13, tables stay
  18, and no revision id was rewritten. Recorded in
  [`PHASE47_ALEMBIC_VERSION_TABLE_HARDENING.md`](PHASE47_ALEMBIC_VERSION_TABLE_HARDENING.md).
- [ ] **Untested against a live MySQL server**, by design — no MySQL is reachable from the validation
  suite. The create/widen/no-op branches are proven against a stubbed dialect and the statements are
  asserted character-for-character; a real fresh MySQL/MariaDB bootstrap is the outstanding
  confirmation, and is the natural first check when the next environment is stood up.

**Production Runtime Readiness Gate (Phase 48 — read-only gate; no production write, no app-row
read, no writer enabled, no source change):**

- [x] **Production re-verified safe before the gate.** Head `013`, `alembic_version` readable and at
  head, 18 expected tables plus `alembic_version`, `governed_columns_checked: 211`,
  `governed_columns_at_risk: 0`, `idempotency_boundaries_checked: 11`,
  `idempotency_boundaries_at_risk: 0`, outcome `verified_safe_no_remediation_required`.
- [x] **Source says runtime needs `SELECT` + `INSERT` only.** All eleven controlled writers are
  create-only (`session.add` is the sole persistence call); the replay path returns an existing row
  without mutating it, so no ORM flush can emit an `UPDATE`; no writer needs schema privileges. The
  three update-shaped allowlist names (`update_review_status`, `update_lifecycle_status`,
  `mark_superseded`) are **declared vocabulary with no implementation** — re-run this gate if any
  gains one.
- [x] **Three credentials, separated by role** (verifier / migration / runtime), each in its own
  operator-local untracked `0600` file defining only its own variable, with three distinct
  usernames. The read-only credential was not upgraded and the migration credential was not reused
  for runtime. **Runtime grants are exactly `SELECT` + `INSERT`** on the application schema — no
  `UPDATE`/`DELETE`/DDL, no global scope, no `GRANT OPTION`, no `ALL PRIVILEGES`; 0 missing, 0
  excess. Established via `SHOW GRANTS FOR CURRENT_USER` only, with no app-table read.
- [x] **Decision: READY** for controlled runtime writer connectivity. **Phase 48 enabled nothing** —
  no writer ran, no deployment or environment config changed. Recorded in
  [`PHASE48_PRODUCTION_RUNTIME_READINESS_GATE.md`](PHASE48_PRODUCTION_RUNTIME_READINESS_GATE.md).
- [ ] **Next (enablement, separately approved): give runtime its own URL variable in source.**
  `peak/db/session.py` reads `PEAK_DATABASE_URL`, so nothing consumes `PEAK_RUNTIME_DATABASE_URL`
  today and the runtime credential cannot yet be used by the application. This must **not** be
  resolved by exporting `PEAK_DATABASE_URL` from the runtime file — that would collapse the runtime
  and migration variables into one name and undo the separation this gate established.

**Runtime Database URL Separation (Phase 49 — source wiring only; no production command, no
connection, no writer enabled, no migration/model/table/writer/allowlist change):**

- [x] **Runtime has its own variable.** `peak/db/session.py` now reads
  `PEAK_RUNTIME_DATABASE_URL` and performs exactly one environment read; `alembic/env.py` still
  reads `PEAK_DATABASE_URL` and names neither other variable; the read-only verifier keeps
  `PEAK_PRODUCTION_DB_URL` and never names the runtime one. The three code paths are disjoint, and
  `.env.example` documents all three as separate placeholders.
- [x] **Fails closed, never falls back.** A missing `PEAK_RUNTIME_DATABASE_URL` raises rather than
  borrowing the migration credential — including when `PEAK_DATABASE_URL` *is* set — because a
  silent fallback would give application code schema-change privileges exactly when configuration
  went wrong. The error names variable names only: no value, no `://` scheme.
- [x] **Local paths unchanged and explicit.** Writers still accept `session_factory=`, and
  `create_session_factory(url=...)` accepts an explicit URL, so harnesses need none of the three
  variables. `get_database_url()` / `create_db_engine()` / `ENV_VAR` remain as deprecated aliases
  resolving to the runtime path. All eleven writers stay create-only and still resolve sessions
  through `create_session_factory()`. Recorded in
  [`PHASE49_RUNTIME_DATABASE_URL_SEPARATION.md`](PHASE49_RUNTIME_DATABASE_URL_SEPARATION.md).
- [ ] **Next: runtime enablement, separately approved.** Phase 49 makes correct wiring *possible*;
  it enables nothing. No writer was run, no deployment or environment config was added, and nothing
  was pointed at production. The enablement phase should also confirm the runtime credential still
  matches the Phase 48 grant set before any writer connects.

**Controlled Runtime Connectivity Gate (Phase 50 — read-only gate + reusable tool; no production
write, no app-row read, no migration, no writer enabled or invoked, no deployment change):**

- [x] **Reusable gate added.** `tools/production_runtime_connectivity_gate.py` connects through
  `peak.db.session.create_runtime_engine` — the application's own path, so a regression there fails
  the gate — using `PEAK_RUNTIME_DATABASE_URL` only. It **scrubs** `PEAK_DATABASE_URL` and
  `PEAK_PRODUCTION_DB_URL` from its own process first, so a successful connection is *evidence* the
  runtime variable sufficed rather than an assertion. Exposed as the opt-in
  `make runtime-connectivity-gate`, deliberately **not** part of `make validate`.
- [x] **Two statements, hard-coded.** `SELECT 1` and `SHOW GRANTS FOR CURRENT_USER`, checked for
  identity (not resemblance) before execution. Neither has a `FROM` clause or a `COUNT(`; no
  application table name appears in the tool; grants are parsed in memory and only booleans leave
  the process; failures report the exception *type* only.
- [x] **Grant policy is exact.** Requires `SELECT` + `INSERT`; fails on any of `UPDATE`, `DELETE`,
  DDL, `INDEX`/`REFERENCES`, routine/view/event/trigger privileges, admin privileges,
  `ALL PRIVILEGES`, `WITH GRANT OPTION`, or any global `*.*` privilege beyond `USAGE`. Too broad
  *or* too narrow fails.
- [x] **Self-test mode is safe by construction.** `--self-test` contacts no database, refuses when a
  runtime URL is set, can never report readiness, and is a CLI flag rather than an environment
  switch. Recorded in
  [`PHASE50_CONTROLLED_RUNTIME_CONNECTIVITY_GATE.md`](PHASE50_CONTROLLED_RUNTIME_CONNECTIVITY_GATE.md).
- [ ] **Next: writer enablement, separately approved.** A passing gate means the connection and
  privilege posture are right — not that writers should start. The enablement phase must explicitly
  choose between no production smoke-write, one approved synthetic/administrative smoke-write (note
  runtime holds no `DELETE`, so such a row cannot be removed by runtime), or a real engagement-only
  write after client authorization exists. Re-run this gate first; grant posture can drift.

**Writer Enablement Decision Gate (Phase 51 — governance decision gate; no writer enabled or
invoked, no production write, no app-row read, no schema/migration change):**

- [x] **Decision recorded: no write, no enablement.** `selected_path = no_production_smoke_write_yet`,
  with `production_write_authorized`, `writer_enablement_authorized`, `synthetic_write_authorized`,
  `real_engagement_write_authorized`, `safe_to_run_writers_now`, and `safe_to_write_production_now`
  all **false**. `tools/production_writer_enablement_decision_gate.py` exits 0 for the no-write path
  and **refuses (exit 3)** any request to record a write-authorizing path — and no field flips when
  one is asked for.
- [x] **Connectivity is prerequisite evidence, not permission.** Phases 48–50 answered technical
  questions (grants, wiring, connection). None answered whether anything *should* be written. The
  gate records `phase50_pass_is_prerequisite_evidence_not_write_permission = true` so that a green
  connectivity check can never be mistaken for authorization.
- [x] **Runtime has no `DELETE`, so cleanup is part of the authorization.** A synthetic or
  administrative record written by runtime **cannot be removed by runtime**; removal needs the
  migration credential under separate approval. Any synthetic record must therefore be treated as
  **durable**. Recorded as `requires_explicit_cleanup_plan_before_synthetic_write = true`.
- [x] **Offline by construction.** The gate has no database code path at all — no engine, session,
  writer, or driver import; no environment read; no statement; no file access. Opt-in as
  `make writer-enablement-decision-gate`; its static harness runs inside `make validate`. Recorded in
  [`PHASE51_WRITER_ENABLEMENT_DECISION_GATE.md`](PHASE51_WRITER_ENABLEMENT_DECISION_GATE.md).
- [ ] **Next: wait for authorized engagement/intake data, or separately approve a no-cleanup
  administrative smoke record.** Whichever future phase authorizes a write must re-run all three
  gates (read-only verifier, runtime connectivity, this decision gate) and name in advance: the
  writer, target table, exact allowed action, authorization scope, idempotency-key design,
  rollback/cleanup posture, and whether a durable synthetic/admin record will remain.

**Runtime Gate Driver-Unavailable Diagnostic (Phase 52A — diagnostic polish only; no production
command, no connection, no writer, no schema/migration change):**

- [x] **A missing local driver is now classified as local, not as a production failure.** The
  Phase 50 gate previously reported only `connect_failed:ModuleNotFoundError`, which reads like a
  production outage when it is a workstation dependency problem. It now emits
  `failure_category=local_driver_unavailable`,
  `production_connectivity_result=not_tested_due_to_local_driver_unavailable`,
  `failure_exception_type` (type only, never a message), and the static remediation
  `recommended_command=make runtime-connectivity-gate PYTHON=.venv/bin/python`, plus human-readable
  `CAUSE:`/`FIX:` lines. Genuine connection failures stay `connection_failed` / `failed`, and a
  missing runtime URL stays `runtime_url_not_set` / `not_tested`.
- [x] **Fail-closed behaviour is unchanged.** Nonzero exit, `connectivity_succeeded=false`,
  `ready_for_later_writer_enablement=false`, zero statements issued, no stack trace, no connection
  detail. The gate installs no dependency, activates no virtual environment, and never silently
  retries under another interpreter. The two-statement allowlist and the hostile-statement guard are
  untouched.
- [x] **Exercised without uninstalling anything.** The harness blocks the driver import in one child
  process — a test-only seam that lives in the harness, never in the gate, so it cannot be switched
  on during a live run.
- [x] **The Phase 51 no-write / no-enablement decision is unchanged**, and this phase authorizes
  nothing.

**Authorized Engagement / Intake Path Planning (Phase 53 — plan only; no production write, no
writer enablement, no synthetic smoke write, no engagement record, no intake note, no schema or
migration change):**

- [x] **The required authorization anchor is a stored `Engagement` row with a populated
  `authorization_scope`.** Every controlled writer loads that row at write time and requires the
  request scope to equal the stored scope; identity matching alone is not sufficient. No controlled
  write of any kind is possible before that row exists.
- [x] **Source inspection findings.** The `Engagement` model/table **exists** (`engagements`, from
  migration `001_initial`) — the schema side of the anchor is already in place. A controlled
  **Engagement writer does not exist**: no writer targets `engagements`, and the table sits in
  `PROHIBITED_TABLES` with no engagement-creating action on the allowlist. The **intake note writer
  exists** (Phase 34, `intake_note_records` / `create_intake_note_record`) and **requires the stored
  Engagement authorization** — it denies on missing subject, blank stored scope, scope mismatch,
  identity mismatch, or a blocked subject lifecycle.
- [x] **Recommended first real operational writer: the intake note writer**, once the anchor exists.
  It depends on the engagement anchor alone, needs no agent/LLM/AgentNet/resolver/network and no
  prior stored artifact, and its first row would be genuine work rather than a synthetic record.
- [x] **`SELECT` + `INSERT` remain sufficient** for the planned path; it requires no `UPDATE` and no
  `DELETE`, so no privilege change is needed.
- [ ] **Next: Phase 54 should add a create-only controlled Engagement authorization anchor writer**
  — and create no engagement record. Because no such writer exists, that is the conditional branch
  the findings selected; had one existed, Phase 54 would instead create the first authorized
  engagement record, only after explicit approval and once the exact authorized values are known.
- [x] **No synthetic smoke-write is authorized.** It stays disallowed unless separately approved,
  and because runtime holds no `DELETE` it would be durable — approvable only as a no-cleanup
  administrative record with that permanence understood up front, or with an explicit cleanup plan
  agreed before the write.
- [x] **The Phase 51 no-write / no-enablement decision is unchanged**, Phase 50 connectivity remains
  prerequisite evidence rather than write permission, the first production write remains deferred,
  and this phase authorizes nothing. See
  [`PHASE53_AUTHORIZED_ENGAGEMENT_INTAKE_PATH.md`](PHASE53_AUTHORIZED_ENGAGEMENT_INTAKE_PATH.md).

**Controlled Engagement Authorization Anchor Writer (Phase 54 — code path only; no engagement
record, no intake note, no synthetic smoke record, no writer enablement, no production write, no
schema or migration change):**

- [x] **The blocker Phase 53 named is resolved in code.** Every controlled writer loads a stored
  `Engagement` anchor and requires its scope to match; nothing could create that anchor, because
  `engagements` is a prohibited root table. Phase 54 adds
  `peak/db/engagement_authorization_anchor_writer.py` — the twelfth narrow writer, and the only one
  that may reach `engagements`.
- [x] **The grant is one pair, not a hole.** `engagements` **stays** on `PROHIBITED_TABLES`; the
  writer travels a separate one-pair gate, `ALLOWED_ANCHOR_CREATION_PAIRS` = exactly
  `engagements` / `create_engagement_authorization_anchor`, checked pair-wise. The generic allowlist
  is unchanged at 13 tables and 15 actions, the anchor action is not on it, and `clients` is listed
  never-writable and refused by both gates. Generic Engagement CRUD remains impossible.
- [x] **The stored-subject check is replaced, not weakened.** It would be circular here — the row
  being created *is* the subject. In its place: the exact pair, an absent `subject`, governed and
  bounded identity, a canonical non-revoked `authorization_scope`, an allowed initial lifecycle
  (`active`/`pending`/`draft`) and status (`prospective`/`active`), a required idempotency key, a
  typed draft whose identity matches, no `fixture_test` mixing, and value-marker screening on the
  label. All fail closed before any connection is opened.
- [x] **Create-only; `SELECT` + `INSERT` remains sufficient.** One `session.add`, one commit. No
  `UPDATE`, `DELETE`, `merge`, bulk operation, raw SQL, or schema operation; no network/LLM/AgentNet/
  MCP/resolver path; no table other than `engagements`; no `Client` row ever created. No privilege
  change is required.
- [x] **No migration was needed.** The anchor's primary key is its idempotency boundary and the
  replay fingerprint is recomputed from the stored row's governed fields, so no `idempotency_key` /
  `payload_fingerprint` column was added. Same id + same definition replays with no second write;
  same id + different definition is denied and the stored row is **not** modified. There is no
  overwrite path.
- [x] **Leak-free receipts.** No credential, DSN, host, database name, SQL string, stack trace, or
  raw payload — and never the `engagement_label`, which can carry a client organisation name. Only
  governed identifiers, safe status labels, and marker *categories*.
- [ ] **Next: the first production engagement anchor remains separately approved future work.** That
  phase must re-run all three gates and name in advance the exact `owner_id` / `client_id` /
  `engagement_id` / `authorization_scope` sources, approval authority, idempotency-key pattern,
  retention/cleanup posture, and whether the record is real client, internal/admin, or a separately
  approved durable admin smoke record.
- [x] **Phase 51 no-write / no-enablement is unchanged**, Phase 50 connectivity remains prerequisite
  evidence rather than write permission, synthetic smoke-writing remains disallowed unless
  separately approved, and runtime still holds no `DELETE` so cleanup cannot be assumed. See
  [`PHASE54_CONTROLLED_ENGAGEMENT_AUTHORIZATION_ANCHOR_WRITER.md`](PHASE54_CONTROLLED_ENGAGEMENT_AUTHORIZATION_ANCHOR_WRITER.md).

**Internal Test Engagement Classification (Phase 55 — plan and classification only; no engagement
record of any kind, no intake note, no synthetic smoke record, no capsule published, no writer
enablement, no schema/model/writer/allowlist change):**

- [x] **A fourth record category is named.** Peak will eventually keep a small number of **durable
  internal test / training engagements** — for training, live testing, and demonstration; retained
  deliberately; **never client-accessible**; carrying **no real client data** unless separately and
  explicitly authorized; optionally authorized for capsule publication when explicitly classified.
  They are distinct from real client engagements, from disposable synthetic smoke records (still
  disallowed), and from the in-memory synthetic fixtures the harnesses build.
- [x] **The current model cannot classify them.** `Engagement` carries `id`, `client_id`,
  `engagement_label`, `status` plus the governance/audit mixins — and none of the
  `client_facing_approved` / `capsule_candidate_ready` / `publication_allowed` real booleans that
  eight other record tables carry.
- [x] **The Phase 54 writer cannot either.** Its draft accepts no classification field, so there is
  nothing for it to validate or refuse.
- [x] **Every no-schema workaround was rejected, with reasons.** `authorization_scope` would be
  overloaded onto an orthogonal axis (it answers *who may see this*, not *what kind of record this
  is*); `fixture_test` is refused for anchors because they require live client/engagement identity
  (verified, not assumed); `engagement_label` and `id`-prefix conventions are too fragile to carry
  governance; `details_json` is documented as non-governance detail only.
- [x] **Isolation must be by classification, not convention**, and no client-facing read path exists
  yet to leak through — but `clients` is never writable, so there is no governed registry from which
  to reserve a non-colliding internal-test `client_id`. The creation packet must guarantee that.
- [ ] **Next: Phase 56 should add internal-test classification support — schema, model, and writer
  validation — and create no records.** Preparing the first creation packet is the phase after that,
  and executing it remains separately approved work.
- [x] **Phase 51 no-write / no-enablement is unchanged**, the Phase 54 writer's existence is **not**
  permission to write, synthetic smoke records remain disallowed unless separately approved with
  their permanence understood, and runtime still holds no `DELETE` so cleanup cannot be assumed. See
  [`PHASE55_INTERNAL_TEST_ENGAGEMENT_CLASSIFICATION.md`](PHASE55_INTERNAL_TEST_ENGAGEMENT_CLASSIFICATION.md).

**Internal Test Engagement Support (Phase 56 — schema + writer classification; no records created,
no writer enabled, no production migration, no capsule published):**

- [x] **Migration `014_engagement_classification`** adds `engagement_category` (governed string;
  `real_client` / `internal_test`), `real_client_data`, `client_accessible`, and
  `capsule_publication_authorized` as **real columns** on `engagements`. Additive, reversible, no
  INSERT/seed data. **18 tables and 12 writers unchanged**; `Client` untouched.
- [x] **Defaults point the safe way** — an unclassified row is a real client engagement, and
  publication is never granted by default.
- [x] **The anchor writer validates the classification** before opening any connection.
  `internal_test` requires no real client data, non-client-accessibility, and a **reserved
  `client_id` namespace** (`99999` / reserved prefix) — a visible marker that is deliberately not
  the whole control. The rule is **bidirectional**: a real client engagement may not use it.
- [x] **Publication requires explicit authorization AND no real client data**, checked together;
  real client engagements may not authorize publication here at all.
- [x] **Writer stays create-only** — `engagements` only, no `UPDATE`/`DELETE`/merge/bulk/raw SQL,
  `SELECT` + `INSERT` sufficient, leak-free receipts. Classification joins the replay fingerprint,
  so a changed classification under the same anchor id is a conflict, never an overwrite.
- [ ] **Next: read-side isolation is still to build** — `client_accessible` is the contract, not the
  enforcement — and the first internal test engagement creation remains a **separately approved
  future phase**. Production was still at migration 013 at that point; 014 was applied to production
  later, in Phase 58.

**Read-Side Isolation for Internal Test Engagements (Phase 57 — enforcement primitive only; no
records created, no client-facing route or UI, no writer enabled, no production migration):**

- [x] **The Phase 56 contract now has enforcement.** `peak/db/engagement_read_isolation.py` supplies
  row predicates and SQLAlchemy filter clauses over the classification columns. No table, model,
  writer, migration, or allowlist pair added; head stays `014`.
- [x] **Exclusion is the default.** The client-facing mode admits only `real_client` +
  `client_accessible` + `real_client_data`, and **ignores** `include_internal_test` — it cannot be
  widened by a flag. Internal/admin reads see internal test engagements **only** on explicit opt-in,
  and an unrecognised mode fails closed.
- [x] **`client_id` is not the access control.** A reserved id (`99999` / reserved prefix) is
  excluded from client-facing reads as defence in depth, but an internal test record with an
  ordinary id is excluded too, and a `client_id` narrowing cannot resurrect an excluded row.
- [x] **Publication eligibility is separate from visibility** — the compound rule describes a record
  that is publishable *and* invisible to every client.
- [x] **No coupling:** the helper opens no connection, creates/modifies no record, imports no
  writer, executes no raw SQL, and reads no environment variable.
- [x] **Next: the first client-facing read path must actually call it** — a read that bypasses
  `apply_read_isolation` is not protected by it. This remains outstanding; migration 014 *was*
  applied to production in Phase 58, and the first internal test engagement creation remains
  separately approved.

**Migration 014 Applied to Production (Phase 58 — schema change only; no production application
records created, no writer invoked, no runtime credential used):**

- [x] **Migration `014_engagement_classification` was applied to production.** Applied with the
  production migration credential using the explicit revision, never an open-ended `upgrade head`.
  **Production schema now supports the Engagement classification fields** `engagement_category`,
  `real_client_data`, `client_accessible`, and `capsule_publication_authorized`, plus
  `ix_engagements_engagement_category`. Head is `014` in production as well as in the repository;
  14 migrations, 18 tables, 12 writers.
- [x] **Three authorized production actions, and only three:** read-only pre-migration verification,
  the migration itself, and read-only post-migration verification. The only production mutation was
  migration 014's schema change plus Alembic's own `alembic_version` update. No downgrade, no manual
  `ALTER`, no migration 015, no cleanup or delete path.
- [x] **The production verifier's expected head is now `014`, not `013`.** The pin in
  `tools/production_mysql_collation_verify.py` tracks the *live* production head, so it moves only
  when a migration has genuinely been applied there — never merely when it is written. Three
  harnesses assert the pin. `engagement_category` classifies as `governed_scope`, so the production
  governed-column count moves 211 → 212 and the deterministic collation posture still holds, with
  all 11 idempotency boundaries case-sensitive.
- [x] **No production application records were created**, read, updated, or deleted; verification
  touched `INFORMATION_SCHEMA` and `alembic_version` only, with the collision probe left unrun. **No
  writer was invoked**, **no runtime credential was used**, and no credential, DSN, or environment
  value was printed or committed.
- [x] **No internal test engagement was created.** 014 makes the classification representable, not
  authorized.
- [x] **Next: the first internal test engagement anchor remains separately approved.** It was
  separately approved and created in Phase 59, on exactly those terms.

**The First Durable Internal Test Engagement Anchor (Phase 59 — one production application record;
no Client record, no intake note, no downstream record, no capsule, no writer enabled):**

- [x] **One durable `internal_test` engagement anchor was created in production**, through the
  unchanged Phase 54/56 controlled writer — Peak's first production application record.
  `engagement_category=internal_test`, `real_client_data=false`, `client_accessible=false`,
  `capsule_publication_authorized=true`, reserved `99999` client namespace, scope
  `internal_peak_only`, `active`/`active`, server-stamped `needs_review`. No migration, table,
  model, writer, or allowlist pair added; head stays `014` with 18 tables and 12 writers.
- [x] **Classification lives in real columns** — never in `details_json`, the label, the scope, or
  the id prefix. The reserved `client_id` is a visible marker on top of the controls, not instead
  of them.
- [x] **Durable, not disposable.** Runtime holds `SELECT` + `INSERT` and no `DELETE`, so the record
  cannot be cleaned up and is not meant to be; cleanup posture was decided before the write.
  Disposable production smoke records remain disallowed, and no writer was enabled.
- [x] **Publication eligibility is not publication.** `capsule_publication_authorized=true` is
  permitted only because the compound internal_test / no-real-client-data / not-client-accessible
  rule is satisfied. No capsule was created or published.
- [x] **Credential boundary held.** The runtime credential was used only through the controlled
  writer path; the connectivity gate confirmed `SELECT` + `INSERT` with no excess grants, no global
  privileges, and no `GRANT OPTION`. The migration credential was not used and no migration ran. No
  `UPDATE`/`DELETE`/manual SQL/cleanup/stamp, no app table scan or count, no secrets printed.
- [x] **A narrow operator utility, not a record creator.**
  `tools/create_internal_test_engagement_anchor.py` holds one hard-coded packet, accepts no record
  field, and is dry-run by default.
- [ ] **Next: the first client-facing read path must actually call `apply_read_isolation`.** An
  internal test row now genuinely exists in production, so an unfiltered client-facing query would
  surface it. Any further production record remains separately approved.

**Intake Taxonomy V0 and the First Internal Test Intake Note (Phase 60 — one production application
record; no Client record, no additional Engagement, no downstream record, no capsule, no writer
enabled):**

- [x] **Intake questions are now grounded in a taxonomy, not invented as form fields.**
  `docs/PEAK_INTAKE_QUESTION_TAXONOMY_V0.md` defines fourteen categories, each mapped to what it
  feeds: the operations assessment, prioritized improvement plan, evidence map, data/source quality
  review, AI/AgentNet readiness view, and future capsule/publication readiness. The rule is that a
  question is justified only when it supports a downstream decision, evidence need, report section,
  or readiness judgment.
- [x] **V0 is explicitly not the final client-facing questionnaire.** Future forms should be
  **generated from the taxonomy, not guessed**; a question mapping to no category means either the
  taxonomy is missing a downstream need or the question should be cut.
- [x] **The GeoSites lesson is preserved at strategy level.** A future GeoSites intake should derive
  its questions from website / GEO-AEO / structured-data / generative-discovery deliverables. The
  category list will differ entirely; the derivation rule will not. **No GeoSites code is built.**
- [x] **One durable `internal_test` intake note was created in production**, tied to
  `internal_test_001` / `99999` / `internal_peak_only` through the unchanged Phase 34 controlled
  writer. Review-gated and non-final (`needs_review` / `draft`), **not client-facing**, containing
  **no real client data**, and durable internal/admin data rather than disposable smoke. Head stays
  `014` with 18 tables and 12 writers.
- [x] **Authorization came from the stored engagement.** The writer loaded the Phase 59 anchor and
  required the request scope to match the stored scope; identity matching alone is not sufficient.
  The anchor was read, not modified.
- [x] **No Client record, no additional Engagement, no downstream record, no capsule.** No
  `UPDATE`/`DELETE`/manual SQL/cleanup/stamp, and no app table scan or count beyond the writer's own
  stored-engagement load and idempotency lookup.
- [x] **No intake prose entered source control.** Note bodies belong only in the managed DB, so the
  operator utility reads the body from outside the repository and reports only its length and
  SHA-256; receipts never echo note content.
- [ ] **Next: render the taxonomy into a real intake form**, and build the first client-facing read
  path on top of `apply_read_isolation`. Any further production record remains separately approved.

**The Internal Test Intake Review Decision (Phase 61 — one production application record; no Client
record, no additional Engagement, no second intake note, no source/evidence/report/capsule record,
no writer enabled):**

- [x] **One internal review decision record was created** in production for the Phase 60 intake
  note `intn_b8b86b8c196c4595`, through the unchanged Phase 22 `review_records` writer. Head stays
  `014` with 18 tables and 12 writers; no writer or allowlist pair was added.
- [x] **`review_records` was the honest fit, and the alternative was rejected.** The writer keeps
  the **authorization anchor** (`request.subject`, which must be an `engagement`) separate from the
  **reviewed target** (`draft.subject_record_id`, stored as `target_id`), so the intake note is
  reviewed under the Phase 59 anchor's authority without overloading either field. The bundle-shaped
  `internal_reviewer_decision_records` draft has no reviewed-target field, so using it would have
  meant misusing a bundle reference.
- [x] **The decision authorizes source/evidence collection, not report or capsule publication.**
  `approve_internal` is the writer's vocabulary for internal reliance only; `client_facing_approve`,
  `verify_financial_impact`, and `publish_capsule` are refused outright. `authoritative=false`,
  `client_facing_approved=false`, `capsule_candidate_ready=false`, output stays `draft`.
- [x] **Covered and missing categories were derived from the V0 taxonomy.** All 14 categories are
  covered *qualitatively*; the note carries **no counts, rates, cadences, or dates**, so eight
  categories are recorded as quantitatively incomplete — which is exactly why the next step is
  collection rather than analysis.
- [x] **Eight next evidence requests are recorded** — inventory export by SKU/location, item/SKU
  master export, adjustment history with reason codes, receiving/putaway records, cycle or physical
  count results, stockout/backorder data, SOP and process documentation, and a system-of-record and
  data-export map.
- [x] **The note remains internal-only and non-client-facing**, and no note prose entered source
  control: the findings are category labels and gap descriptors, and this phase's tools never read
  the note body.
- [ ] **Next: source/evidence request and source ingestion planning** — the source ingestion or
  evidence writer is the sensible next downstream path to exercise. Report drafting, capsule
  candidacy, and publication remain unauthorized.

**The Internal Test Source/Evidence Request Plan (Phase 62 — planning-only; no production write, no
production record, no writer invoked, no migration, no allowlist pair):**

- [x] **Phase 62 creates no production record.** It opens no database connection, issues no SQL,
  invokes no writer, and reads no environment file. Head stays `014` with 14 migrations, 18 tables,
  and 12 writers.
- [x] **The Phase 61 review now feeds a concrete source/evidence request plan** — ten prioritized
  requests (inventory export by SKU/location, item/SKU master, adjustment history with reason codes,
  cycle/physical count results, receiving and putaway records, stockout/fulfilment exception data,
  SOP and process documentation, a system-of-record and data-export map, the location/bin naming
  model, and the target metric/baseline/deadline statement). Each carries purpose, Intake Taxonomy V0
  categories, the downstream deliverable it supports, priority, expected evidence type, AI/AgentNet
  and capsule readiness, and its internal_test-only safety posture.
- [x] **Source ingestion is the recommended Phase 63 path, and evidence writing follows it.**
  `evidence_references` asserts `evidence_status`, `reliability`, and characterization that
  presuppose a registered source, and the Phase 23 boundary derives evidence requests *from* an
  ingested packet. **Evidence and source collection precede analysis, report drafting, and capsule
  publication.**
- [x] **One honest gap was recorded rather than papered over.** A request that has been *made but not
  yet fulfilled* has no writable representation: `source_system_references` models exactly that
  (`source_system_access_status`: `not_requested`/`requested`/…) but has no writer and no allowlist
  pair. No writer was added; the narrowest future change is documented and deliberately not
  implemented.
- [x] **The first source-ingestion packet shape is prepared, not executed** — metadata only, with the
  packet hash and location reference sourced from outside the repository, exactly as the Phase 60
  note body was. No fixture, example, or sample packet entered source control.
- [ ] **Next (Phase 63): create the first internal_test source ingestion record** through the
  unchanged Phase 24 writer — `source_ingestion_records` / `create_source_ingestion_record`, anchored
  on the stored `internal_test_001` engagement — **if the inspected writer contract supports it**,
  meaning a real internal_test artifact exists at write time. If none does, defer rather than
  fabricate a packet reference. Report drafting and capsule publication remain unauthorized, and
  **future real-client intake forms should lead to this same evidence request structure.**

**The First Internal Test Source Ingestion Record (Phase 63 — one production application record; no
Client record, no additional Engagement, no intake/review record, no evidence reference, no
report/capsule record, no writer enabled):**

- [x] **One source ingestion record was created** in production — `ing_4fb70519cbf84401`,
  registering the R8 system-of-record and data-export map through the unchanged Phase 24
  `source_ingestion_records` writer. Head stays `014` with 18 tables and 12 writers; no writer,
  model, or allowlist pair was added.
- [x] **R8 went first, as Phase 62 ranked it.** The system-of-record and data-export map determines
  whether R1–R7 are fulfillable at all, so registering it first lets the remaining requests be
  scoped against named systems and enumerated exports rather than assumptions.
- [x] **Phase 62's precondition was honoured rather than worked around.** No internal_test artifact
  existed when the phase began, so a durable R8 artifact was created **outside the repository**
  first; only then was its metadata registered. The operator utility refuses a missing artifact, any
  path inside the repository working tree, and any path other than the approved artifact.
- [x] **Only metadata was persisted.** Packet reference, schema name/version, source type, a
  **logical** `internal-test-artifact://` location reference, and a SHA-256 hash. The artifact body
  was never decoded, printed, committed, or stored in the database, and no filesystem path reached
  the row. The writer independently refuses payload- and secret-named draft attributes.
- [x] **No evidence reference was created.** `evidence_references` assert `evidence_status` and
  `reliability`, which presuppose a registered source, so they still come **after** source
  ingestion. Report drafting, capsule candidacy, and publication remain unauthorized.
- [x] **Verified before and after.** The read-only verifier reported
  `verified_safe_no_remediation_required` both times (head `014`, 212 governed columns
  deterministic, `data_write_made=False`); the runtime gate reported required grants only, no excess
  grants, and `app_table_read_made=False`.
- [ ] **Next: R1–R7 evidence collection** against the systems and exports the R8 map names, then
  evidence normalization and `evidence_references` as a separately approved phase. Any further
  production record remains separately approved.

**The R1–R7 Source Artifact Collection Plan (Phase 64 — planning-only; no production write, no
production record, no artifact body, no migration, no writer, no allowlist pair):**

- [x] **Phase 64 creates no production record** and no artifact body. It opens no connection, issues
  no SQL, invokes no writer, and reads no environment file. Head stays `014` with 14 migrations, 18
  tables, and 12 writers.
- [x] **Phase 63 registered R8; Phase 64 defines the R1–R7 artifact collection.** Each of the seven
  requests now carries an artifact type, minimum expected fields or document sections, an external
  filename under the approved out-of-repo directory, a logical `internal-test-artifact://phase65/…`
  location reference, a `packet_reference_id`, schema name and version, source type, a SHA-256 hash
  requirement, taxonomy categories, the downstream deliverable, and its future `evidence_reference`
  implications.
- [x] **The registered R8 map vindicated the Phase 62 ordering argument.** Read as a work-list it
  records **R2 as the only unblocked request**, R1 as blocked on the unconfirmed location model, and
  R3–R7 as uncertain or partial — so the map really did determine what is fulfillable.
- [x] **Collection and attribution were separated.** Registering an artifact asserts only that it
  exists, so R1–R7 may be collected while R8 stays `needs_review`. R8's provisional authority rule
  blocks *attribution* — no reliability may be asserted — which is why the next phase is source
  ingestion and not evidence.
- [x] **Artifact bodies stay outside the repository** and out of the database; source ingestion
  persists metadata only. **No example rows were committed** — field and document-section names
  appear, but no SKU values, quantities, location identifiers, or sample export rows.
- [x] **Next (Phase 65): create the external artifact(s) and register `source_ingestion_records`,
  not `evidence_references` yet** — recommended batch R2 then R1, since R2 is unblocked and R1 is
  uninterpretable without the item master, with R1's location dimension registered as explicitly
  provisional. **Capsule publication remains unauthorized despite the live AgentNet resolver**, and
  any further production record remains separately approved.

**The R2 and R1 Internal Test Source Ingestion Records (Phase 65 — two production application
records; no evidence reference, no report, no capsule, no migration, no writer, no allowlist pair):**

- [x] **Two `source_ingestion_records` rows were created: R2 first, then R1**, both through the
  unchanged Phase 24 writer under the stored `internal_test_001` engagement anchor
  (client `99999`, owner `peak_internal_admin`, scope `internal_peak_only`). Head stays `014` with
  14 migrations, 18 tables, and 12 writers.
- [x] **R2 was registered first** because the Phase 63 R8 map records it as the only unblocked
  request and because it is the interpretive key for R1 — R1's item identifiers cannot be assessed
  for duplication or unit-of-measure consistency without the item master.
- [x] **R1's location dimension is registered as explicitly provisional.** Its provenance notes
  record that the R8 location/bin model is unconfirmed, that future evidence must carry degraded
  reliability for location-attributed claims while SKU-level claims are not similarly limited, and
  that R9 (the location/bin naming model) is the unblocker.
- [x] **Artifact bodies live outside the repository** and never entered the database. Only
  metadata was persisted — packet reference, schema name and version, source type, a logical
  `internal-test-artifact://phase65/…` location reference, and a SHA-256 hash. No artifact body was
  printed, committed, or stored; no fixture, example, or sample packet was committed.
- [x] **No `evidence_reference` was created**, and no report, review packet, capsule candidate, or
  client-facing output. No Client record, no additional Engagement, no intake note, no review
  record. No `UPDATE`, `DELETE`, manual SQL, cleanup path, app scan, or app row count.
- [x] **Next: R9 (the location/bin naming model), then the remaining R3–R7**, which stay deferred
  behind their unresolved R8 blockers. `evidence_references` still come after source ingestion and
  after R8 review, as a separately approved phase. **AgentNet resolver publication remains
  unauthorized** despite the live public resolver, and any further production record remains
  separately approved.

**The Internal Test Source Ingestion Review Decision (Phase 66 — one production application record;
no evidence reference, no source record, no report, no capsule, no migration, no writer, no
allowlist pair):**

- [x] **One `review_records` row was created** (`rev_bf7f18a13d8f461c`), recording the internal
  review decision on the
  Phase 65 **R2** source ingestion record (`ing_884c94df03c34908`), through the unchanged Phase 22
  review writer under the stored `internal_test_001` anchor. Head stays `014` with 14 migrations,
  18 tables, and 12 writers.
- [x] **No field was overloaded and no writer was added.** The review writer already separates the
  **authorization anchor** (`request.subject`, required to be the engagement) from the **reviewed
  target** (`subject_record_id` / `subject_record_type`, stored as `target_id`), so
  `source_ingestion_record` is an honest `subject_record_type` — the same shape Phase 61 used for
  the intake note.
- [x] **The decision is `approve_internal`, non-authoritative**, landing on `approved_internal`
  with output still `draft`. It authorizes exactly one narrow next step: a **future
  `evidence_reference` about item-master source availability and data readiness**.
- [x] **It authorizes nothing wider, and says so on the row.** No inventory accuracy conclusion
  (R2 describes an item master, not measured quantity); **R1 stays provisional** on its unconfirmed
  location model; **R8 stays provisional** (`needs_review` / `draft` / `authoritative=false`) with
  its authority precedence rule unconfirmed; **R3–R7 stay deferred**; and report drafting, capsule
  candidacy, client-facing output, and **AgentNet resolver publication remain unauthorized**.
- [x] **The artifact body was never read.** The Phase 66 operator opens no file and computes no
  hash; findings are sanitized structural counts, posture flags, and named gaps — no artifact text,
  field values, item/SKU values, quantities, or location identifiers.
- [x] **Next: the first `evidence_reference`**, scoped to item-master source availability and data
  readiness only, as a separately approved phase. R9 and R3–R7 remain the outstanding collection
  work. Any further production record remains separately approved.

**The First Internal Test Evidence Reference (Phase 67 — one production application record; no
source record, no review record, no report, no capsule, no migration, no writer, no allowlist
pair):**

- [x] **One `evidence_references` row was created** (`evid_56437d9b9c764560`) for the Phase
  66-approved **R2** source
  ingestion record (`ing_884c94df03c34908`), supported by review record `rev_bf7f18a13d8f461c`,
  through the unchanged Phase 21 evidence writer under the stored `internal_test_001` anchor. Head
  stays `014` with 14 migrations, 18 tables, and 12 writers.
- [x] **No field was overloaded and no writer was added.** `source_reference_id` carries the
  registered packet reference, `source_location` a *logical* in-Peak locator for the R2 record, and
  `evidence_type` / `source_type` are `document` — the artifact is a field-level export
  *description*, not an export of rows, so `system_export` would have been the overload. Three
  contract limits are stated rather than worked around: no typed related-object column (the
  supporting review is named in text), `evidence_status` is not caller-settable (the row takes the
  `collected` default), and `draft.reasons` is not persisted (the limits live in
  `normalized_summary` / `observed_condition`).
- [x] **The evidence scope is item-master source availability and data readiness only.** The R2
  artifact is available and registered, and its field-level structure is sufficient to proceed to a
  future item-master **data-readiness review**. Unit-of-measure posture, item-status posture, and
  the duplicate/normalization risks remain recorded open questions.
- [x] **No inventory accuracy conclusion was made, and the row says so.** R2 describes an item
  master, not measured quantity. The evidence does not rely on **R1** location claims (provisional
  pending **R9**) and does not treat **R8** as authoritative (`needs_review` / `draft` /
  `authoritative=false`); **R3–R7 stay deferred**; and report drafting, capsule candidacy,
  client-facing output, and **AgentNet resolver publication remain unauthorized**.
- [x] **The posture is structural, not asserted.** `evidence_references` has **no `authoritative`
  column**, the writer refuses any draft claiming `authoritative`, `client_facing_approved`, or
  `capsule_candidate_ready`, and it server-stamps `review_status='needs_review'` and
  `output_status='draft'` itself.
- [x] **The artifact body was never read.** The Phase 67 operator opens no file and computes no
  hash; the stored text is sanitized structural counts, posture flags, named gaps, and record ids —
  no artifact text, field values, item/SKU values, quantities, or location identifiers.
- [x] **Next: an item-master data-readiness review of R2**, as a separately approved phase. R9
  (which unblocks R1's location dimension), R8 review, and R3–R7 remain the outstanding collection
  and review work. Any further production record remains separately approved.

**The R2 Evidence Reference Review Decision (Phase 68 — one production application record; no
evidence reference, no source record, no report, no capsule, no migration, no writer, no allowlist
pair):**

- [x] **One `review_records` row was created** (`rev_de2b6e73f6c94c67`), recording the internal
  review decision on the
  Phase 67 **R2 evidence reference** (`evid_56437d9b9c764560`), through the unchanged Phase 22
  review writer under the stored `internal_test_001` anchor. Head stays `014` with 14 migrations,
  18 tables, and 12 writers.
- [x] **No field was overloaded and no writer was added.** The review writer separates the
  **authorization anchor** (`request.subject`, required to be the engagement) from the **reviewed
  target** (`subject_record_id` / `subject_record_type`, stored as `target_id`), and persists
  `draft.reasons`, so the limits are stored as findings.
  `subject_record_type='evidence_reference'` follows the Phase 61 / Phase 66 convention of naming
  the reviewed **table**; the older fixtures' `normalized_evidence_record` names the Phase 14
  *in-memory* output, which is never stored.
- [x] **The decision is `approve_internal`, non-authoritative**, landing on `approved_internal`
  with output still `draft`. It authorizes exactly one narrow next step: a **future internal
  assessment finding about item-master source availability and data readiness**.
- [x] **The evidence stays low confidence and non-authoritative**, and **the reviewed evidence row
  is not modified** — a review records a decision about a target, and the writer has no `UPDATE`
  path.
- [x] **It authorizes nothing wider, and says so on the row.** **No inventory accuracy
  conclusion**; no SKU or location quantity reliability claim; **R1 location claims are not
  validated** (provisional pending **R9**); **R8 authority precedence is not confirmed**
  (`needs_review` / `draft` / `authoritative=false`); **R3–R7 stay deferred**; and report drafting,
  capsule publication, client-facing output, and **AgentNet resolver publication remain
  unauthorized**.
- [x] **The artifact body was never read.** The Phase 68 operator opens no file and computes no
  hash; findings are sanitized structural counts, posture flags, and named gaps — no artifact text,
  field values, item/SKU values, quantities, or location identifiers.
- [x] **Next: Phase 69 collected R9**, the location/bin naming model. A future internal assessment
  finding, R8 review, and R3–R7 remain the other outstanding work. Any further production record
  remains separately approved.

**The R9 Location/Bin Naming Model Source Ingestion (Phase 69 — one production application record;
no evidence reference, no review record, no report, no capsule, no migration, no writer, no
allowlist pair):**

- [x] **One R9 source ingestion record was created** (`ing_64b2e2648ac1402b`), registering the
  internal test **R9 location/bin naming model** artifact through the unchanged Phase 24 source
  ingestion writer under the stored `internal_test_001` / `99999` / `internal_peak_only` anchor.
  Head stays `014` with 14 migrations, 18 tables, and 12 writers.
- [x] **R9 is a location/bin naming model artifact** — a structural description of location
  hierarchy fields (site / warehouse / zone / aisle / rack / bin), bin and location naming fields,
  location type and status fields, inventory availability treatment, and the virtual / staging /
  hold / damaged / quarantine / unavailable-inventory concepts. Ownership is stated cautiously as
  ERP / WMS / manual / **unknown**, as open questions rather than claims.
- [x] **The artifact body lives outside the repository** and **only metadata, the hash, and a
  logical location reference were persisted** —
  `internal-test-artifact://phase69/r9-location-bin-naming-model-v1` plus the `packet_hash`. No
  artifact body, filesystem path, export row, item/SKU value, quantity, or location identifier
  reached the database or this repository.
- [x] **R9 was collected to unblock a future R1 location-dimension review.** Phase 65 registered R1
  with its location dimension explicitly provisional; R9 is the model that makes that dimension
  reviewable.
- [x] **R9 does not validate inventory quantities**, is **not** an inventory accuracy finding, and
  **does not make R1 evidence-ready by itself** — R1's location dimension **remains provisional**.
- [x] **R9 must be reviewed before use in evidence references.** It landed `needs_review` /
  `draft` / `active`, `authoritative=false`, `client_facing_approved=false`,
  `capsule_candidate_ready=false`.
- [x] **Nothing wider was created or authorized.** **No evidence reference**, **no review record**,
  no report, no capsule, no client-facing output, and **no AgentNet publication**. **R8 remains
  provisional** (`needs_review` / `draft` / `authoritative=false`, precedence unconfirmed),
  **R3–R7 remain deferred**, and the AgentNet resolver is live but **publication remains gated and
  unauthorized**.
- [x] **Next: Phase 70 reviewed R9.** A possible R1 location-dimension review, a future internal
  assessment finding, R8 review, and R3–R7 remain outstanding. Any further production record
  remains separately approved.

**The R9 Source Ingestion Review Decision (Phase 70 — one production application record; no
evidence reference, no source record, no report, no capsule, no migration, no writer, no allowlist
pair):**

- [x] **One `review_records` row was created** (`rev_3ecc0891f4fe48ce`), recording the internal review
  decision on the Phase 69 **R9 source ingestion record** (`ing_64b2e2648ac1402b`, the location/bin
  naming model), through the unchanged Phase 22 review writer under the stored `internal_test_001`
  anchor. Head stays `014` with 14 migrations, 18 tables, and 12 writers.
- [x] **No field was overloaded and no writer was added.** `subject_record_type =
  'source_ingestion_record'` is the same value **Phase 66** used for the R2 source-ingestion review;
  `source_reference_id` carries the reviewed packet reference and `reasons` carries the limits as
  findings.
- [x] **The decision is `approve_internal`, non-authoritative**, landing on `approved_internal` with
  output still `draft`. It authorizes exactly one narrow next step: **future evidence work about R1
  location-dimension readiness** — and nothing wider.
- [x] **Registration integrity confirmed:** the reviewed artifact's hash still matches the
  `packet_hash` registered in Phase 69.
- [x] **The central recorded limit: R9 is a question set, not an answered model.** All 6 hierarchy
  levels and all 3 type/status fields are presence-unknown, and roughly 53 structural questions are
  posed without any being answered. R9 defines what must be measured rather than reporting what is
  true, so it **cannot by itself lift R1's provisional location marking**, and it gives no basis for
  choosing among the 4 candidate ownership postures.
- [x] **It authorizes nothing wider, and says so on the row.** **No `evidence_reference` was
  created**; **no inventory quantity is validated** (R9 holds no instance data); **R1's location
  dimension remains provisional**; **R8 authority precedence is not resolved**; **R5 WMS scope is
  not resolved**; **R3–R7 stay deferred**; and report drafting, capsule publication, client-facing
  output, and **AgentNet resolver publication remain unauthorized**.
- [x] **The reviewed R9 record was not modified** — a review records a decision about a target, and
  the writer has no `UPDATE` path. **No artifact body was read**: the operator opens no file at all.
- [x] **Next: Phase 71 chose the planning step** over a narrow R9 evidence reference.

**The R1/R9 Evidence-Readiness Plan (Phase 71 — planning-only; no production access and no
production record of any kind):**

- [x] **Planning-only.** No production database was contacted, no environment file sourced, no
  writer invoked, and **no production record created** — no `evidence_reference`, no
  `review_record`, no `source_ingestion_record`, no report, no capsule, no client-facing output, and
  no AgentNet or resolver publication. No migration, model, writer, allowlist pair, or operator
  utility was added.
- [x] **Core finding:** R1 cannot yet support a location-dimension `evidence_reference` because the
  collected R9 artifact **defines the questions that must be answered but does not answer them**.
  The next operational need is a **measured location-model answer set**, not another evidence
  reference.
- [x] **The gap was made concrete.** R1 declares 10 fields of which exactly **two** carry the
  location dimension — one required identifier and one *optional* level marker, both marked
  provisional in the artifact — while R9 describes a **six-level** hierarchy. The optional level
  marker is a first-order readability problem, and because location is a **grain key**, ambiguity
  there is ambiguity in the grain itself.
- [x] **15 required measured answers** were listed as the gate before any R1/R9 evidence reference,
  including which hierarchy levels exist, what the location identifier actually represents, which
  system owns the model, and — stated in advance — **both** the threshold for "readable" and the
  threshold for "not reliable enough".
- [x] **R1 remains provisional**; **R9 is reviewed but non-authoritative and remains a question set,
  not an answered model**; **R8 and R5 remain unresolved**; **R3–R7 remain deferred**. **No
  inventory accuracy conclusion**, no quantity reliability conclusion, no report drafting, no
  capsule publication, no client-facing output, and no AgentNet resolver publication is made or
  authorized.
- [x] **The narrow R9 evidence reference is deferred, not foreclosed.** It would mostly establish
  that Peak holds a reviewed question set, which does not materially advance R1 location readiness;
  it stays available if later wanted for audit completeness.
- [x] **Recommended next: Phase 72 — R10 Location Model Answer Set Source Ingestion**, then Phase
  73 review, Phase 74 R1/R9/R10 evidence reference, Phase 75 review. Phase 72 has now run.

**The R10 Location Model Answer Set Source Ingestion (Phase 72 — one production application record;
no evidence reference, no review record, no report, no capsule, no migration, no writer, no
allowlist pair):**

- [x] **One R10 source ingestion record was created** (`ing_b26d137a0a334ee9`), registering the
  internal test **R10 measured location model answer set** through the unchanged Phase 24 source
  ingestion writer under the stored `internal_test_001` / `99999` / `internal_peak_only` anchor.
  Head stays `014` with 14 migrations, 18 tables, and 12 writers.
- [x] **R10 answers R9's question set.** All **15** Phase 71 checklist items carry an explicit
  answer state from a fixed vocabulary (`answered_yes`, `answered_no`, `partial`, `unknown`,
  `not_present`, `not_measured`, `blocked_by_r8`, `blocked_by_r5`, `requires_follow_up`).
- [x] **The unfavourable answers were kept.** None of the 15 items was dropped, merged, or softened,
  and **11 of 15 resolve to a negative, unknown, or blocked state**. The only two `answered_yes`
  items are the two threshold *definitions*, not favourable findings about the data.
- [x] **The measurement basis is stated honestly:** measured against the registered R1, R2, and R9
  artifact descriptions only — **no live ERP, WMS, production, or client system exists** to measure
  against in this internal_test engagement, so artifact-level assertions were not upgraded into
  measured facts.
- [x] **Headline finding: R1's location dimension is not currently readable**, and on the
  thresholds fixed in advance it is **not reliable enough** for location-attributed evidence. Two
  items are outright `answered_no` — no field-to-level mapping exists, and R1 quantities are not
  time-aligned with a location model that has no effective-dating.
- [x] **The artifact body lives outside the repository** and **only metadata, the hash, and a
  logical location reference were persisted** — no location identifiers, bin codes, aisle, rack,
  warehouse or site names, item values, quantities, or row-like data reached the database or repo.
- [x] **Nothing wider was created or authorized.** **No evidence reference**, **no review record**,
  no report, no capsule, no client-facing output, and **no AgentNet publication**. **R10 remains
  `needs_review` / `draft` / `authoritative=false` and must be reviewed before evidence use**; **R1
  remains provisional**; **R8 precedence and R5 WMS scope remain unresolved** (recorded as
  `blocked_by_r8` / `blocked_by_r5`); **R3–R7 remain deferred**; the resolver is live but
  **publication remains gated**.
- [x] **Next: Phase 73 reviewed R10 and recorded the finding** — see below.

**R10 Review and the Location-Readiness Evidence (Phase 73 — two production application records;
no source ingestion record, no report, no capsule, no migration, no writer, no allowlist pair, and
no new operator or harness):**

- [x] **One `review_records` row** (`rev_9b6b0a67bae54a51`) reviewing the R10 source ingestion
  (`ing_b26d137a0a334ee9`) through the unchanged Phase 22 writer: `approve_internal`,
  `authoritative=false`, approved **only** for evidence about R1 location-dimension data readiness.
  It confirmed R10's registration integrity and **accepts R10's unfavourable answer set as a valid
  data-readiness input** — 11 of 15 items negative, unknown, or blocked — while recording that the
  two `answered_yes` items are threshold *definitions*, not favourable data findings.
- [x] **One `evidence_references` row** (`evid_f26c5f8fc0aa44d4`) through the unchanged Phase 21
  writer, carrying the first **controlled negative finding** in the chain: **under thresholds fixed
  in advance, R1's location dimension is not currently readable and not reliable enough to carry
  location-attributed evidence** (0 of 6 readable conditions met; 5 not-reliable-enough conditions
  met). `document` / `document`, reliability `low`, `needs_review` / `draft`, non-authoritative.
- [x] **Write 2 was gated on write 1**, and both were newly created rather than replayed.
- [x] **No new infrastructure.** Both writes used existing writers via a temporary executor held
  outside the repository and never committed — no persistent operator and no phase-specific harness,
  since neither was demonstrably needed.
- [x] **This is a data-readiness and reliability finding, not an inventory accuracy finding.** **No
  inventory accuracy conclusion** was made; **R1 remains provisional**; **R8 and R5 remain
  unresolved** (dependent R10 items stay `blocked_by_r8` / `blocked_by_r5`); **R3–R7 remain
  deferred**; and no report, capsule, client-facing output, or AgentNet publication was created or
  authorized.
- [x] **Next: Phase 74 took the minimal internal assessment step** — see below.

**Location-Readiness Evidence Review and the Minimal Internal Assessment Outline (Phase 74 — two
production application records; no source ingestion record, no evidence reference, no capsule, no
client-facing output, no migration, no writer, no allowlist pair, and no new operator or harness):**

- [x] **One `review_records` row** (`rev_d94d4711ac12420b`) reviewing the Phase 73 location-readiness
  evidence reference (`evid_f26c5f8fc0aa44d4`) through the unchanged Phase 22 writer:
  `approve_internal`, `authoritative=false`, approved **only** for one minimal internal assessment
  finding / report outline. Its `reasons` record the finding and every limit, in `details_json` —
  the Phase 68 shape, with no field overloaded.
- [x] **One `internal_assessment_report_drafts` row** (`iard_50814a78a44243c2`) through the unchanged
  Phase 37 writer, planned by the DB-free Phase 36 planner: five sections
  (`evidence_summary`, `operational_findings`, `system_data_readiness`, `evidence_gaps`,
  `next_steps_internal`), one finding candidate, zero recommendation candidates, zero open gaps.
  `output_status=plan_persisted` — a persisted **outline**, never report prose — `audience=internal`,
  `needs_review` / `draft`, every approval/verification/publication/execution flag `false`.
- [x] **`inventory_risk_areas` was deliberately excluded** so a data-readiness result cannot be read
  as an inventory-risk conclusion. The single finding candidate is honestly **blocked**
  (`blocked_no_review_support`): this chain has `review_records`, not `review_bundle_records`, and
  the Phase 74 review record was **not** smuggled into `review_bundle_record_ids` to clear it.
- [x] **The assessment finding:** **R1's location dimension is not currently readable or reliable
  enough to carry location-attributed evidence under the thresholds fixed in advance.**
- [x] **Write 2 was gated on write 1**, and both were newly created rather than replayed.
- [x] **No new infrastructure.** Both writes used existing writers via a temporary executor held
  outside the repository and never committed — no persistent operator and no phase-specific harness.
- [x] **This is a data-readiness and reliability finding, not an inventory accuracy finding**, and
  **downstream reports must not reframe it as one**. **No inventory accuracy conclusion** was made;
  **R1 remains provisional**; **R8 and R5 remain unresolved**; **R3–R7 remain deferred**; and no
  report, capsule, client-facing output, or AgentNet publication was created or authorized.
- [x] **Next: Phase 75 examined "give the finding candidate real review support" and declined it** —
  see below.

**Location Assessment Review Support (Phase 75 — no production writes; preferred path declined on
honesty grounds; no migration, writer, allowlist pair, schema, operator, or harness):**

- [x] **The preferred path was mechanically available and was not taken.** The Phase 30
  `review_bundle_records` writer would have accepted a bundle for this engagement, and its id would
  have moved `fnd_000` from `blocked_no_review_support` to `internal_draft_candidate`.
- [x] **A review bundle records that review has *not* happened.** It is the persistence counterpart
  to the Phase 29 packet review boundary: subjects gathered and queued **for** a human reviewer,
  readiness `ready_for_human_review`, carrying Phase 29's own warning that "ready for human review
  does not mean approved". Phase 30 hard-stamps `needs_review` / `draft` / `approval_allowed=false`.
  Clearing a "no review support" block with it would assert the opposite of what the block asks for.
- [x] **It cannot carry the support that exists.** `ReviewBundleDraft` has no review-record field and
  `review_bundle_records` has no such column — the model states `details_json` holds safe references
  "never ... a final review decision". `rev_d94d4711ac12420b` has no honest home in it, and forcing
  it into `subject_refs` would be the exact mirror of the Phase 74 misuse already refused.
- [x] **No production rows were created**, and **no substitute `review_records` row** was created to
  appear to progress. No source ingestion, evidence reference, Client, Engagement, intake, capsule,
  report, client-facing output, or AgentNet publication.
- [x] **`blocked_no_review_support` is a false negative from a vocabulary gap, not a governance
  block.** The corroboration exists in this chain; it is typed `review_records`, which the Phase 36
  planner has no category for.
- [x] **The finding is unchanged and stays narrow**: R1's location dimension is not currently
  readable or reliable enough for location-attributed evidence — **data-readiness / reliability
  only, never inventory accuracy**. R1 provisional; R8 and R5 unresolved; R3–R7 deferred; report
  finalization, capsule publication, and AgentNet publication unauthorized.
- [x] **Next: Phase 76 went after R8 precedence and R5 WMS scope** — see below.

**R8 Authority Review and R5 WMS Scope Clarification (Phase 76 — two production application records;
no evidence reference, no report draft, no review bundle, no capsule, no client-facing output, no
migration, no writer, no allowlist pair, and no new operator or harness):**

- [x] **One `review_records` row** (`rev_1d9696e9218b4e35`) reviewing the R8 source ingestion
  (`ing_4fb70519cbf84401`) through the unchanged Phase 22 writer: `approve_internal`,
  `authoritative=false`, approved as a **source-map and authority-precedence framing artifact** only.
- [x] **The review does not confirm authority precedence, because R8 does not.** R8's own
  `authority_precedence_rule` carries status `provisional_unconfirmed` with **2 items requiring
  confirmation first**. R8 maps 7 requested exports (2 `expected`, 4 `uncertain`, 1 `partial`);
  **5 of 7 carry a recorded blocker, only 1 carries none**, and 4 open questions stay open.
- [x] **Registration integrity was deliberately not re-verified** — no `packet_hash` is committed to
  the repo, and reading the stored row would exceed this phase's permitted lookups. The review claims
  no integrity confirmation.
- [x] **One `source_ingestion_records` row** (`ing_f7a4cc20f1f148c7`) through the unchanged Phase 24
  writer, registering the **R5 WMS scope clarification** — `draft` / `needs_review` / `active`,
  `authoritative=false`, body outside the repo, only metadata and the SHA-256 persisted.
- [x] **This is not the Phase 64 "R5 receiving and putaway" export**, which remains uncollected under
  its own packet reference. It clarifies the WMS-scope blocker R8 records against R5.
- [x] **15 scope items, zero favourable**: 0 `answered_yes`, 1 `answered_no`, 3 `unknown`,
  9 `not_measured`, 2 `blocked_by_r8`. The nine unmeasured items are unmeasured **by necessity** —
  this engagement has no live warehouse management, ERP, production, or client system, and the
  artifact asserts no system landscape.
- [x] **Clarified, not resolved.** Both blockers moved from prose into enumerated, checkable
  structure; **no answer to either changed. R8 precedence and R5 WMS scope both remain unresolved.**
- [x] **No new infrastructure.** Existing writers via a temporary executor outside the repository.
- [x] **No inventory accuracy conclusion.** **R1 remains provisional**; the Phase 73 negative finding
  stands and is **data-readiness / reliability only, never inventory accuracy**; **R3–R7 remain
  deferred**; the Phase 74 outline is unmodified and `fnd_000` still `blocked_no_review_support`; and
  no report, capsule, client-facing output, or AgentNet publication was created or authorized.
- [ ] **Next:** review the R5 clarification (it is `needs_review`), then address **R8's 2 named
  confirmation prerequisites** — the only route to lifting `blocked_by_r8` on anything — and
  establish whether a warehouse management system exists in the scenario at all. Separately approved
  either way. **Phase 77 prepared this; it did not execute it** — see below.

**Parallel Prep for the R5 Clarification Review and R8 Prerequisites (Phase 77 — no production
record, no production access, no writer invoked, no migration, no allowlist pair, and no new operator
or harness):**

- [x] **Phase 77 creates no production record.** It opens no connection, issues no SQL, sources no
  environment file, invokes no writer, and reads no artifact body. Three read-only workstreams ran in
  parallel; **analysis was parallelized, production writes were not**, because none were performed.
- [x] **The R5 WMS scope clarification is ready for internal review.** `ing_f7a4cc20f1f148c7` is
  already `draft` / `needs_review` / `active`, the engagement anchor is unchanged, and reviewing a
  `source_ingestion_record` target has precedent in Phases 66, 70, and 73. Readiness does **not**
  depend on R8 precedence, because reviewing an *enumeration of a blocker* is not approving *answers*.
- [x] **Recommended Phase 78 posture, fixed in advance:** exactly one `review_records` row through the
  unchanged Phase 22 writer — `approve_internal`, `authoritative=false`, `approved_internal` /
  `draft` / `active`, both publication flags false — approving a **scope-blocker enumeration only**.
  `needs_more_info` would be incoherent (the missing information is what the artifact truthfully
  records as unavailable) and `reject` would be wrong (no defect, no invented system landscape).
- [x] **`authoritative=false` is a reviewer decision, not a writer constraint.** The writer's
  `approve_internal` validation never inspects `authoritative` at all; declining it must be recorded
  as a choice.
- [x] **The proposed packet was incomplete as first drafted.** An adversarial QA pass caught three
  omissions that would each deny **before any connection opens** — `subject.stored_authorization_scope`,
  the `draft.owner_id` / `client_id` / `engagement_id` triple, and `draft.requested_by` /
  `reviewer_role` — plus an idempotency rehearsal that would have proved less than claimed, since the
  payload fingerprint excludes `source_phase`. All corrected in the Phase 77 doc.
- [x] **The content of R8's two confirmation prerequisites is not recorded anywhere in this repo** —
  only the shape is known (an array of length 2, a count already on record in Phase 76), and **the
  two strings themselves were never read**. Phase 77 reconstructs their likely content by inference
  from downstream blocked items and **labels it as inference**. This makes the Phase 76 next step
  unactionable from the repository alone and is the largest remaining unknown.
- [x] **Neither prerequisite depends on the Phase 64 R5 export or on the Phase 76 clarification** —
  the dependency runs the other way: prerequisites → R5 WMS scope → the Phase 64 export.
- [x] **No new infrastructure is needed for the follow-up artifact** — the unchanged Phase 24
  ingestion writer plus the Phase 22 review writer suffice. Neither writer has an `UPDATE` path, so
  any confirmation must land as a *new* ingestion plus a *new* review, never as an amendment to R8.
- [x] **R3–R7 all remain uncollected and deferred.** R4 is the only item inside R3–R7 that Phase 62
  marks *required* rather than *important* — a **priority marking in the original request plan**, not
  a dependency of the current track. **R4 is conditionally required / scope-dependent**: it becomes
  required only if a refreshed assessment's scope includes **count or variance reconciliation**, and
  must not be treated as required otherwise. For the current narrow **location-dimension
  data-readiness** track it is **not** required, and pulling it in would widen the finding into
  inventory accuracy, variance, or quantity correctness — which this chain does not claim.
  *(An earlier Phase 77 revision overstated R4 as automatically required; corrected in Phase 78.)*
- [x] **The dependency chain is a scoping and attribution order, not a collection gate.** Phase 64 is
  explicit that R1–R7 may be collected while R8 stays `needs_review`; precedence confirmation gates
  whether an export can be scoped and attributed, not whether it may be fetched. The live gate has
  drifted since Phase 64 was written: R8 has now been reviewed and attribution is still blocked, so
  the operative gate is **precedence confirmation, not R8 review**.
- [x] **A second label collision was found: R10.** Phase 62's R10 (target metric, baseline, deadline;
  *optional*, uncollected) is not Phase 71+'s R10 (location model answer set). No naming rule exists
  for it, unlike the R5 case.
- [x] **Reproducibility gap recorded:** `tools/` has no operator for Phases 73–76 and `tests/`
  validators stop at Phase 72, so those writes have no in-repo replay path. A deliberate decision to
  make, not a defect to fix silently.
- [x] **Nothing moved.** **R8 precedence and R5 WMS scope remain unresolved**, the clarification stays
  `needs_review` / `draft`, the **Phase 64 R5 export stays uncollected**, **R1 remains provisional**,
  **R3–R7 stay deferred**, the Phase 74 outline is unmodified with `fnd_000` still
  `blocked_no_review_support`, **no inventory accuracy conclusion** was made, and report
  finalization, capsule publication, client-facing output, and AgentNet publication remain
  unauthorized.
- [x] **Next (Phase 78):** review the R5 WMS scope clarification as one bounded row, and obtain a
  permitted read of R8's two prerequisites. **Done — see below.**

**The R5 WMS Scope Clarification Review and the R4 Scope Correction (Phase 78 — one production
application record; no source ingestion, evidence reference, report draft, review bundle, capsule,
client-facing output, migration, allowlist pair, or new operator or harness):**

- [x] **One `review_records` row** (`rev_e283136f679a46dd`) reviewing the R5 WMS scope clarification
  source ingestion (`ing_f7a4cc20f1f148c7`) through the unchanged Phase 22 writer:
  `approve_internal`, `authoritative=false`, `approved_internal` / `draft` / `active`, both
  publication flags false. Approved as a **scope-blocker enumeration only**.
- [x] **`authoritative=false` was a reviewer decision, not a writer constraint** — the writer's
  `approve_internal` validation never inspects the field. It was declined because the artifact
  resolves nothing: **0 of 15 items favourable**.
- [x] **Registration integrity is not claimed.** The review writer has no `packet_hash` path, so the
  artifact is reviewed **as registered**, with no hash or integrity confirmation.
- [x] **Idempotency was rehearsed correctly**, off-production against temporary SQLite: varying
  `reasons` (fingerprinted) produced `idempotency_conflict`; varying only `source_phase` produced
  `idempotent_replay`, because `_payload_fingerprint` excludes it — the Phase 77 QA point
  demonstrated rather than asserted. Production returned `created`; an identical replay returned
  `idempotent_replay` with `database_write_made=false`, confirming exactly one row.
- [x] **R8's two prerequisites are now known, and the Phase 77 inference was wrong.** Read from the
  local artifact after a pattern safety screen and recorded as **sanitized concepts only**:
  **quantitative findings**, and **an evidence reliability rating**. Phase 77 had inferred a
  system-of-record designation and a tie-break rule — neither is what the artifact records. The rule
  already states a direction, so what is missing is its **confirmation, not its content**.
- [x] **This makes R8 confirmation a measurement task, not a documentation task** — a material
  re-scoping of the critical path. It also names the exact trigger that would pull R4 into scope.
- [x] **R4 corrected to conditionally required / scope-dependent.** It is the only Phase 62-*required*
  item inside R3–R7 (a priority marking, not a dependency), and is required only if a refreshed
  assessment's scope includes **count or variance reconciliation**. The current location-dimension
  data-readiness track is not so scoped.
- [x] **No new infrastructure.** Existing writers via a temporary scratchpad executor outside the
  repository. **No artifact body** printed, committed, or stored; **no production row read** to obtain
  the prerequisites; **no `UPDATE`/`DELETE`/manual SQL/cleanup**; no app table scanned or counted
  beyond the writer's own lookups.
- [x] **No inventory accuracy conclusion.** **R1 remains provisional**; the location finding stays
  **data-readiness and reliability only**; **R5 WMS scope remains unresolved**; **R8 authority
  precedence remains unresolved** and R8 non-authoritative; the **Phase 64 R5 export stays
  uncollected**; **R3, R4, R6, R7 stay deferred**; the Phase 74 outline is unmodified with `fnd_000`
  still `blocked_no_review_support`; and no report, capsule, client-facing output, or AgentNet
  publication was created or authorized.
- [x] **Next:** because R8's prerequisites are measurement work, establish whether this scenario can
  produce quantitative findings and an evidence reliability rating at all. **Done in Phase 79 — see
  below. It cannot.**

**The R8 Measurement Feasibility Source Ingestion (Phase 79 — one production application record; no
review record, evidence reference, report draft, review bundle, capsule, client-facing output,
migration, allowlist pair, or new operator or harness):**

- [x] **One `source_ingestion_records` row** (`ing_0d671226f2ba4760`) through the unchanged Phase 24
  writer, registering an **R8 authority-precedence measurement-feasibility assessment** —
  `draft` / `needs_review` / `active`, `authoritative=false`, body outside the repo, only metadata
  and a SHA-256 persisted (hash value not disclosed in docs).
- [x] **The answer is a clean negative.** The internal_test scenario **cannot produce** either
  prerequisite: quantitative findings and an evidence reliability rating are both
  `blocked_by_missing_measurement`.
- [x] **Why.** Every collected source records its basis as **registered artifact descriptions only**,
  with **no live system access**. The location-model answer set states outright that an artifact-level
  assertion may not be upgraded into a measured fact; R8's own readiness records its rule as **not
  machine-checkable** because no measured claim can be attributed to a system of record. A reliability
  rating rates a measurement basis, and none exists.
- [x] **This is a measurement gap, not a collection gap and not a documentation gap.** Collecting the
  remaining uncollected requests would **not** resolve it — they describe exports from a system that
  does not exist in this scenario. No sequencing or batching changes the answer.
- [x] **Nothing was fabricated.** No quantitative finding was computed or estimated; no reliability
  rating was assigned. Absence is recorded as absence.
- [x] **Absence of a measurement basis is a negative feasibility result** — not a favourable finding,
  and never to be restated as inventory accuracy.
- [x] **No new infrastructure.** Existing writer via a temporary scratchpad executor outside the
  repository. Idempotency rehearsed off-production against temporary SQLite by varying **fingerprinted
  metadata** (this writer's fingerprint excludes `reasons`/`warnings`, unlike the review writer);
  production returned `created` with exactly one row.
- [x] **Registration is collection, not review.** The row **is not evidence** and needs review.
  **R8 authority precedence remains unresolved** and R8 remains non-authoritative — recording that a
  question cannot be answered here is **not** closing it.
- [x] **Nothing else moved.** **R1 remains provisional**; the location finding stays **data-readiness
  and reliability only**; the **R5 WMS scope clarification remains a reviewed scope-blocker
  enumeration only** and R5 WMS scope is unresolved; the **Phase 64 R5 export stays uncollected**;
  **R3–R7 stay deferred** with the count/variance request **conditionally required /
  scope-dependent**; the Phase 74 outline is unmodified with `fnd_000` still
  `blocked_no_review_support`; and no report, capsule, client-facing output, or AgentNet publication
  was created or authorized.
- [x] **Next:** review the feasibility assessment and record the negative closure. **Done in Phase 80
  — see below.**

**The R8 Measurement Feasibility Review and the Scenario-Specific Closure (Phase 80 — one production
application record; no source ingestion, evidence reference, report draft, review bundle, capsule,
client-facing output, migration, allowlist pair, or new operator or harness):**

- [x] **One `review_records` row** (`rev_4208b1882d044069`) reviewing the R8 measurement-feasibility
  source ingestion (`ing_0d671226f2ba4760`) through the unchanged Phase 22 writer:
  `approve_internal`, `authoritative=false`, `approved_internal` / `draft` / `active`, both
  publication flags false. The reviewed source **remains source-only and is not evidence**.
- [x] **Scenario-specific negative closure recorded:** this internal_test scenario **cannot confirm
  R8 authority precedence**, because it cannot produce measured quantitative findings or a
  reliability rating for the underlying evidence.
- [x] **The closure is a recorded decision, not a database state change.** There is no closure
  decision in the writer's vocabulary and none was simulated. **No R8 row was modified** — the R8
  source ingestion and the earlier R8 review are untouched (no `UPDATE` path), so R8 still reads
  non-authoritative with its precedence rule unconfirmed.
- [x] **The closure is narrow.** It does **not** mean R8 precedence is false — nothing evaluated
  whether the direction is correct, and an unconfirmable claim is not a refuted one. It does **not**
  mean real client data could not confirm R8 later; the limitation belongs to *this scenario*, not to
  the question.
- [x] **Registration integrity is not claimed** — the review writer has no `packet_hash` path, so the
  Phase 79 source is evaluated **as registered**.
- [x] **No new infrastructure.** Existing writer via a temporary scratchpad executor outside the
  repository. Idempotency rehearsed off-production by varying `reasons` (fingerprinted here);
  production returned `created` with exactly one row.
- [x] **No inventory accuracy conclusion.** **R1 remains provisional**; the location finding stays
  **data-readiness and reliability only**; the **R5 WMS scope clarification remains a reviewed
  scope-blocker enumeration only**; the **Phase 64 R5 export stays uncollected**; **R3–R7 stay
  deferred** with the count/variance request **conditionally required / scope-dependent**; the Phase
  74 outline is unmodified with `fnd_000` still `blocked_no_review_support`; and no report, capsule,
  client-facing output, or AgentNet publication was created or authorized.
- [x] **Next: production-parity staging or lab database planning.** The artifact-only internal_test
  chain has reached its **measurement limit** — every remaining R8-track question needs data measured
  against a running system, which this scenario structurally cannot supply. Further collection or
  review inside the current setup would be motion without progress. Separately approved, and a change
  in kind rather than another increment. **Done in Phase 81 — see below.**

**The Production-Parity Lab MySQL Plan (Phase 81 — planning only; no production access, no database,
service, schema, user or credential created, no writer invoked, no record created, no migration run,
no new infrastructure, no branch or commit; docs only):**

- [x] **Phase 81 creates nothing.** It sources no environment file, opens no connection, contacts no
  cloud console or API, issues no SQL, invokes no writer, and creates **no row of any kind** — in
  production or anywhere else. The runtime connectivity gate was run in `--self-test` mode only.
  Head stays `014_engagement_classification` with 14 migrations, 18 tables, and 12 writers, and
  **production remains untouched**.
- [x] **Recommended environment: a separate managed MySQL service labelled `peak_lab`**, provisioned
  independently of production — *not* a second database inside the production service, which shares a
  host, admin plane, and endpoint with production and is rejected for that reason. Purpose:
  **production-parity measured development and validation**. An ephemeral local MySQL 8 container is
  an **optional** rehearsal tier for the fresh-bootstrap path that broke in Phase 46; every container
  artifact must live outside the repository, since a root `docker-compose.yml` fails `make validate`.
- [x] **"staging" is deliberately rejected as the name.** `PEAK_MANAGED_MYSQL_STAGING_DSN`,
  `make mysql-parity-staging`, and `PEAK_MANAGED_MYSQL_DISPOSABLE` already define a staging target as
  an **empty, disposable schema holding no data ever** — the opposite of a durable lab. `peak_lab`
  and the `PEAK_LAB_*` namespace have no collisions.
- [x] **Credentials mirror the production three-role split and reuse nothing from production:**
  `peak_lab_migrate` (DDL), `peak_lab_runtime` (**exactly `SELECT` + `INSERT`**, so the connectivity
  gate stays reusable unmodified and keeps its meaning), `peak_lab_readonly` (`SELECT` only). Secrets
  stay outside the repository and are never printed. Runtime still has **no `DELETE`**, so anything
  the lab runtime writes is **permanent** and scenario data must be designed durable from the start.
- [x] **Schema posture: the lab starts at head `014_engagement_classification`** by applying the
  existing **14** migrations to an empty schema — **18** tables plus `alembic_version`, `InnoDB` /
  `utf8mb4`, `utf8mb4_bin` pinned on governed columns. **No migration `015`** in Phase 81 or 82, and
  Phase 82 applies migrations **to the lab, never to production**.
- [x] **The measured scenario lives behind a source-system boundary.** The controlled 18-table schema
  has **no table that holds measured operational data** — `source_ingestion_records` registers an
  export's metadata, never its rows. So the lab holds **two schemas**: `peak_lab` (the controlled
  Peak schema, byte-identical to production at 14 migrations and 18 tables) and `peak_lab_scenario`
  (the simulated source system holding measured R1/R2/location rows — **lab-only, never
  Alembic-managed, never in production**). This is also conceptually right: R1 and R2 are exports
  *from* a system of record, not Peak records.
- [x] **Measured lab data is not client evidence.** It cannot make R8 authoritative in the production
  record, cannot upgrade `fnd_000` — that block is a **Phase 36 planner vocabulary limitation**, not
  a measurement gap — and does not reopen the Phase 80 closure. **No real client data, and no
  pseudo-client data, fixture, example, or sample packet is committed to the repository.** The lab
  gets its own anchor; it does **not** reuse the production `internal_test_001` / `99999` anchor.
- [x] **The lab carries no publication authority of any kind** — no client-facing report authority,
  no final-report authority, no capsule publication authority, no AgentNet resolver publication
  authority. The AgentNet resolver gate stays **shut rather than relaxed**.
- [x] **Largest residual risk, recorded not hidden:** `alembic/env.py` reads **only**
  `PEAK_DATABASE_URL`, so targeting the lab means putting a lab DSN in the production-named variable.
  Phase 82's control is procedural — a dedicated lab shell that never held a production value.
  Production being already at head `014` makes a misdirected `upgrade head` a no-op today, which
  **stops being true the moment a `015` exists**.
- [x] **Next: write the provisioning runbook before provisioning anything. Done in Phase 82 — see
  below.**

**The Lab MySQL Provisioning Readiness Runbook (Phase 82 — readiness only; no production access, no
cloud contact, no database, service, schema, user, credential, migration, writer, or record):**

- [x] **Phase 82 creates nothing.** It contacts **no cloud service, API, or console**, sources no
  environment file, opens no connection, runs no migration, invokes no writer, and creates no record.
  The runtime connectivity gate was run in `--self-test` mode only. **No new infrastructure** — docs
  only. Head stays `014_engagement_classification` with 14 migrations, 18 tables, 12 writers, and no
  standing production write enablement; **production remains untouched**. See
  [`PHASE82_LAB_MYSQL_PROVISIONING_READINESS.md`](PHASE82_LAB_MYSQL_PROVISIONING_READINESS.md).
- [x] **Phase renumbering.** Inserting a readiness phase shifts Phase 81's labels: what Phase 81
  called "Phase 82" (provisioning) is now **Phase 83**, and its "Phase 83" (scenario seeding) is now
  **Phase 84**.
- [x] **Naming fixed:** managed service label `peak_lab`, controlled Alembic-managed schema
  `peak_lab`, scenario schema `peak_lab_scenario` — **named and reserved now, created only later
  under separate approval.** Explicitly **not production**, **not staging**, **not a second database
  inside the production service**, and **not `--env test`**.
- [x] **Credential plan, names and posture only, no values:** `peak_lab_migrate` (DDL on `peak_lab`
  only), `peak_lab_runtime` (**exactly `SELECT` + `INSERT`**), `peak_lab_verify_ro` (`SELECT` only —
  renamed from Phase 81's `peak_lab_readonly`). No `GRANT OPTION`, no broad grants, no global
  privilege beyond `USAGE`, no `UPDATE`/`DELETE` for runtime unless separately approved, no
  production credential reused, and **no credential for AgentNet publication, capsule publication,
  final report, or client-facing output.**
- [x] **Env files named, not created:** `peak-lab-migrate.env` (`PEAK_DATABASE_URL`),
  `peak-lab-runtime.env` (`PEAK_RUNTIME_DATABASE_URL`), `peak-lab-ro.env`
  (`PEAK_PRODUCTION_DB_URL` + `PEAK_PRODUCTION_DB_READONLY_CONFIRM=1`) — all outside the repository,
  **no secret value in any repo document.** `PEAK_LAB_CONFIRM` is reserved and **reads as a no-op**;
  Phase 81's `PEAK_LAB_*_URL` names are **retired as operative names**, since nothing reads them.
- [x] **The seam is wider than Phase 81 recorded, so the lab-only shell guard is mandatory.** Every
  tool reads a fixed **production-named** variable and nothing else — Alembic only
  `PEAK_DATABASE_URL`, the connectivity gate only `PEAK_RUNTIME_DATABASE_URL`, the verifier
  `PEAK_PRODUCTION_DB_URL` / `PEAK_DATABASE_URL` with a production-named affirmation variable. **No
  variable name says "lab."** Guard: fresh shell, no production env ever sourced in it, exactly one
  lab file at a time, context verified before migrating, never `env`/`printenv`/`set`/`set -x`, an
  explicit lab assertion on host/service/user before `alembic upgrade`, stop on any
  production-looking name, close or unset afterwards.
- [x] **Phase 83 migration and verification plan:** apply the existing **14** migrations to an empty
  `peak_lab` only, head `014_engagement_classification`, **18** tables plus `alembic_version`,
  `InnoDB`/`utf8mb4` with `utf8mb4_bin` pinned per-column. **No `015`.** Verify head, table count,
  migration count, and governed collation via the lab read-only credential
  (`production_mysql_collation_verify.py` works **unmodified**), then each credential's grants, with
  the connectivity gate run live under the runtime file expecting `required_grants_present=true` and
  `excess_grants_present=false`. Confirm `peak_lab_scenario` does **not** exist yet, no measured rows
  exist, and production was never touched.
- [x] **Tooling gaps recorded, deliberately not fixed:** `make mysql-parity-staging` is **not** a live
  verifier (`run_staging()` emits `[hold]` and returns 0 without connecting) and reads
  `PEAK_MANAGED_MYSQL_TEST_DSN` rather than the staging variable; the read-only verifier's output says
  `production_connection_made` even against the lab; `alembic/env.py` has no lab target — the largest
  residual risk; and `GOVERNED_MYSQL_COLLATION_POLICY.md` states 211/308 governed columns while the
  audit reports 212/309 (migration `014`'s `engagement_category`, correctly pinned — stale text, not a
  defect). Lab-specific wrappers are a later **source-only** decision, and only **after** the lab
  exists.
- [x] **Next: provision and verify the lab. Done in Phase 83 — see below.**

**The peak_lab Managed MySQL Lab (Phase 83 — provisioning, migration, and verification only; no
production access, no writer, no record, no measured row):**

- [x] **Executed under explicit user approval** for the recurring managed MySQL cost, cloud
  provisioning, lab service creation, lab schema/user/credential creation, and applying the existing
  migrations to the lab. **Production was not touched** — no production env sourced, no production
  connection opened, no production verifier run, no production service/network/config changed. See
  [`PHASE83_PEAK_LAB_PROVISIONING_AND_VERIFICATION.md`](PHASE83_PEAK_LAB_PROVISIONING_AND_VERIFICATION.md).
- [x] **Naming correction: the service label is `peak-lab`, not `peak_lab`** — the provider rejects
  underscores in service names. **Only the label changed**: the schema is still `peak_lab` and the
  credentials still `peak_lab_migrate` / `peak_lab_runtime` / `peak_lab_verify_ro`, created through
  SQL where MySQL's identifier rules apply. The schema was created by `CREATE DATABASE` from an admin
  session rather than the provider console, so a hyphenated schema name could not appear by accident.
- [x] **Minimal single-node plan** — no high availability, no replicas, no standby, no paid extras.
  **The provider name, hostnames, DSNs, credentials, and cost figures are not recorded in this
  repository**, by standing rule.
- [x] **Grant posture verified on the server by `SHOW GRANTS`:** `peak_lab_migrate` holds schema-scoped
  DDL, `peak_lab_runtime` holds **exactly `SELECT` + `INSERT`**, `peak_lab_verify_ro` holds **`SELECT`
  only** — each with `USAGE` as its only `*.*` privilege and **none holding `GRANT OPTION`**. Every
  credential was reduced with `REVOKE ALL PRIVILEGES, GRANT OPTION` first. No production credential
  reused, no production data copied.
- [x] **The 14 migrations applied to `peak_lab` alone, in one clean pass** — head
  `014_engagement_classification`, **19 base tables** (18 controlled plus `alembic_version`), all
  `InnoDB`, charset `utf8mb4`. **No `015`.** **The Phase 46 failure did not recur**: the Phase 47
  preflight widened `alembic_version` automatically, so the bootstrap that once broke at migration
  `008` completed. **First fresh bootstrap of this schema rehearsed where it was safe to do so.**
- [x] **Read-only verification passed** via `production_mysql_collation_verify.py` unmodified under
  the lab read-only credential: `verified_safe_no_remediation_required`, head matches, **212 governed
  columns all deterministic, 0 at risk**, **11 idempotency boundaries, 0 at risk**, no mutation, no
  write. **First server-verified evidence that the governed-collation policy holds on a server built
  from these migrations** — the offline audit's `MODEL_POLICY_SATISFIED_PRODUCTION_UNVERIFIED` status
  is unchanged and still accurate, because this verified the **lab**.
- [x] **Runtime gate passed live** against the lab runtime credential:
  `required_grants_present=true`, `excess_grants_present=false`, `global_privileges_present=false`,
  `grant_option_present=false`, `app_table_read_made=false`, `writer_invoked=false`.
- [x] **The lab is empty and `peak_lab_scenario` does not exist** — `alembic_version` holds 1 row and
  **all 18 controlled tables hold 0 rows**. No writer was invoked and no Peak record was created.
- [x] **Mandatory output caption.** Both tools read production-named variables and print
  production-named results — `production_connection_made=true`,
  `production_connectivity_result=succeeded`, `ready_for_later_writer_enablement=true`. **All refer to
  the lab.** No production connection was attempted; the last is prerequisite evidence about a lab
  credential, not permission. The Phase 51 gate still reports `safe_to_write_production_now=false`.
- [x] **One incident, recorded not hidden.** An **unquoted** DSN in an env file made the shell fail
  glob expansion on `?` and **echo the migration credential's password** before any guard could run.
  **`peak_lab_migrate` was rotated**; the exposed value was never used again. All lab env values are
  now single-quoted and generated by an out-of-repo helper using hidden input and URL-encoding.
- [ ] **Open: version-family parity is unverified.** The lab runs **MySQL 8.4**; **production's
  version was not read**, since that needs a production connection this phase was barred from. Settle
  it out-of-band before treating the lab as authoritative for production behaviour.
- [x] **Next was scenario seeding — deferred, and renumbered to Phase 85.** §7.7's `alembic/env.py`
  seam was fixed first, as Phase 84 below. Phase 85, separately approved, creates `peak_lab_scenario`
  and seeds the Phase 81 §7 simulated source-system measurement data (a **migration-credential**
  operation, never runtime), creates a lab engagement anchor and durable measured records through
  **existing, unchanged writers**, and adds lab validation/measurement tests. **The writer-enablement
  gate is environment-blind and hardcodes every authorization to `false`** — authorizing lab writes is
  a deliberate source edit with its own review, never an env var. **Writers are create-only**, so
  correcting a scenario means a new version slug, never a rewrite.

**The Alembic migration target guard (Phase 84 — Fix Now, source-only; no production or lab database
contacted, no migration executed, no `015`, no writer, no record):**

- [x] **Fixes Phase 83 §7.7, the largest residual risk.** `alembic/env.py` read `PEAK_DATABASE_URL`
  and nothing else, so **no variable name said which environment the URL pointed at** and only shell
  discipline kept a lab migration off production. Survivable only while both sat at head `014` with
  nothing left to apply — **an accident of timing, not a control**, expiring the moment a `015` exists.
  See [`PHASE84_ALEMBIC_TARGET_GUARD_FIX.md`](PHASE84_ALEMBIC_TARGET_GUARD_FIX.md).
- [x] **No database was contacted, at all.** No env file sourced, no connection opened, **no migration
  run against any live target**, no `015` created, no `peak_lab_scenario` created, no writer invoked,
  no record created, no cloud/provider/API/console contact, and no dependency installed. Source, tests,
  and docs only; **every URL exercised is synthetic**.
- [x] **MySQL/MariaDB migrations now require an explicit, confirmed target**, checked **before the
  engine is created**: `PEAK_ALEMBIC_TARGET` set to `lab` or `production`, plus
  `PEAK_LAB_MIGRATION_CONFIRM=1` or `PEAK_PRODUCTION_MIGRATION_CONFIRM=1`. Each confirmation accepts
  the exact value `1` and neither substitutes for the other. **`PEAK_LAB_CONFIRM` is deliberately not
  reused** — Phase 82 published it as a reserved no-op.
- [x] **Lab target:** must name schema **`peak_lab`** and connect as **`peak_lab_migrate`** with the
  lab confirmation set. `defaultdb` and the system schemas, any other schema, any other user
  (including `peak_lab_runtime`), and any production marker are refused, each with its own reason code.
- [x] **Production target:** requires its own confirmation, refuses any `peak_lab` marker in user or
  schema, and **remains unauthorized outside a separately approved phase** — passing means the URL is
  *consistent with* production, never that the migration is approved. The guard authorizes nothing.
- [x] **SQLite and every other dialect bypass the guard entirely**, with no environment set, so
  temporary-file harnesses are unaffected — Phase 47's live SQLite `upgrade`/`downgrade`/re-`upgrade`
  regression passes unchanged through the guarded accessor.
- [x] **Value-free by construction.** `alembic/migration_target_guard.py` is stdlib-only: it opens no
  file, imports no driver, creates no engine, issues no SQL, and keeps only the parsed username and
  database — host, port, password, and query string are discarded. `make validate-phase84` runs the
  whole decision table on synthetic URLs and asserts no failure message contains a password, host,
  port, query parameter, or connection string.
- [x] **One test change:** Phase 49's *unconditional* "`alembic/env.py` has no pending diff" assertion
  was an authoring-time scope claim left ungated, i.e. a permanent freeze on the file — the failure
  mode Phase 49's own comments describe. It is now gated with the rest of that harness's working-tree
  scope guard; Phase 49's substantive content assertions are untouched and still pass.
- [ ] **Open, and deliberately not addressed here:** the guard checks the URL's **names, not the host**
  behind them; the production branch is necessarily weaker than the lab branch, since production's
  names are not recorded in this repository and must not be; and the connectivity gate and collation
  verifier still take a lab DSN in a production-named variable with **no target of their own**.
- [ ] **Next: commit and accept this fix before any migration `015` or further lab migration work.**
  Only then may **Phase 85** proceed to `peak_lab_scenario` planning and seeding, under its own
  separate approval.

**The peak_lab_scenario source-system schema (Phase 85 — lab-only creation and seeding; no production
access, no live migration, no `015`, no writer, no Peak record):**

- [x] **`peak_lab_scenario` exists and is seeded**, on the lab service only. It is a **simulated
  source-system schema**, not a Peak controlled schema and never production: **not Alembic-managed, no
  `alembic_version` table, no controlled table.** `peak_lab` stays the Alembic-managed controlled
  schema. See [`PHASE85_PEAK_LAB_SCENARIO_SEEDING.md`](PHASE85_PEAK_LAB_SCENARIO_SEEDING.md).
- [x] **Eight tables**, all `InnoDB` / `utf8mb4_0900_ai_ci`, 37 identity columns pinned `utf8mb4_bin`;
  every primary key includes the scenario identity, so a duplicate seed row cannot be inserted.
- [x] **Scenario `internal_test_inventory_ops_v1`** — 87 data rows plus 33 control totals, **120 rows**,
  hash `18459dc1964bc5622d7c7b40ba88b4b2ed7fbc268bf65e20e66f22c828bea1cb`, agreeing across the
  definition, the rows read back from the database, and the stored control total. Deliberately mixed:
  populations that should pass a future readiness check and populations that should fail it. **All
  identifiers are obvious internal synthetic tokens; no client, customer, vendor, brand, address, or
  personal datum appears, and no pseudo-client stands in for one.**
- [x] **Correction policy enforced, not merely stated:** absent → insert; identical → idempotent replay,
  nothing written; **different → stop, new version slug required, no `UPDATE` and no `DELETE`.** Both
  the replay and the divergence-stop paths were exercised.
- [x] **Two new least-privilege credentials**, `peak_lab_scenario_loader` and `peak_lab_scenario_ro`,
  each global `USAGE` only with exactly one database-level grant on `peak_lab_scenario.*` and **no
  `GRANT OPTION`**; **neither can enumerate a single `peak_lab` table.** No controlled-schema credential
  was expanded and no production credential was touched.
- [x] **`peak_lab` re-verified untouched** — head `014_engagement_classification`, `alembic_version` 1
  row, **0 application rows across all 18 controlled tables**. No writer invoked, no Peak record created,
  no production access, no live Alembic migration, **no migration `015`**. Docs only; **no scenario row
  body is committed.**
- [ ] **Open: lab service users arrive over-privileged.** The platform grants new service users global
  `ALL PRIVILEGES` WITH `GRANT OPTION`, so **every future lab credential is over-privileged until
  explicitly reduced**, and the reduction must be verified by connecting as the credential. Two further
  operational hazards are recorded in the phase document: the non-obvious revoke/grant ordering this
  server requires, and that the control plane returns a **masked placeholder** for a stored password,
  so credentials can be reset but never recovered.
- [ ] **Open: the scenario schema is outside the Phase 84 guard**, which covers Alembic only. Protection
  rests on the credential boundary instead — a real control, but a different one.
- [ ] **Next: measurement against the scenario remains unauthorized.** Future evidence, extraction, and
  source-ingestion phases may now measure against it, **each under its own separate approval**. Measured
  values are **lab-scenario values, never client evidence and never a finding.** The writer-enablement
  gate stays environment-blind with every authorization hardcoded `false`, and writers stay create-only.
- [ ] **All Phase 83 §7 open items remain open**, and Phase 85 closes none of them.

**The read-only lab scenario measurement pass (Phase 88 — lab-only, `SELECT` only; no Peak record,
no writer, no production access, no schema change):**

- [x] **The seeded scenario was measured repeatably from the read-only scenario credential.** The
  content hash matches the Phase 85 published value, **all 33 stored control totals were independently
  recomputed from the rows and agreed**, and both referential checks held. Five write attempts were
  issued as a deliberate negative control and **all five were refused by the server**, proving the
  read-only posture by measurement rather than by grant text.
- [x] **Aggregate coverage now exists for R1, R2, R5, R8, R9 and derived R10.** Every domain measures
  **partial** — the scenario behaving as designed, since a dataset in which everything resolved could
  not demonstrate that a readiness check works. Headline figures: inventory SKU attribution
  unblocked (32/32) but only **43.8% of rows fully location-attributable**; 9 of 16 locations
  structurally complete; **4 of 10 authority domains resolved**; 3 of 7 putaway events usable.
- [x] **One design input for the next phase.** A presence-only item-master readiness rule
  **over-counts usable items by 1 in 10**: `ambiguous` encodes a semantic conflict, not a missing
  value. A future readiness rule must consult the completeness classification, not attribute
  presence alone. See [`PHASE88_LAB_SCENARIO_MEASUREMENT.md`](PHASE88_LAB_SCENARIO_MEASUREMENT.md) §4.2.
- [x] **`peak_lab` re-verified unchanged** — 18 controlled tables, head `014_engagement_classification`,
  **0 application rows**. `peak_lab_scenario` unchanged at 120 rows.
- [ ] **Open: the Phase 82 §3 variable-naming seam was encountered directly.** The lab read-only
  credential file sets a **production-named variable** while pointing at the lab schema. Phase 88
  guarded against it by asserting the target database and role **before** connecting, but the seam
  remains a standing trap for any tool that reads a variable name as an environment label.
- [ ] **Next: creating Peak records from these measurements remains unauthorized.** A future phase may
  propose it under its own approval, naming writer, table, action, scope, idempotency key and cleanup
  posture in advance. **Writer enablement remains separately unauthorized.**

**The lab-only writer enablement decision gate (Phase 89 — source, test and docs only; no writer
invoked, no record created, no database contacted, no production access):**

- [x] **Lab enablement is now a separate axis from production enablement.** The Phase 51 gate is
  environment-blind and hardcodes every authorization `false` — right for production, useless for a
  lab rehearsal, and it left lab enablement as an undifferentiated source edit. A new module decides
  the lab question; **the production gate is byte-identical and untouched**, asserted as a git-backed
  check rather than inferred from a passing run.
- [x] **A positive lab decision requires eight things at once**: an explicit `lab` target, an exact
  confirmation value, a MySQL/MariaDB URL, a schema that is not the scenario schema, not the
  provider default, not production-marked and **exactly** `peak_lab`, a user that is not
  production-marked and is the approved lab runtime role, and a requested writer target set wholly
  inside the enableable three. Any one failing denies with a stable, value-free reason code.
- [x] **Nine variables are explicitly refused as authorizers**, including the Phase 82 reserved
  no-op, the Phase 84 migration variables, the Phase 85 scenario variables, and the production-named
  variables — so one confirmation can never grant two authorities. This answers the Phase 82 §3 seam
  Phase 88 hit: the new variables name their own purpose honestly.
- [x] **Writer targets are scoped, not blanket-enabled** — three create-only pairs, a strict subset
  of the controlled allowlist, with the engagement authorization anchor in a separate
  never-enableable set so the exclusion is testable. A mixed request fails whole.
- [x] **123 harness checks plus 31 self-test assertions**, all offline with synthetic URLs, wired
  into `make validate` as `validate-phase89`.
- [ ] **Open: the anchor exclusion may block the first rehearsal.** A lab rehearsal needing an
  engagement anchor will find that pair refused. That is deliberate, but a future phase may need to
  request it, and that request must be its own reviewed change.
- [x] **One unrelated harness fix was required.** Phase 72's "no prior-phase operator utility was
  modified" check sat outside its own authoring-time gate and judged every later phase's `tools/`
  file against Phase 72's allowlist, so adding any operator utility failed `make validate`
  permanently. The check was **moved inside the existing gate**, unchanged in assertion, label, and
  allowlist — the same defect class Phase 86 swept, missed when the adjacent guard was gated.
- [ ] **Next: no lab write is approved.** Phase 89 invokes no writer. A future phase must name the
  writer, the records and expected count, the source measurements, the authorization scope, the
  idempotency keys, the expected receipts, the verification plan, and the cleanup posture —
  decided before the write, given the runtime role has no removal path.

**The lab engagement anchor bootstrap (Phase 90 — one durable lab record; no production access, no
migration, no other writer):**

- [x] **The anchor writer is lab-enabled for bootstrap only.** A second confirmation,
  `PEAK_LAB_ENGAGEMENT_ANCHOR_BOOTSTRAP_CONFIRM=1`, plus every Phase 89 check, plus the anchor as
  the **only** requested target. The pair stays out of `LAB_ENABLEABLE_WRITER_TARGETS`, so no
  ordinary lab request can reach it, and a request mixing it with data targets denies whole.
- [x] **One record exists in `peak_lab`**: `engagements` row `lab_internal_test_001`,
  `engagement_category=internal_test`, `real_client_data=false`, `client_accessible=false`,
  `capsule_publication_authorized=false`. Before: 0 application rows across all 18 controlled
  tables. After: **1**, in `engagements` only. Head stays `014_engagement_classification`.
- [x] **Idempotency exercised, not asserted.** A second run returned `idempotent_replay` with
  `database_write_made=false`, and the table still holds exactly one row.
- [x] **Two contract corrections came from the writer, not the plan.** The planned
  `authorization_scope=internal_peak_lab_only` is not a member of the closed `AuthorizationScope`
  vocabulary and was refused **before any connection opened**; the canonical `internal_peak_only`
  was used. `capsule_publication_authorized` is false here, more conservative than Phase 59.
- [ ] **Open: the dry-run governance pre-check is weaker than the writer boundary.** It passed the
  invalid scope the writer then refused. Nothing was written and defence in depth held, but a green
  dry-run must not be read as proof a write will be accepted.
- [ ] **Open: `peak_lab` is no longer empty.** "0 application rows" was a standing safety assertion
  for every prior lab phase and is now false by design. Future verifiers must expect exactly one
  `engagements` row and must not read it as drift.
- [ ] **Next: lab source-ingestion, evidence and review writes remain unauthorized.** The three
  Phase 89 pairs are *enableable*; that is not approval to run them. Each needs its own phase naming
  writer, records, expected count, scope, idempotency keys, receipts, verification and durability.

**The drift and test-sprawl review (Phase 91 — docs-only; no database, cloud, environment,
migration, writer, record, or scenario activity; no migration 015; no harness added):**

- [x] **Validation cost is now disproportionate to risk.** 72 phase harnesses, 9,292 pass lines,
  ~39,400 harness source lines. Assertion mass concentrates in fourteen near-identical record-chain
  harnesses (Phases 59-72) and in prose/path/history restatement rather than behaviour.
- [x] **The harness convention is habit, not risk assessment.** Roughly one harness per
  code-shipping phase from Phase 33 to Phase 72. Recorded policy: a phase may ship without a
  harness, and one is added only for a durable safety invariant or a repeatable contract.
- [x] **The known freeze defect class is still live in a slower form.** `EXPECTED_MIGRATIONS`,
  `EXPECTED_TABLE_COUNT`, `HEAD_REVISION`, and `EXPECTED_WRITERS` are duplicated across 27-31
  harnesses each, so the next migration or writer fails all of them at once. 34 harnesses freeze a
  file path but only 5 use the authoring-time gate that makes such a claim correct.
- [x] **Parallel read-only agentic workflows are recorded as acceptable**, with bounded prompts, a
  single primary session owning the diff, no live/environment/write access without explicit
  approval, and no printing of connection values or row bodies. Three were used in this phase and
  their material claims were re-verified before being recorded.
- [ ] **Open: consolidation is recommended but deliberately not done here.** All checks pass and
  there is no active failure or false red, so no test was deleted or weakened. A scoped phase
  should extract the shared baseline constants first, then the shared git helpers, then gate the
  remaining file freezes. That removes freeze risk without reducing coverage.
- [x] **`README.md`'s status banner was materially false and was corrected here.** It stated the
  repository has no database, against 14 migrations, 18 controlled tables, and 12 writers. The
  banner now names the controlled schema, the narrow create-only writers, and the enablement gates,
  and records that production write enablement stays false, that rehearsal is lab-only, and that
  there is still no frontend. Banner only; the rest of the README is unchanged.
- [ ] **Next: Phase 92 returns to workflow execution — the first lab source-ingestion write.** Turn
  a Phase 88 read-only measurement into a controlled Peak source-ingestion record against
  `peak_lab`, using the Phase 89 gate as-is. It must name writer, records and expected count, source
  measurement, authorization scope from the closed vocabulary, idempotency keys, expected receipts,
  verification plan, and cleanup posture decided before the write. It should add no permanent
  harness absent a specific unsafe condition, and no migration, schema, model, or writer.

Full record: [`PHASE91_DRIFT_TEST_SPRAWL_PARALLEL_WORKFLOW_REVIEW.md`](PHASE91_DRIFT_TEST_SPRAWL_PARALLEL_WORKFLOW_REVIEW.md).


**The first lab source-ingestion write (Phase 92 — one durable lab record; no production access, no
migration, no schema change, no new harness):**

- [x] **The Phase 89 lab data-record path was used as-is, for the first time.** The gate returned
  `lab_write_authorized` / `lab_target_confirmed_and_scoped`, granting exactly
  `source_ingestion_records/create_source_ingestion_record` with `anchor_bootstrap_authorized=false`
  and all three production fields false. The Phase 90 anchor-bootstrap confirmation was neither set
  nor needed — an ordinary data-record target never reaches that branch.
- [x] **One record exists in `peak_lab`**: `source_ingestion_records` row `ing_d67b76327aba4add`,
  engagement `lab_internal_test_001`, client `99999`, scope `internal_peak_only`, source reference
  `pkt_lab_phase88_scenario_measurement_001`, review-gated at `needs_review` / `draft` / `active`.
  Before: 1 application row. After: **2**, in `engagements` and `source_ingestion_records` only.
  Head stays `014_engagement_classification`.
- [x] **Packet metadata only, derived from the Phase 88 measurement.** Schema/source type
  `lab_scenario_measurement`, a logical location reference rather than a filesystem path, and the
  Phase 85 scenario content hash. `authoritative`, `client_facing_approved`, and
  `capsule_candidate_ready` are all false. No scenario row body, SQL, JSON, or CSV extract entered
  the request, the record, or the docs.
- [x] **The runtime role cannot undo this.** Read back as the credential itself: `SELECT` + `INSERT`
  only, no `UPDATE`/`DELETE`/`DROP`/`CREATE`/`ALTER`/`GRANT OPTION`, and no visibility into
  `peak_lab_scenario`. Writing to the scenario schema was structurally impossible, not merely
  disallowed.
- [x] **No new harness was added.** No defect required one, and Phase 91's policy is that a phase
  may ship without one. The one-time invocation ran from an out-of-repo operator script; every field
  needed to reconstruct the request is recorded in the phase document.
- [ ] **Open: idempotency was verified structurally, not by replay.** The DB-enforced boundary
  `uq_source_ingestion_records_idem` is present over four columns and the row carries its key and a
  64-character payload fingerprint, but this phase authorized exactly one writer call, so no second
  invocation was made. A replay would return `idempotent_replay` without writing.
- [ ] **Open: the gate and the writer read different variables.** The gate reads
  `PEAK_LAB_WRITER_TARGET_URL`; the writer connects via `PEAK_RUNTIME_DATABASE_URL`. The gate cannot
  verify what the writer will actually connect to. Both came from the same single-variable lab file
  here, and post-write verification confirmed the row landed in `peak_lab`.
- [ ] **Next: a first lab evidence reference OR a first review record — not both.** Both pairs are
  already *enableable* by the Phase 89 gate; that is reachability, not approval. Each needs its own
  phase naming writer, records, expected count, scope, idempotency key, receipts, verification and
  cleanup posture.

Full record: [`PHASE92_FIRST_LAB_SOURCE_INGESTION_WRITE.md`](PHASE92_FIRST_LAB_SOURCE_INGESTION_WRITE.md).


**The first lab evidence reference (Phase 93 — one durable lab record; no production access, no
migration, no schema change, no new harness):**

- [x] **The Phase 89 lab data-record path was used as-is, a second time.** The gate granted exactly
  `evidence_references/create_draft` with `anchor_bootstrap_authorized=false` and all three
  production fields false. The Phase 90 bootstrap confirmation was neither set nor needed.
- [x] **One record exists in `peak_lab`**: `evidence_references` row `evid_f094cbe4b47d4048`,
  engagement `lab_internal_test_001`, client `99999`, scope `internal_peak_only`, review-gated at
  `needs_review` / `draft` / `active`, linked to the Phase 92 record `ing_d67b76327aba4add`.
  Before: 2 application rows. After: **3**. Head stays `014_engagement_classification`.
- [x] **The claim is bounded in the record itself.** The stored summary supports exactly one
  statement — that a Phase 88 lab scenario measurement exists as a controlled Peak source-ingestion
  record — and records that it does not support an inventory accuracy conclusion, does not assert
  source-system truth, is not reviewed, not authoritative, not client-facing, not capsule-ready, and
  that publication remains unauthorized.
- [x] **Three contract differences were followed, not worked around.** `evidence_type` and
  `source_type` are bounded by `schemas/evidence-reference.schema.json`, so the proposed
  `lab_source_ingestion_readiness_reference` / `source_ingestion_records` were refused in favour of
  the schema-valid `other`; `evidence_references` has no typed link column, so the link to Phase 92
  is carried three free-form ways; and the table has no `authoritative` column, so that posture is
  enforced pre-connection and stated in the summary but not stored as a flag.
- [ ] **Open: the non-authoritative posture is not independently readable on an evidence row.**
  Unlike `source_ingestion_records`, which records the three flags in `details_json`, the evidence
  writer enforces them and drops them. A future verifier cannot read them back from the row.
- [ ] **Open: idempotency was verified structurally, not by replay**, as in Phase 92 — the boundary
  `uq_evidence_references_idem` is present over four columns and the row carries a 64-character
  fingerprint, but only one writer call was authorized.
- [ ] **Next: a first lab review record.** It would let a reviewer decision act on this evidence
  reference and move it off `needs_review`. Enableable by the Phase 89 gate, which is reachability,
  not approval; it needs its own phase naming writer, records, expected count, scope, idempotency
  key, receipts, verification and cleanup posture.

Full record: [`PHASE93_FIRST_LAB_EVIDENCE_REFERENCE.md`](PHASE93_FIRST_LAB_EVIDENCE_REFERENCE.md).


**The first lab review record (Phase 94 — one durable lab record; no production access, no
migration, no schema change, no new harness):**

- [x] **The Phase 89 lab data-record path was used as-is, a third time.** The gate granted exactly
  `review_records/create_review_record` with `anchor_bootstrap_authorized=false` and all three
  production fields false. All three enableable pairs have now been exercised once each.
- [x] **One record exists in `peak_lab`**: `review_records` row `rev_70b5da9f14d54488`, decision
  `approve_internal`, `authoritative=false`, reviewing target `evid_f094cbe4b47d4048` as
  `subject_record_type=evidence_reference`, linked to `ing_d67b76327aba4add`. Before: 3 application
  rows. After: **4**. Head stays `014_engagement_classification`.
- [x] **The decision is internal-only and claim-bounded.** It approves that a Phase 88 lab scenario
  measurement exists as a controlled source-ingestion record and that the evidence reference
  describing it is well formed. It establishes none of: inventory accuracy, source-system truth,
  client evidence, production evidence, or authoritative status.
- [x] **The Phase 93 asymmetry was respected, not assumed.** `evidence_references` has no
  `authoritative` column — confirmed directly — so no such flag was read from it. The posture rests
  on writer-enforced pre-connection validation, governed state, and the claim-boundary summary
  verified as booleans. The review row itself does carry a stored `authoritative` column.
- [x] **No mutation, and none was needed.** The writer is INSERT-only, so no `UPDATE` grant was
  required and none exists. The evidence row is unchanged, still `needs_review`, with `updated_at`
  still equal to `created_at`.
- [ ] **Open: the approval is recorded, not propagated.** `review_status=approved_internal` lives on
  the review record; anything reading `evidence_references` alone still sees `needs_review`. There is
  no typed join between them, so correlating the two is the reader's job.
- [ ] **Open: the writer never loads the reviewed target.** `target_id` is a free-form column with no
  foreign key and no write-time existence check; a dangling id would be accepted. This phase verified
  the target out of band, which is operator discipline rather than a contract guarantee.
- [ ] **Open: idempotency was verified structurally, not by replay**, as in Phases 92–93.
- [ ] **Next: a decision, not another guardrail phase.** The lab chain is now complete end to end at
  depth one — anchor, source ingestion, evidence reference, review decision. The question is whether
  that is sufficient to attempt a minimal internal lab assessment or report draft, or whether the
  chain needs more breadth first. Weigh that the measurement is partial, the evidence is low
  reliability and non-authoritative, and the approval is internal-only and unpropagated.

Full record: [`PHASE94_FIRST_LAB_REVIEW_RECORD.md`](PHASE94_FIRST_LAB_REVIEW_RECORD.md).


**The minimal internal lab assessment draft (Phase 95 — docs-only; no writer, no record, no
database contact, no schema change, no new harness):**

- [x] **The depth-one chain is sufficient for a docs-only internal assessment, and only that.** The
  Phase 88 measurement was carried through source ingestion, evidence reference, and review decision,
  and the narrow claim boundary survived all three hand-offs without widening — the most useful thing
  the chain demonstrated.
- [x] **A database-backed report draft was refused, and the refusal was verified rather than
  assumed.** Evaluating the Phase 89 gate against
  `internal_assessment_report_drafts/create_internal_assessment_report_draft` returns `denied` /
  `writer_target_not_lab_enableable`, while a control pair authorizes in the same run. The gate's
  enableable set is exactly the three data-record pairs already exercised; a report draft needs its
  own authorization phase, which this phase did not open.
- [x] **Findings are grounded in Phase 88, not invented.** Content hash matched and all 32 stored
  counts/sums recomputed with 0 mismatches; five deliberate write attempts were all refused; every
  measured dimension is *partial* by design; location attribution rather than SKU attribution is the
  R1 constraint; a presence-only readiness rule would over-count usable items by 1 in 10; the R5
  population is small enough that conclusions are directional even within the lab.
- [x] **The most consequential finding — the chain's review record was invisible to the report
  planner — is resolved in Phase 96.** The Phase 36 planner read six reference categories, and
  `review_records` was not one of them; it recognised `review_bundle_records` and
  `internal_reviewer_decision_records` instead. Of its 14 sections the depth-one chain supplied
  references for 6, 3 needed none, and 5 were blocked. Neither review-bundle nor reviewer-decision
  writers are lab-enabled, and Phase 96 did not enable them.
- [ ] **Next: a deliberate breadth decision, not another default guardrail phase.** Either a second
  evidence reference from a distinct Phase 88 dimension on the existing source-ingestion record — the
  smaller step, answering the narrower question — or a second full chain on a different measurement
  basis. Phase 95 performs neither; both need their own approval. If a richer assessment is meant to
  use the existing planner, the gap is the record types the planner reads, not more evidence.

Full record: [`PHASE95_MINIMAL_INTERNAL_LAB_ASSESSMENT_DRAFT.md`](PHASE95_MINIMAL_INTERNAL_LAB_ASSESSMENT_DRAFT.md).


**The planner `review_records` path (Phase 96 — planner/tests/docs only; no writer, no record, no
database contact, no schema/model/enum/writer/allowlist/gate change, no migration 015, no new
harness):**

- [x] **The gap was vocabulary and request shape, not schema.** `review_records` already carries
  `target_id`, `subject_record_type`, `decision`, `authoritative`, `output_status`, the governance
  mixin's status/identity/scope columns, and the idempotency/fingerprint pair. Nothing had to be
  added to the database, so **migration 015 was not created and was not needed.**
- [x] **`review_records` is now an accepted review-support category.** `review_record_ids →
  review_records` joins `REF_CATEGORY_RECORD_TYPES`; `REF_CATEGORY_ALTERNATIVES` declares it
  interchangeable wherever `review_bundle_record_ids` is required, for sections and for candidate
  slots alike. **Nothing was removed** — the review-bundle and reviewer-decision paths are unchanged.
- [x] **The support is category-level, and the plan says so.** The boundary reads no database and
  never sees the reviewed row's stored `decision`, `review_status`, `subject_record_type`, or
  `authoritative` flag, so support means *a review reference was named* and nothing more. Plans
  supported that way carry `REVIEW_RECORD_SUPPORT_CAVEAT` in their reasons and section notes. A
  consumer needing higher assurance must correlate those stored fields deliberately, outside this
  boundary.
- [x] **Approval is still recorded, not propagated.** The change adds no approval propagation to
  `evidence_references`, no FK or target-load enforcement to the review writer, and no authoritative,
  client-facing, production, capsule, publication, or AgentNet posture.
- [x] **The offline exercise confirms the unblock, value-free.** Over the depth-one chain shape with
  approved synthetic ids: ready sections 6 → 7, blocked 5 → 3, open gaps 6 → 4, and the finding slot
  moved from *blocked for want of review support* to *internal draft candidate*. `review_status` went
  blocked → ready; `internal_recommendations` went blocked → partial.
- [x] **Eight ungated harness freezes had to be repaired to land it, per Phase 91 recommendation
  3.** Phases 65–70 and 72 each froze the whole `peak/` tree against the working tree with no
  authoring-time gate; Phase 84 froze the same tree under a label naming only writer files. The
  seven now run under the existing `phase_never_committed` gate and Phase 84's pathspec was narrowed
  to match its label, with a new unconditional check on `models.py` and the allowlist beside it. No
  coverage was weakened — every substantive invariant stays unconditional. Suite: 72 harnesses, 0
  failures.
- [ ] **Next: breadth, deliberately.** Three sections remain blocked — `engagement_context` and
  `intake_summary` want intake-note records, `ai_agent_readiness` wants agent-task-queue records —
  and no recommendation slot exists without a reviewer-decision reference. That is real missing
  breadth, not planner invisibility. The planner now has enough support to plan the chain, so the
  immediate step is a DB-free planner run or draft refinement; adding a further chain is a separate
  decision needing its own approval.

Full record: [`PHASE96_PLANNER_REVIEW_RECORD_PATH.md`](PHASE96_PLANNER_REVIEW_RECORD_PATH.md).


**The DB-free planner run over the depth-one chain (Phase 97 — docs-only; no writer, no record, no
database contact, no env read, no schema change, no new harness):**

- [x] **The planner runs clean over the real chain.** Called offline with the chain's actual
  documented identity and scope rather than placeholders, supplying only the three categories the
  chain has — source ingestion, evidence reference, review record. Deterministic, zero warnings,
  zero controlled write requests, every side-effect flag false.
- [x] **Result: 7 ready / 1 partial / 3 blocked / 3 synthesis-only**, 4 open gaps, 1 finding
  candidate at `internal_draft_candidate`, 0 recommendation candidates. Posture stays
  `plan` / `needs_review` / `draft` with `requires_human_review=true` and every readiness flag false.
  The review-record caveat appears in the plan's reasons and in both affected sections' notes.
- [x] **The finding that matters: readiness is presence, not sufficiency.** Seven "ready" sections
  rest on **three** distinct references — four of them on the *same* single evidence reference, two
  on the same single source record, every one with a supporting-reference count of exactly one.
  `ready_for_internal_drafting` means "each supporting category has at least one reference", nothing
  more. This is Phase 88's F6 over-counting shape reappearing at the planning boundary.
- [x] **Posture decision: (B) with a narrow slice of (A).** The chain is sufficient for a refined
  internal assessment *plan* and a very limited draft over the source → evidence → review spine. It
  is **not** sufficient for a richer assessment: four sections drawing on one evidence reference
  cannot carry four independent findings. One finding slot is the honest ceiling.
- [ ] **Next, after explicit approval — one of three.** (1) Refine the DB-free draft into a bounded
  internal report outline over the spine, carrying the presence-vs-sufficiency caveat — the smallest
  step, adds no records, and the recommended one. (2) Add one intake-note reference chain, unblocking
  engagement context and intake summary. (3) Add one agent-task-queue reference chain, unblocking
  AI/agent readiness. Options 2 and 3 create durable records and each needs its own phase approval,
  writer enablement decision, and cleanup posture decided in advance.

Full record: [`PHASE97_DB_FREE_INTERNAL_ASSESSMENT_PLANNER_RUN.md`](PHASE97_DB_FREE_INTERNAL_ASSESSMENT_PLANNER_RUN.md).


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
