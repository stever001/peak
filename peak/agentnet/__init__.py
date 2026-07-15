"""Peak-side governance wrapper for future AgentNet MCP connector use.

**Scaffold / source contracts only.** This package defines Peak's own governance
boundary around the *existing* AgentNet MCP connector (a separate repo). Peak does
**not** reimplement or vendor that connector; it wraps future MCP use with governance
checks so access is owner/engagement-scoped and gated on governance state before any
call could ever be made.

Phase 12 makes **no live calls**: there is no MCP, resolver, AgentNet, or network
integration here, and no AgentNet integration is complete. Capsule publication is
deferred to a later phase and is not implemented.

See docs/AGENTNET_MCP_BOUNDARY.md and docs/PEAK_RESOLVER_ACCESS_POLICY.md.
"""

from __future__ import annotations

from .contracts import (
    KNOWN_MCP_TOOLS,
    TOOL_RESOLVE,
    TOOL_RESOLVE_HISTORY,
    TOOL_VALIDATE_CAPSULE,
    CapsuleValidationRequest,
    CapsuleValidationResponse,
    GovernanceDecision,
    ResolveHistoryRequest,
    ResolveHistoryResponse,
    ResolverContextRequest,
    ResolverContextResponse,
    ResolverToolCallPlan,
)
from .governance import (
    build_tool_call_plan,
    evaluate_capsule_validation_request,
    evaluate_history_request,
    evaluate_resolve_request,
)
from .mock_mcp import MockAgentNetMCPBoundary

__all__ = [
    "KNOWN_MCP_TOOLS",
    "TOOL_RESOLVE",
    "TOOL_RESOLVE_HISTORY",
    "TOOL_VALIDATE_CAPSULE",
    "ResolverContextRequest",
    "ResolverContextResponse",
    "ResolveHistoryRequest",
    "ResolveHistoryResponse",
    "CapsuleValidationRequest",
    "CapsuleValidationResponse",
    "GovernanceDecision",
    "ResolverToolCallPlan",
    "evaluate_resolve_request",
    "evaluate_history_request",
    "evaluate_capsule_validation_request",
    "build_tool_call_plan",
    "MockAgentNetMCPBoundary",
]
