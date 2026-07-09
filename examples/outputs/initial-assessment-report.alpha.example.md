# Initial Assessment Report — Client Alpha (EXAMPLE OUTPUT / DRAFT)

> Sample output of `prompts/reporting/draft-initial-assessment-report.prompt.md` run
> against [`../engagement-packet.example.json`](../engagement-packet.example.json)
> and the evidence findings. **Internal draft for consultant review — not a
> client-sent document.** Fictional/anonymized. Evidence ids are cited inline; no ROI
> or savings figures are asserted.

## Executive summary
Client Alpha's initial inventory assessment was triggered by an external stock-count
audit that flagged material discrepancies. Discovery to date — two stakeholder
interviews and a site walk-around — points to a consistent theme: the organization
cannot currently trust its inventory record. Two roles independently describe on-hand
figures diverging from reality (`evid_alpha_001`, `evid_alpha_002`), and the practice
of adjusting the ERP to match counts without review or reason codes
(`wobs_alpha_adjustments`, `evid_alpha_002`) appears to mask the problem rather than
correct it. A concrete contributing factor is visible on the floor: small-parts bins
with faded/missing labels and mixed SKUs (`evid_alpha_003`). The evidence so far is
qualitative and largely single-source; quantification depends on ERP data that is not
yet available. Even so, the direction is clear enough to act on two quick wins and to
scope a next-phase remediation.

## Current-state findings
Grouped; each references packet evidence. See
[`evidence-findings.alpha.example.md`](evidence-findings.alpha.example.md) for full
observed-vs-claimed detail.

- **Data quality — counts diverge from the ERP.** Stockouts on fast movers despite
  reported stock (`evid_alpha_001`) and counts that "almost always" disagree
  (`evid_alpha_002`). Unquantified pending ERP export.
- **Control — unreviewed adjustments.** ERP on-hand is edited to match counts with no
  approval and no reason code (`evid_alpha_002`; `wobs_alpha_adjustments`).
- **System — competing sources of truth.** ERP is only nominally authoritative
  (system-profile confidence: low); branches keep separate, unintegrated reorder
  spreadsheets (`evid_alpha_002`).
- **Data quality — bin labeling.** Faded/missing labels and mixed-SKU bins observed in
  small-parts storage (`evid_alpha_003`).
- **Process — informal count scope.** Counts described as weekly but on an informally
  chosen subset of aisles (`evid_alpha_002`); count cadence is contradicted between
  stakeholders and remains open.

## Risk / impact analysis
Severity indicators are qualitative (from the packet); no financial impact is claimed.

| Risk | Severity | Evidence | Why it matters |
| --- | --- | --- | --- |
| Inaccurate on-hand drives stockouts on fast movers | High | `evid_alpha_001` | Lost sales/service on the SKUs that matter most; purchasing distrust |
| Unreviewed adjustments mask root causes (SoD / shrink-concealment) | High | `evid_alpha_002`, `wobs_alpha_adjustments` | Errors recur; potential concealment of loss; weak control environment |
| Competing sources of truth (ERP vs. spreadsheets) | Medium–High | `evid_alpha_002` | No single trusted stock figure; duplicated effort; reorder errors |
| Bin-labeling ambiguity degrades count/pick accuracy | High (localized) | `evid_alpha_003` | A concrete, fixable mechanism behind count errors |
| Negative on-hand possibly unflagged by ERP | Unverified | none | Would hide integrity breaks — **claim only**, verify in ERP |

## Quick wins
Low-effort, high-value, and evidence-linked.

| Quick win | Effort | Expected value (qualitative) | Evidence |
| --- | --- | --- | --- |
| Relabel small-parts bin zones; enforce one-SKU-per-location | Low | More reliable picking and counting where errors are visibly seeded | `evid_alpha_003` |
| Introduce an approval threshold + mandatory reason codes for ERP adjustments | Low–Medium (pending ERP capability) | Restores review and root-cause signal; strengthens control | `evid_alpha_002`, `wobs_alpha_adjustments` |

*Feasibility caveat:* the adjustment-control quick win assumes the ERP supports reason
codes/approvals — to be confirmed.

## Priority recommendations
1. **Establish a trusted count baseline.** Obtain the ERP stock-on-hand export and last
   cycle-count report; quantify divergence to convert qualitative concern (DQ1) into a
   measured baseline. *(Blocked on ERP access.)*
2. **Control inventory adjustments.** Add approval + reason codes and a light
   root-cause step (addresses the highest-severity control finding).
3. **Fix bin labeling in small-parts storage.** Immediate, evidence-backed accuracy
   improvement (`evid_alpha_003`).
4. **Reconcile the branch/ERP source-of-truth split.** Sample branch spreadsheets vs.
   ERP to size the problem before proposing integration.

## Next-step framing (first-tranche value → what comes next)
**What this assessment delivered:** an evidence-based, if still qualitative, picture of
a real record-accuracy problem; identification of two actionable quick wins; and a
prioritized list that separates what today's evidence supports from what needs ERP
data to quantify. **Logical next step:** a scoped next-phase engagement to (a) quantify
the accuracy gap from ERP data, (b) implement adjustment controls and bin relabeling,
and (c) reconcile sources of truth — detailed in the next-phase proposal. This report
intentionally makes **no ROI or savings claim**; any such figure requires the pending
ERP data.

## Caveats
- Evidence is largely single-source, medium reliability; the "6–8 hours/week" figure
  is *reported by the warehouse lead* (`evid_alpha_002`), not verified.
- One open contradiction (count cadence) and two unverified claims (receiving
  book-timing; negative on-hand flagging) are excluded from findings on purpose.
- AgentNet grounding is intended future architecture and was **not** used.
