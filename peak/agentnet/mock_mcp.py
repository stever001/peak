"""No-network mock boundary standing in for the AgentNet MCP connector.

This is a **mock governance boundary, not an AgentNet integration.** It exists so Peak
can develop and test its governance wrapper without the real connector, a resolver, an
MCP server, or any network. It:

- runs Peak-side governance checks first (peak/agentnet/governance.py),
- returns a controlled, in-memory response,
- never opens a socket or performs any network/HTTP/MCP call,
- never reads connector credentials or configuration,
- never imports or calls the real AgentNet MCP connector (a separate repo), and
- always reports ``live_call_made = False`` and ``agentnet_integration_active = False``.

Phase 12 makes **no live calls** and no AgentNet integration is complete. Capsule
publication is deferred to a later phase and is not implemented here.
"""

from __future__ import annotations

from . import governance
from .contracts import (
    CapsuleValidationResponse,
    ResolveHistoryResponse,
    ResolverContextResponse,
)

MOCK_BOUNDARY_NOTE = (
    "mock boundary only — no live AgentNet/MCP/resolver/network call was made; "
    "this is not an AgentNet integration"
)


class MockAgentNetMCPBoundary:
    """In-memory stand-in for the three known connector operations.

    Each method mirrors a connector tool *conceptually* — it does not forward to it. The
    real transport/integration lives in the separate AgentNet MCP connector repo and is
    never invoked here.
    """

    def resolve(self, request) -> ResolverContextResponse:
        """Mock of ``agentnet.resolve`` — governance-checked, no network."""
        decision = governance.evaluate_resolve_request(request)
        return ResolverContextResponse(
            requested_tool=decision.requested_tool,
            permitted=decision.permitted,
            reasons=list(decision.reasons),
            warnings=list(decision.warnings),
            is_mock=True,
            note=MOCK_BOUNDARY_NOTE,
            live_call_made=False,
            agentnet_integration_active=False,
        )

    def resolve_history(self, request) -> ResolveHistoryResponse:
        """Mock of ``agentnet.resolve_history`` — governance-checked, no network."""
        decision = governance.evaluate_history_request(request)
        return ResolveHistoryResponse(
            requested_tool=decision.requested_tool,
            permitted=decision.permitted,
            reasons=list(decision.reasons),
            warnings=list(decision.warnings),
            is_mock=True,
            note=MOCK_BOUNDARY_NOTE,
            live_call_made=False,
            agentnet_integration_active=False,
        )

    def validate_capsule(self, request) -> CapsuleValidationResponse:
        """Mock of ``agentnet.validate_capsule`` — governance-checked, no network.

        ``valid`` only reflects the Peak-side governance decision; no resolver validates
        the capsule, and nothing is published.
        """
        decision = governance.evaluate_capsule_validation_request(request)
        return CapsuleValidationResponse(
            requested_tool=decision.requested_tool,
            permitted=decision.permitted,
            valid=decision.permitted,
            reasons=list(decision.reasons),
            warnings=list(decision.warnings),
            is_mock=True,
            note=MOCK_BOUNDARY_NOTE,
            live_call_made=False,
            agentnet_integration_active=False,
        )
