"""Phase 39: internal_report_review_packet_decisions table (schema only, no data).

Creates the new ``internal_report_review_packet_decisions`` table for the Phase 39 controlled
internal-report-review-packet-decision writer — the eleventh narrow live DB writer.

A row is a Peak human reviewer's **internal-only decision** on a Phase 38
``internal_report_review_packets`` row.

**Why a new table rather than reusing Phase 33.** The Phase 33
``internal_reviewer_decision_records`` writer cannot represent this artifact. It hard-requires a
review-bundle reference (``review_bundle_ref`` or ``review_bundle_record_id``), which an honest
packet decision does not have; and its explicit record mapping has a closed ``details_json`` key
set with no slot for packet / report-draft / plan linkage, so that provenance is silently dropped.
A decision written that way could not answer the core audit question — *which review packet was
this decision about?* This table preserves the chain packet -> report draft -> report plan.

The row stores **no report prose**: no final client-facing language, no raw intake-note / packet /
evidence / interview text, no source bytes, no generated agent output, no ROI or savings figure, no
client-facing approval, and no capsule / AgentNet publish payload. ``decision_scope`` is fixed at
``internal_report_review_packet`` and ``audience`` at ``internal``.

``review_status`` and ``lifecycle_status`` stay inside the Phase 9 governed vocabulary
(``needs_review`` / ``draft``); the decision-specific axis is the separate ``decision_status``
column, server-derived from ``decision_intent``.

The table carries the universal governance axes + audit fields, the internal-only posture columns
(all defaulting to the not-approved / not-verified / not-publishable / needs-review posture), and
the controlled-writer idempotency columns:

- ``idempotency_key`` — the caller-supplied key that backs replay safety;
- ``payload_fingerprint`` — a deterministic hash of the write payload/identity, used to tell an
  exact idempotent replay apart from a conflicting reuse of the same key;
- ``uq_internal_report_review_packet_decisions_idem`` — a UNIQUE index over
  ``(owner_id, client_id, engagement_id, idempotency_key)``.

**Index naming.** The table name is 39 characters, so the convention-derived
``ix_internal_report_review_packet_decisions_<col>`` would reach **78** characters for the longest
columns — over MySQL's 64-character identifier limit. Every index therefore uses the short explicit
``ix_irrpd_<col>`` prefix (max 44). SQLite would accept the long names silently, so they are pinned
here rather than discovered in managed MySQL. See the Phase 38 finding in
docs/PRODUCTION_PARITY_DB_VALIDATION.md.

This migration is schema only. **SQLite (used by the fast local structural smoke path) is not the
production-readiness proof path** — managed MySQL test/staging validation is required before
treating DB-backed functionality as production-ready (see
docs/PRODUCTION_PARITY_DB_VALIDATION.md and docs/MANAGED_MYSQL_PERSISTENCE_RUBRIC.md).

Additive and non-destructive: it creates exactly one new table and its indexes/constraint and
touches nothing else. There are **no INSERTs, no seed data, and no data of any kind**. The full
downgrade drops only this new table (and its indexes/constraint). See
docs/INTERNAL_REPORT_REVIEW_PACKET_DECISION_CONTROLLED_WRITER.md and
docs/INTERNAL_REPORT_REVIEW_PACKET_DECISION_IDEMPOTENCY_POLICY.md.

Revision ID: 012_internal_report_review_packet_decisions
Revises: 011_internal_report_review_packets
Create Date: (static; no timestamp committed)
"""

from __future__ import annotations

import sqlalchemy as sa
from alembic import op

# revision identifiers, used by Alembic.
revision = "012_internal_report_review_packet_decisions"
down_revision = "011_internal_report_review_packets"
branch_labels = None
depends_on = None

TABLE = "internal_report_review_packet_decisions"
UNIQUE_INDEX = "uq_internal_report_review_packet_decisions_idem"
# Short explicit prefix — see the module docstring (the convention-derived names exceed 64 chars).
IX_PREFIX = "ix_irrpd_"

# (index suffix, column). Suffixes are deliberately short so every identifier fits MySQL's limit.
INDEXED_COLUMNS = (
    ("client_id", "client_id"),
    ("engagement_id", "engagement_id"),
    ("owner_id", "owner_id"),
    ("authorization_scope", "authorization_scope"),
    ("review_status", "review_status"),
    ("lifecycle_status", "lifecycle_status"),
    ("agent_run_id", "agent_run_id"),
    ("packet_id", "internal_report_review_packet_id"),
    ("report_draft_id", "internal_assessment_report_draft_id"),
    ("report_plan_id", "report_plan_id"),
    ("plan_fingerprint", "plan_fingerprint"),
    ("audience", "audience"),
    ("decision_scope", "decision_scope"),
    ("decision_intent", "decision_intent"),
    ("decision_status", "decision_status"),
    ("idempotency_key", "idempotency_key"),
)
MYSQL = {"mysql_engine": "InnoDB", "mysql_charset": "utf8mb4"}


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
        # Audit chain: packet -> report draft -> report plan.
        sa.Column("internal_report_review_packet_id", sa.String(64)),
        sa.Column("source_packet_table", sa.String(64)),
        sa.Column("internal_assessment_report_draft_id", sa.String(64)),
        sa.Column("source_report_draft_table", sa.String(64)),
        sa.Column("report_plan_id", sa.String(128)),
        sa.Column("plan_fingerprint", sa.String(64)),
        sa.Column("report_draft_payload_fingerprint", sa.String(64)),
        sa.Column("packet_payload_fingerprint", sa.String(64)),
        sa.Column("requested_by", sa.String(128)),
        sa.Column("requester_role", sa.String(64)),
        sa.Column("reviewer_ref", sa.String(128)),
        # Reviewer selections — short safe labels only, from a closed vocabulary.
        sa.Column("decision_intent", sa.String(48)),
        sa.Column("safe_decision_summary", sa.String(255)),
        sa.Column("requested_followup_actions_json", sa.JSON()),
        # Decision-specific axis (server-derived); the governed axes stay Phase 9 vocabulary.
        sa.Column("decision_status", sa.String(32)),
        sa.Column("decision_scope", sa.String(48), nullable=False,
                  server_default="internal_report_review_packet"),
        sa.Column("audience", sa.String(32), nullable=False, server_default="internal"),
        sa.Column("reasons_json", sa.JSON()),
        sa.Column("warnings_json", sa.JSON()),
        # Governance / internal-only posture.
        sa.Column("client_facing_approved", sa.Boolean(), nullable=False,
                  server_default=sa.text("0")),
        sa.Column("review_approval_made", sa.Boolean(), nullable=False,
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
    for suffix, column in INDEXED_COLUMNS:
        op.create_index(f"{IX_PREFIX}{suffix}", TABLE, [column])
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
    for suffix, _ in reversed(INDEXED_COLUMNS):
        op.drop_index(f"{IX_PREFIX}{suffix}", table_name=TABLE)
    op.drop_table(TABLE)
