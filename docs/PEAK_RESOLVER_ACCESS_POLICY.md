# Peak Resolver Access Policy (Phase 12)

Peak-side policy for **who and what may request resolver context** through the existing
AgentNet MCP connector, and under what governance. **Policy + scaffold only — no live
calls, no AgentNet integration is complete, and no capsule publication** is designed or
implemented. This complements [`AGENTNET_MCP_BOUNDARY.md`](AGENTNET_MCP_BOUNDARY.md),
which describes the boundary and the Peak governance wrapper.

## Who/what may request resolver context (future)

Once integration exists, resolver access is initiated only by **authorized Peak-side
callers acting for an authorized live engagement** — for example a consultant-invoked
internal workflow or a future agent runtime operating under human review. Every request
must carry an accountable `owner_id`. Unauthenticated, client-facing, or third-party
callers are out of scope. Today there is **no caller**: the only runnable path is the
no-network mock boundary.

## Engagement / client / owner scoping

Every resolver request is scoped:

- **`owner_id` (required):** the accountable Peak party/role for the request.
- **`client_id` / `engagement_id`:** at least one is required for a live request, so
  access is bound to a specific authorized engagement/client.
- **`resolver_scope` / `authorization_scope` / `capsule_scope`:** describe what body of
  grounding is being reached and under what authorization.
- **`fixture_test` scope** is synthetic-only and **must never be mixed with live
  client/engagement scope**.

## Allowed tools

Only the three tools currently exposed by the connector are permitted:

- `agentnet.resolve`
- `agentnet.resolve_history`
- `agentnet.validate_capsule`

## Prohibited actions

- **No publication tool** of any kind (no publish/promote/approve/release). Capsule
  publication is deferred to a later phase.
- **No uncontrolled publication** of client data or capsules — ever, and never without
  explicit governance approval (see
  [`DATABASE_TO_RESOLVER_MAPPING.md`](DATABASE_TO_RESOLVER_MAPPING.md)).
- **No client-facing approval** is granted or implied by resolver access alone; resolver
  access is an internal grounding action, not a client sign-off.
- **No live network/MCP/resolver call** in Phase 12.
- **No connector reimplementation** — Peak wraps the existing connector; it does not copy
  it.

## Governance states checked before tool access

Before any tool call would be permitted, the wrapper
([`../peak/agentnet/governance.py`](../peak/agentnet/governance.py)) checks the Phase 9
governance vocabulary:

- `authorization_scope` present and **not `revoked`**.
- `lifecycle_status` **not `revoked` or `archived`** (nor `deleted_reference_only`).
- `review_status` **not `rejected`**.
- `owner_id` present; live requests carry `client_id`/`engagement_id`.

A request that fails any check is **not permitted**, with machine-readable `reasons`.

## Audit expectations (future `AgentRunRecord`)

When a real runtime eventually makes resolver calls, each call is expected to be recorded
as an **`AgentRunRecord`** (see
[`DATABASE_ACCESS_AND_AUDIT.md`](DATABASE_ACCESS_AND_AUDIT.md) and
[`DATABASE_RECORD_MODEL.md`](DATABASE_RECORD_MODEL.md)): who/what (`owner_id`,
`agent_run_id`), the tool used, the client/engagement scope, the governance decision, and
the outcome — so resolver access is attributable and reviewable. Phase 12 writes **no**
such records; this documents the expectation, not an implementation.

## Resolver options remain architecture only

The **public-but-segregated** resolver (governed, not public disclosure) versus a
**private resolver** choice remains **architecture only**
([`RESOLVER_CAPSULE_ARCHITECTURE.md`](RESOLVER_CAPSULE_ARCHITECTURE.md),
[`DATABASE_TO_RESOLVER_MAPPING.md`](DATABASE_TO_RESOLVER_MAPPING.md)). Nothing in this
phase selects, stands up, or publishes to a resolver. **AgentNet integration is not
complete.**
