"""Phase 56: engagement classification columns (schema only, no data).

Adds the narrow columns the Phase 56 classification support needs, and nothing else:

- ``engagement_category`` — ``real_client`` / ``internal_test``. A **governed** (byte-exact)
  string, because a case variant must never read as the same category. Defaults to
  ``real_client`` so an unclassified row can never be mistaken for a hidden internal test record;
- ``real_client_data`` — whether the engagement may hold real client data (default ``true``);
- ``client_accessible`` — whether the engagement is reachable by a real client (default ``true``,
  matching the ``real_client`` default category);
- ``capsule_publication_authorized`` — whether capsules from this engagement may be published
  (default ``false``; publication is never granted by default).

Classification lives in real columns on purpose — never in ``details_json``, ``engagement_label``,
``authorization_scope``, or an id prefix alone. See
docs/PHASE56_INTERNAL_TEST_ENGAGEMENT_SUPPORT.md.

Non-destructive and additive: no table is dropped, no column is removed, no row is touched.
There are **no INSERTs, no seed data, and no data of any kind**.

Revision ID: 014_engagement_classification
Revises: 013_governed_identifier_collation_policy
Create Date: (static; no timestamp committed)
"""

from __future__ import annotations

import sqlalchemy as sa
from alembic import op

# revision identifiers, used by Alembic.
revision = "014_engagement_classification"
down_revision = "013_governed_identifier_collation_policy"
branch_labels = None
depends_on = None

TABLE = "engagements"

#: Mirrors ``peak.db.base.GOVERNED_COLLATION``; kept as a literal so the migration never imports
#: application code. Applied only on dialects that can express a MySQL collation.
GOVERNED_COLLATION = "utf8mb4_bin"
_COLLATING_DIALECTS = {"mysql", "mariadb"}


def _category_type():
    """``engagement_category`` as a governed string on MySQL, plain VARCHAR elsewhere."""
    dialect = op.get_bind().dialect.name
    if dialect in _COLLATING_DIALECTS:
        return sa.String(24, collation=GOVERNED_COLLATION)
    return sa.String(24)


def upgrade() -> None:
    op.add_column(
        TABLE,
        sa.Column("engagement_category", _category_type(), nullable=False,
                  server_default="real_client"),
    )
    op.add_column(
        TABLE,
        sa.Column("real_client_data", sa.Boolean(), nullable=False, server_default=sa.true()),
    )
    op.add_column(
        TABLE,
        sa.Column("client_accessible", sa.Boolean(), nullable=False, server_default=sa.true()),
    )
    op.add_column(
        TABLE,
        sa.Column("capsule_publication_authorized", sa.Boolean(), nullable=False,
                  server_default=sa.false()),
    )
    op.create_index(f"ix_{TABLE}_engagement_category", TABLE, ["engagement_category"])


def downgrade() -> None:
    op.drop_index(f"ix_{TABLE}_engagement_category", table_name=TABLE)
    op.drop_column(TABLE, "capsule_publication_authorized")
    op.drop_column(TABLE, "client_accessible")
    op.drop_column(TABLE, "real_client_data")
    op.drop_column(TABLE, "engagement_category")
