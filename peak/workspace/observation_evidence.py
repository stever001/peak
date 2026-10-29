"""Evidence referencing (Phase 221): a consultant links captured evidence to their observation.

Observation → zero or more captured items (``phase_task_evidence``) of the same engagement.

**The consultant's statement, nothing more.** A link records that the consultant chose a capture as
support for an observation they wrote. It adds no words to the observation, and creates no
observation, finding, recommendation or governed assessment evidence (``evidence_references``). It
changes no task status, readiness or recommendation eligibility. Peak still never reads, parses or
interprets the capture.

**Insert-only, and historical.** There is no unlink and no edit. A link names the exact capture
chosen. Only a current capture (one not yet replaced) can be linked. If it is replaced later, the
link stays on the original and reads as replaced. It is never moved to the newer capture.

**Access.** Reads return captions, task titles and provenance, never a storage key or file name.
The API adds a short-lived content path to each item (``phase_evidence.content_token``).
"""

from __future__ import annotations

import secrets
from typing import Optional

from peak.persistence.allowlist import WORKSPACE_ENGAGEMENT_CREATION_STAMP

from .engagement_phases import _require_allowed
from .service import WorkspaceError

#: Most captures linked in one save. Far above a real observation; bounds the request.
MAX_LINKS_PER_SAVE = 50


def _item(e, tasks: dict, names: dict, replaced_by: dict) -> dict:
    """One capture as a reference: what it is, where it came from, whether it was replaced."""
    task = tasks.get(e.task_id)
    return {
        "id": e.id, "evidence_kind": e.evidence_kind, "caption": e.caption,
        "media_type": e.media_type,
        "task": {"id": e.task_id, "title": task.title if task is not None else None,
                 "phase_id": e.phase_id},
        "uploaded_by": names.get(e.uploaded_by_consultant_id),
        "created_at": e.created_at.isoformat() if e.created_at else None,
        "superseded": e.id in replaced_by, "superseded_by": replaced_by.get(e.id),
        # Material the consultant captured; Peak draws no conclusion from it.
        "interpreted": False,
    }


def engagement_evidence(session_factory, engagement_id: str) -> Optional[dict]:
    """The engagement's linkable captures and every observation's links. Reads only.

    ``available``: current captures (not replaced), newest first. ``links``: for each observation
    with links, its linked captures (by when linked, then when captured), each as it was chosen (a replaced capture
    stays, marked ``superseded``).
    """
    from sqlalchemy import select

    from peak.db.models import Engagement, ObservationEvidenceLink, PhaseTask, PhaseTaskEvidence

    from .discovery import _names

    with session_factory() as session:
        if session.get(Engagement, engagement_id) is None:
            return None
        rows = session.scalars(select(PhaseTaskEvidence)
                               .where(PhaseTaskEvidence.engagement_id == engagement_id)
                               .order_by(PhaseTaskEvidence.created_at.desc(),
                                         PhaseTaskEvidence.id)).all()
        links = session.scalars(select(ObservationEvidenceLink)
                                .where(ObservationEvidenceLink.engagement_id == engagement_id)
                                ).all()
        replaced_by = {e.supersedes_evidence_id: e.id for e in rows if e.supersedes_evidence_id}
        tasks = {t.id: t for t in session.scalars(
            select(PhaseTask).where(PhaseTask.id.in_({e.task_id for e in rows})))} if rows else {}
        names = _names(session, [e.uploaded_by_consultant_id for e in rows]
                       + [link.linked_by_consultant_id for link in links])
        items = {e.id: _item(e, tasks, names, replaced_by) for e in rows}
        captured = {e.id: e.created_at for e in rows}
        # Links saved together share a timestamp; within one, oldest capture first. Deterministic.
        links = sorted(links, key=lambda link: (link.created_at, captured.get(link.evidence_id),
                                                link.evidence_id))
        by_observation: dict = {}
        for link in links:
            item = items.get(link.evidence_id)
            if item is None:  # links are checked on insert; a capture is never deleted
                continue
            by_observation.setdefault(link.observation_id, []).append({
                **item, "linked_by": names.get(link.linked_by_consultant_id),
                "linked_at": link.created_at.isoformat() if link.created_at else None,
            })
        return {"engagement_id": engagement_id,
                "available": [items[e.id] for e in rows if e.id not in replaced_by],
                "links": by_observation}


def evidence_ids_from(data: dict) -> list:
    """Pop and check ``evidence_ids`` from an observation payload: a list of distinct ids."""
    ids = data.pop("evidence_ids", None)
    if ids is None:
        return []
    if not isinstance(ids, list) or not all(isinstance(i, str) and i for i in ids):
        raise WorkspaceError("invalid_field", "Evidence must be a list of evidence ids.")
    if len(set(ids)) != len(ids):
        raise WorkspaceError("duplicate_link", "The same evidence was chosen twice.")
    if len(ids) > MAX_LINKS_PER_SAVE:
        raise WorkspaceError("invalid_field",
                             f"Link at most {MAX_LINKS_PER_SAVE} items in one save.")
    return ids


def add_links(session, observation_id: str, client_id: str, engagement_id: str,
              evidence_ids: list, consultant_id: str) -> None:
    """Add links for an observation inside the caller's transaction. Commits nothing.

    Each capture must belong to the observation's engagement, be current (not replaced) and not be
    linked to this observation already. Any refusal refuses the whole save.
    """
    from sqlalchemy import select

    from peak.db.models import ObservationEvidenceLink, PhaseTaskEvidence

    for evidence_id in evidence_ids:
        e = session.get(PhaseTaskEvidence, evidence_id)
        if e is None or e.engagement_id != engagement_id:
            raise WorkspaceError("invalid_link",
                                 "Only evidence captured in this engagement can be linked.")
        if session.scalar(select(PhaseTaskEvidence.id).where(
                PhaseTaskEvidence.supersedes_evidence_id == e.id)):
            raise WorkspaceError("evidence_replaced",
                                 "That photo was replaced. Link the newest version instead.")
        if session.scalar(select(ObservationEvidenceLink.id).where(
                ObservationEvidenceLink.observation_id == observation_id,
                ObservationEvidenceLink.evidence_id == e.id)):
            raise WorkspaceError("duplicate_link", "That evidence is already linked.")
        values = {"id": f"oevl_{secrets.token_hex(8)}", "client_id": client_id,
                  "engagement_id": engagement_id, "observation_id": observation_id,
                  "evidence_id": e.id, "linked_by_consultant_id": consultant_id}
        _require_allowed("observation_evidence_links", "create_observation_evidence_link", values)
        session.add(ObservationEvidenceLink(**values, **WORKSPACE_ENGAGEMENT_CREATION_STAMP))
