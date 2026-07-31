"""Phase 37: internal_assessment_report_drafts table (schema only, no data).

Creates the new ``internal_assessment_report_drafts`` table for the Phase 37 controlled
internal-assessment-report-draft writer — the ninth narrow live DB writer and the persistence
counterpart to the Phase 36 DB-free report planning boundary.

The row stores a governed, **internal-only** report *plan* artifact: section metadata,
reference-only evidence traces, finding/recommendation candidate slots, open gaps, blocked items,
and future-gate placeholders. It stores **no report prose** — no final client-facing language, no
raw intake-note/packet/evidence/interview text, no source bytes, no generated agent output, no ROI
or savings figure, no approval decision, and no capsule/AgentNet publish payload. ``output_status``
is fixed at ``plan_persisted`` so a row can never be misread as a drafted report.

The table carries the universal governance axes + audit fields (as every table does), the
internal-only posture columns (all defaulting to the not-approved / not-verified / not-publishable /
needs-review posture), and the controlled-writer idempotency columns:

- ``idempotency_key`` — the caller-supplied key that backs replay safety;
- ``payload_fingerprint`` — a deterministic hash of the write payload/identity, used to tell an
  exact idempotent replay apart from a conflicting reuse of the same key;
- ``uq_internal_assessment_report_drafts_idem`` — a UNIQUE index over
  ``(owner_id, client_id, engagement_id, idempotency_key)`` so a repeated authorized write cannot
  create a duplicate row, and a key cannot collide across owner/client/engagement.

This migration is schema only. **SQLite (used by the fast local structural smoke path) is not the
production-readiness proof path** — managed MySQL test/staging validation is required before
treating DB-backed functionality as production-ready (see
docs/PRODUCTION_PARITY_DB_VALIDATION.md and docs/MANAGED_MYSQL_PERSISTENCE_RUBRIC.md).

Additive and non-destructive: it creates exactly one new table and its indexes/constraint and
touches nothing else. There are **no INSERTs, no seed data, and no data of any kind**. The full
downgrade drops only this new table (and its indexes/constraint). See
docs/INTERNAL_ASSESSMENT_REPORT_DRAFT_CONTROLLED_WRITER.md and
docs/INTERNAL_ASSESSMENT_REPORT_DRAFT_IDEMPOTENCY_POLICY.md.

Revision ID: 010_internal_assessment_report_drafts
Revises: 009_intake_note_records
Create Date: (static; no timestamp committed)
"""

from __future__ import annotations

import sqlalchemy as sa
from alembic import op

# revision identifiers, used by Alembic.
revision = "010_internal_assessment_report_drafts"
down_revision = "009_intake_note_records"
branch_labels = None
depends_on = None

TABLE = "internal_assessment_report_drafts"
UNIQUE_INDEX = "uq_internal_assessment_report_drafts_idem"
MYSQL = {"mysql_engine": "InnoDB", "mysql_charset": "utf8mb4"}

# Table-specific indexes (governance/audit indexes are added separately, mirroring 001_initial).
INDEXED_COLUMNS = (
    "client_id",
    "engagement_id",
    "report_plan_id",
    "plan_fingerprint",
    "audience",
    "output_status",
    "idempotency_key",
)
GOVERNANCE_INDEXED_COLUMNS = (
    "owner_id",
    "authorization_scope",
    "review_status",
    "lifecycle_status",
    "agent_run_id",
)


def _common_columns() -> list:
    """Governance + audit columns carried by every record (mirrors 001_initial)."""
    return [
        sa.Column("owner_id", sa.String(128)),
        sa.Column("authorization_scope", sa.String(48)),
        sa.Column("review_status", sa.String(32), nullable=False, server_default="draft"),
        sa.Column("lifecycle_status", sa.String(32), nullable=False, server_default="draft"),
        sa.Column("created_at", sa.DateTime(), server_default=sa.func.now(), nullable=False),
        sa.Column("created_by", sa.String(128)),
        sa.Column("updated_at", sa.DateTime(), server_default=sa.func.now(), nullable=False),
        sa.Column("updated_by", sa.String(128)),
        sa.Column("agent_run_id", sa.String(64)),
        sa.Column("details_json", sa.JSON()),
    ]


def upgrade() -> None:
    op.create_table(
        TABLE,
        sa.Column("id", sa.String(64), primary_key=True),
        sa.Column("client_id", sa.String(64)),
        sa.Column("engagement_id", sa.String(64)),
        # Provenance back to the Phase 36 plan.
        sa.Column("report_plan_id", sa.String(128)),
        sa.Column("plan_fingerprint", sa.String(64)),
        sa.Column("requested_by", sa.String(128)),
        sa.Column("requester_role", sa.String(64)),
        sa.Column("report_purpose", sa.String(255)),
        sa.Column("audience", sa.String(32), nullable=False, server_default="internal"),
        # Structured plan payload — references, labels, counts, and readiness states ONLY.
        sa.Column("sections_json", sa.JSON()),
        sa.Column("evidence_trace_map_json", sa.JSON()),
        sa.Column("finding_candidates_json", sa.JSON()),
        sa.Column("recommendation_candidates_json", sa.JSON()),
        sa.Column("open_gaps_json", sa.JSON()),
        sa.Column("blocked_items_json", sa.JSON()),
        # Forward-looking placeholders naming FUTURE gates; nothing is verified or published here.
        sa.Column("future_financial_verification_items_json", sa.JSON()),
        sa.Column("future_capsule_candidate_items_json", sa.JSON()),
        sa.Column("reasons_json", sa.JSON()),
        sa.Column("warnings_json", sa.JSON()),
        # Governance / internal-only posture.
        sa.Column("output_status", sa.String(32), nullable=False,
                  server_default="plan_persisted"),
        sa.Column("client_facing_approved", sa.Boolean(), nullable=False,
                  server_default=sa.text("0")),
        sa.Column("financial_verified", sa.Boolean(), nullable=False,
                  server_default=sa.text("0")),
        sa.Column("capsule_candidate_ready", sa.Boolean(), nullable=False,
                  server_default=sa.text("0")),
        sa.Column("publication_allowed", sa.Boolean(), nullable=False,
                  server_default=sa.text("0")),
        sa.Column("execution_allowed", sa.Boolean(), nullable=False,
                  server_default=sa.text("0")),
        sa.Column("requires_human_review", sa.Boolean(), nullable=False,
                  server_default=sa.text("1")),
        sa.Column("idempotency_key", sa.String(128)),
        sa.Column("payload_fingerprint", sa.String(64)),
        *_common_columns(),
        **MYSQL,
    )
    for col in INDEXED_COLUMNS:
        op.create_index(f"ix_{TABLE}_{col}", TABLE, [col])
    # Governance/audit indexes carried by every table (mirrors 001_initial).
    for col in GOVERNANCE_INDEXED_COLUMNS:
        op.create_index(f"ix_{TABLE}_{col}", TABLE, [col])
    # DB-enforced idempotency boundary (identity context + key). Unique index is portable
    # across MySQL and the local SQLite structural-smoke database.
    op.create_index(
        UNIQUE_INDEX,
        TABLE,
        ["owner_id", "client_id", "engagement_id", "idempotency_key"],
        unique=True,
    )


def downgrade() -> None:
    op.drop_index(UNIQUE_INDEX, table_name=TABLE)
    for col in reversed(GOVERNANCE_INDEXED_COLUMNS):
        op.drop_index(f"ix_{TABLE}_{col}", table_name=TABLE)
    for col in reversed(INDEXED_COLUMNS):
        op.drop_index(f"ix_{TABLE}_{col}", table_name=TABLE)
    op.drop_table(TABLE)
