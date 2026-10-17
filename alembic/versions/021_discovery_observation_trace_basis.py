"""Phase 216: observation trace and basis; supplemental-question provenance (schema only, no data).

Adds nullable columns to ``discovery_observations`` and ``discovery_questions`` and nothing else: no
table is created or dropped, no existing column is altered, and no artifact table is touched.

On ``discovery_observations``:

- ``question_id``: the discovery question that prompted the observation (a governed identifier
  referencing ``discovery_questions.id``). Optional, so an observation can still stand on its own.
- ``basis``: what the observation rests on: ``testimony``, ``observed``, ``document``,
  ``measured`` or ``inferred``. Enforced by ``ck_discovery_observations_basis`` on MySQL (SQLite
  cannot add a constraint to an existing table; the service enforces it everywhere).

On ``discovery_questions`` (field-use provenance of a consultant-added, supplemental question;
canonical seeded questions leave them null):
- ``engagement_id``: the engagement the question was added in; it is asked only there.
- ``added_by_consultant_id``: who added it.
- ``rationale``: why the consultant asked it.
- ``domain``, ``finding_classes``: optional tags (finding-class codes as a JSON list).

None of these columns makes discovery material evidence (Contract C4), and none makes a question
canonical (only ``seed_key`` marks that). They are written only through the workspace service's
existing observation and question actions. There are **no INSERTs, no seed data, and no data of any
kind**. Existing rows keep null in every new column. See
docs/PHASE216_DISCOVERY_INSTRUMENT.md.

Revision ID: 021_discovery_observation_trace_basis
Revises: 020_internal_test_engagement_retirement
Create Date: (static; no timestamp committed)
"""

from __future__ import annotations

import sqlalchemy as sa
from alembic import op

# revision identifiers, used by Alembic.
revision = "021_discovery_observation_trace_basis"
down_revision = "020_internal_test_engagement_retirement"
branch_labels = None
depends_on = None

#: Mirrors ``peak.db.base.GOVERNED_COLLATION``; kept as a literal so the migration never imports
#: application code. Applied only on dialects that can express a MySQL collation.
GOVERNED_COLLATION = "utf8mb4_bin"
_COLLATING_DIALECTS = {"mysql", "mariadb"}

#: Mirrors ``peak.db.models.DISCOVERY_OBSERVATION_BASES``, as a literal for the same reason.
_BASIS_CHECK = ("basis IS NULL OR basis IN ('testimony', 'observed', 'document', 'measured', "
                "'inferred')")


def _governed(length: int):
    """A governed string on MySQL, plain VARCHAR elsewhere."""
    if op.get_bind().dialect.name in _COLLATING_DIALECTS:
        return sa.String(length, collation=GOVERNED_COLLATION)
    return sa.String(length)


def _alters_constraints() -> bool:
    """SQLite cannot add or drop a constraint on an existing table, so the basis CHECK is created
    only where ``ALTER TABLE ... ADD CONSTRAINT`` exists (MySQL in production). The workspace
    service enforces the same vocabulary on every database, and a database built from the models
    carries the constraint directly."""
    return op.get_bind().dialect.name != "sqlite"


def upgrade() -> None:
    op.add_column("discovery_observations",
                  sa.Column("question_id", _governed(64), nullable=True))
    op.add_column("discovery_observations", sa.Column("basis", sa.String(16), nullable=True))
    op.create_index("ix_discovery_observations_question_id", "discovery_observations",
                    ["question_id"])
    if _alters_constraints():
        op.create_check_constraint("ck_discovery_observations_basis", "discovery_observations",
                                   _BASIS_CHECK)
    op.add_column("discovery_questions",
                  sa.Column("engagement_id", _governed(64), nullable=True))
    op.add_column("discovery_questions",
                  sa.Column("added_by_consultant_id", _governed(64), nullable=True))
    op.add_column("discovery_questions", sa.Column("rationale", sa.Text(), nullable=True))
    op.add_column("discovery_questions", sa.Column("domain", sa.String(128), nullable=True))
    op.add_column("discovery_questions", sa.Column("finding_classes", sa.JSON(), nullable=True))
    op.create_index("ix_discovery_questions_engagement_id", "discovery_questions",
                    ["engagement_id"])


def downgrade() -> None:
    op.drop_index("ix_discovery_questions_engagement_id", table_name="discovery_questions")
    for column in ("finding_classes", "domain", "rationale", "added_by_consultant_id",
                   "engagement_id"):
        op.drop_column("discovery_questions", column)
    if _alters_constraints():
        op.drop_constraint("ck_discovery_observations_basis", "discovery_observations",
                           type_="check")
    op.drop_index("ix_discovery_observations_question_id", table_name="discovery_observations")
    op.drop_column("discovery_observations", "basis")
    op.drop_column("discovery_observations", "question_id")
