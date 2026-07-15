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
│   └── IMPLEMENTATION_PLAN.md
├── peak/                         # Python tooling layer (source only; no data)
│   ├── db/                       # base, enums, models, session (MySQL)
│   ├── agentnet/                 # Governance wrapper for the AgentNet MCP connector (no calls)
│   ├── agents/                   # Agent execution harness scaffold (mock; no live execution)
│   └── workers/                  # Production-shaped workers (evidence normalization; review-gated)
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
