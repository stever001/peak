"""Phase 22: review_records decision/idempotency columns (schema only, no data).

Adds the narrow columns and DB-enforced uniqueness the Phase 22 controlled review writer
needs, and nothing else — mirroring the Phase 20/21 changes:

- ``decision`` — the recorded review decision (governance-relevant, a real column);
- ``subject_record_type`` — the type of the reviewed target (whose id is ``target_id``);
- ``authoritative`` — internal-reliance flag (true only for approve_internal);
- ``output_status`` — governance-relevant review-gate status (a real column, not JSON);
- ``idempotency_key`` — the caller-supplied key that backs replay safety;
- ``payload_fingerprint`` — a deterministic hash of the write payload/identity, used to tell
  an exact idempotent replay apart from a conflicting reuse of the same key;
- ``uq_review_records_idem`` — a UNIQUE index over
  ``(owner_id, client_id, engagement_id, idempotency_key)`` so a repeated authorized write
  cannot create a duplicate row, and a key cannot collide across owner/client/engagement.

Non-destructive and additive: no table is dropped, no column is removed, no row is touched.
There are **no INSERTs, no seed data, and no data of any kind**. See
docs/REVIEW_CONTROLLED_WRITER.md and docs/REVIEW_IDEMPOTENCY_POLICY.md.

Revision ID: 004_review_idem
Revises: 003_evidence_idem
Create Date: (static; no timestamp committed)
"""

from __future__ import annotations

import sqlalchemy as sa
from alembic import op

# revision identifiers, used by Alembic.
revision = "004_review_idem"
down_revision = "003_evidence_idem"
branch_labels = None
depends_on = None

TABLE = "review_records"
UNIQUE_INDEX = "uq_review_records_idem"


def upgrade() -> None:
    op.add_column(TABLE, sa.Column("decision", sa.String(48)))
    op.add_column(TABLE, sa.Column("subject_record_type", sa.String(48)))
    op.add_column(
        TABLE,
        sa.Column("authoritative", sa.Boolean(), nullable=False, server_default=sa.text("0")),
    )
    op.add_column(
        TABLE,
        sa.Column("output_status", sa.String(32), nullable=False, server_default="draft"),
    )
    op.add_column(TABLE, sa.Column("idempotency_key", sa.String(128)))
    op.add_column(TABLE, sa.Column("payload_fingerprint", sa.String(64)))
    op.create_index(f"ix_{TABLE}_decision", TABLE, ["decision"])
    op.create_index(f"ix_{TABLE}_output_status", TABLE, ["output_status"])
    op.create_index(f"ix_{TABLE}_idempotency_key", TABLE, ["idempotency_key"])
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
    op.drop_index(f"ix_{TABLE}_idempotency_key", table_name=TABLE)
    op.drop_index(f"ix_{TABLE}_output_status", table_name=TABLE)
    op.drop_index(f"ix_{TABLE}_decision", table_name=TABLE)
    op.drop_column(TABLE, "payload_fingerprint")
    op.drop_column(TABLE, "idempotency_key")
    op.drop_column(TABLE, "output_status")
    op.drop_column(TABLE, "authoritative")
    op.drop_column(TABLE, "subject_record_type")
    op.drop_column(TABLE, "decision")
