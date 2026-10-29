"""Phase work record (Phase 223): everything recorded during one engagement phase, in one place.

Engagement phase → its agreed tasks, in order → for each: its outcome, the consultant's records,
the photos and documents captured on it, and the observations written while doing it.

**Composed, never stored.** The record is read from the Phase 217–222 rows on every request. It has
no table, no write path and no saved copy. It is not an artifact version, and it is not part of the
assessment or the Final Report.

**Nothing added.** Every word in it was written by a consultant: a result summary, a not-applicable
reason, a record, a caption or an observation. Peak only orders and counts these rows. It does not
summarize them, draw a conclusion from them or read a capture. Readiness is the Phase 217 rule.

**One phase.** Every row read must carry this phase's id (or, for an observation, an origin naming
it) and this phase's engagement. A suggested task is not agreed work and is left out. Storage keys,
file names and hashes are never returned.
"""

from __future__ import annotations

from typing import Optional

from .engagement_phases import _applies, _iso, _phase_summary, _record_dict, phase_readiness

#: How the record is put together, shown with it.
COMPOSITION_RULE = (
    "Composed on request from what was recorded during this phase: each agreed task's outcome, the "
    "consultant's records, captured photos and documents, and observations written during the "
    "task. Nothing is summarized, inferred or saved, and Peak does not read the captures.")


def _outcome(task, by_id, records) -> str:
    """``completed``, ``not_applicable``, ``does_not_apply`` (its condition was not met) or ``open``."""
    if task.status in ("completed", "not_applicable"):
        return task.status
    return "does_not_apply" if _applies(task, by_id, records) is False else "open"


def phase_work_record(session_factory, phase_id: str) -> Optional[dict]:
    """The phase's work record, or None for an unknown phase. Reads only; deterministic."""
    from sqlalchemy import select

    from peak.db.models import (
        Client, DiscoveryObservation, Engagement, EngagementPhase, ObservationEvidenceLink,
        ObservationTaskOrigin, PhaseTask, PhaseTaskEvidence, PhaseTaskRecord, RoadmapItem,
    )

    from .discovery import _names, _observation_dict, _question_refs
    from .observation_evidence import _item
    from .task_observations import origins as origin_map

    with session_factory() as session:
        phase = session.get(EngagementPhase, phase_id)
        if phase is None:
            return None
        eid = phase.engagement_id
        engagement = session.get(Engagement, eid)
        client = session.get(Client, phase.client_id)
        tasks = session.scalars(select(PhaseTask)
                                .where(PhaseTask.phase_id == phase.id, PhaseTask.engagement_id == eid)
                                .order_by(PhaseTask.sequence, PhaseTask.id)).all()
        plan = [t for t in tasks if t.status != "suggested"]
        by_id = {t.id: t for t in plan}
        records = session.scalars(select(PhaseTaskRecord)
                                  .where(PhaseTaskRecord.phase_id == phase.id,
                                         PhaseTaskRecord.engagement_id == eid)
                                  .order_by(PhaseTaskRecord.created_at, PhaseTaskRecord.id)).all()
        captures = session.scalars(select(PhaseTaskEvidence)
                                   .where(PhaseTaskEvidence.phase_id == phase.id,
                                          PhaseTaskEvidence.engagement_id == eid)
                                   .order_by(PhaseTaskEvidence.created_at,
                                             PhaseTaskEvidence.id)).all()
        origin_rows = session.scalars(select(ObservationTaskOrigin)
                                      .where(ObservationTaskOrigin.phase_id == phase.id,
                                             ObservationTaskOrigin.engagement_id == eid)).all()
        task_of = {r.observation_id: r.task_id for r in origin_rows if r.task_id in by_id}
        observations = session.scalars(select(DiscoveryObservation)
                                       .where(DiscoveryObservation.id.in_(set(task_of)),
                                              DiscoveryObservation.engagement_id == eid)
                                       .order_by(DiscoveryObservation.created_at,
                                                 DiscoveryObservation.id)).all() if task_of else []
        links = session.scalars(select(ObservationEvidenceLink)
                                .where(ObservationEvidenceLink.observation_id.in_(
                                           {o.id for o in observations}),
                                       ObservationEvidenceLink.engagement_id == eid)
                                ).all() if observations else []
        # A linked capture may come from another task or phase of the same engagement.
        linked = session.scalars(select(PhaseTaskEvidence)
                                 .where(PhaseTaskEvidence.id.in_({k.evidence_id for k in links}),
                                        PhaseTaskEvidence.engagement_id == eid)).all() \
            if links else []
        all_captures = {e.id: e for e in [*captures, *linked]}
        replaced_by = dict(session.execute(
            select(PhaseTaskEvidence.supersedes_evidence_id, PhaseTaskEvidence.id)
            .where(PhaseTaskEvidence.supersedes_evidence_id.in_(set(all_captures)),
                   PhaseTaskEvidence.engagement_id == eid)
        ).all()) if all_captures else {}
        capture_tasks = {t.id: t for t in session.scalars(
            select(PhaseTask).where(PhaseTask.id.in_({e.task_id for e in all_captures.values()})))} \
            if all_captures else {}
        names = _names(session, [phase.authorized_by_consultant_id, phase.completed_by_consultant_id]
                       + [t.completed_by_consultant_id for t in plan]
                       + [r.recorded_by_consultant_id for r in records]
                       + [e.uploaded_by_consultant_id for e in all_captures.values()]
                       + [o.recorded_by_consultant_id for o in observations]
                       + [k.linked_by_consultant_id for k in links])
        questions = _question_refs(session, [o.question_id for o in observations])
        found = origin_map(session, [o.id for o in observations])
        item = session.get(RoadmapItem, phase.roadmap_item_id) if phase.roadmap_item_id else None

        items = {i: _item(e, capture_tasks, names, replaced_by) for i, e in all_captures.items()}
        captured_at = {i: e.created_at for i, e in all_captures.items()}
        evidence_links: dict = {}
        for k in sorted(links, key=lambda k: (k.created_at, captured_at.get(k.evidence_id),
                                             k.evidence_id)):
            if k.evidence_id in items:  # links are checked on insert; a capture is never deleted
                evidence_links.setdefault(k.observation_id, []).append({
                    **items[k.evidence_id], "linked_by": names.get(k.linked_by_consultant_id),
                    "linked_at": _iso(k.created_at)})

        out_tasks, totals = [], {"tasks": len(plan), "completed": 0, "not_applicable": 0,
                                 "does_not_apply": 0, "open": 0, "records": 0,
                                 "corrected_records": 0, "captures": 0, "replaced_captures": 0,
                                 "observations": len(observations), "linked_captures": 0}
        for t in plan:
            outcome = _outcome(t, by_id, records)
            totals[outcome] += 1
            t_records = [r for r in records if r.task_id == t.id]
            t_captures = [e for e in captures if e.task_id == t.id]
            current = [e for e in t_captures if e.id not in replaced_by]
            t_obs = [o for o in observations if task_of.get(o.id) == t.id]
            record_dicts = [_record_dict(r, t_records, names) for r in t_records]
            totals["records"] += sum(1 for r in record_dicts if not r["superseded_by"])
            totals["corrected_records"] += sum(1 for r in record_dicts if r["superseded_by"])
            totals["captures"] += len(current)
            totals["replaced_captures"] += len(t_captures) - len(current)
            out_tasks.append({
                "id": t.id, "sequence": t.sequence, "title": t.title, "required": bool(t.required),
                "status": t.status, "outcome": outcome,
                "added_after_authorization": bool(t.added_after_authorization),
                "result_summary": t.result_summary,
                "not_applicable_reason": t.not_applicable_reason,
                "completed_by": names.get(t.completed_by_consultant_id),
                "completed_at": _iso(t.completed_at),
                "records": record_dicts,
                "captures": [items[e.id] for e in current],
                "replaced_captures": len(t_captures) - len(current),
                "observations": [_observation_dict(o, names, {}, questions, found) for o in t_obs],
            })
        totals["linked_captures"] = sum(len(v) for v in evidence_links.values())

        summary = _phase_summary(phase, plan)
        for key in ("authorized_by_consultant_id", "completed_by_consultant_id",
                    "created_by_consultant_id"):
            summary.pop(key, None)
            if summary["authorization"]:
                summary["authorization"].pop(key, None)
        if summary["authorization"]:
            summary["authorization"]["authorized_by"] = names.get(phase.authorized_by_consultant_id)
        summary["completed_by"] = names.get(phase.completed_by_consultant_id)
        summary["roadmap_item"] = ({"id": item.id, "title": item.title} if item is not None
                                   else None)
        return {
            "phase": summary,
            "engagement": {"id": eid,
                           "engagement_label": engagement.engagement_label if engagement else None,
                           "client_name": client.organization_label if client else None},
            "readiness": phase_readiness(phase, tasks, records),
            "totals": totals,
            "tasks": out_tasks,
            "suggested_not_accepted": len(tasks) - len(plan),
            "evidence_links": evidence_links,
            "composition": {"rule": COMPOSITION_RULE, "stored": False, "interpreted": False},
        }
