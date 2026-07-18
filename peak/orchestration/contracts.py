"""Contracts for the Controlled Engagement Packet Processing Orchestrator (Phase 25).

A **controlled sequencing layer** over existing narrow boundaries — **not** a generic
importer, workflow engine, CRUD layer, or write dispatcher. These lightweight dataclasses
describe the stage options, per-stage outcomes, and the aggregate orchestration receipt.

Plan-only is the default and is **no-side-effect**. Controlled persistence happens only when
explicitly requested *and* a ``session_factory`` is supplied, and then only through the
existing narrow DB writers (Phase 24 source-ingestion; Phase 21 evidence). Receipts never
carry raw packet payload, raw evidence/interview text, credentials, SQL, connection URLs, or
stack traces — only counts, ids, stage names, safe metadata, warnings, and reason codes.

See docs/CONTROLLED_PACKET_PROCESSING_ORCHESTRATOR.md and
docs/PACKET_PROCESSING_ORCHESTRATION_POLICY.md.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import List, Optional


# --- Stage names (stable identifiers used in the receipt) ---------------------------------
STAGE_EVIDENCE_NORMALIZATION = "evidence_normalization"
STAGE_AGENT_TASK_PLANNING = "agent_task_planning"
STAGE_SOURCE_INGESTION_PERSISTENCE = "source_ingestion_persistence"
STAGE_EVIDENCE_PERSISTENCE = "evidence_persistence"
STAGE_AGENT_RUN_RECORD_PLANNING = "agent_run_record_planning"
STAGE_AGENT_RUN_RECORD_PERSISTENCE = "agent_run_record_persistence"
# Phase 28 — task queue integration stages.
STAGE_AGENT_TASK_QUEUE_READINESS = "agent_task_queue_readiness"
STAGE_AGENT_TASK_QUEUE_PERSISTENCE = "agent_task_queue_persistence"


class StageOutcome:
    """Deterministic per-stage outcome codes (str constants; no Enum dependency)."""

    COMPLETED = "completed"
    SKIPPED_NOT_REQUESTED = "skipped_not_requested"
    SKIPPED_PLAN_ONLY = "skipped_plan_only"
    SKIPPED_MISSING_SESSION_FACTORY = "skipped_missing_session_factory"
    SKIPPED_NO_SAFE_CONTRACT_PATH = "skipped_no_safe_contract_path"
    DENIED = "denied"
    FAILED_BEFORE_WRITE = "failed_before_write"
    WRITE_OUTCOME_UNCERTAIN = "write_outcome_uncertain"
    PARTIAL = "partial"  # a multi-item persistence stage: some items completed, some failed


class OrchestrationOutcome:
    """Aggregate orchestration outcome codes."""

    DENIED = "denied"
    PLANNED = "planned"  # plan-only mode completed; no persistence attempted
    PERSISTED = "persisted"  # controlled persistence ran and every requested writer completed
    PARTIAL = "partial"  # controlled persistence ran but some stage was skipped/denied/failed


@dataclass
class OrchestrationStageOptions:
    """Which stages the orchestrator should attempt. ``plan_only`` gates all persistence.

    Defaults are conservative: plan-only, only the DB-free derivation stages enabled. No
    stage can silently escalate from plan-only to persistence — a persistence stage runs only
    when ``plan_only=False``, the stage is included, and a ``session_factory`` is supplied.
    """

    plan_only: bool = True
    include_source_ingestion_persistence: bool = False
    include_evidence_normalization: bool = True
    include_evidence_persistence: bool = False
    include_agent_task_planning: bool = True
    include_agent_run_record_planning: bool = False
    include_agent_run_record_persistence: bool = False
    # Phase 28 — task queue integration. Readiness is DB-free and execution-free, so it is on
    # by default (it plans review-gated, not-executed queue drafts from the derived Phase 13
    # tasks). Persistence stays off by default and never silently escalates plan-only mode.
    include_agent_task_queue_readiness: bool = True
    include_agent_task_queue_persistence: bool = False


@dataclass
class StageResult:
    """The outcome of one orchestration stage (no raw content)."""

    stage: str
    outcome: str
    reason: Optional[str] = None
    item_count: int = 0
    receipt: Optional[object] = None  # a narrow-writer receipt, when a writer was called


@dataclass
class PacketProcessingReceipt:
    """The aggregate, auditable receipt for one packet-processing orchestration (no raw content)."""

    orchestration_outcome: str = OrchestrationOutcome.DENIED
    permitted: bool = False
    reason_code: Optional[str] = None
    plan_only: bool = True
    # Stage bookkeeping.
    stages_requested: List[str] = field(default_factory=list)
    stages_completed: List[str] = field(default_factory=list)
    stages_skipped: List[str] = field(default_factory=list)
    stages_failed: List[str] = field(default_factory=list)
    stage_results: List[StageResult] = field(default_factory=list)
    # Plan payload (always available; DB-free) — derived requests/plans, never raw payload.
    packet_ingestion_result: Optional[object] = None  # Phase 23 PacketIngestionResult
    source_ingestion_draft: Optional[object] = None  # Phase 23 SourceIngestionDraft
    source_controlled_write_request: Optional[object] = None  # Phase 17 CWR (plan only)
    evidence_normalization_requests: List[object] = field(default_factory=list)  # Phase 14 requests
    agent_task_requests: List[object] = field(default_factory=list)  # Phase 13 requests
    # Persistence receipts (only when controlled persistence ran).
    source_ingestion_persistence_receipt: Optional[object] = None
    evidence_normalization_count: int = 0
    evidence_persistence_receipts: List[object] = field(default_factory=list)
    agent_task_count: int = 0
    agent_run_persistence_receipts: List[object] = field(default_factory=list)
    # Phase 28 — task queue integration payload (all DB-free at plan time; never raw content).
    task_queue_readiness_result: Optional[object] = None  # Phase 26 AgentTaskQueueReadinessResult
    task_queue_drafts: List[object] = field(default_factory=list)  # Phase 26 AgentTaskQueueDraft
    task_queue_readiness_assessments: List[object] = field(default_factory=list)
    task_queue_controlled_write_requests: List[object] = field(default_factory=list)  # Phase 17 CWRs (plan only)
    task_queue_write_receipts: List[object] = field(default_factory=list)  # Phase 27 receipts
    task_queue_draft_count: int = 0
    task_queue_blocked_count: int = 0
    task_queue_controlled_write_request_count: int = 0
    task_queue_persisted_count: int = 0
    task_queue_replay_count: int = 0
    task_queue_conflict_count: int = 0
    task_queue_persistence_outcome: Optional[str] = None
    task_queue_persistence_stage_outcome: Optional[str] = None
    # Aggregate side-effect flags (OR of any narrow-writer calls; all False in plan-only mode).
    database_connection_made: bool = False
    sql_execution_made: bool = False
    database_write_made: bool = False
    stored_record_created: bool = False
    agent_execution_made: bool = False
    mock_agent_execution_made: bool = False
    llm_call_made: bool = False
    agentnet_call_made: bool = False
    resolver_call_made: bool = False
    network_call_made: bool = False
    client_facing_output_created: bool = False
    financial_verification_made: bool = False
    capsule_publication_made: bool = False
    reasons: List[str] = field(default_factory=list)
    warnings: List[str] = field(default_factory=list)
