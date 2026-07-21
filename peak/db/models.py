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
    # Phase 22: DB-enforced idempotency for the controlled review writer. The uniqueness
    # boundary includes identity context so an idempotency key cannot collide across
    # owner / client / engagement. See docs/REVIEW_IDEMPOTENCY_POLICY.md.
    __table_args__ = (
        UniqueConstraint(
            "owner_id",
            "client_id",
            "engagement_id",
            "idempotency_key",
            name="uq_review_records_idem",
        ),
        MYSQL_TABLE_ARGS,
    )
    # id convention: rev_<slug>
    id: Mapped[str] = mapped_column(String(64), primary_key=True)
    client_id: Mapped[Optional[str]] = mapped_column(String(64), index=True)
    engagement_id: Mapped[Optional[str]] = mapped_column(String(64), index=True)
    target_id: Mapped[str] = mapped_column(String(64), index=True, nullable=False)
    previous_status: Mapped[Optional[str]] = mapped_column(String(32))
    new_status: Mapped[Optional[str]] = mapped_column(String(32))
    reviewer: Mapped[Optional[str]] = mapped_column(String(128))
    reason: Mapped[Optional[str]] = mapped_column(Text)
    # Phase 22 controlled-writer fields. decision + authoritative are governance-relevant
    # (real columns); output_status mirrors Phases 20/21; subject_record_type disambiguates
    # the reviewed target (whose id is target_id). idempotency_key + payload_fingerprint back
    # replay/replay-conflict detection.
    decision: Mapped[Optional[str]] = mapped_column(String(48), index=True)
    subject_record_type: Mapped[Optional[str]] = mapped_column(String(48))
    authoritative: Mapped[bool] = mapped_column(Boolean, default=False)
    output_status: Mapped[str] = mapped_column(String(32), index=True, default="draft")
    idempotency_key: Mapped[Optional[str]] = mapped_column(String(128), index=True)
    payload_fingerprint: Mapped[Optional[str]] = mapped_column(String(64))


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
    # Phase 24: DB-enforced idempotency for the controlled source-ingestion writer. The
    # uniqueness boundary includes identity context so an idempotency key cannot collide
    # across owner / client / engagement. See docs/SOURCE_INGESTION_IDEMPOTENCY_POLICY.md.
    __table_args__ = (
        UniqueConstraint(
            "owner_id",
            "client_id",
            "engagement_id",
            "idempotency_key",
            name="uq_source_ingestion_records_idem",
        ),
        MYSQL_TABLE_ARGS,
    )
    # id convention: ing_<slug>
    id: Mapped[str] = mapped_column(String(64), primary_key=True)
    client_id: Mapped[Optional[str]] = mapped_column(String(64), index=True)
    engagement_id: Mapped[Optional[str]] = mapped_column(String(64), index=True)
    source_reference_id: Mapped[str] = mapped_column(String(64), index=True, nullable=False)
    captured_at: Mapped[Optional[datetime]] = mapped_column(DateTime)
    # Phase 24 controlled-writer fields. output_status is governance-relevant (a real column,
    # not JSON); idempotency_key + payload_fingerprint back replay/replay-conflict detection.
    # Packet metadata (schema, source type, location reference, hash) lives in details_json —
    # never the full packet payload or raw content.
    output_status: Mapped[str] = mapped_column(String(32), index=True, default="draft")
    idempotency_key: Mapped[Optional[str]] = mapped_column(String(128), index=True)
    payload_fingerprint: Mapped[Optional[str]] = mapped_column(String(64))


class AgentTaskQueueRecord(Base, GovernanceMixin, AuditMixin):
    __tablename__ = "agent_task_queue_records"
    # Phase 27: DB-enforced idempotency for the controlled agent-task-queue writer. The
    # uniqueness boundary includes identity context so an idempotency key cannot collide across
    # owner / client / engagement. See docs/AGENT_TASK_QUEUE_IDEMPOTENCY_POLICY.md.
    __table_args__ = (
        UniqueConstraint(
            "owner_id",
            "client_id",
            "engagement_id",
            "idempotency_key",
            name="uq_agent_task_queue_records_idem",
        ),
        MYSQL_TABLE_ARGS,
    )
    # id convention: atq_<slug>
    id: Mapped[str] = mapped_column(String(64), primary_key=True)
    client_id: Mapped[Optional[str]] = mapped_column(String(64), index=True)
    engagement_id: Mapped[Optional[str]] = mapped_column(String(64), index=True)
    agent_name: Mapped[str] = mapped_column(String(128), index=True, nullable=False)
    task_type: Mapped[Optional[str]] = mapped_column(String(64))
    requested_action: Mapped[Optional[str]] = mapped_column(String(64))
    source_ingestion_record_id: Mapped[Optional[str]] = mapped_column(String(64), index=True)
    # Governance / execution-posture — real columns (never JSON). "not-executed" is enforced.
    readiness_state: Mapped[Optional[str]] = mapped_column(String(48), index=True)
    output_status: Mapped[str] = mapped_column(String(32), index=True, default="draft")
    execution_status: Mapped[str] = mapped_column(String(32), index=True, default="not_executed")
    authoritative: Mapped[bool] = mapped_column(Boolean, default=False)
    client_facing_approved: Mapped[bool] = mapped_column(Boolean, default=False)
    capsule_candidate_ready: Mapped[bool] = mapped_column(Boolean, default=False)
    execution_allowed: Mapped[bool] = mapped_column(Boolean, default=False)
    llm_execution_allowed: Mapped[bool] = mapped_column(Boolean, default=False)
    agentnet_context_allowed: Mapped[bool] = mapped_column(Boolean, default=False)
    resolver_context_allowed: Mapped[bool] = mapped_column(Boolean, default=False)
    network_allowed: Mapped[bool] = mapped_column(Boolean, default=False)
    requires_human_review: Mapped[bool] = mapped_column(Boolean, default=True)
    # Phase 27 controlled-writer fields. idempotency_key + payload_fingerprint back
    # replay/replay-conflict detection. Safe references (task_input_ref, safe_input_summary,
    # evidence_reference_ids, packet_processing_run_ref, orchestration_ref, prompt_contract_path,
    # reasons, warnings) live in details_json — never raw payload/content.
    idempotency_key: Mapped[Optional[str]] = mapped_column(String(128), index=True)
    payload_fingerprint: Mapped[Optional[str]] = mapped_column(String(64))


class ReviewBundleRecord(Base, GovernanceMixin, AuditMixin):
    __tablename__ = "review_bundle_records"
    # Phase 30: DB-enforced idempotency for the controlled review-bundle writer. The uniqueness
    # boundary includes identity context so an idempotency key cannot collide across
    # owner / client / engagement. See docs/REVIEW_BUNDLE_IDEMPOTENCY_POLICY.md.
    __table_args__ = (
        UniqueConstraint(
            "owner_id",
            "client_id",
            "engagement_id",
            "idempotency_key",
            name="uq_review_bundle_records_idem",
        ),
        MYSQL_TABLE_ARGS,
    )
    # id convention: rvb_<slug>
    id: Mapped[str] = mapped_column(String(64), primary_key=True)
    client_id: Mapped[Optional[str]] = mapped_column(String(64), index=True)
    engagement_id: Mapped[Optional[str]] = mapped_column(String(64), index=True)
    packet_processing_receipt_ref: Mapped[Optional[str]] = mapped_column(String(128))
    reviewer_role: Mapped[Optional[str]] = mapped_column(String(64), index=True)
    review_reason: Mapped[Optional[str]] = mapped_column(String(255))
    review_scope: Mapped[Optional[str]] = mapped_column(String(48))
    # Governance / review-posture — real columns (never JSON). "not-approved" is enforced.
    output_status: Mapped[str] = mapped_column(String(32), index=True, default="draft")
    authoritative: Mapped[bool] = mapped_column(Boolean, default=False)
    client_facing_approved: Mapped[bool] = mapped_column(Boolean, default=False)
    capsule_candidate_ready: Mapped[bool] = mapped_column(Boolean, default=False)
    financial_verified: Mapped[bool] = mapped_column(Boolean, default=False)
    execution_allowed: Mapped[bool] = mapped_column(Boolean, default=False)
    approval_allowed: Mapped[bool] = mapped_column(Boolean, default=False)
    publication_allowed: Mapped[bool] = mapped_column(Boolean, default=False)
    requires_human_review: Mapped[bool] = mapped_column(Boolean, default=True)
    # Phase 30 controlled-writer fields. idempotency_key + payload_fingerprint back
    # replay/replay-conflict detection. Safe references (source/evidence/task-queue ids,
    # subject_refs, reasons, warnings) live in details_json — never raw payload/content or a
    # final review decision.
    idempotency_key: Mapped[Optional[str]] = mapped_column(String(128), index=True)
    payload_fingerprint: Mapped[Optional[str]] = mapped_column(String(64))


class InternalReviewerDecisionRecord(Base, GovernanceMixin, AuditMixin):
    __tablename__ = "internal_reviewer_decision_records"
    # Phase 33: DB-enforced idempotency for the controlled internal-reviewer-decision writer. The
    # uniqueness boundary includes identity context so an idempotency key cannot collide across
    # owner / client / engagement. See docs/INTERNAL_REVIEWER_DECISION_IDEMPOTENCY_POLICY.md.
    __table_args__ = (
        UniqueConstraint(
            "owner_id",
            "client_id",
            "engagement_id",
            "idempotency_key",
            name="uq_internal_reviewer_decision_records_idem",
        ),
        MYSQL_TABLE_ARGS,
    )
    # id convention: ird_<slug>
    id: Mapped[str] = mapped_column(String(64), primary_key=True)
    client_id: Mapped[Optional[str]] = mapped_column(String(64), index=True)
    engagement_id: Mapped[Optional[str]] = mapped_column(String(64), index=True)
    # Safe upstream references (never raw content).
    review_bundle_ref: Mapped[Optional[str]] = mapped_column(String(128))
    review_bundle_record_id: Mapped[Optional[str]] = mapped_column(String(64), index=True)
    review_bundle_draft_ref: Mapped[Optional[str]] = mapped_column(String(128))
    # Reviewer selections — short safe labels only.
    reviewer_role: Mapped[Optional[str]] = mapped_column(String(64), index=True)
    decision_intent: Mapped[Optional[str]] = mapped_column(String(48), index=True)
    decision_reason_code: Mapped[Optional[str]] = mapped_column(String(64))
    safe_decision_summary: Mapped[Optional[str]] = mapped_column(String(255))
    return_to_stage: Mapped[Optional[str]] = mapped_column(String(48))
    # Deterministic routing recommendation (server-derived; no action taken).
    route_to: Mapped[Optional[str]] = mapped_column(String(64), index=True)
    routing_reason_code: Mapped[Optional[str]] = mapped_column(String(64))
    # Governance / non-approval posture — real columns (never JSON). "non-approval" is enforced.
    output_status: Mapped[str] = mapped_column(String(32), index=True, default="draft")
    authoritative: Mapped[bool] = mapped_column(Boolean, default=False)
    client_facing_approved: Mapped[bool] = mapped_column(Boolean, default=False)
    capsule_candidate_ready: Mapped[bool] = mapped_column(Boolean, default=False)
    financial_verified: Mapped[bool] = mapped_column(Boolean, default=False)
    execution_allowed: Mapped[bool] = mapped_column(Boolean, default=False)
    approval_allowed: Mapped[bool] = mapped_column(Boolean, default=False)
    publication_allowed: Mapped[bool] = mapped_column(Boolean, default=False)
    requires_human_review: Mapped[bool] = mapped_column(Boolean, default=True)
    client_facing_output_created: Mapped[bool] = mapped_column(Boolean, default=False)
    review_approval_made: Mapped[bool] = mapped_column(Boolean, default=False)
    # Phase 33 controlled-writer fields. idempotency_key + payload_fingerprint back
    # replay/replay-conflict detection. Safe references (review-plan/evidence/source/task-queue
    # ids, requested_followup_actions, reasons, warnings) live in details_json — never raw
    # payload/content or a final review approval/decision.
    idempotency_key: Mapped[Optional[str]] = mapped_column(String(128), index=True)
    payload_fingerprint: Mapped[Optional[str]] = mapped_column(String(64))


class IntakeNoteRecord(Base, GovernanceMixin, AuditMixin):
    __tablename__ = "intake_note_records"
    # Phase 34: first-class DB-backed intake notes. DB-enforced idempotency for the controlled
    # intake-note writer; the uniqueness boundary includes identity context so an idempotency key
    # cannot collide across owner / client / engagement. Unlike prior summary-only records, this
    # table intentionally stores authorized operational note prose in ``note_text`` — acceptable
    # **only** in the managed DB, never in Git/fixtures/examples/logs/receipts. See
    # docs/INTAKE_NOTE_CONTROLLED_WRITER.md and docs/INTAKE_NOTE_IDEMPOTENCY_POLICY.md.
    __table_args__ = (
        UniqueConstraint(
            "owner_id",
            "client_id",
            "engagement_id",
            "idempotency_key",
            name="uq_intake_note_records_idem",
        ),
        MYSQL_TABLE_ARGS,
    )
    # id convention: intn_<slug>
    id: Mapped[str] = mapped_column(String(64), primary_key=True)
    client_id: Mapped[Optional[str]] = mapped_column(String(64), index=True)
    engagement_id: Mapped[Optional[str]] = mapped_column(String(64), index=True)
    note_type: Mapped[Optional[str]] = mapped_column(String(48), index=True)
    note_source: Mapped[Optional[str]] = mapped_column(String(48), index=True)
    # Authorized operational note prose — bounded; stored in the managed DB only.
    note_text: Mapped[Optional[str]] = mapped_column(Text)
    note_summary: Mapped[Optional[str]] = mapped_column(String(500))
    captured_by: Mapped[Optional[str]] = mapped_column(String(128))
    captured_role: Mapped[Optional[str]] = mapped_column(String(64))
    source_ref: Mapped[Optional[str]] = mapped_column(String(128))
    source_ingestion_record_id: Mapped[Optional[str]] = mapped_column(String(64), index=True)
    related_evidence_reference_id: Mapped[Optional[str]] = mapped_column(String(64), index=True)
    related_review_bundle_record_id: Mapped[Optional[str]] = mapped_column(String(64), index=True)
    # Governance / non-final posture — real columns (never JSON). "non-final" is enforced.
    client_facing_approved: Mapped[bool] = mapped_column(Boolean, default=False)
    financial_verified: Mapped[bool] = mapped_column(Boolean, default=False)
    capsule_candidate_ready: Mapped[bool] = mapped_column(Boolean, default=False)
    publication_allowed: Mapped[bool] = mapped_column(Boolean, default=False)
    execution_allowed: Mapped[bool] = mapped_column(Boolean, default=False)
    requires_human_review: Mapped[bool] = mapped_column(Boolean, default=True)
    # Phase 34 controlled-writer fields. idempotency_key + payload_fingerprint back
    # replay/replay-conflict detection (the fingerprint hashes note_text, never storing it twice).
    # Safe metadata (warnings, safe refs) lives in details_json — never a second copy of note_text.
    idempotency_key: Mapped[Optional[str]] = mapped_column(String(128), index=True)
    payload_fingerprint: Mapped[Optional[str]] = mapped_column(String(64))


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
    AgentTaskQueueRecord,
    ReviewBundleRecord,
    InternalReviewerDecisionRecord,
    IntakeNoteRecord,
]
