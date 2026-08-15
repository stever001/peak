"""Phase 44: pin a deterministic collation on governed string columns (ALTER only, no data).

Applies ``utf8mb4_bin`` to the **211 governed deterministic columns** across all 18 tables — the
columns whose comparisons decide identity, authorization, uniqueness, or integrity.

**Why.** MySQL's server default for ``utf8mb4`` is case- and accent-INSENSITIVE
(``utf8mb4_0900_ai_ci`` on MySQL 8). Nothing in this schema previously pinned a collation, so every
governed comparison inherited that default. The sharpest consequence is the controlled-writer
replay boundary carried by 11 tables::

    UNIQUE (owner_id, client_id, engagement_id, idempotency_key)

Under a case-insensitive collation ``idem-key-1`` and ``idem-KEY-1`` are one key, so two
intentionally distinct writes collapse into an idempotent replay. Writers persist the key verbatim
with no case normalization, so nothing upstream mitigates it. See
docs/GOVERNED_MYSQL_COLLATION_POLICY.md and docs/PRODUCTION_MYSQL_COLLATION_VERIFICATION.md.

**Why ``utf8mb4_bin``.** Governed values are ASCII by construction — refs match
``[A-Za-z0-9_.:/-]`` and fingerprints are sha256 hex — so Unicode-aware ordering buys nothing and
byte comparison is the strictest available guarantee. ``utf8mb4_0900_as_cs`` is a documented
alternative but is MySQL 8.0+ only; this migration deliberately uses the broadly supported one.

**Scope.** Only the deterministic-required governed classes are altered: ``governed_identifier``,
``governed_scope``, ``governed_idempotency``, and ``governed_hash_or_fingerprint``. Deliberately
**excluded**: ``ordinary_text`` (9 columns) and ``json_or_details_text`` (3), which carry no
equality boundary; and ``governed_enum_status`` (85), which the Phase 42 audit classifies as
deterministic-*preferred* rather than *required* because controlled writers already gate those
values against closed vocabularies with case-sensitive Python membership tests.

**Uniqueness direction is safe.** Moving from a case-insensitive to a case-sensitive collation makes
a unique index *more* discriminating: values that previously collided become distinct. Every
existing row was already unique under the looser rule, so it stays unique under the stricter one —
this direction cannot produce new duplicate-key violations. The real behavioral change is that
lookups become case-sensitive.

**This migration is ALTER-only.** It creates and drops no table, adds and drops no column, changes
no index or constraint name, and contains no INSERT/UPDATE/DELETE, no seed data, and no client
data. It rewrites no earlier migration.

**Dialect handling.** The collation change is issued only for MySQL/MariaDB. On SQLite — which
backs the fast local structural-smoke harnesses — it is a deliberate **no-op**, because SQLite has
no such collation and cannot represent this guarantee. A green SQLite run therefore proves the
migration chain still applies; it proves **nothing** about MySQL collation. Only
``make production-mysql-collation-verify`` can confirm the deployed database.

**Production execution is a separate, separately approved operation.** Phase 44 adds this migration
to source control only. It has not been run against production.

Revision ID: 013_governed_identifier_collation_policy
Revises: 012_internal_report_review_packet_decisions
Create Date: (static; no timestamp committed)
"""

from __future__ import annotations

from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import mysql

revision = "013_governed_identifier_collation_policy"
down_revision = "012_internal_report_review_packet_decisions"
branch_labels = None
depends_on = None

#: The deterministic collation pinned by this migration. Mirrors
#: ``peak.db.base.GOVERNED_COLLATION``; kept as a literal so the migration never imports
#: application models at runtime.
GOVERNED_COLLATION = "utf8mb4_bin"

#: Dialects that can express a MySQL collation. Everything else is a no-op.
MYSQL_DIALECTS = ("mysql", "mariadb")

#: Every governed column this migration alters, as ``(table, column, length, nullable)``.
#: Explicit and static by design: reviewable in the diff, and no application model is imported at
#: migration time. Generated from the Phase 42 governed-column classifier and asserted against the
#: live models by tests/validate_phase44_governed_identifier_collation_migration.py.
GOVERNED_COLUMNS = (
    # agent_run_records (11 governed columns)
    ("agent_run_records", "agent_run_id", 64, True),
    ("agent_run_records", "authorization_scope", 48, True),
    ("agent_run_records", "client_id", 64, True),
    ("agent_run_records", "created_by", 128, True),
    ("agent_run_records", "engagement_id", 64, True),
    ("agent_run_records", "id", 64, False),
    ("agent_run_records", "idempotency_key", 128, True),
    ("agent_run_records", "owner_id", 128, True),
    ("agent_run_records", "payload_fingerprint", 64, True),
    ("agent_run_records", "prompt_contract_ref", 255, True),
    ("agent_run_records", "updated_by", 128, True),
    # agent_task_queue_records (11 governed columns)
    ("agent_task_queue_records", "agent_run_id", 64, True),
    ("agent_task_queue_records", "authorization_scope", 48, True),
    ("agent_task_queue_records", "client_id", 64, True),
    ("agent_task_queue_records", "created_by", 128, True),
    ("agent_task_queue_records", "engagement_id", 64, True),
    ("agent_task_queue_records", "id", 64, False),
    ("agent_task_queue_records", "idempotency_key", 128, True),
    ("agent_task_queue_records", "owner_id", 128, True),
    ("agent_task_queue_records", "payload_fingerprint", 64, True),
    ("agent_task_queue_records", "source_ingestion_record_id", 64, True),
    ("agent_task_queue_records", "updated_by", 128, True),
    # capsule_publication_candidates (10 governed columns)
    ("capsule_publication_candidates", "agent_run_id", 64, True),
    ("capsule_publication_candidates", "authorization_scope", 48, True),
    ("capsule_publication_candidates", "capsule_id", 64, False),
    ("capsule_publication_candidates", "client_id", 64, True),
    ("capsule_publication_candidates", "created_by", 128, True),
    ("capsule_publication_candidates", "engagement_id", 64, True),
    ("capsule_publication_candidates", "id", 64, False),
    ("capsule_publication_candidates", "owner_id", 128, True),
    ("capsule_publication_candidates", "resolver_target", 32, True),
    ("capsule_publication_candidates", "updated_by", 128, True),
    # clients (6 governed columns)
    ("clients", "agent_run_id", 64, True),
    ("clients", "authorization_scope", 48, True),
    ("clients", "created_by", 128, True),
    ("clients", "id", 64, False),
    ("clients", "owner_id", 128, True),
    ("clients", "updated_by", 128, True),
    # engagement_records (9 governed columns)
    ("engagement_records", "agent_run_id", 64, True),
    ("engagement_records", "authorization_scope", 48, True),
    ("engagement_records", "client_id", 64, False),
    ("engagement_records", "created_by", 128, True),
    ("engagement_records", "data_class", 32, True),
    ("engagement_records", "engagement_id", 64, False),
    ("engagement_records", "id", 64, False),
    ("engagement_records", "owner_id", 128, True),
    ("engagement_records", "updated_by", 128, True),
    # engagements (7 governed columns)
    ("engagements", "agent_run_id", 64, True),
    ("engagements", "authorization_scope", 48, True),
    ("engagements", "client_id", 64, False),
    ("engagements", "created_by", 128, True),
    ("engagements", "id", 64, False),
    ("engagements", "owner_id", 128, True),
    ("engagements", "updated_by", 128, True),
    # evidence_references (10 governed columns)
    ("evidence_references", "agent_run_id", 64, True),
    ("evidence_references", "authorization_scope", 48, True),
    ("evidence_references", "client_id", 64, True),
    ("evidence_references", "created_by", 128, True),
    ("evidence_references", "engagement_id", 64, True),
    ("evidence_references", "id", 64, False),
    ("evidence_references", "idempotency_key", 128, True),
    ("evidence_references", "owner_id", 128, True),
    ("evidence_references", "payload_fingerprint", 64, True),
    ("evidence_references", "updated_by", 128, True),
    # financial_impact_estimates (9 governed columns)
    ("financial_impact_estimates", "agent_run_id", 64, True),
    ("financial_impact_estimates", "authorization_scope", 48, True),
    ("financial_impact_estimates", "client_id", 64, True),
    ("financial_impact_estimates", "created_by", 128, True),
    ("financial_impact_estimates", "engagement_id", 64, False),
    ("financial_impact_estimates", "id", 64, False),
    ("financial_impact_estimates", "owner_id", 128, True),
    ("financial_impact_estimates", "related_finding_id", 64, True),
    ("financial_impact_estimates", "updated_by", 128, True),
    # intake_note_records (15 governed columns)
    ("intake_note_records", "agent_run_id", 64, True),
    ("intake_note_records", "authorization_scope", 48, True),
    ("intake_note_records", "captured_by", 128, True),
    ("intake_note_records", "client_id", 64, True),
    ("intake_note_records", "created_by", 128, True),
    ("intake_note_records", "engagement_id", 64, True),
    ("intake_note_records", "id", 64, False),
    ("intake_note_records", "idempotency_key", 128, True),
    ("intake_note_records", "owner_id", 128, True),
    ("intake_note_records", "payload_fingerprint", 64, True),
    ("intake_note_records", "related_evidence_reference_id", 64, True),
    ("intake_note_records", "related_review_bundle_record_id", 64, True),
    ("intake_note_records", "source_ingestion_record_id", 64, True),
    ("intake_note_records", "source_ref", 128, True),
    ("intake_note_records", "updated_by", 128, True),
    # internal_assessment_report_drafts (14 governed columns)
    ("internal_assessment_report_drafts", "agent_run_id", 64, True),
    ("internal_assessment_report_drafts", "audience", 32, False),
    ("internal_assessment_report_drafts", "authorization_scope", 48, True),
    ("internal_assessment_report_drafts", "client_id", 64, True),
    ("internal_assessment_report_drafts", "created_by", 128, True),
    ("internal_assessment_report_drafts", "engagement_id", 64, True),
    ("internal_assessment_report_drafts", "id", 64, False),
    ("internal_assessment_report_drafts", "idempotency_key", 128, True),
    ("internal_assessment_report_drafts", "owner_id", 128, True),
    ("internal_assessment_report_drafts", "payload_fingerprint", 64, True),
    ("internal_assessment_report_drafts", "plan_fingerprint", 64, True),
    ("internal_assessment_report_drafts", "report_plan_id", 128, True),
    ("internal_assessment_report_drafts", "requested_by", 128, True),
    ("internal_assessment_report_drafts", "updated_by", 128, True),
    # internal_report_review_packet_decisions (22 governed columns)
    ("internal_report_review_packet_decisions", "agent_run_id", 64, True),
    ("internal_report_review_packet_decisions", "audience", 32, False),
    ("internal_report_review_packet_decisions", "authorization_scope", 48, True),
    ("internal_report_review_packet_decisions", "client_id", 64, True),
    ("internal_report_review_packet_decisions", "created_by", 128, True),
    ("internal_report_review_packet_decisions", "decision_scope", 48, False),
    ("internal_report_review_packet_decisions", "engagement_id", 64, True),
    ("internal_report_review_packet_decisions", "id", 64, False),
    ("internal_report_review_packet_decisions", "idempotency_key", 128, True),
    ("internal_report_review_packet_decisions", "internal_assessment_report_draft_id", 64, True),
    ("internal_report_review_packet_decisions", "internal_report_review_packet_id", 64, True),
    ("internal_report_review_packet_decisions", "owner_id", 128, True),
    ("internal_report_review_packet_decisions", "packet_payload_fingerprint", 64, True),
    ("internal_report_review_packet_decisions", "payload_fingerprint", 64, True),
    ("internal_report_review_packet_decisions", "plan_fingerprint", 64, True),
    ("internal_report_review_packet_decisions", "report_draft_payload_fingerprint", 64, True),
    ("internal_report_review_packet_decisions", "report_plan_id", 128, True),
    ("internal_report_review_packet_decisions", "requested_by", 128, True),
    ("internal_report_review_packet_decisions", "reviewer_ref", 128, True),
    ("internal_report_review_packet_decisions", "source_packet_table", 64, True),
    ("internal_report_review_packet_decisions", "source_report_draft_table", 64, True),
    ("internal_report_review_packet_decisions", "updated_by", 128, True),
    # internal_report_review_packets (19 governed columns)
    ("internal_report_review_packets", "agent_run_id", 64, True),
    ("internal_report_review_packets", "assigned_reviewer", 128, True),
    ("internal_report_review_packets", "audience", 32, False),
    ("internal_report_review_packets", "authorization_scope", 48, True),
    ("internal_report_review_packets", "client_id", 64, True),
    ("internal_report_review_packets", "created_by", 128, True),
    ("internal_report_review_packets", "engagement_id", 64, True),
    ("internal_report_review_packets", "id", 64, False),
    ("internal_report_review_packets", "idempotency_key", 128, True),
    ("internal_report_review_packets", "internal_assessment_report_draft_id", 64, True),
    ("internal_report_review_packets", "owner_id", 128, True),
    ("internal_report_review_packets", "payload_fingerprint", 64, True),
    ("internal_report_review_packets", "plan_fingerprint", 64, True),
    ("internal_report_review_packets", "report_draft_payload_fingerprint", 64, True),
    ("internal_report_review_packets", "report_plan_id", 128, True),
    ("internal_report_review_packets", "requested_by", 128, True),
    ("internal_report_review_packets", "reviewer_decision_record_id", 64, True),
    ("internal_report_review_packets", "source_report_draft_table", 64, True),
    ("internal_report_review_packets", "updated_by", 128, True),
    # internal_reviewer_decision_records (13 governed columns)
    ("internal_reviewer_decision_records", "agent_run_id", 64, True),
    ("internal_reviewer_decision_records", "authorization_scope", 48, True),
    ("internal_reviewer_decision_records", "client_id", 64, True),
    ("internal_reviewer_decision_records", "created_by", 128, True),
    ("internal_reviewer_decision_records", "engagement_id", 64, True),
    ("internal_reviewer_decision_records", "id", 64, False),
    ("internal_reviewer_decision_records", "idempotency_key", 128, True),
    ("internal_reviewer_decision_records", "owner_id", 128, True),
    ("internal_reviewer_decision_records", "payload_fingerprint", 64, True),
    ("internal_reviewer_decision_records", "review_bundle_draft_ref", 128, True),
    ("internal_reviewer_decision_records", "review_bundle_record_id", 64, True),
    ("internal_reviewer_decision_records", "review_bundle_ref", 128, True),
    ("internal_reviewer_decision_records", "updated_by", 128, True),
    # resolver_capsule_records (10 governed columns)
    ("resolver_capsule_records", "agent_run_id", 64, True),
    ("resolver_capsule_records", "authorization_scope", 48, True),
    ("resolver_capsule_records", "capsule_scope", 24, True),
    ("resolver_capsule_records", "client_id", 64, True),
    ("resolver_capsule_records", "created_by", 128, True),
    ("resolver_capsule_records", "engagement_id", 64, True),
    ("resolver_capsule_records", "id", 64, False),
    ("resolver_capsule_records", "owner_id", 128, True),
    ("resolver_capsule_records", "sensitivity_class", 16, True),
    ("resolver_capsule_records", "updated_by", 128, True),
    # review_bundle_records (12 governed columns)
    ("review_bundle_records", "agent_run_id", 64, True),
    ("review_bundle_records", "authorization_scope", 48, True),
    ("review_bundle_records", "client_id", 64, True),
    ("review_bundle_records", "created_by", 128, True),
    ("review_bundle_records", "engagement_id", 64, True),
    ("review_bundle_records", "id", 64, False),
    ("review_bundle_records", "idempotency_key", 128, True),
    ("review_bundle_records", "owner_id", 128, True),
    ("review_bundle_records", "packet_processing_receipt_ref", 128, True),
    ("review_bundle_records", "payload_fingerprint", 64, True),
    ("review_bundle_records", "review_scope", 48, True),
    ("review_bundle_records", "updated_by", 128, True),
    # review_records (13 governed columns)
    ("review_records", "agent_run_id", 64, True),
    ("review_records", "authorization_scope", 48, True),
    ("review_records", "client_id", 64, True),
    ("review_records", "created_by", 128, True),
    ("review_records", "engagement_id", 64, True),
    ("review_records", "id", 64, False),
    ("review_records", "idempotency_key", 128, True),
    ("review_records", "owner_id", 128, True),
    ("review_records", "payload_fingerprint", 64, True),
    ("review_records", "reviewer", 128, True),
    ("review_records", "subject_record_type", 48, True),
    ("review_records", "target_id", 64, False),
    ("review_records", "updated_by", 128, True),
    # source_ingestion_records (11 governed columns)
    ("source_ingestion_records", "agent_run_id", 64, True),
    ("source_ingestion_records", "authorization_scope", 48, True),
    ("source_ingestion_records", "client_id", 64, True),
    ("source_ingestion_records", "created_by", 128, True),
    ("source_ingestion_records", "engagement_id", 64, True),
    ("source_ingestion_records", "id", 64, False),
    ("source_ingestion_records", "idempotency_key", 128, True),
    ("source_ingestion_records", "owner_id", 128, True),
    ("source_ingestion_records", "payload_fingerprint", 64, True),
    ("source_ingestion_records", "source_reference_id", 64, False),
    ("source_ingestion_records", "updated_by", 128, True),
    # source_system_references (9 governed columns)
    ("source_system_references", "agent_run_id", 64, True),
    ("source_system_references", "authorization_scope", 48, True),
    ("source_system_references", "client_id", 64, True),
    ("source_system_references", "created_by", 128, True),
    ("source_system_references", "engagement_id", 64, False),
    ("source_system_references", "id", 64, False),
    ("source_system_references", "owner_id", 128, True),
    ("source_system_references", "sensitivity_class", 16, True),
    ("source_system_references", "updated_by", 128, True),
)


def _alter_collation(collation) -> None:
    """Re-declare every governed column with (or without) an explicit collation.

    ``collation=None`` restores the prior posture: the column inherits the table default, which is
    what every governed column did before this migration.
    """
    bind = op.get_bind()
    if bind.dialect.name not in MYSQL_DIALECTS:
        # SQLite (local structural smoke) cannot express a MySQL collation. Skipping keeps the
        # migration chain applicable locally without implying SQLite validated anything.
        return

    for table, column, length, nullable in GOVERNED_COLUMNS:
        op.alter_column(
            table,
            column,
            existing_type=mysql.VARCHAR(length),
            type_=mysql.VARCHAR(length, collation=collation) if collation
            else mysql.VARCHAR(length),
            existing_nullable=nullable,
        )


def upgrade() -> None:
    """Pin utf8mb4_bin on every governed column. No data is read, written, or moved."""
    _alter_collation(GOVERNED_COLLATION)


def downgrade() -> None:
    """Drop the explicit collation, returning governed columns to the table default.

    This is an honest revert rather than a restoration of a specific prior collation: no collation
    was ever pinned before this migration, so the prior state *was* "inherit the table default".
    Note the direction is the unsafe one — relaxing a unique index from case-sensitive back to
    case-insensitive can surface duplicate-key violations if case-variant rows were written while
    the stricter collation was in force. Treat downgrade as a rollback of last resort.
    """
    _alter_collation(None)
