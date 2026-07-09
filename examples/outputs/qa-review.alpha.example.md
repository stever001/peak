# QA / Governance Review — Client Alpha (EXAMPLE OUTPUT)

> Sample output of `prompts/qa/review-assessment-packet.prompt.md` run against
> [`../engagement-packet.example.json`](../engagement-packet.example.json), the initial
> assessment report, and the next-phase proposal. This is a **gate**: strict but fair.
> Fictional/anonymized.

## Verdict
**Report-readiness score: 3 / 5.**
The internal work product is well-grounded and honest about its limits — evidence is
cited, claims and observations are separated, and no ROI is fabricated. It is **not yet
client-ready**, for two reasons that must be closed first: (1) the central accuracy
claim is unquantified and rests on two single-source, medium-reliability interviews,
and (2) an unresolved stakeholder contradiction (count cadence) sits under the
findings. Fix those and this moves to a 4–4.5.

## Unsupported claims
| Claim | Where | Why flagged |
| --- | --- | --- |
| "6–8 hours/week" reconciling counts | Report caveats / findings OR1 | Correctly labeled *as reported*, but it is a single-source figure with no data behind it — keep it labeled and do **not** let it drift into a quantified benefit. |
| ERP does not flag negative on-hand balances | Excluded from findings (S2) | No evidence id; correctly demoted to Unsupported — must stay out of any client-facing claim until verified. |
| Receiving "put away before booked" | Excluded from findings (P2) | Claim only, no evidence; correctly demoted. Verify on-site before use. |

_No fabricated claims were found in the report or proposal._ The above are about
discipline, not violations.

## Missing evidence
- **Quantification of the accuracy gap (DQ1/OR1).** The strongest business claim
  (counts diverge; stockouts result) has **no data** yet — only `evid_alpha_001` and
  `evid_alpha_002`. Needs the ERP stock-on-hand export and last cycle-count report.
- **Adjustment volume (C-CTRL1).** The control finding lacks the adjustment log needed
  to size frequency/materiality.
- **Source-of-truth divergence (S1).** No branch-vs-ERP sample yet.

## Contradictions
- **Count cadence (unresolved).** `evid_alpha_002` records operations manager =
  full-warehouse monthly vs. warehouse lead = partial weekly. The report notes it as
  "open," which is honest, but a client-facing report must resolve it — it affects how
  count coverage (finding P1) is characterized.

## Weak recommendations
| Recommendation | Weakness | How to strengthen |
| --- | --- | --- |
| WS2 adjustment controls (report rec #2 / proposal WS2) | Depends on unverified ERP capability for reason codes/approvals | Confirm ERP capability first; state the compensating manual control if unsupported (proposal flags this — make it a gating check, not a footnote) |
| "Reconcile source-of-truth split" (rec #4 / WS4) | Currently broad; success measure is "recommendation accepted," which is soft | Define what "reconciled" means and a sizing metric (e.g. % SKU divergence on a sample) |
| Quick win: bin relabeling | Strong and evidenced (`evid_alpha_003`), but value stated only qualitatively | Keep qualitative; optionally pre/post sample-count to evidence the gain |

## Required fixes (prioritized)
- [ ] **Resolve the count-cadence contradiction** with both stakeholders before any
  client-facing version.
- [ ] **Gate WS1/WS2 on ERP access + ERP capability**; make these explicit
  preconditions, not assumptions buried in prose.
- [ ] **Keep every unverified item quarantined** (negative on-hand; receiving timing;
  the 6–8 hrs/week figure) and labeled until corroborated.
- [ ] **Add a one-line reliability statement** to the report's executive summary noting
  the evidence is qualitative/single-source pending ERP data.
- [ ] Tighten WS4 success measure to something observable.

## Consistency checks (packet integrity)
- All cited evidence ids (`evid_alpha_001/002/003`) exist in the packet. ✔
- No claim was traced to a non-existent evidence id. ✔
- No text implies AgentNet validated or grounded anything. ✔ (AgentNet correctly
  described as intended future architecture.)
- Stakeholder claims are not promoted to facts in the report. ✔

## Fairness note
The drafts are appropriately cautious for an early, data-blocked assessment; the score
reflects **client-readiness**, not the quality of the internal analysis, which is
sound given the available evidence.
