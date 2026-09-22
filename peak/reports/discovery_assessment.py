"""Discovery material as assessment context (Phase 206) — persisted discovery in, a projection out.

Turns the Phase 206 discovery summaries into a :class:`DiscoveryAssessmentContext`: the North Star,
a deterministic interview-coverage summary, discovery-derived findings, and consultant-flagged
low-hanging-fruit candidates, each carrying enough traceability to answer "where did this come
from?".

**Discovery is not evidence, and this module never lets it become evidence.** A discovery-derived
finding is consultant working material. It carries no review status, no reliability, no claim
scope, and — deliberately — no ``recommendation_eligible`` field at all, so there is no attribute
for a later caller to flip. The Phase 117/118 eligibility rules are untouched and are not consulted
here: they decide the fate of evidence-backed findings only. Every object this module produces is
``internal_only`` and ``requires_human_review``.

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

#: Where a discovery-derived finding came from. Only the first is produced today: a consultant
#: observation is an explicit, deliberate statement, whereas turning every answer into a finding
#: would be inference. ``DIRECT_STRUCTURED_ANSWER`` is the reserved name for the narrow future case
#: where a structured answer supports a statement with no interpretation at all.
SOURCE_DISCOVERY_OBSERVATION = "discovery_observation"
SOURCE_DIRECT_STRUCTURED_ANSWER = "direct_structured_answer"

#: The status every discovery-derived item carries. It is working material, never a deliverable.
DISCOVERY_STATUS_CONSULTANT_WORKING_MATERIAL = "consultant_working_material"

#: Effort/value levels as the consultant entered them. Ordered only for display grouping.
_VALUE_ORDER = {"high": 0, "medium": 1, "low": 2}
_EFFORT_ORDER = {"low": 0, "medium": 1, "high": 2}

DISCOVERY_NOT_EVIDENCE_TEXT = (
    "Consultant discovery material. Recorded during interviews, not reviewed evidence: it carries "
    "no review status, no reliability rating, and no recommendation eligibility. It informs the "
    "assessment; it does not support a formal recommendation on its own.")

LOW_HANGING_FRUIT_GROUPING_TEXT = (
    "Grouped for reading by the effort and value the consultant entered. This is a display "
    "grouping, not a score, a ranking, or a priority order, and no ROI is calculated.")

NO_DISCOVERY_TEXT = "No discovery material has been recorded for this engagement."


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
    internal_only: bool = True
    requires_human_review: bool = True


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
                             consultant_names: Optional[Dict[str, str]] = None
                             ) -> List[DiscoveryFinding]:
    """One finding per consultant observation, quoting the observation exactly.

    **Answers are not converted into findings.** An answer is a response to a question the
    consultant asked; an observation is a statement the consultant chose to make. Only the second
    is a finding, and only because the consultant already wrote it as one — which is why the
    statement is quoted rather than synthesised.
    """
    names = consultant_names or {}
    by_session = {s.get("session_id"): s for s in sessions}
    findings = []
    for observation in observations:
        statement = (observation.get("observation_text") or "").strip()
        if not statement:
            continue  # an empty observation states nothing; it is not a finding
        observation_id = observation.get("observation_id")
        session = by_session.get(observation.get("session_id")) or {}
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
                recorded_by=names.get(observation.get("recorded_by_consultant_id")),
                recorded_by_consultant_id=observation.get("recorded_by_consultant_id"),
            ),
            low_hanging_fruit=bool(observation.get("low_hanging_fruit")),
            estimated_effort=observation.get("estimated_effort"),
            estimated_value=observation.get("estimated_value"),
        ))
    return findings


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

    findings = build_discovery_findings(observations, sessions, names)
    context = DiscoveryAssessmentContext(
        engagement_id=north_star.get("engagement_id"),
        north_star=north_star.get("north_star"),
        north_star_context=north_star.get("north_star_context"),
        workspace_stamped=bool(north_star.get("workspace_stamped")),
        coverage=build_interview_coverage(sessions, answers, active_questions, names),
        findings=findings,
        low_hanging_fruit=build_low_hanging_fruit(findings),
    )
    context.available = bool(context.north_star or sessions or observations)
    return context
