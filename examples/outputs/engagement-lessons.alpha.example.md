# Engagement Lessons — Client Alpha (EXAMPLE OUTPUT)

> Sample output of `prompts/learning/extract-engagement-lessons.prompt.md` run against
> [`../engagement-packet.example.json`](../engagement-packet.example.json) and the
> engagement's outputs (report, proposal, QA review). Internal retrospective; feeds
> Peak's own methodology. Fictional/anonymized. **Candidate capsules are DRAFT only —
> nothing here has been published to or grounded by AgentNet.**

## Engagement reference
`intake_alpha_2026` / packet `pkt_alpha_2026` — Client Alpha, medium industrial-parts
distributor; assessment triggered by an external stock-count audit.

## Reusable patterns
Labeled **observed** (seen this engagement) vs. **hypothesized** (may generalize).
- **Observed:** "adjust ERP to match the count, no reason code" is the mechanism that
  *masks* recurring accuracy problems (`evid_alpha_002`, `wobs_alpha_adjustments`).
  → **Hypothesized generalizable:** unreviewed adjustment authority is a recurring
  root cause of persistent record inaccuracy at distributors.
- **Observed:** branches keep parallel spreadsheets because they distrust ERP
  availability (`evid_alpha_002`). → **Hypothesized:** "competing sources of truth"
  is a strong early signal worth probing whenever spreadsheets shadow an ERP.
- **Observed:** a single high-reliability floor observation (`evid_alpha_003`, bins)
  gave the assessment its most concrete, actionable quick win, versus medium-reliability
  interviews. → **Hypothesized:** prioritize at least one photographable floor finding
  early to anchor credibility while data access is pending.

## Checklist improvements
- Add to the discovery walk-around: **verify ERP reason-code/approval capability**
  early — the highest-value control recommendation gated on it and it was unknown.
- Add to intake: **explicitly capture counting cadence from each stakeholder** to catch
  contradictions (the monthly-vs-weekly conflict surfaced only in interview).
- Add a **data-access checklist** up front (ERP export, cycle-count report, adjustment
  log, branch spreadsheets) with owner and status, since access blockers shaped scope.

## Prompt improvements
| Prompt file | Suggested change | Reason |
| --- | --- | --- |
| `prompts/discovery/generate-discovery-plan.prompt.md` | Prompt for an explicit "access blockers & owners" subsection | Access status materially gated this engagement |
| `prompts/evidence/extract-evidence-findings.prompt.md` | Ask the model to tag each finding's evidence **reliability** and **corroboration count** | Two of three items were single-source medium; QA needed this surfaced |
| `prompts/reporting/draft-initial-assessment-report.prompt.md` | Require a one-line evidence-reliability statement in the executive summary | QA flagged its absence as a client-readiness fix |
| `prompts/proposal/generate-next-phase-proposal.prompt.md` | Elevate "preconditions/gates" from prose to a required labeled section | Assumptions (ERP access/capability) were easy to under-weight |

## Schema gaps
| Object / field | What was missing | Impact |
| --- | --- | --- |
| `EvidenceReference` | No explicit `corroborated_by` / linkage between evidence items describing the same issue | Corroboration had to be inferred narratively |
| `StakeholderInterview.quantified_impacts` | No `verified` flag distinguishing reported vs. confirmed figures | The "6–8 hrs/week" figure needed manual labeling everywhere |
| `EngagementPacket` | No first-class `open_contradictions` or `access_blockers` list at packet level | Both were important but lived inside nested notes |

## Candidate internal knowledge capsules (DRAFT — not grounded, not published)
> These are drafts for **possible future** AgentNet grounding. No capsule has been
> published or grounded; AgentNet remains intended future architecture.

- **[DRAFT] Capsule: "Unreviewed adjustments mask accuracy loss."**
  Summary: when staff edit system on-hand to match counts without approval/reason
  codes, accuracy problems recur and may conceal shrink. When to apply: any assessment
  finding direct count-to-system adjustments. Source: `evid_alpha_002`,
  `wobs_alpha_adjustments`.
- **[DRAFT] Capsule: "Shadow spreadsheets = trust signal."**
  Summary: parallel branch/store spreadsheets indicate distrust of the system of
  record; probe source-of-truth confidence early. When to apply: ERP + spreadsheet
  environments. Source: `evid_alpha_002`, system profile.
- **[DRAFT] Capsule: "Anchor with a photographable floor finding."**
  Summary: secure one high-reliability visual finding early to anchor credibility while
  data access is pending. When to apply: data-blocked initial assessments. Source:
  `evid_alpha_003`.

## Follow-up actions
- [ ] (`consultant_a`) Add access-blocker + contradiction sections to the discovery
  prompt and packet notes template.
- [ ] (Peak methodology owner) Review the three schema-gap suggestions for a future
  schema revision — **not** applied in this phase.
- [ ] (Peak methodology owner) Hold the DRAFT capsules for a future AgentNet-grounding
  decision; do not treat as published.
- [ ] (`consultant_a`) Feed the QA "required fixes" back into the report/proposal before
  any client-facing version.
