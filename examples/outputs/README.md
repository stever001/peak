# Example Outputs

Human-reviewable **sample run artifacts** that demonstrate the Phase 3 prompt
contracts ([`../../prompts/`](../../prompts/)) producing Peak internal work product
from a single source packet.

> **These are illustrative examples, not automation output.** They were authored to
> show what a consultant running each prompt contract against the packet should get.
> There is no agent runtime, API, or database involved. Every artifact is a **draft**
> a consultant would review and own.

## Source

- **Packet:** [`../engagement-packet.example.json`](../engagement-packet.example.json)
  (`pkt_alpha_2026`, engagement `intake_alpha_2026`).
- All content is fictional and anonymized (client `client_alpha`, `consultant_a`,
  `stakeholder_1..3`). Reported figures are illustrative only.

## Artifacts

| File | Produced by contract | Workflow |
| --- | --- | --- |
| `discovery-plan.alpha.example.md` | `prompts/discovery/generate-discovery-plan` | Assessment planning |
| `evidence-findings.alpha.example.md` | `prompts/evidence/extract-evidence-findings` | Evidence normalization |
| `initial-assessment-report.alpha.example.md` | `prompts/reporting/draft-initial-assessment-report` | Initial report |
| `next-phase-proposal.alpha.example.md` | `prompts/proposal/generate-next-phase-proposal` | Next-phase proposal |
| `qa-review.alpha.example.md` | `prompts/qa/review-assessment-packet` | QA / governance |
| `engagement-lessons.alpha.example.md` | `prompts/learning/extract-engagement-lessons` | Engagement learning |

## Grounding rules honored by these examples

- **Packet-only.** Nothing is used that is not in `engagement-packet.example.json`.
- **Evidence-cited.** Material findings reference packet `evid_` ids
  (`evid_alpha_001`, `evid_alpha_002`, `evid_alpha_003`).
- **Four-way separation.** Observed evidence, stakeholder claims, consultant
  interpretation, and recommended follow-up are kept distinct.
- **No fabrication.** No invented metrics, ROI, photos, systems, interviews, or
  pricing. The only quantified figure ("6–8 hours/week") is carried through **as
  reported** by the warehouse lead, not as a verified fact.
- **AgentNet is intended, not integrated.** No artifact claims AgentNet grounding,
  resolution, or publication occurred.

## The evidence base (for quick reference)

| Evidence | Type | Reliability | Gist |
| --- | --- | --- | --- |
| `evid_alpha_001` | interview (ops manager) | medium | Stockouts on fast movers despite ERP stock; purchasing distrusts on-hand figures. |
| `evid_alpha_002` | interview (warehouse lead) | medium | Counts almost always disagree with ERP; fixed by adjusting ERP to match, no root-cause. |
| `evid_alpha_003` | photograph (site walk) | high | Small-parts bins with faded/missing labels and mixed SKUs. |

## Validation

A lightweight, stdlib-only presence/heading check confirms all six artifacts exist
and contain their expected sections:

```bash
make validate            # includes Phase 4
make validate-phase4     # just these output artifacts
```

The check is structural only — it does **not** assess report quality (that stays a
human judgment for now). See [`../../tests/`](../../tests/).
