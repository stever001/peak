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
