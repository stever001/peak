"""Peak-side governance guard checks for future AgentNet MCP connector use.

Deterministic, dependency-free checks that Peak would run **before** any future MCP
tool call. Phase 12 performs **no live calls** and no AgentNet integration is complete:
these functions only decide whether a call *would be* permitted and why.

Governance state vocabulary mirrors the Phase 9 contracts (peak/db/enums.py and
schemas/*.schema.json are the source of truth); the small blocking sets below are kept
as local literals so this module stays import-light and does not touch the DB layer.

Nothing here opens a socket, reads connector credentials, or reaches the network.
"""

from __future__ import annotations

from .contracts import (
    KNOWN_MCP_TOOLS,
    TOOL_RESOLVE,
    TOOL_RESOLVE_HISTORY,
    TOOL_VALIDATE_CAPSULE,
    GovernanceDecision,
    ResolverToolCallPlan,
)

# Authorization scope that can never authorize a tool call.
REVOKED_AUTHORIZATION_SCOPE = "revoked"

# Lifecycle statuses that block any resolver access.
BLOCKED_LIFECYCLE_STATUSES = frozenset({"revoked", "archived", "deleted_reference_only"})

# Review statuses that block access.
BLOCKED_REVIEW_STATUSES = frozenset({"rejected"})

# The synthetic/test scope must never be combined with live client scope.
FIXTURE_TEST_SCOPE = "fixture_test"

# Substrings that mark a publication-style tool (never allowed in Phase 12).
PUBLICATION_TOOL_MARKERS = ("publish", "publication", "promote", "approve", "release")

# Standard, always-emitted reminder: resolver access is not client-facing approval.
CLIENT_FACING_WARNING = "resolver access does not imply client-facing approval"


def _is_blank(value) -> bool:
    return value is None or (isinstance(value, str) and not value.strip())


def _scope_values(request) -> set:
    """Collect the non-blank scope-ish fields present on a request."""
    values = set()
    for attr in ("resolver_scope", "authorization_scope", "capsule_scope"):
        val = getattr(request, attr, None)
        if not _is_blank(val):
            values.add(val)
    return values


def _evaluate(request, expected_tool: str) -> GovernanceDecision:
    """Run the shared governance checks for a request against its expected tool."""
    reasons: list = []
    warnings: list = []

    tool = getattr(request, "requested_tool", None)

    # 1. Tool must be one of the known MCP tools — and no publication tool is allowed.
    if tool not in KNOWN_MCP_TOOLS:
        lowered = (tool or "").lower()
        if any(marker in lowered for marker in PUBLICATION_TOOL_MARKERS):
            reasons.append(
                f"requested_tool '{tool}' is a publication-style tool; no publication "
                "tool is allowed in Phase 12"
            )
        else:
            reasons.append(
                f"requested_tool '{tool}' is not a known AgentNet MCP tool "
                f"({', '.join(KNOWN_MCP_TOOLS)})"
            )
    elif tool != expected_tool:
        reasons.append(
            f"requested_tool '{tool}' does not match this operation "
            f"(expected '{expected_tool}')"
        )

    # 2. owner_id is always required.
    if _is_blank(getattr(request, "owner_id", None)):
        reasons.append("owner_id is required")

    # 3. Scope: fixture_test must not be mixed with live client/engagement scope; a live
    #    request must carry a client_id or engagement_id.
    scopes = _scope_values(request)
    has_live_ref = not _is_blank(getattr(request, "client_id", None)) or not _is_blank(
        getattr(request, "engagement_id", None)
    )
    if FIXTURE_TEST_SCOPE in scopes:
        if has_live_ref:
            reasons.append(
                "fixture_test scope must not be mixed with live client/engagement scope"
            )
    elif not has_live_ref:
        reasons.append("client_id or engagement_id is required")

    # 4. authorization_scope must be present and not revoked.
    auth = getattr(request, "authorization_scope", None)
    if _is_blank(auth):
        reasons.append("authorization_scope is required")
    elif auth == REVOKED_AUTHORIZATION_SCOPE:
        reasons.append(
            "authorization_scope 'revoked' is not compatible with resolver access"
        )

    # 5. lifecycle_status must not be revoked/archived.
    lifecycle = getattr(request, "lifecycle_status", None)
    if lifecycle in BLOCKED_LIFECYCLE_STATUSES:
        reasons.append(
            f"lifecycle_status '{lifecycle}' is not permitted "
            "(must not be revoked or archived)"
        )

    # 6. review_status must not be rejected.
    review = getattr(request, "review_status", None)
    if review in BLOCKED_REVIEW_STATUSES:
        reasons.append(f"review_status '{review}' is rejected and cannot access the resolver")

    # 7. Resolver access is never client-facing approval — always remind.
    warnings.append(CLIENT_FACING_WARNING)

    return GovernanceDecision(
        requested_tool=tool,
        permitted=not reasons,
        reasons=reasons,
        warnings=warnings,
        live_call_made=False,
        agentnet_integration_active=False,
    )


def evaluate_resolve_request(request) -> GovernanceDecision:
    """Governance decision for an ``agentnet.resolve`` request."""
    return _evaluate(request, TOOL_RESOLVE)


def evaluate_history_request(request) -> GovernanceDecision:
    """Governance decision for an ``agentnet.resolve_history`` request."""
    return _evaluate(request, TOOL_RESOLVE_HISTORY)


def evaluate_capsule_validation_request(request) -> GovernanceDecision:
    """Governance decision for an ``agentnet.validate_capsule`` request."""
    return _evaluate(request, TOOL_VALIDATE_CAPSULE)


def build_tool_call_plan(request) -> ResolverToolCallPlan:
    """Build a (never-executed) tool-call plan wrapping the governance decision.

    Dispatches to the matching evaluator by ``requested_tool``; an unknown or
    publication-style tool yields a rejecting decision. No call is made either way.
    """
    tool = getattr(request, "requested_tool", None)
    if tool == TOOL_RESOLVE:
        decision = evaluate_resolve_request(request)
    elif tool == TOOL_RESOLVE_HISTORY:
        decision = evaluate_history_request(request)
    elif tool == TOOL_VALIDATE_CAPSULE:
        decision = evaluate_capsule_validation_request(request)
    else:
        # Unknown/publication-like tool: _evaluate rejects it (expected == requested,
        # but the tool is not in KNOWN_MCP_TOOLS).
        decision = _evaluate(request, tool)

    return ResolverToolCallPlan(
        requested_tool=tool,
        owner_id=getattr(request, "owner_id", None),
        client_id=getattr(request, "client_id", None),
        engagement_id=getattr(request, "engagement_id", None),
        resolver_scope=getattr(request, "resolver_scope", None),
        decision=decision,
        live_call_made=False,
        agentnet_integration_active=False,
    )
