"""SQLAlchemy models for the controlled engagement database (MySQL).

Minimal Phase 11 scaffold aligned to the Phase 8 architecture contracts and Phase 9
governance states. Schema only — **no data, no seed records, no fixtures**. IDs are
prefixed strings; governance/audit fields are real columns. Relationships are kept
simple: `client_id` / `engagement_id` are indexed string references (referential
integrity is enforced app-side for now, not via hard FK constraints).
"""

from __future__ import annotations

from datetime import datetime
from typing import Optional

from sqlalchemy import Boolean, DateTime, Numeric, String, Text, UniqueConstraint
from sqlalchemy.orm import Mapped, mapped_column

from .base import MYSQL_TABLE_ARGS, AuditMixin, Base, GovernanceMixin


class Client(Base, GovernanceMixin, AuditMixin):
    __tablename__ = "clients"
    __table_args__ = MYSQL_TABLE_ARGS
    # id convention: client_<slug>
    id: Mapped[str] = mapped_column(String(64), primary_key=True)
    organization_label: Mapped[Optional[str]] = mapped_column(String(255))


class Engagement(Base, GovernanceMixin, AuditMixin):
    __tablename__ = "engagements"
    __table_args__ = MYSQL_TABLE_ARGS
    # id convention: eng_<slug>
    id: Mapped[str] = mapped_column(String(64), primary_key=True)
    client_id: Mapped[str] = mapped_column(String(64), index=True, nullable=False)
    engagement_label: Mapped[Optional[str]] = mapped_column(String(255))
    status: Mapped[Optional[str]] = mapped_column(String(32))  # prospective/active/on_hold/complete/closed


class EngagementRecord(Base, GovernanceMixin, AuditMixin):
    __tablename__ = "engagement_records"
    __table_args__ = MYSQL_TABLE_ARGS
    # id convention: engrec_<slug>
    id: Mapped[str] = mapped_column(String(64), primary_key=True)
    client_id: Mapped[str] = mapped_column(String(64), index=True, nullable=False)
    engagement_id: Mapped[str] = mapped_column(String(64), index=True, nullable=False)
    data_class: Mapped[Optional[str]] = mapped_column(String(32))  # live_client_data


class EvidenceReference(Base, GovernanceMixin, AuditMixin):
    __tablename__ = "evidence_references"
    # Phase 21: DB-enforced idempotency for the controlled evidence writer. The uniqueness
    # boundary includes identity context so an idempotency key cannot collide across
    # owner / client / engagement. See docs/EVIDENCE_IDEMPOTENCY_POLICY.md.
    __table_args__ = (
        UniqueConstraint(
            "owner_id",
            "client_id",
            "engagement_id",
            "idempotency_key",
            name="uq_evidence_references_idem",
        ),
        MYSQL_TABLE_ARGS,
    )
    # id convention: evid_<slug>
    id: Mapped[str] = mapped_column(String(64), primary_key=True)
    client_id: Mapped[Optional[str]] = mapped_column(String(64), index=True)
    engagement_id: Mapped[Optional[str]] = mapped_column(String(64), index=True)
    evidence_type: Mapped[Optional[str]] = mapped_column(String(48))
    source_type: Mapped[Optional[str]] = mapped_column(String(48))
    reliability: Mapped[Optional[str]] = mapped_column(String(16))
    evidence_status: Mapped[str] = mapped_column(String(32), index=True, default="collected")
    sensitive_data_flag: Mapped[bool] = mapped_column(Boolean, default=False)
    summary: Mapped[Optional[str]] = mapped_column(Text)  # non-sensitive summary only
    # Phase 21 controlled-writer fields. output_status is governance-relevant (a real
    # column, not JSON); idempotency_key + payload_fingerprint back replay/replay-conflict
    # detection. Normalized detail (title, areas, etc.) remains in details_json.
    output_status: Mapped[str] = mapped_column(String(32), index=True, default="draft")
    idempotency_key: Mapped[Optional[str]] = mapped_column(String(128), index=True)
    payload_fingerprint: Mapped[Optional[str]] = mapped_column(String(64))


class SourceSystemReference(Base, GovernanceMixin, AuditMixin):
    __tablename__ = "source_system_references"
    __table_args__ = MYSQL_TABLE_ARGS
    # id convention: src_<slug>
    id: Mapped[str] = mapped_column(String(64), primary_key=True)
    client_id: Mapped[Optional[str]] = mapped_column(String(64), index=True)
    engagement_id: Mapped[str] = mapped_column(String(64), index=True, nullable=False)
    source_type: Mapped[Optional[str]] = mapped_column(String(32))
    sensitivity_class: Mapped[Optional[str]] = mapped_column(String(16))
    source_system_access_status: Mapped[str] = mapped_column(String(24), index=True, default="not_requested")
    location_descriptor: Mapped[Optional[str]] = mapped_column(String(255))


class FinancialImpactEstimate(Base, GovernanceMixin, AuditMixin):
    __tablename__ = "financial_impact_estimates"
    __table_args__ = MYSQL_TABLE_ARGS
    # id convention: fie_<slug>
    id: Mapped[str] = mapped_column(String(64), primary_key=True)
    client_id: Mapped[Optional[str]] = mapped_column(String(64), index=True)
    engagement_id: Mapped[str] = mapped_column(String(64), index=True, nullable=False)
    related_finding_id: Mapped[Optional[str]] = mapped_column(String(64))
    impact_type: Mapped[Optional[str]] = mapped_column(String(24))
    amount_low: Mapped[Optional[float]] = mapped_column(Numeric(18, 2))
    amount_high: Mapped[Optional[float]] = mapped_column(Numeric(18, 2))
    currency: Mapped[Optional[str]] = mapped_column(String(3))
    period: Mapped[Optional[str]] = mapped_column(String(24))
    verification_status: Mapped[Optional[str]] = mapped_column(String(16))  # unverified/reported/verified
    financial_impact_status: Mapped[str] = mapped_column(String(32), index=True, default="not_assessed")
    client_facing_approved: Mapped[bool] = mapped_column(Boolean, default=False)


class ResolverCapsuleRecord(Base, GovernanceMixin, AuditMixin):
    __tablename__ = "resolver_capsule_records"
    __table_args__ = MYSQL_TABLE_ARGS
    # id convention: cap_<slug>
    id: Mapped[str] = mapped_column(String(64), primary_key=True)
    client_id: Mapped[Optional[str]] = mapped_column(String(64), index=True)
    engagement_id: Mapped[Optional[str]] = mapped_column(String(64), index=True)
    capsule_scope: Mapped[Optional[str]] = mapped_column(String(24))  # peak_methodology/client_private/fixture_test
    sensitivity_class: Mapped[Optional[str]] = mapped_column(String(16))
    capsule_status: Mapped[str] = mapped_column(String(32), index=True, default="draft_capsule")


class ReviewRecord(Base, GovernanceMixin, AuditMixin):
    __tablename__ = "review_records"
    __table_args__ = MYSQL_TABLE_ARGS
    # id convention: rev_<slug>
    id: Mapped[str] = mapped_column(String(64), primary_key=True)
    client_id: Mapped[Optional[str]] = mapped_column(String(64), index=True)
    engagement_id: Mapped[Optional[str]] = mapped_column(String(64), index=True)
    target_id: Mapped[str] = mapped_column(String(64), index=True, nullable=False)
    previous_status: Mapped[Optional[str]] = mapped_column(String(32))
    new_status: Mapped[Optional[str]] = mapped_column(String(32))
    reviewer: Mapped[Optional[str]] = mapped_column(String(128))
    reason: Mapped[Optional[str]] = mapped_column(Text)


class AgentRunRecord(Base, GovernanceMixin, AuditMixin):
    __tablename__ = "agent_run_records"
    # Phase 20: DB-enforced idempotency for the controlled agent-run writer. The uniqueness
    # boundary includes identity context so an idempotency key cannot collide across
    # owner / client / engagement. See docs/AGENT_RUN_IDEMPOTENCY_POLICY.md.
    __table_args__ = (
        UniqueConstraint(
            "owner_id",
            "client_id",
            "engagement_id",
            "idempotency_key",
            name="uq_agent_run_records_idem",
        ),
        MYSQL_TABLE_ARGS,
    )
    # id convention: arun_<slug>
    id: Mapped[str] = mapped_column(String(64), primary_key=True)
    client_id: Mapped[Optional[str]] = mapped_column(String(64), index=True)
    engagement_id: Mapped[Optional[str]] = mapped_column(String(64), index=True)
    prompt_contract_ref: Mapped[Optional[str]] = mapped_column(String(255))
    model_label: Mapped[Optional[str]] = mapped_column(String(128))
    started_at: Mapped[Optional[datetime]] = mapped_column(DateTime)
    finished_at: Mapped[Optional[datetime]] = mapped_column(DateTime)
    # Phase 20 controlled-writer fields. output_status is governance-relevant (a real
    # column, not JSON); idempotency_key + payload_fingerprint back replay/replay-conflict
    # detection. agent_name/workflow/input ids remain non-governance detail in details_json.
    output_status: Mapped[str] = mapped_column(String(32), index=True, default="draft")
    idempotency_key: Mapped[Optional[str]] = mapped_column(String(128), index=True)
    payload_fingerprint: Mapped[Optional[str]] = mapped_column(String(64))
    # input/output record ids live in details_json (non-governance detail).


class CapsulePublicationCandidate(Base, GovernanceMixin, AuditMixin):
    __tablename__ = "capsule_publication_candidates"
    __table_args__ = MYSQL_TABLE_ARGS
    # id convention: capc_<slug>
    id: Mapped[str] = mapped_column(String(64), primary_key=True)
    client_id: Mapped[Optional[str]] = mapped_column(String(64), index=True)
    engagement_id: Mapped[Optional[str]] = mapped_column(String(64), index=True)
    capsule_id: Mapped[str] = mapped_column(String(64), index=True, nullable=False)
    resolver_target: Mapped[Optional[str]] = mapped_column(String(32))  # public_but_segregated / private
    client_facing_approval_status: Mapped[Optional[str]] = mapped_column(String(32))
    approval_decision: Mapped[Optional[str]] = mapped_column(String(32))


class SourceIngestionRecord(Base, GovernanceMixin, AuditMixin):
    __tablename__ = "source_ingestion_records"
    __table_args__ = MYSQL_TABLE_ARGS
    # id convention: ing_<slug>
    id: Mapped[str] = mapped_column(String(64), primary_key=True)
    client_id: Mapped[Optional[str]] = mapped_column(String(64), index=True)
    engagement_id: Mapped[Optional[str]] = mapped_column(String(64), index=True)
    source_reference_id: Mapped[str] = mapped_column(String(64), index=True, nullable=False)
    captured_at: Mapped[Optional[datetime]] = mapped_column(DateTime)


# Convenience list of all model classes (used by tooling/validation).
ALL_MODELS = [
    Client,
    Engagement,
    EngagementRecord,
    EvidenceReference,
    SourceSystemReference,
    FinancialImpactEstimate,
    ResolverCapsuleRecord,
    ReviewRecord,
    AgentRunRecord,
    CapsulePublicationCandidate,
    SourceIngestionRecord,
]
