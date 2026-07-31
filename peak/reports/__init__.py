"""Peak Internal Assessment Report Assembly Planning Boundary (Phase 36).

A **report-planning boundary**, not a report writer, a report table, a report-draft persistence
layer, a client-facing deliverable generator, a workflow engine, or a DB writer. It turns governed
record references and reviewer decisions into a deterministic **internal assessment report plan**:
which sections an internal report should contain, which durable records support each one, which
evidence gaps remain, which findings and internal-only recommendations are candidate slots, and
which items are blocked or deferred to a future gate.

This phase is analogous to Phases 29 and 32: those planned review bundles and reviewer decisions
without DB writes; Phase 36 plans internal report assembly without DB writes. It is **DB-free and
network-free** and produces **no** ``ControlledWriteRequest`` objects.

The plan is **internal only**: ``audience="internal"``, ``output_status="plan"``,
``review_status="needs_review"``, ``lifecycle_status="draft"``, with
``client_facing_approved`` / ``financial_verified`` / ``capsule_candidate_ready`` /
``publication_allowed`` / ``execution_allowed`` all false and ``requires_human_review=True``.

It drafts no report, persists nothing, approves nothing, generates no client-facing language,
calculates no ROI, verifies no savings, creates or publishes no capsule, and makes no LLM / MockLLM
/ agent / AgentNet / MCP / resolver / connector / network call. It reads **no** database: every
reference is caller-supplied. Determinism is guaranteed — canonical section order, sorted
de-duplicated references, positional candidate ids, and a SHA-256 ``plan_fingerprint``, with **no
random ids and no timestamps**.

This package imports only stdlib plus the public, DB-free Phase 32 value classifier. See
docs/INTERNAL_ASSESSMENT_REPORT_PLANNING_BOUNDARY.md and
docs/INTERNAL_REPORT_ASSEMBLY_GOVERNANCE_POLICY.md.
"""

from __future__ import annotations

from .contracts import (
    ALLOWED_AUDIENCES,
    ALLOWED_REPORT_ACTIONS,
    AUDIENCE_INTERNAL,
    BLOCKED_DISALLOWED_INTENT,
    BLOCKED_DISALLOWED_POSTURE,
    BLOCKED_DUPLICATE_SECTION,
    BLOCKED_INVALID_SCOPE,
    BLOCKED_LIFECYCLE,
    BLOCKED_MISSING_IDENTITY,
    BLOCKED_MISSING_PLAN_ID,
    BLOCKED_RAW_CONTENT,
    BLOCKED_REFERENCE_IDENTITY,
    BLOCKED_SECRET_LIKE_CONTENT,
    BLOCKED_UNSUPPORTED_AUDIENCE,
    BLOCKED_UNSUPPORTED_SECTION,
    DEFAULT_LIFECYCLE_STATUS,
    DEFAULT_OUTPUT_STATUS,
    DEFAULT_REVIEW_STATUS,
    GAP_MISSING_REFERENCES,
    OUTCOME_DENIED,
    OUTCOME_PLANNED,
    RECOMMENDATION_BLOCKED_NO_EVIDENCE,
    RECOMMENDATION_BLOCKED_NO_REVIEW,
    RECOMMENDATION_INTERNAL_DRAFT,
    RECOMMENDATION_READINESS_STATES,
    REF_CATEGORIES,
    REF_CATEGORY_RECORD_TYPES,
    SECTION_BLOCKED_NO_REFS,
    SECTION_PARTIAL,
    SECTION_READINESS_STATES,
    SECTION_READY,
    SECTION_REF_REQUIREMENTS,
    SECTION_SYNTHESIS_ONLY,
    SECTION_TITLES,
    SUPPORTED_SECTION_IDS,
    SUPPORTED_SECTIONS,
    GovernedRecordReference,
    InternalAssessmentReportPlan,
    InternalAssessmentReportPlanningResult,
    InternalAssessmentReportPlanRequest,
    InternalReportEvidenceTrace,
    InternalReportFindingCandidate,
    InternalReportGap,
    InternalReportPlanningValidationResult,
    InternalReportRecommendationCandidate,
    InternalReportSectionPlan,
)
from .governance import (
    DB_ARTIFACT_KEY_TERMS,
    DISALLOWED_INTENT_KEY_TERMS,
    RAW_CONTENT_KEY_TERMS,
    SECRET_KEY_TERMS,
    ReportPlanningGovernanceDecision,
    classify_value,
    evaluate_internal_assessment_report_plan_request,
    reference_identity_mismatches,
    scan_prohibited_content,
)
from .internal_assessment_planner import prepare_internal_assessment_report_plan

__all__ = [
    # contracts
    "InternalAssessmentReportPlanRequest",
    "InternalAssessmentReportPlan",
    "InternalAssessmentReportPlanningResult",
    "InternalReportPlanningValidationResult",
    "InternalReportSectionPlan",
    "InternalReportEvidenceTrace",
    "InternalReportFindingCandidate",
    "InternalReportRecommendationCandidate",
    "InternalReportGap",
    "GovernedRecordReference",
    "SUPPORTED_SECTIONS",
    "SUPPORTED_SECTION_IDS",
    "SECTION_REF_REQUIREMENTS",
    "SECTION_TITLES",
    "SECTION_READINESS_STATES",
    "SECTION_READY",
    "SECTION_PARTIAL",
    "SECTION_BLOCKED_NO_REFS",
    "SECTION_SYNTHESIS_ONLY",
    "RECOMMENDATION_READINESS_STATES",
    "RECOMMENDATION_INTERNAL_DRAFT",
    "RECOMMENDATION_BLOCKED_NO_EVIDENCE",
    "RECOMMENDATION_BLOCKED_NO_REVIEW",
    "REF_CATEGORIES",
    "REF_CATEGORY_RECORD_TYPES",
    "GAP_MISSING_REFERENCES",
    "ALLOWED_AUDIENCES",
    "ALLOWED_REPORT_ACTIONS",
    "AUDIENCE_INTERNAL",
    "DEFAULT_OUTPUT_STATUS",
    "DEFAULT_REVIEW_STATUS",
    "DEFAULT_LIFECYCLE_STATUS",
    "OUTCOME_DENIED",
    "OUTCOME_PLANNED",
    "BLOCKED_MISSING_IDENTITY",
    "BLOCKED_INVALID_SCOPE",
    "BLOCKED_MISSING_PLAN_ID",
    "BLOCKED_UNSUPPORTED_SECTION",
    "BLOCKED_DUPLICATE_SECTION",
    "BLOCKED_UNSUPPORTED_AUDIENCE",
    "BLOCKED_DISALLOWED_POSTURE",
    "BLOCKED_DISALLOWED_INTENT",
    "BLOCKED_LIFECYCLE",
    "BLOCKED_RAW_CONTENT",
    "BLOCKED_SECRET_LIKE_CONTENT",
    "BLOCKED_REFERENCE_IDENTITY",
    # governance
    "ReportPlanningGovernanceDecision",
    "evaluate_internal_assessment_report_plan_request",
    "scan_prohibited_content",
    "reference_identity_mismatches",
    "classify_value",
    "SECRET_KEY_TERMS",
    "RAW_CONTENT_KEY_TERMS",
    "DB_ARTIFACT_KEY_TERMS",
    "DISALLOWED_INTENT_KEY_TERMS",
    # entry point
    "prepare_internal_assessment_report_plan",
]
