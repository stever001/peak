# Evidence-Backed Findings — Client Alpha (EXAMPLE OUTPUT)

> Sample output of `prompts/evidence/extract-evidence-findings.prompt.md` run against
> [`../engagement-packet.example.json`](../engagement-packet.example.json). Internal
> draft; a consultant validates each finding. Every finding cites packet `evid_` ids;
> uncited items are demoted to **Unsupported items**. Fictional/anonymized.

Confidence reflects evidence strength: the two interview statements are single-source,
reliability **medium**, and not yet corroborated against ERP data; the bin photograph
is reliability **high**.

---

## Process

### Finding P1 — Cycle counting is partial and informally scoped
- **Evidence:** `evid_alpha_002`
- **Observed evidence:** none direct (no count records reviewed yet).
- **Stakeholder claim:** warehouse lead states counts are done weekly but only on an
  informally chosen subset of aisles.
- **Consultant interpretation:** informal scope likely leaves portions of inventory
  rarely counted, allowing errors to persist between counts.
- **Confidence:** low (single stakeholder claim; contradicted on cadence — see C1).
- **Recommended follow-up:** obtain the last cycle-count report and the count schedule
  to establish true coverage and cadence.

### Finding P2 — Possible receive-before-book gap in receiving
- **Evidence:** none (claim only)
- **Observed evidence:** none.
- **Stakeholder claim:** warehouse lead says received goods are *sometimes* put away
  before being booked into the ERP.
- **Consultant interpretation:** if real, this creates windows where physical stock
  exists but the ERP shows none — a plausible contributor to on-hand inaccuracy.
- **Confidence:** low (uncorroborated, no evidence id).
- **Recommended follow-up:** observe receiving during the walk-around; check receipt
  timestamps vs. put-away. *(Tracked under Unsupported items.)*

## System

### Finding S1 — Competing sources of truth (ERP vs. branch spreadsheets)
- **Evidence:** `evid_alpha_002` (manual workaround), plus `inventory_system_profile`
- **Observed evidence:** system profile records the ERP as nominal source of truth
  with **low** confidence, and a manual, low-reliability reconciliation between branch
  spreadsheets and the ERP.
- **Stakeholder claim:** branches keep their own reorder spreadsheets because they do
  not trust ERP availability figures (`evid_alpha_002`).
- **Consultant interpretation:** parallel, unintegrated records mean no single trusted
  stock figure, undermining purchasing and reordering.
- **Confidence:** medium.
- **Recommended follow-up:** sample branch spreadsheets vs. ERP for the same SKUs once
  access is granted.

### Finding S2 — ERP may not flag negative on-hand balances
- **Evidence:** none (claim only)
- **Observed evidence:** none.
- **Stakeholder claim:** warehouse lead states the ERP does not flag negative on-hand,
  so they go unnoticed.
- **Consultant interpretation:** unflagged negatives would hide data-integrity breaks.
- **Confidence:** low (uncorroborated).
- **Recommended follow-up:** verify ERP behavior directly. *(Unsupported items.)*

## Control

### Finding C-CTRL1 — Inventory adjustments are unreviewed and reason-code-free
- **Evidence:** `evid_alpha_002` (and `wobs_alpha_adjustments`)
- **Observed evidence:** workflow observation records that staff adjust ERP on-hand to
  match a count directly, with **no approval step and no reason code**.
- **Stakeholder claim:** discrepancies are resolved by adjusting the ERP to match the
  count without root-cause review (`evid_alpha_002`).
- **Consultant interpretation:** this is a segregation-of-duties weakness and masks
  recurring accuracy problems rather than correcting them; also a shrink-concealment
  exposure.
- **Confidence:** medium (consistent stakeholder + workflow observation; adjustment
  log not yet obtained).
- **Recommended follow-up:** obtain the adjustment log to quantify frequency/size;
  confirm whether the ERP supports approval thresholds and reason codes.

## Data quality

### Finding DQ1 — Physical counts routinely diverge from ERP on-hand
- **Evidence:** `evid_alpha_001`, `evid_alpha_002`
- **Observed evidence:** none yet from data (ERP export pending).
- **Stakeholder claim:** operations manager reports stockouts on fast movers despite
  ERP showing stock (`evid_alpha_001`); warehouse lead reports counts "almost always"
  disagree (`evid_alpha_002`).
- **Consultant interpretation:** two independent roles describe the same accuracy gap
  from different vantage points (purchasing impact vs. counting floor), which
  strengthens the qualitative case even though it is unquantified.
- **Confidence:** medium (corroborated across two stakeholders; not yet quantified).
- **Recommended follow-up:** quantify divergence from the ERP stock-on-hand export and
  the last cycle-count report.

### Finding DQ2 — Bin labeling gaps degrade count/pick accuracy
- **Evidence:** `evid_alpha_003` (and `vobs_alpha_binspill`)
- **Observed evidence:** photographs show small-parts bins with faded/missing location
  labels and bins holding mixed SKUs without partition labels.
- **Stakeholder claim:** none.
- **Consultant interpretation:** ambiguous bin identity makes accurate picking and
  counting harder, a concrete mechanism behind the count/ERP divergence in DQ1.
- **Confidence:** high (direct photographic evidence).
- **Recommended follow-up:** sample-count a labeled vs. unlabeled zone to compare
  accuracy; scope relabeling.

## Operational risk

### Finding OR1 — Eroded trust in ERP stock drives workarounds and stockouts
- **Evidence:** `evid_alpha_001`, `evid_alpha_002`
- **Observed evidence:** system profile shows low source-of-truth confidence and
  branch workarounds.
- **Stakeholder claim:** purchasing "no longer trusts on-hand figures"
  (`evid_alpha_001`); branches maintain separate spreadsheets (`evid_alpha_002`).
- **Consultant interpretation:** loss of trust is now operationalized as parallel
  processes, increasing cost/effort and stockout risk on fast movers; also raises a
  valuation-reliability question for finance (to explore with `stakeholder_3`).
- **Confidence:** medium.
- **Recommended follow-up:** quantify stockout frequency and reconciliation effort
  ("6–8 hours/week" is *as reported* in `evid_alpha_002`, not verified).

---

## Unsupported items (no evidence yet — do not treat as findings)
- Receiving "put away before booked" (P2) — needs walk-around observation.
- ERP not flagging negative on-hand (S2) — needs direct ERP verification.
- Counting cadence (weekly-partial vs. monthly-full) — **contradiction** between
  `stakeholder_1` and `stakeholder_2`; resolve before reporting.
- Any stockout rate, accuracy percentage, or financial impact — **not present in the
  packet**; must come from the pending ERP export.

## Cross-cutting notes
- Reliability ceiling: two of three evidence items are single-source medium-reliability
  interviews; treat their findings as directional until ERP data corroborates them.
- AgentNet was **not** used; grounding is intended future architecture.
