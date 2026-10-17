"""Final Report foundation (Phase 208) — an internal assessment in, a report-shaped document out.

Rearranges an existing :class:`~peak.reports.internal_assessment.InternalAssessment` into the six
sections a final report will eventually carry — executive overview, discovery summary,
low-hanging-fruit opportunities, evidence-backed findings, internal recommendations, and
limitations / human review — and renders them as deterministic Markdown.

**It composes an assessment; it never re-reads the database.** The composer's only inputs are the
assessment the Phase 119/206 workflow already built and the engagement's workspace identity (label
and client name) the route already fetched. There is no ``peak.db`` import, no connection, no
writer, no cache and no stored report: a report is recomputed from the assessment on every request,
so it can never drift from the records behind it.

**No new wording that requires interpretation.** Every sentence is a fixed label from this module
or the modules it reads, a value from a stored record quoted exactly, or a count. The executive
summary is counts of what the assessment holds, never a characterisation of it. There is **no LLM
call, no severity, no priority, no ranking, no score, no ROI, and no alignment claim against the
North Star**.

**The evidence/discovery boundary is carried through unchanged.** Discovery material stays under
headings labelled as consultant working material; evidence-backed findings stay under the governed
heading with their review status and reliability. Recommendations are exactly the Phase 118
recommendations the assessment already produced for Phase 117-eligible findings — this module
creates none, and defensively drops any whose finding is not eligible. A low-hanging-fruit flag is
never turned into a recommendation.

**Low-hanging fruit keeps its Phase 206 display grouping.** Candidates arrive already in display
order (value, then effort, as the consultant entered them); this module only splits that order into
labelled groups. No group, candidate, or position carries a rank, score, or priority.

**Internal only.** The report is an internal draft: not client-facing, not approved for client use,
not changed by export (Phase 209), and it always requires consultant review. See
docs/PHASE208_FINAL_REPORT_FOUNDATION.md.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Dict, List, Optional

from .discovery_assessment import (
    DISCOVERY_NOT_EVIDENCE_TEXT,
    LOW_HANGING_FRUIT_GROUPING_TEXT,
    NO_DISCOVERY_TEXT,
    DiscoveryFinding,
    basis_label,
    InterviewCoverage,
    LowHangingFruitCandidate,
)
from .internal_assessment import (
    EVIDENCE_MATERIAL_LABEL,
    NO_DISCOVERY_FINDINGS_TEXT,
    NO_FINDINGS_TEXT,
    NO_LOW_HANGING_FRUIT_TEXT,
    NO_NORTH_STAR_TEXT,
    NO_STATEMENT_TEXT,
    STATUS_INTERNAL_DRAFT,
    AssessmentFinding,
    InternalAssessment,
    InternalRecommendation,
    _trace_line,
)

REPORT_KIND = "final_report_foundation"

#: The section keys, in the only order the report is ever rendered.
SECTION_EXECUTIVE_OVERVIEW = "executive_overview"
SECTION_DISCOVERY_SUMMARY = "discovery_summary"
SECTION_LOW_HANGING_FRUIT = "low_hanging_fruit"
SECTION_EVIDENCE_FINDINGS = "evidence_findings"
SECTION_RECOMMENDATIONS = "recommendations"
SECTION_LIMITATIONS = "limitations"
SECTION_ORDER = (SECTION_EXECUTIVE_OVERVIEW, SECTION_DISCOVERY_SUMMARY, SECTION_LOW_HANGING_FRUIT,
                 SECTION_EVIDENCE_FINDINGS, SECTION_RECOMMENDATIONS, SECTION_LIMITATIONS)

#: What kind of material each section holds. "report" sections only restate counts and fixed text.
MATERIAL_REPORT = "report"
MATERIAL_DISCOVERY = "consultant_working_material"
MATERIAL_EVIDENCE = "evidence_backed_governed"

SECTION_TITLES: Dict[str, str] = {
    SECTION_EXECUTIVE_OVERVIEW: "Executive overview",
    SECTION_DISCOVERY_SUMMARY: "Discovery summary (consultant working material)",
    SECTION_LOW_HANGING_FRUIT: "Low-hanging-fruit opportunities (consultant working material)",
    SECTION_EVIDENCE_FINDINGS: "Evidence-backed findings (governed material)",
    SECTION_RECOMMENDATIONS: "Internal recommendations (evidence-backed only)",
    SECTION_LIMITATIONS: "Limitations and human review",
}

REPORT_STATUS_TEXT = (
    "Internal draft report. Not client-facing and not approved for client use; an exported copy "
    "is still this internal draft. Composed deterministically from the internal assessment; it "
    "requires consultant review before any part of it is used with a client.")

LOW_HANGING_FRUIT_NOT_RANKED_TEXT = (
    "These are the consultant's own flags with the effort and value they entered. They are not "
    "approved recommendations, not a formal ranking, and not a return-on-investment estimate.")

NO_RECOMMENDATIONS_TEXT = (
    "No recommendation is available from the current evidence posture, and none was drafted. "
    "Discovery material and low-hanging-fruit flags do not produce a formal recommendation.")

#: Fixed statements that always appear in the limitations section.
BOUNDARY_STATEMENTS = (
    "Discovery sections hold consultant working material recorded during interviews. It is not "
    "reviewed evidence and carries no review status, reliability rating, or recommendation "
    "eligibility.",
    "Evidence-backed sections hold governed material. Review status and reliability are shown as "
    "recorded; unreviewed evidence is unconfirmed.",
    "Internal recommendations appear only for evidence-backed findings already eligible under the "
    "Phase 117/118 rules.",
    "This report is internal. It has not been approved for client use and requires consultant "
    "review.",
)

_LEVEL_LABELS = {"low": "Low", "medium": "Medium", "high": "High"}


@dataclass
class ExecutiveOverview:
    engagement_id: Optional[str] = None
    engagement_label: Optional[str] = None
    client_id: Optional[str] = None
    client_name: Optional[str] = None
    north_star: Optional[str] = None
    north_star_context: Optional[str] = None
    summary: List[str] = field(default_factory=list)  # counts only, in fixed wording


@dataclass
class DiscoverySummarySection:
    material: str = MATERIAL_DISCOVERY
    available: bool = False
    coverage: Optional[InterviewCoverage] = None
    findings: List[DiscoveryFinding] = field(default_factory=list)
    limitations: List[str] = field(default_factory=list)


@dataclass
class LowHangingFruitGroup:
    """Consecutive candidates sharing the consultant's entered value and effort. Not a tier."""

    estimated_value: Optional[str] = None
    estimated_effort: Optional[str] = None
    label: str = ""
    candidates: List[LowHangingFruitCandidate] = field(default_factory=list)


@dataclass
class LowHangingFruitSection:
    material: str = MATERIAL_DISCOVERY
    grouping_note: str = LOW_HANGING_FRUIT_GROUPING_TEXT
    not_ranked_note: str = LOW_HANGING_FRUIT_NOT_RANKED_TEXT
    groups: List[LowHangingFruitGroup] = field(default_factory=list)


@dataclass
class EvidenceFindingsSection:
    material: str = MATERIAL_EVIDENCE
    findings: List[AssessmentFinding] = field(default_factory=list)
    confidence_notes: List[str] = field(default_factory=list)
    excluded_evidence: List[Dict[str, str]] = field(default_factory=list)


@dataclass
class RecommendationsSection:
    material: str = MATERIAL_EVIDENCE
    status: str = ""
    recommendations: List[InternalRecommendation] = field(default_factory=list)
    blocked_reasons: List[str] = field(default_factory=list)


@dataclass
class LimitationsSection:
    boundary_statements: List[str] = field(default_factory=list)
    assessment_limitations: List[str] = field(default_factory=list)
    discovery_limitations: List[str] = field(default_factory=list)


@dataclass
class FinalReport:
    """The internal Final Report foundation. Derived, never stored, never client-facing."""

    kind: str = REPORT_KIND
    status: str = STATUS_INTERNAL_DRAFT
    audience: str = "internal"
    client_facing: bool = False
    approved_for_client: bool = False
    requires_human_review: bool = True
    section_order: List[str] = field(default_factory=lambda: list(SECTION_ORDER))
    section_titles: Dict[str, str] = field(default_factory=lambda: dict(SECTION_TITLES))
    executive_overview: ExecutiveOverview = field(default_factory=ExecutiveOverview)
    discovery_summary: DiscoverySummarySection = field(default_factory=DiscoverySummarySection)
    low_hanging_fruit: LowHangingFruitSection = field(default_factory=LowHangingFruitSection)
    evidence_findings: EvidenceFindingsSection = field(default_factory=EvidenceFindingsSection)
    recommendations: RecommendationsSection = field(default_factory=RecommendationsSection)
    limitations: LimitationsSection = field(default_factory=LimitationsSection)


def _level(value: Optional[str]) -> str:
    return _LEVEL_LABELS.get(value, "Not stated") if value else "Not stated"


def _group_label(value: Optional[str], effort: Optional[str]) -> str:
    return f"Value {_level(value)} · Effort {_level(effort)}"


def group_low_hanging_fruit(candidates: List[LowHangingFruitCandidate]
                            ) -> List[LowHangingFruitGroup]:
    """Split the Phase 206 display order into labelled groups, keeping that order exactly.

    Grouping is by consecutive equal (value, effort) pairs, so the candidates' order is never
    changed here and no group is assigned a number, score, or tier.
    """
    groups: List[LowHangingFruitGroup] = []
    for candidate in candidates:
        key = (candidate.estimated_value, candidate.estimated_effort)
        if not groups or (groups[-1].estimated_value, groups[-1].estimated_effort) != key:
            groups.append(LowHangingFruitGroup(estimated_value=key[0], estimated_effort=key[1],
                                               label=_group_label(*key)))
        groups[-1].candidates.append(candidate)
    return groups


def _eligible_recommendations(assessment: InternalAssessment) -> List[InternalRecommendation]:
    """The assessment's recommendations whose finding is Phase 117-eligible. None are created."""
    eligible = {f.finding_id for f in assessment.findings
                if f.recommendation_eligible and f.statement_available}
    return [r for r in assessment.recommendations if r.finding_id in eligible]


def _plural(count: int, noun: str) -> str:
    return f"{count} {noun}{'' if count == 1 else 's'}"


def _summary_lines(assessment: InternalAssessment,
                   recommendations: List[InternalRecommendation]) -> List[str]:
    """Counts of what the assessment holds, in fixed wording. No judgement about any of them."""
    discovery = assessment.discovery
    lines = []
    if discovery is not None and discovery.available:
        coverage = discovery.coverage
        lines.append(f"Discovery: {_plural(coverage.total_sessions, 'interview')} recorded "
                     f"({coverage.completed_sessions} completed, {coverage.in_progress_sessions} "
                     f"in progress); people interviewed: {len(coverage.interviewees)}.")
        lines.append(f"Discovery-derived findings: {len(discovery.findings)} consultant "
                     f"observation(s), of which {len(discovery.low_hanging_fruit)} flagged as "
                     f"low-hanging fruit.")
    else:
        lines.append(f"Discovery: {NO_DISCOVERY_TEXT}")
    reviewed = sum(1 for f in assessment.findings if f.review_status != "unreviewed")
    eligible = sum(1 for f in assessment.findings if f.recommendation_eligible)
    lines.append(f"Evidence-backed findings: {len(assessment.findings)}, of which {reviewed} "
                 f"targeted by a review and {eligible} eligible for an internal recommendation.")
    lines.append(f"Internal recommendations: {len(recommendations)} "
                 f"(status: {assessment.recommendation_status}).")
    return lines


def _discovery_limitations(assessment: InternalAssessment) -> List[str]:
    discovery = assessment.discovery
    if discovery is None or not discovery.available:
        return [NO_DISCOVERY_TEXT]
    coverage = discovery.coverage
    items = []
    if not discovery.north_star:
        items.append(NO_NORTH_STAR_TEXT)
    if coverage.in_progress_sessions:
        items.append(f"{_plural(coverage.in_progress_sessions, 'interview')} still in progress.")
    if coverage.branching_makes_percentage_ambiguous:
        items.append("No pool-wide completion percentage is reported: follow-up questions are "
                     "shown only to some interviewees, so the denominator would be ambiguous.")
    if not discovery.findings:
        items.append(NO_DISCOVERY_FINDINGS_TEXT)
    # Phase 216: say plainly how many findings rest on what someone said or concluded.
    uncorroborated = sum(1 for f in discovery.findings if f.basis in ("testimony", "inferred"))
    if uncorroborated:
        items.append(f"{_plural(uncorroborated, 'discovery finding')} rest on client testimony or "
                     "consultant inference only.")
    unrecorded = sum(1 for f in discovery.findings if not f.basis)
    if unrecorded:
        items.append(f"{_plural(unrecorded, 'discovery finding')} have no recorded basis.")
    return items


def compose_final_report(assessment: InternalAssessment,
                         engagement: Optional[dict] = None) -> FinalReport:
    """Compose the Final Report foundation from an existing internal assessment.

    ``engagement`` is the workspace engagement dict the caller already holds (label and client
    name only are read). Nothing is fetched here, and the assessment is not modified.
    """
    engagement = engagement or {}
    discovery = assessment.discovery
    recommendations = _eligible_recommendations(assessment)
    discovery_limitations = _discovery_limitations(assessment)
    return FinalReport(
        audience=assessment.audience,
        executive_overview=ExecutiveOverview(
            engagement_id=assessment.engagement_id or engagement.get("id"),
            engagement_label=engagement.get("engagement_label"),
            client_id=assessment.client_id or (engagement.get("client") or {}).get("id"),
            client_name=(engagement.get("client") or {}).get("name"),
            north_star=discovery.north_star if discovery else None,
            north_star_context=discovery.north_star_context if discovery else None,
            summary=_summary_lines(assessment, recommendations),
        ),
        discovery_summary=DiscoverySummarySection(
            available=bool(discovery and discovery.available),
            coverage=discovery.coverage if discovery and discovery.available else None,
            findings=list(discovery.findings) if discovery else [],
            limitations=discovery_limitations,
        ),
        low_hanging_fruit=LowHangingFruitSection(
            groups=group_low_hanging_fruit(list(discovery.low_hanging_fruit) if discovery else [])),
        evidence_findings=EvidenceFindingsSection(
            findings=list(assessment.findings),
            confidence_notes=list(assessment.confidence_notes),
            excluded_evidence=list(assessment.excluded_evidence),
        ),
        recommendations=RecommendationsSection(
            status=assessment.recommendation_status,
            recommendations=recommendations,
            blocked_reasons=list(assessment.recommendation_blocked_reasons),
        ),
        limitations=LimitationsSection(
            boundary_statements=list(BOUNDARY_STATEMENTS),
            assessment_limitations=list(assessment.limitations),
            discovery_limitations=list(discovery_limitations),
        ),
    )


# --- Markdown -----------------------------------------------------------------------------------

def _render_overview(report: FinalReport) -> List[str]:
    o = report.executive_overview
    lines = [f"## {SECTION_TITLES[SECTION_EXECUTIVE_OVERVIEW]}", "",
             f"- Engagement: {o.engagement_label or 'Untitled engagement'} ({o.engagement_id})",
             f"- Client: {o.client_name or 'not recorded'}"
             + (f" ({o.client_id})" if o.client_id else ""), "",
             "### North Star", ""]
    if o.north_star:
        lines += [o.north_star, ""]
        if o.north_star_context:
            lines += [o.north_star_context, ""]
    else:
        lines += [f"_{NO_NORTH_STAR_TEXT}_", ""]
    lines += ["### Summary", ""] + [f"- {line}" for line in o.summary] + [""]
    return lines


def _render_discovery(report: FinalReport) -> List[str]:
    s = report.discovery_summary
    lines = [f"## {SECTION_TITLES[SECTION_DISCOVERY_SUMMARY]}", "", DISCOVERY_NOT_EVIDENCE_TEXT, "",
             "### Interview coverage", ""]
    if s.coverage is None:
        lines += [f"_{NO_DISCOVERY_TEXT}_", ""]
    else:
        c = s.coverage
        lines += [f"- Interviews: {c.total_sessions} ({c.completed_sessions} completed, "
                  f"{c.in_progress_sessions} in progress)",
                  f"- People interviewed: {len(c.interviewees)}"
                  + (f" — {', '.join(c.interviewees)}" if c.interviewees else "")]
        if c.interviewee_titles:
            lines.append(f"- Roles represented: {', '.join(c.interviewee_titles)}")
        lines.append(f"- Distinct questions answered: {c.answered_questions} "
                     f"(of {c.active_questions} active question(s) in the pool)")
        if c.branching_makes_percentage_ambiguous:
            lines.append(f"- Of the {c.unbranched_active_questions} question(s) every interview "
                         f"sees, {c.answered_unbranched_questions} have been answered.")
        lines.append("")
    lines += ["### Discovery-derived findings", ""]
    if not s.findings:
        lines += [f"_{NO_DISCOVERY_FINDINGS_TEXT}_", ""]
    for finding in s.findings:
        lines += [f"- {finding.statement}",
                  f"  - Category: {finding.category or 'none recorded'}",
                  f"  - Basis: {basis_label(finding.basis)}",
                  f"  - Where this came from: {_trace_line(finding.trace)}"]
    if s.findings:
        lines.append("")
    lines += ["### Discovery limitations", ""]
    lines += [f"- {item}" for item in s.limitations] or ["- None recorded."]
    return lines + [""]


def _render_low_hanging_fruit(report: FinalReport) -> List[str]:
    s = report.low_hanging_fruit
    lines = [f"## {SECTION_TITLES[SECTION_LOW_HANGING_FRUIT]}", ""]
    if not s.groups:
        return lines + [f"_{NO_LOW_HANGING_FRUIT_TEXT}_", ""]
    lines += [s.grouping_note, "", s.not_ranked_note, ""]
    for group in s.groups:
        lines += [f"### {group.label}", ""]
        for candidate in group.candidates:
            lines += [f"- {candidate.statement}",
                      f"  - Category: {candidate.category or 'none recorded'}",
                      f"  - Consultant-entered effort: {_level(candidate.estimated_effort)}; "
                      f"value: {_level(candidate.estimated_value)}",
                      f"  - Basis: {basis_label(candidate.basis)}",
                      f"  - Where this came from: {_trace_line(candidate.trace)}"]
        lines.append("")
    return lines


def _render_evidence(report: FinalReport) -> List[str]:
    s = report.evidence_findings
    lines = [f"## {SECTION_TITLES[SECTION_EVIDENCE_FINDINGS]}", "", EVIDENCE_MATERIAL_LABEL, ""]
    if not s.findings:
        lines += [NO_FINDINGS_TEXT, ""]
    for index, finding in enumerate(s.findings, start=1):
        lines += [f"### Finding {index} — {finding.finding_id}", "",
                  finding.statement if finding.statement_available else f"_{NO_STATEMENT_TEXT}_",
                  "",
                  f"- Evidence: {finding.evidence_id}",
                  f"- Source: {', '.join(finding.source_reference_ids) or 'none recorded'}",
                  f"- Review status: {finding.review_status}",
                  f"- Supporting reviews: {', '.join(finding.supporting_review_ids) or 'none'}",
                  f"- Reliability: {finding.reliability or 'not recorded'}",
                  f"- Claim scope: {finding.claim_scope or 'not recorded'}",
                  f"- Recommendation eligibility: "
                  f"{'eligible' if finding.recommendation_eligible else 'blocked'}", ""]
    if s.confidence_notes:
        lines += ["### Evidence confidence", ""] + [f"- {n}" for n in s.confidence_notes] + [""]
    return lines


def _render_recommendations(report: FinalReport) -> List[str]:
    s = report.recommendations
    lines = [f"## {SECTION_TITLES[SECTION_RECOMMENDATIONS]}", ""]
    if not s.recommendations:
        lines += [f"**{s.status.capitalize()}.** {NO_RECOMMENDATIONS_TEXT}", ""]
        lines += [f"- {reason}" for reason in s.blocked_reasons]
        return lines + [""] if s.blocked_reasons else lines
    for rec in s.recommendations:
        lines += [f"- {rec.text}",
                  f"  - For finding {rec.finding_id}; evidence "
                  f"{', '.join(rec.supporting_evidence_ids)}",
                  "  - Internal only; requires human review"]
    return lines + [""]


def _render_limitations(report: FinalReport) -> List[str]:
    s = report.limitations
    lines = [f"## {SECTION_TITLES[SECTION_LIMITATIONS]}", ""]
    lines += [f"- {item}" for item in s.boundary_statements] + [""]
    lines += ["### Evidence limitations", ""]
    lines += [f"- {item}" for item in s.assessment_limitations] or ["- None recorded."]
    lines += ["", "### Discovery limitations", ""]
    lines += [f"- {item}" for item in s.discovery_limitations] or ["- None recorded."]
    return lines + [""]


def render_final_report_markdown(report: FinalReport) -> str:
    """Render the report as deterministic Markdown, sections in :data:`SECTION_ORDER`."""
    o = report.executive_overview
    lines = [f"# Final report (internal draft) — {o.engagement_label or o.engagement_id}", "",
             f"- Status: {report.status}",
             f"- Client-facing: {'yes' if report.client_facing else 'no'}",
             f"- Approved for client use: {'yes' if report.approved_for_client else 'no'}",
             f"- Requires human review: {'yes' if report.requires_human_review else 'no'}", "",
             REPORT_STATUS_TEXT, ""]
    renderers = {
        SECTION_EXECUTIVE_OVERVIEW: _render_overview,
        SECTION_DISCOVERY_SUMMARY: _render_discovery,
        SECTION_LOW_HANGING_FRUIT: _render_low_hanging_fruit,
        SECTION_EVIDENCE_FINDINGS: _render_evidence,
        SECTION_RECOMMENDATIONS: _render_recommendations,
        SECTION_LIMITATIONS: _render_limitations,
    }
    for key in SECTION_ORDER:
        lines += renderers[key](report)
    return "\n".join(lines).rstrip("\n") + "\n"
