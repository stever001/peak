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

## Cross-cutting rules

- **Evidence-first:** every finding, risk, quick win, and recommendation links to
  at least one `EvidenceReference`.
- **Human-in-the-loop:** no agent output reaches a client without consultant review
  and QA/governance sign-off.
- **Grounding (intended):** outputs are meant to be reconciled by AgentNet against
  Peak methodology and prior engagements — target architecture, not yet live.
