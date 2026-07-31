"""Internal assessment report **planning** (Phase 36) — structure and traceability, never prose.

Turns governed record references and reviewer decisions into a deterministic internal assessment
report *plan*: which sections an internal report should contain, which durable records support each
one, which evidence gaps remain, which findings and internal-only recommendations are candidate
slots, and which items are blocked or deferred to a future gate.

This is a **planning boundary**. It does not draft a report, persist a report draft, create a report
table or DB writer, generate client-facing language, verify financial impact, calculate ROI, create
or publish capsule candidates, call an LLM / AgentNet / MCP / resolver / network, execute an agent,
or broaden database access. It reads **no** database: every reference is caller-supplied.

Determinism: the plan is a pure function of the request. Sections are emitted in the module's
canonical order (never the caller's order), references are normalized and de-duplicated in sorted
order, candidate ids are positional, and ``plan_fingerprint`` is a SHA-256 over the safe request
fields and references. There are **no random ids and no timestamps**.

See docs/INTERNAL_ASSESSMENT_REPORT_PLANNING_BOUNDARY.md and
docs/INTERNAL_REPORT_ASSEMBLY_GOVERNANCE_POLICY.md.
"""

from __future__ import annotations

import hashlib
import json
from typing import Dict, List

from .contracts import (
    AUDIENCE_INTERNAL,
    DEFAULT_LIFECYCLE_STATUS,
    DEFAULT_OUTPUT_STATUS,
    DEFAULT_REVIEW_STATUS,
    GAP_MISSING_REFERENCES,
    OUTCOME_DENIED,
    OUTCOME_PLANNED,
    RECOMMENDATION_BLOCKED_NO_EVIDENCE,
    RECOMMENDATION_BLOCKED_NO_REVIEW,
    RECOMMENDATION_INTERNAL_DRAFT,
    REF_CATEGORIES,
    REF_CATEGORY_RECORD_TYPES,
    SECTION_BLOCKED_NO_REFS,
    SECTION_INTERNAL_RECOMMENDATIONS,
    SECTION_OPERATIONAL_FINDINGS,
    SECTION_PARTIAL,
    SECTION_READY,
    SECTION_REF_REQUIREMENTS,
    SECTION_SYNTHESIS_ONLY,
    SECTION_TITLES,
    SUPPORTED_SECTIONS,
    GovernedRecordReference,
    InternalAssessmentReportPlan,
    InternalAssessmentReportPlanningResult,
    InternalReportEvidenceTrace,
    InternalReportFindingCandidate,
    InternalReportGap,
    InternalReportRecommendationCandidate,
    InternalReportSectionPlan,
)
from .governance import evaluate_internal_assessment_report_plan_request

#: Bound on how many candidate slots the plan will emit per family, so a very large reference list
#: cannot produce an unbounded plan. Truncation is always reported as a warning, never silent.
MAX_CANDIDATES_PER_FAMILY = 200


def prepare_internal_assessment_report_plan(
    request,
) -> InternalAssessmentReportPlanningResult:
    """Plan (never draft, persist, approve, or send) an internal assessment report.

    Returns an :class:`InternalAssessmentReportPlanningResult`. Expected governance failures are
    typed denials, not exceptions. The result never echoes intake note text, raw packet/evidence/
    interview text, source bytes, generated agent output, credentials, DSNs, raw SQL, stack traces,
    final client-facing language, or approval decisions.
    """
    decision = evaluate_internal_assessment_report_plan_request(request)
    if not decision.permitted:
        return InternalAssessmentReportPlanningResult(
            outcome=OUTCOME_DENIED,
            permitted=False,
            status="rejected",
            reason_code=decision.reason_code,
            validation_result=decision.validation,
            reasons=list(decision.reasons),
            warnings=list(decision.warnings),
        )

    warnings: List[str] = list(decision.warnings)
    reasons: List[str] = []

    refs = _normalized_references(request)
    reference_counts = {category: len(refs[category]) for category in REF_CATEGORIES}
    sections = _selected_sections(request)

    section_plans: List[InternalReportSectionPlan] = []
    trace_map: Dict[str, InternalReportEvidenceTrace] = {}
    gaps: List[InternalReportGap] = []
    blocked_items: List[str] = []

    for order, section_id in enumerate(sections):
        plan, trace, section_gaps = _plan_section(section_id, order, refs)
        section_plans.append(plan)
        trace_map[section_id] = trace
        gaps.extend(section_gaps)
        if plan.readiness_state == SECTION_BLOCKED_NO_REFS:
            blocked_items.append(section_id)

    findings, finding_warnings = _finding_candidates(refs, sections)
    warnings.extend(finding_warnings)

    recommendations, rec_warnings = _recommendation_candidates(refs, sections)
    warnings.extend(rec_warnings)
    blocked_items.extend(
        r.recommendation_candidate_id for r in recommendations if r.blocked_reason)
    blocked_items.extend(f.finding_candidate_id for f in findings if f.blocked_reason)

    # Forward-looking slots. These *name* future gates; nothing is verified or published here.
    future_financial = [r.recommendation_candidate_id for r in recommendations
                        if r.requires_financial_verification]
    future_capsule = list(refs["source_ingestion_refs"])

    if future_financial:
        reasons.append(
            f"{len(future_financial)} internal recommendation candidate(s) would require a future "
            "financial verification gate before any ROI or savings claim; financial_verified "
            "remains false and no ROI was calculated")
    if future_capsule:
        reasons.append(
            f"{len(future_capsule)} source ingestion reference(s) are noted as possible future "
            "capsule candidates; capsule_candidate_ready and publication_allowed remain false and "
            "no capsule candidate was created or published")
    reasons.append(
        "internal assessment report plan assembled: structure, traceability, and readiness only "
        "(no report draft, no client-facing language, no approval)")

    plan = InternalAssessmentReportPlan(
        report_plan_id=request.report_plan_id or request.idempotency_key,
        owner_id=request.owner_id,
        client_id=request.client_id,
        engagement_id=request.engagement_id,
        authorization_scope=request.authorization_scope,
        requested_by=request.requested_by,
        requester_role=request.requester_role,
        workflow_id=request.workflow_id,
        managed_record_workflow_ref=request.managed_record_workflow_ref,
        report_purpose=request.report_purpose,
        audience=AUDIENCE_INTERNAL,
        output_status=DEFAULT_OUTPUT_STATUS,
        review_status=DEFAULT_REVIEW_STATUS,
        lifecycle_status=DEFAULT_LIFECYCLE_STATUS,
        sections=section_plans,
        evidence_trace_map=trace_map,
        finding_candidates=findings,
        recommendation_candidates=recommendations,
        open_gaps=gaps,
        blocked_items=blocked_items,
        future_financial_verification_items=future_financial,
        future_capsule_candidate_items=future_capsule,
        reference_counts=reference_counts,
        reasons=list(reasons),
        warnings=list(warnings),
    )
    plan.plan_fingerprint = _plan_fingerprint(request, refs, sections)

    if request.strict_mode and warnings:
        reasons.append(
            "strict_mode: the plan carries warnings and must be resolved by a human reviewer "
            "before it is used to draft anything")

    return InternalAssessmentReportPlanningResult(
        outcome=OUTCOME_PLANNED,
        permitted=True,
        status="planned",
        reason_code=None,
        validation_result=decision.validation,
        report_plan=plan,
        plan_fingerprint=plan.plan_fingerprint,
        section_count=len(section_plans),
        finding_candidate_count=len(findings),
        recommendation_candidate_count=len(recommendations),
        open_gap_count=len(gaps),
        blocked_item_count=len(blocked_items),
        reasons=list(reasons),
        warnings=list(warnings),
    )


# --------------------------------------------------------------------------- references


def _normalized_references(request) -> Dict[str, List[str]]:
    """Normalize every reference category to a sorted, de-duplicated list of record-id strings.

    Sorting and de-duplication are what make the plan a pure function of the request's reference
    *set* rather than of caller ordering.
    """
    normalized: Dict[str, List[str]] = {}
    for category in REF_CATEGORIES:
        values = []
        for item in list(getattr(request, category, None) or []):
            record_id = item.record_id if isinstance(item, GovernedRecordReference) else item
            if isinstance(record_id, str) and record_id.strip():
                values.append(record_id)
        normalized[category] = sorted(set(values))
    return normalized


def _selected_sections(request) -> List[str]:
    """Return the requested sections in the module's canonical order (never the caller's order)."""
    requested = list(getattr(request, "requested_sections", None) or [])
    if not requested:
        return list(SUPPORTED_SECTIONS)
    chosen = set(requested)
    return [section for section in SUPPORTED_SECTIONS if section in chosen]


# --------------------------------------------------------------------------- sections


def _plan_section(section_id: str, order: int, refs: Dict[str, List[str]]):
    """Build one section plan, its evidence trace, and any gaps it opens."""
    required = list(SECTION_REF_REQUIREMENTS.get(section_id, ()))
    satisfied = [category for category in required if refs.get(category)]
    missing = [category for category in required if not refs.get(category)]

    supporting = {category: list(refs.get(category, [])) for category in satisfied}
    supporting_count = sum(len(v) for v in supporting.values())

    if not required:
        readiness = SECTION_SYNTHESIS_ONLY
        blocked_reason = None
    elif not satisfied:
        readiness = SECTION_BLOCKED_NO_REFS
        blocked_reason = "no supporting governed record references were supplied for this section"
    elif missing:
        readiness = SECTION_PARTIAL
        blocked_reason = None
    else:
        readiness = SECTION_READY
        blocked_reason = None

    notes: List[str] = []
    if readiness == SECTION_SYNTHESIS_ONLY:
        notes.append("synthesis section: structured from the other sections, never from raw text")

    plan = InternalReportSectionPlan(
        section_id=section_id,
        title=SECTION_TITLES[section_id],
        order=order,
        readiness_state=readiness,
        required_ref_categories=required,
        satisfied_ref_categories=satisfied,
        missing_ref_categories=missing,
        supporting_ref_count=supporting_count,
        synthesis_only=not required,
        blocked_reason=blocked_reason,
        notes=notes,
    )
    trace = InternalReportEvidenceTrace(
        section_id=section_id,
        supporting_refs=supporting,
        supporting_ref_count=supporting_count,
        missing_categories=list(missing),
    )
    gaps = [
        InternalReportGap(
            gap_id=f"gap_{section_id}_{category}",
            gap_kind=GAP_MISSING_REFERENCES,
            section_id=section_id,
            missing_ref_category=category,
            missing_record_type=REF_CATEGORY_RECORD_TYPES.get(category),
            blocks_section=(readiness == SECTION_BLOCKED_NO_REFS),
            note=f"no {category} reference was supplied to support '{section_id}'",
        )
        for category in missing
    ]
    return plan, trace, gaps


# --------------------------------------------------------------------------- candidates


def _finding_candidates(refs: Dict[str, List[str]], sections: List[str]):
    """One structured finding slot per evidence reference — references only, never narrative."""
    warnings: List[str] = []
    if SECTION_OPERATIONAL_FINDINGS not in sections:
        return [], warnings

    evidence = refs["evidence_reference_ids"]
    review = refs["review_bundle_record_ids"]
    if len(evidence) > MAX_CANDIDATES_PER_FAMILY:
        warnings.append(
            f"finding candidates truncated to the first {MAX_CANDIDATES_PER_FAMILY} of "
            f"{len(evidence)} evidence references (sorted order); the remainder were not planned")
        evidence = evidence[:MAX_CANDIDATES_PER_FAMILY]

    candidates: List[InternalReportFindingCandidate] = []
    for index, evidence_ref in enumerate(evidence):
        blocked = None if review else "no review bundle reference supports this finding slot"
        candidates.append(InternalReportFindingCandidate(
            finding_candidate_id=f"fnd_{index:03d}",
            section_id=SECTION_OPERATIONAL_FINDINGS,
            evidence_support_refs=[evidence_ref],
            review_support_refs=list(review),
            readiness_state=(RECOMMENDATION_INTERNAL_DRAFT if review
                             else RECOMMENDATION_BLOCKED_NO_REVIEW),
            blocked_reason=blocked,
        ))
    return candidates, warnings


def _recommendation_candidates(refs: Dict[str, List[str]], sections: List[str]):
    """One internal-only recommendation slot per reviewer decision reference.

    Every slot stays internal: not final, not client-facing, not approved, not financially
    verified, not a capsule candidate, not publishable, not executable.
    """
    warnings: List[str] = []
    if SECTION_INTERNAL_RECOMMENDATIONS not in sections:
        return [], warnings

    decisions = refs["internal_reviewer_decision_record_ids"]
    evidence = refs["evidence_reference_ids"]
    review = refs["review_bundle_record_ids"]
    if len(decisions) > MAX_CANDIDATES_PER_FAMILY:
        warnings.append(
            f"recommendation candidates truncated to the first {MAX_CANDIDATES_PER_FAMILY} of "
            f"{len(decisions)} reviewer decision references (sorted order); the remainder were "
            "not planned")
        decisions = decisions[:MAX_CANDIDATES_PER_FAMILY]

    candidates: List[InternalReportRecommendationCandidate] = []
    for index, decision_ref in enumerate(decisions):
        if not evidence:
            readiness = RECOMMENDATION_BLOCKED_NO_EVIDENCE
            blocked = "no evidence reference supports this recommendation slot"
        elif not review:
            readiness = RECOMMENDATION_BLOCKED_NO_REVIEW
            blocked = "no review bundle reference supports this recommendation slot"
        else:
            readiness = RECOMMENDATION_INTERNAL_DRAFT
            blocked = None
        candidates.append(InternalReportRecommendationCandidate(
            recommendation_candidate_id=f"rec_{index:03d}",
            section_id=SECTION_INTERNAL_RECOMMENDATIONS,
            reviewer_decision_refs=[decision_ref],
            review_support_refs=list(review),
            evidence_support_refs=list(evidence),
            readiness_state=readiness,
            blocked_reason=blocked,
            # A recommendation that might later carry an ROI/savings claim needs a *future*
            # financial verification gate. Nothing is calculated or verified here.
            requires_financial_verification=(readiness == RECOMMENDATION_INTERNAL_DRAFT),
        ))
    return candidates, warnings


# --------------------------------------------------------------------------- determinism


def _plan_fingerprint(request, refs: Dict[str, List[str]], sections: List[str]) -> str:
    """A deterministic SHA-256 over the safe request fields, references, and section selection.

    Uses no random source and no clock, so the same request always yields the same fingerprint.
    Reference *content* never participates — only the caller-supplied record ids.
    """
    material = {
        "owner_id": request.owner_id,
        "client_id": request.client_id,
        "engagement_id": request.engagement_id,
        "authorization_scope": request.authorization_scope,
        "requested_by": request.requested_by,
        "requester_role": request.requester_role,
        "report_plan_id": request.report_plan_id or request.idempotency_key,
        "workflow_id": request.workflow_id,
        "managed_record_workflow_ref": request.managed_record_workflow_ref,
        "report_purpose": request.report_purpose,
        "audience": AUDIENCE_INTERNAL,
        "output_status": DEFAULT_OUTPUT_STATUS,
        "sections": list(sections),
        "references": {category: list(refs[category]) for category in REF_CATEGORIES},
    }
    blob = json.dumps(material, sort_keys=True, separators=(",", ":"), default=str)
    return hashlib.sha256(blob.encode("utf-8")).hexdigest()
