"""Phase 215: logical deletion (retirement) of internal_test engagements (schema only, no data).

Adds two nullable columns to ``engagements`` and nothing else: no table is created, dropped or
rewritten, no existing column is altered, and no artifact table is touched.

- ``deleted_at``: when an Admin deleted this internal_test engagement from active use.
- ``deleted_by_consultant_id``: the Admin who did it (a governed identifier referencing
  ``consultants.id``).

Deletion is logical: the engagement row and every discovery and artifact record under it are kept,
immutable and auditable. The columns are written only by the workspace service's
``retire_internal_test_engagement`` action, and only for an internal_test engagement. There are
**no INSERTs, no seed data, and no data of any kind**. See docs/PHASE215_INTERNAL_TEST_ENGAGEMENTS.md.

Revision ID: 020_internal_test_engagement_retirement
Revises: 019_artifact_approval_release
Create Date: (static; no timestamp committed)
"""

from __future__ import annotations

import sqlalchemy as sa
from alembic import op

# revision identifiers, used by Alembic.
revision = "020_internal_test_engagement_retirement"
down_revision = "019_artifact_approval_release"
branch_labels = None
depends_on = None

#: Mirrors ``peak.db.base.GOVERNED_COLLATION``; kept as a literal so the migration never imports
#: application code. Applied only on dialects that can express a MySQL collation.
GOVERNED_COLLATION = "utf8mb4_bin"
_COLLATING_DIALECTS = {"mysql", "mariadb"}


def _governed(length: int):
    """A governed string on MySQL, plain VARCHAR elsewhere."""
    if op.get_bind().dialect.name in _COLLATING_DIALECTS:
        return sa.String(length, collation=GOVERNED_COLLATION)
    return sa.String(length)


def upgrade() -> None:
    op.add_column("engagements", sa.Column("deleted_at", sa.DateTime(), nullable=True))
    op.add_column("engagements",
                  sa.Column("deleted_by_consultant_id", _governed(64), nullable=True))


def downgrade() -> None:
    op.drop_column("engagements", "deleted_by_consultant_id")
    op.drop_column("engagements", "deleted_at")
