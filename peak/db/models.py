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

from sqlalchemy import (
    JSON, Boolean, DateTime, Index, Numeric, String, Text, UniqueConstraint,
)
from sqlalchemy import false as sa_false, true as sa_true
from sqlalchemy.orm import Mapped, mapped_column

from .base import MYSQL_TABLE_ARGS, AuditMixin, Base, GovernanceMixin, GovernedString


class Client(Base, GovernanceMixin, AuditMixin):
    __tablename__ = "clients"
    __table_args__ = MYSQL_TABLE_ARGS
    # id convention: client_<slug>
    id: Mapped[str] = mapped_column(GovernedString(64), primary_key=True)
    organization_label: Mapped[Optional[str]] = mapped_column(String(255))


class Engagement(Base, GovernanceMixin, AuditMixin):
    __tablename__ = "engagements"
    __table_args__ = MYSQL_TABLE_ARGS
    # id convention: eng_<slug>
    id: Mapped[str] = mapped_column(GovernedString(64), primary_key=True)
    client_id: Mapped[str] = mapped_column(GovernedString(64), index=True, nullable=False)
    engagement_label: Mapped[Optional[str]] = mapped_column(String(255))
    status: Mapped[Optional[str]] = mapped_column(String(32))  # prospective/active/on_hold/complete/closed
    # Phase 56 classification — real columns, never JSON/label/scope/id-prefix. `engagement_category`
    # is governed (byte-exact) so a case variant can never read as the same category. Defaults are
    # the safe direction: an unclassified row is a real client engagement, not a hidden test record.
    engagement_category: Mapped[str] = mapped_column(
        GovernedString(24), index=True, nullable=False, default="real_client",
        server_default="real_client")  # real_client / internal_test
    real_client_data: Mapped[bool] = mapped_column(
        Boolean, nullable=False, default=True, server_default=sa_true())
    client_accessible: Mapped[bool] = mapped_column(
        Boolean, nullable=False, default=True, server_default=sa_true())
    capsule_publication_authorized: Mapped[bool] = mapped_column(
        Boolean, nullable=False, default=False, server_default=sa_false())


class EngagementRecord(Base, GovernanceMixin, AuditMixin):
    __tablename__ = "engagement_records"
    __table_args__ = MYSQL_TABLE_ARGS
    # id convention: engrec_<slug>
    id: Mapped[str] = mapped_column(GovernedString(64), primary_key=True)
    client_id: Mapped[str] = mapped_column(GovernedString(64), index=True, nullable=False)
    engagement_id: Mapped[str] = mapped_column(GovernedString(64), index=True, nullable=False)
    data_class: Mapped[Optional[str]] = mapped_column(GovernedString(32))  # live_client_data


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
    id: Mapped[str] = mapped_column(GovernedString(64), primary_key=True)
    client_id: Mapped[Optional[str]] = mapped_column(GovernedString(64), index=True)
    engagement_id: Mapped[Optional[str]] = mapped_column(GovernedString(64), index=True)
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
    idempotency_key: Mapped[Optional[str]] = mapped_column(GovernedString(128), index=True)
    payload_fingerprint: Mapped[Optional[str]] = mapped_column(GovernedString(64))


class SourceSystemReference(Base, GovernanceMixin, AuditMixin):
    __tablename__ = "source_system_references"
    __table_args__ = MYSQL_TABLE_ARGS
    # id convention: src_<slug>
    id: Mapped[str] = mapped_column(GovernedString(64), primary_key=True)
    client_id: Mapped[Optional[str]] = mapped_column(GovernedString(64), index=True)
    engagement_id: Mapped[str] = mapped_column(GovernedString(64), index=True, nullable=False)
    source_type: Mapped[Optional[str]] = mapped_column(String(32))
    sensitivity_class: Mapped[Optional[str]] = mapped_column(GovernedString(16))
    source_system_access_status: Mapped[str] = mapped_column(String(24), index=True, default="not_requested")
    location_descriptor: Mapped[Optional[str]] = mapped_column(String(255))


class FinancialImpactEstimate(Base, GovernanceMixin, AuditMixin):
    __tablename__ = "financial_impact_estimates"
    __table_args__ = MYSQL_TABLE_ARGS
    # id convention: fie_<slug>
    id: Mapped[str] = mapped_column(GovernedString(64), primary_key=True)
    client_id: Mapped[Optional[str]] = mapped_column(GovernedString(64), index=True)
    engagement_id: Mapped[str] = mapped_column(GovernedString(64), index=True, nullable=False)
    related_finding_id: Mapped[Optional[str]] = mapped_column(GovernedString(64))
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
    id: Mapped[str] = mapped_column(GovernedString(64), primary_key=True)
    client_id: Mapped[Optional[str]] = mapped_column(GovernedString(64), index=True)
    engagement_id: Mapped[Optional[str]] = mapped_column(GovernedString(64), index=True)
    capsule_scope: Mapped[Optional[str]] = mapped_column(GovernedString(24))  # peak_methodology/client_private/fixture_test
    sensitivity_class: Mapped[Optional[str]] = mapped_column(GovernedString(16))
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
    id: Mapped[str] = mapped_column(GovernedString(64), primary_key=True)
    client_id: Mapped[Optional[str]] = mapped_column(GovernedString(64), index=True)
    engagement_id: Mapped[Optional[str]] = mapped_column(GovernedString(64), index=True)
    target_id: Mapped[str] = mapped_column(GovernedString(64), index=True, nullable=False)
    previous_status: Mapped[Optional[str]] = mapped_column(String(32))
    new_status: Mapped[Optional[str]] = mapped_column(String(32))
    reviewer: Mapped[Optional[str]] = mapped_column(GovernedString(128))
    reason: Mapped[Optional[str]] = mapped_column(Text)
    # Phase 22 controlled-writer fields. decision + authoritative are governance-relevant
    # (real columns); output_status mirrors Phases 20/21; subject_record_type disambiguates
    # the reviewed target (whose id is target_id). idempotency_key + payload_fingerprint back
    # replay/replay-conflict detection.
    decision: Mapped[Optional[str]] = mapped_column(String(48), index=True)
    subject_record_type: Mapped[Optional[str]] = mapped_column(GovernedString(48))
    authoritative: Mapped[bool] = mapped_column(Boolean, default=False)
    output_status: Mapped[str] = mapped_column(String(32), index=True, default="draft")
    idempotency_key: Mapped[Optional[str]] = mapped_column(GovernedString(128), index=True)
    payload_fingerprint: Mapped[Optional[str]] = mapped_column(GovernedString(64))


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
    id: Mapped[str] = mapped_column(GovernedString(64), primary_key=True)
    client_id: Mapped[Optional[str]] = mapped_column(GovernedString(64), index=True)
    engagement_id: Mapped[Optional[str]] = mapped_column(GovernedString(64), index=True)
    prompt_contract_ref: Mapped[Optional[str]] = mapped_column(GovernedString(255))
    model_label: Mapped[Optional[str]] = mapped_column(String(128))
    started_at: Mapped[Optional[datetime]] = mapped_column(DateTime)
    finished_at: Mapped[Optional[datetime]] = mapped_column(DateTime)
    # Phase 20 controlled-writer fields. output_status is governance-relevant (a real
    # column, not JSON); idempotency_key + payload_fingerprint back replay/replay-conflict
    # detection. agent_name/workflow/input ids remain non-governance detail in details_json.
    output_status: Mapped[str] = mapped_column(String(32), index=True, default="draft")
    idempotency_key: Mapped[Optional[str]] = mapped_column(GovernedString(128), index=True)
    payload_fingerprint: Mapped[Optional[str]] = mapped_column(GovernedString(64))
    # input/output record ids live in details_json (non-governance detail).


class CapsulePublicationCandidate(Base, GovernanceMixin, AuditMixin):
    __tablename__ = "capsule_publication_candidates"
    __table_args__ = MYSQL_TABLE_ARGS
    # id convention: capc_<slug>
    id: Mapped[str] = mapped_column(GovernedString(64), primary_key=True)
    client_id: Mapped[Optional[str]] = mapped_column(GovernedString(64), index=True)
    engagement_id: Mapped[Optional[str]] = mapped_column(GovernedString(64), index=True)
    capsule_id: Mapped[str] = mapped_column(GovernedString(64), index=True, nullable=False)
    resolver_target: Mapped[Optional[str]] = mapped_column(GovernedString(32))  # public_but_segregated / private
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
    id: Mapped[str] = mapped_column(GovernedString(64), primary_key=True)
    client_id: Mapped[Optional[str]] = mapped_column(GovernedString(64), index=True)
    engagement_id: Mapped[Optional[str]] = mapped_column(GovernedString(64), index=True)
    source_reference_id: Mapped[str] = mapped_column(GovernedString(64), index=True, nullable=False)
    captured_at: Mapped[Optional[datetime]] = mapped_column(DateTime)
    # Phase 24 controlled-writer fields. output_status is governance-relevant (a real column,
    # not JSON); idempotency_key + payload_fingerprint back replay/replay-conflict detection.
    # Packet metadata (schema, source type, location reference, hash) lives in details_json —
    # never the full packet payload or raw content.
    output_status: Mapped[str] = mapped_column(String(32), index=True, default="draft")
    idempotency_key: Mapped[Optional[str]] = mapped_column(GovernedString(128), index=True)
    payload_fingerprint: Mapped[Optional[str]] = mapped_column(GovernedString(64))


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
    id: Mapped[str] = mapped_column(GovernedString(64), primary_key=True)
    client_id: Mapped[Optional[str]] = mapped_column(GovernedString(64), index=True)
    engagement_id: Mapped[Optional[str]] = mapped_column(GovernedString(64), index=True)
    agent_name: Mapped[str] = mapped_column(String(128), index=True, nullable=False)
    task_type: Mapped[Optional[str]] = mapped_column(String(64))
    requested_action: Mapped[Optional[str]] = mapped_column(String(64))
    source_ingestion_record_id: Mapped[Optional[str]] = mapped_column(GovernedString(64), index=True)
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
    idempotency_key: Mapped[Optional[str]] = mapped_column(GovernedString(128), index=True)
    payload_fingerprint: Mapped[Optional[str]] = mapped_column(GovernedString(64))


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
    id: Mapped[str] = mapped_column(GovernedString(64), primary_key=True)
    client_id: Mapped[Optional[str]] = mapped_column(GovernedString(64), index=True)
    engagement_id: Mapped[Optional[str]] = mapped_column(GovernedString(64), index=True)
    packet_processing_receipt_ref: Mapped[Optional[str]] = mapped_column(GovernedString(128))
    reviewer_role: Mapped[Optional[str]] = mapped_column(String(64), index=True)
    review_reason: Mapped[Optional[str]] = mapped_column(String(255))
    review_scope: Mapped[Optional[str]] = mapped_column(GovernedString(48))
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
    idempotency_key: Mapped[Optional[str]] = mapped_column(GovernedString(128), index=True)
    payload_fingerprint: Mapped[Optional[str]] = mapped_column(GovernedString(64))


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
    id: Mapped[str] = mapped_column(GovernedString(64), primary_key=True)
    client_id: Mapped[Optional[str]] = mapped_column(GovernedString(64), index=True)
    engagement_id: Mapped[Optional[str]] = mapped_column(GovernedString(64), index=True)
    # Safe upstream references (never raw content).
    review_bundle_ref: Mapped[Optional[str]] = mapped_column(GovernedString(128))
    review_bundle_record_id: Mapped[Optional[str]] = mapped_column(GovernedString(64), index=True)
    review_bundle_draft_ref: Mapped[Optional[str]] = mapped_column(GovernedString(128))
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
    idempotency_key: Mapped[Optional[str]] = mapped_column(GovernedString(128), index=True)
    payload_fingerprint: Mapped[Optional[str]] = mapped_column(GovernedString(64))


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
    id: Mapped[str] = mapped_column(GovernedString(64), primary_key=True)
    client_id: Mapped[Optional[str]] = mapped_column(GovernedString(64), index=True)
    engagement_id: Mapped[Optional[str]] = mapped_column(GovernedString(64), index=True)
    note_type: Mapped[Optional[str]] = mapped_column(String(48), index=True)
    note_source: Mapped[Optional[str]] = mapped_column(String(48), index=True)
    # Authorized operational note prose — bounded; stored in the managed DB only.
    note_text: Mapped[Optional[str]] = mapped_column(Text)
    note_summary: Mapped[Optional[str]] = mapped_column(String(500))
    captured_by: Mapped[Optional[str]] = mapped_column(GovernedString(128))
    captured_role: Mapped[Optional[str]] = mapped_column(String(64))
    source_ref: Mapped[Optional[str]] = mapped_column(GovernedString(128))
    source_ingestion_record_id: Mapped[Optional[str]] = mapped_column(GovernedString(64), index=True)
    related_evidence_reference_id: Mapped[Optional[str]] = mapped_column(GovernedString(64), index=True)
    related_review_bundle_record_id: Mapped[Optional[str]] = mapped_column(GovernedString(64), index=True)
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
    idempotency_key: Mapped[Optional[str]] = mapped_column(GovernedString(128), index=True)
    payload_fingerprint: Mapped[Optional[str]] = mapped_column(GovernedString(64))


class InternalAssessmentReportDraftRecord(Base, GovernanceMixin, AuditMixin):
    __tablename__ = "internal_assessment_report_drafts"
    # Phase 37: the persistence counterpart to the Phase 36 internal assessment report planning
    # boundary. Stores a governed, **internal-only** report *plan* artifact — section metadata,
    # reference-only evidence traces, finding/recommendation candidate slots, open gaps, and
    # future-gate placeholders. It stores **no report prose**: no final client-facing language, no
    # raw note/packet/evidence/interview text, no generated agent output, no ROI figure, and no
    # approval decision. ``output_status`` is fixed at ``plan_persisted`` so a row can never be
    # misread as a drafted report. DB-enforced idempotency mirrors the prior writers: the
    # uniqueness boundary includes identity context so a key cannot collide across
    # owner / client / engagement. See docs/INTERNAL_ASSESSMENT_REPORT_DRAFT_CONTROLLED_WRITER.md
    # and docs/INTERNAL_ASSESSMENT_REPORT_DRAFT_IDEMPOTENCY_POLICY.md.
    __table_args__ = (
        UniqueConstraint(
            "owner_id",
            "client_id",
            "engagement_id",
            "idempotency_key",
            name="uq_internal_assessment_report_drafts_idem",
        ),
        MYSQL_TABLE_ARGS,
    )
    # id convention: iard_<slug>
    id: Mapped[str] = mapped_column(GovernedString(64), primary_key=True)
    client_id: Mapped[Optional[str]] = mapped_column(GovernedString(64), index=True)
    engagement_id: Mapped[Optional[str]] = mapped_column(GovernedString(64), index=True)
    # Provenance back to the Phase 36 plan that produced this row.
    report_plan_id: Mapped[Optional[str]] = mapped_column(GovernedString(128), index=True)
    plan_fingerprint: Mapped[Optional[str]] = mapped_column(GovernedString(64), index=True)
    requested_by: Mapped[Optional[str]] = mapped_column(GovernedString(128))
    requester_role: Mapped[Optional[str]] = mapped_column(String(64))
    report_purpose: Mapped[Optional[str]] = mapped_column(String(255))
    # Internal-only audience — a real column, never JSON. "internal" is the only accepted value.
    audience: Mapped[str] = mapped_column(GovernedString(32), index=True, default="internal")
    # Structured plan payload — references, labels, counts, and readiness states ONLY.
    sections_json: Mapped[Optional[dict]] = mapped_column(JSON)
    evidence_trace_map_json: Mapped[Optional[dict]] = mapped_column(JSON)
    finding_candidates_json: Mapped[Optional[dict]] = mapped_column(JSON)
    recommendation_candidates_json: Mapped[Optional[dict]] = mapped_column(JSON)
    open_gaps_json: Mapped[Optional[dict]] = mapped_column(JSON)
    blocked_items_json: Mapped[Optional[dict]] = mapped_column(JSON)
    # Forward-looking placeholders naming FUTURE gates. Nothing is verified or published here.
    future_financial_verification_items_json: Mapped[Optional[dict]] = mapped_column(JSON)
    future_capsule_candidate_items_json: Mapped[Optional[dict]] = mapped_column(JSON)
    reasons_json: Mapped[Optional[dict]] = mapped_column(JSON)
    warnings_json: Mapped[Optional[dict]] = mapped_column(JSON)
    # Governance / non-final posture — real columns (never JSON). "internal-only" is enforced.
    output_status: Mapped[str] = mapped_column(String(32), index=True, default="plan_persisted")
    client_facing_approved: Mapped[bool] = mapped_column(Boolean, default=False)
    financial_verified: Mapped[bool] = mapped_column(Boolean, default=False)
    capsule_candidate_ready: Mapped[bool] = mapped_column(Boolean, default=False)
    publication_allowed: Mapped[bool] = mapped_column(Boolean, default=False)
    execution_allowed: Mapped[bool] = mapped_column(Boolean, default=False)
    requires_human_review: Mapped[bool] = mapped_column(Boolean, default=True)
    # Phase 37 controlled-writer fields. idempotency_key + payload_fingerprint back
    # replay/replay-conflict detection.
    idempotency_key: Mapped[Optional[str]] = mapped_column(GovernedString(128), index=True)
    payload_fingerprint: Mapped[Optional[str]] = mapped_column(GovernedString(64))


class InternalReportReviewPacketRecord(Base, GovernanceMixin, AuditMixin):
    __tablename__ = "internal_report_review_packets"
    # Phase 38: the internal-only review packet handed to a Peak human reviewer for a Phase 37
    # internal assessment report draft. It records **what the reviewer was shown and asked to
    # evaluate** — a section review checklist, reference-only evidence traces, open gaps, blocked
    # items, short internal reviewer questions, a readiness checklist, required follow-up actions,
    # and future-gate placeholders. It stores **no report prose**: no final client-facing language,
    # no raw note/packet/evidence/interview text, no generated agent output, no ROI figure, and no
    # approval decision. ``packet_status`` is fixed at ``ready_for_internal_review`` and
    # ``reviewer_decision_status`` at ``not_decided`` — a packet is created *before* any decision
    # exists, so it can never be misread as a review outcome. DB-enforced idempotency mirrors the
    # prior writers. See docs/INTERNAL_REPORT_REVIEW_PACKET_CONTROLLED_WRITER.md and
    # docs/INTERNAL_REPORT_REVIEW_PACKET_IDEMPOTENCY_POLICY.md.
    __table_args__ = (
        UniqueConstraint(
            "owner_id",
            "client_id",
            "engagement_id",
            "idempotency_key",
            name="uq_internal_report_review_packets_idem",
        ),
        # Named explicitly: the auto-generated
        # ``ix_internal_report_review_packets_internal_assessment_report_draft_id`` would be 69
        # characters, over MySQL's 64-character identifier limit. SQLite would accept it silently,
        # so the short name is pinned here rather than discovered in managed MySQL.
        Index("ix_internal_report_review_packets_report_draft",
              "internal_assessment_report_draft_id"),
        MYSQL_TABLE_ARGS,
    )
    # id convention: irrp_<slug>
    id: Mapped[str] = mapped_column(GovernedString(64), primary_key=True)
    client_id: Mapped[Optional[str]] = mapped_column(GovernedString(64), index=True)
    engagement_id: Mapped[Optional[str]] = mapped_column(GovernedString(64), index=True)
    # Linkage back to the Phase 37 stored report draft (verified against the stored row at write time).
    internal_assessment_report_draft_id: Mapped[Optional[str]] = mapped_column(GovernedString(64))
    source_report_draft_table: Mapped[Optional[str]] = mapped_column(GovernedString(64))
    report_plan_id: Mapped[Optional[str]] = mapped_column(GovernedString(128), index=True)
    plan_fingerprint: Mapped[Optional[str]] = mapped_column(GovernedString(64), index=True)
    report_draft_payload_fingerprint: Mapped[Optional[str]] = mapped_column(GovernedString(64))
    requested_by: Mapped[Optional[str]] = mapped_column(GovernedString(128))
    requester_role: Mapped[Optional[str]] = mapped_column(String(64))
    assigned_reviewer: Mapped[Optional[str]] = mapped_column(GovernedString(128))
    packet_purpose: Mapped[Optional[str]] = mapped_column(String(255))
    # Internal-only audience — a real column, never JSON. "internal" is the only accepted value.
    audience: Mapped[str] = mapped_column(GovernedString(32), index=True, default="internal")
    packet_status: Mapped[str] = mapped_column(
        String(32), index=True, default="ready_for_internal_review")
    # Reviewer decision linkage is populated by a *later* controlled path, never at creation.
    reviewer_decision_record_id: Mapped[Optional[str]] = mapped_column(GovernedString(64), index=True)
    reviewer_decision_status: Mapped[Optional[str]] = mapped_column(String(32), default="not_decided")
    # Structured packet payload — labels, statuses, references, and counts ONLY.
    section_review_checklist_json: Mapped[Optional[dict]] = mapped_column(JSON)
    evidence_trace_refs_json: Mapped[Optional[dict]] = mapped_column(JSON)
    open_gaps_json: Mapped[Optional[dict]] = mapped_column(JSON)
    blocked_items_json: Mapped[Optional[dict]] = mapped_column(JSON)
    reviewer_questions_json: Mapped[Optional[dict]] = mapped_column(JSON)
    readiness_checklist_json: Mapped[Optional[dict]] = mapped_column(JSON)
    required_followup_actions_json: Mapped[Optional[dict]] = mapped_column(JSON)
    # Forward-looking placeholders naming FUTURE gates. Nothing is verified or published here.
    future_financial_verification_items_json: Mapped[Optional[dict]] = mapped_column(JSON)
    future_capsule_candidate_items_json: Mapped[Optional[dict]] = mapped_column(JSON)
    reasons_json: Mapped[Optional[dict]] = mapped_column(JSON)
    warnings_json: Mapped[Optional[dict]] = mapped_column(JSON)
    # Governance / non-final posture — real columns (never JSON). "internal-only" is enforced.
    client_facing_approved: Mapped[bool] = mapped_column(Boolean, default=False)
    review_approval_made: Mapped[bool] = mapped_column(Boolean, default=False)
    financial_verified: Mapped[bool] = mapped_column(Boolean, default=False)
    capsule_candidate_ready: Mapped[bool] = mapped_column(Boolean, default=False)
    publication_allowed: Mapped[bool] = mapped_column(Boolean, default=False)
    execution_allowed: Mapped[bool] = mapped_column(Boolean, default=False)
    requires_human_review: Mapped[bool] = mapped_column(Boolean, default=True)
    # Phase 38 controlled-writer fields. idempotency_key + payload_fingerprint back
    # replay/replay-conflict detection.
    idempotency_key: Mapped[Optional[str]] = mapped_column(GovernedString(128), index=True)
    payload_fingerprint: Mapped[Optional[str]] = mapped_column(GovernedString(64))


class InternalReportReviewPacketDecisionRecord(Base, GovernanceMixin, AuditMixin):
    __tablename__ = "internal_report_review_packet_decisions"
    # Phase 39: a Peak human reviewer's **internal-only** decision on a Phase 38
    # ``internal_report_review_packets`` row. A separate narrow table exists because the Phase 33
    # ``internal_reviewer_decision_records`` writer cannot represent this artifact: it hard-requires
    # a review-bundle reference (a packet decision has none), and its explicit record mapping has no
    # slot for packet / report-draft / plan linkage, so that provenance would be silently dropped.
    # This row therefore preserves the audit chain packet -> report draft -> report plan.
    #
    # It stores **no report prose**: no final client-facing language, no raw note/packet/evidence/
    # interview text, no generated agent output, no ROI figure, no client-facing approval, and no
    # capsule/AgentNet payload. ``decision_scope`` is fixed at ``internal_report_review_packet`` and
    # ``audience`` at ``internal``. ``review_status`` / ``lifecycle_status`` stay inside the Phase 9
    # governed vocabulary; the decision-specific axis is the separate ``decision_status`` column.
    #
    # Index naming: the table name is 39 characters, so the convention-derived
    # ``ix_internal_report_review_packet_decisions_<col>`` would reach 78 characters for the longest
    # columns — over MySQL's 64-character identifier limit. Every index therefore uses the short
    # explicit ``ix_irrpd_<col>`` prefix (max 44). See the Phase 38 identifier-length finding in
    # docs/PRODUCTION_PARITY_DB_VALIDATION.md.
    __table_args__ = (
        UniqueConstraint(
            "owner_id",
            "client_id",
            "engagement_id",
            "idempotency_key",
            name="uq_internal_report_review_packet_decisions_idem",
        ),
        Index("ix_irrpd_client_id", "client_id"),
        Index("ix_irrpd_engagement_id", "engagement_id"),
        Index("ix_irrpd_owner_id", "owner_id"),
        Index("ix_irrpd_authorization_scope", "authorization_scope"),
        Index("ix_irrpd_review_status", "review_status"),
        Index("ix_irrpd_lifecycle_status", "lifecycle_status"),
        Index("ix_irrpd_agent_run_id", "agent_run_id"),
        Index("ix_irrpd_packet_id", "internal_report_review_packet_id"),
        Index("ix_irrpd_report_draft_id", "internal_assessment_report_draft_id"),
        Index("ix_irrpd_report_plan_id", "report_plan_id"),
        Index("ix_irrpd_plan_fingerprint", "plan_fingerprint"),
        Index("ix_irrpd_audience", "audience"),
        Index("ix_irrpd_decision_scope", "decision_scope"),
        Index("ix_irrpd_decision_intent", "decision_intent"),
        Index("ix_irrpd_decision_status", "decision_status"),
        Index("ix_irrpd_idempotency_key", "idempotency_key"),
        MYSQL_TABLE_ARGS,
    )
    # id convention: irrpd_<slug>
    id: Mapped[str] = mapped_column(GovernedString(64), primary_key=True)
    client_id: Mapped[Optional[str]] = mapped_column(GovernedString(64))
    engagement_id: Mapped[Optional[str]] = mapped_column(GovernedString(64))
    # Audit chain: packet -> report draft -> report plan (all verified against stored rows).
    internal_report_review_packet_id: Mapped[Optional[str]] = mapped_column(GovernedString(64))
    source_packet_table: Mapped[Optional[str]] = mapped_column(GovernedString(64))
    internal_assessment_report_draft_id: Mapped[Optional[str]] = mapped_column(GovernedString(64))
    source_report_draft_table: Mapped[Optional[str]] = mapped_column(GovernedString(64))
    report_plan_id: Mapped[Optional[str]] = mapped_column(GovernedString(128))
    plan_fingerprint: Mapped[Optional[str]] = mapped_column(GovernedString(64))
    report_draft_payload_fingerprint: Mapped[Optional[str]] = mapped_column(GovernedString(64))
    packet_payload_fingerprint: Mapped[Optional[str]] = mapped_column(GovernedString(64))
    requested_by: Mapped[Optional[str]] = mapped_column(GovernedString(128))
    requester_role: Mapped[Optional[str]] = mapped_column(String(64))
    reviewer_ref: Mapped[Optional[str]] = mapped_column(GovernedString(128))
    # Reviewer selections — short safe labels only, from a closed vocabulary.
    decision_intent: Mapped[Optional[str]] = mapped_column(String(48))
    safe_decision_summary: Mapped[Optional[str]] = mapped_column(String(255))
    requested_followup_actions_json: Mapped[Optional[dict]] = mapped_column(JSON)
    # Decision-specific axis, server-derived from decision_intent. Kept separate so the governed
    # review_status / lifecycle_status axes stay inside the Phase 9 vocabulary.
    decision_status: Mapped[Optional[str]] = mapped_column(String(32))
    decision_scope: Mapped[str] = mapped_column(
        GovernedString(48), default="internal_report_review_packet")
    audience: Mapped[str] = mapped_column(GovernedString(32), default="internal")
    reasons_json: Mapped[Optional[dict]] = mapped_column(JSON)
    warnings_json: Mapped[Optional[dict]] = mapped_column(JSON)
    # Governance / non-approval posture — real columns (never JSON).
    client_facing_approved: Mapped[bool] = mapped_column(Boolean, default=False)
    review_approval_made: Mapped[bool] = mapped_column(Boolean, default=False)
    financial_verified: Mapped[bool] = mapped_column(Boolean, default=False)
    capsule_candidate_ready: Mapped[bool] = mapped_column(Boolean, default=False)
    publication_allowed: Mapped[bool] = mapped_column(Boolean, default=False)
    execution_allowed: Mapped[bool] = mapped_column(Boolean, default=False)
    requires_human_review: Mapped[bool] = mapped_column(Boolean, default=True)
    # Phase 39 controlled-writer fields.
    idempotency_key: Mapped[Optional[str]] = mapped_column(GovernedString(128))
    payload_fingerprint: Mapped[Optional[str]] = mapped_column(GovernedString(64))


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
    InternalAssessmentReportDraftRecord,
    InternalReportReviewPacketRecord,
    InternalReportReviewPacketDecisionRecord,
]
