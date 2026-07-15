"""No-op controlled write planning for the Controlled DB Writer Boundary (Phase 17).

Deterministic, **DB-aware but not DB-writing**. Given a governance-approved
``ControlledWriteRequest``, builds a no-op ``ControlledWritePlan`` (the plan a *future*
controlled DB writer would execute) and an in-memory ``ControlledWriteAuditDraft``.

Nothing here opens a database connection or imports SQLAlchemy / Alembic / ``peak.db``;
executes no SQL; makes no LLM, AgentNet, MCP, resolver, network, or file call; creates no
client-facing output; and publishes no capsule. ``database_write_made``,
``database_connection_made``, ``sql_execution_made``, and ``stored_record_created`` are
always ``False``; ``requires_controlled_db_writer`` is always ``True``;
``audit_record_id`` and ``created_at`` stay ``None`` for future controlled-DB assignment.
See docs/CONTROLLED_DB_WRITER_BOUNDARY.md and docs/CONTROLLED_WRITE_ALLOWLIST.md.
"""

from __future__ import annotations

from .contracts import (
    ControlledWriteAuditDraft,
    ControlledWriteDecision,
    ControlledWritePlan,
    ControlledWriteRequest,
    ControlledWriteResult,
)
from .governance import evaluate_controlled_write_request

# Every plan carries this so a caller can never mistake it for an executed write.
_WRITE_PLAN_WARNING = (
    "controlled write plan only — a write plan is not a write; no database connection is "
    "opened and no SQL runs. A future controlled DB writer is required to persist this "
    "record under access control."
)


def build_controlled_write_plan(request: ControlledWriteRequest) -> ControlledWritePlan:
    """Wrap a request's record draft in a no-op write plan (never executed)."""
    return ControlledWritePlan(
        permitted=True,
        target_table=getattr(request, "target_table", None),
        requested_action=getattr(request, "requested_action", None),
        record_draft=getattr(request, "record_draft", None),
        requires_controlled_db_writer=True,
        database_write_made=False,
        database_connection_made=False,
        sql_execution_made=False,
        stored_record_created=False,
        reasons=[],
        warnings=[_WRITE_PLAN_WARNING],
    )


def build_controlled_write_audit_draft(
    request: ControlledWriteRequest, decision: ControlledWriteDecision
) -> ControlledWriteAuditDraft:
    """Build an in-memory audit draft of the write attempt (never persisted here).

    ``audit_record_id`` and ``created_at`` are left ``None`` — a future controlled DB writer
    assigns them.
    """
    permitted = getattr(decision, "permitted", False)
    return ControlledWriteAuditDraft(
        audit_record_id=None,  # assigned later by a controlled-DB writer; nothing stored here
        owner_id=getattr(request, "owner_id", None),
        client_id=getattr(request, "client_id", None),
        engagement_id=getattr(request, "engagement_id", None),
        target_table=getattr(request, "target_table", None),
        requested_action=getattr(request, "requested_action", None),
        requested_by=getattr(request, "requested_by", None),
        requester_role=getattr(request, "requester_role", None),
        source_phase=getattr(request, "source_phase", None),
        idempotency_key=getattr(request, "idempotency_key", None),
        decision="permitted" if permitted else "rejected",
        reasons=list(getattr(decision, "reasons", []) or []),
        warnings=list(getattr(decision, "warnings", []) or []),
        created_at=None,  # reserved for future controlled-DB assignment
    )


def prepare_controlled_write(request: ControlledWriteRequest) -> ControlledWriteResult:
    """Prepare a no-side-effect controlled write plan for an allowlisted, scoped request."""
    governance = evaluate_controlled_write_request(request)

    if not governance.permitted:
        return ControlledWriteResult(
            permitted=False,
            status="rejected",
            write_plan=None,
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

    write_plan = build_controlled_write_plan(request)

    return ControlledWriteResult(
        permitted=True,
        status="write_plan_prepared",
        write_plan=write_plan,
        database_write_made=False,
        database_connection_made=False,
        sql_execution_made=False,
        stored_record_created=False,
        llm_call_made=False,
        agentnet_call_made=False,
        network_call_made=False,
        capsule_publication_made=False,
        client_facing_output_created=False,
        reasons=[],
        warnings=list(governance.warnings) + list(write_plan.warnings),
    )
