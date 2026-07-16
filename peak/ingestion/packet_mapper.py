"""Deterministic packet-to-request mapping helpers (Phase 23).

Maps a validated ``EngagementPacket`` payload into **production-shaped but review-gated**,
no-side-effect plans:

    EngagementPacket payload
      -> SourceIngestionDraft                    (review-gated; never persisted here)
      -> Phase 14 EvidenceNormalizationRequest[] (derived from present sections)
      -> Phase 13 AgentTaskRequest[]             (only for known registry agents; never run)
      -> Phase 17 ControlledWriteRequest[]       (plan only; a write plan is not a write)
      -> no DB write

Nothing here opens a database connection or imports SQLAlchemy / Alembic / ``peak.db``;
executes no SQL; makes no LLM, AgentNet, MCP, resolver, network, or file call; calls no
Phase 20/21/22 DB writer; creates no client-facing output; and publishes no capsule. Every
derived record stays ``draft`` / ``needs_review``. It imports **only** other DB-free,
no-side-effect Peak contracts (Phase 14 workers, Phase 13 agents registry, Phase 17
controlled-write contracts). See docs/ENGAGEMENT_PACKET_INGESTION_BOUNDARY.md and
docs/PACKET_TO_CONTROLLED_WORKFLOW_POLICY.md.
"""

from __future__ import annotations

from typing import List, Optional

# DB-free, no-side-effect contracts from earlier phases (none import peak.db / SQLAlchemy).
from peak.agents.contracts import AgentTaskRequest
from peak.agents.registry import get_agent
from peak.persistence.contracts import ControlledWriteRequest, ControlledWriteSubject
from peak.workers.contracts import (
    EvidenceNormalizationRequest,
    EvidenceSourceReference,
    RawEvidenceReference,
)

from .contracts import (
    AGENT_TASK_SECTION,
    EVIDENCE_LIKE_SECTIONS,
    SOURCE_INGESTION_ACTION,
    SOURCE_INGESTION_TABLE,
    PacketDerivedAgentTaskPlan,
    PacketDerivedEvidencePlan,
    PacketIngestionPlan,
    PacketIngestionRequest,
    PacketIngestionResult,
    PacketValidationResult,
    SourceIngestionDraft,
)
from .governance import build_packet_validation_result, evaluate_packet_ingestion_request

_PREVIEW_LIMIT = 240
_INGESTION_PLAN_WARNING = (
    "ingestion plans are not writes — no database connection is opened, no SQL runs, and "
    "no packet contents are stored; a future narrow source ingestion writer is required to "
    "persist a source_ingestion_records row"
)

# Section -> conservative default (source_type, content_type) for derived evidence.
_SECTION_DEFAULTS = {
    "evidence_items": ("document", "note"),
    "source_references": ("system", "reference"),
    "interview_notes": ("stakeholder", "note"),
    "walkaround_observations": ("site_walk", "note"),
    "inventory_observations": ("system", "measurement"),
}


def validate_packet(request: PacketIngestionRequest) -> PacketValidationResult:
    """Validate the packet contract/shape (delegates to ingestion governance)."""
    return build_packet_validation_result(request)


def _preview(value) -> Optional[str]:
    """Return a short, non-sensitive preview string (truncated); never the full raw text."""
    if not isinstance(value, str) or not value.strip():
        return None
    text = value.strip()
    if len(text) > _PREVIEW_LIMIT:
        return text[:_PREVIEW_LIMIT].rstrip() + "…"
    return text


def build_source_ingestion_draft(
    request: PacketIngestionRequest, validation_result: PacketValidationResult
) -> SourceIngestionDraft:
    """Map the packet reference into a review-gated ``SourceIngestionDraft`` (never stored).

    ``source_ingestion_record_id`` and ``created_at`` are left ``None`` — a *future* narrow
    controlled DB writer assigns them. The review-gate posture is stamped, not inherited.
    """
    ref = getattr(request, "packet_reference", None)
    warnings = list(getattr(validation_result, "warnings", []) or [])
    warnings.append(_INGESTION_PLAN_WARNING)
    return SourceIngestionDraft(
        source_ingestion_record_id=None,  # future controlled-DB writer assigns; nothing stored
        owner_id=getattr(request, "owner_id", None),
        client_id=getattr(request, "client_id", None),
        engagement_id=getattr(request, "engagement_id", None),
        packet_reference_id=getattr(ref, "packet_reference_id", None),
        packet_schema_name=getattr(ref, "packet_schema_name", None),
        packet_schema_version=getattr(ref, "packet_schema_version", None),
        packet_source_type=getattr(ref, "packet_source_type", None),
        packet_location_reference=getattr(ref, "packet_location_reference", None),
        packet_hash=getattr(ref, "packet_hash", None),
        output_status="draft",
        review_status="needs_review",
        lifecycle_status="active",
        authoritative=False,
        client_facing_approved=False,
        capsule_candidate_ready=False,
        reasons=[],
        warnings=warnings,
        created_at=None,  # reserved for future controlled-DB assignment
    )


def _evidence_request_from_item(
    request: PacketIngestionRequest, section: str, index: int, item: dict
) -> EvidenceNormalizationRequest:
    """Build one Phase 14 ``EvidenceNormalizationRequest`` from a packet section item."""
    default_source_type, default_content_type = _SECTION_DEFAULTS.get(section, ("document", "note"))
    source_ref = EvidenceSourceReference(
        source_reference_id=item.get("source_reference_id") or item.get("id"),
        source_type=item.get("source_type") or default_source_type,
        source_name=item.get("source_name"),
        source_location=item.get("source_location") or item.get("location"),
        captured_by=item.get("captured_by") or request.requested_by,
        captured_at=item.get("captured_at"),
        source_system=item.get("source_system"),
        authorization_scope=request.authorization_scope,  # inherited from the authorized request
    )
    raw = RawEvidenceReference(
        raw_reference_id=item.get("raw_reference_id") or item.get("id") or f"{section}_{index}",
        source_reference=source_ref,
        content_type=item.get("content_type") or default_content_type,
        observed_at=item.get("observed_at"),
        observation_context=item.get("observation_context") or item.get("context"),
        raw_text_preview=_preview(
            item.get("raw_text_preview") or item.get("text") or item.get("note")
            or item.get("summary")
        ),
        attachment_reference=item.get("attachment_reference"),
        location_context=item.get("location_context") or item.get("location"),
    )
    return EvidenceNormalizationRequest(
        owner_id=request.owner_id,
        client_id=request.client_id,
        engagement_id=request.engagement_id,
        requested_by=request.requested_by,
        workflow="evidence",
        authorization_scope=request.authorization_scope,
        review_status="needs_review",
        lifecycle_status="draft",
        raw_evidence=raw,
        normalize_for="assessment",
    )


def derive_evidence_normalization_requests(
    request: PacketIngestionRequest, validation_result: PacketValidationResult
) -> PacketDerivedEvidencePlan:
    """Derive Phase 14 evidence normalization requests from structurally present sections."""
    payload = getattr(request, "packet_payload", None)
    requests: List[object] = []
    warnings: List[str] = []
    if not isinstance(payload, dict):
        return PacketDerivedEvidencePlan(permitted=False, reasons=["packet_payload is not a dict"])

    for section in EVIDENCE_LIKE_SECTIONS:
        items = payload.get(section)
        if items is None:
            continue
        if not isinstance(items, (list, tuple)):
            warnings.append(f"section '{section}' is not a list; skipped")
            continue
        for index, item in enumerate(items):
            if not isinstance(item, dict):
                warnings.append(f"{section}[{index}] is not an object; skipped")
                continue
            has_content = any(
                item.get(k) for k in ("raw_text_preview", "text", "note", "summary",
                                      "observation_context", "context", "source_reference_id", "id")
            )
            if not has_content:
                warnings.append(f"{section}[{index}] has no usable content; included with minimal detail")
            requests.append(_evidence_request_from_item(request, section, index, item))

    return PacketDerivedEvidencePlan(
        permitted=True,
        evidence_request_count=len(requests),
        evidence_requests=requests,
        reasons=[],
        warnings=warnings,
    )


def derive_agent_task_requests(
    request: PacketIngestionRequest, validation_result: PacketValidationResult
) -> PacketDerivedAgentTaskPlan:
    """Derive Phase 13 agent task requests only for known registry agents (never executed)."""
    payload = getattr(request, "packet_payload", None)
    requests: List[object] = []
    warnings: List[str] = []
    if not isinstance(payload, dict):
        return PacketDerivedAgentTaskPlan(permitted=False, reasons=["packet_payload is not a dict"])

    tasks = payload.get(AGENT_TASK_SECTION)
    if tasks is None:
        return PacketDerivedAgentTaskPlan(permitted=True, agent_task_request_count=0)
    if not isinstance(tasks, (list, tuple)):
        return PacketDerivedAgentTaskPlan(
            permitted=True, agent_task_request_count=0,
            warnings=[f"section '{AGENT_TASK_SECTION}' is not a list; skipped"],
        )

    for index, task in enumerate(tasks):
        if not isinstance(task, dict):
            warnings.append(f"{AGENT_TASK_SECTION}[{index}] is not an object; skipped")
            continue
        agent_name = task.get("agent_name")
        entry = get_agent(agent_name)
        if entry is None:
            warnings.append(f"unknown agent '{agent_name}' skipped (not in the Phase 13 registry)")
            continue
        requests.append(
            AgentTaskRequest(
                agent_name=entry.agent_name,
                workflow=entry.workflow,
                owner_id=request.owner_id,
                client_id=request.client_id,
                engagement_id=request.engagement_id,
                requested_action=task.get("requested_action"),
                input_record_ids=list(task.get("input_record_ids") or []),
                prompt_contract_path=entry.prompt_contract_path,
                authorization_scope=request.authorization_scope,
                review_status="needs_review",
                lifecycle_status="draft",
                resolver_context_allowed=False,
                llm_execution_allowed=False,  # never executed by ingestion
                client_facing_output_requested=False,
            )
        )

    return PacketDerivedAgentTaskPlan(
        permitted=True,
        agent_task_request_count=len(requests),
        agent_task_requests=requests,
        reasons=[],
        warnings=warnings,
    )


def _build_source_ingestion_write_request(
    request: PacketIngestionRequest, draft: SourceIngestionDraft
) -> ControlledWriteRequest:
    """Build a Phase 17 ``ControlledWriteRequest`` for a *future* source_ingestion_records
    write (a plan only — nothing is executed and no DB writer is called here)."""
    subject = ControlledWriteSubject(
        subject_record_id=request.engagement_id,
        subject_record_type="engagement",
        owner_id=request.owner_id,
        client_id=request.client_id,
        engagement_id=request.engagement_id,
        stored_authorization_scope=request.authorization_scope,
    )
    return ControlledWriteRequest(
        owner_id=request.owner_id,
        client_id=request.client_id,
        engagement_id=request.engagement_id,
        requested_by=request.requested_by,
        requester_role=request.requester_role,
        authorization_scope=request.authorization_scope,
        target_table=SOURCE_INGESTION_TABLE,
        requested_action=SOURCE_INGESTION_ACTION,
        subject=subject,
        record_draft=draft,
        source_phase=getattr(request, "source_phase", None) or "phase23",
        lifecycle_status=getattr(request, "lifecycle_status", None),
        idempotency_key=getattr(request, "idempotency_key", None),
    )


def build_packet_ingestion_plan(request: PacketIngestionRequest) -> PacketIngestionPlan:
    """Build the full no-side-effect ingestion plan (assumes governance already permitted)."""
    validation_result = validate_packet(request)
    draft = build_source_ingestion_draft(request, validation_result)
    evidence_plan = derive_evidence_normalization_requests(request, validation_result)
    agent_task_plan = derive_agent_task_requests(request, validation_result)
    write_request = _build_source_ingestion_write_request(request, draft)

    warnings = [_INGESTION_PLAN_WARNING]
    return PacketIngestionPlan(
        permitted=True,
        source_ingestion_draft=draft,
        evidence_plan=evidence_plan,
        agent_task_plan=agent_task_plan,
        controlled_write_requests=[write_request],
        direct_database_write_made=False,
        database_connection_made=False,
        sql_execution_made=False,
        stored_record_created=False,
        llm_call_made=False,
        agentnet_call_made=False,
        network_call_made=False,
        capsule_publication_made=False,
        client_facing_output_created=False,
        reasons=[],
        warnings=warnings,
    )


def prepare_packet_ingestion(request: PacketIngestionRequest) -> PacketIngestionResult:
    """Prepare a no-side-effect ingestion plan for an engagement packet."""
    governance = evaluate_packet_ingestion_request(request)
    validation_result = build_packet_validation_result(request)

    if not governance.permitted:
        return PacketIngestionResult(
            permitted=False,
            status="rejected",
            validation_result=validation_result,
            ingestion_plan=None,
            direct_database_write_made=False,
            database_connection_made=False,
            sql_execution_made=False,
            stored_record_created=False,
            llm_call_made=False,
            agentnet_call_made=False,
            network_call_made=False,
            capsule_publication_made=False,
            client_facing_output_created=False,
            reasons=list(governance.reasons),
            warnings=list(governance.warnings),
        )

    plan = build_packet_ingestion_plan(request)
    return PacketIngestionResult(
        permitted=True,
        status="ingestion_plan_prepared",
        validation_result=validation_result,
        ingestion_plan=plan,
        direct_database_write_made=False,
        database_connection_made=False,
        sql_execution_made=False,
        stored_record_created=False,
        llm_call_made=False,
        agentnet_call_made=False,
        network_call_made=False,
        capsule_publication_made=False,
        client_facing_output_created=False,
        reasons=[],
        warnings=list(plan.warnings),
    )
