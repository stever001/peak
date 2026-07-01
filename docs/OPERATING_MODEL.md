# Operating Model

## Purpose

Peak Inventory Solutions delivers inventory consulting: helping clients understand
and improve how they count, control, value, and manage inventory. Today that work
depends heavily on individual consultant expertise. The quality of an engagement
can vary with who runs it, how much time they have, and how well prior lessons are
carried forward.

This internal AI operating system exists to change that. Its purpose is to make
Peak's consulting:

- **Repeatable** — the same rigorous process runs every engagement, regardless of
  which consultant leads it.
- **Scalable** — Peak can take on more engagements without linearly adding senior
  headcount, because structuring and drafting work is agent-assisted.
- **Evidence-based** — every finding, risk, and recommendation traces back to
  observed evidence rather than opinion.
- **Commercially effective** — faster time-to-insight, cleaner reports, and a
  clear, well-justified path from initial assessment to paid next-phase work.

## Operating premise

> Peak uses Agents/AI **internally**, grounded by **AgentNet**, to make inventory
> consulting more repeatable, scalable, evidence-based, and commercially effective.

Agents do the structuring, drafting, cross-referencing, and consistency work.
Peak's consultants and management provide judgment, client relationship, and
accountability. AgentNet is the intended grounding layer that keeps agent output
anchored to Peak's real methodology and evidence.

## Internal vs. client-facing capability

This distinction is deliberate and should be preserved as the system grows.

### Internal Peak capability (current focus)

- Assists Peak consultants and management.
- Structures intake, planning, discovery, evidence, reporting, and proposals.
- Improves the **quality and consistency** of Peak's own work product.
- Keeps a human consultant accountable for every client-facing artifact.
- Captures reusable knowledge across engagements.

### Future client-facing capability (explicitly out of scope for now)

- Client-facing portals, dashboards, or self-serve tools.
- Deliverables generated and sent to clients **without** consultant review.
- Automated client-facing commitments or SLAs.
- Any product Peak's clients log into or operate directly.

We are intentionally building the internal operating system first. Client-facing
capability, if pursued, is a later phase that would build on a proven internal core.

## Roles

| Role | Responsibility in this system |
| --- | --- |
| **Consultant** | Runs engagements, directs agents, exercises judgment, owns client relationship and final deliverables. |
| **Management** | Oversees quality via QA/governance, sets standards, reviews commercial output (proposals). |
| **Agents** | Draft, structure, normalize, cross-reference, and check consistency. Never the final decision-maker. |
| **AgentNet (intended)** | Grounds and resolves agent output against Peak methodology, prior engagements, and evidence standards. |

**How "agents" work today:** there is no autonomous agent runtime yet. The agent role
is currently fulfilled by **prompt contracts** ([`../prompts/`](../prompts/)) — fixed,
reviewed instructions a consultant copies into an LLM, operating on an
`EngagementPacket` and required to cite evidence. This keeps a human in the loop while
Peak proves the workflow, and the contracts double as the specification for any future
agents.

## AgentNet as grounding architecture (intended)

AgentNet is referenced as the **intended grounding and resolution layer**. Its role
is to ensure agent outputs are:

- **Grounded** — anchored to Peak's documented methodology and standards.
- **Resolved** — reconciled against prior engagements and reusable knowledge so the
  system gets smarter over time.
- **Traceable** — connected to concrete evidence rather than free-floating claims.

**Implementation status: not yet integrated.** All references to AgentNet grounding
describe target architecture. No file in this repository should claim AgentNet
integration is complete unless it demonstrably is.

## Guiding principles

1. **Human-in-the-loop by default.** Agents assist; consultants decide.
2. **Evidence-first.** No finding without a traceable `EvidenceReference`.
3. **Portable, not locked in.** No dependence on a single model or vendor.
4. **Lightweight before elaborate.** Prove the workflow before adding machinery.
5. **Governed output.** Internal QA/governance reviews agent output before it
   reaches a client.
6. **Learning compounds.** Every engagement feeds reusable knowledge back in.

## Success measures (early)

- Reduced time from intake to a client-ready initial report.
- Consistent report structure and evidence traceability across consultants.
- A clear, well-supported next-phase proposal produced from every assessment.
- Fewer quality issues caught late; more caught by internal QA.
- Growing reusable knowledge base that improves later engagements.
