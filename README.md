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
│   └── IMPLEMENTATION_PLAN.md
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

## AgentNet grounding (intended architecture)

AgentNet is described throughout this repository as the **intended grounding and
resolution layer**. It is the mechanism by which agent outputs are meant to be
anchored to Peak's methodology, prior engagements, and evidence standards.

**AgentNet integration is not yet implemented.** Wherever grounding is referenced,
treat it as target architecture unless a file explicitly states it is live.

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
