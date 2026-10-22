"""Phase 217: engagement roadmap, engagement phases, guided work plans (schema only, no data).

Creates four new tables and nothing else: no existing table or column is altered, and no artifact
or discovery table is touched.

- ``roadmap_items``: proposed future consulting work derived from discovery. Advisory; never
  authorized work. Framing is fixed at creation; a revision supersedes (``supersedes_item_id``).
- ``engagement_phases``: one separately authorized unit of consulting work, optionally from one
  accepted roadmap item (``uq_engagement_phases_roadmap_item``). Authorization is a recorded human
  act (``authorized_by_consultant_id`` / ``authorized_at`` / ``authorization_basis``).
- ``phase_tasks``: the phase's ordered guided work plan (``uq_phase_tasks_sequence``), with
  dependencies, one optional condition, required/optional, origin and inclusion reason.
- ``phase_task_records``: what the consultant recorded while doing a task. Insert-only; a
  correction supersedes (``uq_phase_task_records_supersedes``).

Every closed vocabulary is a named CHECK constraint, created with the table, so it holds on every
dialect. There are **no INSERTs, no seed data, and no data of any kind**. See
docs/PHASE217_ENGAGEMENT_ROADMAP_WORK_PLAN.md.

Production note: the runtime role needs SELECT and INSERT on all four tables, and UPDATE on
``roadmap_items``, ``engagement_phases`` and ``phase_tasks`` (lifecycle and task progress).
``phase_task_records`` needs no UPDATE. That grant change is a separate, approved cutover step.

Revision ID: 022_engagement_roadmap_work_plan
Revises: 021_discovery_observation_trace_basis
Create Date: (static; no timestamp committed)
"""

from __future__ import annotations

import sqlalchemy as sa
from alembic import op

# revision identifiers, used by Alembic.
revision = "022_engagement_roadmap_work_plan"
down_revision = "021_discovery_observation_trace_basis"
branch_labels = None
depends_on = None

#: Mirrors ``peak.db.base.GOVERNED_COLLATION``; kept as a literal so the migration never imports
#: application code. Applied only on dialects that can express a MySQL collation.
GOVERNED_COLLATION = "utf8mb4_bin"
_COLLATING_DIALECTS = {"mysql", "mariadb"}

#: Mirror the ``peak.db.models`` vocabularies, as literals for the same reason.
_ROADMAP_STATUSES = ("proposed", "accepted", "deferred", "declined", "superseded")
_ORIGINS = ("peak_method", "consultant", "si_suggested")
_PHASE_STATUSES = ("planned", "authorized", "completed")
_PHASE_ORIGINS = ("roadmap_item", "manual")
_TASK_STATUSES = ("suggested", "open", "in_progress", "completed", "not_applicable")
_RECORD_KINDS = ("note", "interview_response", "measurement", "mismatch", "photo",
                 "document_photo", "document")
_BASES = ("testimony", "observed", "document", "measured", "inferred")

_TABLES = ("roadmap_items", "engagement_phases", "phase_tasks", "phase_task_records")


def _in(column, values):
    return f"{column} IN ({', '.join(repr(v) for v in values)})"


def _governed(length: int):
    """A governed string on MySQL, plain VARCHAR elsewhere."""
    if op.get_bind().dialect.name in _COLLATING_DIALECTS:
        return sa.String(length, collation=GOVERNED_COLLATION)
    return sa.String(length)


def _common():
    """GovernanceMixin and AuditMixin columns, as every governed table carries them."""
    return [
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
    ]


def _indexes(table, columns):
    for column in ("owner_id", "authorization_scope", "review_status", "lifecycle_status",
                   "agent_run_id", *columns):
        op.create_index(f"ix_{table}_{column}", table, [column])


_TABLE_ARGS = {"mysql_engine": "InnoDB", "mysql_charset": "utf8mb4"}


def upgrade() -> None:
    op.create_table(
        "roadmap_items",
        sa.Column("id", _governed(64), primary_key=True),
        sa.Column("client_id", _governed(64), nullable=False),
        sa.Column("engagement_id", _governed(64), nullable=False),
        sa.Column("sequence", sa.Integer(), nullable=False),
        sa.Column("title", sa.String(255), nullable=False),
        sa.Column("problem_framing", sa.Text(), nullable=False),
        sa.Column("rationale", sa.Text(), nullable=False),
        sa.Column("expected_outcome", sa.Text(), nullable=False),
        sa.Column("source_observation_ids", sa.JSON(), nullable=True),
        sa.Column("origin", sa.String(16), nullable=False),
        sa.Column("template_key", _governed(64), nullable=True),
        sa.Column("method_version", sa.String(64), nullable=True),
        sa.Column("status", sa.String(16), nullable=False),
        sa.Column("status_note", sa.Text(), nullable=True),
        sa.Column("supersedes_item_id", _governed(64), nullable=True),
        sa.Column("created_by_consultant_id", _governed(64), nullable=False),
        sa.Column("decided_by_consultant_id", _governed(64), nullable=True),
        sa.Column("decided_at", sa.DateTime(), nullable=True),
        *_common(),
        sa.UniqueConstraint("supersedes_item_id", name="uq_roadmap_items_supersedes"),
        sa.CheckConstraint(_in("status", _ROADMAP_STATUSES), name="ck_roadmap_items_status"),
        sa.CheckConstraint(_in("origin", _ORIGINS), name="ck_roadmap_items_origin"),
        sa.CheckConstraint("sequence >= 1", name="ck_roadmap_items_sequence"),
        **_TABLE_ARGS,
    )
    _indexes("roadmap_items", ("client_id", "engagement_id"))

    op.create_table(
        "engagement_phases",
        sa.Column("id", _governed(64), primary_key=True),
        sa.Column("client_id", _governed(64), nullable=False),
        sa.Column("engagement_id", _governed(64), nullable=False),
        sa.Column("origin", sa.String(16), nullable=False),
        sa.Column("roadmap_item_id", _governed(64), nullable=True),
        sa.Column("origin_note", sa.Text(), nullable=True),
        sa.Column("title", sa.String(255), nullable=False),
        sa.Column("scope_summary", sa.Text(), nullable=False),
        sa.Column("status", sa.String(16), nullable=False),
        sa.Column("created_by_consultant_id", _governed(64), nullable=False),
        sa.Column("authorization_basis", sa.Text(), nullable=True),
        sa.Column("authorization_reference", sa.String(255), nullable=True),
        sa.Column("authorized_by_consultant_id", _governed(64), nullable=True),
        sa.Column("authorized_at", sa.DateTime(), nullable=True),
        sa.Column("completed_by_consultant_id", _governed(64), nullable=True),
        sa.Column("completed_at", sa.DateTime(), nullable=True),
        *_common(),
        sa.UniqueConstraint("roadmap_item_id", name="uq_engagement_phases_roadmap_item"),
        sa.CheckConstraint(_in("status", _PHASE_STATUSES), name="ck_engagement_phases_status"),
        sa.CheckConstraint(_in("origin", _PHASE_ORIGINS), name="ck_engagement_phases_origin"),
        **_TABLE_ARGS,
    )
    _indexes("engagement_phases", ("client_id", "engagement_id"))

    op.create_table(
        "phase_tasks",
        sa.Column("id", _governed(64), primary_key=True),
        sa.Column("client_id", _governed(64), nullable=False),
        sa.Column("engagement_id", _governed(64), nullable=False),
        sa.Column("phase_id", _governed(64), nullable=False),
        sa.Column("sequence", sa.Integer(), nullable=False),
        sa.Column("title", sa.String(255), nullable=False),
        sa.Column("instructions", sa.Text(), nullable=False),
        sa.Column("why_it_matters", sa.Text(), nullable=True),
        sa.Column("what_to_observe", sa.Text(), nullable=True),
        sa.Column("suggested_evidence", sa.JSON(), nullable=True),
        sa.Column("follow_up_questions", sa.JSON(), nullable=True),
        sa.Column("expected_result", sa.Text(), nullable=True),
        sa.Column("required", sa.Boolean(), server_default=sa.true(), nullable=False),
        sa.Column("requires_record", sa.Boolean(), server_default=sa.false(), nullable=False),
        sa.Column("depends_on_task_ids", sa.JSON(), nullable=True),
        sa.Column("condition_task_id", _governed(64), nullable=True),
        sa.Column("condition_record_kind", sa.String(24), nullable=True),
        sa.Column("origin", sa.String(16), nullable=False),
        sa.Column("template_key", _governed(64), nullable=True),
        sa.Column("inclusion_reason", sa.Text(), nullable=True),
        sa.Column("added_after_authorization", sa.Boolean(), server_default=sa.false(),
                  nullable=False),
        sa.Column("status", sa.String(16), nullable=False),
        sa.Column("consultant_notes", sa.Text(), nullable=True),
        sa.Column("result_summary", sa.Text(), nullable=True),
        sa.Column("not_applicable_reason", sa.Text(), nullable=True),
        sa.Column("created_by_consultant_id", _governed(64), nullable=False),
        sa.Column("completed_by_consultant_id", _governed(64), nullable=True),
        sa.Column("completed_at", sa.DateTime(), nullable=True),
        *_common(),
        sa.UniqueConstraint("phase_id", "sequence", name="uq_phase_tasks_sequence"),
        sa.CheckConstraint(_in("status", _TASK_STATUSES), name="ck_phase_tasks_status"),
        sa.CheckConstraint(_in("origin", _ORIGINS), name="ck_phase_tasks_origin"),
        sa.CheckConstraint("condition_record_kind IS NULL OR "
                           + _in("condition_record_kind", _RECORD_KINDS),
                           name="ck_phase_tasks_condition_kind"),
        sa.CheckConstraint("sequence >= 1", name="ck_phase_tasks_sequence"),
        **_TABLE_ARGS,
    )
    _indexes("phase_tasks", ("client_id", "engagement_id", "phase_id"))

    op.create_table(
        "phase_task_records",
        sa.Column("id", _governed(64), primary_key=True),
        sa.Column("client_id", _governed(64), nullable=False),
        sa.Column("engagement_id", _governed(64), nullable=False),
        sa.Column("phase_id", _governed(64), nullable=False),
        sa.Column("task_id", _governed(64), nullable=False),
        sa.Column("record_kind", sa.String(24), nullable=False),
        sa.Column("record_text", sa.Text(), nullable=False),
        sa.Column("structured", sa.JSON(), nullable=True),
        sa.Column("basis", sa.String(16), nullable=True),
        sa.Column("supersedes_record_id", _governed(64), nullable=True),
        sa.Column("recorded_by_consultant_id", _governed(64), nullable=False),
        *_common(),
        sa.UniqueConstraint("supersedes_record_id", name="uq_phase_task_records_supersedes"),
        sa.CheckConstraint(_in("record_kind", _RECORD_KINDS), name="ck_phase_task_records_kind"),
        sa.CheckConstraint("basis IS NULL OR " + _in("basis", _BASES),
                           name="ck_phase_task_records_basis"),
        **_TABLE_ARGS,
    )
    _indexes("phase_task_records", ("client_id", "engagement_id", "phase_id", "task_id"))


def downgrade() -> None:
    for table in reversed(_TABLES):
        op.drop_table(table)
