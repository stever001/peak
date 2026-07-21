"""Phase 34: intake_note_records table (schema only, no data).

Creates the new ``intake_note_records`` table for the Phase 34 controlled intake-note writer — the
eighth narrow live DB writer and the first table designed to hold **authorized operational note
prose** (``note_text``). Intake notes are first-class operational records (client interviews,
consultant observations, warehouse walkaround notes, discovery calls, source-intake comments,
controlled packet-ingestion outputs, consultant-authored notes). Real note text is acceptable
**only in the managed DB**, never in Git / fixtures / examples / sample packets / logs / receipts /
test data.

The table carries the universal governance axes + audit fields (as every table does), the
non-final posture columns (all defaulting to the not-approved / not-allowed / needs-review
posture), and the controlled-writer idempotency columns:

- ``idempotency_key`` — the caller-supplied key that backs replay safety;
- ``payload_fingerprint`` — a deterministic hash of the write payload/identity (the note body is
  incorporated as a hash, not re-stored), used to tell an exact idempotent replay apart from a
  conflicting reuse of the same key;
- ``uq_intake_note_records_idem`` — a UNIQUE index over
  ``(owner_id, client_id, engagement_id, idempotency_key)`` so a repeated authorized write cannot
  create a duplicate row, and a key cannot collide across owner/client/engagement.

This migration is schema only. **SQLite (used by the fast local structural smoke path) is not the
production-readiness proof path** — managed MySQL test/staging validation is required before
treating DB-backed functionality as production-ready (see
docs/PRODUCTION_PARITY_DB_VALIDATION.md and docs/MANAGED_MYSQL_PERSISTENCE_RUBRIC.md).

Additive and non-destructive: it creates exactly one new table and its indexes/constraint and
touches nothing else. There are **no INSERTs, no seed data, and no data of any kind**. The full
downgrade drops only this new table (and its indexes/constraint). See
docs/INTAKE_NOTE_CONTROLLED_WRITER.md and docs/INTAKE_NOTE_IDEMPOTENCY_POLICY.md.

Revision ID: 009_intake_note_records
Revises: 008_internal_reviewer_decision_records
Create Date: (static; no timestamp committed)
"""

from __future__ import annotations

import sqlalchemy as sa
from alembic import op

# revision identifiers, used by Alembic.
revision = "009_intake_note_records"
down_revision = "008_internal_reviewer_decision_records"
branch_labels = None
depends_on = None

TABLE = "intake_note_records"
UNIQUE_INDEX = "uq_intake_note_records_idem"
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
        sa.Column("note_type", sa.String(48)),
        sa.Column("note_source", sa.String(48)),
        sa.Column("note_text", sa.Text()),
        sa.Column("note_summary", sa.String(500)),
        sa.Column("captured_by", sa.String(128)),
        sa.Column("captured_role", sa.String(64)),
        sa.Column("source_ref", sa.String(128)),
        sa.Column("source_ingestion_record_id", sa.String(64)),
        sa.Column("related_evidence_reference_id", sa.String(64)),
        sa.Column("related_review_bundle_record_id", sa.String(64)),
        sa.Column("client_facing_approved", sa.Boolean(), nullable=False, server_default=sa.text("0")),
        sa.Column("financial_verified", sa.Boolean(), nullable=False, server_default=sa.text("0")),
        sa.Column("capsule_candidate_ready", sa.Boolean(), nullable=False, server_default=sa.text("0")),
        sa.Column("publication_allowed", sa.Boolean(), nullable=False, server_default=sa.text("0")),
        sa.Column("execution_allowed", sa.Boolean(), nullable=False, server_default=sa.text("0")),
        sa.Column("requires_human_review", sa.Boolean(), nullable=False, server_default=sa.text("1")),
        sa.Column("idempotency_key", sa.String(128)),
        sa.Column("payload_fingerprint", sa.String(64)),
        *_common_columns(),
        **MYSQL,
    )
    op.create_index(f"ix_{TABLE}_client_id", TABLE, ["client_id"])
    op.create_index(f"ix_{TABLE}_engagement_id", TABLE, ["engagement_id"])
    op.create_index(f"ix_{TABLE}_note_type", TABLE, ["note_type"])
    op.create_index(f"ix_{TABLE}_note_source", TABLE, ["note_source"])
    op.create_index(f"ix_{TABLE}_source_ingestion_record_id", TABLE, ["source_ingestion_record_id"])
    op.create_index(f"ix_{TABLE}_related_evidence_reference_id", TABLE,
                    ["related_evidence_reference_id"])
    op.create_index(f"ix_{TABLE}_related_review_bundle_record_id", TABLE,
                    ["related_review_bundle_record_id"])
    op.create_index(f"ix_{TABLE}_idempotency_key", TABLE, ["idempotency_key"])
    # Governance/audit indexes carried by every table (mirrors 001_initial).
    for col in ("owner_id", "authorization_scope", "review_status", "lifecycle_status",
                "agent_run_id"):
        op.create_index(f"ix_{TABLE}_{col}", TABLE, [col])
    # DB-enforced idempotency boundary (identity context + key). Unique index is portable
    # across MySQL and the local SQLite structural-smoke database.
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
    op.drop_index(f"ix_{TABLE}_related_review_bundle_record_id", table_name=TABLE)
    op.drop_index(f"ix_{TABLE}_related_evidence_reference_id", table_name=TABLE)
    op.drop_index(f"ix_{TABLE}_source_ingestion_record_id", table_name=TABLE)
    op.drop_index(f"ix_{TABLE}_note_source", table_name=TABLE)
    op.drop_index(f"ix_{TABLE}_note_type", table_name=TABLE)
    op.drop_index(f"ix_{TABLE}_engagement_id", table_name=TABLE)
    op.drop_index(f"ix_{TABLE}_client_id", table_name=TABLE)
    op.drop_table(TABLE)
