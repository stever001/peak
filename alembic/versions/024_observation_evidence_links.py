"""Phase 221: evidence referencing (schema only, no data).

Creates one new table and nothing else: no existing table or column is altered.

- ``observation_evidence_links``: a consultant's link from one of their observations
  (``discovery_observations``) to one captured item (``phase_task_evidence``) of the same
  engagement. Insert-only; a pair is linked at most once (``uq_observation_evidence_links_pair``).
  A link names the exact capture chosen and is never moved to a later replacement. It creates no
  finding, recommendation or governed assessment evidence.

There are **no INSERTs, no seed data, and no data of any kind**. See
docs/PHASE221_EVIDENCE_REFERENCING.md.

Production note: the runtime role needs SELECT and INSERT only (already granted schema-wide). The
table is append-only, so it needs **no UPDATE grant** and the Phase 50 gate fails on one.

Revision ID: 024_observation_evidence_links
Revises: 023_phase_task_evidence
Create Date: (static; no timestamp committed)
"""

from __future__ import annotations

import sqlalchemy as sa
from alembic import op

# revision identifiers, used by Alembic.
revision = "024_observation_evidence_links"
down_revision = "023_phase_task_evidence"
branch_labels = None
depends_on = None

#: Mirrors ``peak.db.base.GOVERNED_COLLATION``; kept as a literal so the migration never imports
#: application code. Applied only on dialects that can express a MySQL collation.
GOVERNED_COLLATION = "utf8mb4_bin"
_COLLATING_DIALECTS = {"mysql", "mariadb"}

_TABLE = "observation_evidence_links"


def _governed(length: int):
    """A governed string on MySQL, plain VARCHAR elsewhere."""
    if op.get_bind().dialect.name in _COLLATING_DIALECTS:
        return sa.String(length, collation=GOVERNED_COLLATION)
    return sa.String(length)


def upgrade() -> None:
    op.create_table(
        _TABLE,
        sa.Column("id", _governed(64), primary_key=True),
        sa.Column("client_id", _governed(64), nullable=False),
        sa.Column("engagement_id", _governed(64), nullable=False),
        sa.Column("observation_id", _governed(64), nullable=False),
        sa.Column("evidence_id", _governed(64), nullable=False),
        sa.Column("linked_by_consultant_id", _governed(64), nullable=False),
        # GovernanceMixin and AuditMixin columns, as every governed table carries them.
        sa.Column("owner_id", _governed(128), nullable=True),
        sa.Column("authorization_scope", _governed(48), nullable=True),
        sa.Column("review_status", sa.String(32), nullable=False, server_default="draft"),
        sa.Column("lifecycle_status", sa.String(32), nullable=False, server_default="draft"),
        sa.Column("created_at", sa.DateTime(), server_default=sa.func.now(), nullable=False),
        sa.Column("created_by", _governed(128), nullable=True),
        sa.Column("updated_at", sa.DateTime(), server_default=sa.func.now(), nullable=False),
        sa.Column("updated_by", _governed(128), nullable=True),
        sa.Column("agent_run_id", _governed(64), nullable=True),
        sa.Column("details_json", sa.JSON(), nullable=True),
        sa.UniqueConstraint("observation_id", "evidence_id",
                            name="uq_observation_evidence_links_pair"),
        mysql_engine="InnoDB", mysql_charset="utf8mb4",
    )
    for column in ("owner_id", "authorization_scope", "review_status", "lifecycle_status",
                   "agent_run_id", "client_id", "engagement_id", "observation_id", "evidence_id"):
        op.create_index(f"ix_{_TABLE}_{column}", _TABLE, [column])


def downgrade() -> None:
    op.drop_table(_TABLE)
