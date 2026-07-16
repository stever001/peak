"""Public contracts for the Phase 20 controlled DB writers (receipt + outcomes).

Pure stdlib dataclasses/constants — **no SQLAlchemy, no peak.db model/session import** — so
the receipt shape can be consumed and asserted on without a live database. The writer that
produces these lives in ``peak.db.agent_run_writer`` and *does* use SQLAlchemy.

The receipt is a **production-shaped persistence receipt**: enough to audit the operation
without exposing credentials, SQL strings, connection URLs, or raw stored content. Every
flag reports **actual** behavior (a denial before any DB connection reports no connection /
no SQL; an idempotent replay reports reads but no new record; a created result reports the
committed write; an uncertain outcome must not falsely claim no record exists). See
docs/AGENT_RUN_CONTROLLED_WRITER.md.
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
