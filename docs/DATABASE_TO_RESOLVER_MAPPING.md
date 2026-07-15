# Database to Resolver Mapping

How live controlled-database records prepare for **private resolver capsules** — the
future governed grounding/resolution layer. **Planning only — no publication, resolver
integration, or capsule store is implemented, and no capsule is published.** AgentNet
grounding is **intended future architecture, not implemented**.

The controlled database is a **pre-capsulization staging layer**: as consulting work
refines messy client data into verified, approved, well-scoped records, those records
become eligible to be prepared as capsules for eventual AgentNet-based agentic AI
operations in warehouse/inventory workflows.

## Likely capsule candidates

Records that, once governed and approved, are likely to become capsule candidates:

- **Verified evidence** (`EvidenceReference` with `EvidenceStatus = verified`).
- **Source-system references** (`SourceSystemReference` — grounding pointers).
- **Workflow maps** (derived from `WorkflowObservation`).
- **Approved operational facts** (from visual/workflow observations and system profile).
- **Inventory policies** (from `InventorySystemProfile` and approved findings).
- **Control gaps** (`ControlGap`, once approved).
- **Approved recommendations** (`Recommendation` with client-facing/internal approval).
- **Financial impact estimates** — **only when approved and appropriately scoped**.
- **Peak methodology abstractions** (reusable, client-agnostic methodology capsules).

Identity records (Client, Engagement) and governance/process records (ReviewRecord,
AgentRunRecord) are **not** capsule candidates.

## Capsule readiness criteria

A record is capsule-ready only when **all** of the following hold:

- **Evidence-linked** — carries `evidence_ids` tracing to supporting evidence.
- **Source-labeled** — reported vs. verified is explicit; provenance is recorded.
- **Authorization scope assigned** — a valid `authorization_scope` (not `revoked`).
- **Sensitivity class assigned** — `internal` / `confidential` / `restricted`.
- **Review status sufficient** — at least `approved_internal` (and, for client-facing
  content, `client_facing_approved`).
- **Lifecycle status active** — `lifecycle_status = active` (not superseded/revoked/archived).
- **Client/engagement scope clear** — `client_id` / `engagement_id` unambiguous.

Readiness is staged through a `CapsulePublicationCandidate` (see
[`DATABASE_RECORD_MODEL.md`](DATABASE_RECORD_MODEL.md)) and gated by governance approval;
capsule state follows `ResolverCapsuleStatus` in
[`STATE_TRANSITIONS.md`](STATE_TRANSITIONS.md).

## Resolver publication options

Two governed options; the choice is per capsule, by policy:

1. **Public-but-segregated resolver** — the likely primary model — using **Node/capsule
   governance** techniques.
2. **Private resolver** — retained as an option where required (more restrictive scope).

### "Public-but-segregated" definition

**Public-but-segregated does NOT mean public disclosure.** It means the capsule is
**resolver-accessible but governed** — scoped, authorized, and **segregated by node/capsule
metadata and policy**. Access is mediated by the resolver's governance (authorization
scope, sensitivity class, node/capsule segregation), not open to the public. Client
confidentiality is preserved; nothing is disclosed publicly by making a capsule
resolver-accessible.

## Resolver access via the AgentNet MCP connector

Future resolver *reads* (grounding lookups, resolve history, capsule validation) would go
through the **existing AgentNet MCP connector** (a separate repo), governed by Peak's own
wrapper — see [`AGENTNET_MCP_BOUNDARY.md`](AGENTNET_MCP_BOUNDARY.md) and
[`PEAK_RESOLVER_ACCESS_POLICY.md`](PEAK_RESOLVER_ACCESS_POLICY.md). That wrapper is
scaffold/contracts only: **no live calls**, and **AgentNet integration is not complete**.
Note the distinction — access/grounding is being scaffolded now; **capsule publication
(the mapping below) remains deferred** and is not implemented.

## Guardrails

- **No publication implementation exists** — this is a mapping/plan only.
- **No uncontrolled publication.** Every publication requires an approved
  `CapsulePublicationCandidate` and a `resolver publisher` action (future role).
- **No agent may publish capsules** or approve publication without human/governance
  approval (see [`DATABASE_ACCESS_AND_AUDIT.md`](DATABASE_ACCESS_AND_AUDIT.md)).
- Client-specific capsules stay private/segregated; promotion to reusable **Peak
  methodology** requires abstraction + human review + governance approval.
