# Resolver Capsule Architecture

How Peak's **private resolver capsules** work as the governed grounding/resolution
layer. **Architecture documentation only** — no resolver, capsule store, or AgentNet
integration is implemented. Resolver/AgentNet grounding is **intended future
architecture, not implemented in this repository**.

## What a resolver capsule is

A **resolver capsule** is a private, governed **grounding record**: a scoped unit of
knowledge that internal Peak AI workflows can be grounded against, holding metadata and
references (to sources and evidence) rather than raw client content. Capsules live in
Peak's controlled storage / resolver layer — **not in Git**.

The capsule record shape is defined by
[`../schemas/resolver-capsule-record.schema.json`](../schemas/resolver-capsule-record.schema.json)
(a contract only; no instances are committed).

## Ownership and scoping

`capsule_scope` distinguishes three kinds:

- **Peak internal methodology capsules** (`peak_methodology`) — reusable Peak knowledge
  (patterns, checklists, methodology). Not client data.
- **Client-specific private capsules** (`client_private`) — grounded on a specific
  client/engagement. Private engagement data; never reused across clients or published
  without governance approval.
- **Fixture/test capsules** (`fixture_test`) — only if ever needed for testing. Must be
  **clearly marked**, synthetic, and **never live-client** data. Not committed as stored
  data.

## Governance rule

**No shared or public publication of client data** — and no cross-client reuse of
client-private capsules — **without explicit governance approval.** This mirrors the
rule in [`DATA_HANDLING_POLICY.md`](DATA_HANDLING_POLICY.md).

## Capsule metadata requirements

Every capsule record carries:

| Field | Purpose |
| --- | --- |
| `owner_id` | The owning party (Peak team/role, or governing owner). |
| `client_id` / `engagement_id` | The client/engagement it pertains to, where applicable. |
| `capsule_scope` | `peak_methodology` \| `client_private` \| `fixture_test`. |
| `source_reference_ids` | `SourceSystemReference` ids the capsule is grounded on. |
| `evidence_ids` | `EvidenceReference` ids the capsule is grounded on. |
| `sensitivity_class` | `internal` \| `confidential` \| `restricted`. |
| `authorization_scope` | The authorization governing use. |
| `review_status` | Governance review state. |
| `lifecycle_status` | `draft` \| `active` \| `archived` \| `retired`. |

Grounding is **traceable by construction**: a capsule points back to the sources and
evidence it was built from.

## Capsule lifecycle & governance states

A capsule moves through the `ResolverCapsuleStatus` family — `draft_capsule` →
`private_client_capsule` → `reviewed_private` → `active_private`, with promotion to
`methodology_candidate` (only after abstraction + human review) and `approved_methodology`
(only after governance approval), plus `superseded`/`revoked`/`archived`. Agents may
create drafts and *propose* methodology candidates but may not activate, approve,
publish, or promote. See [`GOVERNANCE_STATES.md`](GOVERNANCE_STATES.md) §F and the
transitions in [`STATE_TRANSITIONS.md`](STATE_TRANSITIONS.md).

## From controlled database to capsules

Capsules are prepared from records in the controlled engagement database once they meet
readiness criteria (evidence-linked, source-labeled, approved, scoped). The mapping,
readiness checklist, and publication options (**public-but-segregated** — governed, not
public disclosure — and **private resolver**) are in
[`DATABASE_TO_RESOLVER_MAPPING.md`](DATABASE_TO_RESOLVER_MAPPING.md). No publication is
implemented.

## AgentNet / resolver integration status

AgentNet and the resolver integration are **intended future architecture**. Nothing in
this repository performs, implements, or implies any capsule creation, resolver lookup,
grounding, or AgentNet publication. These documents describe the target so the data
contracts and governance are defined before any integration is built.
