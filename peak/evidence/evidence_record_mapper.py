"""Evidence-to-controlled-write mapping helpers (Phase 18).

Deterministic, **DB-aware but not DB-writing**. Connects the Phase 14 evidence normalization
output to the Phase 17 controlled write boundary:

    NormalizedEvidenceRecord / EvidenceNormalizationResult
      -> EvidencePersistenceDraft            (production-shaped, review-gated)
      -> ControlledWriteSubject              (Phase 17)
      -> ControlledWriteRequest              (target evidence_references / create_draft)
      -> ControlledWritePlan                 (Phase 17 no-op plan)
      -> no DB write

Nothing here opens a database connection or imports SQLAlchemy / Alembic / ``peak.db``;
executes no SQL; makes no LLM, AgentNet, MCP, resolver, network, or file call; creates no
client-facing output; and publishes no capsule. The review-gate posture (``draft`` /
``needs_review``, non-authoritative, not client-facing, not a capsule candidate) is
preserved, and ``evidence_record_id`` / ``created_at`` stay ``None`` for future
controlled-DB assignment. See docs/EVIDENCE_PERSISTENCE_MAPPING.md and
docs/EVIDENCE_WRITE_PLAN_POLICY.md.
"""

from __future__ import annotations

# Bridges two existing boundaries: the Phase 17 controlled-write contracts and its no-op
# planner. (No SQLAlchemy / Alembic / peak.db import — those stay out of this package.)
from peak.persistence.contracts import ControlledWriteRequest, ControlledWriteSubject
from peak.persistence.write_plan import prepare_controlled_write

from .persistence_contracts import (
    ALLOWED_PERSISTENCE_ACTION,
    EvidencePersistenceDraft,
    EvidencePersistenceMappingResult,
    EvidencePersistenceRequest,
    TARGET_ACTION,
    TARGET_TABLE,
)
from .persistence_governance import evaluate_evidence_persistence_request

# Every result carries this so a caller can never mistake a plan for an executed write.
_WRITE_PLAN_WARNING = (
    "evidence write plan only — a write plan is not a write; no database connection is "
    "opened and no SQL runs. A future controlled DB writer is required to persist this "
    "evidence_references draft under access control."
)


def build_evidence_persistence_draft(
    request: EvidencePersistenceRequest,
) -> EvidencePersistenceDraft:
    """Map a ``NormalizedEvidenceRecord`` into a review-gated ``EvidencePersistenceDraft``.

    ``evidence_record_id`` and ``created_at`` are left ``None`` — a future controlled DB
    writer assigns them. The review-gate posture is stamped explicitly, never inherited from
    a claim on the input: draft / needs_review, non-authoritative, not client-facing, not a
    capsule candidate.
    """
    record = getattr(request, "normalized_record", None)
    return EvidencePersistenceDraft(
        evidence_record_id=None,  # assigned later by a controlled-DB writer; nothing stored here
        owner_id=getattr(request, "owner_id", None),
        client_id=getattr(request, "client_id", None),
        engagement_id=getattr(request, "engagement_id", None),
        source_reference_id=getattr(record, "source_reference_id", None),
        evidence_type=getattr(record, "evidence_type", None),
        normalized_title=getattr(record, "normalized_title", None),
        normalized_summary=getattr(record, "normalized_summary", None),
        observed_condition=getattr(record, "observed_condition", None),
        operational_area=getattr(record, "operational_area", None),
        inventory_process_area=getattr(record, "inventory_process_area", None),
        source_type=getattr(record, "source_type", None),
        source_location=getattr(record, "source_location", None),
        confidence_level=getattr(record, "confidence_level", "low"),
        # Review-gated posture — stamped, not inherited.
        output_status="draft",
        review_status="needs_review",
        lifecycle_status="active",
        authoritative=False,
        client_facing_approved=False,
        capsule_candidate_ready=False,
        reasons=list(getattr(record, "reasons", []) or []),
        warnings=list(getattr(record, "warnings", []) or []),
        created_at=None,  # reserved for future controlled-DB assignment
    )


def build_controlled_write_subject(request: EvidencePersistenceRequest) -> ControlledWriteSubject:
    """Build a Phase 17 ``ControlledWriteSubject`` from the parent subject snapshot."""
    snapshot = getattr(request, "subject_snapshot", None)
    return ControlledWriteSubject(
        subject_record_id=getattr(snapshot, "subject_record_id", None),
        subject_record_type=getattr(snapshot, "subject_record_type", None),
        owner_id=getattr(snapshot, "owner_id", None),
        client_id=getattr(snapshot, "client_id", None),
        engagement_id=getattr(snapshot, "engagement_id", None),
        stored_authorization_scope=getattr(snapshot, "stored_authorization_scope", None),
        stored_output_status=getattr(snapshot, "stored_output_status", None),
        stored_review_status=getattr(snapshot, "stored_review_status", None),
        stored_lifecycle_status=getattr(snapshot, "stored_lifecycle_status", None),
        source_reference_id=getattr(snapshot, "source_reference_id", None),
    )


def build_controlled_write_request(
    request: EvidencePersistenceRequest, evidence_persistence_draft: EvidencePersistenceDraft
) -> ControlledWriteRequest:
    """Build a Phase 17 ``ControlledWriteRequest`` targeting evidence_references / create_draft."""
    return ControlledWriteRequest(
        owner_id=getattr(request, "owner_id", None),
        client_id=getattr(request, "client_id", None),
        engagement_id=getattr(request, "engagement_id", None),
        requested_by=getattr(request, "requested_by", None),
        requester_role=getattr(request, "requester_role", None),
        authorization_scope=getattr(request, "authorization_scope", None),
        target_table=TARGET_TABLE,
        requested_action=TARGET_ACTION,
        subject=build_controlled_write_subject(request),
        record_draft=evidence_persistence_draft,
        source_phase=getattr(request, "source_phase", None) or "phase18",
        lifecycle_status=getattr(request, "lifecycle_status", None),
        idempotency_key=getattr(request, "idempotency_key", None),
    )


def prepare_evidence_persistence(
    request: EvidencePersistenceRequest,
) -> EvidencePersistenceMappingResult:
    """Map a normalized evidence output into a no-side-effect controlled write plan."""
    governance = evaluate_evidence_persistence_request(request)

    if not governance.permitted:
        return EvidencePersistenceMappingResult(
            permitted=False,
            status="rejected",
            evidence_persistence_draft=None,
            controlled_write_request=None,
            controlled_write_result=None,
            database_write_made=False,
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

    draft = build_evidence_persistence_draft(request)
    write_request = build_controlled_write_request(request, draft)
    # Route through the Phase 17 boundary — a no-op ControlledWriteResult (no DB, no SQL).
    write_result = prepare_controlled_write(write_request)

    # The mapping never adds a side effect; mirror the Phase 17 flags (all false) and add
    # our own always-false surface, then fold in the plan's warnings.
    warnings = [_WRITE_PLAN_WARNING]
    warnings.extend(getattr(write_result, "warnings", []) or [])
    permitted = bool(getattr(write_result, "permitted", False))

    return EvidencePersistenceMappingResult(
        permitted=permitted,
        status="write_plan_prepared" if permitted else "rejected",
        evidence_persistence_draft=draft,
        controlled_write_request=write_request,
        controlled_write_result=write_result,
        database_write_made=False,
        database_connection_made=False,
        sql_execution_made=False,
        stored_record_created=False,
        llm_call_made=False,
        agentnet_call_made=False,
        network_call_made=False,
        capsule_publication_made=False,
        client_facing_output_created=False,
        reasons=list(getattr(write_result, "reasons", []) or []),
        warnings=warnings,
    )
