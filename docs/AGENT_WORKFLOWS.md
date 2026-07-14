# Agent Workflows

This document maps the internal workflows this system supports. Each workflow is
**agent-assisted**: an agent structures and drafts, a Peak consultant reviews and
decides. All outputs are intended to be grounded by AgentNet (target architecture)
and to trace to evidence.

## Workflow index

| # | Workflow | Agent group (`agents/`) | Primary outputs (data objects) |
| --- | --- | --- | --- |
| 1 | New client intake | `intake/` | `ClientIntake` |
| 2 | Initial assessment planning | `discovery/` | Assessment plan, `InventorySystemProfile` |
| 3 | Interview preparation & structuring | `discovery/` | `StakeholderInterview` |
| 4 | Walk-around visual inspection structuring | `discovery/` | `VisualObservation`, `WorkflowObservation` |
| 5 | Evidence normalization | `evidence/` | `EvidenceReference`, `DataQualityIssue`, `ControlGap`, `OperationalRisk` |
| 6 | Initial management report generation | `reporting/` | `ClientReportSection` |
| 7 | Quick-win identification | `proposal/` | `QuickWin` |
| 8 | Next-phase proposal generation | `proposal/` | `Recommendation`, `PhaseTwoOpportunity` |
| 9 | Internal QA / governance review | `qa/` | QA findings, sign-off record |
| 10 | Engagement learning / reusable knowledge capture | `learning/` | Reusable knowledge entries |

## Prompt contracts (Phase 3)

Before any autonomous agent runtime exists, each workflow is operated by a **prompt
contract** in [`../prompts/`](../prompts/): a markdown file a consultant copies into an
LLM, with a fixed structure (purpose, inputs, grounding/evidence rules, non-goals,
output format, quality checks, and a reusable body). Most operate on an
`EngagementPacket` and require the model to cite packet `evid_` ids. They are
**internal operating prompts**, human-run and human-owned — not agents, and not
client-facing.

| Workflow(s) | Prompt contract |
| --- | --- |
| 1 | `prompts/intake/normalize-client-intake.prompt.md` |
| 2–4 | `prompts/discovery/generate-discovery-plan.prompt.md` |
| 5 | `prompts/evidence/extract-evidence-findings.prompt.md` |
| 6–7 | `prompts/reporting/draft-initial-assessment-report.prompt.md` |
| 8 | `prompts/proposal/generate-next-phase-proposal.prompt.md` |
| 9 | `prompts/qa/review-assessment-packet.prompt.md` |
| 10 | `prompts/learning/extract-engagement-lessons.prompt.md` |

**Output structure.** Each contract's expected output structure (sections it must
produce) is defined by the contract itself and exercised by
[`../tests/validate_phase4_outputs.py`](../tests/validate_phase4_outputs.py) against a
synthetic, runtime-generated document. Peak does **not** commit sample outputs — real
work product lives in controlled engagement storage, not the repo.

**Runner (human-in-the-loop).** [`../tools/packet_runner.py`](../tools/packet_runner.py)
requires an explicit `--packet` path (a real packet from controlled engagement storage;
there is no demo mode) and is a read-only helper: given a packet, it prints a summary
and points the consultant at the right contract. It runs **no** LLM, API, database,
AgentNet, or network call, and **stores nothing** — the consultant does the LLM step by
hand and owns the result. It is not an agent runtime.

**Step-by-step consultant process.** [`CONSULTANT_WORKFLOW.md`](CONSULTANT_WORKFLOW.md)
walks the whole flow — capture notes → normalize intake → add evidence/profile/
interviews/observations → bundle a packet → summarize → run a contract → QA → save →
capture lessons — with the consultant rules, the QA readiness ladder, and the current
phase boundary.

## The first end-to-end thread

The initial priority is one clean, connected path from a new client through to a
proposal for paid next-phase work:

```
┌──────────────┐    ┌──────────────────────┐    ┌───────────────────┐
│ New Client   │ →  │ Initial Assessment   │ →  │ Discovery         │
│ Intake       │    │ Planning             │    │ (interviews +     │
│              │    │                      │    │  walk-around)     │
└──────────────┘    └──────────────────────┘    └─────────┬─────────┘
                                                           │
                     ┌─────────────────────────────────────┘
                     ▼
┌──────────────┐    ┌──────────────────────┐    ┌───────────────────┐
│ Evidence     │ →  │ Initial Management   │ →  │ Next-Phase        │
│ Normalization│    │ Report + Quick Wins  │    │ Proposal          │
└──────────────┘    └──────────────────────┘    └─────────┬─────────┘
                                                           │
                                              ┌────────────▼────────────┐
                                              │ Internal QA / Governance │
                                              └────────────┬────────────┘
                                                           │
                                              ┌────────────▼────────────┐
                                              │ Engagement Learning      │
                                              │ Capture                  │
                                              └──────────────────────────┘
```

QA/governance and learning capture wrap the whole thread — QA gates output before
it reaches the client, and learning capture feeds every engagement back into
reusable knowledge.

## Workflow detail

### 1. New client intake (`agents/intake/`)
Capture who the client is, why they're engaging Peak, their inventory context, and
initial pain points. Produces a structured `ClientIntake` that seeds everything
downstream.

- **In:** raw notes, discovery call, questionnaire responses.
- **Out:** `ClientIntake`.
- **Human role:** consultant confirms scope, sensitivities, and objectives.

### 2. Initial assessment planning (`agents/discovery/`)
Turn the intake into a concrete assessment plan: what to look at, who to interview,
which systems and locations to inspect. Begins the `InventorySystemProfile`.

- **In:** `ClientIntake`.
- **Out:** assessment plan, initial `InventorySystemProfile`.
- **Human role:** consultant tailors scope to time/budget and client access.

### 3. Interview preparation & structuring (`agents/discovery/`)
Prepare structured interview guides per stakeholder role and capture responses in a
consistent form.

- **In:** assessment plan, stakeholder list.
- **Out:** `StakeholderInterview` (one per interview).
- **Human role:** consultant runs the interview; agent structures prep and notes.

### 4. Walk-around visual inspection structuring (`agents/discovery/`)
Structure the on-site walk-around: what to observe, how to record it, and how
observations map to inventory workflows.

- **In:** assessment plan, site details.
- **Out:** `VisualObservation`, `WorkflowObservation`.
- **Human role:** consultant observes on-site; agent structures capture.

### 5. Evidence normalization (`agents/evidence/`)
Take heterogeneous raw inputs (interviews, observations, documents) and normalize
them into consistent, deduplicated, traceable evidence. Derive candidate issues.

- **In:** `StakeholderInterview`, `VisualObservation`, `WorkflowObservation`.
- **Out:** `EvidenceReference`, and candidate `DataQualityIssue`, `ControlGap`,
  `OperationalRisk`.
- **Human role:** consultant validates that derived issues are real and material.

### 6. Initial management report generation (`agents/reporting/`)
Draft a structured, evidence-linked initial management report for the client.

- **In:** normalized evidence and derived issues.
- **Out:** `ClientReportSection` set forming the report.
- **Human role:** consultant edits, sets tone, owns the final deliverable.

### 7. Quick-win identification (`agents/proposal/`)
Identify low-effort, high-value improvements the client can act on immediately.

- **In:** derived issues and evidence.
- **Out:** `QuickWin`.
- **Human role:** consultant confirms feasibility and client appetite.

### 8. Next-phase proposal generation (`agents/proposal/`)
Turn findings into `Recommendation`s and a proposal for a paid next phase.

- **In:** issues, quick wins, report.
- **Out:** `Recommendation`, `PhaseTwoOpportunity`.
- **Human role:** consultant/management own commercial framing and pricing.

### 9. Internal QA / governance review (`agents/qa/`)
Before anything reaches a client, check evidence traceability, consistency,
completeness, and adherence to Peak standards.

- **In:** report, proposal, underlying evidence.
- **Out:** QA findings and a sign-off record.
- **Human role:** management reviews and signs off.

### 10. Engagement learning / reusable knowledge capture (`agents/learning/`)
Capture what worked, what recurred, and what's reusable, feeding it back so future
engagements start smarter. This is the loop that AgentNet grounding is meant to
strengthen over time.

- **In:** the full engagement record.
- **Out:** reusable knowledge entries.
- **Human role:** consultant/management curate what's worth keeping.

## The operating unit: EngagementPacket

Workflows 1–5 of the first thread all read from and write to a single
**`EngagementPacket`** — a self-contained bundle of one engagement's intake, system
profile, evidence, interviews, and observations (see
[`DATA_OBJECTS.md`](DATA_OBJECTS.md) and
[`../schemas/engagement-packet.schema.json`](../schemas/engagement-packet.schema.json)).
It is the practical unit future internal agents will operate on: intake seeds it,
discovery and evidence normalization enrich it, and reporting/proposal read from it.
Its packet-level invariants (evidence resolves within the packet; every nested
object points at the packet's intake) are enforced by the validation harness, giving
agents a dependable, self-contained input to reason over. AgentNet grounding, when
integrated, is intended to operate over packets — not yet live.

## Where the data lives

Agents and workflows operate on `EngagementPacket`s and related records held in Peak's
**controlled engagement storage** and, for grounding, **private resolver capsules** —
never on committed repo data (there is none). Agent/AI workflows consume authorized data
through controlled access paths. See
[`CONTROLLED_DATA_ARCHITECTURE.md`](CONTROLLED_DATA_ARCHITECTURE.md),
[`ENGAGEMENT_DATA_MODEL.md`](ENGAGEMENT_DATA_MODEL.md), and
[`RESOLVER_CAPSULE_ARCHITECTURE.md`](RESOLVER_CAPSULE_ARCHITECTURE.md) — all architecture
only, not implemented.

## Governance states & agent guardrails

Every record agents touch carries governance state (see
[`GOVERNANCE_STATES.md`](GOVERNANCE_STATES.md) and
[`STATE_TRANSITIONS.md`](STATE_TRANSITIONS.md)). Future agents must respect the gates:
agent output **defaults to `draft`/`needs_review`** (and `not_client_facing`); agents may
**not** set `client_facing_approved`, may **not** verify financial impact without human
review, and may **not** publish or approve resolver capsules — they may only *propose*
methodology candidates. These are contract-level rules, enforced by human review until
any runtime exists; the access roles, audit fields, and agent permission limits for the
future controlled database are in
[`DATABASE_ACCESS_AND_AUDIT.md`](DATABASE_ACCESS_AND_AUDIT.md).

## Cross-cutting rules

- **Evidence-first:** every finding, risk, quick win, and recommendation links to
  at least one `EvidenceReference`.
- **Human-in-the-loop:** no agent output reaches a client without consultant review
  and QA/governance sign-off.
- **Grounding (intended):** outputs are meant to be reconciled by AgentNet against
  Peak methodology and prior engagements — target architecture, not yet live.
