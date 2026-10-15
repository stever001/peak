"""Phase 212: artifact identity and immutable artifact versions (schema only, no data).

Adds:

- ``artifacts``: the stable identity of one logical engagement artifact — client, engagement,
  artifact type, and a snapshot of the engagement's phase label (there is no engagement-phase
  entity);
- ``artifact_versions``: one immutable snapshot per version — internal sequence number, canonical
  business-content text, its sha256 content hash, the version it supersedes (unique, so history
  stays a single line), a lifecycle status that starts at ``versioned``, the creating consultant,
  and source references.

Both tables carry the governance/audit columns of every governed record. Governed identifiers are
pinned to the governed collation at creation. Written only by ``peak.workspace.artifacts``
(``peak.persistence.allowlist.WORKSPACE_WRITE_COLUMNS``: create actions only, no update, no delete).

Additive. There are **no INSERTs, no seed data, and no data of any kind**. See
docs/PHASE212_ARTIFACT_VERSION_PERSISTENCE.md and docs/ARTIFACT_LIFECYCLE.md.

Revision ID: 018_artifact_versions
Revises: 017_discovery_workflow
Create Date: (static; no timestamp committed)
"""

from __future__ import annotations

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects import mysql

# revision identifiers, used by Alembic.
revision = "018_artifact_versions"
down_revision = "017_discovery_workflow"
branch_labels = None
depends_on = None

#: Mirrors ``peak.db.base.GOVERNED_COLLATION``; kept as a literal so the migration never imports
#: application code. Applied only on dialects that can express a MySQL collation.
GOVERNED_COLLATION = "utf8mb4_bin"
_COLLATING_DIALECTS = {"mysql", "mariadb"}
TABLE_OPTIONS = {"mysql_engine": "InnoDB", "mysql_charset": "utf8mb4"}

GOVERNED_TABLE_INDEXES = {
    "artifacts": ("client_id", "engagement_id", "artifact_type"),
    "artifact_versions": ("artifact_id", "client_id", "engagement_id", "content_hash"),
}
GOVERNANCE_INDEXED = ("owner_id", "authorization_scope", "review_status", "lifecycle_status",
                      "agent_run_id")


def _governed(length: int):
    """A governed string on MySQL, plain VARCHAR elsewhere."""
    if op.get_bind().dialect.name in _COLLATING_DIALECTS:
        return sa.String(length, collation=GOVERNED_COLLATION)
    return sa.String(length)


def _long_text():
    """LONGTEXT on MySQL (canonical content can exceed TEXT's 64 KB), TEXT elsewhere."""
    if op.get_bind().dialect.name in _COLLATING_DIALECTS:
        return mysql.LONGTEXT()
    return sa.Text()


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
    op.create_table(
        "artifacts",
        sa.Column("id", _governed(64), primary_key=True),
        sa.Column("client_id", _governed(64), nullable=False),
        sa.Column("engagement_id", _governed(64), nullable=False),
        sa.Column("artifact_type", sa.String(48), nullable=False),
        sa.Column("engagement_phase_label", sa.String(128)),
        sa.Column("created_by_consultant_id", _governed(64), nullable=False),
        *_governance_columns(),
        **TABLE_OPTIONS,
    )

    op.create_table(
        "artifact_versions",
        sa.Column("id", _governed(64), primary_key=True),
        sa.Column("artifact_id", _governed(64), nullable=False),
        sa.Column("client_id", _governed(64), nullable=False),
        sa.Column("engagement_id", _governed(64), nullable=False),
        sa.Column("version_number", sa.Integer(), nullable=False),
        sa.Column("content_format", sa.String(64), nullable=False),
        sa.Column("content_canonical", _long_text(), nullable=False),
        sa.Column("content_hash", _governed(64), nullable=False),
        sa.Column("supersedes_version_id", _governed(64)),
        sa.Column("version_status", sa.String(24), nullable=False, server_default="versioned"),
        sa.Column("created_by_consultant_id", _governed(64), nullable=False),
        sa.Column("source_references", sa.JSON()),
        *_governance_columns(),
        sa.UniqueConstraint("artifact_id", "version_number", name="uq_artifact_versions_number"),
        sa.UniqueConstraint("supersedes_version_id", name="uq_artifact_versions_supersedes"),
        sa.CheckConstraint(
            "version_status IN ('versioned', 'lead_approved', 'final_approved', 'released', "
            "'superseded', 'rejected')",
            name="ck_artifact_versions_status"),
        sa.CheckConstraint("version_number >= 1", name="ck_artifact_versions_number"),
        **TABLE_OPTIONS,
    )

    for table, columns in GOVERNED_TABLE_INDEXES.items():
        for column in columns + GOVERNANCE_INDEXED:
            op.create_index(f"ix_{table}_{column}", table, [column])


def downgrade() -> None:
    op.drop_table("artifact_versions")
    op.drop_table("artifacts")
