"""Discovery material as assessment context (Phase 206) — persisted discovery in, a projection out.

Turns the Phase 206 discovery summaries into a :class:`DiscoveryAssessmentContext`: the North Star,
a deterministic interview-coverage summary, discovery-derived findings, and consultant-flagged
low-hanging-fruit candidates, each carrying enough traceability to answer "where did this come
from?".

**Discovery is not evidence, and this module never lets it become evidence.** A discovery-derived
finding is consultant working material. It carries no review status, no reliability, no claim
scope, and — deliberately — no ``recommendation_eligible`` field at all, so there is no attribute
for a later caller to flip. The Phase 117/118 eligibility rules are untouched: they decide the fate
of evidence-backed findings only. Every object this module produces is
``internal_only`` and ``requires_human_review``.

**Phase 226: a Lead review is the one route to recommendation eligibility.** The engagement's Lead
Consultant may review an observation as worded (``observation_lead_reviews``). Eligibility is then
*derived* by :func:`observation_recommendation_block_reasons`, a fixed rule over that stored review
and the finding, and held apart from the finding in
:attr:`DiscoveryAssessmentContext.recommendation_eligibility`. The finding itself still has no
eligibility, review or reliability field, so nothing that renders a finding can carry one, and
nothing here drafts a recommendation. Phase 227: the internal assessment gives an eligible finding
the Phase 118 bounded recommendation; the finding itself is unchanged.

**A low-hanging-fruit flag is not an approved recommendation.** It is the consultant's own mark on
their own observation. It is displayed, grouped for readability, and never scored.

**It composes; it never writes, and it never infers.** Every statement in the output is either a
fixed label from this module or a value that came from a stored record. A discovery finding's
statement is the consultant's ``observation_text`` **quoted exactly as stored** — never re-worded,
summarised, or expanded. There is **no LLM call, no severity, no priority, no ranking, no root
cause, no ROI, and no alignment claim against the North Star**.

**Coverage is counted, never estimated.** Branching means the set of questions a given interview
should have shown depends on that interview's own answers, so a single global "answered out of
active" percentage would be arithmetic over an ambiguous denominator. This module therefore reports
**counts**, and reports a percentage only for the unbranched questions every interview sees. See
:func:`build_interview_coverage`.

Side-effect boundary: pure functions over plain dicts. No database connection, no ``peak.db``
import, no environment read, no file or network access, no writer, and no LLM. Output is
deterministic — fixed ordering, no timestamp, no random id. See
docs/PHASE206_DISCOVERY_ASSESSMENT_INTEGRATION.md.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Dict, List, Optional

from .packet_view_report import RECOMMENDATION_RELIABILITY

#: Where a discovery-derived finding came from. Only the first is produced today: a consultant
#: observation is an explicit, deliberate statement, whereas turning every answer into a finding
#: would be inference. ``DIRECT_STRUCTURED_ANSWER`` is the reserved name for the narrow future case
#: where a structured answer supports a statement with no interpretation at all.
SOURCE_DISCOVERY_OBSERVATION = "discovery_observation"
SOURCE_DIRECT_STRUCTURED_ANSWER = "direct_structured_answer"

#: Phase 216: what a consultant observation rests on, as readers see it. A basis describes footing;
#: it never promotes discovery material to evidence (Contract C4), whichever value it has.
OBSERVATION_BASIS_LABELS = {
    "testimony": "Client testimony",
    "observed": "Consultant observation on site",
    "document": "Document or system record reviewed by the consultant",
    "measured": "Measured or counted by the consultant",
    "inferred": "Consultant inference",
}
BASIS_NOT_RECORDED_TEXT = "Basis not recorded"


def basis_label(basis: Optional[str]) -> str:
    return OBSERVATION_BASIS_LABELS.get(basis, BASIS_NOT_RECORDED_TEXT)


#: The status every discovery-derived item carries. It is working material, never a deliverable.
DISCOVERY_STATUS_CONSULTANT_WORKING_MATERIAL = "consultant_working_material"

#: Effort/value levels as the consultant entered them. Ordered only for display grouping.
_VALUE_ORDER = {"high": 0, "medium": 1, "low": 2}
_EFFORT_ORDER = {"low": 0, "medium": 1, "high": 2}

DISCOVERY_NOT_EVIDENCE_TEXT = (
    "Consultant discovery material. Recorded during interviews, not reviewed evidence: it carries "
    "no review status, no reliability rating, and no recommendation eligibility. It informs the "
    "assessment; it does not support a formal recommendation on its own.")

#: Phase 225: the same statement when some of the material was not recorded in an interview.
DISCOVERY_NOT_EVIDENCE_WIDER_TEXT = DISCOVERY_NOT_EVIDENCE_TEXT.replace(
    "during interviews,", "during interviews or other consulting work,")

#: Phase 226: the internal assessment's ending for that sentence once any observation has a Lead
#: review, because "no reliability rating, and no recommendation eligibility" is then untrue.
_NO_STANDING_TAIL = ("it carries no review status, no reliability rating, and no recommendation "
                     "eligibility. It informs the assessment; it does not support a formal "
                     "recommendation on its own.")
LEAD_REVIEWED_TAIL = (
    "it carries no evidence review status. Only an observation shown with an approving Lead review "
    "carries a reliability rating and can be eligible to support a recommendation. None of it "
    "supports a formal recommendation on its own, and no recommendation is drafted from it.")
#: Phase 227: the ending once an eligible observation has the bounded recommendation, since "no
#: recommendation is drafted from it" is then untrue. Used only then.
RECOMMENDED_TAIL = (
    "it carries no evidence review status. Only an observation shown with an approving Lead review "
    "carries a reliability rating and can be eligible to support a recommendation. None of it "
    "supports a formal recommendation on its own: an eligible observation supports only the fixed, "
    "bounded recommendation wording, and it never becomes evidence.")
assert _NO_STANDING_TAIL in DISCOVERY_NOT_EVIDENCE_TEXT

LOW_HANGING_FRUIT_GROUPING_TEXT = (
    "Grouped for reading by the effort and value the consultant entered. This is a display "
    "grouping, not a score, a ranking, or a priority order, and no ROI is calculated.")

NO_DISCOVERY_TEXT = "No discovery material has been recorded for this engagement."

#: Phase 226: why a discovery-derived finding cannot support a recommendation; none means eligible.
#: Each mirrors a Phase 117 control: a targeted approving review, its reliability, and the exact
#: persisted statement it approved.
OBS_BLOCK_NO_LEAD_REVIEW = "no Lead review of this observation"
OBS_BLOCK_NOT_APPROVED = "the current Lead review does not approve it for internal reliance"
OBS_BLOCK_RELIABILITY_LOW = "the Lead rated its reliability low"
OBS_BLOCK_RELIABILITY_UNSPECIFIED = "its reliability is unspecified or unrecognised"
OBS_BLOCK_STATEMENT_CHANGED = "the observation has changed since the Lead reviewed it"

LEAD_APPROVE = "approve_internal"


@dataclass
class DiscoveryTrace:
    """Where one piece of discovery material came from, in consultant-readable terms first."""

    session_id: Optional[str] = None
    interviewee_name: Optional[str] = None  # the human-readable form of session_id
    observation_id: Optional[str] = None
    question_id: Optional[str] = None
    answer_id: Optional[str] = None
    question_prompt: Optional[str] = None  # the prompt as snapshotted with the answer
    recorded_by: Optional[str] = None  # consultant name where known
    recorded_by_consultant_id: Optional[str] = None


@dataclass
class DiscoveryFinding:
    """One consultant-recorded finding from discovery. Never evidence, never a recommendation.

    Note what is absent: no ``review_status``, no ``reliability``, no ``claim_scope``, and no
    ``recommendation_eligible``. Those belong to evidence-backed findings, and a discovery finding
    has no field for them by design.
    """

    finding_id: str
    statement: str  # the consultant's observation text, exactly as stored
    category: Optional[str] = None
    source_type: str = SOURCE_DISCOVERY_OBSERVATION
    source_ids: List[str] = field(default_factory=list)
    trace: DiscoveryTrace = field(default_factory=DiscoveryTrace)
    low_hanging_fruit: bool = False
    estimated_effort: Optional[str] = None
    estimated_value: Optional[str] = None
    basis: Optional[str] = None  # Phase 216: OBSERVATION_BASIS_LABELS key, as recorded
    status: str = DISCOVERY_STATUS_CONSULTANT_WORKING_MATERIAL
    internal_only: bool = True
    requires_human_review: bool = True


@dataclass
class LowHangingFruitCandidate:
    """One observation the consultant explicitly flagged as low-hanging fruit."""

    finding_id: str
    statement: str
    category: Optional[str] = None
    estimated_effort: Optional[str] = None
    estimated_value: Optional[str] = None
    trace: DiscoveryTrace = field(default_factory=DiscoveryTrace)
    basis: Optional[str] = None  # Phase 216
    internal_only: bool = True
    requires_human_review: bool = True


@dataclass
class LeadReviewView:
    """The current Lead review of one observation, as stored. Phase 226."""

    review_id: str
    review_number: int
    decision: str
    reliability: Optional[str] = None
    reviewer: Optional[str] = None  # consultant name where known
    reviewer_consultant_id: Optional[str] = None
    statement_matches: bool = False  # the observation still reads exactly as reviewed


@dataclass
class DiscoveryRecommendationEligibility:
    """Whether one discovery-derived finding may support a recommendation. Derived, never stored.

    Eligibility drafts nothing itself. Phase 227: the internal assessment derives the one bounded
    recommendation from it on each read.
    """

    finding_id: str
    observation_id: Optional[str] = None
    recommendation_eligible: bool = False
    recommendation_blocked_reasons: List[str] = field(default_factory=list)
    lead_review: Optional[LeadReviewView] = None
    reviewed_by_author: bool = False
    internal_only: bool = True


@dataclass
class InterviewSummary:
    """One interview, for the coverage list."""

    session_id: str
    interviewee_name: str
    interviewee_title: Optional[str] = None
    status: str = ""
    conducted_by: Optional[str] = None
    answered_count: int = 0


@dataclass
class InterviewCoverage:
    """Counts of what discovery actually covered. Counts, not completeness estimates."""

    total_sessions: int = 0
    completed_sessions: int = 0
    in_progress_sessions: int = 0
    interviewees: List[str] = field(default_factory=list)
    interviewee_titles: List[str] = field(default_factory=list)
    answered_questions: int = 0  # distinct questions answered across all interviews
    active_questions: int = 0
    unbranched_active_questions: int = 0
    answered_unbranched_questions: int = 0
    branching_makes_percentage_ambiguous: bool = False
    sessions: List[InterviewSummary] = field(default_factory=list)


@dataclass
class DiscoveryAssessmentContext:
    """Everything the internal assessment shows under its discovery headings.

    ``available`` is false when the engagement has no discovery material at all, which is the normal
    state for an evidence-only engagement and for the Phase 59 internal-test anchor.
    """

    engagement_id: Optional[str] = None
    available: bool = False
    north_star: Optional[str] = None
    north_star_context: Optional[str] = None
    workspace_stamped: bool = False
    coverage: InterviewCoverage = field(default_factory=InterviewCoverage)
    findings: List[DiscoveryFinding] = field(default_factory=list)
    low_hanging_fruit: List[LowHangingFruitCandidate] = field(default_factory=list)
    #: Phase 226: one per finding, in finding order. Beside the findings, never inside them.
    recommendation_eligibility: List[DiscoveryRecommendationEligibility] = field(default_factory=list)
    status: str = DISCOVERY_STATUS_CONSULTANT_WORKING_MATERIAL
    internal_only: bool = True
    requires_human_review: bool = True


def _answered(answers: List[dict]) -> List[dict]:
    """Answers that actually carry text. A skipped question is not coverage."""
    return [a for a in answers if (a.get("answer_text") or "").strip()]


def build_interview_coverage(sessions: List[dict], answers: List[dict],
                             active_questions: List[dict],
                             consultant_names: Optional[Dict[str, str]] = None
                             ) -> InterviewCoverage:
    """Count interviews, interviewees and answered questions. Nothing is estimated.

    A percentage is meaningful only over questions every interview sees, so the unbranched count is
    reported separately and ``branching_makes_percentage_ambiguous`` says whether a global
    percentage would mislead. The caller decides how to phrase it; this module refuses to compute
    the misleading number.
    """
    names = consultant_names or {}
    answered = _answered(answers)
    per_session: Dict[str, int] = {}
    for answer in answered:
        sid = answer.get("session_id")
        if sid:
            per_session[sid] = per_session.get(sid, 0) + 1

    unbranched = [q for q in active_questions if not q.get("branch_question_id")]
    unbranched_ids = {q.get("question_id") for q in unbranched}
    answered_question_ids = {a.get("question_id") for a in answered}

    coverage = InterviewCoverage(
        total_sessions=len(sessions),
        completed_sessions=sum(1 for s in sessions if s.get("status") == "completed"),
        in_progress_sessions=sum(1 for s in sessions if s.get("status") == "in_progress"),
        interviewees=sorted({s.get("interviewee_name") for s in sessions
                             if s.get("interviewee_name")}),
        interviewee_titles=sorted({s.get("interviewee_title") for s in sessions
                                   if s.get("interviewee_title")}),
        answered_questions=len(answered_question_ids),
        active_questions=len(active_questions),
        unbranched_active_questions=len(unbranched),
        answered_unbranched_questions=len(answered_question_ids & unbranched_ids),
        branching_makes_percentage_ambiguous=len(unbranched) != len(active_questions),
    )
    coverage.sessions = [
        InterviewSummary(
            session_id=s.get("session_id"),
            interviewee_name=s.get("interviewee_name") or "",
            interviewee_title=s.get("interviewee_title"),
            status=s.get("status") or "",
            conducted_by=names.get(s.get("conducted_by_consultant_id")),
            answered_count=per_session.get(s.get("session_id"), 0),
        )
        for s in sessions
    ]
    return coverage


def build_discovery_findings(observations: List[dict], sessions: List[dict],
                             consultant_names: Optional[Dict[str, str]] = None,
                             answers: Optional[List[dict]] = None,
                             question_prompts: Optional[Dict[str, str]] = None
                             ) -> List[DiscoveryFinding]:
    """One finding per consultant observation, quoting the observation exactly.

    **Answers are not converted into findings.** An answer is a response to a question the
    consultant asked; an observation is a statement the consultant chose to make. Only the second
    is a finding, and only because the consultant already wrote it as one — which is why the
    statement is quoted rather than synthesised.

    Phase 216: when the observation names the question that prompted it, the trace carries that
    question. If the observation's interview answered it, the trace also names that answer and uses
    the answer's prompt snapshot; otherwise it uses the question's prompt. The answer's text is never
    copied into the finding. The observation's ``basis`` is carried as recorded.
    """
    names = consultant_names or {}
    prompts = question_prompts or {}
    by_session = {s.get("session_id"): s for s in sessions}
    answered = {(a.get("session_id"), a.get("question_id")): a for a in _answered(answers or [])}
    findings = []
    for observation in observations:
        statement = (observation.get("observation_text") or "").strip()
        if not statement:
            continue  # an empty observation states nothing; it is not a finding
        observation_id = observation.get("observation_id")
        session = by_session.get(observation.get("session_id")) or {}
        question_id = observation.get("question_id")
        answer = answered.get((observation.get("session_id"), question_id)) if question_id else None
        findings.append(DiscoveryFinding(
            finding_id=f"disc_{observation_id}",
            statement=statement,
            category=observation.get("category"),
            source_type=SOURCE_DISCOVERY_OBSERVATION,
            source_ids=[observation_id] if observation_id else [],
            trace=DiscoveryTrace(
                session_id=observation.get("session_id"),
                interviewee_name=session.get("interviewee_name"),
                observation_id=observation_id,
                question_id=question_id,
                answer_id=answer.get("answer_id") if answer else None,
                question_prompt=(answer.get("question_prompt_snapshot") if answer
                                 else prompts.get(question_id)) if question_id else None,
                recorded_by=names.get(observation.get("recorded_by_consultant_id")),
                recorded_by_consultant_id=observation.get("recorded_by_consultant_id"),
            ),
            low_hanging_fruit=bool(observation.get("low_hanging_fruit")),
            estimated_effort=observation.get("estimated_effort"),
            estimated_value=observation.get("estimated_value"),
            basis=observation.get("basis"),
        ))
    return findings


def recorded_outside_interviews(findings) -> bool:
    """Phase 225: whether any finding has no interview session. A fixed test on the trace."""
    return any(not f.trace.session_id for f in findings or [])


def discovery_not_evidence_text(findings, lead_reviewed: bool = False,
                                recommended: bool = False) -> str:
    """The discovery boundary sentence that is true of ``findings``. A pure function of them.

    Phase 226: ``lead_reviewed`` is passed by the internal assessment, which shows Lead reviews.
    Phase 227: ``recommended`` is passed when an eligible observation has the bounded
    recommendation. The Final Report passes it only then, so every other report is unchanged.
    """
    text = (DISCOVERY_NOT_EVIDENCE_WIDER_TEXT if recorded_outside_interviews(findings)
            else DISCOVERY_NOT_EVIDENCE_TEXT)
    if recommended:
        return text.replace(_NO_STANDING_TAIL, RECOMMENDED_TAIL)
    return text.replace(_NO_STANDING_TAIL, LEAD_REVIEWED_TAIL) if lead_reviewed else text


def current_lead_review(reviews: List[dict], engagement_id: Optional[str],
                        observation_id: Optional[str]) -> Optional[dict]:
    """The highest-numbered review of this observation in this engagement, or ``None``.

    A review of another observation or engagement never counts, whatever it says.
    """
    mine = [r for r in reviews if observation_id and r.get("observation_id") == observation_id
            and r.get("engagement_id") == engagement_id]
    return max(mine, key=lambda r: r.get("review_number") or 0) if mine else None


def observation_recommendation_block_reasons(finding: DiscoveryFinding,
                                             review: Optional[dict]) -> List[str]:
    """Stable reasons ``finding`` cannot support a recommendation; empty means eligible (Phase 226).

    The Phase 117 controls, applied to a consultant observation: a Lead review targets it, the
    current one approves it for internal reliance, its reliability is medium or high, and it approved
    the statement exactly as it now stands. Nothing is inferred, and the order is fixed.
    """
    if review is None:
        return [OBS_BLOCK_NO_LEAD_REVIEW]
    reasons = []
    if review.get("decision") != LEAD_APPROVE:
        reasons.append(OBS_BLOCK_NOT_APPROVED)
    elif review.get("reliability") == "low":
        reasons.append(OBS_BLOCK_RELIABILITY_LOW)
    elif review.get("reliability") not in RECOMMENDATION_RELIABILITY:
        reasons.append(OBS_BLOCK_RELIABILITY_UNSPECIFIED)
    if (review.get("reviewed_statement") or "").strip() != finding.statement:
        reasons.append(OBS_BLOCK_STATEMENT_CHANGED)
    return reasons


def build_recommendation_eligibility(findings: List[DiscoveryFinding], reviews: List[dict],
                                     engagement_id: Optional[str],
                                     consultant_names: Optional[Dict[str, str]] = None
                                     ) -> List[DiscoveryRecommendationEligibility]:
    """One eligibility decision per finding, from the stored Lead reviews. Pure and deterministic."""
    names = consultant_names or {}
    out = []
    for f in findings:
        r = current_lead_review(reviews, engagement_id, f.trace.observation_id)
        reasons = observation_recommendation_block_reasons(f, r)
        view = None
        if r is not None:
            view = LeadReviewView(
                review_id=r.get("review_id"), review_number=r.get("review_number"),
                decision=r.get("decision"),
                reliability=r.get("reliability"),
                reviewer=names.get(r.get("reviewer_consultant_id")),
                reviewer_consultant_id=r.get("reviewer_consultant_id"),
                statement_matches=(r.get("reviewed_statement") or "").strip() == f.statement)
        out.append(DiscoveryRecommendationEligibility(
            finding_id=f.finding_id, observation_id=f.trace.observation_id,
            recommendation_eligible=not reasons, recommendation_blocked_reasons=reasons,
            lead_review=view,
            reviewed_by_author=bool(view and view.reviewer_consultant_id
                                    and view.reviewer_consultant_id
                                    == f.trace.recorded_by_consultant_id)))
    return out


def lead_reviewed(context: Optional[DiscoveryAssessmentContext]) -> bool:
    """Whether any finding in ``context`` has a Lead review. Phase 226."""
    return bool(context and any(e.lead_review for e in context.recommendation_eligibility))


def _display_group(candidate: LowHangingFruitCandidate):
    """Sort key for the low-hanging-fruit **display grouping**. Not a score and not a ranking.

    High value before low, then low effort before high, then finding id so the order is stable.
    Anything the consultant left blank sorts after everything they filled in, because an unstated
    level is not a low one.
    """
    return (_VALUE_ORDER.get(candidate.estimated_value, len(_VALUE_ORDER)),
            _EFFORT_ORDER.get(candidate.estimated_effort, len(_EFFORT_ORDER)),
            candidate.finding_id)


def build_low_hanging_fruit(findings: List[DiscoveryFinding]) -> List[LowHangingFruitCandidate]:
    """The consultant-flagged findings only, grouped for readability by their entered levels."""
    candidates = [
        LowHangingFruitCandidate(
            finding_id=f.finding_id,
            statement=f.statement,
            category=f.category,
            estimated_effort=f.estimated_effort,
            estimated_value=f.estimated_value,
            trace=f.trace,
            basis=f.basis,
        )
        for f in findings if f.low_hanging_fruit
    ]
    return sorted(candidates, key=_display_group)


def build_discovery_assessment_context(summaries: Optional[dict]) -> DiscoveryAssessmentContext:
    """Build the projection from the Phase 206 discovery summaries.

    ``None`` or empty summaries produce an unavailable context rather than an error, so an
    engagement with no discovery material — and an assessment built without a database at all —
    still renders.
    """
    summaries = summaries or {}
    north_star = summaries.get("north_star") or {}
    sessions = list(summaries.get("sessions") or [])
    answers = list(summaries.get("answers") or [])
    observations = list(summaries.get("observations") or [])
    active_questions = list(summaries.get("active_questions") or [])
    names = dict(summaries.get("consultant_names") or {})

    findings = build_discovery_findings(observations, sessions, names, answers,
                                        dict(summaries.get("question_prompts") or {}))
    context = DiscoveryAssessmentContext(
        engagement_id=north_star.get("engagement_id"),
        north_star=north_star.get("north_star"),
        north_star_context=north_star.get("north_star_context"),
        workspace_stamped=bool(north_star.get("workspace_stamped")),
        coverage=build_interview_coverage(sessions, answers, active_questions, names),
        findings=findings,
        low_hanging_fruit=build_low_hanging_fruit(findings),
        recommendation_eligibility=build_recommendation_eligibility(
            findings, list(summaries.get("lead_reviews") or []), north_star.get("engagement_id"),
            names),
    )
    context.available = bool(context.north_star or sessions or observations)
    return context
