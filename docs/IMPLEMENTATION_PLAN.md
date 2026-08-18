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
