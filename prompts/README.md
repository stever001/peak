# Prompts

Reusable, portable **prompt contracts** for Peak's internal first-thread assessment
workflow. These are **internal operating prompts** — a consultant copies the reusable
body into an LLM of their choice. They are vendor-neutral (no provider-specific
assumptions) and are **not** client-facing product prompts. No autonomous agent
runtime exists yet; humans run these and own every output.

Most contracts operate on an `EngagementPacket`
([`../schemas/engagement-packet.schema.json`](../schemas/engagement-packet.schema.json))
and require the model to cite packet `evid_` ids.

## Contracts (Phase 3)

| Folder / file | Workflow | Operates on |
| --- | --- | --- |
| `intake/normalize-client-intake.prompt.md` | New client intake | Raw notes → `ClientIntake` draft |
| `discovery/generate-discovery-plan.prompt.md` | Assessment planning | `EngagementPacket` |
| `evidence/extract-evidence-findings.prompt.md` | Evidence normalization | `EngagementPacket` |
| `reporting/draft-initial-assessment-report.prompt.md` | Initial report | `EngagementPacket` (+ findings) |
| `proposal/generate-next-phase-proposal.prompt.md` | Next-phase proposal | `EngagementPacket` (+ report) |
| `qa/review-assessment-packet.prompt.md` | QA / governance | `EngagementPacket` (+ drafts) |
| `learning/extract-engagement-lessons.prompt.md` | Engagement learning | `EngagementPacket` (+ outputs) |

## Contract structure

Every prompt file is markdown with the same ten sections:

1. Purpose
2. Intended user / operator
3. Required input
4. Expected output
5. Grounding rules
6. Evidence rules
7. Non-goals
8. Output format
9. Quality checks
10. Reusable prompt body (the copy-paste block)

## Shared principles across all contracts

- **Evidence-first.** Outputs cite packet `evid_` ids; uncited claims are demoted to
  follow-ups, not stated as findings.
- **No fabrication.** Never invent client details, metrics, interviews, observations,
  ROI, pricing, or identifiers.
- **Four-way separation.** Keep *observed evidence*, *stakeholder claims*, *consultant
  interpretation*, and *recommended follow-up* distinct — never silently promote a
  claim to a fact.
- **AgentNet is intended, not integrated.** Prompts must not claim any AgentNet
  grounding, lookup, or publication occurred. It is described only as intended future
  grounding/resolution architecture.
- **Internal, human-in-the-loop.** A consultant reviews and owns every result; raw
  output is a draft, never a client-sent artifact.

## Validation

A lightweight inventory check confirms every required contract exists and contains all
ten required section headings:

```bash
make validate            # runs Phase 1 + Phase 2 + Phase 3 checks
make validate-phase3     # just the prompt inventory check
```

The Phase 3 check is stdlib-only (no dependencies). See
[`../tests/`](../tests/).
