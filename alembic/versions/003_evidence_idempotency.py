"""Phase 21: evidence_references idempotency + review-gate columns (schema only, no data).

Adds the narrow columns and DB-enforced uniqueness the Phase 21 controlled evidence writer
needs, and nothing else — mirroring the Phase 20 `agent_run_records` change:

- ``output_status`` — governance-relevant review-gate status (a real column, not JSON);
- ``idempotency_key`` — the caller-supplied key that backs replay safety;
- ``payload_fingerprint`` — a deterministic hash of the write payload/identity, used to tell
  an exact idempotent replay apart from a conflicting reuse of the same key;
- ``uq_evidence_references_idem`` — a UNIQUE index over
  ``(owner_id, client_id, engagement_id, idempotency_key)`` so a repeated authorized write
  cannot create a duplicate row, and a key cannot collide across owner/client/engagement.

Non-destructive and additive: no table is dropped, no column is removed, no row is touched.
There are **no INSERTs, no seed data, and no data of any kind**. See
docs/EVIDENCE_CONTROLLED_WRITER.md and docs/EVIDENCE_IDEMPOTENCY_POLICY.md.

Revision ID: 003_evidence_idem
Revises: 002_agent_run_idem
Create Date: (static; no timestamp committed)
"""

from __future__ import annotations

import sqlalchemy as sa
from alembic import op

# revision identifiers, used by Alembic.
revision = "003_evidence_idem"
down_revision = "002_agent_run_idem"
branch_labels = None
depends_on = None

TABLE = "evidence_references"
UNIQUE_INDEX = "uq_evidence_references_idem"


def upgrade() -> None:
    op.add_column(
        TABLE,
        sa.Column("output_status", sa.String(32), nullable=False, server_default="draft"),
    )
    op.add_column(TABLE, sa.Column("idempotency_key", sa.String(128)))
    op.add_column(TABLE, sa.Column("payload_fingerprint", sa.String(64)))
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
    op.drop_column(TABLE, "payload_fingerprint")
    op.drop_column(TABLE, "idempotency_key")
    op.drop_column(TABLE, "output_status")
