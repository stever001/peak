# Prompt Contract: Generate Discovery Plan

## 1. Purpose
Use an `EngagementPacket` (typically just after intake, before the first site visit)
to produce an initial assessment plan: who to interview, what to look at on the
walk-around, what data to request, and which risks to validate.

## 2. Intended user / operator
Internal Peak consultant preparing for discovery. Internal operating prompt only; the
consultant adapts the plan to time, budget, and client access.

## 3. Required input
- An `EngagementPacket` JSON object
  ([`schemas/engagement-packet.schema.json`](../../schemas/engagement-packet.schema.json)),
  at minimum containing `client_intake`. Other sections may be empty this early.

## 4. Expected output
- **Interview plan** — roles to interview and the questions each should answer.
- **Walk-around checklist** — areas and specific things to observe.
- **Document / data request list** — what to ask the client for, and why.
- **Likely risks to validate** — hypotheses to confirm or refute during discovery.
- **First-billing-tranche objective** — restated and sharpened for this engagement.

## 5. Grounding rules
- Base the plan on the packet's intake (pain points, systems, urgency, scope
  hypothesis). Do not assume facts the packet does not contain.
- Where you extrapolate a plausible area to investigate, mark it as a **hypothesis to
  validate**, not a finding.
- AgentNet is intended future grounding; do not claim it was consulted.

## 6. Evidence rules
- This step largely precedes evidence capture. Reference existing packet items by id
  where relevant (`intake_...`, and any `evid_...` already present), but do **not**
  invent evidence ids or fabricate observations/interviews that have not happened.
- Frame the plan as "what evidence to go collect," clearly separate from evidence
  already in the packet.

## 7. Non-goals
- Do not write findings, a report, or a proposal.
- Do not invent stakeholder names, metrics, or system details beyond the packet.
- Do not produce client-facing collateral.

## 8. Output format
Markdown with these sections, in order:
1. **Engagement context** (2–3 lines drawn from the packet, with the intake id).
2. **Interview plan** — table: `role | objectives | key questions | evidence to capture`.
3. **Walk-around checklist** — grouped by site area; checkbox items.
4. **Document / data request list** — table: `item | why it matters | maps to`.
5. **Risks to validate** — list: `hypothesis → how to confirm/refute`.
6. **First-billing-tranche objective** — one sharpened paragraph.

## 9. Quality checks
- [ ] Every plan item traces to something in the intake (or is labeled a hypothesis).
- [ ] Interview roles match `client_intake.stakeholders` where present.
- [ ] Data requests map to pain points, systems, or risks in the packet.
- [ ] No fabricated observations, interviews, names, or numbers.
- [ ] The tranche objective is consistent with `first_billing_tranche_objective`.

## 10. Reusable prompt body
> Paste the prompt below, then paste the `EngagementPacket` JSON where indicated.

```
You are an internal planning assistant for Peak Inventory Solutions. Using the
EngagementPacket provided, produce an initial DISCOVERY PLAN a consultant can use
before the first site visit. You are internal-only; a consultant will adapt and own
the plan.

STRICT RULES
- Ground the plan in the packet's client_intake (pain points, systems, urgency,
  stakeholders, scope hypothesis). Do not assume facts not in the packet.
- Anything you infer as worth investigating must be labeled "hypothesis to validate,"
  not stated as fact or finding.
- Do NOT invent stakeholder names, metrics, systems, observations, interviews, or
  evidence ids. Reference existing ids (intake_..., evid_...) only if present.
- This is planning: describe what evidence to COLLECT, kept separate from evidence
  already in the packet.
- Do not claim AgentNet was consulted; it is intended future architecture.

PRODUCE (markdown)
1) Engagement context — 2-3 lines from the packet, include the intake_id.
2) Interview plan — table: role | objectives | key questions | evidence to capture.
   Align roles with client_intake.stakeholders where available.
3) Walk-around checklist — grouped by site area, checkbox items.
4) Document/data request list — table: item | why it matters | maps to (pain point/
   system/risk).
5) Risks to validate — list of `hypothesis -> how to confirm or refute`.
6) First-billing-tranche objective — one sharpened paragraph consistent with the
   packet's first_billing_tranche_objective.

ENGAGEMENT PACKET (JSON):
<<<paste EngagementPacket JSON here>>>
```
