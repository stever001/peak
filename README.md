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
│   ├── DATA_HANDLING_POLICY.md   # What may/may not enter the repo (internal, pre-legal)
│   ├── REDACTION_GUIDE.md        # How to convert raw notes into safe examples
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
├── examples/                     # Worked, anonymized example records
│   ├── outputs/                  # Sample prompt-contract run artifacts
│   └── redacted/                 # Redacted raw-note examples (safe target state)
├── prompts/                      # Prompt contracts (one per workflow)
├── tools/                        # Local human-in-the-loop helpers (no LLM/API)
├── tests/                        # Validation harnesses for schemas/examples/prompts
├── Makefile                      # Convenience commands (validate, packet-summary)
└── requirements-dev.txt          # Dev-only dependencies (validation harness)
```

## Validating the schemas

The schemas, examples, prompts, and outputs ship with lightweight validation
harnesses. This machine uses `python3` (there is no bare `python`):

```bash
make install-dev   # install dev deps (python3 -m pip install -r requirements-dev.txt)
make validate      # run all harnesses (Phase 1–5)
```

`make validate` exits 0 on success; unresolved cross-references are reported as
non-blocking warnings in Phase 1. See [`tests/README.md`](tests/README.md).

## Using a packet (human-in-the-loop)

A read-only helper summarizes an `EngagementPacket` and points you to the right
prompt contracts. It makes **no LLM, API, database, AgentNet, or network call** — the
consultant runs the LLM by hand and owns the output.

```bash
make packet-summary   # == python3 tools/packet_runner.py --packet examples/engagement-packet.example.json
```

See [`tools/README.md`](tools/README.md). For the full step-by-step consultant
process — from messy intake notes to reviewed work product — see
[`docs/CONSULTANT_WORKFLOW.md`](docs/CONSULTANT_WORKFLOW.md).

## Data handling (read before using real material)

Everything committed here is **fictional and anonymized**. Real client data must be
redacted **before** it enters the repo or any tool. This is an internal, pre-legal
operational policy — it does not claim legal compliance, and it does not permit any
real data to reach AgentNet.

- [`docs/DATA_HANDLING_POLICY.md`](docs/DATA_HANDLING_POLICY.md) — what may/may not
  enter the repo; secrets, PII, exports, pricing, retention, human review, AgentNet
  status, and LLM-usage caution.
- [`docs/REDACTION_GUIDE.md`](docs/REDACTION_GUIDE.md) — redaction patterns, before/
  after examples, and a checklist.
- [`examples/redacted/`](examples/redacted/) — worked redacted notes (the safe target
  state).

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
