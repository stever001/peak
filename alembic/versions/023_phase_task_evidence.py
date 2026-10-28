"""Phase 220: guided evidence capture (schema only, no data).

Creates one new table and nothing else: no existing table or column is altered.

- ``phase_task_evidence``: a photo or document photo a consultant captured while doing a task.
  Metadata, linkage and provenance only; the original bytes live in object storage under the
  server-generated ``storage_key`` (``uq_phase_task_evidence_storage_key``). Insert-only; a
  replacement supersedes (``uq_phase_task_evidence_supersedes``). Optionally linked to one task
  record of the same task (``task_record_id``). Never an observation, finding, recommendation or
  governed assessment evidence.

Every closed vocabulary is a named CHECK constraint, created with the table, so it holds on every
dialect. There are **no INSERTs, no seed data, and no data of any kind**. See
docs/PHASE220_GUIDED_EVIDENCE_CAPTURE.md.

Production note: the runtime role needs SELECT and INSERT only (already granted schema-wide). The
table is append-only, so it needs **no UPDATE grant** and the Phase 50 gate fails on one.

Revision ID: 023_phase_task_evidence
Revises: 022_engagement_roadmap_work_plan
Create Date: (static; no timestamp committed)
"""

from __future__ import annotations

import sqlalchemy as sa
from alembic import op

# revision identifiers, used by Alembic.
revision = "023_phase_task_evidence"
down_revision = "022_engagement_roadmap_work_plan"
branch_labels = None
depends_on = None

#: Mirrors ``peak.db.base.GOVERNED_COLLATION``; kept as a literal so the migration never imports
#: application code. Applied only on dialects that can express a MySQL collation.
GOVERNED_COLLATION = "utf8mb4_bin"
_COLLATING_DIALECTS = {"mysql", "mariadb"}

#: Mirror the ``peak.db.models`` vocabularies, as literals for the same reason.
_KINDS = ("photo", "document_photo")
_MEDIA_TYPES = ("image/jpeg", "image/png", "image/heic", "image/heif")
_BACKENDS = ("filesystem", "r2")

_TABLE = "phase_task_evidence"


def _in(column, values):
    return f"{column} IN ({', '.join(repr(v) for v in values)})"


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
        sa.Column("phase_id", _governed(64), nullable=False),
        sa.Column("task_id", _governed(64), nullable=False),
        sa.Column("task_record_id", _governed(64), nullable=True),
        sa.Column("evidence_kind", sa.String(24), nullable=False),
        sa.Column("caption", sa.Text(), nullable=True),
        sa.Column("media_type", sa.String(64), nullable=False),
        sa.Column("byte_length", sa.Integer(), nullable=False),
        sa.Column("content_hash", _governed(64), nullable=False),
        sa.Column("storage_backend", sa.String(16), nullable=False),
        sa.Column("storage_key", _governed(255), nullable=False),
        sa.Column("file_name", sa.String(255), nullable=True),
        sa.Column("supersedes_evidence_id", _governed(64), nullable=True),
        sa.Column("uploaded_by_consultant_id", _governed(64), nullable=False),
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
        sa.UniqueConstraint("supersedes_evidence_id", name="uq_phase_task_evidence_supersedes"),
        sa.UniqueConstraint("storage_key", name="uq_phase_task_evidence_storage_key"),
        sa.CheckConstraint(_in("evidence_kind", _KINDS), name="ck_phase_task_evidence_kind"),
        sa.CheckConstraint(_in("media_type", _MEDIA_TYPES),
                           name="ck_phase_task_evidence_media_type"),
        sa.CheckConstraint(_in("storage_backend", _BACKENDS),
                           name="ck_phase_task_evidence_storage_backend"),
        sa.CheckConstraint("byte_length > 0", name="ck_phase_task_evidence_byte_length"),
        mysql_engine="InnoDB", mysql_charset="utf8mb4",
    )
    for column in ("owner_id", "authorization_scope", "review_status", "lifecycle_status",
                   "agent_run_id", "client_id", "engagement_id", "phase_id", "task_id",
                   "task_record_id", "content_hash"):
        op.create_index(f"ix_{_TABLE}_{column}", _TABLE, [column])


def downgrade() -> None:
    op.drop_table(_TABLE)
