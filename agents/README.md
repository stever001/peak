# Agents

Each subfolder is an **agent capability group** supporting one or more of the ten
internal workflows (see [`../docs/AGENT_WORKFLOWS.md`](../docs/AGENT_WORKFLOWS.md)).

Agents **assist**; Peak consultants decide. No agent output reaches a client without
consultant review and QA/governance sign-off. Outputs are intended to be grounded by
AgentNet (target architecture — not yet live).

| Folder | Workflows covered |
| --- | --- |
| `intake/` | New client intake |
| `discovery/` | Assessment planning, interview prep, walk-around structuring |
| `evidence/` | Evidence normalization and finding derivation |
| `reporting/` | Initial management report generation |
| `proposal/` | Quick-win identification, next-phase proposal generation |
| `qa/` | Internal QA / governance review |
| `learning/` | Engagement learning / reusable knowledge capture |

> No agent logic is implemented yet. These folders are placeholders defining where
> lightweight, schema-conforming agents will live (see
> [`../docs/IMPLEMENTATION_PLAN.md`](../docs/IMPLEMENTATION_PLAN.md), Phase 2).
