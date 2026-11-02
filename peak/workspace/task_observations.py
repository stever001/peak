"""Guided work observations (Phase 222): a consultant records an observation while doing a task.

Phase task → zero or more observations the consultant wrote while doing it.

**One observation model.** A work observation is an ordinary ``discovery_observations`` row: the
consultant's own words, with the same basis, low-hanging-fruit and effort/value fields, edited in
place as before, and read by the assessment like any other observation. This module adds only its
origin (``observation_task_origins``): the phase and task it was recorded during, written once in
the same transaction as the observation and never moved.

**Nothing automatic.** Task records and captured evidence are never turned into an observation, and
no wording is suggested. Recording one changes no task status, completion rule or phase readiness,
and creates no finding or recommendation beyond what any observation already feeds.

**Where.** On an agreed task of an authorized or completed phase, in that task's engagement. Phase
224: this includes a resolved task and a completed phase, because a consultant often sees what the
work showed only once it is finished. Task records and captures stay closed then, and nothing about
the task or phase changes. Such an observation is shown as written after the work, never as observed
during it (``written_after_work``, derived on each read).
"""

from __future__ import annotations

import secrets
from typing import Optional

from peak.persistence.allowlist import WORKSPACE_ENGAGEMENT_CREATION_STAMP

from .engagement_phases import RESOLVED_TASK_STATUSES, _phase_for_work, _require_allowed
from .service import WorkspaceError


def require_task(session, task_id: str, engagement_id: str):
    """The task an observation is being written on, if it is agreed work of a phase that was
    authorized; else refuse."""
    from peak.db.models import PhaseTask

    task = session.get(PhaseTask, task_id)
    if task is None or task.engagement_id != engagement_id:
        raise WorkspaceError("invalid_link", "That task is not part of this engagement.")
    _phase_for_work(session, task.phase_id, allowed=("authorized", "completed"))
    if task.status == "suggested":
        raise WorkspaceError("task_not_accepted", "Accept the suggested task into the plan first.")
    return task


def _written_after_work(origin, task, phase) -> bool:
    """Was this origin created after its task resolved or its phase completed?

    Read from ``updated_at``, not ``completed_at``: a resolved task and a completed phase are never
    updated again, so ``updated_at`` is when that happened, on the same database clock as the
    origin's ``created_at``. ``completed_at`` comes from the API host's clock.
    """
    finished = []
    if task is not None and task.status in RESOLVED_TASK_STATUSES:
        finished.append(task.updated_at)
    if phase is not None and phase.status == "completed":
        finished.append(phase.updated_at)
    return any(origin.created_at > at for at in finished if at and origin.created_at)


def add_origin(session, observation_id: str, task) -> None:
    """Record the task an observation was made during, inside the caller's transaction."""
    from peak.db.models import ObservationTaskOrigin

    values = {"id": f"otor_{secrets.token_hex(8)}", "client_id": task.client_id,
              "engagement_id": task.engagement_id, "observation_id": observation_id,
              "phase_id": task.phase_id, "task_id": task.id}
    _require_allowed("observation_task_origins", "create_observation_task_origin", values)
    session.add(ObservationTaskOrigin(**values, **WORKSPACE_ENGAGEMENT_CREATION_STAMP))


def origins(session, observation_ids) -> dict:
    """``{observation_id: origin}`` for the observations given that were made during a task."""
    from sqlalchemy import select

    from peak.db.models import EngagementPhase, ObservationTaskOrigin, PhaseTask

    ids = {i for i in observation_ids if i}
    if not ids:
        return {}
    rows = session.scalars(select(ObservationTaskOrigin)
                           .where(ObservationTaskOrigin.observation_id.in_(ids))).all()
    if not rows:
        return {}
    tasks = {t.id: t for t in session.scalars(
        select(PhaseTask).where(PhaseTask.id.in_({r.task_id for r in rows})))}
    phases = {p.id: p for p in session.scalars(
        select(EngagementPhase).where(EngagementPhase.id.in_({r.phase_id for r in rows})))}
    out = {}
    for r in rows:
        task, phase = tasks.get(r.task_id), phases.get(r.phase_id)
        out[r.observation_id] = {
            "phase_id": r.phase_id, "phase_title": phase.title if phase is not None else None,
            "task_id": r.task_id, "task_title": task.title if task is not None else None,
            "task_sequence": task.sequence if task is not None else None,
            "written_after_work": _written_after_work(r, task, phase),
        }
    return out


def engagement_origins(session_factory, engagement_id: str) -> dict:
    """Every work observation's origin in one engagement, by observation id. Reads only."""
    from sqlalchemy import select

    from peak.db.models import ObservationTaskOrigin

    with session_factory() as session:
        ids = session.scalars(select(ObservationTaskOrigin.observation_id)
                              .where(ObservationTaskOrigin.engagement_id == engagement_id)).all()
        return origins(session, ids)


def task_engagement_id(session_factory, task_id: str) -> Optional[str]:
    """The engagement a task belongs to, or None. Read-only."""
    from peak.db.models import PhaseTask

    with session_factory() as session:
        task = session.get(PhaseTask, task_id)
        return task.engagement_id if task is not None else None


def task_observations(session_factory, task_id: str) -> Optional[dict]:
    """The observations written on one task, newest first, and whether writing one is possible.

    Reads only; creates nothing.
    """
    from sqlalchemy import select

    from peak.db.models import DiscoveryObservation, ObservationTaskOrigin, PhaseTask

    from .discovery import _names, _observation_dict, _question_refs

    with session_factory() as session:
        task = session.get(PhaseTask, task_id)
        if task is None:
            return None
        ids = session.scalars(select(ObservationTaskOrigin.observation_id)
                              .where(ObservationTaskOrigin.task_id == task_id)).all()
        rows = session.scalars(select(DiscoveryObservation)
                               .where(DiscoveryObservation.id.in_(ids))
                               .order_by(DiscoveryObservation.created_at.desc(),
                                         DiscoveryObservation.id)).all() if ids else []
        names = _names(session, [o.recorded_by_consultant_id for o in rows])
        questions = _question_refs(session, [o.question_id for o in rows])
        found = origins(session, ids)
        try:
            require_task(session, task_id, task.engagement_id)
            closed = None
        except WorkspaceError as exc:
            closed = {"code": exc.code, "message": str(exc)}
        return {"task_id": task.id, "phase_id": task.phase_id, "engagement_id": task.engagement_id,
                "observations": [_observation_dict(o, names, {}, questions, found) for o in rows],
                "recording_closed": closed}
