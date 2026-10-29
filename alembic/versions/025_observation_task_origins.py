"""Phase 222: guided work observations (schema only, no data).

Creates one new table and nothing else: no existing table or column is altered.

- ``observation_task_origins``: the phase task (``phase_tasks``) a consultant was doing when they
  recorded an observation (``discovery_observations``) of the same engagement. Insert-only; an
  observation has at most one origin (``uq_observation_task_origins_observation``). The observation
  stays an ordinary consultant observation; the origin is provenance only and creates no finding,
  recommendation, task status or readiness change.

There are **no INSERTs, no seed data, and no data of any kind**. See
docs/PHASE222_GUIDED_WORK_OBSERVATIONS.md.

Production note: the runtime role needs SELECT and INSERT only (already granted schema-wide). The
table is append-only, so it needs **no UPDATE grant** and the Phase 50 gate fails on one.

Revision ID: 025_observation_task_origins
Revises: 024_observation_evidence_links
Create Date: (static; no timestamp committed)
"""

from __future__ import annotations

import sqlalchemy as sa
from alembic import op

# revision identifiers, used by Alembic.
revision = "025_observation_task_origins"
down_revision = "024_observation_evidence_links"
branch_labels = None
depends_on = None

#: Mirrors ``peak.db.base.GOVERNED_COLLATION``; kept as a literal so the migration never imports
#: application code. Applied only on dialects that can express a MySQL collation.
GOVERNED_COLLATION = "utf8mb4_bin"
_COLLATING_DIALECTS = {"mysql", "mariadb"}

_TABLE = "observation_task_origins"


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
        sa.Column("phase_id", _governed(64), nullable=False),
        sa.Column("task_id", _governed(64), nullable=False),
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
        sa.UniqueConstraint("observation_id", name="uq_observation_task_origins_observation"),
        mysql_engine="InnoDB", mysql_charset="utf8mb4",
    )
    for column in ("owner_id", "authorization_scope", "review_status", "lifecycle_status",
                   "agent_run_id", "client_id", "engagement_id", "observation_id", "phase_id",
                   "task_id"):
        op.create_index(f"ix_{_TABLE}_{column}", _TABLE, [column])


def downgrade() -> None:
    op.drop_table(_TABLE)
