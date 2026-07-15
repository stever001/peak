"""Review-record mapping helpers for the Review Persistence Boundary (Phase 16).

Deterministic, **DB-aware but not DB-writing**. Maps a permitted Phase 15 ``ReviewGateResult``
into a production-shaped ``ReviewRecordDraft`` and wraps it in a no-op ``ReviewWritePlan``
targeting the ``review_records`` table — the plan a *future* controlled-DB writer would
execute under access control.

Nothing here opens a database session or imports SQLAlchemy / ``peak.db``; makes no LLM,
AgentNet, MCP, resolver, network, or file call; creates no client-facing output; and
publishes no capsule. ``database_write_made``, ``database_connection_made``, and
``stored_review_record_created`` are always ``False``; ``review_record_id`` and
``created_at`` stay ``None`` for future controlled-DB assignment. See
docs/REVIEW_PERSISTENCE_BOUNDARY.md and docs/DB_BACKED_REVIEW_SCOPE_POLICY.md.
"""

from __future__ import annotations

from .persistence_contracts import (
    REVIEW_RECORDS_TABLE,
    ReviewPersistenceRequest,
    ReviewPersistenceResult,
    ReviewRecordDraft,
    ReviewWritePlan,
)
from .persistence_governance import evaluate_review_persistence_request

# Every plan carries this so a caller can never mistake it for an executed write.
_WRITE_PLAN_WARNING = (
    "write plan only — no database write is performed; a future controlled-DB writer is "
    "required to persist this ReviewRecord under access control"
)


def build_review_record_draft(request: ReviewPersistenceRequest) -> ReviewRecordDraft:
    """Map a permitted ``ReviewGateResult`` into an in-memory ``ReviewRecordDraft``.

    ``review_record_id`` and ``created_at`` are left ``None`` — a future controlled-DB
    writer assigns them. Client-facing approval and capsule readiness are never created
    here; they are only carried through if the subject snapshot already stored them.
    """
    gate = getattr(request, "review_gate_result", None)
    decision = getattr(gate, "decision", None) if gate is not None else None
    subject = getattr(request, "subject_snapshot", None)

    # Preserve (never create) an existing stored client-facing flag from the subject.
    preserved_client_facing = bool(
        getattr(subject, "stored_client_facing_approved", False)
    ) if subject is not None else False

    return ReviewRecordDraft(
        review_record_id=None,  # assigned later by a controlled-DB writer; nothing stored here
        subject_record_id=getattr(subject, "subject_record_id", None),
        subject_record_type=getattr(subject, "subject_record_type", None),
        owner_id=getattr(request, "owner_id", None),
        client_id=getattr(request, "client_id", None),
        engagement_id=getattr(request, "engagement_id", None),
        reviewer_role=getattr(request, "reviewer_role", None),
        requested_by=getattr(request, "requested_by", None),
        decision=getattr(decision, "decision", None),
        next_output_status=getattr(decision, "next_output_status", None),
        next_review_status=getattr(decision, "next_review_status", None),
        next_lifecycle_status=getattr(decision, "next_lifecycle_status", None),
        authoritative=bool(getattr(decision, "authoritative", False)),
        client_facing_approved=preserved_client_facing,  # never created in Phase 16
        capsule_candidate_ready=False,  # never created in Phase 16
        reasons=list(getattr(decision, "reasons", []) or []),
        warnings=list(getattr(decision, "warnings", []) or []),
        source_reference_id=getattr(subject, "source_reference_id", None),
        created_at=None,  # reserved for future controlled-DB assignment
    )


def build_review_write_plan(request: ReviewPersistenceRequest) -> ReviewWritePlan:
    """Wrap a ``ReviewRecordDraft`` in a no-op write plan (never executed)."""
    draft = build_review_record_draft(request)
    return ReviewWritePlan(
        permitted=True,
        action=getattr(request, "requested_persistence_action", None),
        review_record_draft=draft,
        target_table=REVIEW_RECORDS_TABLE,
        database_write_made=False,
        database_connection_made=False,
        requires_controlled_db_writer=True,
        reasons=[],
        warnings=[_WRITE_PLAN_WARNING],
    )


def prepare_review_persistence(request: ReviewPersistenceRequest) -> ReviewPersistenceResult:
    """Prepare a no-side-effect review persistence plan for a permitted review outcome."""
    governance = evaluate_review_persistence_request(request)

    if not governance.permitted:
        return ReviewPersistenceResult(
            permitted=False,
            status="rejected",
            write_plan=None,
            database_write_made=False,
            database_connection_made=False,
            llm_call_made=False,
            agentnet_call_made=False,
            network_call_made=False,
            capsule_publication_made=False,
            client_facing_output_created=False,
            stored_review_record_created=False,
            reasons=list(governance.reasons),
            warnings=list(governance.warnings),
        )

    write_plan = build_review_write_plan(request)

    return ReviewPersistenceResult(
        permitted=True,
        status="write_plan_prepared",
        write_plan=write_plan,
        database_write_made=False,
        database_connection_made=False,
        llm_call_made=False,
        agentnet_call_made=False,
        network_call_made=False,
        capsule_publication_made=False,
        client_facing_output_created=False,
        stored_review_record_created=False,
        reasons=[],
        warnings=list(governance.warnings) + list(write_plan.warnings),
    )
