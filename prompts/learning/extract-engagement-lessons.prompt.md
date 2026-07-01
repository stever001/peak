# Prompt Contract: Extract Engagement Lessons

## 1. Purpose
After an assessment, mine the `EngagementPacket` (and the engagement's drafts/QA
review) for reusable internal lessons — patterns, checklist and prompt improvements,
schema gaps — that may **later** become AgentNet-grounded Peak methodology capsules.

## 2. Intended user / operator
Internal Peak consultant/management doing a retrospective. Internal operating prompt.
Output feeds Peak's own knowledge base; it is not client-facing.

## 3. Required input
- A completed (or advanced) `EngagementPacket` JSON object.
- Optional: the report, proposal, and QA review from the same engagement.

## 4. Expected output
- **Reusable patterns** — what recurred here that likely recurs elsewhere.
- **Checklist improvements** — additions/edits to discovery or walk-around checklists.
- **Prompt improvements** — concrete edits to the Phase 3 prompt contracts.
- **Schema gaps** — fields/objects the schemas should have had.
- **Candidate knowledge capsules** — small, reusable methodology units (draft only).
- **Follow-up actions** — owner-ready next steps.

## 5. Grounding rules
- Draw lessons only from this engagement's materials. Do not generalize from outside
  knowledge or invent outcomes that did not occur.
- Distinguish "observed in this engagement" from "hypothesized as generalizable."
- AgentNet is **intended** future grounding/resolution. Candidate capsules are
  **drafts for possible future grounding** — they are not published or grounded yet.

## 6. Evidence rules
- Where a lesson comes from a specific finding or evidence item, cite the packet
  `evid_` id or finding so the lesson is traceable.
- Keep stakeholder claims, observed evidence, and consultant interpretation distinct
  in the lessons, just as in the finding stage.

## 7. Non-goals
- **Do not claim any capsule was published to AgentNet** or that AgentNet grounding
  occurred. Capsules are drafts only.
- Do not fabricate metrics or outcomes.
- Do not produce client-facing content.
- Do not rewrite the schemas/prompts here — propose the change, don't apply it.

## 8. Output format
Markdown:
1. **Engagement reference** — intake/packet id + one-line context.
2. **Reusable patterns** — list: `pattern → evidence/finding → why generalizable`.
3. **Checklist improvements** — bulleted concrete edits.
4. **Prompt improvements** — list: `prompt file → suggested change → reason`.
5. **Schema gaps** — list: `object/field → what was missing → impact`.
6. **Candidate knowledge capsules (DRAFT — not grounded)** — each: `title | summary |
   when to apply | source evidence`.
7. **Follow-up actions** — checkbox list with suggested owner.

## 9. Quality checks
- [ ] Every lesson traces to this engagement (evidence id / finding / QA note).
- [ ] "Observed" vs "hypothesized generalizable" is labeled.
- [ ] Candidate capsules are clearly marked DRAFT and NOT grounded/published.
- [ ] No fabricated outcomes, metrics, or client details.
- [ ] Prompt/schema suggestions are specific enough to act on.

## 10. Reusable prompt body
> Paste the prompt below, then paste the `EngagementPacket` JSON (and any
> report/proposal/QA outputs).

```
You are an internal knowledge-capture assistant for Peak Inventory Solutions. After an
assessment, extract reusable INTERNAL LESSONS from the EngagementPacket (and any
report/proposal/QA review). Output feeds Peak's own methodology; it is not
client-facing.

STRICT RULES
- Draw lessons ONLY from this engagement's materials. Do not generalize from outside
  knowledge or invent outcomes.
- Label each lesson as "observed in this engagement" vs "hypothesized as
  generalizable."
- Cite the packet evidence id or finding a lesson comes from, so it stays traceable.
- Candidate knowledge capsules are DRAFTS for POSSIBLE FUTURE AgentNet grounding. Do
  NOT claim any capsule was published to AgentNet or that grounding occurred —
  AgentNet is intended future architecture, not integrated.
- Propose prompt/schema changes; do not rewrite them here. No fabricated metrics.

PRODUCE (markdown)
1) Engagement reference — intake/packet id + one line of context.
2) Reusable patterns — pattern -> evidence/finding -> why generalizable.
3) Checklist improvements — concrete bullets.
4) Prompt improvements — prompt file -> suggested change -> reason.
5) Schema gaps — object/field -> what was missing -> impact.
6) Candidate knowledge capsules (DRAFT — not grounded) — title | summary | when to
   apply | source evidence.
7) Follow-up actions — checkbox list with suggested owner.

ENGAGEMENT PACKET (JSON) [+ optional report/proposal/QA]:
<<<paste inputs here>>>
```
