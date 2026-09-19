"""Phase 204: consultant discovery / interview workflow (schema only, no data).

Adds:

- ``engagements.north_star`` and ``engagements.north_star_context`` (nullable text);
- ``discovery_questions``: the editable question pool (application configuration, not client data;
  deactivated rather than deleted; optional one-question ``equals`` / ``not_equals`` branch;
  ``seed_key`` unique so the explicit initialization tool is idempotent);
- ``discovery_sessions``: interviews, with an interviewee name/title snapshot and
  ``in_progress`` / ``completed`` status;
- ``discovery_answers``: one per (session, question), with the prompt snapshotted;
- ``discovery_observations``: consultant observations with low-hanging-fruit, effort and value.

Sessions, answers and observations carry the governance/audit columns of every governed record.
Governed identifiers are pinned to the governed collation at creation. Written only by the
consultant workspace service (``peak.persistence.allowlist.WORKSPACE_WRITE_COLUMNS``).

Additive. There are **no INSERTs, no seed data, and no data of any kind**: the initial question
pool is created only by the explicit ``tools/init_discovery_questions.py``. See
docs/PHASE204_DISCOVERY_INTERVIEW_WORKFLOW.md.

Revision ID: 017_discovery_workflow
Revises: 016_client_engagement_workspace_fields
Create Date: (static; no timestamp committed)
"""

from __future__ import annotations

import sqlalchemy as sa
from alembic import op

# revision identifiers, used by Alembic.
revision = "017_discovery_workflow"
down_revision = "016_client_engagement_workspace_fields"
branch_labels = None
depends_on = None

#: Mirrors ``peak.db.base.GOVERNED_COLLATION``; kept as a literal so the migration never imports
#: application code. Applied only on dialects that can express a MySQL collation.
GOVERNED_COLLATION = "utf8mb4_bin"
_COLLATING_DIALECTS = {"mysql", "mariadb"}
TABLE_OPTIONS = {"mysql_engine": "InnoDB", "mysql_charset": "utf8mb4"}

#: Tables carrying the governance/audit columns, and their indexed columns.
GOVERNED_TABLE_INDEXES = {
    "discovery_sessions": ("client_id", "engagement_id"),
    "discovery_answers": ("client_id", "engagement_id", "session_id", "question_id"),
    "discovery_observations": ("client_id", "engagement_id", "session_id"),
}
GOVERNANCE_INDEXED = ("owner_id", "authorization_scope", "review_status", "lifecycle_status",
                      "agent_run_id")


def _governed(length: int):
    """A governed string on MySQL, plain VARCHAR elsewhere."""
    if op.get_bind().dialect.name in _COLLATING_DIALECTS:
        return sa.String(length, collation=GOVERNED_COLLATION)
    return sa.String(length)


def _governance_columns():
    return [
        sa.Column("owner_id", _governed(128)),
        sa.Column("authorization_scope", _governed(48)),
        sa.Column("review_status", sa.String(32), nullable=False, server_default="draft"),
        sa.Column("lifecycle_status", sa.String(32), nullable=False, server_default="draft"),
        sa.Column("created_at", sa.DateTime(), server_default=sa.func.now(), nullable=False),
        sa.Column("created_by", _governed(128)),
        sa.Column("updated_at", sa.DateTime(), server_default=sa.func.now(), nullable=False),
        sa.Column("updated_by", _governed(128)),
        sa.Column("agent_run_id", _governed(64)),
        sa.Column("details_json", sa.JSON()),
    ]


def upgrade() -> None:
    op.add_column("engagements", sa.Column("north_star", sa.Text(), nullable=True))
    op.add_column("engagements", sa.Column("north_star_context", sa.Text(), nullable=True))

    op.create_table(
        "discovery_questions",
        sa.Column("id", _governed(64), primary_key=True),
        sa.Column("prompt", sa.String(1000), nullable=False),
        sa.Column("category", sa.String(64), nullable=False),
        sa.Column("answer_type", sa.String(16), nullable=False),
        sa.Column("choices", sa.JSON()),
        sa.Column("display_order", sa.Integer(), nullable=False),
        sa.Column("active", sa.Boolean(), nullable=False, server_default=sa.true()),
        sa.Column("branch_question_id", _governed(64)),
        sa.Column("branch_operator", sa.String(16)),
        sa.Column("branch_value", sa.String(255)),
        sa.Column("seed_key", _governed(64)),
        sa.Column("created_at", sa.DateTime(), server_default=sa.func.now(), nullable=False),
        sa.Column("updated_at", sa.DateTime(), server_default=sa.func.now(), nullable=False),
        sa.UniqueConstraint("seed_key", name="uq_discovery_questions_seed_key"),
        sa.CheckConstraint(
            "answer_type IN ('short_text', 'long_text', 'yes_no', 'single_choice')",
            name="ck_discovery_questions_answer_type"),
        sa.CheckConstraint(
            "branch_operator IS NULL OR branch_operator IN ('equals', 'not_equals')",
            name="ck_discovery_questions_branch_operator"),
        **TABLE_OPTIONS,
    )
    op.create_index("ix_discovery_questions_category", "discovery_questions", ["category"])

    op.create_table(
        "discovery_sessions",
        sa.Column("id", _governed(64), primary_key=True),
        sa.Column("client_id", _governed(64), nullable=False),
        sa.Column("engagement_id", _governed(64), nullable=False),
        sa.Column("interviewee_name", sa.String(255), nullable=False),
        sa.Column("interviewee_title", sa.String(255)),
        sa.Column("notes", sa.Text()),
        sa.Column("status", sa.String(16), nullable=False),
        sa.Column("conducted_by_consultant_id", _governed(64), nullable=False),
        sa.Column("started_at", sa.DateTime(), nullable=False),
        sa.Column("completed_at", sa.DateTime()),
        *_governance_columns(),
        sa.CheckConstraint("status IN ('in_progress', 'completed')",
                           name="ck_discovery_sessions_status"),
        **TABLE_OPTIONS,
    )

    op.create_table(
        "discovery_answers",
        sa.Column("id", _governed(64), primary_key=True),
        sa.Column("client_id", _governed(64), nullable=False),
        sa.Column("engagement_id", _governed(64), nullable=False),
        sa.Column("session_id", _governed(64), nullable=False),
        sa.Column("question_id", _governed(64), nullable=False),
        sa.Column("question_prompt_snapshot", sa.String(1000), nullable=False),
        sa.Column("answer_text", sa.Text()),
        *_governance_columns(),
        sa.UniqueConstraint("session_id", "question_id",
                            name="uq_discovery_answers_session_question"),
        **TABLE_OPTIONS,
    )

    op.create_table(
        "discovery_observations",
        sa.Column("id", _governed(64), primary_key=True),
        sa.Column("client_id", _governed(64), nullable=False),
        sa.Column("engagement_id", _governed(64), nullable=False),
        sa.Column("session_id", _governed(64)),
        sa.Column("category", sa.String(64)),
        sa.Column("observation_text", sa.Text(), nullable=False),
        sa.Column("low_hanging_fruit", sa.Boolean(), nullable=False, server_default=sa.false()),
        sa.Column("estimated_effort", sa.String(8)),
        sa.Column("estimated_value", sa.String(8)),
        sa.Column("recorded_by_consultant_id", _governed(64), nullable=False),
        *_governance_columns(),
        sa.CheckConstraint("estimated_effort IS NULL OR estimated_effort IN ('low', 'medium', 'high')",
                           name="ck_discovery_observations_effort"),
        sa.CheckConstraint("estimated_value IS NULL OR estimated_value IN ('low', 'medium', 'high')",
                           name="ck_discovery_observations_value"),
        **TABLE_OPTIONS,
    )

    for table, columns in GOVERNED_TABLE_INDEXES.items():
        for column in columns + GOVERNANCE_INDEXED:
            op.create_index(f"ix_{table}_{column}", table, [column])


def downgrade() -> None:
    op.drop_table("discovery_observations")
    op.drop_table("discovery_answers")
    op.drop_table("discovery_sessions")
    op.drop_table("discovery_questions")
    op.drop_column("engagements", "north_star_context")
    op.drop_column("engagements", "north_star")
