# Discovery Plan — Client Alpha (EXAMPLE OUTPUT)

> Sample output of `prompts/discovery/generate-discovery-plan.prompt.md` run against
> [`../engagement-packet.example.json`](../engagement-packet.example.json)
> (`intake_alpha_2026`). Internal draft; a consultant adapts it to time, budget, and
> access. Fictional/anonymized. Nothing here is drawn from outside the packet.

## Engagement context
Client Alpha (`intake_alpha_2026`) is a medium industrial-parts distributor
(fasteners, fittings, safety equipment) running make-to-stock distribution from a
central warehouse to regional branches, on an aging on-premise ERP plus
non-integrated per-branch reorder spreadsheets. The engagement was triggered by an
external stock-count audit that flagged material discrepancies (urgency: high).

## Assessment objective
Produce an evidence-based initial assessment that (a) characterizes and, where data
allows, begins to quantify inventory record-accuracy problems, and (b) identifies
low-effort quick wins — positioning a scoped next-phase remediation engagement. This
restates the packet's `first_billing_tranche_objective` for this plan.

## Interview plan
Roles taken from `client_intake.stakeholders`. Do not add stakeholders not in the
packet.

| Role (label) | Objectives | Key questions | Evidence to capture |
| --- | --- | --- | --- |
| Operations manager / sponsor (`stakeholder_1`) | Confirm business impact and priorities; reconcile the counting-cadence contradiction | How often are full counts done vs. partial? Which SKUs stock out most? What did the audit specifically flag? | Statement records; any audit summary the client will share |
| Warehouse lead (`stakeholder_2`) | Deepen the counting/adjustment account already captured in `evid_alpha_002` | Walk me through a count-vs-ERP mismatch end to end; who can adjust; is a reason code possible? | Adjustment-log request; count-process notes |
| Finance controller (`stakeholder_3`) | Understand valuation exposure of inaccurate on-hand | How are month-end inventory values derived? How are adjustments treated in the ledger? | Valuation-process notes |

**Open contradiction to resolve (from `evid_alpha_002` interview):** operations
manager reportedly described counts as full-warehouse monthly, while the warehouse
lead described partial weekly. Confirm the actual cadence with both.

## Walk-around checklist
Grounded in the intake's storage types (`racked`, `bulk`, `small_parts_bins`) and the
known pain around counts. Items are planned observations, not findings.

- [ ] **Small-parts bins** — label legibility, one-SKU-per-location discipline, mixed
  bins (directly relevant to the count/ERP gap). *Note: this later produced
  `vobs_alpha_binspill` / `evid_alpha_003`.*
- [ ] **Racked storage** — location labeling and put-away accuracy.
- [ ] **Bulk storage** — how quantities are estimated/counted.
- [ ] **Receiving dock** — whether goods are booked into the ERP before put-away
  (a stakeholder claim to verify — see follow-up below).
- [ ] **Count staging** — how cycle counts are recorded and reconciled.
- [ ] **Adjustment point** — where/how staff change ERP on-hand after a count.

## Document / data request list
| Item | Why it matters | Maps to |
| --- | --- | --- |
| ERP stock-on-hand export | Quantify divergence between system and physical counts | pain point (`evid_alpha_002`); source `available: on_request` |
| Last cycle-count report | Compare counted vs. system quantities | data-quality concern (counts); source `available` |
| Inventory adjustment log | Quantify volume/size of unreviewed adjustments | `wobs_alpha_adjustments`; interview follow-up (`evid_alpha_002`) |
| Branch reorder spreadsheets (sample) | Assess unreconciled branch reordering | `manual_workarounds` (`evid_alpha_002`); source `restricted` |

**Access reality (from `assessment_readiness`):** ERP export access is pending IT
approval and branch spreadsheets are restricted, so the walk-around should proceed
first while data access is arranged.

## Risks to validate
Each is a **hypothesis to confirm/refute**, not a finding.
- Record accuracy is eroded primarily by uncontrolled adjustments → confirm via the
  adjustment log and the warehouse-lead account (`evid_alpha_002`).
- Stockouts on fast movers stem from inaccurate on-hand rather than true supply gaps
  → confirm by quantifying stockouts against on-hand from the ERP export
  (`evid_alpha_001`, currently unquantified).
- Bin-labeling ambiguity contributes to count errors → confirm by sample-counting a
  labeled vs. unlabeled zone (anticipates `evid_alpha_003`).
- The ERP does not flag negative on-hand balances → **claim only**, no evidence yet;
  verify directly in the ERP.

## First-billing-tranche objective (sharpened)
Deliver, within the initial assessment, a clear evidence-based picture of Client
Alpha's inventory record-accuracy problem and its operational consequences, with at
least one or two validated quick wins (e.g. bin relabeling, adjustment controls) and a
defensible case for a scoped next-phase remediation engagement — explicitly
distinguishing what the current evidence supports from what still needs ERP data to
quantify.

## Assumptions & caveats
- This plan assumes the three named stakeholders remain available; no others are
  assumed to exist.
- No metrics are asserted here; the only figure in the engagement ("6–8 hours/week"
  reconciling counts) is a *reported* value from `evid_alpha_002`, to be verified.
- AgentNet grounding is intended future architecture and was **not** used to build
  this plan.
