"""Consultant discovery / interview workflow (Phase 204).

The question pool, the engagement North Star, interview sessions, answers and observations. Every
write names its (table, action) pair and exact columns and is checked by
``is_allowed_workspace_write``. Sessions, answers and observations are created with the fixed
``WORKSPACE_ENGAGEMENT_CREATION_STAMP`` (owner ``peak_consultants``, scope ``engagement_authorized``),
only under an engagement that carries that stamp. The conducting or recording consultant is always
the signed-in consultant, never a caller-supplied value. Nothing is deleted: questions are deactivated.

Branching is deliberately small. A question may name one *earlier* question (lower display order),
an operator (``equals`` / ``not_equals``) and a value. A question is shown when it has no branch, or
when its branch question is itself shown and the stored answer satisfies the rule. There is no
expression language.
"""

from __future__ import annotations

import secrets
from datetime import datetime
from typing import Optional

from peak.persistence.allowlist import (
    WORKSPACE_ENGAGEMENT_CREATION_STAMP,
    is_allowed_workspace_write,
)

from .service import WorkspaceError, _clean

ANSWER_TYPES = ("short_text", "long_text", "yes_no", "single_choice")
BRANCH_OPERATORS = ("equals", "not_equals")
YES_NO = ("yes", "no")
LEVELS = ("low", "medium", "high")
MAX_CHOICES = 20
_ANSWER_LIMITS = {"short_text": 1000, "long_text": 10000}


def _now() -> datetime:
    return datetime.utcnow().replace(microsecond=0)


def _require_allowed(table: str, action: str, values: dict) -> None:
    if not is_allowed_workspace_write(table, action, values.keys()):
        raise WorkspaceError("write_not_permitted", f"{table}/{action} may not write these fields.")


def _level(value, label: str) -> Optional[str]:
    if value in (None, ""):
        return None
    if value not in LEVELS:
        raise WorkspaceError("invalid_field", f"{label} must be low, medium or high.")
    return value


# --------------------------------------------------------------------------- question pool


def _question_dict(q) -> dict:
    return {
        "id": q.id, "prompt": q.prompt, "category": q.category, "answer_type": q.answer_type,
        "choices": q.choices or [], "display_order": q.display_order, "active": bool(q.active),
        "branch": ({"question_id": q.branch_question_id, "operator": q.branch_operator,
                    "value": q.branch_value} if q.branch_question_id else None),
    }


def _choices(value) -> Optional[list]:
    if value is None:
        return None
    if not isinstance(value, list):
        raise WorkspaceError("invalid_field", "Choices must be a list.")
    out = []
    for item in value:
        text = _clean(item, 255, "Choice")
        if text and text not in out:
            out.append(text)
    return out or None


def _validate_branch_value(parent, value: str) -> None:
    if parent.answer_type == "yes_no" and value not in YES_NO:
        raise WorkspaceError("invalid_branch", "A yes/no branch value must be yes or no.")
    if parent.answer_type == "single_choice" and value not in (parent.choices or []):
        raise WorkspaceError("invalid_branch", "The branch value must be one of that question's choices.")


def _question_values(session, data: dict, current=None) -> dict:
    """Validate a create (``current`` None) or an edit merged over ``current``."""
    from sqlalchemy import func, select

    from peak.db.models import DiscoveryQuestion

    allowed = {"prompt", "category", "answer_type", "choices", "display_order", "active", "branch"}
    unknown = set(data) - allowed
    if unknown:
        raise WorkspaceError("invalid_field", f"Not an editable question field: {sorted(unknown)[0]}")

    values = {}
    if "prompt" in data:
        values["prompt"] = _clean(data["prompt"], 1000, "Question")
    if "category" in data:
        values["category"] = _clean(data["category"], 64, "Category")
    if "answer_type" in data:
        if data["answer_type"] not in ANSWER_TYPES:
            raise WorkspaceError("invalid_field", "Unknown answer type.")
        values["answer_type"] = data["answer_type"]
    if "choices" in data:
        values["choices"] = _choices(data["choices"])
    if "display_order" in data:
        order = data["display_order"]
        if not isinstance(order, int) or isinstance(order, bool) or not 0 <= order <= 1_000_000:
            raise WorkspaceError("invalid_field", "Display order must be a whole number from 0.")
        values["display_order"] = order
    if "active" in data:
        if not isinstance(data["active"], bool):
            raise WorkspaceError("invalid_field", "Active must be true or false.")
        values["active"] = data["active"]
    if "branch" in data:
        branch = data["branch"]
        if branch is None:
            values.update(branch_question_id=None, branch_operator=None, branch_value=None)
        else:
            if not isinstance(branch, dict) or set(branch) != {"question_id", "operator", "value"}:
                raise WorkspaceError("invalid_branch", "A branch needs a question, operator and value.")
            if branch["operator"] not in BRANCH_OPERATORS:
                raise WorkspaceError("invalid_branch", "The branch operator must be equals or not_equals.")
            value = _clean(branch["value"], 255, "Branch value")
            if not value:
                raise WorkspaceError("invalid_branch", "The branch needs a value.")
            values.update(branch_question_id=branch["question_id"],
                          branch_operator=branch["operator"], branch_value=value)

    def merged(field, default=None):
        if field in values:
            return values[field]
        return getattr(current, field) if current is not None else default

    if not merged("prompt"):
        raise WorkspaceError("invalid_field", "The question text is required.")
    if not merged("category"):
        raise WorkspaceError("invalid_field", "A category is required.")
    answer_type = merged("answer_type")
    if answer_type not in ANSWER_TYPES:
        raise WorkspaceError("invalid_field", "An answer type is required.")
    choices = merged("choices")
    if answer_type == "single_choice":
        if not choices or len(choices) < 2 or len(choices) > MAX_CHOICES:
            raise WorkspaceError("invalid_field", f"A single-choice question needs 2–{MAX_CHOICES} choices.")
    elif choices:
        values["choices"] = None  # choices only apply to single-choice questions
    if current is None and "display_order" not in values:
        highest = session.scalar(select(func.max(DiscoveryQuestion.display_order)))
        values["display_order"] = (highest or 0) + 10
    order = merged("display_order")

    parent_id = merged("branch_question_id")
    if parent_id:
        parent = session.get(DiscoveryQuestion, parent_id)
        if parent is None or (current is not None and parent.id == current.id):
            raise WorkspaceError("invalid_branch", "The branch must name another existing question.")
        if parent.display_order >= order:
            raise WorkspaceError("invalid_branch", "The branch must name an earlier question.")
        _validate_branch_value(parent, merged("branch_value"))

    if current is not None:
        # Questions that branch on this one must stay later, with values that still make sense.
        children = session.scalars(select(DiscoveryQuestion).where(
            DiscoveryQuestion.branch_question_id == current.id)).all()
        probe = type("Probe", (), {"answer_type": answer_type, "choices": merged("choices")})
        for child in children:
            if child.display_order <= order:
                raise WorkspaceError("invalid_branch",
                                     "Another question branches on this one and must stay after it.")
            _validate_branch_value(probe, child.branch_value)
    return values


def list_questions(session_factory) -> list:
    from sqlalchemy import select

    from peak.db.models import DiscoveryQuestion

    with session_factory() as session:
        rows = session.scalars(select(DiscoveryQuestion).order_by(
            DiscoveryQuestion.display_order, DiscoveryQuestion.id)).all()
        return [_question_dict(q) for q in rows]


def get_question(session_factory, question_id: str) -> Optional[dict]:
    from peak.db.models import DiscoveryQuestion

    with session_factory() as session:
        q = session.get(DiscoveryQuestion, question_id)
        return _question_dict(q) if q is not None else None


def create_question(session_factory, data: dict, seed_key: Optional[str] = None) -> dict:
    """Add a question. ``seed_key`` is used only by the explicit initialization tool."""
    from peak.db.models import DiscoveryQuestion

    with session_factory() as session:
        values = {"id": f"dq_{secrets.token_hex(8)}", "active": True,
                  **_question_values(session, data)}
        if seed_key is not None:
            values["seed_key"] = seed_key
        _require_allowed("discovery_questions", "create_discovery_question", values)
        session.add(DiscoveryQuestion(**values))
        session.commit()
        return _question_dict(session.get(DiscoveryQuestion, values["id"]))


def update_question(session_factory, question_id: str, data: dict) -> Optional[dict]:
    from sqlalchemy import update

    from peak.db.models import DiscoveryQuestion

    with session_factory() as session:
        current = session.get(DiscoveryQuestion, question_id)
        if current is None:
            return None
        values = _question_values(session, data, current)
        if not values:
            raise WorkspaceError("invalid_field", "Nothing to update.")
        _require_allowed("discovery_questions", "update_discovery_question", values)
        session.execute(update(DiscoveryQuestion).where(DiscoveryQuestion.id == question_id)
                        .values(**values))
        session.commit()
    return get_question(session_factory, question_id)


# --------------------------------------------------------------------------- engagement discovery


def _workspace_engagement(session, engagement_id: str):
    """The engagement, if it exists and carries the workspace stamp; otherwise refuse."""
    from peak.db.models import Engagement

    engagement = session.get(Engagement, engagement_id)
    if engagement is None:
        return None
    if any(getattr(engagement, k) != v for k, v in WORKSPACE_ENGAGEMENT_CREATION_STAMP.items()):
        raise WorkspaceError("not_a_workspace_engagement",
                             "Discovery is available only for consultant-workspace engagements.")
    return engagement


def set_north_star(session_factory, engagement_id: str, data: dict) -> Optional[dict]:
    from sqlalchemy import update

    from peak.db.models import Engagement

    unknown = set(data) - {"north_star", "north_star_context"}
    if unknown:
        raise WorkspaceError("invalid_field", f"Not a North Star field: {sorted(unknown)[0]}")
    values = {}
    if "north_star" in data:
        values["north_star"] = _clean(data["north_star"], 1000, "North Star")
    if "north_star_context" in data:
        values["north_star_context"] = _clean(data["north_star_context"], 4000, "Context")
    if not values:
        raise WorkspaceError("invalid_field", "Nothing to update.")
    _require_allowed("engagements", "set_engagement_north_star", values)
    with session_factory() as session:
        if _workspace_engagement(session, engagement_id) is None:
            return None
        session.execute(update(Engagement).where(Engagement.id == engagement_id).values(**values))
        session.commit()
    return get_discovery(session_factory, engagement_id)


def _names(session, ids) -> dict:
    from sqlalchemy import select

    from peak.db.models import Consultant

    ids = {i for i in ids if i}
    return dict(session.execute(select(Consultant.id, Consultant.name)
                                .where(Consultant.id.in_(ids))).all()) if ids else {}


def _observation_dict(o, names, sessions) -> dict:
    s = sessions.get(o.session_id)
    return {
        "id": o.id, "engagement_id": o.engagement_id, "category": o.category,
        "observation_text": o.observation_text, "low_hanging_fruit": bool(o.low_hanging_fruit),
        "estimated_effort": o.estimated_effort, "estimated_value": o.estimated_value,
        "session": ({"id": s.id, "interviewee_name": s.interviewee_name} if s else None),
        "recorded_by": names.get(o.recorded_by_consultant_id),
        "created_at": o.created_at.isoformat() if o.created_at else None,
    }


def get_discovery(session_factory, engagement_id: str) -> Optional[dict]:
    """North Star, interviews and observations for one engagement."""
    from sqlalchemy import func, select

    from peak.db.models import (
        Client, DiscoveryAnswer, DiscoveryObservation, DiscoverySession, Engagement,
    )

    with session_factory() as session:
        engagement = session.get(Engagement, engagement_id)
        if engagement is None:
            return None
        eligible = all(getattr(engagement, k) == v
                       for k, v in WORKSPACE_ENGAGEMENT_CREATION_STAMP.items())
        sessions = session.scalars(select(DiscoverySession)
                                   .where(DiscoverySession.engagement_id == engagement_id)
                                   .order_by(DiscoverySession.started_at.desc())).all()
        answered = dict(session.execute(
            select(DiscoveryAnswer.session_id, func.count())
            .where(DiscoveryAnswer.engagement_id == engagement_id,
                   DiscoveryAnswer.answer_text.isnot(None))
            .group_by(DiscoveryAnswer.session_id)).all())
        observations = session.scalars(select(DiscoveryObservation)
                                       .where(DiscoveryObservation.engagement_id == engagement_id)
                                       .order_by(DiscoveryObservation.created_at.desc(),
                                                 DiscoveryObservation.id)).all()
        names = _names(session, [s.conducted_by_consultant_id for s in sessions]
                       + [o.recorded_by_consultant_id for o in observations])
        by_id = {s.id: s for s in sessions}
        client = session.get(Client, engagement.client_id)
        return {
            "engagement_id": engagement.id,
            "discovery_enabled": eligible,
            "north_star": engagement.north_star,
            "north_star_context": engagement.north_star_context,
            "key_personnel": (client.key_personnel or []) if client is not None else [],
            "sessions": [{
                "id": s.id, "interviewee_name": s.interviewee_name,
                "interviewee_title": s.interviewee_title, "status": s.status,
                "conducted_by": names.get(s.conducted_by_consultant_id),
                "started_at": s.started_at.isoformat(), "answered_count": answered.get(s.id, 0),
            } for s in sessions],
            "observations": [_observation_dict(o, names, by_id) for o in observations],
        }


# --------------------------------------------------------------------------- interview sessions


def _visible_flow(questions, answers: dict) -> list:
    """Questions in order with visibility; a branch needs its (earlier) question shown and matched."""
    shown = {}
    flow = []
    for q in questions:
        visible = bool(q.active)
        if visible and q.branch_question_id:
            parent_answer = answers.get(q.branch_question_id)
            parent_shown = shown.get(q.branch_question_id, False)
            if q.branch_operator == "equals":
                visible = parent_shown and parent_answer == q.branch_value
            else:
                visible = parent_shown and parent_answer is not None \
                    and parent_answer != q.branch_value
        shown[q.id] = visible
        flow.append((q, visible))
    return flow


def _session_flow(session, discovery_session):
    from sqlalchemy import select

    from peak.db.models import DiscoveryAnswer, DiscoveryQuestion

    questions = session.scalars(select(DiscoveryQuestion).order_by(
        DiscoveryQuestion.display_order, DiscoveryQuestion.id)).all()
    answer_rows = session.scalars(select(DiscoveryAnswer)
                                  .where(DiscoveryAnswer.session_id == discovery_session.id)).all()
    answers = {a.question_id: a.answer_text for a in answer_rows}
    return _visible_flow(questions, answers), {a.question_id: a for a in answer_rows}


def get_session(session_factory, session_id: str) -> Optional[dict]:
    """The interview with its question flow: visible questions, and every stored answer.

    A deactivated or now-hidden question that was already answered stays in ``history`` with its
    snapshotted prompt, so completed interviews never lose content.
    """
    from peak.db.models import Client, DiscoverySession, Engagement

    with session_factory() as session:
        s = session.get(DiscoverySession, session_id)
        if s is None:
            return None
        flow, answer_rows = _session_flow(session, s)
        engagement = session.get(Engagement, s.engagement_id)
        client = session.get(Client, s.client_id)
        names = _names(session, [s.conducted_by_consultant_id])
        questions = [{**_question_dict(q), "answer": (answer_rows[q.id].answer_text
                                                       if q.id in answer_rows else None)}
                     for q, visible in flow if visible]
        visible_ids = {q["id"] for q in questions}
        history = [{"question_id": a.question_id, "prompt": a.question_prompt_snapshot,
                    "answer": a.answer_text}
                   for a in answer_rows.values() if a.question_id not in visible_ids and a.answer_text]
        return {
            "id": s.id, "status": s.status, "interviewee_name": s.interviewee_name,
            "interviewee_title": s.interviewee_title, "notes": s.notes,
            "conducted_by": names.get(s.conducted_by_consultant_id),
            "started_at": s.started_at.isoformat(),
            "completed_at": s.completed_at.isoformat() if s.completed_at else None,
            "engagement": {"id": s.engagement_id,
                           "name": engagement.engagement_label if engagement else None},
            "client": {"id": s.client_id, "name": client.organization_label if client else None},
            "questions": questions,
            "history": history,
        }


def _session_details(data: dict, creating: bool) -> dict:
    unknown = set(data) - {"interviewee_name", "interviewee_title", "notes"}
    if unknown:
        raise WorkspaceError("invalid_field", f"Not an editable interview field: {sorted(unknown)[0]}")
    values = {}
    if "interviewee_name" in data:
        values["interviewee_name"] = _clean(data["interviewee_name"], 255, "Interviewee name")
    if "interviewee_title" in data:
        values["interviewee_title"] = _clean(data["interviewee_title"], 255, "Interviewee title")
    if "notes" in data:
        values["notes"] = _clean(data["notes"], 4000, "Notes")
    if (creating or "interviewee_name" in values) and not values.get("interviewee_name"):
        raise WorkspaceError("invalid_field", "The interviewee's name is required.")
    return values


def start_session(session_factory, engagement_id: str, data: dict, consultant_id: str) -> Optional[dict]:
    """Start an interview. The conducting consultant is the signed-in consultant."""
    from peak.db.models import DiscoverySession

    values = _session_details(data, creating=True)
    with session_factory() as session:
        engagement = _workspace_engagement(session, engagement_id)
        if engagement is None:
            return None
        values.update(id=f"dsess_{secrets.token_hex(8)}", client_id=engagement.client_id,
                      engagement_id=engagement.id, status="in_progress",
                      conducted_by_consultant_id=consultant_id, started_at=_now())
        _require_allowed("discovery_sessions", "start_discovery_session", values)
        session.add(DiscoverySession(**values, **WORKSPACE_ENGAGEMENT_CREATION_STAMP))
        session.commit()
    return get_session(session_factory, values["id"])


def _open_session(session, session_id: str):
    from peak.db.models import DiscoverySession

    s = session.get(DiscoverySession, session_id)
    if s is not None and s.status != "in_progress":
        raise WorkspaceError("session_completed", "This interview is completed and read-only.")
    return s


def update_session(session_factory, session_id: str, data: dict) -> Optional[dict]:
    from sqlalchemy import update

    from peak.db.models import DiscoverySession

    values = _session_details(data, creating=False)
    if not values:
        raise WorkspaceError("invalid_field", "Nothing to update.")
    _require_allowed("discovery_sessions", "update_discovery_session", values)
    with session_factory() as session:
        if _open_session(session, session_id) is None:
            return None
        session.execute(update(DiscoverySession).where(DiscoverySession.id == session_id)
                        .values(**values))
        session.commit()
    return get_session(session_factory, session_id)


def complete_session(session_factory, session_id: str) -> Optional[dict]:
    from sqlalchemy import update

    from peak.db.models import DiscoverySession

    values = {"status": "completed", "completed_at": _now()}
    _require_allowed("discovery_sessions", "complete_discovery_session", values)
    with session_factory() as session:
        if _open_session(session, session_id) is None:
            return None
        session.execute(update(DiscoverySession).where(DiscoverySession.id == session_id)
                        .values(**values))
        session.commit()
    return get_session(session_factory, session_id)


def _normalize_answer(question, value) -> Optional[str]:
    if value is None or (isinstance(value, str) and not value.strip()):
        return None
    if not isinstance(value, str):
        raise WorkspaceError("invalid_answer", "An answer must be text.")
    value = value.strip()
    if question.answer_type == "yes_no":
        value = value.lower()
        if value not in YES_NO:
            raise WorkspaceError("invalid_answer", "Answer yes or no.")
    elif question.answer_type == "single_choice":
        if value not in (question.choices or []):
            raise WorkspaceError("invalid_answer", "Choose one of the listed options.")
    elif len(value) > _ANSWER_LIMITS[question.answer_type]:
        raise WorkspaceError("invalid_answer", "That answer is too long.")
    return value


def save_answer(session_factory, session_id: str, question_id: str, answer) -> Optional[dict]:
    """Create or update this session's answer to one currently shown question."""
    from sqlalchemy import update

    from peak.db.models import DiscoveryAnswer, DiscoveryQuestion

    with session_factory() as session:
        s = _open_session(session, session_id)
        if s is None:
            return None
        question = session.get(DiscoveryQuestion, question_id)
        if question is None:
            return None
        flow, answer_rows = _session_flow(session, s)
        if not dict((q.id, v) for q, v in flow).get(question_id):
            raise WorkspaceError("question_not_shown",
                                 "That question is inactive or not shown for this interview.")
        text = _normalize_answer(question, answer)
        existing = answer_rows.get(question_id)
        if existing is None:
            values = {"id": f"dans_{secrets.token_hex(8)}", "client_id": s.client_id,
                      "engagement_id": s.engagement_id, "session_id": s.id,
                      "question_id": question.id, "question_prompt_snapshot": question.prompt,
                      "answer_text": text}
            _require_allowed("discovery_answers", "create_discovery_answer", values)
            session.add(DiscoveryAnswer(**values, **WORKSPACE_ENGAGEMENT_CREATION_STAMP))
        else:
            values = {"answer_text": text}
            _require_allowed("discovery_answers", "update_discovery_answer", values)
            session.execute(update(DiscoveryAnswer).where(DiscoveryAnswer.id == existing.id)
                            .values(**values))
        session.commit()
    return get_session(session_factory, session_id)


# --------------------------------------------------------------------------- observations


def _observation_values(data: dict, creating: bool) -> dict:
    allowed = {"category", "observation_text", "low_hanging_fruit", "estimated_effort",
               "estimated_value"} | ({"session_id"} if creating else set())
    unknown = set(data) - allowed
    if unknown:
        raise WorkspaceError("invalid_field", f"Not an editable observation field: {sorted(unknown)[0]}")
    values = {}
    if "category" in data:
        values["category"] = _clean(data["category"], 64, "Category")
    if "observation_text" in data:
        values["observation_text"] = _clean(data["observation_text"], 10000, "Observation")
    if "low_hanging_fruit" in data:
        if not isinstance(data["low_hanging_fruit"], bool):
            raise WorkspaceError("invalid_field", "Low-hanging fruit must be true or false.")
        values["low_hanging_fruit"] = data["low_hanging_fruit"]
    if "estimated_effort" in data:
        values["estimated_effort"] = _level(data["estimated_effort"], "Estimated effort")
    if "estimated_value" in data:
        values["estimated_value"] = _level(data["estimated_value"], "Estimated value")
    if (creating or "observation_text" in values) and not values.get("observation_text"):
        raise WorkspaceError("invalid_field", "The observation text is required.")
    return values


def get_observation(session_factory, observation_id: str) -> Optional[dict]:
    from peak.db.models import DiscoveryObservation, DiscoverySession

    with session_factory() as session:
        o = session.get(DiscoveryObservation, observation_id)
        if o is None:
            return None
        s = session.get(DiscoverySession, o.session_id) if o.session_id else None
        return _observation_dict(o, _names(session, [o.recorded_by_consultant_id]),
                                 {s.id: s} if s else {})


def create_observation(session_factory, engagement_id: str, data: dict,
                       consultant_id: str) -> Optional[dict]:
    """Record an observation. The recording consultant is the signed-in consultant."""
    from peak.db.models import DiscoveryObservation, DiscoverySession

    values = _observation_values({k: v for k, v in data.items() if k != "session_id"}, creating=True)
    with session_factory() as session:
        engagement = _workspace_engagement(session, engagement_id)
        if engagement is None:
            return None
        session_id = data.get("session_id") or None
        if session_id is not None:
            linked = session.get(DiscoverySession, session_id)
            if linked is None or linked.engagement_id != engagement.id:
                raise WorkspaceError("invalid_field", "That interview is not part of this engagement.")
        values.update(id=f"dobs_{secrets.token_hex(8)}", client_id=engagement.client_id,
                      engagement_id=engagement.id, session_id=session_id,
                      recorded_by_consultant_id=consultant_id)
        values.setdefault("low_hanging_fruit", False)
        _require_allowed("discovery_observations", "create_discovery_observation", values)
        session.add(DiscoveryObservation(**values, **WORKSPACE_ENGAGEMENT_CREATION_STAMP))
        session.commit()
    return get_observation(session_factory, values["id"])


def update_observation(session_factory, observation_id: str, data: dict) -> Optional[dict]:
    from sqlalchemy import update

    from peak.db.models import DiscoveryObservation

    values = _observation_values(data, creating=False)
    if not values:
        raise WorkspaceError("invalid_field", "Nothing to update.")
    _require_allowed("discovery_observations", "update_discovery_observation", values)
    with session_factory() as session:
        result = session.execute(update(DiscoveryObservation)
                                 .where(DiscoveryObservation.id == observation_id).values(**values))
        session.commit()
        if result.rowcount == 0:
            return None
    return get_observation(session_factory, observation_id)
