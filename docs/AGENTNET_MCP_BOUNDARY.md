# AgentNet MCP Boundary (Phase 12)

How Peak governs **future** use of the **existing AgentNet MCP connector** without
reimplementing it. **Scaffold / contracts only — Phase 12 makes no live calls**, and
**AgentNet integration is not complete**. Capsule publication strategy is deferred to a
later phase and is **not** designed or implemented here.

## The existing connector (separate repo)

There is an **existing AgentNet MCP connector** maintained separately (the
`agentnet-connectors` repo). It is a **transport/integration layer** that forwards MCP
tool calls to an AgentNet-compatible **Resolver HTTP API**. Peak **does not duplicate,
vendor, or copy** that connector into this repository. None of the connector's code
lives here.

Peak's job is narrower and complementary: provide a **Peak governance wrapper** — a
boundary and a set of governance checks — that decides *whether* and *how* Peak would
ever use the connector, before any call is made.

## Known MCP tools

The connector currently exposes exactly three tools. Peak treats this as the **only**
permitted tool surface in Phase 12:

| Tool | Purpose (connector-side) | Peak-side contract |
| --- | --- | --- |
| `agentnet.resolve` | Resolve grounding context | `ResolverContextRequest` → `ResolverContextResponse` |
| `agentnet.resolve_history` | Fetch prior resolve history | `ResolveHistoryRequest` → `ResolveHistoryResponse` |
| `agentnet.validate_capsule` | Validate a capsule's shape/metadata | `CapsuleValidationRequest` → `CapsuleValidationResponse` |

Any other tool — in particular any **publication-style** tool — is **rejected** by
Peak governance in this phase (see [`PEAK_RESOLVER_ACCESS_POLICY.md`](PEAK_RESOLVER_ACCESS_POLICY.md)).

## What Peak adds (this phase)

Peak wraps future MCP use with governance checks. The Peak-side scaffold is:

- [`../peak/agentnet/contracts.py`](../peak/agentnet/contracts.py) — request/response
  dataclasses and the closed `KNOWN_MCP_TOOLS` set. Source contracts only; no stored
  records.
- [`../peak/agentnet/governance.py`](../peak/agentnet/governance.py) — deterministic
  guard checks (`evaluate_resolve_request`, `evaluate_history_request`,
  `evaluate_capsule_validation_request`, `build_tool_call_plan`) run **before** any call.
- [`../peak/agentnet/mock_mcp.py`](../peak/agentnet/mock_mcp.py) — a **no-network mock
  boundary** (`MockAgentNetMCPBoundary`) that runs governance first and returns a
  controlled response. It never opens a socket, reads connector credentials, or calls the
  real connector.

Every response and plan carries `live_call_made = False` and
`agentnet_integration_active = False`.

## Governance checks (summary)

Before a call would be permitted, the wrapper requires:

- `owner_id` present.
- `client_id` or `engagement_id` present for live requests.
- `requested_tool` ∈ {`agentnet.resolve`, `agentnet.resolve_history`,
  `agentnet.validate_capsule`}; **no publication tool** is allowed.
- `authorization_scope` present and not `revoked`.
- `lifecycle_status` not `revoked`/`archived`.
- `review_status` not `rejected`.
- `fixture_test` scope is **never** mixed with live client/engagement scope.
- Resolver access **never** implies client-facing approval (emitted as a standing
  warning on every decision).

See the full policy in [`PEAK_RESOLVER_ACCESS_POLICY.md`](PEAK_RESOLVER_ACCESS_POLICY.md).

## Future connector configuration (names only — no secrets)

When integration is eventually built, the *connector* (not this repo) is configured via
environment variables such as `AGENTNET_BASE_URL`, `AGENTNET_API_KEY`, and
`AGENTNET_TIMEOUT`. These are named here only as **future connector configuration**;
**no credentials or values are committed**, and Peak's wrapper does not read them in
Phase 12.

## Explicit boundaries

- **No live calls.** Nothing here performs an MCP, resolver, AgentNet, HTTP, or network
  call. The only runnable boundary is a mock.
- **No connector code copied.** The connector remains a separate repo.
- **No capsule publication.** Publication strategy is deferred; it is not designed or
  implemented in Phase 12.
- **AgentNet integration is not complete.** These are contracts and a mock boundary,
  ahead of any real integration.
