"""Public contracts for the controlled DB writers (receipts + outcomes).

Pure stdlib dataclasses/constants — **no SQLAlchemy, no peak.db model/session import** — so
receipt shapes can be consumed and asserted on without a live database. The writers that
produce these live in ``peak.db.agent_run_writer`` (Phase 20), ``peak.db.evidence_writer``
(Phase 21), ``peak.db.review_writer`` (Phase 22), and ``peak.db.source_ingestion_writer``
(Phase 24) and *do* use SQLAlchemy.

A receipt is a **production-shaped persistence receipt**: enough to audit the operation
without exposing credentials, SQL strings, connection URLs, or raw stored content. Every
flag reports **actual** behavior (a denial before any DB connection reports no connection /
no SQL; an idempotent replay reports reads but no new record; a created result reports the
committed write; an uncertain outcome must not falsely claim no record exists). See
docs/AGENT_RUN_CONTROLLED_WRITER.md, docs/EVIDENCE_CONTROLLED_WRITER.md,
docs/REVIEW_CONTROLLED_WRITER.md, and docs/SOURCE_INGESTION_CONTROLLED_WRITER.md.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import List, Optional


class AgentRunWriteOutcome:
    """Outcome codes for a controlled agent-run write (str constants; no Enum dependency)."""

    CREATED = "created"
    IDEMPOTENT_REPLAY = "idempotent_replay"
    DENIED = "denied"
    FAILED_BEFORE_WRITE = "failed_before_write"
    WRITE_OUTCOME_UNCERTAIN = "write_outcome_uncertain"


# The single table/action this writer family may target (Phase 17 allowlist subset).
TARGET_TABLE = "agent_run_records"
TARGET_ACTION = "create_agent_run_record"

ALL_OUTCOMES = (
    AgentRunWriteOutcome.CREATED,
    AgentRunWriteOutcome.IDEMPOTENT_REPLAY,
    AgentRunWriteOutcome.DENIED,
    AgentRunWriteOutcome.FAILED_BEFORE_WRITE,
    AgentRunWriteOutcome.WRITE_OUTCOME_UNCERTAIN,
)


@dataclass
class AgentRunWriteReceipt:
    """A typed, auditable receipt for one controlled agent-run write attempt.

    Contains no credentials, no SQL, no connection URL, and no raw stored content. The
    boolean flags describe what actually happened during this attempt.
    """

    outcome: str = AgentRunWriteOutcome.DENIED
    permitted: bool = False
    reason_code: Optional[str] = None
    target_table: str = TARGET_TABLE
    target_action: str = TARGET_ACTION
    # Stored identity — set only when safely known (created / idempotent_replay).
    stored_record_id: Optional[str] = None
    idempotency_key: Optional[str] = None  # the caller's key (not a secret); a safe reference
    audit_trace_ref: Optional[str] = None
    # Actual-behavior flags.
    database_connection_made: bool = False
    sql_execution_made: bool = False
    database_write_made: bool = False
    stored_record_created: bool = False
    existing_record_returned: bool = False
    transaction_committed: bool = False
    outcome_uncertain: bool = False
    # Review-gate posture of the record this write concerns.
    review_status: Optional[str] = None
    output_status: Optional[str] = None
    # Server-stamped timestamps read back from the DB (ISO strings), when known.
    created_at: Optional[str] = None
    database_write_at: Optional[str] = None
    reasons: List[str] = field(default_factory=list)
    warnings: List[str] = field(default_factory=list)


class EvidenceWriteOutcome:
    """Outcome codes for a controlled evidence write (str constants; no Enum dependency)."""

    CREATED = "created"
    IDEMPOTENT_REPLAY = "idempotent_replay"
    DENIED = "denied"
    FAILED_BEFORE_WRITE = "failed_before_write"
    WRITE_OUTCOME_UNCERTAIN = "write_outcome_uncertain"


# The single table/action the Phase 21 evidence writer may target (Phase 17 allowlist subset).
EVIDENCE_TARGET_TABLE = "evidence_references"
EVIDENCE_TARGET_ACTION = "create_draft"

EVIDENCE_ALL_OUTCOMES = (
    EvidenceWriteOutcome.CREATED,
    EvidenceWriteOutcome.IDEMPOTENT_REPLAY,
    EvidenceWriteOutcome.DENIED,
    EvidenceWriteOutcome.FAILED_BEFORE_WRITE,
    EvidenceWriteOutcome.WRITE_OUTCOME_UNCERTAIN,
)


@dataclass
class EvidenceWriteReceipt:
    """A typed, auditable receipt for one controlled evidence write attempt.

    Contains no credentials, no SQL, no connection URL, and no raw stored content. The
    boolean flags describe what actually happened during this attempt.
    """

    outcome: str = EvidenceWriteOutcome.DENIED
    permitted: bool = False
    reason_code: Optional[str] = None
    target_table: str = EVIDENCE_TARGET_TABLE
    target_action: str = EVIDENCE_TARGET_ACTION
    # Stored identity — set only when safely known (created / idempotent_replay).
    stored_record_id: Optional[str] = None
    idempotency_key: Optional[str] = None  # the caller's key (not a secret); a safe reference
    audit_trace_ref: Optional[str] = None
    # Actual-behavior flags.
    database_connection_made: bool = False
    sql_execution_made: bool = False
    database_write_made: bool = False
    stored_record_created: bool = False
    existing_record_returned: bool = False
    transaction_committed: bool = False
    outcome_uncertain: bool = False
    # Review-gate posture of the record this write concerns.
    review_status: Optional[str] = None
    output_status: Optional[str] = None
    # Server-stamped timestamps read back from the DB (ISO strings), when known.
    created_at: Optional[str] = None
    database_write_at: Optional[str] = None
    reasons: List[str] = field(default_factory=list)
    warnings: List[str] = field(default_factory=list)


class ReviewWriteOutcome:
    """Outcome codes for a controlled review-record write (str constants; no Enum)."""

    CREATED = "created"
    IDEMPOTENT_REPLAY = "idempotent_replay"
    DENIED = "denied"
    FAILED_BEFORE_WRITE = "failed_before_write"
    WRITE_OUTCOME_UNCERTAIN = "write_outcome_uncertain"


# The single table/action the Phase 22 review writer may target (Phase 17 allowlist subset).
REVIEW_TARGET_TABLE = "review_records"
REVIEW_TARGET_ACTION = "create_review_record"

REVIEW_ALL_OUTCOMES = (
    ReviewWriteOutcome.CREATED,
    ReviewWriteOutcome.IDEMPOTENT_REPLAY,
    ReviewWriteOutcome.DENIED,
    ReviewWriteOutcome.FAILED_BEFORE_WRITE,
    ReviewWriteOutcome.WRITE_OUTCOME_UNCERTAIN,
)


@dataclass
class ReviewWriteReceipt:
    """A typed, auditable receipt for one controlled review-record write attempt.

    Contains no credentials, no SQL, no connection URL, and no raw stored content. The
    boolean flags describe what actually happened during this attempt. ``decision`` and
    ``authoritative`` echo the recorded review outcome.
    """

    outcome: str = ReviewWriteOutcome.DENIED
    permitted: bool = False
    reason_code: Optional[str] = None
    target_table: str = REVIEW_TARGET_TABLE
    target_action: str = REVIEW_TARGET_ACTION
    # Stored identity — set only when safely known (created / idempotent_replay).
    stored_record_id: Optional[str] = None
    idempotency_key: Optional[str] = None  # the caller's key (not a secret); a safe reference
    audit_trace_ref: Optional[str] = None
    # Actual-behavior flags.
    database_connection_made: bool = False
    sql_execution_made: bool = False
    database_write_made: bool = False
    stored_record_created: bool = False
    existing_record_returned: bool = False
    transaction_committed: bool = False
    outcome_uncertain: bool = False
    # Recorded review outcome.
    decision: Optional[str] = None
    authoritative: bool = False
    review_status: Optional[str] = None
    output_status: Optional[str] = None
    # Server-stamped timestamps read back from the DB (ISO strings), when known.
    created_at: Optional[str] = None
    database_write_at: Optional[str] = None
    reasons: List[str] = field(default_factory=list)
    warnings: List[str] = field(default_factory=list)


class AgentTaskQueueWriteOutcome:
    """Outcome codes for a controlled agent-task-queue write (str constants; no Enum)."""

    CREATED = "created"
    IDEMPOTENT_REPLAY = "idempotent_replay"
    DENIED = "denied"
    FAILED_BEFORE_WRITE = "failed_before_write"
    WRITE_OUTCOME_UNCERTAIN = "write_outcome_uncertain"


# The single table/action the Phase 27 agent-task-queue writer may target (Phase 17 subset).
AGENT_TASK_QUEUE_TARGET_TABLE = "agent_task_queue_records"
AGENT_TASK_QUEUE_TARGET_ACTION = "create_agent_task_queue_record"

AGENT_TASK_QUEUE_ALL_OUTCOMES = (
    AgentTaskQueueWriteOutcome.CREATED,
    AgentTaskQueueWriteOutcome.IDEMPOTENT_REPLAY,
    AgentTaskQueueWriteOutcome.DENIED,
    AgentTaskQueueWriteOutcome.FAILED_BEFORE_WRITE,
    AgentTaskQueueWriteOutcome.WRITE_OUTCOME_UNCERTAIN,
)


@dataclass
class AgentTaskQueueWriteReceipt:
    """A typed, auditable receipt for one controlled agent-task-queue write attempt.

    Contains no credentials, no SQL, no connection URL, and **no raw packet/evidence/interview
    content, source bytes, or generated agent output**. The boolean flags describe what
    actually happened during this attempt. This write persists a **review-gated, not-executed**
    queue record only — it never executes an agent and never creates an ``agent_run_records`` row.
    """

    outcome: str = AgentTaskQueueWriteOutcome.DENIED
    permitted: bool = False
    reason_code: Optional[str] = None
    target_table: str = AGENT_TASK_QUEUE_TARGET_TABLE
    target_action: str = AGENT_TASK_QUEUE_TARGET_ACTION
    # Stored identity — set only when safely known (created / idempotent_replay).
    stored_record_id: Optional[str] = None
    idempotency_key: Optional[str] = None  # the caller's key (not a secret); a safe reference
    audit_trace_ref: Optional[str] = None
    # Actual-behavior flags.
    database_connection_made: bool = False
    sql_execution_made: bool = False
    database_write_made: bool = False
    stored_record_created: bool = False
    existing_record_returned: bool = False
    transaction_committed: bool = False
    outcome_uncertain: bool = False
    # Review-gate / non-execution posture of the record this write concerns.
    review_status: Optional[str] = None
    output_status: Optional[str] = None
    execution_status: Optional[str] = None
    readiness_state: Optional[str] = None
    # Server-stamped timestamps read back from the DB (ISO strings), when known.
    created_at: Optional[str] = None
    database_write_at: Optional[str] = None
    reasons: List[str] = field(default_factory=list)
    warnings: List[str] = field(default_factory=list)


class ReviewBundleWriteOutcome:
    """Outcome codes for a controlled review-bundle write (str constants; no Enum)."""

    CREATED = "created"
    IDEMPOTENT_REPLAY = "idempotent_replay"
    DENIED = "denied"
    FAILED_BEFORE_WRITE = "failed_before_write"
    WRITE_OUTCOME_UNCERTAIN = "write_outcome_uncertain"


# The single table/action the Phase 30 review-bundle writer may target (Phase 17 subset).
REVIEW_BUNDLE_TARGET_TABLE = "review_bundle_records"
REVIEW_BUNDLE_TARGET_ACTION = "create_review_bundle_record"

REVIEW_BUNDLE_ALL_OUTCOMES = (
    ReviewBundleWriteOutcome.CREATED,
    ReviewBundleWriteOutcome.IDEMPOTENT_REPLAY,
    ReviewBundleWriteOutcome.DENIED,
    ReviewBundleWriteOutcome.FAILED_BEFORE_WRITE,
    ReviewBundleWriteOutcome.WRITE_OUTCOME_UNCERTAIN,
)


@dataclass
class ReviewBundleWriteReceipt:
    """A typed, auditable receipt for one controlled review-bundle write attempt.

    Contains no credentials, no SQL, no connection URL, **no raw packet/evidence/interview
    content, source bytes, generated agent output, or final review decision**. The boolean flags
    describe what actually happened during this attempt. This write persists a **review-gated,
    not-approved** review bundle record only — it approves nothing, calls no Phase 22 review
    writer, and creates no ``review_records`` or ``agent_run_records`` row.
    """

    outcome: str = ReviewBundleWriteOutcome.DENIED
    permitted: bool = False
    reason_code: Optional[str] = None
    target_table: str = REVIEW_BUNDLE_TARGET_TABLE
    target_action: str = REVIEW_BUNDLE_TARGET_ACTION
    # Stored identity — set only when safely known (created / idempotent_replay).
    stored_record_id: Optional[str] = None
    idempotency_key: Optional[str] = None  # the caller's key (not a secret); a safe reference
    audit_trace_ref: Optional[str] = None
    # Actual-behavior flags.
    database_connection_made: bool = False
    sql_execution_made: bool = False
    database_write_made: bool = False
    stored_record_created: bool = False
    existing_record_returned: bool = False
    transaction_committed: bool = False
    outcome_uncertain: bool = False
    # Review-gate / non-approval posture of the record this write concerns.
    review_status: Optional[str] = None
    output_status: Optional[str] = None
    lifecycle_status: Optional[str] = None
    # Non-effect flags — always False (Phase 30 approves nothing and executes nothing).
    review_approval_made: bool = False
    client_facing_output_created: bool = False
    financial_verification_made: bool = False
    capsule_publication_made: bool = False
    agent_execution_made: bool = False
    llm_call_made: bool = False
    agentnet_call_made: bool = False
    resolver_call_made: bool = False
    network_call_made: bool = False
    # Server-stamped timestamps read back from the DB (ISO strings), when known.
    created_at: Optional[str] = None
    database_write_at: Optional[str] = None
    reasons: List[str] = field(default_factory=list)
    warnings: List[str] = field(default_factory=list)


class InternalReviewerDecisionWriteOutcome:
    """Outcome codes for a controlled internal-reviewer-decision write (str constants; no Enum)."""

    CREATED = "created"
    IDEMPOTENT_REPLAY = "idempotent_replay"
    DENIED = "denied"
    FAILED_BEFORE_WRITE = "failed_before_write"
    WRITE_OUTCOME_UNCERTAIN = "write_outcome_uncertain"


# The single table/action the Phase 33 internal-reviewer-decision writer may target (Phase 17 subset).
INTERNAL_REVIEWER_DECISION_TARGET_TABLE = "internal_reviewer_decision_records"
INTERNAL_REVIEWER_DECISION_TARGET_ACTION = "create_internal_reviewer_decision_record"

INTERNAL_REVIEWER_DECISION_ALL_OUTCOMES = (
    InternalReviewerDecisionWriteOutcome.CREATED,
    InternalReviewerDecisionWriteOutcome.IDEMPOTENT_REPLAY,
    InternalReviewerDecisionWriteOutcome.DENIED,
    InternalReviewerDecisionWriteOutcome.FAILED_BEFORE_WRITE,
    InternalReviewerDecisionWriteOutcome.WRITE_OUTCOME_UNCERTAIN,
)


@dataclass
class InternalReviewerDecisionWriteReceipt:
    """A typed, auditable receipt for one controlled internal-reviewer-decision write attempt.

    Contains no credentials, no SQL, no connection URL, **no raw packet/evidence/interview
    content, source bytes, generated agent output, final review decision, or client-facing
    language**. The boolean flags describe what actually happened during this attempt. This write
    persists a **review-gated, non-approval** internal reviewer decision record only — it approves
    nothing, calls no Phase 22 review writer, and creates no ``review_records`` or
    ``agent_run_records`` row. ``decision_intent`` and ``route_to`` echo the routing recommendation;
    ``ready_for_internal_use`` is **not** approval.
    """

    outcome: str = InternalReviewerDecisionWriteOutcome.DENIED
    permitted: bool = False
    reason_code: Optional[str] = None
    target_table: str = INTERNAL_REVIEWER_DECISION_TARGET_TABLE
    target_action: str = INTERNAL_REVIEWER_DECISION_TARGET_ACTION
    # Stored identity — set only when safely known (created / idempotent_replay).
    stored_record_id: Optional[str] = None
    idempotency_key: Optional[str] = None  # the caller's key (not a secret); a safe reference
    audit_trace_ref: Optional[str] = None
    # Actual-behavior flags.
    database_connection_made: bool = False
    sql_execution_made: bool = False
    database_write_made: bool = False
    stored_record_created: bool = False
    existing_record_returned: bool = False
    transaction_committed: bool = False
    outcome_uncertain: bool = False
    # Decision-routing posture of the record this write concerns (safe labels only).
    decision_intent: Optional[str] = None
    route_to: Optional[str] = None
    review_status: Optional[str] = None
    output_status: Optional[str] = None
    lifecycle_status: Optional[str] = None
    # Non-effect flags — always False (Phase 33 approves nothing and executes nothing).
    review_records_write_made: bool = False
    review_approval_made: bool = False
    client_facing_output_created: bool = False
    financial_verification_made: bool = False
    capsule_publication_made: bool = False
    agent_execution_made: bool = False
    llm_call_made: bool = False
    agentnet_call_made: bool = False
    resolver_call_made: bool = False
    network_call_made: bool = False
    # Server-stamped timestamps read back from the DB (ISO strings), when known.
    created_at: Optional[str] = None
    database_write_at: Optional[str] = None
    reasons: List[str] = field(default_factory=list)
    warnings: List[str] = field(default_factory=list)


class SourceIngestionWriteOutcome:
    """Outcome codes for a controlled source-ingestion write (str constants; no Enum)."""

    CREATED = "created"
    IDEMPOTENT_REPLAY = "idempotent_replay"
    DENIED = "denied"
    FAILED_BEFORE_WRITE = "failed_before_write"
    WRITE_OUTCOME_UNCERTAIN = "write_outcome_uncertain"


# The single table/action the Phase 24 source-ingestion writer may target (Phase 17 subset).
SOURCE_INGESTION_TARGET_TABLE = "source_ingestion_records"
SOURCE_INGESTION_TARGET_ACTION = "create_source_ingestion_record"

SOURCE_INGESTION_ALL_OUTCOMES = (
    SourceIngestionWriteOutcome.CREATED,
    SourceIngestionWriteOutcome.IDEMPOTENT_REPLAY,
    SourceIngestionWriteOutcome.DENIED,
    SourceIngestionWriteOutcome.FAILED_BEFORE_WRITE,
    SourceIngestionWriteOutcome.WRITE_OUTCOME_UNCERTAIN,
)


@dataclass
class SourceIngestionWriteReceipt:
    """A typed, auditable receipt for one controlled source-ingestion write attempt.

    Contains no credentials, no SQL, no connection URL, and **no raw packet content**. The
    boolean flags describe what actually happened during this attempt.
    """

    outcome: str = SourceIngestionWriteOutcome.DENIED
    permitted: bool = False
    reason_code: Optional[str] = None
    target_table: str = SOURCE_INGESTION_TARGET_TABLE
    target_action: str = SOURCE_INGESTION_TARGET_ACTION
    # Stored identity — set only when safely known (created / idempotent_replay).
    stored_record_id: Optional[str] = None
    idempotency_key: Optional[str] = None  # the caller's key (not a secret); a safe reference
    audit_trace_ref: Optional[str] = None
    # Actual-behavior flags.
    database_connection_made: bool = False
    sql_execution_made: bool = False
    database_write_made: bool = False
    stored_record_created: bool = False
    existing_record_returned: bool = False
    transaction_committed: bool = False
    outcome_uncertain: bool = False
    # Review-gate posture of the record this write concerns.
    review_status: Optional[str] = None
    output_status: Optional[str] = None
    # Server-stamped timestamps read back from the DB (ISO strings), when known.
    created_at: Optional[str] = None
    database_write_at: Optional[str] = None
    reasons: List[str] = field(default_factory=list)
    warnings: List[str] = field(default_factory=list)


class IntakeNoteWriteOutcome:
    """Outcome codes for a controlled intake-note write (str constants; no Enum)."""

    CREATED = "created"
    IDEMPOTENT_REPLAY = "idempotent_replay"
    DENIED = "denied"
    FAILED_BEFORE_WRITE = "failed_before_write"
    WRITE_OUTCOME_UNCERTAIN = "write_outcome_uncertain"


# The single table/action the Phase 34 intake-note writer may target (Phase 17 subset).
INTAKE_NOTE_TARGET_TABLE = "intake_note_records"
INTAKE_NOTE_TARGET_ACTION = "create_intake_note_record"

INTAKE_NOTE_ALL_OUTCOMES = (
    IntakeNoteWriteOutcome.CREATED,
    IntakeNoteWriteOutcome.IDEMPOTENT_REPLAY,
    IntakeNoteWriteOutcome.DENIED,
    IntakeNoteWriteOutcome.FAILED_BEFORE_WRITE,
    IntakeNoteWriteOutcome.WRITE_OUTCOME_UNCERTAIN,
)


@dataclass
class IntakeNoteDraft:
    """A DB-free input draft for one authorized intake note (never persisted by itself).

    Intake notes are **first-class operational records** (client interviews, consultant
    observations, warehouse walkaround notes, discovery calls, source-intake comments, controlled
    packet-ingestion outputs, consultant-authored notes). Unlike prior summary-only drafts, the
    ``note_text`` field is intended to carry **authorized operational client prose** — which is
    acceptable **only in the managed DB**, never in Git / fixtures / examples / sample packets /
    logs / receipts / test data. ``intake_note_id`` and ``captured_at`` are server-controlled and
    left ``None`` here. All approval/publication/execution posture flags default to the not-allowed
    posture and ``requires_human_review`` defaults to ``True``.
    """

    intake_note_id: Optional[str] = None  # server-controlled; caller must leave None
    owner_id: Optional[str] = None
    client_id: Optional[str] = None
    engagement_id: Optional[str] = None
    authorization_scope: Optional[str] = None
    note_type: Optional[str] = None      # short safe label (e.g. "interview", "walkaround")
    note_source: Optional[str] = None    # short safe label (e.g. "discovery_call")
    note_text: Optional[str] = None      # bounded operational prose (managed-DB storage only)
    note_summary: Optional[str] = None   # short safe summary (optional)
    captured_by: Optional[str] = None    # short safe label
    captured_role: Optional[str] = None  # short safe label (optional)
    source_ref: Optional[str] = None     # short safe reference (optional)
    source_ingestion_record_id: Optional[str] = None
    related_evidence_reference_id: Optional[str] = None
    related_review_bundle_record_id: Optional[str] = None
    review_status: str = "needs_review"
    lifecycle_status: str = "draft"
    client_facing_approved: bool = False
    financial_verified: bool = False
    capsule_candidate_ready: bool = False
    publication_allowed: bool = False
    execution_allowed: bool = False
    requires_human_review: bool = True
    warnings: List[str] = field(default_factory=list)
    captured_at: Optional[str] = None  # reserved; server-stamped created_at is authoritative


@dataclass
class IntakeNoteWriteReceipt:
    """A typed, auditable receipt for one controlled intake-note write attempt.

    Contains no credentials, no SQL, no connection URL, and — critically — **never the stored
    ``note_text`` / note body or any raw note content**. Denial reasons report only a field name /
    marker *category*, never the offending value. The boolean flags describe what actually happened
    during this attempt. This write persists a **review-gated, non-final** internal operational
    record only — it approves nothing, publishes nothing, executes nothing, and creates no
    ``review_records`` / ``agent_run_records`` row.
    """

    outcome: str = IntakeNoteWriteOutcome.DENIED
    permitted: bool = False
    reason_code: Optional[str] = None
    target_table: str = INTAKE_NOTE_TARGET_TABLE
    target_action: str = INTAKE_NOTE_TARGET_ACTION
    # Stored identity — set only when safely known (created / idempotent_replay).
    stored_record_id: Optional[str] = None
    idempotency_key: Optional[str] = None  # the caller's key (not a secret); a safe reference
    audit_trace_ref: Optional[str] = None
    # Actual-behavior flags.
    database_connection_made: bool = False
    sql_execution_made: bool = False
    database_write_made: bool = False
    stored_record_created: bool = False
    existing_record_returned: bool = False
    transaction_committed: bool = False
    outcome_uncertain: bool = False
    # Safe routing labels of the record this write concerns (labels, never note content).
    note_type: Optional[str] = None
    note_source: Optional[str] = None
    review_status: Optional[str] = None
    lifecycle_status: Optional[str] = None
    # Non-effect flags — always False (Phase 34 approves/publishes/executes nothing).
    review_records_write_made: bool = False
    review_approval_made: bool = False
    client_facing_output_created: bool = False
    financial_verification_made: bool = False
    capsule_publication_made: bool = False
    agentnet_publication_made: bool = False
    agent_execution_made: bool = False
    llm_call_made: bool = False
    agentnet_call_made: bool = False
    resolver_call_made: bool = False
    network_call_made: bool = False
    # Server-stamped timestamps read back from the DB (ISO strings), when known.
    created_at: Optional[str] = None
    database_write_at: Optional[str] = None
    reasons: List[str] = field(default_factory=list)
    warnings: List[str] = field(default_factory=list)


class InternalAssessmentReportDraftWriteOutcome:
    """Outcome codes for a controlled internal-assessment-report-draft write (str constants)."""

    CREATED = "created"
    IDEMPOTENT_REPLAY = "idempotent_replay"
    DENIED = "denied"
    FAILED_BEFORE_WRITE = "failed_before_write"
    WRITE_OUTCOME_UNCERTAIN = "write_outcome_uncertain"


# The single table/action the Phase 37 report-draft writer may target (Phase 17 subset).
INTERNAL_ASSESSMENT_REPORT_DRAFT_TARGET_TABLE = "internal_assessment_report_drafts"
INTERNAL_ASSESSMENT_REPORT_DRAFT_TARGET_ACTION = "create_internal_assessment_report_draft"

INTERNAL_ASSESSMENT_REPORT_DRAFT_ALL_OUTCOMES = (
    InternalAssessmentReportDraftWriteOutcome.CREATED,
    InternalAssessmentReportDraftWriteOutcome.IDEMPOTENT_REPLAY,
    InternalAssessmentReportDraftWriteOutcome.DENIED,
    InternalAssessmentReportDraftWriteOutcome.FAILED_BEFORE_WRITE,
    InternalAssessmentReportDraftWriteOutcome.WRITE_OUTCOME_UNCERTAIN,
)


@dataclass
class InternalAssessmentReportDraftWriteReceipt:
    """A typed, auditable receipt for one controlled internal-report-draft write attempt.

    Contains no credentials, no SQL, no connection URL, and **no report prose** — no final
    client-facing language, no raw intake-note/packet/evidence/interview text, no source bytes, no
    generated agent output, no ROI or savings figure, no approval decision, and no capsule/AgentNet
    publish payload. Denial reasons report only a field name / reference position / marker
    *category*, never the offending value.

    The boolean flags describe what actually happened during this attempt. This write persists a
    **review-gated, internal-only, non-final** report *plan* record — it approves nothing, verifies
    nothing, publishes nothing, executes nothing, calls no Phase 22 review writer, and creates no
    ``review_records`` / ``agent_run_records`` row. ``output_status`` is fixed at
    ``plan_persisted``: a stored row is a persisted plan, never a drafted report.
    """

    outcome: str = InternalAssessmentReportDraftWriteOutcome.DENIED
    permitted: bool = False
    reason_code: Optional[str] = None
    target_table: str = INTERNAL_ASSESSMENT_REPORT_DRAFT_TARGET_TABLE
    target_action: str = INTERNAL_ASSESSMENT_REPORT_DRAFT_TARGET_ACTION
    # Stored identity — set only when safely known (created / idempotent_replay).
    stored_record_id: Optional[str] = None
    report_plan_id: Optional[str] = None      # a safe caller-supplied plan ref
    plan_fingerprint: Optional[str] = None    # the Phase 36 deterministic plan digest
    idempotency_key: Optional[str] = None     # the caller's key (not a secret); a safe reference
    audit_trace_ref: Optional[str] = None
    # Actual-behavior flags.
    database_connection_made: bool = False
    sql_execution_made: bool = False
    database_write_made: bool = False
    stored_record_created: bool = False
    existing_record_returned: bool = False
    transaction_committed: bool = False
    outcome_uncertain: bool = False
    # Internal-only posture of the record this write concerns (safe labels only).
    audience: Optional[str] = None
    output_status: Optional[str] = None
    review_status: Optional[str] = None
    lifecycle_status: Optional[str] = None
    # Safe structural counts (never content).
    section_count: int = 0
    finding_candidate_count: int = 0
    recommendation_candidate_count: int = 0
    open_gap_count: int = 0
    # Non-effect flags — always False (Phase 37 approves/verifies/publishes/executes nothing).
    review_records_write_made: bool = False
    agent_run_records_write_made: bool = False
    review_approval_made: bool = False
    client_facing_output_created: bool = False
    client_facing_approval_made: bool = False
    financial_verification_made: bool = False
    capsule_candidate_created: bool = False
    capsule_publication_made: bool = False
    agentnet_publication_made: bool = False
    agent_execution_made: bool = False
    mock_agent_execution_made: bool = False
    llm_call_made: bool = False
    agentnet_call_made: bool = False
    resolver_call_made: bool = False
    network_call_made: bool = False
    # Server-stamped timestamps read back from the DB (ISO strings), when known.
    created_at: Optional[str] = None
    database_write_at: Optional[str] = None
    reasons: List[str] = field(default_factory=list)
    warnings: List[str] = field(default_factory=list)


class InternalReportReviewPacketWriteOutcome:
    """Outcome codes for a controlled internal-report-review-packet write (str constants)."""

    CREATED = "created"
    IDEMPOTENT_REPLAY = "idempotent_replay"
    DENIED = "denied"
    FAILED_BEFORE_WRITE = "failed_before_write"
    WRITE_OUTCOME_UNCERTAIN = "write_outcome_uncertain"


# The single table/action the Phase 38 review-packet writer may target (Phase 17 subset).
INTERNAL_REPORT_REVIEW_PACKET_TARGET_TABLE = "internal_report_review_packets"
INTERNAL_REPORT_REVIEW_PACKET_TARGET_ACTION = "create_internal_report_review_packet"

INTERNAL_REPORT_REVIEW_PACKET_ALL_OUTCOMES = (
    InternalReportReviewPacketWriteOutcome.CREATED,
    InternalReportReviewPacketWriteOutcome.IDEMPOTENT_REPLAY,
    InternalReportReviewPacketWriteOutcome.DENIED,
    InternalReportReviewPacketWriteOutcome.FAILED_BEFORE_WRITE,
    InternalReportReviewPacketWriteOutcome.WRITE_OUTCOME_UNCERTAIN,
)

# The one report-draft table a packet may reference (Phase 37).
REVIEW_PACKET_SOURCE_REPORT_DRAFT_TABLE = "internal_assessment_report_drafts"
# Documented fixed stored values (see docs/INTERNAL_REPORT_REVIEW_PACKET_CONTROLLED_WRITER.md).
REVIEW_PACKET_STATUS = "ready_for_internal_review"
REVIEW_PACKET_DECISION_STATUS = "not_decided"


@dataclass
class InternalReportReviewPacketDraft:
    """A DB-free input draft for one internal-only report review packet (never persisted alone).

    A packet records **what a Peak human reviewer was shown and asked to evaluate** for a Phase 37
    ``internal_assessment_report_drafts`` row. It carries **labels, statuses, references, and short
    internal prompts only** — never final client-facing language, raw intake-note / packet /
    evidence / interview text, source bytes, generated agent output, LLM prompts, credentials,
    DSNs, raw SQL, stack traces, approval decisions, ROI or savings figures, or capsule / AgentNet
    publish payloads.

    ``review_packet_id`` and ``created_at`` are server-controlled and must be left ``None``.
    ``reviewer_decision_record_id`` must also be ``None``: a packet is created *before* any
    reviewer decision exists. All approval / verification / publication / execution posture flags
    default to the not-allowed posture and ``requires_human_review`` defaults to ``True``.

    Checklist families are lists of small strict dicts:

    * ``section_review_checklist`` — ``{"section_id", "check_id", "status"}``
    * ``readiness_checklist``      — ``{"check_id", "status"}``
    * ``required_followup_actions``— ``{"action_id", "status"}``
    """

    review_packet_id: Optional[str] = None  # server-controlled; caller must leave None
    owner_id: Optional[str] = None
    client_id: Optional[str] = None
    engagement_id: Optional[str] = None
    authorization_scope: Optional[str] = None
    # Linkage to the Phase 37 stored report draft (verified against the stored row at write time).
    internal_assessment_report_draft_id: Optional[str] = None
    report_plan_id: Optional[str] = None
    plan_fingerprint: Optional[str] = None
    report_draft_payload_fingerprint: Optional[str] = None
    assigned_reviewer: Optional[str] = None  # short safe label/ref (optional)
    packet_purpose: Optional[str] = None     # short safe internal label (optional)
    audience: str = "internal"
    packet_status: str = REVIEW_PACKET_STATUS
    review_status: str = "needs_review"
    lifecycle_status: str = "draft"
    reviewer_decision_record_id: Optional[str] = None  # must be None at creation
    reviewer_decision_status: str = REVIEW_PACKET_DECISION_STATUS
    section_review_checklist: List[dict] = field(default_factory=list)
    evidence_trace_refs: List[str] = field(default_factory=list)   # record ids only
    open_gaps: List[str] = field(default_factory=list)
    blocked_items: List[str] = field(default_factory=list)
    reviewer_questions: List[str] = field(default_factory=list)    # short internal prompts
    readiness_checklist: List[dict] = field(default_factory=list)
    required_followup_actions: List[dict] = field(default_factory=list)
    # Forward-looking placeholders naming FUTURE gates; nothing is verified or published here.
    future_financial_verification_items: List[str] = field(default_factory=list)
    future_capsule_candidate_items: List[str] = field(default_factory=list)
    client_facing_approved: bool = False
    review_approval_made: bool = False
    financial_verified: bool = False
    capsule_candidate_ready: bool = False
    publication_allowed: bool = False
    execution_allowed: bool = False
    requires_human_review: bool = True
    reasons: List[str] = field(default_factory=list)
    warnings: List[str] = field(default_factory=list)
    created_at: Optional[str] = None  # server-stamped created_at is authoritative


@dataclass
class InternalReportReviewPacketWriteReceipt:
    """A typed, auditable receipt for one controlled review-packet write attempt.

    Contains no credentials, no SQL, no connection URL, and **no report prose** — no final
    client-facing language, no raw note/packet/evidence/interview text, no source bytes, no
    generated agent output, no ROI or savings figure, no approval decision, and no capsule /
    AgentNet publish payload. Denial reasons report only a field name, an item position, or a
    marker *category*, never the offending value.

    This write persists a **review-gated, internal-only, pre-decision** review packet — it approves
    nothing, verifies nothing, publishes nothing, executes nothing, calls no Phase 22 review
    writer, and creates no ``review_records`` / ``agent_run_records`` row.
    """

    outcome: str = InternalReportReviewPacketWriteOutcome.DENIED
    permitted: bool = False
    reason_code: Optional[str] = None
    target_table: str = INTERNAL_REPORT_REVIEW_PACKET_TARGET_TABLE
    target_action: str = INTERNAL_REPORT_REVIEW_PACKET_TARGET_ACTION
    # Stored identity — set only when safely known (created / idempotent_replay).
    stored_record_id: Optional[str] = None
    internal_assessment_report_draft_id: Optional[str] = None
    report_plan_id: Optional[str] = None
    plan_fingerprint: Optional[str] = None
    idempotency_key: Optional[str] = None
    audit_trace_ref: Optional[str] = None
    # Actual-behavior flags.
    database_connection_made: bool = False
    sql_execution_made: bool = False
    database_write_made: bool = False
    stored_record_created: bool = False
    existing_record_returned: bool = False
    transaction_committed: bool = False
    outcome_uncertain: bool = False
    # Internal-only posture of the record this write concerns (safe labels only).
    audience: Optional[str] = None
    packet_status: Optional[str] = None
    review_status: Optional[str] = None
    lifecycle_status: Optional[str] = None
    reviewer_decision_status: Optional[str] = None
    # Safe structural counts (never content).
    section_review_item_count: int = 0
    reviewer_question_count: int = 0
    readiness_check_item_count: int = 0
    required_followup_action_count: int = 0
    open_gap_count: int = 0
    evidence_trace_ref_count: int = 0
    # Non-effect flags — always False (Phase 38 approves/verifies/publishes/executes nothing).
    review_records_write_made: bool = False
    agent_run_records_write_made: bool = False
    review_approval_made: bool = False
    client_facing_output_created: bool = False
    client_facing_approval_made: bool = False
    financial_verification_made: bool = False
    capsule_candidate_created: bool = False
    capsule_publication_made: bool = False
    agentnet_publication_made: bool = False
    agent_execution_made: bool = False
    mock_agent_execution_made: bool = False
    llm_call_made: bool = False
    agentnet_call_made: bool = False
    resolver_call_made: bool = False
    network_call_made: bool = False
    # Server-stamped timestamps read back from the DB (ISO strings), when known.
    created_at: Optional[str] = None
    database_write_at: Optional[str] = None
    reasons: List[str] = field(default_factory=list)
    warnings: List[str] = field(default_factory=list)


class InternalReportReviewPacketDecisionWriteOutcome:
    """Outcome codes for a controlled packet-decision write (str constants)."""

    CREATED = "created"
    IDEMPOTENT_REPLAY = "idempotent_replay"
    DENIED = "denied"
    FAILED_BEFORE_WRITE = "failed_before_write"
    WRITE_OUTCOME_UNCERTAIN = "write_outcome_uncertain"


# The single table/action the Phase 39 packet-decision writer may target (Phase 17 subset).
PACKET_DECISION_TARGET_TABLE = "internal_report_review_packet_decisions"
PACKET_DECISION_TARGET_ACTION = "create_internal_report_review_packet_decision"

PACKET_DECISION_ALL_OUTCOMES = (
    InternalReportReviewPacketDecisionWriteOutcome.CREATED,
    InternalReportReviewPacketDecisionWriteOutcome.IDEMPOTENT_REPLAY,
    InternalReportReviewPacketDecisionWriteOutcome.DENIED,
    InternalReportReviewPacketDecisionWriteOutcome.FAILED_BEFORE_WRITE,
    InternalReportReviewPacketDecisionWriteOutcome.WRITE_OUTCOME_UNCERTAIN,
)

# Fixed stored values (see docs/INTERNAL_REPORT_REVIEW_PACKET_DECISION_CONTROLLED_WRITER.md).
PACKET_DECISION_SCOPE = "internal_report_review_packet"
PACKET_DECISION_SOURCE_PACKET_TABLE = "internal_report_review_packets"
PACKET_DECISION_SOURCE_REPORT_DRAFT_TABLE = "internal_assessment_report_drafts"
# Decision-specific axis, server-derived from decision_intent (never caller-supplied).
PACKET_DECISION_STATUS_RECORDED = "decision_recorded"
PACKET_DECISION_STATUS_NEEDS_FOLLOWUP = "needs_followup"


@dataclass
class InternalReportReviewPacketDecisionDraft:
    """A DB-free input draft for one internal-only packet-review decision (never persisted alone).

    Records a Peak human reviewer's decision on a Phase 38 ``internal_report_review_packets`` row,
    preserving the audit chain packet -> report draft -> report plan. It carries **short safe
    labels, references, and one bounded internal summary only** — never final client-facing
    language, raw intake-note / packet / evidence / interview text, source bytes, generated agent
    output, LLM prompts, credentials, DSNs, raw SQL, stack traces, client-facing approvals, ROI or
    savings figures, or capsule / AgentNet publish payloads.

    ``decision_record_id`` and ``created_at`` are server-controlled and must be left ``None``.
    ``decision_status``, ``decision_scope``, ``audience``, ``review_status``, and
    ``lifecycle_status`` are all server-stamped by the writer and are not caller inputs.

    ``requested_followup_actions`` is a list of strict dicts ``{"action_id", "status"}``.
    """

    decision_record_id: Optional[str] = None  # server-controlled; caller must leave None
    owner_id: Optional[str] = None
    client_id: Optional[str] = None
    engagement_id: Optional[str] = None
    authorization_scope: Optional[str] = None
    # Audit chain (each verified against the stored rows at write time).
    internal_report_review_packet_id: Optional[str] = None
    internal_assessment_report_draft_id: Optional[str] = None
    report_plan_id: Optional[str] = None
    plan_fingerprint: Optional[str] = None
    report_draft_payload_fingerprint: Optional[str] = None
    packet_payload_fingerprint: Optional[str] = None
    reviewer_ref: Optional[str] = None       # short safe reviewer label/ref (optional)
    decision_intent: Optional[str] = None    # closed Phase 32 internal-only vocabulary
    safe_decision_summary: Optional[str] = None  # short single-line internal note (optional)
    requested_followup_actions: List[dict] = field(default_factory=list)
    audience: str = "internal"
    client_facing_approved: bool = False
    review_approval_made: bool = False
    financial_verified: bool = False
    capsule_candidate_ready: bool = False
    publication_allowed: bool = False
    execution_allowed: bool = False
    requires_human_review: bool = True
    reasons: List[str] = field(default_factory=list)
    warnings: List[str] = field(default_factory=list)
    created_at: Optional[str] = None  # server-stamped created_at is authoritative


@dataclass
class InternalReportReviewPacketDecisionWriteReceipt:
    """A typed, auditable receipt for one controlled packet-decision write attempt.

    Contains no credentials, no SQL, no connection URL, and **no report prose**. Denial reasons
    report only a field name, an item position, or a marker *category*, never the offending value.

    This write persists an **internal-only** reviewer decision. It approves nothing for client use,
    verifies nothing financially, publishes nothing, executes nothing, updates **no** packet or
    report-draft row, calls no Phase 22 review writer, and creates no ``review_records`` /
    ``agent_run_records`` row.
    """

    outcome: str = InternalReportReviewPacketDecisionWriteOutcome.DENIED
    permitted: bool = False
    reason_code: Optional[str] = None
    target_table: str = PACKET_DECISION_TARGET_TABLE
    target_action: str = PACKET_DECISION_TARGET_ACTION
    # Stored identity — set only when safely known (created / idempotent_replay).
    stored_record_id: Optional[str] = None
    internal_report_review_packet_id: Optional[str] = None
    internal_assessment_report_draft_id: Optional[str] = None
    report_plan_id: Optional[str] = None
    plan_fingerprint: Optional[str] = None
    decision_intent: Optional[str] = None
    idempotency_key: Optional[str] = None
    audit_trace_ref: Optional[str] = None
    # Actual-behavior flags.
    database_connection_made: bool = False
    sql_execution_made: bool = False
    database_write_made: bool = False
    stored_record_created: bool = False
    existing_record_returned: bool = False
    transaction_committed: bool = False
    outcome_uncertain: bool = False
    # Internal-only posture of the record this write concerns (safe labels only).
    audience: Optional[str] = None
    decision_scope: Optional[str] = None
    decision_status: Optional[str] = None
    review_status: Optional[str] = None
    lifecycle_status: Optional[str] = None
    requested_followup_action_count: int = 0
    # Non-effect flags — always False (Phase 39 approves/verifies/publishes/executes nothing and
    # mutates no other row).
    packet_row_updated: bool = False
    report_draft_row_updated: bool = False
    review_records_write_made: bool = False
    agent_run_records_write_made: bool = False
    review_approval_made: bool = False
    client_facing_output_created: bool = False
    client_facing_approval_made: bool = False
    financial_verification_made: bool = False
    capsule_candidate_created: bool = False
    capsule_publication_made: bool = False
    agentnet_publication_made: bool = False
    agent_execution_made: bool = False
    mock_agent_execution_made: bool = False
    llm_call_made: bool = False
    agentnet_call_made: bool = False
    resolver_call_made: bool = False
    network_call_made: bool = False
    # Server-stamped timestamps read back from the DB (ISO strings), when known.
    created_at: Optional[str] = None
    database_write_at: Optional[str] = None
    reasons: List[str] = field(default_factory=list)
    warnings: List[str] = field(default_factory=list)
