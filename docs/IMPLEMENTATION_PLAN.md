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
