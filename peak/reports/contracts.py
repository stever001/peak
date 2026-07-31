"""Contracts for the Internal Assessment Report Assembly Planning Boundary (Phase 36).

A **report-planning boundary**, not a report writer, a report table, a draft-persistence layer, or a
client-facing deliverable generator. These pure stdlib dataclasses/constants describe the request, a
deterministic internal report *plan* (sections, evidence traceability, candidate slots, gaps), and
the planning result.

Nothing here is persisted, approved, published, executed, or sent. The plan is **internal only**:
``audience="internal"``, ``output_status="plan"``, ``review_status="needs_review"``,
``lifecycle_status="draft"``, and every approval/verification/publication/execution posture flag is
false with ``requires_human_review=True``.

The boundary carries **references and short safe labels only** — never intake note text, raw packet
payload, raw evidence/interview text, source bytes, generated agent output, credentials, DSNs, raw
SQL, stack traces, final client-facing language, or approval decisions.

**No module here imports SQLAlchemy, Alembic, ``peak.db``, a DB writer, an AgentNet/MCP/resolver
connector, an LLM/mock-LLM/agent executor, or any network client.**

See docs/INTERNAL_ASSESSMENT_REPORT_PLANNING_BOUNDARY.md and
docs/INTERNAL_REPORT_ASSEMBLY_GOVERNANCE_POLICY.md.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Dict, List, Optional

# --- Requested action --------------------------------------------------------------------
ALLOWED_REPORT_ACTIONS = frozenset({"prepare_internal_assessment_report_plan"})

# --- Posture defaults (the plan never advances authority) ---------------------------------
AUDIENCE_INTERNAL = "internal"
ALLOWED_AUDIENCES = frozenset({AUDIENCE_INTERNAL})
DEFAULT_OUTPUT_STATUS = "plan"
DEFAULT_REVIEW_STATUS = "needs_review"
DEFAULT_LIFECYCLE_STATUS = "draft"

# --- Governed record reference categories -------------------------------------------------
# Each maps a request field to the durable record type it references. Phase 36 reads **no**
# database: these are caller-supplied references to records other phases already persisted.
REF_CATEGORY_RECORD_TYPES = {
    "intake_note_refs": "intake_note_records",
    "source_ingestion_refs": "source_ingestion_records",
    "evidence_reference_ids": "evidence_references",
    "agent_task_queue_record_ids": "agent_task_queue_records",
    "review_bundle_record_ids": "review_bundle_records",
    "internal_reviewer_decision_record_ids": "internal_reviewer_decision_records",
}
REF_CATEGORIES = tuple(REF_CATEGORY_RECORD_TYPES)

# --- Supported internal report sections (canonical, deterministic order) -------------------
SECTION_EXECUTIVE_OVERVIEW = "executive_overview"
SECTION_ENGAGEMENT_CONTEXT = "engagement_context"
SECTION_INTAKE_SUMMARY = "intake_summary"
SECTION_SOURCE_INVENTORY = "source_inventory"
SECTION_EVIDENCE_SUMMARY = "evidence_summary"
SECTION_OPERATIONAL_FINDINGS = "operational_findings"
SECTION_INVENTORY_RISK_AREAS = "inventory_risk_areas"
SECTION_PROCESS_IMPROVEMENT_CANDIDATES = "process_improvement_candidates"
SECTION_SYSTEM_DATA_READINESS = "system_data_readiness"
SECTION_AI_AGENT_READINESS = "ai_agent_readiness"
SECTION_INTERNAL_RECOMMENDATIONS = "internal_recommendations"
SECTION_EVIDENCE_GAPS = "evidence_gaps"
SECTION_REVIEW_STATUS = "review_status"
SECTION_NEXT_STEPS_INTERNAL = "next_steps_internal"

#: Canonical section order. A plan always emits its sections in this order, never in caller order,
#: so the same request always yields the same plan.
SUPPORTED_SECTIONS = (
    SECTION_EXECUTIVE_OVERVIEW,
    SECTION_ENGAGEMENT_CONTEXT,
    SECTION_INTAKE_SUMMARY,
    SECTION_SOURCE_INVENTORY,
    SECTION_EVIDENCE_SUMMARY,
    SECTION_OPERATIONAL_FINDINGS,
    SECTION_INVENTORY_RISK_AREAS,
    SECTION_PROCESS_IMPROVEMENT_CANDIDATES,
    SECTION_SYSTEM_DATA_READINESS,
    SECTION_AI_AGENT_READINESS,
    SECTION_INTERNAL_RECOMMENDATIONS,
    SECTION_EVIDENCE_GAPS,
    SECTION_REVIEW_STATUS,
    SECTION_NEXT_STEPS_INTERNAL,
)
SUPPORTED_SECTION_IDS = frozenset(SUPPORTED_SECTIONS)

#: Which governed reference categories support each section. A section with no requirements is a
#: **synthesis** section: it is structured from the other sections' material, never from raw text.
SECTION_REF_REQUIREMENTS = {
    SECTION_EXECUTIVE_OVERVIEW: (),
    SECTION_ENGAGEMENT_CONTEXT: ("intake_note_refs",),
    SECTION_INTAKE_SUMMARY: ("intake_note_refs",),
    SECTION_SOURCE_INVENTORY: ("source_ingestion_refs",),
    SECTION_EVIDENCE_SUMMARY: ("evidence_reference_ids",),
    SECTION_OPERATIONAL_FINDINGS: ("evidence_reference_ids",),
    SECTION_INVENTORY_RISK_AREAS: ("evidence_reference_ids",),
    SECTION_PROCESS_IMPROVEMENT_CANDIDATES: ("evidence_reference_ids",),
    SECTION_SYSTEM_DATA_READINESS: ("source_ingestion_refs",),
    SECTION_AI_AGENT_READINESS: ("agent_task_queue_record_ids",),
    SECTION_INTERNAL_RECOMMENDATIONS: ("internal_reviewer_decision_record_ids",
                                       "review_bundle_record_ids"),
    SECTION_EVIDENCE_GAPS: (),
    SECTION_REVIEW_STATUS: ("review_bundle_record_ids",),
    SECTION_NEXT_STEPS_INTERNAL: (),
}

# --- Section readiness states (deterministic) ----------------------------------------------
SECTION_READY = "ready_for_internal_drafting"      # every supporting category has a reference
SECTION_PARTIAL = "partial_supporting_references"  # some supporting categories are empty
SECTION_BLOCKED_NO_REFS = "blocked_no_supporting_references"
SECTION_SYNTHESIS_ONLY = "synthesis_only"          # no direct refs required (derived structure)
SECTION_READINESS_STATES = frozenset({
    SECTION_READY, SECTION_PARTIAL, SECTION_BLOCKED_NO_REFS, SECTION_SYNTHESIS_ONLY,
})

# --- Recommendation candidate readiness (internal-only; never approval) --------------------
RECOMMENDATION_INTERNAL_DRAFT = "internal_draft_candidate"
RECOMMENDATION_BLOCKED_NO_EVIDENCE = "blocked_no_evidence_support"
RECOMMENDATION_BLOCKED_NO_REVIEW = "blocked_no_review_support"
RECOMMENDATION_READINESS_STATES = frozenset({
    RECOMMENDATION_INTERNAL_DRAFT, RECOMMENDATION_BLOCKED_NO_EVIDENCE,
    RECOMMENDATION_BLOCKED_NO_REVIEW,
})

# --- Gap kinds ------------------------------------------------------------------------------
GAP_MISSING_REFERENCES = "missing_supporting_references"

# --- Request-level blocked states (mirrors the Phase 32 vocabulary) -------------------------
BLOCKED_INVALID_SCOPE = "blocked_invalid_scope"
BLOCKED_MISSING_IDENTITY = "blocked_missing_identity"
BLOCKED_MISSING_PLAN_ID = "blocked_missing_plan_id"
BLOCKED_UNSUPPORTED_SECTION = "blocked_unsupported_section"
BLOCKED_DUPLICATE_SECTION = "blocked_duplicate_section"
BLOCKED_UNSUPPORTED_AUDIENCE = "blocked_unsupported_audience"
BLOCKED_DISALLOWED_POSTURE = "blocked_disallowed_posture"
BLOCKED_DISALLOWED_INTENT = "blocked_disallowed_intent"
BLOCKED_LIFECYCLE = "blocked_lifecycle"
BLOCKED_RAW_CONTENT = "blocked_raw_content"
BLOCKED_SECRET_LIKE_CONTENT = "blocked_secret_like_content"
BLOCKED_REFERENCE_IDENTITY = "blocked_reference_identity"

# --- Planning outcomes ----------------------------------------------------------------------
OUTCOME_DENIED = "denied"    # request-level governance denied the whole request; no plan built
OUTCOME_PLANNED = "planned"  # a deterministic internal report plan was assembled


@dataclass
class GovernedRecordReference:
    """A structured reference to a record another phase already persisted (never its content).

    Callers may pass plain short string ids instead; this typed form additionally lets the boundary
    verify tenant/engagement/scope consistency and deny cross-tenant or cross-engagement material
    before it reaches a plan.
    """

    record_id: Optional[str] = None
    record_type: Optional[str] = None
    owner_id: Optional[str] = None
    client_id: Optional[str] = None
    engagement_id: Optional[str] = None
    authorization_scope: Optional[str] = None
    label: Optional[str] = None  # short safe routing label; never content


@dataclass
class InternalAssessmentReportPlanRequest:
    """A request to plan (never draft, persist, or send) an internal assessment report.

    Carries **only** ids/references and short safe labels. It must never carry intake note text,
    raw packet payload, raw evidence/interview text, source bytes, generated agent output,
    credentials/secrets, DSNs, raw SQL, stack traces, final client-facing language, approval
    decisions, LLM prompts, AgentNet publish payloads, resolver credentials, or arbitrary report
    JSON blobs. ``context`` is optional safe metadata whose keys are scanned.

    The posture flags exist so a caller cannot smuggle an elevated posture past the boundary: each
    must stay at its safe default or the request is denied.
    """

    owner_id: Optional[str] = None
    client_id: Optional[str] = None
    engagement_id: Optional[str] = None
    authorization_scope: Optional[str] = None
    requested_by: Optional[str] = None
    requester_role: Optional[str] = None
    # Plan identity — at least one of these is required and backs the deterministic fingerprint.
    report_plan_id: Optional[str] = None
    idempotency_key: Optional[str] = None
    # Governed record references (strings or GovernedRecordReference objects).
    intake_note_refs: List[object] = field(default_factory=list)
    source_ingestion_refs: List[object] = field(default_factory=list)
    evidence_reference_ids: List[object] = field(default_factory=list)
    agent_task_queue_record_ids: List[object] = field(default_factory=list)
    review_bundle_record_ids: List[object] = field(default_factory=list)
    internal_reviewer_decision_record_ids: List[object] = field(default_factory=list)
    # Optional provenance links back to the Phase 35 managed-record workflow.
    workflow_id: Optional[str] = None
    managed_record_workflow_ref: Optional[str] = None
    # Section selection (canonical order is always applied); empty means "all supported sections".
    requested_sections: List[str] = field(default_factory=list)
    report_purpose: Optional[str] = None  # short safe internal label, never client-facing prose
    audience: str = AUDIENCE_INTERNAL     # only "internal" is accepted
    allow_empty_reference_plan: bool = False  # opt in to a skeletal plan (emits a warning)
    strict_mode: bool = True
    requested_action: Optional[str] = "prepare_internal_assessment_report_plan"
    source_phase: Optional[str] = None
    lifecycle_status: Optional[str] = None
    # Posture flags — must stay at these safe defaults.
    client_facing_approved: bool = False
    financial_verified: bool = False
    capsule_candidate_ready: bool = False
    publication_allowed: bool = False
    execution_allowed: bool = False
    requires_human_review: bool = True
    context: Optional[dict] = None  # safe metadata only; keys scanned for prohibited terms


@dataclass
class InternalReportEvidenceTrace:
    """Which governed references support one section (references only, never content)."""

    section_id: str = ""
    supporting_refs: Dict[str, List[str]] = field(default_factory=dict)  # category -> record ids
    supporting_ref_count: int = 0
    missing_categories: List[str] = field(default_factory=list)


@dataclass
class InternalReportSectionPlan:
    """A planned internal report section — structure and traceability, never prose.

    ``title`` is a fixed internal section label from this module, not generated narrative, and
    never client-facing language.
    """

    section_id: str = ""
    title: str = ""
    order: int = 0
    readiness_state: str = SECTION_BLOCKED_NO_REFS
    required_ref_categories: List[str] = field(default_factory=list)
    satisfied_ref_categories: List[str] = field(default_factory=list)
    missing_ref_categories: List[str] = field(default_factory=list)
    supporting_ref_count: int = 0
    synthesis_only: bool = False
    blocked_reason: Optional[str] = None
    requires_human_review: bool = True
    client_facing_approved: bool = False
    notes: List[str] = field(default_factory=list)  # safe planning notes; never report prose


@dataclass
class InternalReportFindingCandidate:
    """A structured placeholder for a finding, tied to references — **not** generated narrative."""

    finding_candidate_id: str = ""
    section_id: str = ""
    evidence_support_refs: List[str] = field(default_factory=list)
    review_support_refs: List[str] = field(default_factory=list)
    readiness_state: str = RECOMMENDATION_BLOCKED_NO_EVIDENCE
    requires_human_review: bool = True
    client_facing_approved: bool = False
    financial_verified: bool = False
    capsule_candidate_ready: bool = False
    publication_allowed: bool = False
    blocked_reason: Optional[str] = None


@dataclass
class InternalReportRecommendationCandidate:
    """An **internal-only** recommendation slot. Never final, never client-facing, never approved."""

    recommendation_candidate_id: str = ""
    section_id: str = SECTION_INTERNAL_RECOMMENDATIONS
    reviewer_decision_refs: List[str] = field(default_factory=list)
    review_support_refs: List[str] = field(default_factory=list)
    evidence_support_refs: List[str] = field(default_factory=list)
    readiness_state: str = RECOMMENDATION_BLOCKED_NO_EVIDENCE
    audience: str = AUDIENCE_INTERNAL
    requires_human_review: bool = True
    client_facing_approved: bool = False
    financial_verified: bool = False
    capsule_candidate_ready: bool = False
    publication_allowed: bool = False
    execution_allowed: bool = False
    requires_financial_verification: bool = False  # a *future* gate, never performed here
    blocked_reason: Optional[str] = None


@dataclass
class InternalReportGap:
    """A missing-evidence / missing-reference gap the plan surfaces for human follow-up."""

    gap_id: str = ""
    gap_kind: str = GAP_MISSING_REFERENCES
    section_id: str = ""
    missing_ref_category: Optional[str] = None
    missing_record_type: Optional[str] = None
    blocks_section: bool = False
    note: Optional[str] = None  # safe label-level note; never content


@dataclass
class InternalAssessmentReportPlan:
    """The deterministic internal assessment report plan (structure + traceability + readiness).

    This is a **plan**, not a report draft and not a client-facing deliverable. It contains no
    generated prose, no final language, no ROI figure, and no approval.
    """

    report_plan_id: Optional[str] = None
    plan_fingerprint: Optional[str] = None
    owner_id: Optional[str] = None
    client_id: Optional[str] = None
    engagement_id: Optional[str] = None
    authorization_scope: Optional[str] = None
    requested_by: Optional[str] = None
    requester_role: Optional[str] = None
    workflow_id: Optional[str] = None
    managed_record_workflow_ref: Optional[str] = None
    report_purpose: Optional[str] = None
    audience: str = AUDIENCE_INTERNAL
    output_status: str = DEFAULT_OUTPUT_STATUS
    review_status: str = DEFAULT_REVIEW_STATUS
    lifecycle_status: str = DEFAULT_LIFECYCLE_STATUS
    client_facing_approved: bool = False
    financial_verified: bool = False
    capsule_candidate_ready: bool = False
    publication_allowed: bool = False
    execution_allowed: bool = False
    requires_human_review: bool = True
    sections: List[InternalReportSectionPlan] = field(default_factory=list)
    evidence_trace_map: Dict[str, InternalReportEvidenceTrace] = field(default_factory=dict)
    finding_candidates: List[InternalReportFindingCandidate] = field(default_factory=list)
    recommendation_candidates: List[InternalReportRecommendationCandidate] = \
        field(default_factory=list)
    open_gaps: List[InternalReportGap] = field(default_factory=list)
    blocked_items: List[str] = field(default_factory=list)
    # Forward-looking slots. These name *future* gates; nothing is verified or published here.
    future_financial_verification_items: List[str] = field(default_factory=list)
    future_capsule_candidate_items: List[str] = field(default_factory=list)
    reference_counts: Dict[str, int] = field(default_factory=dict)
    reasons: List[str] = field(default_factory=list)
    warnings: List[str] = field(default_factory=list)


@dataclass
class InternalReportPlanningValidationResult:
    """Result of the deterministic request-level validation (no side effects)."""

    permitted: bool = False
    identity_valid: bool = False
    scope_valid: bool = False
    plan_id_valid: bool = False
    audience_valid: bool = False
    sections_valid: bool = False
    posture_valid: bool = False
    references_valid: bool = False
    has_any_reference: bool = False
    contains_prohibited_content: bool = False
    blocked_state: Optional[str] = None
    reasons: List[str] = field(default_factory=list)
    warnings: List[str] = field(default_factory=list)


@dataclass
class InternalAssessmentReportPlanningResult:
    """The controlled result of planning an internal assessment report (no side effects).

    Reports never echo intake note text, raw packet/evidence/interview text, source bytes,
    generated agent output, credentials, DSNs, raw SQL, stack traces, final client-facing language,
    or approval decisions — only field names, reference ids, counts, and marker categories.
    """

    outcome: str = OUTCOME_DENIED
    permitted: bool = False
    reason_code: Optional[str] = None
    status: str = "rejected"
    validation_result: Optional[InternalReportPlanningValidationResult] = None
    report_plan: Optional[InternalAssessmentReportPlan] = None
    plan_fingerprint: Optional[str] = None
    section_count: int = 0
    finding_candidate_count: int = 0
    recommendation_candidate_count: int = 0
    open_gap_count: int = 0
    blocked_item_count: int = 0
    controlled_write_request_count: int = 0  # Phase 36 produces none
    reasons: List[str] = field(default_factory=list)
    warnings: List[str] = field(default_factory=list)
    # Aggregate side-effect flags — all stay False in Phase 36.
    direct_database_write_made: bool = False
    database_connection_made: bool = False
    sql_execution_made: bool = False
    stored_record_created: bool = False
    report_draft_persisted: bool = False
    review_records_write_made: bool = False
    agent_run_records_write_made: bool = False
    review_approval_made: bool = False
    client_facing_output_created: bool = False
    client_facing_approval_made: bool = False
    financial_verification_made: bool = False
    capsule_publication_made: bool = False
    capsule_candidate_created: bool = False
    agentnet_publication_made: bool = False
    agent_execution_made: bool = False
    mock_agent_execution_made: bool = False
    llm_call_made: bool = False
    agentnet_call_made: bool = False
    resolver_call_made: bool = False
    network_call_made: bool = False


#: Fixed internal section labels. These are planning labels, not report prose and never
#: client-facing language.
SECTION_TITLES = {
    SECTION_EXECUTIVE_OVERVIEW: "Executive overview (internal)",
    SECTION_ENGAGEMENT_CONTEXT: "Engagement context",
    SECTION_INTAKE_SUMMARY: "Intake summary",
    SECTION_SOURCE_INVENTORY: "Source system inventory",
    SECTION_EVIDENCE_SUMMARY: "Evidence summary",
    SECTION_OPERATIONAL_FINDINGS: "Operational findings",
    SECTION_INVENTORY_RISK_AREAS: "Inventory risk areas",
    SECTION_PROCESS_IMPROVEMENT_CANDIDATES: "Process improvement candidates",
    SECTION_SYSTEM_DATA_READINESS: "System and data readiness",
    SECTION_AI_AGENT_READINESS: "AI / agent readiness",
    SECTION_INTERNAL_RECOMMENDATIONS: "Internal recommendations",
    SECTION_EVIDENCE_GAPS: "Evidence gaps",
    SECTION_REVIEW_STATUS: "Review status",
    SECTION_NEXT_STEPS_INTERNAL: "Next steps (internal)",
}
