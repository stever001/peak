"""Phase 27: agent_task_queue_records table (schema only, no data).

Creates the new ``agent_task_queue_records`` table for the Phase 27 controlled agent-task-queue
writer — the first live DB persistence for the Phase 26 readiness/queue boundary. It stores
**review-gated, not-executed** queue records only: no agent is executed, no ``agent_run_records``
row is created, and no raw packet/evidence/interview content or secret is persisted.

The table carries the universal governance axes + audit fields (as every table does), the
execution-posture columns (all defaulting to the not-executed / not-allowed / needs-review
posture), and the controlled-writer idempotency columns:

- ``idempotency_key`` — the caller-supplied key that backs replay safety;
- ``payload_fingerprint`` — a deterministic hash of the write payload/identity, used to tell an
  exact idempotent replay apart from a conflicting reuse of the same key;
- ``uq_agent_task_queue_records_idem`` — a UNIQUE index over
  ``(owner_id, client_id, engagement_id, idempotency_key)`` so a repeated authorized write
  cannot create a duplicate row, and a key cannot collide across owner/client/engagement.

Additive and non-destructive: it creates exactly one new table and its indexes/constraint and
touches nothing else. There are **no INSERTs, no seed data, and no data of any kind**. The full
downgrade drops only this new table (and its indexes/constraint). See
docs/AGENT_TASK_QUEUE_CONTROLLED_WRITER.md and docs/AGENT_TASK_QUEUE_IDEMPOTENCY_POLICY.md.

Revision ID: 006_agent_task_queue_records
Revises: 005_source_ingestion_idem
Create Date: (static; no timestamp committed)
"""

from __future__ import annotations

import sqlalchemy as sa
from alembic import op

# revision identifiers, used by Alembic.
revision = "006_agent_task_queue_records"
down_revision = "005_source_ingestion_idem"
branch_labels = None
depends_on = None

TABLE = "agent_task_queue_records"
UNIQUE_INDEX = "uq_agent_task_queue_records_idem"
MYSQL = {"mysql_engine": "InnoDB", "mysql_charset": "utf8mb4"}


def _common_columns() -> list:
    """Governance + audit columns carried by every record (mirrors 001_initial)."""
    return [
        sa.Column("owner_id", sa.String(128)),
        sa.Column("authorization_scope", sa.String(48)),
        sa.Column("review_status", sa.String(32), nullable=False, server_default="draft"),
        sa.Column("lifecycle_status", sa.String(32), nullable=False, server_default="draft"),
        sa.Column("created_at", sa.DateTime(), server_default=sa.func.now(), nullable=False),
        sa.Column("created_by", sa.String(128)),
        sa.Column("updated_at", sa.DateTime(), server_default=sa.func.now(), nullable=False),
        sa.Column("updated_by", sa.String(128)),
        sa.Column("agent_run_id", sa.String(64)),
        sa.Column("details_json", sa.JSON()),
    ]


def upgrade() -> None:
    op.create_table(
        TABLE,
        sa.Column("id", sa.String(64), primary_key=True),
        sa.Column("client_id", sa.String(64)),
        sa.Column("engagement_id", sa.String(64)),
        sa.Column("agent_name", sa.String(128), nullable=False),
        sa.Column("task_type", sa.String(64)),
        sa.Column("requested_action", sa.String(64)),
        sa.Column("source_ingestion_record_id", sa.String(64)),
        sa.Column("readiness_state", sa.String(48)),
        sa.Column("output_status", sa.String(32), nullable=False, server_default="draft"),
        sa.Column("execution_status", sa.String(32), nullable=False, server_default="not_executed"),
        sa.Column("authoritative", sa.Boolean(), nullable=False, server_default=sa.text("0")),
        sa.Column("client_facing_approved", sa.Boolean(), nullable=False, server_default=sa.text("0")),
        sa.Column("capsule_candidate_ready", sa.Boolean(), nullable=False, server_default=sa.text("0")),
        sa.Column("execution_allowed", sa.Boolean(), nullable=False, server_default=sa.text("0")),
        sa.Column("llm_execution_allowed", sa.Boolean(), nullable=False, server_default=sa.text("0")),
        sa.Column("agentnet_context_allowed", sa.Boolean(), nullable=False, server_default=sa.text("0")),
        sa.Column("resolver_context_allowed", sa.Boolean(), nullable=False, server_default=sa.text("0")),
        sa.Column("network_allowed", sa.Boolean(), nullable=False, server_default=sa.text("0")),
        sa.Column("requires_human_review", sa.Boolean(), nullable=False, server_default=sa.text("1")),
        sa.Column("idempotency_key", sa.String(128)),
        sa.Column("payload_fingerprint", sa.String(64)),
        *_common_columns(),
        **MYSQL,
    )
    op.create_index(f"ix_{TABLE}_client_id", TABLE, ["client_id"])
    op.create_index(f"ix_{TABLE}_engagement_id", TABLE, ["engagement_id"])
    op.create_index(f"ix_{TABLE}_agent_name", TABLE, ["agent_name"])
    op.create_index(f"ix_{TABLE}_source_ingestion_record_id", TABLE, ["source_ingestion_record_id"])
    op.create_index(f"ix_{TABLE}_readiness_state", TABLE, ["readiness_state"])
    op.create_index(f"ix_{TABLE}_output_status", TABLE, ["output_status"])
    op.create_index(f"ix_{TABLE}_execution_status", TABLE, ["execution_status"])
    op.create_index(f"ix_{TABLE}_idempotency_key", TABLE, ["idempotency_key"])
    # Governance/audit indexes carried by every table (mirrors 001_initial).
    for col in ("owner_id", "authorization_scope", "review_status", "lifecycle_status",
                "agent_run_id"):
        op.create_index(f"ix_{TABLE}_{col}", TABLE, [col])
    # DB-enforced idempotency boundary (identity context + key). Unique index is portable
    # across MySQL and the local SQLite test database.
    op.create_index(
        UNIQUE_INDEX,
        TABLE,
        ["owner_id", "client_id", "engagement_id", "idempotency_key"],
        unique=True,
    )


def downgrade() -> None:
    op.drop_index(UNIQUE_INDEX, table_name=TABLE)
    for col in ("agent_run_id", "lifecycle_status", "review_status", "authorization_scope",
                "owner_id"):
        op.drop_index(f"ix_{TABLE}_{col}", table_name=TABLE)
    op.drop_index(f"ix_{TABLE}_idempotency_key", table_name=TABLE)
    op.drop_index(f"ix_{TABLE}_execution_status", table_name=TABLE)
    op.drop_index(f"ix_{TABLE}_output_status", table_name=TABLE)
    op.drop_index(f"ix_{TABLE}_readiness_state", table_name=TABLE)
    op.drop_index(f"ix_{TABLE}_source_ingestion_record_id", table_name=TABLE)
    op.drop_index(f"ix_{TABLE}_agent_name", table_name=TABLE)
    op.drop_index(f"ix_{TABLE}_engagement_id", table_name=TABLE)
    op.drop_index(f"ix_{TABLE}_client_id", table_name=TABLE)
    op.drop_table(TABLE)
