"""Engagement roadmap, engagement phases and guided work plans (Phase 217).

Discovery → roadmap item (advisory) → engagement phase (separately authorized) → guided work plan
(ordered tasks) → consultant task records → deterministic completion readiness.

**A roadmap item is advisory.** It proposes future consulting work and cites the discovery
observations it rests on. Its framing is fixed at creation; a revision is a new item that supersedes
it. ``accepted`` means the client wants the phase proposed to them. It is never authorized work.

**An engagement phase is authorized by a recorded human act.** It may come from one accepted
roadmap item or be created manually with a stated reason. Only the engagement's Lead (assigned
consultant) or an Admin records the authorization, with its basis (what the client agreed to). Work
is recorded only on an authorized phase. Nothing infers authorization.

**The work plan is the phase's ordered tasks.** A task says what to do, why, what to observe, which
records would help and which questions to ask. It may depend on earlier tasks and may apply only if
an earlier task recorded a given kind of record (one deterministic condition, no expression
language). A task added after authorization is marked ``added_after_authorization``: a visible scope
change, never a silent one. A synthesis-suggested task (``si_suggested``) enters as ``suggested``
and is not part of the plan until a consultant accepts it.

**Only a consultant records and completes.** Completing a task needs a result summary from the
signed-in consultant and, when the task requires it, at least one record. Records are insert-only;
a correction supersedes. Nothing here creates a record, an observation or a finding on its own.

**Readiness is computed, never stored or guessed.** :func:`phase_readiness` applies fixed rules to
the plan; a phase can be completed only when it says ready. Final reporting is later work.

Framing fields pass the advisory boundary (``peak.workspace.advisory_boundary``; Contract C21).
Every write names its (table, action) pair and columns and is checked by
``is_allowed_workspace_write``; rows carry the workspace stamp. There is no delete.
"""

from __future__ import annotations

import secrets
from datetime import datetime
from typing import Optional

from peak.persistence.allowlist import (
    PHASE_TASK_FRAMING_COLUMNS,
    ROADMAP_ITEM_FRAMING_COLUMNS,
    WORKSPACE_ENGAGEMENT_CREATION_STAMP,
    is_allowed_workspace_write,
)

from . import peak_method_phases as method
from .advisory_boundary import BOUNDARY_MESSAGE, first_violation
from .service import ASSIGNMENT_ROLE, WorkspaceError, _clean

TITLE_LIMIT = 255
TEXT_LIMIT = 4000
MAX_LIST_ITEMS = 20
#: Mirrors ``peak.db.models.PHASE_TASK_RECORD_KINDS``.
RECORD_KINDS = ("note", "interview_response", "measurement", "mismatch", "photo",
                "document_photo", "document")
#: Reserved for future evidence capture (iPad photos, document photos, uploads). Refused until
#: storage exists; a consultant records a note describing the item meanwhile.
MEDIA_RECORD_KINDS = ("photo", "document_photo", "document")
#: Kind-specific structured fields a record may carry.
STRUCTURED_FIELDS = {
    "note": (),
    "interview_response": ("interviewee_role", "question"),
    "measurement": ("measure", "value", "unit"),
    "mismatch": ("reference", "expected", "observed", "resolution"),
}
#: Mirrors ``peak.db.models.DISCOVERY_OBSERVATION_BASES``.
RECORD_BASES = ("testimony", "observed", "document", "measured", "inferred")
#: Roadmap decisions a consultant may record, by current status.
ROADMAP_TRANSITIONS = {
    "proposed": ("accepted", "deferred", "declined"),
    "deferred": ("proposed", "accepted", "declined"),
    "accepted": ("deferred", "declined"),
}
RESOLVED_TASK_STATUSES = ("completed", "not_applicable")

READINESS_RULE = (
    "Ready when the phase is authorized, its work plan has at least one task, and every required "
    "task that applies is completed or resolved not applicable with a reason. Optional and "
    "suggested tasks never block. A conditional task applies only when its condition task recorded "
    "the named kind of record.")


def _now() -> datetime:
    return datetime.utcnow().replace(microsecond=0)


def _require_allowed(table: str, action: str, values: dict) -> None:
    if not is_allowed_workspace_write(table, action, values.keys()):
        raise WorkspaceError("write_not_permitted", f"{table}/{action} may not write these fields.")


def _require_advisory(values: dict, framing_columns) -> None:
    hit = first_violation({k: v for k, v in values.items() if k in framing_columns})
    if hit:
        raise WorkspaceError("advisory_boundary", BOUNDARY_MESSAGE.format(concept=hit[1]))


def _text(value, label: str, limit: int = TEXT_LIMIT, required: bool = False) -> Optional[str]:
    value = _clean(value, limit, label)
    if required and not value:
        raise WorkspaceError("invalid_field", f"{label} is required.")
    return value


def _text_list(value, label: str) -> Optional[list]:
    if value is None:
        return None
    if not isinstance(value, list) or len(value) > MAX_LIST_ITEMS:
        raise WorkspaceError("invalid_field", f"{label} must be a list of at most "
                                              f"{MAX_LIST_ITEMS} items.")
    out = [t for t in (_clean(v, 1000, label) for v in value) if t]
    return out or None


def _engagement(session, engagement_id: str):
    from .discovery import _workspace_engagement

    return _workspace_engagement(session, engagement_id)


def _stamped(row) -> bool:
    return all(getattr(row, k) == v for k, v in WORKSPACE_ENGAGEMENT_CREATION_STAMP.items())


def _iso(value) -> Optional[str]:
    return value.isoformat() if value else None


# --------------------------------------------------------------------------- roadmap


def _roadmap_item_dict(item) -> dict:
    return {
        "id": item.id, "engagement_id": item.engagement_id, "sequence": item.sequence,
        "title": item.title, "problem_framing": item.problem_framing,
        "rationale": item.rationale, "expected_outcome": item.expected_outcome,
        "source_observation_ids": item.source_observation_ids or [], "origin": item.origin,
        "template_key": item.template_key, "method_version": item.method_version,
        "status": item.status, "status_note": item.status_note,
        "supersedes_item_id": item.supersedes_item_id,
        "created_by_consultant_id": item.created_by_consultant_id,
        "decided_by_consultant_id": item.decided_by_consultant_id,
        "decided_at": _iso(item.decided_at), "created_at": _iso(item.created_at),
        # Advisory by construction: a roadmap item is never authorized work.
        "authorized_work": False,
    }


def _discovery_grounding(session, engagement_id: str):
    """Observations of the engagement as ``{id, category, question_id}``, and question categories."""
    from sqlalchemy import select

    from peak.db.models import DiscoveryObservation, DiscoveryQuestion

    observations = [{"id": o.id, "category": o.category, "question_id": o.question_id}
                    for o in session.scalars(
                        select(DiscoveryObservation)
                        .where(DiscoveryObservation.engagement_id == engagement_id)
                        .order_by(DiscoveryObservation.created_at, DiscoveryObservation.id))]
    qids = {o["question_id"] for o in observations if o["question_id"]}
    categories = dict(session.execute(select(DiscoveryQuestion.id, DiscoveryQuestion.category)
                                      .where(DiscoveryQuestion.id.in_(qids))).all()) if qids else {}
    return observations, categories


def get_roadmap(session_factory, engagement_id: str) -> Optional[dict]:
    """Live roadmap items in sequence, superseded history, and deterministic suggestions."""
    from sqlalchemy import select

    from peak.db.models import Engagement, RoadmapItem

    with session_factory() as session:
        engagement = session.get(Engagement, engagement_id)
        if engagement is None:
            return None
        items = session.scalars(select(RoadmapItem).where(RoadmapItem.engagement_id == engagement_id)
                                .order_by(RoadmapItem.sequence, RoadmapItem.created_at,
                                          RoadmapItem.id)).all()
        live = [i for i in items if i.status != "superseded"]
        observations, categories = _discovery_grounding(session, engagement_id)
        suggestions = method.suggest(observations, categories,
                                     on_roadmap={i.template_key for i in live if i.template_key})
        return {
            "engagement_id": engagement_id,
            "enabled": engagement.deleted_at is None and _stamped(engagement),
            "items": [_roadmap_item_dict(i) for i in live],
            "superseded": [_roadmap_item_dict(i) for i in items if i.status == "superseded"],
            "suggestions": suggestions,
        }


def _get_roadmap_item(session_factory, item_id: str) -> Optional[dict]:
    from peak.db.models import RoadmapItem

    with session_factory() as session:
        item = session.get(RoadmapItem, item_id)
        return _roadmap_item_dict(item) if item is not None else None


def _source_observations(session, engagement_id: str, value) -> Optional[list]:
    from sqlalchemy import select

    from peak.db.models import DiscoveryObservation

    if value is None:
        return None
    if not isinstance(value, list) or not all(isinstance(v, str) for v in value):
        raise WorkspaceError("invalid_field", "Source observations must be a list of ids.")
    ids = list(dict.fromkeys(value))
    found = set(session.scalars(select(DiscoveryObservation.id)
                                .where(DiscoveryObservation.id.in_(ids),
                                       DiscoveryObservation.engagement_id == engagement_id))) \
        if ids else set()
    if set(ids) - found:
        raise WorkspaceError("invalid_field",
                             "Every source observation must be an observation of this engagement.")
    return ids or None


def _roadmap_values(session, engagement_id: str, data: dict, origin: str) -> dict:
    allowed = {"template_key", "title", "problem_framing", "rationale", "expected_outcome",
               "source_observation_ids", "sequence"}
    unknown = set(data) - allowed
    if unknown:
        raise WorkspaceError("invalid_field", f"Not a roadmap item field: {sorted(unknown)[0]}")
    values = {"origin": origin}
    tmpl = None
    if data.get("template_key") is not None:
        tmpl = method.BY_KEY.get(data["template_key"])
        if tmpl is None:
            raise WorkspaceError("invalid_field", "Unknown Peak Method phase template.")
        values.update(template_key=tmpl["key"], method_version=method.METHOD_VERSION)
    for field, label in (("problem_framing", "Problem or opportunity"),
                         ("rationale", "Why this phase is suggested"),
                         ("expected_outcome", "Expected operational outcome")):
        given = _text(data.get(field), label)
        values[field] = given or (tmpl[field] if tmpl else None)
        if not values[field]:
            raise WorkspaceError("invalid_field", f"{label} is required.")
    values["title"] = (_text(data.get("title"), "Title", TITLE_LIMIT)
                       or (tmpl["title"] if tmpl else None))
    if not values["title"]:
        raise WorkspaceError("invalid_field", "Title is required.")
    values["source_observation_ids"] = _source_observations(
        session, engagement_id, data.get("source_observation_ids"))
    if origin != "consultant" and not values["source_observation_ids"]:
        raise WorkspaceError("ungrounded_suggestion",
                             "A Peak Method or synthesis suggestion must cite the discovery "
                             "observations it rests on.")
    if "sequence" in data and data["sequence"] is not None:
        if not isinstance(data["sequence"], int) or isinstance(data["sequence"], bool) \
                or data["sequence"] < 1:
            raise WorkspaceError("invalid_field", "Sequence must be a positive whole number.")
        values["sequence"] = data["sequence"]
    _require_advisory(values, ROADMAP_ITEM_FRAMING_COLUMNS)
    return values


def _next_sequence(session, model, *where) -> int:
    from sqlalchemy import func, select

    return (session.scalar(select(func.max(model.sequence)).where(*where)) or 0) + 1


def create_roadmap_item(session_factory, engagement_id: str, data: dict, consultant_id: str,
                        origin: Optional[str] = None) -> Optional[dict]:
    """Add a proposed roadmap item. ``template_key`` makes it a Peak Method item (origin
    ``peak_method``, framing defaulting to the template); otherwise the consultant frames it.
    ``origin="si_suggested"`` is for a synthesis caller, never the API. Always ``proposed``."""
    from peak.db.models import RoadmapItem

    with session_factory() as session:
        engagement = _engagement(session, engagement_id)
        if engagement is None:
            return None
        origin = origin or ("peak_method" if data.get("template_key") else "consultant")
        if origin not in ("peak_method", "consultant", "si_suggested"):
            raise WorkspaceError("invalid_field", "Unknown origin.")
        values = _roadmap_values(session, engagement.id, data, origin)
        values.setdefault("sequence", _next_sequence(session, RoadmapItem,
                                                     RoadmapItem.engagement_id == engagement.id))
        values.update(id=f"rmi_{secrets.token_hex(8)}", client_id=engagement.client_id,
                      engagement_id=engagement.id, status="proposed",
                      created_by_consultant_id=consultant_id)
        _require_allowed("roadmap_items", "create_roadmap_item", values)
        session.add(RoadmapItem(**values, **WORKSPACE_ENGAGEMENT_CREATION_STAMP))
        session.commit()
    return _get_roadmap_item(session_factory, values["id"])


def decide_roadmap_item(session_factory, item_id: str, status: str, note,
                        consultant_id: str) -> Optional[dict]:
    """Record the client's position on a roadmap item. Accepting it authorizes nothing."""
    from sqlalchemy import select, update

    from peak.db.models import EngagementPhase, RoadmapItem

    note = _text(note, "Note")
    with session_factory() as session:
        item = session.get(RoadmapItem, item_id)
        if item is None:
            return None
        _engagement(session, item.engagement_id)
        if status not in ROADMAP_TRANSITIONS.get(item.status, ()):
            raise WorkspaceError("invalid_transition",
                                 f"A {item.status} roadmap item cannot become {status}.")
        if item.status == "accepted" and session.scalar(
                select(EngagementPhase.id).where(EngagementPhase.roadmap_item_id == item.id)):
            raise WorkspaceError("phase_exists",
                                 "An engagement phase already exists for this roadmap item.")
        values = {"status": status, "status_note": note, "decided_by_consultant_id": consultant_id,
                  "decided_at": _now()}
        _require_allowed("roadmap_items", "decide_roadmap_item", values)
        session.execute(update(RoadmapItem).where(RoadmapItem.id == item.id,
                                                  RoadmapItem.status == item.status)
                        .values(**values))
        session.commit()
    return _get_roadmap_item(session_factory, item_id)


def revise_roadmap_item(session_factory, item_id: str, data: dict,
                        consultant_id: str) -> Optional[dict]:
    """Revise a proposed or deferred item: a new item supersedes it; the original is kept."""
    from sqlalchemy import update

    from peak.db.models import RoadmapItem

    with session_factory() as session:
        old = session.get(RoadmapItem, item_id)
        if old is None:
            return None
        engagement = _engagement(session, old.engagement_id)
        if old.status not in ("proposed", "deferred"):
            raise WorkspaceError("invalid_transition",
                                 f"A {old.status} roadmap item cannot be revised.")
        merged = {"template_key": old.template_key, "title": old.title,
                  "problem_framing": old.problem_framing, "rationale": old.rationale,
                  "expected_outcome": old.expected_outcome,
                  "source_observation_ids": old.source_observation_ids, "sequence": old.sequence,
                  **data}
        values = _roadmap_values(session, engagement.id, merged, old.origin)
        values.update(id=f"rmi_{secrets.token_hex(8)}", client_id=engagement.client_id,
                      engagement_id=engagement.id, status="proposed", supersedes_item_id=old.id,
                      created_by_consultant_id=consultant_id)
        _require_allowed("roadmap_items", "create_roadmap_item", values)
        _require_allowed("roadmap_items", "mark_roadmap_item_superseded", {"status": "superseded"})
        result = session.execute(update(RoadmapItem).where(RoadmapItem.id == old.id,
                                                           RoadmapItem.status == old.status)
                                 .values(status="superseded"))
        if result.rowcount != 1:
            raise WorkspaceError("invalid_transition", "The roadmap item changed; reload it.")
        session.add(RoadmapItem(**values, **WORKSPACE_ENGAGEMENT_CREATION_STAMP))
        session.commit()
    return _get_roadmap_item(session_factory, values["id"])


# --------------------------------------------------------------------------- phases


def _work_plan_status(phase, plan_tasks) -> str:
    if phase.status == "completed":
        return "closed"
    if not plan_tasks:
        return "not_started"
    return "active" if phase.status == "authorized" else "draft"


def _phase_summary(phase, plan_tasks) -> dict:
    return {
        "id": phase.id, "engagement_id": phase.engagement_id, "title": phase.title,
        "scope_summary": phase.scope_summary, "status": phase.status, "origin": phase.origin,
        "roadmap_item_id": phase.roadmap_item_id, "origin_note": phase.origin_note,
        "authorized": phase.status in ("authorized", "completed"),
        "authorization": ({"basis": phase.authorization_basis,
                           "reference": phase.authorization_reference,
                           "authorized_by_consultant_id": phase.authorized_by_consultant_id,
                           "authorized_at": _iso(phase.authorized_at)}
                          if phase.authorized_at else None),
        "work_plan_status": _work_plan_status(phase, plan_tasks),
        "completed_at": _iso(phase.completed_at),
        "completed_by_consultant_id": phase.completed_by_consultant_id,
        "created_by_consultant_id": phase.created_by_consultant_id,
        "created_at": _iso(phase.created_at),
    }


def list_phases(session_factory, engagement_id: str) -> Optional[list]:
    from sqlalchemy import select

    from peak.db.models import Engagement, EngagementPhase, PhaseTask

    with session_factory() as session:
        if session.get(Engagement, engagement_id) is None:
            return None
        phases = session.scalars(select(EngagementPhase)
                                 .where(EngagementPhase.engagement_id == engagement_id)
                                 .order_by(EngagementPhase.created_at, EngagementPhase.id)).all()
        tasks = session.scalars(select(PhaseTask).where(PhaseTask.engagement_id == engagement_id,
                                                        PhaseTask.status != "suggested")).all()
        return [_phase_summary(p, [t for t in tasks if t.phase_id == p.id]) for p in phases]


def create_phase(session_factory, engagement_id: str, data: dict,
                 consultant_id: str) -> Optional[dict]:
    """Create a planned (not yet authorized) phase, from an accepted roadmap item or manually."""
    from sqlalchemy.exc import IntegrityError

    from peak.db.models import EngagementPhase, RoadmapItem

    unknown = set(data) - {"roadmap_item_id", "title", "scope_summary", "origin_note"}
    if unknown:
        raise WorkspaceError("invalid_field", f"Not a phase field: {sorted(unknown)[0]}")
    with session_factory() as session:
        engagement = _engagement(session, engagement_id)
        if engagement is None:
            return None
        values = {"title": _text(data.get("title"), "Title", TITLE_LIMIT),
                  "scope_summary": _text(data.get("scope_summary"), "Scope")}
        item_id = data.get("roadmap_item_id")
        if item_id:
            item = session.get(RoadmapItem, item_id)
            if item is None or item.engagement_id != engagement.id:
                raise WorkspaceError("invalid_field", "That roadmap item is not on this roadmap.")
            if item.status != "accepted":
                raise WorkspaceError("roadmap_item_not_accepted",
                                     "Only an accepted roadmap item can become a phase.")
            tmpl = method.BY_KEY.get(item.template_key) if item.template_key else None
            values["title"] = values["title"] or item.title
            values["scope_summary"] = (values["scope_summary"]
                                       or (tmpl["scope_summary"] if tmpl else item.expected_outcome))
            values.update(origin="roadmap_item", roadmap_item_id=item.id,
                          origin_note=_text(data.get("origin_note"), "Origin note"))
        else:
            values.update(origin="manual",
                          origin_note=_text(data.get("origin_note"), "Why this phase exists",
                                            required=True))
            if not values["title"] or not values["scope_summary"]:
                raise WorkspaceError("invalid_field", "A manual phase needs a title and a scope.")
        _require_advisory(values, {"title", "scope_summary", "origin_note"})
        values.update(id=f"ephase_{secrets.token_hex(8)}", client_id=engagement.client_id,
                      engagement_id=engagement.id, status="planned",
                      created_by_consultant_id=consultant_id)
        _require_allowed("engagement_phases", "create_engagement_phase", values)
        session.add(EngagementPhase(**values, **WORKSPACE_ENGAGEMENT_CREATION_STAMP))
        try:
            session.commit()
        except IntegrityError:  # the roadmap item's unique phase binding
            raise WorkspaceError("phase_exists", "This roadmap item already has a phase.") \
                from None
    return get_phase(session_factory, values["id"])


def _phase_for_work(session, phase_id: str, allowed=("authorized",)):
    """The phase and its engagement, refusing a phase whose status does not allow this work."""
    from peak.db.models import EngagementPhase

    phase = session.get(EngagementPhase, phase_id)
    if phase is None:
        return None, None
    engagement = _engagement(session, phase.engagement_id)
    if phase.status not in allowed:
        code = "phase_not_authorized" if phase.status == "planned" else "phase_closed"
        raise WorkspaceError(code, f"This phase is {phase.status}; that is not possible now.")
    return phase, engagement


def authorize_phase(session_factory, phase_id: str, data: dict, actor_id: str,
                    actor_role: Optional[str]) -> Optional[dict]:
    """Record that the client separately agreed to this phase. A human act, Lead or Admin only."""
    from sqlalchemy import update

    from peak.db.models import EngagementPhase

    unknown = set(data) - {"authorization_basis", "authorization_reference"}
    if unknown:
        raise WorkspaceError("invalid_field", f"Not an authorization field: {sorted(unknown)[0]}")
    values = {"status": "authorized",
              "authorization_basis": _text(data.get("authorization_basis"),
                                           "What the client agreed to", required=True),
              "authorization_reference": _text(data.get("authorization_reference"), "Reference",
                                               TITLE_LIMIT),
              "authorized_by_consultant_id": actor_id, "authorized_at": _now()}
    with session_factory() as session:
        phase, engagement = _phase_for_work(session, phase_id, allowed=("planned",))
        if phase is None:
            return None
        if actor_role != ASSIGNMENT_ROLE and actor_id != engagement.assigned_consultant_id:
            raise WorkspaceError("lead_or_admin_required",
                                 "Only the engagement's Lead or an Admin records authorization.")
        _require_allowed("engagement_phases", "record_phase_authorization", values)
        session.execute(update(EngagementPhase).where(EngagementPhase.id == phase.id,
                                                      EngagementPhase.status == "planned")
                        .values(**values))
        session.commit()
    return get_phase(session_factory, phase_id)


def complete_phase(session_factory, phase_id: str, consultant_id: str) -> Optional[dict]:
    """Mark the phase's required work complete. Refused unless :func:`phase_readiness` is ready."""
    from sqlalchemy import update

    from peak.db.models import EngagementPhase

    with session_factory() as session:
        phase, _ = _phase_for_work(session, phase_id)
        if phase is None:
            return None
        readiness = phase_readiness(*_plan_state(session, phase))
        if not readiness["ready"]:
            raise WorkspaceError("phase_not_ready",
                                 "Required work is not complete: "
                                 + "; ".join(b["reason_text"] for b in readiness["blocking"]))
        values = {"status": "completed", "completed_by_consultant_id": consultant_id,
                  "completed_at": _now()}
        _require_allowed("engagement_phases", "complete_engagement_phase", values)
        session.execute(update(EngagementPhase).where(EngagementPhase.id == phase.id,
                                                      EngagementPhase.status == "authorized")
                        .values(**values))
        session.commit()
    return get_phase(session_factory, phase_id)


# --------------------------------------------------------------------------- work plan


def _task_dict(t, records) -> dict:
    return {
        "id": t.id, "phase_id": t.phase_id, "sequence": t.sequence, "title": t.title,
        "instructions": t.instructions, "why_it_matters": t.why_it_matters,
        "what_to_observe": t.what_to_observe,
        "suggested_evidence": t.suggested_evidence or [],
        "follow_up_questions": t.follow_up_questions or [],
        "expected_result": t.expected_result, "required": bool(t.required),
        "requires_record": bool(t.requires_record),
        "depends_on_task_ids": t.depends_on_task_ids or [],
        "condition": ({"task_id": t.condition_task_id, "record_kind": t.condition_record_kind}
                      if t.condition_task_id else None),
        "origin": t.origin, "template_key": t.template_key,
        "inclusion_reason": t.inclusion_reason,
        "added_after_authorization": bool(t.added_after_authorization),
        "status": t.status, "consultant_notes": t.consultant_notes,
        "result_summary": t.result_summary, "not_applicable_reason": t.not_applicable_reason,
        "completed_by_consultant_id": t.completed_by_consultant_id,
        "completed_at": _iso(t.completed_at),
        "records": [_record_dict(r, records) for r in records if r.task_id == t.id],
    }


def _record_dict(r, all_records) -> dict:
    superseded_by = next((o.id for o in all_records if o.supersedes_record_id == r.id), None)
    return {"id": r.id, "task_id": r.task_id, "record_kind": r.record_kind,
            "record_text": r.record_text, "structured": r.structured or {}, "basis": r.basis,
            "supersedes_record_id": r.supersedes_record_id, "superseded_by": superseded_by,
            "recorded_by_consultant_id": r.recorded_by_consultant_id,
            "created_at": _iso(r.created_at)}


def _plan_state(session, phase):
    from sqlalchemy import select

    from peak.db.models import PhaseTask, PhaseTaskRecord

    tasks = session.scalars(select(PhaseTask).where(PhaseTask.phase_id == phase.id)
                            .order_by(PhaseTask.sequence)).all()
    records = session.scalars(select(PhaseTaskRecord).where(PhaseTaskRecord.phase_id == phase.id)
                              .order_by(PhaseTaskRecord.created_at, PhaseTaskRecord.id)).all()
    return phase, tasks, records


def get_phase(session_factory, phase_id: str) -> Optional[dict]:
    """The phase, its ordered work plan with each task's records, and its readiness."""
    from peak.db.models import EngagementPhase

    with session_factory() as session:
        phase = session.get(EngagementPhase, phase_id)
        if phase is None:
            return None
        phase, tasks, records = _plan_state(session, phase)
        out = _phase_summary(phase, [t for t in tasks if t.status != "suggested"])
        out["tasks"] = [_task_dict(t, records) for t in tasks]
        out["readiness"] = phase_readiness(phase, tasks, records)
        return out


def _active_kinds(records, task_id: str) -> set:
    superseded = {r.supersedes_record_id for r in records if r.supersedes_record_id}
    return {r.record_kind for r in records if r.task_id == task_id and r.id not in superseded}


def _applies(task, by_id, records) -> Optional[bool]:
    """True/False once a conditional task's condition is decided; None while it is pending."""
    if not task.condition_task_id:
        return True
    cond = by_id.get(task.condition_task_id)
    if cond is None or cond.status == "not_applicable":
        return False
    if cond.status != "completed":
        return None
    return task.condition_record_kind in _active_kinds(records, cond.id)


def _resolved(task, by_id, records) -> bool:
    return task.status in RESOLVED_TASK_STATUSES or _applies(task, by_id, records) is False


def phase_readiness(phase, tasks, records) -> dict:
    """Has the consultant completed the required work for this phase? Deterministic (READINESS_RULE).

    Reads rows (or row-like objects); never writes, never infers.
    """
    plan = [t for t in tasks if t.status != "suggested"]
    by_id = {t.id: t for t in plan}
    blocking, notes = [], []

    def block(code, text, task=None):
        blocking.append({"code": code, "reason_text": text,
                         **({"task_id": task.id, "sequence": task.sequence, "title": task.title}
                            if task is not None else {})})

    if phase.status == "planned":
        block("phase_not_authorized", "the phase has not been authorized")
    if not plan:
        block("no_work_plan", "the phase has no work plan tasks")
    for t in plan:
        applies = _applies(t, by_id, records)
        if t.status == "not_applicable":
            notes.append({"code": "resolved_not_applicable", "task_id": t.id,
                          "reason_text": t.not_applicable_reason})
        elif applies is False:
            notes.append({"code": "condition_not_met", "task_id": t.id,
                          "reason_text": "its condition was not met, so it does not apply"})
        elif t.status == "completed":
            continue
        elif not t.required:
            notes.append({"code": "optional_incomplete", "task_id": t.id,
                          "reason_text": "optional task not completed"})
        elif applies is None:
            block("condition_pending", f"task {t.sequence} waits on its condition task", t)
        else:
            block("required_task_incomplete", f"required task {t.sequence} is not complete", t)
        if t.added_after_authorization:
            notes.append({"code": "added_after_authorization", "task_id": t.id,
                          "reason_text": "added to the plan after the phase was authorized"})
    for t in tasks:
        if t.status == "suggested":
            notes.append({"code": "suggestion_pending", "task_id": t.id,
                          "reason_text": "suggested task not accepted into the plan"})
    required = [t for t in plan if t.required]
    return {
        "ready": not blocking and phase.status in ("authorized", "completed"),
        "phase_status": phase.status,
        "required_tasks": len(required),
        "required_resolved": sum(1 for t in required if _resolved(t, by_id, records)),
        "blocking": blocking, "notes": notes, "rule": READINESS_RULE,
    }


def _task_values(session, phase, data: dict) -> dict:
    from sqlalchemy import select

    from peak.db.models import PhaseTask

    allowed = {"title", "instructions", "why_it_matters", "what_to_observe", "suggested_evidence",
               "follow_up_questions", "expected_result", "required", "requires_record",
               "depends_on_task_ids", "condition", "inclusion_reason"}
    unknown = set(data) - allowed
    if unknown:
        raise WorkspaceError("invalid_field", f"Not a task field: {sorted(unknown)[0]}")
    values = {
        "title": _text(data.get("title"), "Task", TITLE_LIMIT, required=True),
        "instructions": _text(data.get("instructions"), "What to do", required=True),
        "why_it_matters": _text(data.get("why_it_matters"), "Why it matters"),
        "what_to_observe": _text(data.get("what_to_observe"), "What to observe"),
        "follow_up_questions": _text_list(data.get("follow_up_questions"), "Questions"),
        "expected_result": _text(data.get("expected_result"), "Expected result"),
        "inclusion_reason": _text(data.get("inclusion_reason"), "Why the task is included",
                                  required=True),
    }
    evidence = data.get("suggested_evidence")
    if evidence is not None:
        if not isinstance(evidence, list) or any(e not in RECORD_KINDS for e in evidence):
            raise WorkspaceError("invalid_field",
                                 f"Suggested evidence must be kinds from: {', '.join(RECORD_KINDS)}.")
        values["suggested_evidence"] = list(dict.fromkeys(evidence)) or None
    for flag, default in (("required", True), ("requires_record", False)):
        value = data.get(flag, default)
        if not isinstance(value, bool):
            raise WorkspaceError("invalid_field", f"{flag} must be true or false.")
        values[flag] = value
    existing = set(session.scalars(select(PhaseTask.id).where(PhaseTask.phase_id == phase.id)))
    depends = data.get("depends_on_task_ids")
    if depends is not None:
        if (not isinstance(depends, list) or not all(isinstance(d, str) for d in depends)
                or not set(depends) <= existing):
            raise WorkspaceError("invalid_field", "Prerequisites must be tasks of this phase.")
        values["depends_on_task_ids"] = list(dict.fromkeys(depends)) or None
    condition = data.get("condition")
    if condition is not None:
        if (not isinstance(condition, dict) or set(condition) != {"task_id", "record_kind"}
                or condition["task_id"] not in existing
                or condition["record_kind"] not in RECORD_KINDS):
            raise WorkspaceError("invalid_field", "A condition names an earlier task of this phase "
                                                  "and a record kind.")
        values.update(condition_task_id=condition["task_id"],
                      condition_record_kind=condition["record_kind"])
    return values


def _add_task(session, phase, engagement, values: dict, origin: str, consultant_id: str) -> str:
    from peak.db.models import PhaseTask

    _require_advisory(values, PHASE_TASK_FRAMING_COLUMNS)
    values = {k: v for k, v in values.items() if v is not None}
    values.update(id=f"ptask_{secrets.token_hex(8)}", client_id=engagement.client_id,
                  engagement_id=engagement.id, phase_id=phase.id, origin=origin,
                  sequence=_next_sequence(session, PhaseTask, PhaseTask.phase_id == phase.id),
                  status="suggested" if origin == "si_suggested" else "open",
                  added_after_authorization=phase.status == "authorized",
                  created_by_consultant_id=consultant_id)
    _require_allowed("phase_tasks", "create_phase_task", values)
    session.add(PhaseTask(**values, **WORKSPACE_ENGAGEMENT_CREATION_STAMP))
    session.flush()
    return values["id"]


def add_task(session_factory, phase_id: str, data: dict, consultant_id: str,
             origin: str = "consultant") -> Optional[dict]:
    """Add one task to the end of the plan. ``origin="si_suggested"`` (a synthesis caller, never the
    API) enters as ``suggested`` and is not part of the plan until a consultant accepts it."""
    if origin not in ("consultant", "si_suggested"):
        raise WorkspaceError("invalid_field", "Unknown origin.")
    with session_factory() as session:
        phase, engagement = _phase_for_work(session, phase_id, allowed=("planned", "authorized"))
        if phase is None:
            return None
        _add_task(session, phase, engagement, _task_values(session, phase, data), origin,
                  consultant_id)
        session.commit()
    return get_phase(session_factory, phase_id)


def add_template_tasks(session_factory, phase_id: str, template_key: Optional[str],
                       consultant_id: str) -> Optional[dict]:
    """Add a Peak Method template's guided tasks, in order, with dependencies and conditions.

    ``template_key`` defaults to the phase's roadmap item template. A template is added once.
    """
    from sqlalchemy import select

    from peak.db.models import PhaseTask, RoadmapItem

    with session_factory() as session:
        phase, engagement = _phase_for_work(session, phase_id, allowed=("planned", "authorized"))
        if phase is None:
            return None
        if template_key is None and phase.roadmap_item_id:
            template_key = session.get(RoadmapItem, phase.roadmap_item_id).template_key
        tmpl = method.BY_KEY.get(template_key) if template_key else None
        if tmpl is None:
            raise WorkspaceError("invalid_field", "Name a Peak Method phase template.")
        if session.scalar(select(PhaseTask.id).where(
                PhaseTask.phase_id == phase.id,
                PhaseTask.template_key.startswith(f"{tmpl['key']}.", autoescape=True))):
            raise WorkspaceError("template_already_added",
                                 "This template's tasks are already in the plan.")
        ids = {}
        for step in tmpl["tasks"]:
            values = {
                "title": step["title"], "instructions": step["instructions"],
                "why_it_matters": step["why_it_matters"],
                "what_to_observe": step["what_to_observe"],
                "suggested_evidence": step["suggested_evidence"] or None,
                "follow_up_questions": step["follow_up_questions"] or None,
                "expected_result": step["expected_result"], "required": step["required"],
                "requires_record": step["requires_record"],
                "depends_on_task_ids": [ids[k] for k in step["depends_on"]] or None,
                "template_key": f"{tmpl['key']}.{step['key']}",
                "inclusion_reason": f"Peak Method phase template '{tmpl['title']}' "
                                    f"({method.METHOD_VERSION}).",
            }
            if step["condition"]:
                values.update(condition_task_id=ids[step["condition"][0]],
                              condition_record_kind=step["condition"][1])
            ids[step["key"]] = _add_task(session, phase, engagement, values, "peak_method",
                                         consultant_id)
        session.commit()
    return get_phase(session_factory, phase_id)


def _task_for_work(session, task_id: str):
    from peak.db.models import PhaseTask

    task = session.get(PhaseTask, task_id)
    if task is None:
        return None, None
    phase, _ = _phase_for_work(session, task.phase_id)
    return task, phase


def _open_task(task) -> None:
    if task.status == "suggested":
        raise WorkspaceError("task_not_accepted", "Accept the suggested task into the plan first.")
    if task.status in RESOLVED_TASK_STATUSES:
        raise WorkspaceError("task_resolved", "This task is already resolved.")


def accept_task(session_factory, task_id: str) -> Optional[dict]:
    """A consultant accepts a suggested task into the plan (a visible scope decision)."""
    from sqlalchemy import update

    from peak.db.models import EngagementPhase, PhaseTask

    with session_factory() as session:
        task = session.get(PhaseTask, task_id)
        if task is None:
            return None
        phase = session.get(EngagementPhase, task.phase_id)
        _engagement(session, phase.engagement_id)
        if phase.status == "completed":
            raise WorkspaceError("phase_closed", "This phase is completed.")
        if task.status != "suggested":
            raise WorkspaceError("invalid_transition", "Only a suggested task can be accepted.")
        _require_allowed("phase_tasks", "accept_suggested_phase_task", {"status": "open"})
        session.execute(update(PhaseTask).where(PhaseTask.id == task.id,
                                                PhaseTask.status == "suggested")
                        .values(status="open"))
        session.commit()
        phase_id = task.phase_id
    return get_phase(session_factory, phase_id)


def update_task(session_factory, task_id: str, data: dict) -> Optional[dict]:
    """Start a task or edit the consultant's notes. Framing is not editable."""
    from sqlalchemy import update

    from peak.db.models import PhaseTask

    unknown = set(data) - {"status", "consultant_notes"}
    if unknown:
        raise WorkspaceError("invalid_field", f"Not an editable task field: {sorted(unknown)[0]}")
    values = {}
    if "status" in data:
        if data["status"] != "in_progress":
            raise WorkspaceError("invalid_field", "A task can only be started here.")
        values["status"] = "in_progress"
    if "consultant_notes" in data:
        values["consultant_notes"] = _text(data["consultant_notes"], "Notes", 10000)
    if not values:
        raise WorkspaceError("invalid_field", "Nothing to update.")
    with session_factory() as session:
        task, phase = _task_for_work(session, task_id)
        if task is None:
            return None
        _open_task(task)
        _require_allowed("phase_tasks", "update_phase_task_progress", values)
        session.execute(update(PhaseTask).where(PhaseTask.id == task.id).values(**values))
        session.commit()
    return get_phase(session_factory, phase.id)


def complete_task(session_factory, task_id: str, data: dict,
                  consultant_id: str) -> Optional[dict]:
    """The signed-in consultant completes a task with a result summary they write."""
    from sqlalchemy import update

    from peak.db.models import PhaseTask

    unknown = set(data) - {"result_summary"}
    if unknown:
        raise WorkspaceError("invalid_field", f"Not a completion field: {sorted(unknown)[0]}")
    summary = _text(data.get("result_summary"), "Result summary", 10000, required=True)
    with session_factory() as session:
        task, phase = _task_for_work(session, task_id)
        if task is None:
            return None
        _open_task(task)
        _, tasks, records = _plan_state(session, phase)
        by_id = {t.id: t for t in tasks if t.status != "suggested"}
        pending = [by_id[d].sequence for d in task.depends_on_task_ids or []
                   if d in by_id and not _resolved(by_id[d], by_id, records)]
        if pending:
            raise WorkspaceError("prerequisites_incomplete",
                                 f"Resolve task(s) {', '.join(map(str, pending))} first.")
        if task.requires_record and not _active_kinds(records, task.id):
            raise WorkspaceError("record_required",
                                 "Record what you found against this task before completing it.")
        values = {"status": "completed", "result_summary": summary,
                  "completed_by_consultant_id": consultant_id, "completed_at": _now()}
        _require_allowed("phase_tasks", "complete_phase_task", values)
        session.execute(update(PhaseTask).where(PhaseTask.id == task.id).values(**values))
        session.commit()
    return get_phase(session_factory, phase.id)


def resolve_task_not_applicable(session_factory, task_id: str, data: dict,
                                consultant_id: str) -> Optional[dict]:
    """The consultant records that a task does not apply, and why. Shown in readiness notes."""
    from sqlalchemy import update

    from peak.db.models import PhaseTask

    unknown = set(data) - {"reason"}
    if unknown:
        raise WorkspaceError("invalid_field", f"Not a field: {sorted(unknown)[0]}")
    reason = _text(data.get("reason"), "Reason", required=True)
    with session_factory() as session:
        task, phase = _task_for_work(session, task_id)
        if task is None:
            return None
        _open_task(task)
        values = {"status": "not_applicable", "not_applicable_reason": reason,
                  "completed_by_consultant_id": consultant_id, "completed_at": _now()}
        _require_allowed("phase_tasks", "resolve_phase_task_not_applicable", values)
        session.execute(update(PhaseTask).where(PhaseTask.id == task.id).values(**values))
        session.commit()
    return get_phase(session_factory, phase.id)


def _structured(kind: str, value) -> Optional[dict]:
    if value is None:
        return None
    fields = STRUCTURED_FIELDS[kind]
    if not isinstance(value, dict) or set(value) - set(fields):
        raise WorkspaceError("invalid_field", f"A {kind} record may carry only: "
                                              f"{', '.join(fields) or 'no structured fields'}.")
    out = {}
    for key, item in value.items():
        if isinstance(item, (int, float)) and not isinstance(item, bool) and key == "value":
            out[key] = item
        else:
            text = _clean(item, 1000, key)
            if text:
                out[key] = text
    return out or None


def record_task_work(session_factory, task_id: str, data: dict,
                     consultant_id: str) -> Optional[dict]:
    """The signed-in consultant records what they found while doing a task. Insert-only."""
    from sqlalchemy import update
    from sqlalchemy.exc import IntegrityError

    from peak.db.models import PhaseTask, PhaseTaskRecord

    unknown = set(data) - {"record_kind", "record_text", "structured", "basis",
                           "supersedes_record_id"}
    if unknown:
        raise WorkspaceError("invalid_field", f"Not a record field: {sorted(unknown)[0]}")
    kind = data.get("record_kind")
    if kind in MEDIA_RECORD_KINDS:
        raise WorkspaceError("evidence_capture_not_available",
                             "Photo and document capture is not available yet; record a note "
                             "describing the item and where it is kept.")
    if kind not in STRUCTURED_FIELDS:
        raise WorkspaceError("invalid_field", "Unknown record kind.")
    basis = data.get("basis") or None
    if basis is not None and basis not in RECORD_BASES:
        raise WorkspaceError("invalid_field", "Basis must be testimony, observed, document, "
                                              "measured or inferred.")
    values = {"record_kind": kind,
              "record_text": _text(data.get("record_text"), "What you found", 10000,
                                   required=True),
              "structured": _structured(kind, data.get("structured")), "basis": basis}
    with session_factory() as session:
        task, phase = _task_for_work(session, task_id)
        if task is None:
            return None
        _open_task(task)
        supersedes = data.get("supersedes_record_id") or None
        if supersedes is not None:
            old = session.get(PhaseTaskRecord, supersedes)
            if old is None or old.task_id != task.id:
                raise WorkspaceError("invalid_field", "A correction must supersede a record of "
                                                      "this task.")
        values = {k: v for k, v in values.items() if v is not None}
        values.update(id=f"ptrec_{secrets.token_hex(8)}", client_id=task.client_id,
                      engagement_id=task.engagement_id, phase_id=task.phase_id, task_id=task.id,
                      supersedes_record_id=supersedes, recorded_by_consultant_id=consultant_id)
        values = {k: v for k, v in values.items() if v is not None}
        _require_allowed("phase_task_records", "create_phase_task_record", values)
        session.add(PhaseTaskRecord(**values, **WORKSPACE_ENGAGEMENT_CREATION_STAMP))
        if task.status == "open":
            _require_allowed("phase_tasks", "update_phase_task_progress",
                             {"status": "in_progress"})
            session.execute(update(PhaseTask).where(PhaseTask.id == task.id,
                                                    PhaseTask.status == "open")
                            .values(status="in_progress"))
        try:
            session.commit()
        except IntegrityError:  # a record is superseded at most once
            raise WorkspaceError("already_superseded",
                                 "That record has already been corrected.") from None
    return get_phase(session_factory, phase.id)
