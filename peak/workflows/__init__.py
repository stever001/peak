"""Peak governed workflow integration layers (Phase 35 + Phase 40).

Two integration layers live here, neither of which is a persistence primitive:

* **Phase 35 — managed record workflow (write path, gated).** Sequences six already durable record
  types through their existing narrow controlled writers under explicit per-stage persistence
  gates. Documented immediately below.
* **Phase 40 — end-to-end internal report review workflow (read-only).** Consolidates the stored
  Phase 37 report draft, Phase 38 review packet, and Phase 39 packet decision rows into one
  deterministic computed workflow state. It writes nothing at all: no row is inserted, updated, or
  deleted, and the Phase 38 packet row is **derived from**, never mutated. See
  :func:`summarize_internal_report_review_workflow` and
  docs/INTERNAL_REPORT_REVIEW_WORKFLOW_INTEGRATION.md.

Neither layer adds a DB table, model, Alembic migration, or Phase 17 allowlist pair, and neither
imports SQLAlchemy at module scope — so ``import peak.workflows`` still needs no database driver.

--- Phase 35 ---------------------------------------------------------------------------------

A **workflow integration layer** over the eight existing narrow controlled DB writers — not a new
persistence primitive, a generic CRUD layer, an ORM, a raw-SQL executor, a broad repository, an
API, or a workflow engine. It sequences six already durable record types through their existing
narrow writer APIs under explicit per-stage persistence gates:

``intake_note_records`` → ``source_ingestion_records`` → ``evidence_references`` →
``agent_task_queue_records`` → ``review_bundle_records`` → ``internal_reviewer_decision_records``.

Phase 35 adds **no DB table, model, or migration** (Alembic head stays ``009_intake_note_records``;
``make db-check`` stays at 15 tables) and **no new Phase 17 allowlist pair**. It calls no Phase 22
review writer and no agent-run writer, so ``review_records`` and ``agent_run_records`` are never
written here. It creates no client-facing output, verifies no financial impact, publishes no
capsule, executes no agent or LLM, and makes no AgentNet / MCP / resolver / network call.

**Plan-only is the default and is no-side-effect.** A stage persists only when its gate is
explicitly ``True``, its payload is present and safe, and a ``session_factory`` is injected — this
layer never falls back to an ambient environment database URL, so standard validation needs no live
managed-MySQL credentials and no network. The DB writers are imported **lazily** inside the
persistence step, so this package imports and runs plan-only without SQLAlchemy installed.

See docs/MANAGED_RECORD_WORKFLOW_INTEGRATION.md and
docs/WORKFLOW_INTEGRATION_GOVERNANCE_POLICY.md.
"""

from __future__ import annotations

from .contracts import (
    IDEMPOTENCY_NAMESPACE,
    IDEMPOTENCY_SEPARATOR,
    MAX_IDEMPOTENCY_KEY_LEN,
    STAGE_AGENT_TASK_QUEUE,
    STAGE_EVIDENCE_REFERENCE,
    STAGE_INTAKE_NOTE,
    STAGE_PAYLOAD_ATTRS,
    STAGE_REVIEW_BUNDLE,
    STAGE_REVIEWER_DECISION,
    STAGE_SOURCE_INGESTION,
    STAGE_TARGETS,
    WORKFLOW_STAGES,
    WORKFLOW_TABLES,
    ManagedRecordWorkflowRequest,
    ManagedRecordWorkflowResult,
    WorkflowOutcome,
    WorkflowStageOutcome,
    WorkflowStageReceipt,
    WorkflowStageResult,
)
from .governance import (
    PROHIBITED_KEY_MARKERS,
    PROSE_EXEMPT_FIELDS,
    STAGE_KEY_FIELDS,
    STAGE_REF_FIELDS,
    WorkflowGovernanceDecision,
    derive_stage_idempotency_key,
    evaluate_stage_payload,
    evaluate_workflow_request,
    stage_payload_fingerprint,
)
from .internal_report_review_workflow import (
    EXPECTED_DECISION_STATUS_BY_INTENT,
    INTENT_WORKFLOW_STATES,
    PACKET_DECISION_STATES,
    SOURCE_TABLES,
    WORKFLOW_STATES,
    ComputedPacketDecisionState,
    InternalReportReviewWorkflowOutcome,
    InternalReportReviewWorkflowRequest,
    InternalReportReviewWorkflowResult,
    InternalReportReviewWorkflowState,
    InternalReportReviewWorkflowTrace,
    derive_workflow_state,
    evaluate_internal_report_review_workflow_request,
    summarize_internal_report_review_workflow,
)
from .managed_record_workflow import run_managed_record_workflow

__all__ = [
    # contracts
    "ManagedRecordWorkflowRequest",
    "ManagedRecordWorkflowResult",
    "WorkflowStageResult",
    "WorkflowStageReceipt",
    "WorkflowOutcome",
    "WorkflowStageOutcome",
    "WORKFLOW_STAGES",
    "WORKFLOW_TABLES",
    "STAGE_TARGETS",
    "STAGE_PAYLOAD_ATTRS",
    "STAGE_INTAKE_NOTE",
    "STAGE_SOURCE_INGESTION",
    "STAGE_EVIDENCE_REFERENCE",
    "STAGE_AGENT_TASK_QUEUE",
    "STAGE_REVIEW_BUNDLE",
    "STAGE_REVIEWER_DECISION",
    "IDEMPOTENCY_NAMESPACE",
    "IDEMPOTENCY_SEPARATOR",
    "MAX_IDEMPOTENCY_KEY_LEN",
    # governance
    "WorkflowGovernanceDecision",
    "evaluate_workflow_request",
    "evaluate_stage_payload",
    "derive_stage_idempotency_key",
    "stage_payload_fingerprint",
    "PROHIBITED_KEY_MARKERS",
    "PROSE_EXEMPT_FIELDS",
    "STAGE_REF_FIELDS",
    "STAGE_KEY_FIELDS",
    # entry point
    "run_managed_record_workflow",
    # --- Phase 40: read-only internal report review workflow integration ---
    "InternalReportReviewWorkflowRequest",
    "InternalReportReviewWorkflowResult",
    "InternalReportReviewWorkflowTrace",
    "InternalReportReviewWorkflowOutcome",
    "InternalReportReviewWorkflowState",
    "ComputedPacketDecisionState",
    "WORKFLOW_STATES",
    "PACKET_DECISION_STATES",
    "INTENT_WORKFLOW_STATES",
    "EXPECTED_DECISION_STATUS_BY_INTENT",
    "SOURCE_TABLES",
    "evaluate_internal_report_review_workflow_request",
    "derive_workflow_state",
    "summarize_internal_report_review_workflow",
]
