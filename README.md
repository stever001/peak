# Peak Internal AI Operating System

An internal, AgentNet-grounded agent workflow system for **Peak Inventory Solutions**.

> **Status:** Early-stage scaffolding. This repository currently defines the
> operating model, agent workflow map, data objects, and implementation plan.
> It does **not** yet contain production agent logic, a database, or a frontend.

---

## What this is

Peak is an inventory consulting firm. This project is the **internal operating
system** that Peak's consultants and management use to make inventory consulting
work more **repeatable, scalable, evidence-based, and commercially effective**.

The core premise: Peak's consulting knowledge and process are encoded as a set of
**agent-assisted workflows**. These workflows are **grounded by AgentNet**, which
serves as the intended knowledge-grounding and resolution layer so that agent
outputs are anchored to Peak's real methodology, evidence, and standards rather
than to unverified model output.

## What this is **not** (yet)

This is an important distinction that runs through the whole repository:

| Internal Peak capability (this repo's focus) | Future client-facing capability (out of scope for now) |
| --- | --- |
| Tools for Peak consultants and management | Products or dashboards used directly by clients |
| Structuring intake, assessment, evidence, and reporting | Self-serve client portals |
| Improving repeatability and quality of Peak's own work | Automated deliverables sent without consultant review |
| Internal QA/governance of agent output | Client-facing SLAs or automation guarantees |

Everything here is designed to **assist Peak's people**, not replace the
consultant relationship with the client. Client-facing functionality is a
deliberate later phase.

## The first workflow

The initial end-to-end thread this system supports:

```
New Client Intake  →  Initial Assessment Planning  →  Discovery (interviews +
walk-around)  →  Evidence Normalization  →  Initial Management Report  →
Quick-Win Identification  →  Next-Phase Proposal  →  Internal QA/Governance  →
Engagement Learning Capture
```

See [`docs/AGENT_WORKFLOWS.md`](docs/AGENT_WORKFLOWS.md) for the full map.

## Repository layout

```
peak/
├── README.md                     # This file
├── docs/                         # Operating model, workflows, data objects, plan
│   ├── OPERATING_MODEL.md
│   ├── AGENT_WORKFLOWS.md
│   ├── DATA_OBJECTS.md
│   ├── CONSULTANT_WORKFLOW.md    # How a consultant uses this repo, step by step
│   ├── DATA_HANDLING_POLICY.md   # Source-assets-only; client data never in the repo
│   ├── FIXTURE_STRATEGY.md       # Synthetic fixtures at runtime; no stored data
│   ├── CONTROLLED_DATA_ARCHITECTURE.md   # Where real engagement data lives (not Git)
│   ├── RESOLVER_CAPSULE_ARCHITECTURE.md  # Private resolver capsules (intended future)
│   ├── ENGAGEMENT_DATA_MODEL.md          # Controlled-storage data model (architecture)
│   ├── SOURCE_SYSTEM_CAPSULIZATION.md    # Source→capsule path (intended future)
│   ├── GOVERNANCE_STATES.md              # Authorization/review/lifecycle state families
│   ├── STATE_TRANSITIONS.md              # Allowed transitions + agent guardrails
│   ├── DATABASE_IMPLEMENTATION_PLAN.md   # Staged plan for the controlled database
│   ├── DATABASE_RECORD_MODEL.md          # Planned record groups (no data)
│   ├── DATABASE_ACCESS_AND_AUDIT.md      # Access roles, audit fields, agent limits
│   ├── DATABASE_TO_RESOLVER_MAPPING.md   # DB records → resolver capsules (planning)
│   ├── DATABASE_SCAFFOLD.md              # MySQL scaffold: models, enums, migration
│   ├── AGENTNET_MCP_BOUNDARY.md          # Peak governance wrapper for the MCP connector
│   ├── PEAK_RESOLVER_ACCESS_POLICY.md    # Who/what may reach the resolver, under governance
│   ├── AGENT_EXECUTION_HARNESS.md        # How future agents are invoked/governed (no execution)
│   ├── AGENT_RUN_RECORDS.md              # Future AgentRunRecord shape (nothing stored)
│   ├── EVIDENCE_NORMALIZATION_WORKER.md  # First production-shaped worker (review-gated)
│   ├── EVIDENCE_RECORD_LIFECYCLE.md      # Raw → normalized draft → reviewed evidence
│   ├── QA_REVIEW_GATE.md                 # QA / review gate scaffold (no-side-effect decisions)
│   ├── REVIEW_DECISION_MODEL.md          # Allowed/prohibited review decisions + state effects
│   ├── REVIEW_PERSISTENCE_BOUNDARY.md    # Future ReviewRecord persistence (DB-aware, not DB-writing)
│   ├── DB_BACKED_REVIEW_SCOPE_POLICY.md  # Stored-scope comparison rule for DB-backed review
│   ├── CONTROLLED_DB_WRITER_BOUNDARY.md  # Generic controlled-write boundary (DB-aware, not DB-writing)
│   ├── CONTROLLED_WRITE_ALLOWLIST.md     # Allowed/prohibited write tables + actions
│   ├── EVIDENCE_PERSISTENCE_MAPPING.md   # Normalized evidence → controlled write plan (Phase 14→17)
│   ├── EVIDENCE_WRITE_PLAN_POLICY.md     # Evidence write-plan rules (idempotency, stored-scope)
│   ├── AGENT_RUN_PERSISTENCE_MAPPING.md  # Agent run output → controlled write plan (Phase 13→17)
│   ├── AGENT_RUN_WRITE_PLAN_POLICY.md    # Agent run write-plan rules (idempotency, stored-scope)
│   ├── AGENT_RUN_CONTROLLED_WRITER.md    # First real DB-backed writer for agent_run_records (Phase 20)
│   ├── AGENT_RUN_IDEMPOTENCY_POLICY.md   # DB-enforced idempotency: replay vs replay-conflict
│   ├── EVIDENCE_CONTROLLED_WRITER.md     # Second DB-backed writer, for evidence_references (Phase 21)
│   ├── EVIDENCE_IDEMPOTENCY_POLICY.md    # DB-enforced idempotency for evidence rows
│   ├── REVIEW_CONTROLLED_WRITER.md       # Third DB-backed writer, for review_records (Phase 22)
│   ├── REVIEW_IDEMPOTENCY_POLICY.md      # DB-enforced idempotency for review rows
│   ├── ENGAGEMENT_PACKET_INGESTION_BOUNDARY.md  # Packet ingestion boundary (no direct DB writes)
│   ├── PACKET_TO_CONTROLLED_WORKFLOW_POLICY.md   # Packet-derived outputs + prohibited effects
│   ├── SOURCE_INGESTION_CONTROLLED_WRITER.md     # Fourth DB-backed writer, for source_ingestion_records (Phase 24)
│   ├── SOURCE_INGESTION_IDEMPOTENCY_POLICY.md    # DB-enforced idempotency for source ingestion rows
│   ├── CONTROLLED_PACKET_PROCESSING_ORCHESTRATOR.md # Controlled sequencing layer over Phases 23/24/14/21/13 (Phase 25)
│   ├── PACKET_PROCESSING_ORCHESTRATION_POLICY.md   # Orchestration governance: modes, no-escalation, packet-content rule (Phase 25)
│   ├── AGENT_TASK_QUEUE_READINESS_BOUNDARY.md      # DB-free agent task queue / execution readiness boundary (Phase 26)
│   ├── AGENT_TASK_QUEUE_GOVERNANCE_POLICY.md       # Queue/readiness governance: readiness states, no execution (Phase 26)
│   ├── AGENT_TASK_QUEUE_CONTROLLED_WRITER.md       # Fifth DB-backed writer, for agent_task_queue_records (Phase 27)
│   ├── AGENT_TASK_QUEUE_IDEMPOTENCY_POLICY.md      # DB-enforced idempotency for agent task queue rows (Phase 27)
│   ├── PACKET_TO_TASK_QUEUE_ORCHESTRATION_INTEGRATION.md # Phase 25 orchestrator ↔ Phase 26/27 queue path integration (Phase 28)
│   ├── PACKET_DERIVED_REVIEW_ORCHESTRATION_BOUNDARY.md # DB-free review-planning boundary for human reviewers (Phase 29)
│   ├── REVIEW_ORCHESTRATION_GOVERNANCE_POLICY.md   # Review-orchestration governance: readiness states, no approval (Phase 29)
│   ├── REVIEW_BUNDLE_CONTROLLED_WRITER.md          # Sixth DB-backed writer, for review_bundle_records (Phase 30)
│   ├── REVIEW_BUNDLE_IDEMPOTENCY_POLICY.md         # DB-enforced idempotency for review bundle rows (Phase 30)
│   ├── PACKET_TO_REVIEW_BUNDLE_ORCHESTRATION_INTEGRATION.md # Packet processor ↔ Phase 29/30 review path integration (Phase 31)
│   ├── INTERNAL_REVIEWER_DECISION_BOUNDARY.md      # DB-free internal reviewer decision-planning boundary (Phase 32)
│   ├── INTERNAL_REVIEWER_DECISION_GOVERNANCE_POLICY.md # Reviewer-decision governance: intents, routing, no approval (Phase 32)
│   └── IMPLEMENTATION_PLAN.md
├── peak/                         # Python tooling layer (source only; no data)
│   ├── db/                       # base, enums, models, session + agent_run (P20), evidence (P21), review (P22), source-ingestion (P24), agent-task-queue (P27) & review-bundle (P30) writers
│   ├── agentnet/                 # Governance wrapper for the AgentNet MCP connector (no calls)
│   ├── agents/                   # Agent execution harness (mock) + agent run persistence mapping (no live DB)
│   ├── workers/                  # Production-shaped workers (evidence normalization; review-gated)
│   ├── review/                   # QA / review gate + review persistence boundary (no-side-effect)
│   ├── persistence/              # Controlled DB writer boundary: allowlist + governance (no live DB)
│   ├── evidence/                 # Evidence persistence mapping: Phase 14 → Phase 17 (no live DB)
│   ├── ingestion/                # Engagement packet ingestion boundary: derives plans (no DB writes)
│   ├── orchestration/            # Controlled packet-processing orchestrator: sequences existing boundaries (P25; plan-only default)
│   ├── task_queue/               # Agent task queue / execution readiness boundary: plans queue drafts (P26; DB-free, no execution)
│   ├── review_orchestration/     # Packet-derived review orchestration: plans human-review bundles (P29; DB-free, no approval)
│   └── reviewer_decisions/       # Internal reviewer decision boundary: plans decision drafts + routing (P32; DB-free, no approval)
├── alembic/                      # Alembic migrations (schema only; no data)
├── alembic.ini                   # Alembic config (URL from env, not the repo)
├── .env.example                  # Env placeholders only (PEAK_DATABASE_URL); .env ignored
├── agents/                       # One folder per agent capability group
│   ├── intake/                   # New client intake
│   ├── discovery/                # Assessment planning, interviews, walk-around
│   ├── evidence/                 # Evidence normalization
│   ├── reporting/                # Management report generation
│   ├── proposal/                 # Quick wins + next-phase proposals
│   ├── qa/                       # Internal QA / governance review
│   └── learning/                 # Reusable knowledge capture
├── schemas/                      # Data object schemas (JSON Schema, draft 2020-12)
├── prompts/                      # Prompt contracts (one per workflow)
├── tools/                        # Local human-in-the-loop helpers (no LLM/API)
├── tests/                        # Validation harnesses (synthetic fixtures, no data)
├── Makefile                      # Convenience commands (validate, packet-summary)
└── requirements-dev.txt          # Dev-only dependencies (validation harness)
```

No `examples/` directory: the repo stores **source assets only** and no data
artifacts. Validation generates synthetic fixtures at runtime (see
[`docs/FIXTURE_STRATEGY.md`](docs/FIXTURE_STRATEGY.md)).

## Validating

The schemas, prompts, and tools ship with lightweight validation harnesses that build
**synthetic fixtures at runtime** — no stored example data. This machine uses `python3`
(there is no bare `python`):

```bash
make install-dev   # install dev deps (python3 -m pip install -r requirements-dev.txt)
make validate      # run all harnesses
```

`make validate` exits 0 on success. See [`tests/README.md`](tests/README.md).

## Using a packet (human-in-the-loop)

A read-only helper summarizes an `EngagementPacket` and points you to the right
prompt contracts. It makes **no LLM, API, database, AgentNet, or network call**, and
**stores nothing** — the consultant runs the LLM by hand and owns the output.

```bash
# --packet is required; point it at a real packet in controlled engagement storage:
python3 tools/packet_runner.py --packet /path/to/engagement-packet.json
make packet-summary PACKET=/path/to/engagement-packet.json
```

There is no demo/sample packet — the repo stores none. See
[`tools/README.md`](tools/README.md). For the full step-by-step consultant process, see
[`docs/CONSULTANT_WORKFLOW.md`](docs/CONSULTANT_WORKFLOW.md).

## Data handling (read before using real material)

This is a **private, internal Peak project — not open source**, with no outside
developer access. The repository holds **source assets only** (Peak docs, schemas,
prompt contracts, tools, tests, policy) — it stores **no data artifacts**: no client
data, no committed fixtures, no sample packets or outputs. Validation uses **synthetic
fixtures generated at runtime**.

Collected client data is **private engagement data**, handled only for authorized live
engagements. It lives in **controlled engagement database/storage and private resolver
capsules — not Git** — and is never used for examples, fixtures, tests, demos, or
training. No external publication, cross-client reuse, or AgentNet publication happens
without explicit governance approval. This is an internal, pre-legal policy; it does not
claim legal compliance.

- [`docs/DATA_HANDLING_POLICY.md`](docs/DATA_HANDLING_POLICY.md) — source-assets-only
  rule, controlled engagement storage, resolver capsules, secrets, retention, human
  review, AgentNet status, LLM-usage caution.
- [`docs/FIXTURE_STRATEGY.md`](docs/FIXTURE_STRATEGY.md) — synthetic fixtures at
  runtime; no stored data; real client data never used for fixtures/tests/demos.

## Controlled data architecture (where real data lives)

Real engagement data lives **outside this repo**, in controlled engagement storage and
private resolver capsules. This is **architecture documentation only** — no database,
API, resolver, ingestion pipeline, or AgentNet integration is implemented.

- [`docs/CONTROLLED_DATA_ARCHITECTURE.md`](docs/CONTROLLED_DATA_ARCHITECTURE.md) —
  repo-vs-data layers, the classification model, and the architecture diagram.
- [`docs/ENGAGEMENT_DATA_MODEL.md`](docs/ENGAGEMENT_DATA_MODEL.md) — the controlled-storage
  data model (incl. `FinancialImpactEstimate`); architecture, not a DB migration.
- [`docs/RESOLVER_CAPSULE_ARCHITECTURE.md`](docs/RESOLVER_CAPSULE_ARCHITECTURE.md) —
  private resolver capsules as the governed grounding layer (intended future).
- [`docs/SOURCE_SYSTEM_CAPSULIZATION.md`](docs/SOURCE_SYSTEM_CAPSULIZATION.md) — the
  source→capsule path (intended future).

Architecture-contract schemas (shapes only, no committed instances):
`engagement-record`, `financial-impact-estimate`, `source-system-reference`,
`resolver-capsule-record`.

## Governance states (authorization, review, lifecycle)

Governance state families define the allowed statuses, transitions, and human-review
gates for engagement records, evidence, financial estimates, resolver capsules, source
systems, and client-facing approval — so future agents create drafts, label evidence,
distinguish reported vs. verified, and never approve client-facing output on their own.
Enum contracts only; no stored data.

- [`docs/GOVERNANCE_STATES.md`](docs/GOVERNANCE_STATES.md) — the eight state families.
- [`docs/STATE_TRANSITIONS.md`](docs/STATE_TRANSITIONS.md) — allowed transitions and
  agent guardrails.
- Schemas: `governance-state` (master), `authorization-scope`, `review-status`,
  `lifecycle-status`.

## Controlled database (planning)

Peak plans a **controlled engagement database** as the system of record for live data —
serving immediate consulting delivery **and** progressive AI-readiness (a
pre-capsulization staging layer). **Planning only — no database, migrations, DB config,
API, or resolver code**; the repo stays source-only and client data never enters Git.

- [`docs/DATABASE_IMPLEMENTATION_PLAN.md`](docs/DATABASE_IMPLEMENTATION_PLAN.md) — staged
  plan (Phase 10 plan → 11 scaffold → 12 capsule adapter → 13 agent harness → later
  ingestion); no vendor/SQL yet.
- [`docs/DATABASE_RECORD_MODEL.md`](docs/DATABASE_RECORD_MODEL.md) — planned record
  groups (no records).
- [`docs/DATABASE_ACCESS_AND_AUDIT.md`](docs/DATABASE_ACCESS_AND_AUDIT.md) — roles, audit
  fields, human-review gates, agent permission limits.
- [`docs/DATABASE_TO_RESOLVER_MAPPING.md`](docs/DATABASE_TO_RESOLVER_MAPPING.md) — how
  records become resolver-capsule candidates; **public-but-segregated** (governed, not
  public disclosure) and **private resolver** options.

### Scaffold (Phase 11)

The controlled database targets **MySQL**, with a Python tooling layer (**SQLAlchemy +
Alembic + PyMySQL**). Phase 11 adds **source assets only** — models, enum contracts, and
an Alembic migration that defines **schema structure only**. **No data, no credentials,
no database files** are committed; the connection URL comes from `PEAK_DATABASE_URL`
(see `.env.example`). See [`docs/DATABASE_SCAFFOLD.md`](docs/DATABASE_SCAFFOLD.md).

```bash
make db-check                              # validate the scaffold (structural; stdlib-only)
python3 -m pip install -r requirements.txt # SQLAlchemy/alembic/PyMySQL (to run migrations)
cp .env.example .env                       # then set a real PEAK_DATABASE_URL (never committed)
alembic upgrade head                       # create schema in a real MySQL (no data)
```

## AgentNet grounding (intended architecture)

AgentNet is described throughout this repository as the **intended grounding and
resolution layer**. It is the mechanism by which agent outputs are meant to be
anchored to Peak's methodology, prior engagements, and evidence standards.

**AgentNet integration is not yet implemented.** Wherever grounding is referenced,
treat it as target architecture unless a file explicitly states it is live.

### AgentNet MCP boundary (Phase 12)

There is an **existing AgentNet MCP connector** (a separate repo) that forwards MCP tool
calls to an AgentNet-compatible resolver. Peak does **not** reimplement or copy it —
instead Peak adds its own **governance wrapper** around *future* connector use. Phase 12
is scaffold/contracts only: it makes **no live calls**, and **AgentNet integration is not
complete**. Capsule publication strategy is deferred to a later phase.

- [`peak/agentnet/`](peak/agentnet/) — request/response contracts, deterministic
  governance guard checks, and a **no-network mock boundary** (never calls the connector,
  reads no credentials, opens no socket).
- [`docs/AGENTNET_MCP_BOUNDARY.md`](docs/AGENTNET_MCP_BOUNDARY.md) — the boundary and the
  three known tools (`agentnet.resolve`, `agentnet.resolve_history`,
  `agentnet.validate_capsule`).
- [`docs/PEAK_RESOLVER_ACCESS_POLICY.md`](docs/PEAK_RESOLVER_ACCESS_POLICY.md) — who/what
  may request resolver context, scoping, allowed tools, prohibited actions, and the
  governance states checked before access.

```bash
make validate-phase12   # AgentNet MCP boundary check (stdlib-only; no network)
```

### Agent execution harness (Phase 13)

A **scaffold** for how future Peak internal agents/workers will be **invoked, governed,
and recorded** — with **no live execution**. Nothing here calls an LLM, AgentNet, an MCP
connector, a resolver, a database, or the network, and nothing creates client-facing
output. Governance forces agent output to `draft` / `needs_review`; agents never
self-approve, publish capsules, or verify financial impact.

- [`peak/agents/`](peak/agents/) — task/result contracts, a static registry of the 10
  known agents/workers, deterministic governance checks, a **no-op mock executor**, and a
  **mock LLM** (live execution disabled).
- [`docs/AGENT_EXECUTION_HARNESS.md`](docs/AGENT_EXECUTION_HARNESS.md) — how tasks are
  governed, how prompt contracts are selected, and how the Phase 12 resolver boundary fits.
- [`docs/AGENT_RUN_RECORDS.md`](docs/AGENT_RUN_RECORDS.md) — the future `AgentRunRecord`
  shape (nothing is stored in this phase).

```bash
make validate-phase13   # agent-execution-harness check (stdlib-only; no execution)
```

### Evidence Normalization Worker (Phase 14)

The first **production-shaped** worker. It turns a raw evidence reference into a
structured, **review-gated** normalized evidence record — output whose *shape* fits the
controlled data architecture, but whose *status* is always gated (`draft` /
`needs_review`, `authoritative = false`, `client_facing_approved = false`). Normalization
is deterministic: **no live LLM call, no AgentNet call, no database write, no network
call, no client-facing output, no capsule publication**. A record is not authoritative
merely because a worker created it.

- [`peak/workers/`](peak/workers/) — worker contracts, deterministic normalization
  helpers, and governance guards.
- [`docs/EVIDENCE_NORMALIZATION_WORKER.md`](docs/EVIDENCE_NORMALIZATION_WORKER.md) — design,
  inputs, output categories, and boundaries.
- [`docs/EVIDENCE_RECORD_LIFECYCLE.md`](docs/EVIDENCE_RECORD_LIFECYCLE.md) — raw → normalized
  draft → reviewed → (future) capsule candidate.

```bash
make validate-phase14   # evidence-normalization-worker check (stdlib-only; deterministic)
```

### QA / Review Gate (Phase 15)

How Peak evaluates worker/agent outputs (the Phase 14 evidence drafts and future outputs)
for **internal** approval, rejection, return for revision, supersession, or continued
review. Decisions are **production-shaped but no-side-effect**: the gate persists nothing
and confers no final authority. `approve_internal` means **internal reliance only** —
client-facing approval, financial-impact verification, and capsule publication remain
separate future gates (`client_facing_approved` and `capsule_candidate_ready` stay
`false`). **No live LLM call, no AgentNet call, no database write, no network call, no
client-facing output, no stored review records.**

- [`peak/review/`](peak/review/) — review contracts, deterministic governance guards, and
  a no-side-effect review-gate evaluator.
- [`docs/QA_REVIEW_GATE.md`](docs/QA_REVIEW_GATE.md) — purpose, how it complements Phase 14,
  and the future relationship to a controlled-DB `ReviewRecord`.
- [`docs/REVIEW_DECISION_MODEL.md`](docs/REVIEW_DECISION_MODEL.md) — allowed vs. prohibited
  decisions, the `approve_internal` checklist, and per-decision state effects.

```bash
make validate-phase15   # QA / review-gate check (stdlib-only; no-side-effect)
```

### Review Persistence Boundary (Phase 16)

How a **permitted** Phase 15 review outcome will later be persisted as a controlled-DB
`ReviewRecord` — described precisely, but **not executed**. Phase 16 is **DB-aware but not
DB-writing**: it maps a `ReviewGateResult` into a production-shaped `ReviewRecordDraft` and
a no-op `ReviewWritePlan` (target table `review_records`), but opens no database session,
imports no SQLAlchemy / `peak.db`, and writes nothing. `review_record_id` and `created_at`
stay `None` for a **future controlled DB writer**. **No live database read/write, no
database connection, no stored review records, no live LLM/AgentNet/network call, no
client-facing approval, no financial verification, no capsule publication.**

The critical scope rule: a DB-backed review must compare `request.authorization_scope`
against the subject record's **stored** scope (`stored_authorization_scope`) — owner/client/
engagement matching is necessary but not sufficient. Implemented now with an in-memory
`StoredReviewSubjectSnapshot`.

- [`peak/review/`](peak/review/) — persistence contracts, deterministic persistence-readiness
  governance, and review-record mapping / write-plan helpers.
- [`docs/REVIEW_PERSISTENCE_BOUNDARY.md`](docs/REVIEW_PERSISTENCE_BOUNDARY.md) — the boundary,
  what is planned vs. executed, and the future controlled-DB writer.
- [`docs/DB_BACKED_REVIEW_SCOPE_POLICY.md`](docs/DB_BACKED_REVIEW_SCOPE_POLICY.md) — the
  stored-scope comparison rule, denial behavior, and audit expectations.

```bash
make validate-phase16   # review-persistence-boundary check (stdlib-only; DB-aware, not DB-writing)
```

### Controlled DB Writer Boundary (Phase 17)

The generic policy and validation boundary every **future** controlled database write must
pass through — defined precisely, but **not executed**. Phase 17 is **DB-aware but not
DB-writing**: a `ControlledWriteRequest` is checked against a **table/action allowlist** and
governance (identity, subject stored-scope comparison, lifecycle, prohibited effects), then
mapped to a no-op `ControlledWritePlan` and an in-memory `ControlledWriteAuditDraft`. It
opens **no live database connection**, runs **no SQL execution**, and creates **no stored
records**. Kept in `peak/persistence/` (not `peak/db/`) so it stays stdlib-only and imports
no SQLAlchemy / Alembic / `peak.db`.

Enforced at the boundary: `request.authorization_scope` must equal the subject's stored
`stored_authorization_scope` (owner/client/engagement matching is necessary but not
sufficient); an `idempotency_key` is required; and prohibited tables/actions (`clients`,
`engagements`, `financial_impact_estimates`, `resolver_capsule_records`, and any
publish / client-facing-approve / verify-financial / delete / migrate / seed / raw_sql
action) are denied. **No client-facing approval, no financial verification, no capsule
publication, no credentials/secrets, no deletes/migrations, no live LLM/AgentNet/network
call.** A write plan is not a write.

- [`peak/persistence/`](peak/persistence/) — controlled-write contracts, the table/action
  allowlist, deterministic write governance, and no-op write-plan helpers.
- [`docs/CONTROLLED_DB_WRITER_BOUNDARY.md`](docs/CONTROLLED_DB_WRITER_BOUNDARY.md) — the
  boundary, what is planned vs. executed, and the future controlled DB writer.
- [`docs/CONTROLLED_WRITE_ALLOWLIST.md`](docs/CONTROLLED_WRITE_ALLOWLIST.md) — allowed vs.
  prohibited tables/actions and how the allowlist may expand through governance gates.

```bash
make validate-phase17   # controlled-DB-writer-boundary check (stdlib-only; DB-aware, not DB-writing)
```

### Evidence Persistence Mapping (Phase 18)

Connects the Phase 14 normalized evidence output to the Phase 17 controlled writer boundary
— defined precisely, but **not executed**. Phase 18 is **DB-aware but not DB-writing**: it
maps a `NormalizedEvidenceRecord` into a production-shaped but **review-gated**
`EvidencePersistenceDraft` and routes it through Phase 17 as a no-op plan targeting
`evidence_references` / `create_draft`. The draft's `evidence_record_id` and `created_at`
stay `None` for a **future controlled DB writer**; the review gate (`draft` /
`needs_review`, non-authoritative, not client-facing, not a capsule candidate) is preserved.
**Evidence workers still do not write directly to the DB.**

```
NormalizedEvidenceRecord → EvidencePersistenceDraft → ControlledWriteSubject
  → ControlledWriteRequest → ControlledWritePlan → no DB write
```

Enforced: `request.authorization_scope` must equal the parent subject snapshot's stored
`stored_authorization_scope` (owner/client/engagement matching is necessary but not
sufficient); an `idempotency_key` is required; and the carried normalization output must be
permitted, side-effect-free, and still review-gated. **No live database connection, no SQL
execution, no stored records, no live LLM/AgentNet/network call, no client-facing approval,
no financial verification, no capsule publication.** A write plan is not a write.

- [`peak/evidence/`](peak/evidence/) — evidence persistence contracts, deterministic mapping
  governance, and evidence-to-controlled-write mapping helpers (bridging Phase 14 ↔ Phase 17).
- [`docs/EVIDENCE_PERSISTENCE_MAPPING.md`](docs/EVIDENCE_PERSISTENCE_MAPPING.md) — the core
  flow, what is mapped vs. executed, and the future controlled DB writer.
- [`docs/EVIDENCE_WRITE_PLAN_POLICY.md`](docs/EVIDENCE_WRITE_PLAN_POLICY.md) — idempotency,
  stored-scope, and the parent-subject authorization anchor.

```bash
make validate-phase18   # evidence-persistence-mapping check (stdlib-only; DB-aware, not DB-writing)
```

### Agent Run Persistence Mapping (Phase 19)

Connects the Phase 13 agent run output to the Phase 17 controlled writer boundary — defined
precisely, but **not executed**. Phase 19 is **DB-aware but not DB-writing**: it maps an
`AgentTaskResult` + `AgentRunDraft` into a production-shaped but **review-gated**
`AgentRunPersistenceDraft` and routes it through Phase 17 as a no-op plan targeting
`agent_run_records` / `create_agent_run_record`. The draft's `agent_run_record_id` and
`created_at` stay `None` for a **future controlled DB writer**; the no-side-effect posture
(`draft` / `needs_review`, every "a call was made" flag false) is preserved. **Agent
execution still does not write directly to the DB.**

```
AgentTaskResult / AgentRunDraft → AgentRunPersistenceDraft → ControlledWriteSubject
  → ControlledWriteRequest → ControlledWritePlan → no DB write
```

Enforced: `request.authorization_scope` must equal the stored subject snapshot's
`stored_authorization_scope` (owner/client/engagement matching is necessary but not
sufficient); an `idempotency_key` is required; and the carried agent output must be permitted,
side-effect-free, and still review-gated. **No live database connection, no SQL execution, no
stored records, no live LLM/AgentNet/network call, no client-facing output, no financial
verification, no capsule publication.** A write plan is not a write.

- [`peak/agents/`](peak/agents/) — agent run persistence contracts, deterministic mapping
  governance, and agent-run-to-controlled-write mapping helpers (bridging Phase 13 ↔ Phase 17).
- [`docs/AGENT_RUN_PERSISTENCE_MAPPING.md`](docs/AGENT_RUN_PERSISTENCE_MAPPING.md) — the core
  flow, what is mapped vs. executed, and the future controlled DB writer.
- [`docs/AGENT_RUN_WRITE_PLAN_POLICY.md`](docs/AGENT_RUN_WRITE_PLAN_POLICY.md) — idempotency,
  stored-scope, and the stored-subject authorization anchor.

```bash
make validate-phase19   # agent-run-persistence-mapping check (stdlib-only; DB-aware, not DB-writing)
```

### Agent Run Controlled Writer (Phase 20)

The **first real DB-backed persistence path**: a narrow controlled writer that creates
review-gated `agent_run_records` rows from the Phase 19 output. It is not a generic CRUD
repository — it allows exactly `agent_run_records` / `create_agent_run_record` and nothing
else. At **write-time** it loads the authoritative stored authorization subject (the
`Engagement` row) from the database and requires `request.authorization_scope ==
engagement.authorization_scope`; identity matching is necessary but not sufficient. It
enforces DB-level idempotency (unique index over owner/client/engagement/idempotency_key),
distinguishing `created`, `idempotent_replay`, `denied`, `failed_before_write`, and
`write_outcome_uncertain`, and returns a typed `AgentRunWriteReceipt`. It performs **no LLM,
AgentNet, connector, external network, client-facing, financial, or capsule-publication side
effect**, and never updates or deletes. The Phase 19 agent-domain mapper stays DB-free.

- [`peak/db/agent_run_writer.py`](peak/db/agent_run_writer.py) — the controlled writer.
- [`peak/db/writer_contracts.py`](peak/db/writer_contracts.py) — the typed receipt + outcomes.
- [`alembic/versions/002_agent_run_idempotency.py`](alembic/versions/002_agent_run_idempotency.py)
  — additive migration (idempotency key, payload fingerprint, unique index; no data).
- [`docs/AGENT_RUN_CONTROLLED_WRITER.md`](docs/AGENT_RUN_CONTROLLED_WRITER.md) and
  [`docs/AGENT_RUN_IDEMPOTENCY_POLICY.md`](docs/AGENT_RUN_IDEMPOTENCY_POLICY.md).

```bash
# DB-backed suite (uses the local .venv with SQLAlchemy; builds a temporary SQLite database):
make validate-phase20 PYTHON=.venv/bin/python
# On plain python3 (no SQLAlchemy) the DB layer is skipped and the structural checks run:
make validate-phase20
```

### Evidence Controlled Writer (Phase 21)

The **second DB-backed writer**, applying the Phase 20 pattern to `evidence_references`. It
persists exactly one review-gated evidence row from a Phase 18 `EvidencePersistenceDraft`
routed through the Phase 17 `ControlledWriteRequest` boundary — allowing only
`evidence_references` / `create_draft`. At **write-time** it loads the authoritative stored
`Engagement` row and requires `request.authorization_scope == engagement.authorization_scope`
(identity matching necessary but not sufficient); enforces DB-level idempotency (unique index
over owner/client/engagement/idempotency_key + payload fingerprint), distinguishing `created`,
`idempotent_replay`, `denied`, `failed_before_write`, and `write_outcome_uncertain`; and
returns a typed `EvidenceWriteReceipt`. Required posture: `output_status=draft`,
`review_status=needs_review`, `lifecycle_status=active`, non-authoritative, not
client-facing-approved, not a capsule candidate. It performs **no LLM, AgentNet, connector,
external network, client-facing approval, financial verification, or capsule-publication side
effect**, and never updates or deletes. The Phase 18 evidence-domain mapper stays DB-free.

- [`peak/db/evidence_writer.py`](peak/db/evidence_writer.py) — the controlled writer.
- [`alembic/versions/003_evidence_idempotency.py`](alembic/versions/003_evidence_idempotency.py)
  — additive migration (idempotency key, payload fingerprint, unique index; no data).
- [`docs/EVIDENCE_CONTROLLED_WRITER.md`](docs/EVIDENCE_CONTROLLED_WRITER.md) and
  [`docs/EVIDENCE_IDEMPOTENCY_POLICY.md`](docs/EVIDENCE_IDEMPOTENCY_POLICY.md).

```bash
make validate-phase21 PYTHON=.venv/bin/python   # full DB-backed suite (temporary SQLite)
make validate-phase21                           # structural only on plain python3
```

### Review Record Controlled Writer (Phase 22)

The **third DB-backed writer**, applying the same pattern to `review_records`. It persists
exactly one review row from a Phase 16 `ReviewRecordDraft` routed through the Phase 17
`ControlledWriteRequest` boundary — allowing only `review_records` / `create_review_record`.
At **write-time** it loads the authoritative stored `Engagement` row and requires
`request.authorization_scope == engagement.authorization_scope` (identity matching necessary
but not sufficient); enforces DB-level idempotency (unique index over
owner/client/engagement/idempotency_key + payload fingerprint); distinguishes `created`,
`idempotent_replay`, `denied`, `failed_before_write`, and `write_outcome_uncertain`; and
returns a typed `ReviewWriteReceipt`. Decision posture: `approve_internal` means internal
reliance only (may set `authoritative=true` only when `next_review_status=approved_internal`,
never client-facing); `reject`/`return_for_revision`/`supersede`/`keep_needs_review` must be
non-authoritative; `client_facing_approve`/`verify_financial_impact`/`publish_capsule` are
rejected. It performs **no LLM, AgentNet, connector, external network, client-facing approval,
financial verification, or capsule-publication side effect**, and never updates or deletes.
The Phase 16 review-domain mapper stays DB-free.

- [`peak/db/review_writer.py`](peak/db/review_writer.py) — the controlled writer.
- [`alembic/versions/004_review_idempotency.py`](alembic/versions/004_review_idempotency.py)
  — additive migration (decision/authoritative/output_status columns, idempotency key, payload
  fingerprint, unique index; no data).
- [`docs/REVIEW_CONTROLLED_WRITER.md`](docs/REVIEW_CONTROLLED_WRITER.md) and
  [`docs/REVIEW_IDEMPOTENCY_POLICY.md`](docs/REVIEW_IDEMPOTENCY_POLICY.md).

```bash
make validate-phase22 PYTHON=.venv/bin/python   # full DB-backed suite (temporary SQLite)
make validate-phase22                           # structural only on plain python3
```

### Engagement Packet Ingestion Boundary (Phase 23)

The controlled front door for external `EngagementPacket` material — an **ingestion
boundary, not a direct importer and not a DB writer**. It validates a packet's identity,
scope, and shape (rejecting credential/secret payloads), then derives **production-shaped but
review-gated** no-side-effect plans: a `SourceIngestionDraft`, Phase 14
`EvidenceNormalizationRequest` objects (from present sections), Phase 13 `AgentTaskRequest`
objects (known registry agents only, never executed, `llm_execution_allowed=false`), and
optionally a Phase 17 `ControlledWriteRequest` for `source_ingestion_records` — **a plan
only**. **No direct DB writes from packet ingestion**, no DB connection, no SQL, no stored
packet, no live LLM/AgentNet/network call, no client-facing approval, no financial
verification, no capsule publication. `source_ingestion_records` persistence awaits a future
narrow source ingestion writer.

```
EngagementPacket → validate → govern → SourceIngestionDraft + evidence requests
  + agent tasks + (optional) Phase 17 write plan → no DB writes
```

- [`peak/ingestion/`](peak/ingestion/) — ingestion contracts, deterministic packet governance,
  and packet-to-request mapping helpers (bridging to Phases 13/14/17, all DB-free).
- [`docs/ENGAGEMENT_PACKET_INGESTION_BOUNDARY.md`](docs/ENGAGEMENT_PACKET_INGESTION_BOUNDARY.md)
  and [`docs/PACKET_TO_CONTROLLED_WORKFLOW_POLICY.md`](docs/PACKET_TO_CONTROLLED_WORKFLOW_POLICY.md).

```bash
make validate-phase23   # engagement-packet-ingestion-boundary check (stdlib-only; no DB)
```

### Source Ingestion Record Controlled Writer (Phase 24)

The **fourth DB-backed writer**, applying the same pattern to `source_ingestion_records`. It
persists exactly one review-gated source ingestion row from a Phase 23 `SourceIngestionDraft`
routed through the Phase 17 `ControlledWriteRequest` boundary — allowing only
`source_ingestion_records` / `create_source_ingestion_record`. At **write-time** it loads the
authoritative stored `Engagement` row and requires `request.authorization_scope ==
engagement.authorization_scope` (identity matching necessary but not sufficient); enforces
DB-level idempotency (unique index over owner/client/engagement/idempotency_key + payload
fingerprint over packet **metadata only**); distinguishes `created`, `idempotent_replay`,
`denied`, `failed_before_write`, and `write_outcome_uncertain`; and returns a typed
`SourceIngestionWriteReceipt`. **Packet metadata only** is persisted (reference id, schema,
source type, location reference, hash) — never the full packet payload, raw content, or
secrets; a draft carrying `packet_payload` / `raw_packet_content` / a secret-like attribute is
rejected. Required posture: `output_status=draft`, `review_status=needs_review`,
`lifecycle_status=active`, non-authoritative, not client-facing, not a capsule candidate. **No
LLM, AgentNet, connector, external network, client-facing approval, financial verification, or
capsule-publication side effect**, and never updates or deletes. The Phase 23 ingestion
package stays DB-free.

- [`peak/db/source_ingestion_writer.py`](peak/db/source_ingestion_writer.py) — the controlled writer.
- [`alembic/versions/005_source_ingestion_idempotency.py`](alembic/versions/005_source_ingestion_idempotency.py)
  — additive migration (idempotency key, payload fingerprint, output_status, unique index; no data).
- [`docs/SOURCE_INGESTION_CONTROLLED_WRITER.md`](docs/SOURCE_INGESTION_CONTROLLED_WRITER.md) and
  [`docs/SOURCE_INGESTION_IDEMPOTENCY_POLICY.md`](docs/SOURCE_INGESTION_IDEMPOTENCY_POLICY.md).

```bash
make validate-phase24 PYTHON=.venv/bin/python   # full DB-backed suite (temporary SQLite)
make validate-phase24                           # structural only on plain python3
```

### Controlled Packet Processing Orchestrator (Phase 25)

A **controlled sequencing layer** over the existing narrow boundaries — **not** a generic
importer, workflow engine, CRUD layer, or write dispatcher. `process_engagement_packet` accepts
a Phase 23 `PacketIngestionRequest`, routes it through the Phase 23 ingestion boundary, exposes
the derived plan (source ingestion draft, plan-only source `ControlledWriteRequest`, Phase 14
evidence requests, Phase 13 agent task requests), and — **only when explicitly requested and a
`session_factory` is supplied** — persists through the existing narrow DB writers (Phase 24
source-ingestion, Phase 21 evidence). It adds no table, no migration (head stays
`005_source_ingestion_idem`), no generic writer, and no raw SQL.

- **Plan-only is the default and no-side-effect** — every side-effect flag on the receipt is
  `false`; it calls no DB writer, no agent/LLM, no AgentNet/MCP/resolver, no network.
- **No stage may silently escalate from plan-only to persistence** — a persistence stage that is
  not included, or is requested while `plan_only=true`, or has no `session_factory`, is *skipped*
  with a specific reason (`skipped_not_requested` / `skipped_plan_only` /
  `skipped_missing_session_factory`), never a silent write.
- **Orchestrator preflight checks are helpful but not authoritative**: **stored Engagement
  authorization remains authoritative** for every DB write and is enforced inside the narrow
  writers at write-time. **Identity matching is necessary but not sufficient.**
- It **never stores or echoes raw packet payload content** in receipts, logs, docs, exceptions,
  or persistence receipts — only counts, ids, stage names, safe metadata, warnings, reason codes.
- Agent-run persistence (Phase 19/20) is intentionally deferred (`skipped_no_safe_contract_path`),
  since it would require running the Phase 13 mock executor; partial safe orchestration is
  preferable to unsafe breadth. **AgentNet integration is not complete.**
- Deterministic per-stage outcomes: `completed`, `skipped_not_requested`, `skipped_plan_only`,
  `skipped_missing_session_factory`, `skipped_no_safe_contract_path`, `denied`,
  `failed_before_write`, `write_outcome_uncertain`. A persistence stage reports `completed` only
  when a narrow writer actually created or replayed a row — never for merely producing a plan.

- [`peak/orchestration/`](peak/orchestration/) — orchestration contracts, deterministic preflight
  governance, and the `process_engagement_packet` sequencer (DB writers imported lazily).
- [`docs/CONTROLLED_PACKET_PROCESSING_ORCHESTRATOR.md`](docs/CONTROLLED_PACKET_PROCESSING_ORCHESTRATOR.md)
  and [`docs/PACKET_PROCESSING_ORCHESTRATION_POLICY.md`](docs/PACKET_PROCESSING_ORCHESTRATION_POLICY.md).

```bash
make validate-phase25 PYTHON=.venv/bin/python   # structural + plan-only + DB-backed (temporary SQLite)
make validate-phase25                           # structural + plan-only on plain python3 (DB layer skipped)
```

### Controlled Agent Task Queue / Execution Readiness Boundary (Phase 26)

A **readiness/queue-planning boundary** over derived Phase 13 `AgentTaskRequest` objects — **not**
an executor, task runner, job queue, workflow engine, or DB writer. `prepare_agent_task_queue_plan`
turns those tasks into governed, **review-gated**, **not executed** Agent Task Queue drafts and
Execution Readiness assessments, plus optional plan-only Phase 17 controlled write requests for a
*future* `agent_task_queue_records` writer. It is deliberately analogous to Phase 23 (which
prepared source-ingestion plans without DB writes): Phase 26 prepares task-queue / readiness plans
without DB writes. It adds no table and no migration (Alembic head stays `005_source_ingestion_idem`).

- It executes **no agent** (live or mock), makes **no live LLM** / MockLLM / **AgentNet** / MCP /
  resolver / network call, opens **no DB** connection, and writes no row; it creates no
  client-facing output, verifies no financial impact, and publishes no capsule. Every side-effect
  flag on the result stays `false`.
- Each queue draft is review-gated and non-executed: `agent_task_queue_record_id=None`,
  `output_status=draft`, `review_status=needs_review`, `execution_status=not_executed`,
  `execution_allowed=false`, `requires_human_review=true`, and carries only ids/references (never
  raw payload/text). Its idempotency key is deterministic per task
  (`<key>::taskq::<index>::<agent_name>`).
- Deterministic readiness states: `queued_for_review`, `blocked_by_policy`,
  `blocked_missing_evidence`, `blocked_unknown_agent`, `blocked_invalid_scope`,
  `blocked_lifecycle`, `ready_for_future_controlled_execution`. **"Ready" never means "execute
  now"** — it means structurally ready for a later controlled execution phase after review.
- Governance rejects unknown agents, identity/scope/lifecycle mismatches, live-execution / LLM /
  resolver / client-facing requests, and any raw-content / secret / execution-intent field
  (reporting key names only — secret and raw values are never echoed). **Identity matching is
  necessary but not sufficient.**
- **Phase 25 integration** is by documented handoff (Phase 25 code unchanged): Phase 26 consumes
  the same Phase 13 `AgentTaskRequest` objects Phase 25 surfaces on its receipt. A future Phase 27
  may add the narrow `agent_task_queue_records` DB writer.

- [`peak/task_queue/`](peak/task_queue/) — queue/readiness contracts, deterministic governance,
  and the `prepare_agent_task_queue_plan` mapper (DB-free; no execution).
- [`docs/AGENT_TASK_QUEUE_READINESS_BOUNDARY.md`](docs/AGENT_TASK_QUEUE_READINESS_BOUNDARY.md) and
  [`docs/AGENT_TASK_QUEUE_GOVERNANCE_POLICY.md`](docs/AGENT_TASK_QUEUE_GOVERNANCE_POLICY.md).

```bash
make validate-phase26   # agent-task-queue / execution-readiness check (stdlib-only; DB-free)
```

### Agent Task Queue Controlled Writer (Phase 27)

The **fifth** DB-backed writer, applying the Phase 20–24 pattern to `agent_task_queue_records`.
It persists **exactly one** review-gated, **not-executed** queue row from a Phase 26
`AgentTaskQueueDraft` routed through the Phase 17 `ControlledWriteRequest` boundary — allowing
only `agent_task_queue_records` / `create_agent_task_queue_record`. At **write-time** it loads the
authoritative stored `Engagement` row and requires `request.authorization_scope ==
engagement.authorization_scope` (identity matching necessary but not sufficient); enforces
DB-level idempotency (unique index over owner/client/engagement/idempotency_key + payload
fingerprint); distinguishes `created` / `idempotent_replay` / `denied` / `failed_before_write` /
`write_outcome_uncertain`; and returns a typed `AgentTaskQueueWriteReceipt`.

It **executes no agent** (live or mock), makes **no LLM / MockLLM / AgentNet / MCP / resolver /
connector / network call**, and **never creates an `agent_run_records` row**. Required posture:
`output_status=draft`, `review_status=needs_review`, `lifecycle_status=draft`,
`execution_status=not_executed`, `execution_allowed=false` (and `llm_execution_allowed` /
`agentnet_context_allowed` / `resolver_context_allowed` / `network_allowed` all false),
`requires_human_review=true`, non-authoritative, not client-facing, not a capsule candidate. Only
safe references/summaries are stored (never raw packet/evidence/interview content, source bytes,
generated output, or secrets); a draft carrying such an attribute is rejected without echoing the
value. Agent identity is gated against the Phase 13 registry — unknown agents are never persisted.

- [`peak/db/agent_task_queue_writer.py`](peak/db/agent_task_queue_writer.py) — the controlled writer.
- [`alembic/versions/006_agent_task_queue_records.py`](alembic/versions/006_agent_task_queue_records.py)
  — additive migration creating the single new table (down_revision `005_source_ingestion_idem`;
  single linear head `006_agent_task_queue_records`; no data).
- [`docs/AGENT_TASK_QUEUE_CONTROLLED_WRITER.md`](docs/AGENT_TASK_QUEUE_CONTROLLED_WRITER.md) and
  [`docs/AGENT_TASK_QUEUE_IDEMPOTENCY_POLICY.md`](docs/AGENT_TASK_QUEUE_IDEMPOTENCY_POLICY.md).

```bash
make validate-phase27 PYTHON=.venv/bin/python   # full DB-backed suite (temporary SQLite)
make validate-phase27                           # structural only on plain python3
```

### Packet → Task Queue Orchestration Integration (Phase 28)

Wires the Phase 26 task queue / execution readiness boundary and the Phase 27 narrow writer into
the Phase 25 packet processor. It is an **orchestration integration phase, not a new writer
phase** — no new table, no migration (head stays `006_agent_task_queue_records`; still 12 tables),
no new writer. The orchestrator now routes the Phase 13 `AgentTaskRequest` objects it already
derives through Phase 26 `prepare_agent_task_queue_plan` and, only when explicitly requested,
persists the results through Phase 27.

- **Plan-only (default):** exposes `task_queue_drafts`, `task_queue_readiness_assessments`,
  `task_queue_controlled_write_requests` and their counts — review-gated, **not-executed** — with
  every side-effect flag `false` (queue readiness is DB-free and execution-free).
- **Controlled persistence:** only when `plan_only=false`, `include_agent_task_queue_persistence=true`,
  and a `session_factory` is supplied does it call **only** `persist_agent_task_queue_record`
  (Phase 27), attach the write receipts, and aggregate DB flags from actual writer calls;
  idempotent replay and conflict flow through Phase 27. No option silently escalates plan-only.
- **No execution:** never executes an agent, calls the Phase 13 executor / MockLLM / a live LLM /
  AgentNet / MCP / resolver / connector / network, and **never creates an `agent_run_records`
  row**. Agent task queue persistence is not execution.
- **Authorization:** orchestrator preflight is advisory; **stored `Engagement` authorization
  remains authoritative** inside the Phase 27 writer (identity necessary but not sufficient).

- [`peak/orchestration/packet_processor.py`](peak/orchestration/packet_processor.py) — the two
  new stages (`agent_task_queue_readiness`, `agent_task_queue_persistence`).
- [`docs/PACKET_TO_TASK_QUEUE_ORCHESTRATION_INTEGRATION.md`](docs/PACKET_TO_TASK_QUEUE_ORCHESTRATION_INTEGRATION.md).

```bash
make validate-phase28 PYTHON=.venv/bin/python   # structural + plan-only + DB-backed (temporary SQLite)
make validate-phase28                           # structural + plan-only on plain python3 (DB layer skipped)
```

### Packet-Derived Review Orchestration Boundary (Phase 29)

A **DB-free review-planning boundary** that organizes packet-derived outputs (safe references,
receipts, metadata from prior phases) into **review-ready** plans for human reviewers — review
bundle drafts, review plan items, and review readiness assessments. It is analogous to Phase 26
(which planned task-queue readiness without DB writes): Phase 29 plans human-review readiness
without DB writes. It adds no table and no migration (head stays `006_agent_task_queue_records`;
still 12 tables), and produces **no** `ControlledWriteRequest` objects — future persistence is
deferred.

- **It is not an approval phase.** **"Ready for human review" never means approved.** It never
  performs `approve_internal`, creates client-facing output, verifies financial impact, publishes a
  capsule, executes an agent, or calls an LLM/MockLLM/AgentNet/MCP/resolver/network; it does not
  call or change the Phase 22 review writer and creates **no `review_records` row**. Every bundle
  stays `output_status=draft` / `review_status=needs_review` / `lifecycle_status=draft` with
  `approval_allowed=false` and `requires_human_review=true`. Every side-effect flag stays `false`.
- **Public entry point:** `prepare_packet_review_plan(request) -> PacketReviewOrchestrationResult`.
- **Item types:** `source_ingestion_review`, `evidence_reference_review`, `agent_task_queue_review`,
  `packet_processing_review`, `cross_stage_consistency_review`, `missing_evidence_review`,
  `readiness_exception_review`.
- **Readiness states:** `ready_for_human_review`, `blocked_no_subjects`, `blocked_invalid_scope`,
  `blocked_lifecycle`, `blocked_raw_content`, `blocked_secret_like_content`,
  `blocked_execution_intent`, `blocked_approval_intent`, `blocked_publication_intent`,
  `blocked_financial_verification_intent`.
- **Governance** rejects missing identity/scope/idempotency, subject scope mismatch (identity
  necessary but not sufficient), prohibited lifecycle, raw-content / secret-like fields, and
  approval / execution / client-facing / publication / financial-verification intent — reporting
  key names only (values never echoed).
- **Handoff (documented):** the Phase 25/28 packet processor can hand its receipt refs and task
  queue outputs (all safe references) into Phase 29; Phase 29 does not run inside Phase 25/28 and
  imports no Phase 27 writer / no Phase 22 writer / no `peak.db`.

- [`peak/review_orchestration/`](peak/review_orchestration/) — review-planning contracts,
  deterministic governance, and the `prepare_packet_review_plan` planner (stdlib-only).
- [`docs/PACKET_DERIVED_REVIEW_ORCHESTRATION_BOUNDARY.md`](docs/PACKET_DERIVED_REVIEW_ORCHESTRATION_BOUNDARY.md)
  and [`docs/REVIEW_ORCHESTRATION_GOVERNANCE_POLICY.md`](docs/REVIEW_ORCHESTRATION_GOVERNANCE_POLICY.md).

```bash
make validate-phase29   # packet-derived review orchestration boundary check (stdlib-only; DB-free)
```

### Review Bundle Controlled Writer (Phase 30)

The **sixth** DB-backed writer, the persistence counterpart to Phase 29. It persists **exactly
one** review-gated, **not-approved** `review_bundle_records` row from a Phase 29 `ReviewBundleDraft`
routed through the Phase 17 `ControlledWriteRequest` boundary — allowing only `review_bundle_records`
/ `create_review_bundle_record`. At **write-time** it loads the authoritative stored `Engagement`
row and requires `request.authorization_scope == engagement.authorization_scope` (identity
necessary but not sufficient); enforces DB-level idempotency (unique index over
owner/client/engagement/idempotency_key + payload fingerprint); distinguishes `created` /
`idempotent_replay` / `denied` / `failed_before_write` / `write_outcome_uncertain`; and returns a
typed `ReviewBundleWriteReceipt`.

It **approves nothing** — no `approve_internal`, **no Phase 22 review writer call, no
`review_records` row**. It executes no agent, makes no LLM/MockLLM/AgentNet/MCP/resolver/connector/
network call, creates no `agent_run_records` row, and performs no client-facing output / financial
verification / capsule publication. Required posture: `output_status=draft`,
`review_status=needs_review`, `lifecycle_status=draft`, and all of `authoritative` /
`client_facing_approved` / `capsule_candidate_ready` / `financial_verified` / `execution_allowed` /
`approval_allowed` / `publication_allowed` false with `requires_human_review=true`. Only safe
references/summaries are stored (never raw packet/evidence/interview content, source bytes,
generated output, secrets, or a final review decision); a draft carrying such an attribute is
rejected without echoing the value.

- [`peak/db/review_bundle_writer.py`](peak/db/review_bundle_writer.py) — the controlled writer.
- [`alembic/versions/007_review_bundle_records.py`](alembic/versions/007_review_bundle_records.py)
  — additive migration creating the single new table (down_revision `006_agent_task_queue_records`;
  single linear head `007_review_bundle_records`; no data).
- [`docs/REVIEW_BUNDLE_CONTROLLED_WRITER.md`](docs/REVIEW_BUNDLE_CONTROLLED_WRITER.md) and
  [`docs/REVIEW_BUNDLE_IDEMPOTENCY_POLICY.md`](docs/REVIEW_BUNDLE_IDEMPOTENCY_POLICY.md).

```bash
make validate-phase30 PYTHON=.venv/bin/python   # full DB-backed suite (temporary SQLite)
make validate-phase30                           # structural only on plain python3
```

### Packet → Review Bundle Orchestration Integration (Phase 31)

Wires the Phase 29 review orchestration boundary and the Phase 30 narrow writer into the Phase
25/28 packet processor. It is an **orchestration integration phase, not a new writer phase and not
an approval phase** — no new table, no migration (head stays `007_review_bundle_records`; still 13
tables), no new writer. After the existing Phase 23/24/14/18/21/13/26/27 path, the orchestrator
gathers safe references and adds two stages: `review_orchestration` (Phase 29) and
`review_bundle_persistence` (Phase 30).

- **Plan-only (default):** runs Phase 29 `prepare_packet_review_plan` over safe refs and exposes
  `review_bundle_drafts`, `review_plan_items`, `review_readiness_assessments`, and the
  `review_*_count` fields — review-gated, **not-approved** — with every side-effect flag `false`
  (Phase 29 is DB-free and approval-free).
- **Controlled persistence:** only when `plan_only=false`, `include_review_bundle_persistence=true`,
  and a `session_factory` is supplied does it build a Phase 17 request per draft and call **only**
  `persist_review_bundle_record` (Phase 30), attaching receipts and aggregating DB flags from actual
  writer calls; idempotent replay and conflict flow through Phase 30. No option silently escalates
  plan-only.
- **No approval / no execution:** approves nothing, never calls the Phase 22 review writer, creates
  **no `review_records`** row, executes no agent, calls no LLM/MockLLM/AgentNet/MCP/resolver/network,
  and creates **no `agent_run_records`** row. `ready_for_human_review` is not approval.
- **Authorization:** orchestrator preflight is advisory; **stored `Engagement` authorization
  remains authoritative** inside the Phase 30 writer (identity necessary but not sufficient).

- [`peak/orchestration/packet_processor.py`](peak/orchestration/packet_processor.py) — the two new
  stages (`review_orchestration`, `review_bundle_persistence`).
- [`docs/PACKET_TO_REVIEW_BUNDLE_ORCHESTRATION_INTEGRATION.md`](docs/PACKET_TO_REVIEW_BUNDLE_ORCHESTRATION_INTEGRATION.md).

```bash
make validate-phase31 PYTHON=.venv/bin/python   # structural + plan-only + DB-backed (temporary SQLite)
make validate-phase31                           # structural + plan-only on plain python3 (DB layer skipped)
```

### Internal Reviewer Decision Boundary (Phase 32)

A **DB-free decision-planning boundary** that lets Peak represent a structured internal reviewer
decision against a review bundle / review plan items — producing a review-gated decision *draft*, a
decision-readiness assessment, and a deterministic **routing recommendation**. It is analogous to
Phase 29 (which planned review bundles without DB writes). It adds no table and no migration (head
stays `007_review_bundle_records`; still 13 tables), and produces **no** `ControlledWriteRequest`
objects — future persistence is deferred to Phase 33.

- **It is not an approval phase.** It never persists a decision, never calls the Phase 22 review
  writer, creates **no `review_records` row**, never calls `approve_internal`, and never creates
  client-facing output, verifies financial impact, publishes a capsule, executes an agent, or calls
  an LLM/MockLLM/AgentNet/MCP/resolver/network. Every side-effect flag stays `false`.
  **`ready_for_internal_use` is not approval.**
- **Public entry point:** `prepare_internal_reviewer_decision(request) -> InternalReviewerDecisionResult`.
- **Allowed intents:** `needs_more_evidence`, `return_for_revision`, `ready_for_internal_use`,
  `blocked_by_scope`, `blocked_by_quality`, `blocked_by_missing_source`, `rejected_for_policy`,
  `defer_review` — each mapped to a deterministic **route recommendation** (not an action).
  Approval / publication / execution / financial / client-facing intents are denied.
- **Governance** rejects missing identity/scope/idempotency/review-bundle-ref, prohibited
  lifecycle, disallowed/unsupported intents, email-like reviewer roles, and raw-content /
  secret-like / DB-URL / raw-SQL fields — reporting key names only (values never echoed). Identity
  matching is necessary but not sufficient.
- **Handoff (documented):** Phase 32 consumes safe references shaped like Phase 30 output
  (`review_bundle_record_id`) and Phase 29 output (review plan item refs); it does not run inside
  packet processing and imports no Phase 30 / Phase 22 writer / `peak.db`.

- [`peak/reviewer_decisions/`](peak/reviewer_decisions/) — decision contracts, deterministic
  governance, and the `prepare_internal_reviewer_decision` mapper (stdlib-only).
- [`docs/INTERNAL_REVIEWER_DECISION_BOUNDARY.md`](docs/INTERNAL_REVIEWER_DECISION_BOUNDARY.md) and
  [`docs/INTERNAL_REVIEWER_DECISION_GOVERNANCE_POLICY.md`](docs/INTERNAL_REVIEWER_DECISION_GOVERNANCE_POLICY.md).

```bash
make validate-phase32   # internal reviewer decision boundary check (stdlib-only; DB-free)
```

## Design constraints

- **Lightweight first.** Scaffolding and clear docs before complex agent logic.
- **No vendor lock-in.** Data objects, schemas, and prompts are described in
  portable terms; no specific model provider or framework is assumed.
- **Evidence-first.** Every substantive claim an agent produces should trace to an
  `EvidenceReference` (see [`docs/DATA_OBJECTS.md`](docs/DATA_OBJECTS.md)).
- **Human-in-the-loop.** Agents draft and structure; Peak consultants decide.

## Who should read what

- **Developers:** [`docs/DATA_OBJECTS.md`](docs/DATA_OBJECTS.md) and
  [`docs/IMPLEMENTATION_PLAN.md`](docs/IMPLEMENTATION_PLAN.md).
- **Consultants:** [`docs/AGENT_WORKFLOWS.md`](docs/AGENT_WORKFLOWS.md) and
  [`docs/OPERATING_MODEL.md`](docs/OPERATING_MODEL.md).
- **Investors / leadership:** [`docs/OPERATING_MODEL.md`](docs/OPERATING_MODEL.md)
  and this README.
