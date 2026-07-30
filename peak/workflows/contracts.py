"""Contracts for the Managed Record Workflow integration layer (Phase 35).

A **governed workflow integration layer** over the eight existing narrow controlled DB writers —
**not** a new persistence primitive, a generic CRUD layer, an ORM, a write dispatcher, or a
workflow engine. Phase 35 adds **no table, no model, and no migration**: it sequences six already
durable record types through their existing narrow writer APIs, under explicit per-stage
persistence gates.

These are pure stdlib dataclasses/constants — **no SQLAlchemy, no Alembic, no ``peak.db`` import at
module scope**. The narrow writers (which do use SQLAlchemy) are imported lazily inside the
persistence stages, so this package imports and runs plan-only without a database driver installed.

Nothing here echoes raw content. Payloads carry operational fields; **results carry only stage
names, safe record refs, counts, reason codes, and marker categories** — never intake note text,
raw packet/evidence/interview text, source bytes, generated agent output, credentials, DSNs, raw
SQL, stack traces, client-facing language, or approval decisions.

See docs/MANAGED_RECORD_WORKFLOW_INTEGRATION.md and
docs/WORKFLOW_INTEGRATION_GOVERNANCE_POLICY.md.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Dict, List, Optional

# --- Stage names (stable identifiers used in gates, keys, and results) ---------------------
STAGE_INTAKE_NOTE = "intake_note"
STAGE_SOURCE_INGESTION = "source_ingestion"
STAGE_EVIDENCE_REFERENCE = "evidence_reference"
STAGE_AGENT_TASK_QUEUE = "agent_task_queue"
STAGE_REVIEW_BUNDLE = "review_bundle"
STAGE_REVIEWER_DECISION = "reviewer_decision"

#: The controlled workflow order. Each stage depends on the ones before it, so a halting stage
#: stops every later stage (see ``ManagedRecordWorkflowResult.halted_after_stage``).
WORKFLOW_STAGES = (
    STAGE_INTAKE_NOTE,
    STAGE_SOURCE_INGESTION,
    STAGE_EVIDENCE_REFERENCE,
    STAGE_AGENT_TASK_QUEUE,
    STAGE_REVIEW_BUNDLE,
    STAGE_REVIEWER_DECISION,
)

#: stage -> the request attribute carrying that stage's already-shaped draft payload.
STAGE_PAYLOAD_ATTRS = {
    STAGE_INTAKE_NOTE: "intake_note_payload",
    STAGE_SOURCE_INGESTION: "source_ingestion_payload",
    STAGE_EVIDENCE_REFERENCE: "evidence_payload",
    STAGE_AGENT_TASK_QUEUE: "agent_task_payload",
    STAGE_REVIEW_BUNDLE: "review_bundle_payload",
    STAGE_REVIEWER_DECISION: "reviewer_decision_payload",
}

#: stage -> (target_table, requested_action). These mirror the Phase 17 allowlist pairs that
#: already exist; Phase 35 adds **no new allowlist pair** and targets no other table/action.
STAGE_TARGETS = {
    STAGE_INTAKE_NOTE: ("intake_note_records", "create_intake_note_record"),
    STAGE_SOURCE_INGESTION: ("source_ingestion_records", "create_source_ingestion_record"),
    STAGE_EVIDENCE_REFERENCE: ("evidence_references", "create_draft"),
    STAGE_AGENT_TASK_QUEUE: ("agent_task_queue_records", "create_agent_task_queue_record"),
    STAGE_REVIEW_BUNDLE: ("review_bundle_records", "create_review_bundle_record"),
    STAGE_REVIEWER_DECISION: ("internal_reviewer_decision_records",
                              "create_internal_reviewer_decision_record"),
}

#: The controlled tables this workflow may ever touch. ``review_records`` and ``agent_run_records``
#: are deliberately absent: Phase 35 calls no Phase 22 review writer and no agent-run writer.
WORKFLOW_TABLES = tuple(table for table, _ in STAGE_TARGETS.values())

#: Idempotency-key namespace. Every stage key produced by this layer is prefixed
#: ``wf35::<stage>::`` so one string can never collide across two tables/actions.
IDEMPOTENCY_NAMESPACE = "wf35"
IDEMPOTENCY_SEPARATOR = "::"
MAX_IDEMPOTENCY_KEY_LEN = 128  # the writers' own hard bound


class WorkflowStageOutcome:
    """Deterministic per-stage outcome codes (str constants; no Enum dependency)."""

    SKIPPED = "skipped"            # no payload and the gate is off — nothing to do
    PLANNED = "planned"            # payload present, gate off — plan-only, no writer called
    PERSISTED = "persisted"        # the narrow writer created one row
    REPLAYED = "replayed"          # the narrow writer returned an idempotent replay
    DENIED = "denied"              # denied here (pre-flight) or by the narrow writer
    CONFLICTED = "conflicted"      # the narrow writer reported an idempotency conflict
    FAILED_BEFORE_WRITE = "failed_before_write"
    WRITE_OUTCOME_UNCERTAIN = "write_outcome_uncertain"
    HALTED = "halted"              # not attempted: an earlier stage halted the workflow


#: Stage outcomes that stop every later (dependent) stage.
HALTING_STAGE_OUTCOMES = frozenset({
    WorkflowStageOutcome.DENIED,
    WorkflowStageOutcome.CONFLICTED,
    WorkflowStageOutcome.FAILED_BEFORE_WRITE,
    WorkflowStageOutcome.WRITE_OUTCOME_UNCERTAIN,
})


class WorkflowOutcome:
    """Aggregate workflow outcome codes."""

    DENIED = "denied"        # pre-flight denial; no stage ran and no writer was called
    PLANNED = "planned"      # nothing was persisted (plan-only default or every gate off)
    PERSISTED = "persisted"  # every gated stage persisted or replayed
    PARTIAL = "partial"      # some gated stage persisted and some did not
    HALTED = "halted"        # a stage halted the workflow before the later stages ran


@dataclass
class ManagedRecordWorkflowRequest:
    """One governed managed-record workflow run (DB-free; nothing here is persisted by itself).

    Stage payloads are **already-shaped drafts** produced upstream by the existing DB-free
    boundaries (Phase 23/14/26/29/32 and the Phase 25/28/31 packet processor) — see
    docs/MANAGED_RECORD_WORKFLOW_INTEGRATION.md for the handoff. This layer never accepts raw
    client files, binary blobs, DB URLs, credentials, raw SQL, LLM prompts, resolver credentials,
    final client-facing language, or arbitrary workflow JSON blobs.

    ``persistence_gates`` maps a stage name to ``True``/``False``. The default is **plan-only**:
    an absent or false gate means the stage is planned and no writer is called. No stage can
    silently escalate from plan-only to persistence.
    """

    owner_id: Optional[str] = None
    client_id: Optional[str] = None
    engagement_id: Optional[str] = None
    authorization_scope: Optional[str] = None
    requested_by: Optional[str] = None
    requester_role: Optional[str] = None
    # Workflow identity. ``workflow_id`` backs deterministic stage-key derivation; when it is
    # absent, every gated stage must supply its own key in ``stage_idempotency_keys``.
    workflow_id: Optional[str] = None
    # Already-shaped stage drafts (see STAGE_PAYLOAD_ATTRS).
    intake_note_payload: Optional[object] = None        # Phase 34 IntakeNoteDraft
    source_ingestion_payload: Optional[object] = None   # Phase 23 SourceIngestionDraft
    evidence_payload: Optional[object] = None           # Phase 18 EvidencePersistenceDraft
    agent_task_payload: Optional[object] = None         # Phase 26 AgentTaskQueueDraft
    review_bundle_payload: Optional[object] = None      # Phase 29 ReviewBundleDraft
    reviewer_decision_payload: Optional[object] = None  # Phase 32 InternalReviewerDecisionDraft
    # Explicit per-stage persistence gates: stage -> bool. Missing == False == plan-only.
    persistence_gates: Dict[str, bool] = field(default_factory=dict)
    # Optional explicit per-stage idempotency keys: stage -> key (still stage-namespaced).
    stage_idempotency_keys: Dict[str, str] = field(default_factory=dict)
    # Strict mode: any stage warning halts the workflow after that stage.
    strict_mode: bool = False
    # Passed through to the narrow writers' ControlledWriteRequest (never authorization).
    source_phase: str = "phase35"
    lifecycle_status: str = "active"
    # The stored authorization subject (an Engagement id). Defaults to ``engagement_id``.
    subject_record_id: Optional[str] = None


@dataclass
class WorkflowStageReceipt:
    """A sanitized, per-stage copy of the narrow writer's receipt (safe fields only).

    Carries no credentials, no SQL, no connection URL, no raw stored content, and no note body.
    ``reasons``/``warnings`` are re-scanned by this layer and replaced with a marker *category*
    if they would ever carry an unsafe value.
    """

    stage: str = ""
    target_table: Optional[str] = None
    target_action: Optional[str] = None
    writer_outcome: Optional[str] = None
    permitted: bool = False
    reason_code: Optional[str] = None
    stored_record_id: Optional[str] = None   # a safe server-assigned ref, never content
    idempotency_key: Optional[str] = None    # the stage-namespaced key (not a secret)
    review_status: Optional[str] = None
    lifecycle_status: Optional[str] = None
    created_at: Optional[str] = None
    database_connection_made: bool = False
    sql_execution_made: bool = False
    database_write_made: bool = False
    stored_record_created: bool = False
    existing_record_returned: bool = False
    transaction_committed: bool = False
    outcome_uncertain: bool = False
    reasons: List[str] = field(default_factory=list)
    warnings: List[str] = field(default_factory=list)


@dataclass
class WorkflowStageResult:
    """The outcome of one workflow stage (no raw content, no payload echo)."""

    stage: str = ""
    outcome: str = WorkflowStageOutcome.SKIPPED
    gate_enabled: bool = False
    payload_present: bool = False
    writer_called: bool = False
    reason_code: Optional[str] = None
    target_table: Optional[str] = None
    target_action: Optional[str] = None
    idempotency_key: Optional[str] = None
    idempotency_key_source: Optional[str] = None  # "explicit" | "derived" | None
    created_record_ref: Optional[str] = None
    receipt: Optional[WorkflowStageReceipt] = None
    reasons: List[str] = field(default_factory=list)
    warnings: List[str] = field(default_factory=list)


@dataclass
class ManagedRecordWorkflowResult:
    """The aggregate, auditable receipt for one managed-record workflow run.

    Reports which stages were planned, skipped, persisted, replayed, denied, conflicted, or
    halted, plus per-table write counts and safe created-record refs. It **never** echoes intake
    note text, raw packet/evidence/interview text, source bytes, generated agent output,
    credentials, DSNs, raw SQL, stack traces, final client-facing language, or approval decisions.
    """

    outcome: str = WorkflowOutcome.DENIED
    permitted: bool = False
    reason_code: Optional[str] = None
    # Identity echo (safe identifiers the caller supplied; never credentials).
    workflow_id: Optional[str] = None
    owner_id: Optional[str] = None
    client_id: Optional[str] = None
    engagement_id: Optional[str] = None
    authorization_scope: Optional[str] = None
    strict_mode: bool = False
    # Stage bookkeeping (stage-name lists; ordered as WORKFLOW_STAGES).
    stages_requested: List[str] = field(default_factory=list)
    stages_planned: List[str] = field(default_factory=list)
    stages_skipped: List[str] = field(default_factory=list)
    stages_persisted: List[str] = field(default_factory=list)
    stages_replayed: List[str] = field(default_factory=list)
    stages_denied: List[str] = field(default_factory=list)
    stages_conflicted: List[str] = field(default_factory=list)
    stages_halted: List[str] = field(default_factory=list)
    halted_after_stage: Optional[str] = None
    # Per-stage detail.
    stage_results: Dict[str, WorkflowStageResult] = field(default_factory=dict)
    receipts: Dict[str, WorkflowStageReceipt] = field(default_factory=dict)
    created_record_refs: Dict[str, str] = field(default_factory=dict)  # stage -> stored id
    table_write_counts: Dict[str, int] = field(default_factory=dict)   # table -> rows created
    stage_idempotency_keys: Dict[str, str] = field(default_factory=dict)
    # Aggregate side-effect flags (OR of the narrow-writer receipts; all False in plan-only mode).
    database_connection_made: bool = False
    sql_execution_made: bool = False
    database_write_made: bool = False
    stored_record_created: bool = False
    # Non-effect flags — always False (Phase 35 approves/publishes/executes nothing).
    review_records_write_made: bool = False
    agent_run_records_write_made: bool = False
    review_approval_made: bool = False
    client_facing_output_created: bool = False
    financial_verification_made: bool = False
    capsule_publication_made: bool = False
    agent_execution_made: bool = False
    mock_agent_execution_made: bool = False
    llm_call_made: bool = False
    agentnet_call_made: bool = False
    resolver_call_made: bool = False
    network_call_made: bool = False
    reasons: List[str] = field(default_factory=list)
    warnings: List[str] = field(default_factory=list)
