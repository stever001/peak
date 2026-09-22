"""Read-only persisted-state fetch for the discovery side of the internal assessment (Phase 206).

Retrieves one engagement's persisted **discovery** records — the North Star on the engagement row,
its ``discovery_sessions``, ``discovery_answers``, ``discovery_observations``, and the
``discovery_questions`` pool — in the shape
:func:`peak.reports.discovery_assessment.build_discovery_assessment_context` consumes. It is the
discovery counterpart of :mod:`peak.db.engagement_packet_reader`, and it follows the same rules.

**Read-only by construction.** Every statement is a ``select()`` over an explicit, whitelisted
column list. This module issues no ``INSERT`` / ``UPDATE`` / ``DELETE``, imports and invokes no
writer, creates no session or engine, holds no credential, and reads no environment variable — the
caller establishes and owns the connection, so the privilege stays outside this code.

**Discovery is consultant working material, not governed evidence.** These records are written by
the Phase 204 consultant workspace, not by a controlled writer, and nothing here changes that: this
module reads them so they can be *displayed beside* evidence-backed material under their own
labels. It grants no review status, no reliability, no claim scope, and no recommendation
eligibility, and it touches no governance column beyond reading the stamp that says which workspace
created the record.

**The Phase 202 workspace stamp is reported, not enforced here.** A discovery record is written only
under a stamped engagement (Phase 204), so this module reports whether the engagement carries the
stamp and lets the projection decide what that means. It does not widen any authorization: an
engagement without the stamp simply has no discovery records to read, which is the Phase 59
internal-test anchor's case.

Output is plain dicts in a deterministic order, so the same database state always yields the same
context. See docs/PHASE206_DISCOVERY_ASSESSMENT_INTEGRATION.md.
"""

from __future__ import annotations

from typing import Dict, List

from sqlalchemy import select

from .models import (
    DiscoveryAnswer, DiscoveryObservation, DiscoveryQuestion, DiscoverySession, Engagement,
)

#: The stamp every Phase 202 workspace engagement carries, and which every Phase 204 discovery
#: record is written under. Mirrored from ``peak.persistence.allowlist`` as a literal so this
#: read path never imports the write allowlist.
WORKSPACE_OWNER_ID = "peak_consultants"
WORKSPACE_AUTHORIZATION_SCOPE = "engagement_authorized"


def _rows(connection, statement) -> List[Dict[str, object]]:
    return [dict(row._mapping) for row in connection.execute(statement)]


def fetch_north_star(connection, engagement_id: str) -> Dict[str, object]:
    """The engagement's North Star statement and context, plus whether it carries the stamp.

    Returns ``{}`` when no such engagement exists. ``engagement_label`` is not selected — the
    assessment names the engagement from the packet summary it already holds.
    """
    statement = select(
        Engagement.id.label("engagement_id"),
        Engagement.north_star,
        Engagement.north_star_context,
        Engagement.owner_id,
        Engagement.authorization_scope,
    ).where(Engagement.id == engagement_id)
    found = _rows(connection, statement)
    if not found:
        return {}
    row = found[0]
    row["workspace_stamped"] = (row.get("owner_id") == WORKSPACE_OWNER_ID
                                and row.get("authorization_scope") == WORKSPACE_AUTHORIZATION_SCOPE)
    return row


def fetch_session_summaries(connection, engagement_id: str) -> List[Dict[str, object]]:
    """The engagement's interviews, oldest first then by id, so the order is stable.

    ``notes`` is **not** selected: it is a free-text consultant scratch column, and the assessment
    reports coverage and observations rather than interview notes.
    """
    statement = select(
        DiscoverySession.id.label("session_id"),
        DiscoverySession.client_id,
        DiscoverySession.engagement_id,
        DiscoverySession.interviewee_name,
        DiscoverySession.interviewee_title,
        DiscoverySession.status,
        DiscoverySession.conducted_by_consultant_id,
        DiscoverySession.started_at,
        DiscoverySession.completed_at,
        DiscoverySession.owner_id,
        DiscoverySession.authorization_scope,
    ).where(DiscoverySession.engagement_id == engagement_id
            ).order_by(DiscoverySession.started_at, DiscoverySession.id)
    return _rows(connection, statement)


def fetch_answer_summaries(connection, engagement_id: str) -> List[Dict[str, object]]:
    """The engagement's answers, sorted by id.

    ``question_prompt_snapshot`` is the prompt **as it stood when the answer was given** (Phase
    204), so a later edit to the question pool cannot silently restate a consultant's answer.
    """
    statement = select(
        DiscoveryAnswer.id.label("answer_id"),
        DiscoveryAnswer.session_id,
        DiscoveryAnswer.question_id,
        DiscoveryAnswer.question_prompt_snapshot,
        DiscoveryAnswer.answer_text,
    ).where(DiscoveryAnswer.engagement_id == engagement_id).order_by(DiscoveryAnswer.id)
    return _rows(connection, statement)


def fetch_observation_summaries(connection, engagement_id: str) -> List[Dict[str, object]]:
    """The engagement's consultant observations, oldest first then by id, so the order is stable.

    Recording order is the order a consultant recorded them in, which is the order they expect to
    read them back in. ``created_at`` orders the rows but is not selected: it is an audit column,
    not assessment content.

    ``observation_text`` is consultant-authored working material, selected because it *is* the
    discovery finding statement — the projection quotes it rather than synthesising prose.
    """
    statement = select(
        DiscoveryObservation.id.label("observation_id"),
        DiscoveryObservation.session_id,
        DiscoveryObservation.category,
        DiscoveryObservation.observation_text,
        DiscoveryObservation.low_hanging_fruit,
        DiscoveryObservation.estimated_effort,
        DiscoveryObservation.estimated_value,
        DiscoveryObservation.recorded_by_consultant_id,
        DiscoveryObservation.owner_id,
        DiscoveryObservation.authorization_scope,
    ).where(DiscoveryObservation.engagement_id == engagement_id
            ).order_by(DiscoveryObservation.created_at, DiscoveryObservation.id)
    return _rows(connection, statement)


def fetch_active_question_summaries(connection) -> List[Dict[str, object]]:
    """The active question pool in display order — the denominator side of interview coverage.

    Branch metadata is selected so the projection can tell whether a global "answered out of"
    percentage would be misleading. It is application configuration, not client data.
    """
    statement = select(
        DiscoveryQuestion.id.label("question_id"),
        DiscoveryQuestion.category,
        DiscoveryQuestion.answer_type,
        DiscoveryQuestion.display_order,
        DiscoveryQuestion.branch_question_id,
    ).where(DiscoveryQuestion.active.is_(True)
            ).order_by(DiscoveryQuestion.display_order, DiscoveryQuestion.id)
    return _rows(connection, statement)


def fetch_consultant_names(connection, consultant_ids) -> Dict[str, str]:
    """``{consultant_id: name}`` for the ids given, so traceability can name a person.

    Imported lazily: ``consultants`` is the Phase 201 account table, and this keeps the discovery
    read path from depending on it when no record names a consultant.
    """
    ids = sorted({i for i in consultant_ids if i})
    if not ids:
        return {}
    from .models import Consultant

    statement = select(Consultant.id, Consultant.name).where(Consultant.id.in_(ids))
    return {row[0]: row[1] for row in connection.execute(statement)}


def fetch_discovery_summaries(connection, engagement_id: str) -> Dict[str, object]:
    """Fetch every discovery summary the assessment projection needs for one engagement.

    Returns ``{"north_star": {...}, "sessions": [...], "answers": [...], "observations": [...],
    "active_questions": [...], "consultant_names": {...}}``. Visibility is **not** re-decided here:
    the caller has already passed the Phase 57 engagement check through
    :mod:`peak.db.engagement_packet_reader`, and an engagement with no discovery records simply
    returns empty lists.
    """
    sessions = fetch_session_summaries(connection, engagement_id)
    observations = fetch_observation_summaries(connection, engagement_id)
    names = fetch_consultant_names(
        connection,
        [s.get("conducted_by_consultant_id") for s in sessions]
        + [o.get("recorded_by_consultant_id") for o in observations])
    return {
        "north_star": fetch_north_star(connection, engagement_id),
        "sessions": sessions,
        "answers": fetch_answer_summaries(connection, engagement_id),
        "observations": observations,
        "active_questions": fetch_active_question_summaries(connection),
        "consultant_names": names,
    }
