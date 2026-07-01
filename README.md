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
│   └── IMPLEMENTATION_PLAN.md
├── agents/                       # One folder per agent capability group
│   ├── intake/                   # New client intake
│   ├── discovery/                # Assessment planning, interviews, walk-around
│   ├── evidence/                 # Evidence normalization
│   ├── reporting/                # Management report generation
│   ├── proposal/                 # Quick wins + next-phase proposals
│   ├── qa/                       # Internal QA / governance review
│   └── learning/                 # Reusable knowledge capture
├── schemas/                      # Data object schemas (to be defined)
├── examples/                     # Worked examples and sample records
├── prompts/                      # Reusable prompt building blocks
└── tests/                        # Tests for schemas and workflows
```

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
