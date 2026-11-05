"""Phase 226: Lead review of an observation (schema only, no data).

Creates one new table and nothing else: no existing table or column is altered.

- ``observation_lead_reviews``: the engagement's Lead Consultant's decision on one consultant
  observation (``discovery_observations``) of the same engagement, exactly as it was worded when
  reviewed: approve it for internal reliance at a stated reliability, or decline. Insert-only.
  Reviews of one observation are numbered 1, 2, 3 (``uq_observation_lead_reviews_number``); the
  highest is current and the earlier ones stay as history. The observation is
  never changed. The review creates no finding, recommendation or report content: it is one input to
  a derived recommendation-eligibility decision.

There are **no INSERTs, no seed data, and no data of any kind**. See
docs/PHASE226_OBSERVATION_LEAD_REVIEW.md.

Production note: the runtime role needs SELECT and INSERT only (already granted schema-wide). The
table is append-only, so it needs **no UPDATE grant** and the Phase 50 gate fails on one.

Revision ID: 026_observation_lead_reviews
Revises: 025_observation_task_origins
Create Date: (static; no timestamp committed)
"""

from __future__ import annotations

import sqlalchemy as sa
from alembic import op

# revision identifiers, used by Alembic.
revision = "026_observation_lead_reviews"
down_revision = "025_observation_task_origins"
branch_labels = None
depends_on = None

#: Mirrors ``peak.db.base.GOVERNED_COLLATION``; kept as a literal so the migration never imports
#: application code. Applied only on dialects that can express a MySQL collation.
GOVERNED_COLLATION = "utf8mb4_bin"
_COLLATING_DIALECTS = {"mysql", "mariadb"}

_TABLE = "observation_lead_reviews"


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
        sa.Column("reviewer_consultant_id", _governed(64), nullable=False),
        sa.Column("decision", sa.String(24), nullable=False),
        sa.Column("reliability", sa.String(8), nullable=True),
        sa.Column("reviewed_statement", sa.Text(), nullable=False),
        sa.Column("review_number", sa.Integer(), nullable=False),
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
        sa.CheckConstraint("decision IN ('approve_internal', 'decline')",
                           name="ck_observation_lead_reviews_decision"),
        sa.CheckConstraint("(decision = 'approve_internal' AND reliability IN ('low', 'medium', "
                           "'high')) OR (decision = 'decline' AND reliability IS NULL)",
                           name="ck_observation_lead_reviews_reliability"),
        sa.CheckConstraint("review_number >= 1", name="ck_observation_lead_reviews_number"),
        sa.UniqueConstraint("observation_id", "review_number",
                            name="uq_observation_lead_reviews_number"),
        mysql_engine="InnoDB", mysql_charset="utf8mb4",
    )
    for column in ("owner_id", "authorization_scope", "review_status", "lifecycle_status",
                   "agent_run_id", "client_id", "engagement_id", "observation_id"):
        op.create_index(f"ix_{_TABLE}_{column}", _TABLE, [column])


def downgrade() -> None:
    op.drop_table(_TABLE)
