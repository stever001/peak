"""Phase 201: consultant accounts for the Peak web application (schema only, no data).

Adds one table, ``consultants``, and nothing else:

- ``id`` — ``cons_<hex>``, a governed (byte-exact) string primary key;
- ``name`` — display name (ordinary prose, not governed);
- ``email`` — normalized by the application, governed and **unique**;
- ``password_hash`` — an Argon2id hash, governed (a secret hash); no plaintext password is stored;
- ``role`` — ``admin`` / ``consultant``, governed and limited by a CHECK constraint;
- ``created_at``.

No client relation, no assignment ACL, no profile fields. See
docs/PHASE201_CONSULTANT_WEB_SHELL_AUTH.md.

Additive: no existing table is altered. There are **no INSERTs, no seed data, and no data of any
kind** — the initial Admin is created out-of-band by ``tools/bootstrap_admin.py``.

Revision ID: 015_consultants
Revises: 014_engagement_classification
Create Date: (static; no timestamp committed)
"""

from __future__ import annotations

import sqlalchemy as sa
from alembic import op

# revision identifiers, used by Alembic.
revision = "015_consultants"
down_revision = "014_engagement_classification"
branch_labels = None
depends_on = None

TABLE = "consultants"

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
    op.create_table(
        TABLE,
        sa.Column("id", _governed(64), primary_key=True),
        sa.Column("name", sa.String(255), nullable=False),
        sa.Column("email", _governed(254), nullable=False),
        sa.Column("password_hash", _governed(255), nullable=False),
        sa.Column("role", _governed(16), nullable=False),
        sa.Column("created_at", sa.DateTime(), server_default=sa.func.now(), nullable=False),
        sa.UniqueConstraint("email", name="uq_consultants_email"),
        sa.CheckConstraint("role IN ('admin', 'consultant')", name="ck_consultants_role"),
        mysql_engine="InnoDB",
        mysql_charset="utf8mb4",
    )


def downgrade() -> None:
    op.drop_table(TABLE)
