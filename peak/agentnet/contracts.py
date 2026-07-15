"""Peak-side request/response contracts for future AgentNet MCP connector use.

**Source contracts only — no stored records, no live calls.** These lightweight
dataclasses describe how Peak would *ask* the existing AgentNet MCP connector (a
separate repo — see docs/AGENTNET_MCP_BOUNDARY.md) to resolve context, fetch resolve
history, or validate a capsule, and how a governed decision/response is shaped on
Peak's side.

Peak does **not** reimplement the connector. Nothing here opens a socket, reads
connector credentials, or performs an MCP/HTTP/network call. Every response carries
``live_call_made = False`` and ``agentnet_integration_active = False``: Phase 12 makes
**no live calls** and no AgentNet integration is complete.

Capsule *publication* is deferred to a later phase and is deliberately not modeled here.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import List, Optional

# The three tools currently exposed by the existing AgentNet MCP connector. Peak treats
# this as the *only* permitted tool surface in Phase 12. Any other tool — notably any
# publication-style tool — is rejected by governance (see peak/agentnet/governance.py).
TOOL_RESOLVE = "agentnet.resolve"
TOOL_RESOLVE_HISTORY = "agentnet.resolve_history"
TOOL_VALIDATE_CAPSULE = "agentnet.validate_capsule"

# Exact, closed set of known MCP tools. Order-independent; compared as a set.
KNOWN_MCP_TOOLS = (TOOL_RESOLVE, TOOL_RESOLVE_HISTORY, TOOL_VALIDATE_CAPSULE)


# --------------------------------------------------------------------------------------
# Requests (Peak-side intent; never sent anywhere in Phase 12)
# --------------------------------------------------------------------------------------


@dataclass
class ResolverContextRequest:
    """Intent to resolve grounding context for an engagement (``agentnet.resolve``)."""

    owner_id: Optional[str] = None
    client_id: Optional[str] = None
    engagement_id: Optional[str] = None
    requested_tool: str = TOOL_RESOLVE
    resolver_scope: Optional[str] = None
    authorization_scope: Optional[str] = None
    review_status: Optional[str] = None
    lifecycle_status: Optional[str] = None
    capsule_scope: Optional[str] = None
    query: Optional[str] = None


@dataclass
class ResolveHistoryRequest:
    """Intent to fetch prior resolve history (``agentnet.resolve_history``)."""

    owner_id: Optional[str] = None
    client_id: Optional[str] = None
    engagement_id: Optional[str] = None
    requested_tool: str = TOOL_RESOLVE_HISTORY
    resolver_scope: Optional[str] = None
    authorization_scope: Optional[str] = None
    review_status: Optional[str] = None
    lifecycle_status: Optional[str] = None
    capsule_scope: Optional[str] = None
    query: Optional[str] = None


@dataclass
class CapsuleValidationRequest:
    """Intent to validate a capsule's shape/metadata (``agentnet.validate_capsule``).

    ``capsule_payload`` is a metadata-shaped dict describing the capsule to validate;
    it is **not** persisted and is never transmitted in Phase 12.
    """

    owner_id: Optional[str] = None
    client_id: Optional[str] = None
    engagement_id: Optional[str] = None
    requested_tool: str = TOOL_VALIDATE_CAPSULE
    resolver_scope: Optional[str] = None
    authorization_scope: Optional[str] = None
    review_status: Optional[str] = None
    lifecycle_status: Optional[str] = None
    capsule_scope: Optional[str] = None
    capsule_payload: Optional[dict] = None


# --------------------------------------------------------------------------------------
# Governance decision + tool-call plan
# --------------------------------------------------------------------------------------


@dataclass
class GovernanceDecision:
    """Result of Peak-side governance checks run *before* any future MCP call.

    ``permitted`` is only ``True`` when there are no blocking ``reasons``. Even a
    permitted decision does not imply client-facing approval and does not perform a call.
    """

    requested_tool: Optional[str] = None
    permitted: bool = False
    reasons: List[str] = field(default_factory=list)
    warnings: List[str] = field(default_factory=list)
    live_call_made: bool = False
    agentnet_integration_active: bool = False


@dataclass
class ResolverToolCallPlan:
    """A *plan* describing a tool call Peak could make once integration exists.

    A plan is never executed in Phase 12: it bundles the governance decision with the
    scoping fields so a future runtime (with human review) could act on it. Building a
    plan performs no call — ``live_call_made`` stays ``False``.
    """

    requested_tool: Optional[str] = None
    owner_id: Optional[str] = None
    client_id: Optional[str] = None
    engagement_id: Optional[str] = None
    resolver_scope: Optional[str] = None
    decision: Optional[GovernanceDecision] = None
    live_call_made: bool = False
    agentnet_integration_active: bool = False


# --------------------------------------------------------------------------------------
# Responses (produced only by the no-network mock boundary)
# --------------------------------------------------------------------------------------


@dataclass
class ResolverContextResponse:
    """Controlled response for a resolve request from the mock boundary (no network)."""

    requested_tool: str = TOOL_RESOLVE
    permitted: bool = False
    reasons: List[str] = field(default_factory=list)
    warnings: List[str] = field(default_factory=list)
    is_mock: bool = True
    note: str = ""
    live_call_made: bool = False
    agentnet_integration_active: bool = False


@dataclass
class ResolveHistoryResponse:
    """Controlled response for a resolve-history request (no network)."""

    requested_tool: str = TOOL_RESOLVE_HISTORY
    permitted: bool = False
    reasons: List[str] = field(default_factory=list)
    warnings: List[str] = field(default_factory=list)
    is_mock: bool = True
    note: str = ""
    live_call_made: bool = False
    agentnet_integration_active: bool = False


@dataclass
class CapsuleValidationResponse:
    """Controlled response for a capsule-validation request (no network).

    ``valid`` reflects only the Peak-side governance decision, not any real capsule
    validation by a resolver — no resolver is contacted in Phase 12.
    """

    requested_tool: str = TOOL_VALIDATE_CAPSULE
    permitted: bool = False
    valid: bool = False
    reasons: List[str] = field(default_factory=list)
    warnings: List[str] = field(default_factory=list)
    is_mock: bool = True
    note: str = ""
    live_call_made: bool = False
    agentnet_integration_active: bool = False
