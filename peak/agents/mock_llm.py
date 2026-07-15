"""Mock / no-op LLM interface for the Phase 13 agent harness.

Makes **no LLM call** of any kind: it opens no socket, reads no API key, and contacts no
model provider or AgentNet. It returns a controlled message stating that live LLM
execution is disabled in Phase 13, with ``llm_call_made = False``.
"""

from __future__ import annotations

from dataclasses import dataclass

LLM_DISABLED_MESSAGE = (
    "live LLM execution is disabled in Phase 13; this is a mock interface and no model "
    "provider, AgentNet, or network was contacted"
)


@dataclass
class MockLLMResponse:
    """A controlled, inert response — never produced by a real model call."""

    message: str = LLM_DISABLED_MESSAGE
    llm_call_made: bool = False


class MockLLM:
    """No-op stand-in for a future LLM client. Every method is inert."""

    def complete(self, request=None) -> MockLLMResponse:
        """Return the disabled-execution message without calling anything."""
        return MockLLMResponse(message=LLM_DISABLED_MESSAGE, llm_call_made=False)
