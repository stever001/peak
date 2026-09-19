"""Phase 202: client profile and engagement workflow fields (schema only, no data).

Adds nullable columns only — no table is created, dropped, or rewritten, and no existing column is
altered:

- ``clients``: ``description``; structured address (``address_line1``, ``address_line2``,
  ``city``, ``region``, ``postal_code``, ``country``); main contact (``contact_name``,
  ``contact_title``, ``contact_email``, ``contact_phone``); ``key_personnel`` (JSON list of
  name/role/email/phone — deliberately not a personnel table).
- ``engagements``: ``objective``; ``assigned_consultant_id`` (a governed identifier referencing
  ``consultants.id``, indexed, workflow metadata only); ``current_phase`` (a simple label).

The company name reuses ``clients.organization_label``; engagement title and status reuse
``engagement_label`` and ``status``. These columns are written only by the consultant workspace
service (``peak.persistence.allowlist.WORKSPACE_WRITE_COLUMNS``). There are **no INSERTs, no seed
data, and no data of any kind**. See docs/PHASE202_CLIENT_ENGAGEMENT_CRUD.md.

Revision ID: 016_client_engagement_workspace_fields
Revises: 015_consultants
Create Date: (static; no timestamp committed)
"""

from __future__ import annotations

import sqlalchemy as sa
from alembic import op

# revision identifiers, used by Alembic.
revision = "016_client_engagement_workspace_fields"
down_revision = "015_consultants"
branch_labels = None
depends_on = None

#: Mirrors ``peak.db.base.GOVERNED_COLLATION``; kept as a literal so the migration never imports
#: application code. Applied only on dialects that can express a MySQL collation.
GOVERNED_COLLATION = "utf8mb4_bin"
_COLLATING_DIALECTS = {"mysql", "mariadb"}

CLIENT_COLUMNS = (
    ("description", sa.Text()),
    ("address_line1", sa.String(255)),
    ("address_line2", sa.String(255)),
    ("city", sa.String(128)),
    ("region", sa.String(128)),
    ("postal_code", sa.String(32)),
    ("country", sa.String(128)),
    ("contact_name", sa.String(255)),
    ("contact_title", sa.String(255)),
    ("contact_email", sa.String(254)),
    ("contact_phone", sa.String(64)),
    ("key_personnel", sa.JSON()),
)


def _governed(length: int):
    """A governed string on MySQL, plain VARCHAR elsewhere."""
    if op.get_bind().dialect.name in _COLLATING_DIALECTS:
        return sa.String(length, collation=GOVERNED_COLLATION)
    return sa.String(length)


def upgrade() -> None:
    for name, type_ in CLIENT_COLUMNS:
        op.add_column("clients", sa.Column(name, type_, nullable=True))
    op.add_column("engagements", sa.Column("objective", sa.Text(), nullable=True))
    op.add_column("engagements", sa.Column("assigned_consultant_id", _governed(64), nullable=True))
    op.add_column("engagements", sa.Column("current_phase", sa.String(128), nullable=True))
    op.create_index("ix_engagements_assigned_consultant_id", "engagements",
                    ["assigned_consultant_id"])


def downgrade() -> None:
    op.drop_index("ix_engagements_assigned_consultant_id", table_name="engagements")
    for name in ("current_phase", "assigned_consultant_id", "objective"):
        op.drop_column("engagements", name)
    for name, _type in reversed(CLIENT_COLUMNS):
        op.drop_column("clients", name)
