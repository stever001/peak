"""Initial controlled database schema (MySQL) — tables only, no data.

Creates the minimal Phase 11 tables for the controlled engagement database. This
migration defines **schema structure only**: no INSERTs, no seed data, no example
records, no client data. See docs/DATABASE_SCAFFOLD.md.

Revision ID: 001_initial
Revises:
Create Date: (static; no timestamp committed)
"""

from __future__ import annotations

import sqlalchemy as sa
from alembic import op

# revision identifiers, used by Alembic.
revision = "001_initial"
down_revision = None
branch_labels = None
depends_on = None

MYSQL = {"mysql_engine": "InnoDB", "mysql_charset": "utf8mb4"}


def _common_columns() -> list[sa.Column]:
    """Fresh instances of the governance + audit columns carried by every record.

    Governance fields are real columns (not hidden in JSON). `details_json` is for
    non-governance detail only.
    """
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


def _common_indexes(table: str) -> None:
    for col in ("owner_id", "authorization_scope", "review_status", "lifecycle_status", "agent_run_id"):
        op.create_index(f"ix_{table}_{col}", table, [col])


def upgrade() -> None:
    # clients
    op.create_table(
        "clients",
        sa.Column("id", sa.String(64), primary_key=True),
        sa.Column("organization_label", sa.String(255)),
        *_common_columns(),
        **MYSQL,
    )
    _common_indexes("clients")

    # engagements
    op.create_table(
        "engagements",
        sa.Column("id", sa.String(64), primary_key=True),
        sa.Column("client_id", sa.String(64), nullable=False),
        sa.Column("engagement_label", sa.String(255)),
        sa.Column("status", sa.String(32)),
        *_common_columns(),
        **MYSQL,
    )
    op.create_index("ix_engagements_client_id", "engagements", ["client_id"])
    _common_indexes("engagements")

    # engagement_records
    op.create_table(
        "engagement_records",
        sa.Column("id", sa.String(64), primary_key=True),
        sa.Column("client_id", sa.String(64), nullable=False),
        sa.Column("engagement_id", sa.String(64), nullable=False),
        sa.Column("data_class", sa.String(32)),
        *_common_columns(),
        **MYSQL,
    )
    op.create_index("ix_engagement_records_client_id", "engagement_records", ["client_id"])
    op.create_index("ix_engagement_records_engagement_id", "engagement_records", ["engagement_id"])
    _common_indexes("engagement_records")

    # evidence_references
    op.create_table(
        "evidence_references",
        sa.Column("id", sa.String(64), primary_key=True),
        sa.Column("client_id", sa.String(64)),
        sa.Column("engagement_id", sa.String(64)),
        sa.Column("evidence_type", sa.String(48)),
        sa.Column("source_type", sa.String(48)),
        sa.Column("reliability", sa.String(16)),
        sa.Column("evidence_status", sa.String(32), nullable=False, server_default="collected"),
        sa.Column("sensitive_data_flag", sa.Boolean(), nullable=False, server_default=sa.text("0")),
        sa.Column("summary", sa.Text()),
        *_common_columns(),
        **MYSQL,
    )
    op.create_index("ix_evidence_references_client_id", "evidence_references", ["client_id"])
    op.create_index("ix_evidence_references_engagement_id", "evidence_references", ["engagement_id"])
    op.create_index("ix_evidence_references_evidence_status", "evidence_references", ["evidence_status"])
    _common_indexes("evidence_references")

    # source_system_references
    op.create_table(
        "source_system_references",
        sa.Column("id", sa.String(64), primary_key=True),
        sa.Column("client_id", sa.String(64)),
        sa.Column("engagement_id", sa.String(64), nullable=False),
        sa.Column("source_type", sa.String(32)),
        sa.Column("sensitivity_class", sa.String(16)),
        sa.Column("source_system_access_status", sa.String(24), nullable=False, server_default="not_requested"),
        sa.Column("location_descriptor", sa.String(255)),
        *_common_columns(),
        **MYSQL,
    )
    op.create_index("ix_source_system_references_client_id", "source_system_references", ["client_id"])
    op.create_index("ix_source_system_references_engagement_id", "source_system_references", ["engagement_id"])
    op.create_index(
        "ix_source_system_references_access_status", "source_system_references",
        ["source_system_access_status"],
    )
    _common_indexes("source_system_references")

    # financial_impact_estimates
    op.create_table(
        "financial_impact_estimates",
        sa.Column("id", sa.String(64), primary_key=True),
        sa.Column("client_id", sa.String(64)),
        sa.Column("engagement_id", sa.String(64), nullable=False),
        sa.Column("related_finding_id", sa.String(64)),
        sa.Column("impact_type", sa.String(24)),
        sa.Column("amount_low", sa.Numeric(18, 2)),
        sa.Column("amount_high", sa.Numeric(18, 2)),
        sa.Column("currency", sa.String(3)),
        sa.Column("period", sa.String(24)),
        sa.Column("verification_status", sa.String(16)),
        sa.Column("financial_impact_status", sa.String(32), nullable=False, server_default="not_assessed"),
        sa.Column("client_facing_approved", sa.Boolean(), nullable=False, server_default=sa.text("0")),
        *_common_columns(),
        **MYSQL,
    )
    op.create_index("ix_financial_impact_estimates_client_id", "financial_impact_estimates", ["client_id"])
    op.create_index("ix_financial_impact_estimates_engagement_id", "financial_impact_estimates", ["engagement_id"])
    op.create_index(
        "ix_financial_impact_estimates_status", "financial_impact_estimates",
        ["financial_impact_status"],
    )
    _common_indexes("financial_impact_estimates")

    # resolver_capsule_records
    op.create_table(
        "resolver_capsule_records",
        sa.Column("id", sa.String(64), primary_key=True),
        sa.Column("client_id", sa.String(64)),
        sa.Column("engagement_id", sa.String(64)),
        sa.Column("capsule_scope", sa.String(24)),
        sa.Column("sensitivity_class", sa.String(16)),
        sa.Column("capsule_status", sa.String(32), nullable=False, server_default="draft_capsule"),
        *_common_columns(),
        **MYSQL,
    )
    op.create_index("ix_resolver_capsule_records_client_id", "resolver_capsule_records", ["client_id"])
    op.create_index("ix_resolver_capsule_records_engagement_id", "resolver_capsule_records", ["engagement_id"])
    op.create_index("ix_resolver_capsule_records_capsule_status", "resolver_capsule_records", ["capsule_status"])
    _common_indexes("resolver_capsule_records")

    # review_records
    op.create_table(
        "review_records",
        sa.Column("id", sa.String(64), primary_key=True),
        sa.Column("client_id", sa.String(64)),
        sa.Column("engagement_id", sa.String(64)),
        sa.Column("target_id", sa.String(64), nullable=False),
        sa.Column("previous_status", sa.String(32)),
        sa.Column("new_status", sa.String(32)),
        sa.Column("reviewer", sa.String(128)),
        sa.Column("reason", sa.Text()),
        *_common_columns(),
        **MYSQL,
    )
    op.create_index("ix_review_records_client_id", "review_records", ["client_id"])
    op.create_index("ix_review_records_engagement_id", "review_records", ["engagement_id"])
    op.create_index("ix_review_records_target_id", "review_records", ["target_id"])
    _common_indexes("review_records")

    # agent_run_records
    op.create_table(
        "agent_run_records",
        sa.Column("id", sa.String(64), primary_key=True),
        sa.Column("client_id", sa.String(64)),
        sa.Column("engagement_id", sa.String(64)),
        sa.Column("prompt_contract_ref", sa.String(255)),
        sa.Column("model_label", sa.String(128)),
        sa.Column("started_at", sa.DateTime()),
        sa.Column("finished_at", sa.DateTime()),
        *_common_columns(),
        **MYSQL,
    )
    op.create_index("ix_agent_run_records_client_id", "agent_run_records", ["client_id"])
    op.create_index("ix_agent_run_records_engagement_id", "agent_run_records", ["engagement_id"])
    _common_indexes("agent_run_records")

    # capsule_publication_candidates
    op.create_table(
        "capsule_publication_candidates",
        sa.Column("id", sa.String(64), primary_key=True),
        sa.Column("client_id", sa.String(64)),
        sa.Column("engagement_id", sa.String(64)),
        sa.Column("capsule_id", sa.String(64), nullable=False),
        sa.Column("resolver_target", sa.String(32)),
        sa.Column("client_facing_approval_status", sa.String(32)),
        sa.Column("approval_decision", sa.String(32)),
        *_common_columns(),
        **MYSQL,
    )
    op.create_index("ix_capsule_publication_candidates_client_id", "capsule_publication_candidates", ["client_id"])
    op.create_index(
        "ix_capsule_publication_candidates_engagement_id", "capsule_publication_candidates", ["engagement_id"]
    )
    op.create_index("ix_capsule_publication_candidates_capsule_id", "capsule_publication_candidates", ["capsule_id"])
    _common_indexes("capsule_publication_candidates")

    # source_ingestion_records
    op.create_table(
        "source_ingestion_records",
        sa.Column("id", sa.String(64), primary_key=True),
        sa.Column("client_id", sa.String(64)),
        sa.Column("engagement_id", sa.String(64)),
        sa.Column("source_reference_id", sa.String(64), nullable=False),
        sa.Column("captured_at", sa.DateTime()),
        *_common_columns(),
        **MYSQL,
    )
    op.create_index("ix_source_ingestion_records_client_id", "source_ingestion_records", ["client_id"])
    op.create_index("ix_source_ingestion_records_engagement_id", "source_ingestion_records", ["engagement_id"])
    op.create_index("ix_source_ingestion_records_source_reference_id", "source_ingestion_records", ["source_reference_id"])
    _common_indexes("source_ingestion_records")


def downgrade() -> None:
    for table in (
        "source_ingestion_records",
        "capsule_publication_candidates",
        "agent_run_records",
        "review_records",
        "resolver_capsule_records",
        "financial_impact_estimates",
        "source_system_references",
        "evidence_references",
        "engagement_records",
        "engagements",
        "clients",
    ):
        op.drop_table(table)
