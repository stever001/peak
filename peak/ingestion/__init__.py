"""Peak engagement packet ingestion boundary (Phase 23).

Defines how Peak accepts an external ``EngagementPacket``, validates its contract/shape,
evaluates ingestion governance, and derives **production-shaped but review-gated**
no-side-effect plans — a ``SourceIngestionDraft``, Phase 14 evidence normalization requests,
Phase 13 agent task requests, and (optionally) a Phase 17 controlled write request (plan
only). It is an **ingestion boundary, not a direct importer and not a DB writer**: packet
contents are not stored, ingestion plans are not writes, and eligible material is routed
through existing controlled boundaries.

Across the package:

- **no direct database write, no database connection, no SQL execution, no stored records**;
- **no live LLM call, no AgentNet call, no MCP/resolver call, no network call**;
- **no file write, no client-facing approval, no financial verification, no capsule publication**;
- packet payloads carrying credential/secret keys are rejected.

This package imports no SQLAlchemy, no Alembic, and no ``peak.db`` module; it calls no
Phase 20/21/22 DB writer. See docs/ENGAGEMENT_PACKET_INGESTION_BOUNDARY.md and
docs/PACKET_TO_CONTROLLED_WORKFLOW_POLICY.md.
"""

from __future__ import annotations

from .contracts import (
    ALLOWED_INGESTION_ACTIONS,
    SOURCE_INGESTION_ACTION,
    SOURCE_INGESTION_TABLE,
    EngagementPacketReference,
    PacketDerivedAgentTaskPlan,
    PacketDerivedEvidencePlan,
    PacketIngestionPlan,
    PacketIngestionRequest,
    PacketIngestionResult,
    PacketValidationResult,
    SourceIngestionDraft,
)
from .governance import (
    PacketIngestionGovernanceDecision,
    build_packet_validation_result,
    evaluate_packet_ingestion_request,
    validate_packet_payload_shape,
    validate_packet_reference_scope,
)
from .packet_mapper import (
    build_packet_ingestion_plan,
    build_source_ingestion_draft,
    derive_agent_task_requests,
    derive_evidence_normalization_requests,
    prepare_packet_ingestion,
    validate_packet,
)

__all__ = [
    # contracts
    "ALLOWED_INGESTION_ACTIONS",
    "SOURCE_INGESTION_TABLE",
    "SOURCE_INGESTION_ACTION",
    "EngagementPacketReference",
    "PacketIngestionRequest",
    "PacketValidationResult",
    "SourceIngestionDraft",
    "PacketDerivedEvidencePlan",
    "PacketDerivedAgentTaskPlan",
    "PacketIngestionPlan",
    "PacketIngestionResult",
    # governance
    "PacketIngestionGovernanceDecision",
    "evaluate_packet_ingestion_request",
    "validate_packet_reference_scope",
    "validate_packet_payload_shape",
    "build_packet_validation_result",
    # mapper
    "validate_packet",
    "build_source_ingestion_draft",
    "derive_evidence_normalization_requests",
    "derive_agent_task_requests",
    "build_packet_ingestion_plan",
    "prepare_packet_ingestion",
]
