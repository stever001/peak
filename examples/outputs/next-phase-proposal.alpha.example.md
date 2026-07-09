# Next-Phase Proposal — Client Alpha (EXAMPLE OUTPUT / DRAFT)

> Sample output of `prompts/proposal/generate-next-phase-proposal.prompt.md` run
> against [`../engagement-packet.example.json`](../engagement-packet.example.json) and
> the assessment findings. **Internal draft — Peak owns commercial framing and
> pricing.** Fictional/anonymized. No pricing is invented; timelines are assumptions.

## Context & first-tranche value
The initial assessment (triggered by an external stock-count audit) established, from
stakeholder interviews and a walk-around, that Client Alpha cannot currently trust its
inventory record: counts diverge from the ERP (`evid_alpha_001`, `evid_alpha_002`),
adjustments are made without review or reason codes (`wobs_alpha_adjustments`), sources
of truth compete (ERP vs. branch spreadsheets, `evid_alpha_002`), and bin labeling is
degraded (`evid_alpha_003`). The next phase converts these evidenced problems into
remediation, and quantifies what the assessment could not (pending ERP data).

## Recommended scope
**In scope:**
- Quantify inventory record-accuracy against ERP data and establish a measured
  baseline.
- Implement inventory-adjustment controls (approval + reason codes + light root cause).
- Remediate small-parts bin labeling and one-SKU-per-location discipline.
- Reconcile ERP vs. branch-spreadsheet sources of truth (assess, then recommend).

**Explicitly out of scope (this phase):**
- ERP replacement or major re-platforming.
- Branch-spreadsheet-to-ERP systems integration build (assessed here; built later if
  warranted).
- Any client-facing tooling.

## Workstreams
Each traces to assessment evidence/findings.

| Workstream | Objective | Traces to |
| --- | --- | --- |
| WS1 — Accuracy baseline | Quantify count-vs-ERP divergence; define an accuracy metric | `evid_alpha_001`, `evid_alpha_002` (finding DQ1) |
| WS2 — Adjustment controls | Approval threshold, mandatory reason codes, root-cause step | `evid_alpha_002`, `wobs_alpha_adjustments` (C-CTRL1) |
| WS3 — Bin labeling remediation | Relabel small-parts zones; enforce one-SKU-per-location | `evid_alpha_003` (DQ2) |
| WS4 — Source-of-truth reconciliation | Sample branch vs. ERP; recommend target operating model | `evid_alpha_002`, system profile (S1) |

## Deliverables
- Baseline accuracy report with an agreed accuracy metric and method (WS1).
- Adjustment-control design + rollout checklist, contingent on ERP capability (WS2).
- Bin-relabeling plan and completion evidence for targeted zones (WS3).
- Source-of-truth reconciliation findings + recommended target model (WS4).
- End-of-phase summary and options for a subsequent implementation phase.

## Timeline assumptions
All items are **assumptions**, not commitments, and depend on the stated conditions.
- **Assumption:** ERP read access and the stock-on-hand export are granted before WS1
  begins (currently `assessment_readiness` = ERP access pending).
- **Assumption:** the ERP supports reason codes/approval workflow; if not, WS2 shifts
  to a compensating manual control and the design scope changes.
- **Assumption:** branch spreadsheet access is approved for WS4 (currently restricted).
- Sequencing assumption: WS3 (bin labeling) can start immediately in parallel, as it
  needs no ERP access; WS1/WS2/WS4 gate on the access items above.
- No duration in weeks/days is asserted here — durations to be set with the client
  once access and ERP capability are confirmed.

## Client responsibilities
- Grant ERP read access and provide the stock-on-hand export and last cycle-count
  report.
- Provide the inventory adjustment log.
- Approve sampled access to branch reorder spreadsheets.
- Make `stakeholder_1` (sponsor), `stakeholder_2` (warehouse lead), and `stakeholder_3`
  (finance) available for scheduled sessions.
- Confirm ERP configuration capability for reason codes/approvals.

## Success measures
Observable, tied to the findings:
- A defined and measured inventory-accuracy baseline exists (WS1).
- Adjustments require approval and carry reason codes; a root-cause log exists (WS2).
- Targeted bin zones are relabeled and pass a labeled-vs-unlabeled sample count (WS3).
- A documented recommendation on sources of truth is delivered and accepted (WS4).

## Commercial rationale
The audit already created urgency (high) and executive sponsorship. The next phase
turns a qualitative, evidence-backed problem into a measured baseline and concrete
control/accuracy improvements, directly addressing the highest-severity findings
(unreviewed adjustments; count/ERP divergence) while a fast, low-cost win (bin
relabeling) demonstrates early progress. Value is framed in operational terms
(accuracy, control, trust in stock figures); **no ROI or savings figure is asserted**
because the supporting data is not yet available.

## Pricing
**[PRICING TBD].** No rate or price inputs were provided in the packet, so no pricing
is stated. Inputs needed to price this proposal:
- Peak day-rate / blended rate assumptions.
- Estimated effort per workstream (dependent on ERP access timing and capability).
- On-site vs. remote split and travel assumptions.
- Whether WS4 remains assess-only or extends toward implementation.

## Caveats
- Scope assumes the three named stakeholders and the systems in the packet; nothing
  else is assumed to exist.
- AgentNet grounding is intended future architecture and was **not** used.
