"""Phase 213: release packages, renditions, two-stage approval and release (schema only, no data).

Adds five append-only tables. Approval applies to a **release package**: one immutable canonical
artifact version bound to the exact client-facing renditions proposed for release
(docs/ARTIFACT_LIFECYCLE.md §9A).

- ``artifact_release_packages``: one package per (artifact, package number), bound to one version
  and its content hash, with a package hash over that hash and the rendition hashes. A newer package
  supersedes the previous one (unique, so the history stays a single line);
- ``artifact_renditions``: the exact rendered bytes of one rendition of a package — ``web`` (static
  HTML) or ``docx`` — with their sha256 hash; one per type per package. Stored, never regenerated;
- ``artifact_approvals``: one decision (``approved`` / ``rejected``) per approval level
  (``lead_consultant`` / ``final_approver``) per package — unique on (package, level) — bound to the
  package hash and the version's content hash, recording which rendition (web or DOCX) the human
  reviewed, with an optional note. A final decision also records the designation it was made under;
- ``artifact_final_approver_designations``: who is designated Final Approver of a package, and by
  whom. Reassignment adds a row that supersedes the previous one; no row is ever overwritten;
- ``artifact_releases``: the release of one package — at most one per package — bound to its
  package hash and the two approvals that made it eligible.

Lifecycle state is derived from these records; ``artifact_versions`` is not altered and stays
insert-only. Every table carries the governance/audit columns of every governed record, and
governed identifiers are pinned to the governed collation at creation. Written only by
``peak.workspace.approvals`` (create actions only — no update, no delete).

Additive. There are **no INSERTs, no seed data, and no data of any kind**. See
docs/PHASE213_ARTIFACT_APPROVAL_RELEASE.md and docs/ARTIFACT_LIFECYCLE.md §5–§7.

Revision ID: 019_artifact_approval_release
Revises: 018_artifact_versions
Create Date: (static; no timestamp committed)
"""

from __future__ import annotations

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects import mysql

# revision identifiers, used by Alembic.
revision = "019_artifact_approval_release"
down_revision = "018_artifact_versions"
branch_labels = None
depends_on = None

#: Mirrors ``peak.db.base.GOVERNED_COLLATION``; kept as a literal so the migration never imports
#: application code. Applied only on dialects that can express a MySQL collation.
GOVERNED_COLLATION = "utf8mb4_bin"
_COLLATING_DIALECTS = {"mysql", "mariadb"}
TABLE_OPTIONS = {"mysql_engine": "InnoDB", "mysql_charset": "utf8mb4"}

GOVERNED_TABLE_INDEXES = {
    "artifact_release_packages": ("artifact_id", "artifact_version_id", "client_id",
                                  "engagement_id"),
    "artifact_renditions": ("artifact_id", "artifact_version_id", "client_id", "engagement_id"),
    "artifact_approvals": ("artifact_id", "artifact_version_id", "release_package_id", "client_id",
                           "engagement_id"),
    "artifact_final_approver_designations": ("artifact_id", "artifact_version_id",
                                             "release_package_id", "client_id", "engagement_id"),
    "artifact_releases": ("artifact_id", "artifact_version_id", "client_id", "engagement_id"),
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


def _long_blob():
    """LONGBLOB on MySQL (a rendition can exceed BLOB's 64 KB), BLOB elsewhere."""
    if op.get_bind().dialect.name in _COLLATING_DIALECTS:
        return mysql.LONGBLOB()
    return sa.LargeBinary()


def _version_columns():
    return [
        sa.Column("id", _governed(64), primary_key=True),
        sa.Column("artifact_id", _governed(64), nullable=False),
        sa.Column("artifact_version_id", _governed(64), nullable=False),
        sa.Column("client_id", _governed(64), nullable=False),
        sa.Column("engagement_id", _governed(64), nullable=False),
    ]


def upgrade() -> None:
    op.create_table(
        "artifact_release_packages",
        *_version_columns(),
        sa.Column("package_number", sa.Integer(), nullable=False),
        sa.Column("content_hash", _governed(64), nullable=False),
        sa.Column("package_hash", _governed(64), nullable=False),
        sa.Column("supersedes_package_id", _governed(64)),
        sa.Column("created_by_consultant_id", _governed(64), nullable=False),
        *_governance_columns(),
        sa.UniqueConstraint("artifact_id", "package_number", name="uq_artifact_packages_number"),
        sa.UniqueConstraint("supersedes_package_id", name="uq_artifact_packages_supersedes"),
        sa.CheckConstraint("package_number >= 1", name="ck_artifact_packages_number"),
        **TABLE_OPTIONS,
    )

    op.create_table(
        "artifact_renditions",
        *_version_columns(),
        sa.Column("release_package_id", _governed(64), nullable=False),
        sa.Column("rendition_type", sa.String(16), nullable=False),
        sa.Column("media_type", sa.String(128), nullable=False),
        sa.Column("rendered_by", sa.String(128), nullable=False),
        sa.Column("file_name", sa.String(255)),
        sa.Column("byte_length", sa.Integer(), nullable=False),
        sa.Column("content_bytes", _long_blob(), nullable=False),
        sa.Column("rendition_hash", _governed(64), nullable=False),
        *_governance_columns(),
        sa.UniqueConstraint("release_package_id", "rendition_type",
                            name="uq_artifact_renditions_type"),
        sa.CheckConstraint("rendition_type IN ('web', 'docx')", name="ck_artifact_renditions_type"),
        **TABLE_OPTIONS,
    )

    op.create_table(
        "artifact_approvals",
        *_version_columns(),
        sa.Column("release_package_id", _governed(64), nullable=False),
        sa.Column("approval_level", sa.String(24), nullable=False),
        sa.Column("decision", sa.String(16), nullable=False),
        sa.Column("approver_consultant_id", _governed(64), nullable=False),
        sa.Column("content_hash", _governed(64), nullable=False),
        sa.Column("package_hash", _governed(64), nullable=False),
        sa.Column("reviewed_rendition_type", sa.String(16), nullable=False),
        sa.Column("decision_note", sa.Text()),
        sa.Column("designation_id", _governed(64)),
        *_governance_columns(),
        sa.UniqueConstraint("release_package_id", "approval_level",
                            name="uq_artifact_approvals_level"),
        sa.CheckConstraint("approval_level IN ('lead_consultant', 'final_approver')",
                           name="ck_artifact_approvals_level"),
        sa.CheckConstraint("decision IN ('approved', 'rejected')",
                           name="ck_artifact_approvals_decision"),
        sa.CheckConstraint("reviewed_rendition_type IN ('web', 'docx')",
                           name="ck_artifact_approvals_reviewed"),
        **TABLE_OPTIONS,
    )

    op.create_table(
        "artifact_final_approver_designations",
        *_version_columns(),
        sa.Column("release_package_id", _governed(64), nullable=False),
        sa.Column("designation_number", sa.Integer(), nullable=False),
        sa.Column("designated_consultant_id", _governed(64), nullable=False),
        sa.Column("designated_by_consultant_id", _governed(64), nullable=False),
        sa.Column("supersedes_designation_id", _governed(64)),
        *_governance_columns(),
        sa.UniqueConstraint("release_package_id", "designation_number",
                            name="uq_artifact_designations_number"),
        sa.UniqueConstraint("supersedes_designation_id", name="uq_artifact_designations_supersedes"),
        sa.CheckConstraint("designation_number >= 1", name="ck_artifact_designations_number"),
        **TABLE_OPTIONS,
    )

    op.create_table(
        "artifact_releases",
        *_version_columns(),
        sa.Column("release_package_id", _governed(64), nullable=False),
        sa.Column("released_by_consultant_id", _governed(64), nullable=False),
        sa.Column("content_hash", _governed(64), nullable=False),
        sa.Column("package_hash", _governed(64), nullable=False),
        sa.Column("lead_approval_id", _governed(64), nullable=False),
        sa.Column("final_approval_id", _governed(64), nullable=False),
        *_governance_columns(),
        sa.UniqueConstraint("release_package_id", name="uq_artifact_releases_package"),
        **TABLE_OPTIONS,
    )

    for table, columns in GOVERNED_TABLE_INDEXES.items():
        for column in columns + GOVERNANCE_INDEXED:
            op.create_index(f"ix_{table}_{column}", table, [column])


def downgrade() -> None:
    op.drop_table("artifact_releases")
    op.drop_table("artifact_final_approver_designations")
    op.drop_table("artifact_approvals")
    op.drop_table("artifact_renditions")
    op.drop_table("artifact_release_packages")
