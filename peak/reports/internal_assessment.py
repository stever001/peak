"""Consultant-readable internal assessment (Phase 116) — reporting inputs in, a document out.

Turns the Phase 111 :class:`~peak.reports.packet_view_report.PacketViewReportInputs` into an
:class:`InternalAssessment` — a small, immutable-in-practice object a consultant can read — and
renders it as deterministic Markdown. This is the end of the persisted-state route: stored records
supply identity, relationships, review targets, the governed claim scope (Phase 114), and the
finding statement (Phase 115), and this module arranges them into something usable.

**It composes; it never writes.** Every sentence in the output is either a fixed label from this
module or a value that came from a stored record. Nothing is generated, paraphrased, inferred, or
filled in: a finding with no persisted statement says so, and stays in the document. There is **no
LLM call, no severity, no priority, no ranking, no root cause, no ROI, no inventory-accuracy figure,
no source-of-record claim, and no operational prescription** — none of those are supported by the
current evidence posture, so none appear.

**Recommendations are bounded (Phase 118).** Each finding carries its Phase 117 eligibility (eligible
/ blocked, with the bridge's blocker reasons). Only an eligible finding receives one
:class:`InternalRecommendation`, built from the fixed :data:`RECOMMENDATION_TEMPLATE` around its
persisted statement, quoted verbatim — no root cause, no prescribed fix, no LLM. A blocked finding
receives none. Recommendations are internal-only and always require human review.

**Internal only.** ``audience`` is internal, ``status`` is internal draft, ``client_facing`` is
always false, and human review is always required.

**Discovery material sits beside evidence, never inside it (Phase 206).** An optional
:class:`~peak.reports.discovery_assessment.DiscoveryAssessmentContext` adds the engagement's North
Star, interview coverage, consultant-recorded discovery findings, and low-hanging-fruit candidates
under their own clearly labelled headings. It is additive and inert: discovery never enters
``findings``, never produces an :class:`InternalRecommendation`, and never changes a review status,
reliability, claim scope, or the Phase 117 eligibility of any evidence-backed finding. An
assessment built without it renders exactly as before, minus a short line saying no discovery
material was recorded.

Side-effect boundary: pure functions over an in-memory ``PacketViewReportInputs``. No database
connection, no SQLAlchemy / ``peak.db`` import, no environment read, no file or network access, no
writer, no agent execution, and no LLM. Output is deterministic — fixed section order, records in
the order the bridge already sorted them, and no timestamp or random id. See
docs/PHASE116_CONSULTANT_INTERNAL_ASSESSMENT.md.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Dict, List, Optional

from .contracts import AUDIENCE_INTERNAL, SECTION_OPERATIONAL_FINDINGS, SECTION_TITLES
from .discovery_assessment import (
    DISCOVERY_NOT_EVIDENCE_TEXT,
    LOW_HANGING_FRUIT_GROUPING_TEXT,
    NO_DISCOVERY_TEXT,
    DiscoveryAssessmentContext,
)

#: The only status this document can carry. It is a working document, not a deliverable.
STATUS_INTERNAL_DRAFT = "internal_draft"

#: Recommendation statuses. "internal_draft" only when an eligible finding produced a recommendation.
RECOMMENDATIONS_BLOCKED = "blocked"
RECOMMENDATIONS_INTERNAL_DRAFT = "internal_draft"

#: The only recommendation wording this module produces (Phase 118). It asks for investigation and
#: validation of the finding as stated, and names no cause, fix, cost, or priority.
RECOMMENDATION_TEMPLATE = 'Investigate and validate corrective action for the finding: "{statement}"'

#: The packet view already spells a missing section as "... (not supplied)"; strip that so the
#: limitation line does not say it twice.
_SUPPLY_SUFFIX = " (not supplied)"

#: Phase 206 headings. Each names which kind of material it holds, so a reader never has to infer
#: whether a section is governed evidence or consultant working material.
DISCOVERY_SECTION_TITLE = "Discovery summary (consultant working material)"
DISCOVERY_FINDINGS_SECTION_TITLE = "Discovery-derived findings (consultant working material)"
LOW_HANGING_FRUIT_SECTION_TITLE = "Low-hanging-fruit candidates (consultant working material)"
NORTH_STAR_SECTION_TITLE = "North Star"
EVIDENCE_MATERIAL_LABEL = "Evidence-backed, governed material."
NO_NORTH_STAR_TEXT = "No North Star has been recorded for this engagement."
NO_DISCOVERY_FINDINGS_TEXT = "No consultant observation has been recorded for this engagement."
NO_LOW_HANGING_FRUIT_TEXT = "The consultant has flagged no low-hanging fruit for this engagement."

NO_STATEMENT_TEXT = "No persisted finding statement is available for this evidence."
NO_FINDINGS_TEXT = "No evidence currently supports an operational finding for this engagement."
NOT_CLIENT_FACING_TEXT = (
    "Internal working document. Not client-facing, not approved, and not a deliverable. "
    "Every finding below requires human review before it is used with a client.")


@dataclass
class AssessmentFinding:
    """One readable finding: its persisted statement and the posture of the evidence behind it."""

    finding_id: str
    evidence_id: str
    statement: Optional[str] = None  # persisted; None means the evidence carries none
    statement_available: bool = False
    source_reference_ids: List[str] = field(default_factory=list)
    review_status: str = ""  # effective, derived from reviews that target this evidence
    stored_review_status: Optional[str] = None
    supporting_review_ids: List[str] = field(default_factory=list)
    reliability: Optional[str] = None
    claim_scope: Optional[str] = None
    recommendation_eligible: bool = False  # Phase 117: decided by the bridge, never here
    recommendation_blocked_reasons: List[str] = field(default_factory=list)
    recommendation_id: Optional[str] = None  # Phase 118: set only for an eligible finding


@dataclass
class InternalRecommendation:
    """One bounded internal recommendation for one eligible finding (Phase 118). Never client-facing."""

    recommendation_id: str
    finding_id: str
    text: str
    supporting_evidence_ids: List[str] = field(default_factory=list)
    supporting_source_ids: List[str] = field(default_factory=list)
    supporting_review_ids: List[str] = field(default_factory=list)
    internal_only: bool = True
    requires_human_review: bool = True


@dataclass
class InternalAssessment:
    """A consultant-readable internal assessment assembled from persisted state."""

    engagement_id: Optional[str] = None
    client_id: Optional[str] = None
    owner_id: Optional[str] = None
    authorization_scope: Optional[str] = None
    audience: str = AUDIENCE_INTERNAL
    status: str = STATUS_INTERNAL_DRAFT
    client_facing: bool = False
    requires_human_review: bool = True
    findings: List[AssessmentFinding] = field(default_factory=list)
    confidence_notes: List[str] = field(default_factory=list)
    excluded_evidence: List[Dict[str, str]] = field(default_factory=list)
    limitations: List[str] = field(default_factory=list)
    recommendation_status: str = RECOMMENDATIONS_BLOCKED
    recommendation_blocked_reasons: List[str] = field(default_factory=list)
    recommendations: List[InternalRecommendation] = field(default_factory=list)
    #: Phase 206 consultant discovery material, or ``None`` when the engagement has none. It is
    #: displayed beside the evidence-backed sections and never merged into them.
    discovery: Optional[DiscoveryAssessmentContext] = None


def _recommendation_for(finding: AssessmentFinding) -> Optional[InternalRecommendation]:
    """The bounded recommendation for an eligible finding with a statement; otherwise ``None``."""
    if not finding.recommendation_eligible or not finding.statement_available:
        return None
    return InternalRecommendation(
        recommendation_id=f"rec_{finding.finding_id}",
        finding_id=finding.finding_id,
        text=RECOMMENDATION_TEMPLATE.format(statement=finding.statement),
        supporting_evidence_ids=[finding.evidence_id],
        supporting_source_ids=list(finding.source_reference_ids),
        supporting_review_ids=list(finding.supporting_review_ids),
    )


def _confidence_notes(findings: List[AssessmentFinding]) -> List[str]:
    """State the confidence position as a fact about the cited evidence, never as a judgement."""
    if not findings:
        return []
    notes = []
    unreviewed = [f.evidence_id for f in findings if f.review_status == "unreviewed"]
    if unreviewed:
        notes.append(f"{len(unreviewed)} of {len(findings)} finding(s) cite evidence that no review "
                     f"has targeted; their review status is unreviewed.")
    low = [f.evidence_id for f in findings if f.reliability == "low"]
    if low:
        notes.append(f"{len(low)} of {len(findings)} finding(s) cite evidence recorded at low "
                     f"reliability.")
    missing = [f.evidence_id for f in findings if not f.statement_available]
    if missing:
        notes.append(f"{len(missing)} of {len(findings)} finding(s) have no persisted statement; "
                     f"no wording was generated for them.")
    return notes


def build_internal_assessment(report_inputs,
                              discovery: Optional[DiscoveryAssessmentContext] = None
                              ) -> InternalAssessment:
    """Build an :class:`InternalAssessment` from Phase 111 reporting inputs.

    Findings keep the order the bridge produced, so the same inputs always yield the same document.
    Nothing is added that the inputs did not already carry.

    ``discovery`` (Phase 206) is attached as-is and takes no part in any decision below: it does not
    reach ``findings``, ``recommendations``, ``confidence_notes``, or ``limitations``, and the
    recommendation status is computed before it is attached. Passing ``None`` — or a context with
    no material — leaves the assessment exactly as Phases 116–118 produced it.
    """
    engagement = report_inputs.engagement or {}
    assessment = InternalAssessment(
        engagement_id=engagement.get("engagement_id"),
        client_id=engagement.get("client_id"),
        owner_id=engagement.get("owner_id"),
        authorization_scope=engagement.get("authorization_scope"),
        audience=report_inputs.audience,
        client_facing=bool(report_inputs.client_facing_allowed),
        # Blocked unless an eligible finding produces a recommendation below.
        recommendation_status=RECOMMENDATIONS_BLOCKED,
        recommendation_blocked_reasons=list(report_inputs.recommendations_blocked_reasons),
    )

    for item in report_inputs.finding_inputs:
        assessment.findings.append(AssessmentFinding(
            finding_id=item.finding_candidate_id,
            evidence_id=item.cited_evidence_id,
            statement=item.finding_statement,
            statement_available=item.finding_statement is not None,
            source_reference_ids=[item.source_reference_id] if item.source_reference_id else [],
            review_status=item.effective_review_status,
            stored_review_status=item.stored_review_status,
            supporting_review_ids=list(item.review_support_refs),
            reliability=item.reliability,
            claim_scope=item.claim_scope,
            recommendation_eligible=bool(item.recommendation_eligible),
            recommendation_blocked_reasons=list(item.recommendation_blocked_reasons),
        ))

    for finding in assessment.findings:
        recommendation = _recommendation_for(finding)
        if recommendation is not None:
            finding.recommendation_id = recommendation.recommendation_id
            assessment.recommendations.append(recommendation)
    if assessment.recommendations:
        assessment.recommendation_status = RECOMMENDATIONS_INTERNAL_DRAFT

    assessment.confidence_notes = _confidence_notes(assessment.findings)
    assessment.excluded_evidence = [{"evidence_id": x.evidence_id, "reason": x.reason}
                                    for x in report_inputs.excluded_evidence]

    # Limitations are carried through from what the reporting inputs already established, plus the
    # posture of each finding. Nothing new is asserted about the engagement.
    limitations = list(report_inputs.strict_engagement_packet_reasons)
    for section in report_inputs.missing_sections:
        label = section[:-len(_SUPPLY_SUFFIX)] if section.endswith(_SUPPLY_SUFFIX) else section
        limitations.append(f"not supplied: {label}")
    for finding in assessment.findings:
        if finding.review_status == "unreviewed":
            limitations.append(
                f"{finding.evidence_id} has not been reviewed, so this finding is unconfirmed.")
        if not finding.statement_available:
            limitations.append(f"{finding.evidence_id} carries no persisted statement.")
    for excluded in assessment.excluded_evidence:
        limitations.append(f"{excluded['evidence_id']} backs no finding: {excluded['reason']}.")
    assessment.limitations = limitations

    # Attached last, and only after every evidence decision above is final, so there is no order in
    # which discovery material could influence one.
    assessment.discovery = discovery
    return assessment


def _trace_line(trace) -> str:
    """One readable provenance line: the person and interview first, identifiers after.

    A consultant reading this should be able to answer "where did this come from?" without knowing
    what a governance id is, so the interviewee's name leads and the raw ids follow in parentheses.
    """
    parts = []
    if trace.interviewee_name:
        parts.append(f"interview with {trace.interviewee_name}")
    elif trace.session_id:
        parts.append("recorded outside an interview")
    else:
        parts.append("recorded outside an interview")
    if trace.question_prompt:
        parts.append(f'question "{trace.question_prompt}"')
    if trace.recorded_by:
        parts.append(f"recorded by {trace.recorded_by}")
    ids = [f"observation {trace.observation_id}" if trace.observation_id else "",
           f"session {trace.session_id}" if trace.session_id else "",
           f"question {trace.question_id}" if trace.question_id else "",
           f"answer {trace.answer_id}" if trace.answer_id else ""]
    ids = [i for i in ids if i]
    line = "; ".join(parts)
    return f"{line} ({', '.join(ids)})" if ids else line


def _render_north_star(discovery: Optional[DiscoveryAssessmentContext]) -> List[str]:
    """The North Star, for orientation. It scores nothing and claims no alignment."""
    lines = [f"## {NORTH_STAR_SECTION_TITLE}", ""]
    if discovery is None or not discovery.north_star:
        return lines + [f"_{NO_NORTH_STAR_TEXT}_", ""]
    lines += [discovery.north_star, ""]
    if discovery.north_star_context:
        lines += [discovery.north_star_context, ""]
    return lines


def _render_discovery_summary(discovery: Optional[DiscoveryAssessmentContext]) -> List[str]:
    """Interview coverage as counts. No completeness percentage over an ambiguous denominator."""
    lines = [f"## {DISCOVERY_SECTION_TITLE}", "", DISCOVERY_NOT_EVIDENCE_TEXT, ""]
    if discovery is None or not discovery.available:
        return lines + [f"_{NO_DISCOVERY_TEXT}_", ""]
    coverage = discovery.coverage
    lines += [
        f"- Interviews: {coverage.total_sessions} "
        f"({coverage.completed_sessions} completed, {coverage.in_progress_sessions} in progress)",
        f"- People interviewed: {len(coverage.interviewees)}"
        + (f" — {', '.join(coverage.interviewees)}" if coverage.interviewees else ""),
    ]
    if coverage.interviewee_titles:
        lines.append(f"- Roles represented: {', '.join(coverage.interviewee_titles)}")
    lines.append(f"- Distinct questions answered: {coverage.answered_questions} "
                 f"(of {coverage.active_questions} active question(s) in the pool)")
    if coverage.branching_makes_percentage_ambiguous:
        lines.append(
            f"- Of the {coverage.unbranched_active_questions} question(s) every interview sees, "
            f"{coverage.answered_unbranched_questions} have been answered. A single percentage "
            f"across the whole pool is not reported: branching means follow-up questions are shown "
            f"only to some interviewees, so the denominator would be ambiguous.")
    lines.append("")
    for interview in coverage.sessions:
        title = f" ({interview.interviewee_title})" if interview.interviewee_title else ""
        conducted = f", conducted by {interview.conducted_by}" if interview.conducted_by else ""
        lines.append(f"- {interview.interviewee_name}{title} — {interview.status}, "
                     f"{interview.answered_count} question(s) answered{conducted}")
    lines.append("")
    return lines


def _render_discovery_findings(discovery: Optional[DiscoveryAssessmentContext]) -> List[str]:
    """Consultant observations, quoted. Each says plainly that it is not evidence."""
    lines = [f"## {DISCOVERY_FINDINGS_SECTION_TITLE}", ""]
    findings = discovery.findings if discovery else []
    if not findings:
        return lines + [f"_{NO_DISCOVERY_FINDINGS_TEXT}_", ""]
    for index, finding in enumerate(findings, start=1):
        lines += [f"### Discovery finding {index} — {finding.finding_id}", "", finding.statement, ""]
        lines.append(f"- Category: {finding.category or 'none recorded'}")
        lines.append(f"- Source: {finding.source_type}")
        lines.append(f"- Where this came from: {_trace_line(finding.trace)}")
        if finding.low_hanging_fruit:
            lines.append(f"- Consultant flagged as low-hanging fruit: effort "
                         f"{finding.estimated_effort or 'not stated'}, value "
                         f"{finding.estimated_value or 'not stated'}")
        lines += [f"- Status: {finding.status}",
                  "- Evidence status: none. This is not reviewed evidence and supports no formal "
                  "recommendation.",
                  f"- Internal only: {'yes' if finding.internal_only else 'no'}",
                  f"- Requires human review: "
                  f"{'yes' if finding.requires_human_review else 'no'}", ""]
    return lines


def _render_low_hanging_fruit(discovery: Optional[DiscoveryAssessmentContext]) -> List[str]:
    """Consultant-flagged candidates, grouped for reading. Explicitly not a ranking."""
    lines = [f"## {LOW_HANGING_FRUIT_SECTION_TITLE}", ""]
    candidates = discovery.low_hanging_fruit if discovery else []
    if not candidates:
        return lines + [f"_{NO_LOW_HANGING_FRUIT_TEXT}_", ""]
    lines += [LOW_HANGING_FRUIT_GROUPING_TEXT, ""]
    for candidate in candidates:
        lines += [f"### {candidate.finding_id}", "", candidate.statement, ""]
        lines += [f"- Category: {candidate.category or 'none recorded'}",
                  f"- Consultant-entered effort: {candidate.estimated_effort or 'not stated'}",
                  f"- Consultant-entered value: {candidate.estimated_value or 'not stated'}",
                  f"- Where this came from: {_trace_line(candidate.trace)}",
                  "- Not an approved recommendation. The consultant's own flag on their own "
                  "observation; it requires human review before it is used with a client.", ""]
    return lines


def render_internal_assessment_markdown(assessment: InternalAssessment) -> str:
    """Render the assessment as deterministic Markdown a consultant can read or copy directly.

    The persisted statement is written **exactly as stored** — never re-wrapped, re-worded, or
    summarised. Every other line is a fixed label from this module or a stored value.
    """
    lines: List[str] = [
        f"# Internal assessment — {assessment.engagement_id}",
        "",
        f"- Status: {assessment.status}",
        f"- Audience: {assessment.audience}",
        f"- Client-facing: {'yes' if assessment.client_facing else 'no'}",
        f"- Requires human review: {'yes' if assessment.requires_human_review else 'no'}",
        f"- Owner: {assessment.owner_id}",
        f"- Client: {assessment.client_id}",
        f"- Authorization scope: {assessment.authorization_scope}",
        "",
        NOT_CLIENT_FACING_TEXT,
        "",
    ]

    # Phase 206: discovery material first, for orientation, each section labelled as consultant
    # working material. Everything after this point is the evidence-backed document, unchanged.
    lines += _render_north_star(assessment.discovery)
    lines += _render_discovery_summary(assessment.discovery)
    lines += _render_discovery_findings(assessment.discovery)
    lines += _render_low_hanging_fruit(assessment.discovery)

    lines += [f"## {SECTION_TITLES[SECTION_OPERATIONAL_FINDINGS]} "
              f"(evidence-backed, governed material)", "", EVIDENCE_MATERIAL_LABEL, ""]

    if not assessment.findings:
        lines += [NO_FINDINGS_TEXT, ""]
    for index, finding in enumerate(assessment.findings, start=1):
        lines.append(f"### Finding {index} — {finding.finding_id}")
        lines.append("")
        lines.append(finding.statement if finding.statement_available else f"_{NO_STATEMENT_TEXT}_")
        lines.append("")
        lines.append(f"- Evidence: {finding.evidence_id}")
        sources = ", ".join(finding.source_reference_ids) or "none recorded"
        lines.append(f"- Source: {sources}")
        lines.append(f"- Review status: {finding.review_status} "
                     f"(stored on the evidence record: {finding.stored_review_status})")
        supporting = ", ".join(finding.supporting_review_ids) or "none"
        lines.append(f"- Supporting reviews: {supporting}")
        lines.append(f"- Reliability: {finding.reliability}")
        lines.append(f"- Claim scope: {finding.claim_scope}")
        lines.append(f"- Recommendation eligibility: "
                     f"{'eligible' if finding.recommendation_eligible else 'blocked'}")
        lines += [f"  - {reason}" for reason in finding.recommendation_blocked_reasons]
        if finding.recommendation_id:
            lines.append(f"- Internal recommendation: {finding.recommendation_id}")
        lines.append("")

    lines += ["## Evidence and confidence", ""]
    lines += [f"- {note}" for note in assessment.confidence_notes] or (
        ["- No additional evidence-confidence caveats."] if assessment.findings
        else ["- No findings to assess."])
    lines.append("")

    lines += ["## Open limitations and unresolved questions", ""]
    lines += [f"- {item}" for item in assessment.limitations] or ["- None recorded."]
    lines.append("")

    lines += ["## Recommendations", ""]
    if not assessment.recommendations:
        lines += [f"**{assessment.recommendation_status.capitalize()}.** No recommendation is "
                  f"available from the current evidence posture, and none was drafted.", ""]
        lines += [f"- {reason}" for reason in assessment.recommendation_blocked_reasons]
        lines.append("")
    else:
        lines += [f"**Internal draft.** {len(assessment.recommendations)} bounded internal "
                  f"recommendation(s), only for recommendation-eligible findings. Internal only; each "
                  f"requires human review.", ""]
    for rec in assessment.recommendations:
        lines += [f"### {rec.recommendation_id} — for {rec.finding_id}", "", rec.text, "",
                  f"- Evidence: {', '.join(rec.supporting_evidence_ids)}",
                  f"- Source: {', '.join(rec.supporting_source_ids) or 'none recorded'}",
                  f"- Supporting reviews: {', '.join(rec.supporting_review_ids) or 'none'}",
                  f"- Internal only: {'yes' if rec.internal_only else 'no'}",
                  f"- Requires human review: {'yes' if rec.requires_human_review else 'no'}", ""]
    return "\n".join(lines)
