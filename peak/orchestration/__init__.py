"""Peak controlled engagement packet processing orchestrator (Phase 25).

A **controlled sequencing layer** over the existing narrow boundaries — not a generic
importer, workflow engine, CRUD layer, or write dispatcher. It accepts a Phase 23
``PacketIngestionRequest``, routes it through the Phase 23 ingestion boundary, exposes the
derived plan, and — only when explicitly requested and a ``session_factory`` is supplied —
persists through the existing narrow DB writers (Phase 24 source-ingestion, Phase 21
evidence). Agent-run persistence is intentionally left plan-only.

Plan-only is the default and is **no-side-effect**. No stage silently escalates from plan-only
to persistence. The orchestrator never executes an agent or LLM, calls AgentNet/MCP/resolver/
network, creates client-facing output, verifies financial impact, or publishes a capsule, and
never stores or echoes raw packet payload content. DB writers are imported **lazily** inside
the persistence stages, so this package imports and runs (plan-only) without SQLAlchemy.

See docs/CONTROLLED_PACKET_PROCESSING_ORCHESTRATOR.md and
docs/PACKET_PROCESSING_ORCHESTRATION_POLICY.md.
"""

from __future__ import annotations

from .contracts import (
    STAGE_AGENT_RUN_RECORD_PERSISTENCE,
    STAGE_AGENT_RUN_RECORD_PLANNING,
    STAGE_AGENT_TASK_PLANNING,
    STAGE_AGENT_TASK_QUEUE_PERSISTENCE,
    STAGE_AGENT_TASK_QUEUE_READINESS,
    STAGE_EVIDENCE_NORMALIZATION,
    STAGE_EVIDENCE_PERSISTENCE,
    STAGE_SOURCE_INGESTION_PERSISTENCE,
    OrchestrationOutcome,
    OrchestrationStageOptions,
    PacketProcessingReceipt,
    StageOutcome,
    StageResult,
)
from .governance import (
    OrchestrationGovernanceDecision,
    derived_identity_mismatches,
    evaluate_orchestration_request,
)
from .packet_processor import process_engagement_packet

__all__ = [
    # contracts
    "OrchestrationStageOptions",
    "OrchestrationOutcome",
    "StageOutcome",
    "StageResult",
    "PacketProcessingReceipt",
    "STAGE_EVIDENCE_NORMALIZATION",
    "STAGE_AGENT_TASK_PLANNING",
    "STAGE_SOURCE_INGESTION_PERSISTENCE",
    "STAGE_EVIDENCE_PERSISTENCE",
    "STAGE_AGENT_RUN_RECORD_PLANNING",
    "STAGE_AGENT_RUN_RECORD_PERSISTENCE",
    "STAGE_AGENT_TASK_QUEUE_READINESS",
    "STAGE_AGENT_TASK_QUEUE_PERSISTENCE",
    # governance
    "OrchestrationGovernanceDecision",
    "evaluate_orchestration_request",
    "derived_identity_mismatches",
    # processor
    "process_engagement_packet",
]
