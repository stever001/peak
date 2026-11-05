"""Lead review of an observation (Phase 226): the one route from discovery to recommendation eligibility.

Consultant observation → the engagement's Lead reviews it as worded → derived eligibility.

**The fact recorded.** The Lead Consultant's decision on one observation, exactly as it read when
they reviewed it: approve it for internal reliance as an operational finding at a stated
reliability (``low`` / ``medium`` / ``high``, the Phase 117 vocabulary), or decline. That judgement
cannot be derived from anything Peak holds, and it is the review Contract C4 says only the governed
path can supply.

**Who.** Only the engagement's Lead Consultant (``engagements.assigned_consultant_id``), the same
holder as the Lead artifact approval. Refused when none is assigned. The Lead may review their own
observation; the assessment then says so.

**History, not edits.** Each review is a new ``observation_lead_reviews`` row, numbered per
observation; the highest is current. The request names the review and the text the Lead was shown,
so a decision is never recorded against a review or a wording they did not see. Repeating the
current decision on the same text writes nothing.

**What it does not do.** It never changes the observation or any finding, writes no evidence or
review record of the governed evidence path, and drafts no recommendation. Eligibility is derived on
each read by :func:`peak.reports.discovery_assessment.build_recommendation_eligibility`, the same
rule the assessment uses. No task, phase, readiness, package or approval state changes.
"""

from __future__ import annotations

import hashlib
import secrets
from typing import Optional

from peak.persistence.allowlist import WORKSPACE_ENGAGEMENT_CREATION_STAMP

from .discovery import _names, _require_allowed, _workspace_engagement
from .service import WorkspaceError

DECISIONS = ("approve_internal", "decline")
RELIABILITY = ("low", "medium", "high")
_FIELDS = {"decision", "reliability", "statement_hash", "current_review_id"}


def statement_hash(text: str) -> str:
    """The SHA-256 of the observation text as stored. What the Lead's request must name."""
    return hashlib.sha256((text or "").encode("utf-8")).hexdigest()


def _reviews(session, observation_id: str) -> list:
    from sqlalchemy import select

    from peak.db.models import ObservationLeadReview

    return list(session.scalars(select(ObservationLeadReview)
                                .where(ObservationLeadReview.observation_id == observation_id)
                                .order_by(ObservationLeadReview.review_number)))


def _summary(r) -> dict:
    return {"review_id": r.id, "engagement_id": r.engagement_id, "observation_id": r.observation_id,
            "reviewer_consultant_id": r.reviewer_consultant_id, "decision": r.decision,
            "reliability": r.reliability, "reviewed_statement": r.reviewed_statement,
            "review_number": r.review_number}


def _state(session, observation, engagement, consultant_id: Optional[str]) -> dict:
    """The observation's reviews and derived eligibility, by the assessment's own rule."""
    import dataclasses

    from peak.reports.discovery_assessment import (
        build_discovery_findings, build_recommendation_eligibility,
    )

    rows = _reviews(session, observation.id)
    names = _names(session, [r.reviewer_consultant_id for r in rows]
                   + [engagement.assigned_consultant_id, observation.recorded_by_consultant_id])
    finding = build_discovery_findings([{
        "observation_id": observation.id, "observation_text": observation.observation_text,
        "session_id": observation.session_id,
        "recorded_by_consultant_id": observation.recorded_by_consultant_id}], [], names)
    eligibility = build_recommendation_eligibility(finding, [_summary(r) for r in rows],
                                                   engagement.id, names)
    lead = engagement.assigned_consultant_id
    return {
        "observation_id": observation.id,
        "engagement_id": engagement.id,
        "statement_hash": statement_hash(observation.observation_text),
        "lead": {"id": lead, "name": names.get(lead)} if lead else None,
        "you_are_lead": bool(lead and consultant_id == lead),
        "history": [{"review_id": r.id, "review_number": r.review_number, "decision": r.decision,
                     "reliability": r.reliability,
                     "reviewer": names.get(r.reviewer_consultant_id),
                     "statement_matches": r.reviewed_statement.strip()
                     == (observation.observation_text or "").strip(),
                     "created_at": r.created_at.isoformat() if r.created_at else None}
                    for r in reversed(rows)],
        "eligibility": dataclasses.asdict(eligibility[0]) if eligibility else None,
    }


def get_lead_review(session_factory, observation_id: str,
                    consultant_id: Optional[str] = None) -> Optional[dict]:
    """The observation's Lead reviews, newest first, and its derived eligibility. Reads only."""
    from peak.db.models import DiscoveryObservation, Engagement

    with session_factory() as session:
        observation = session.get(DiscoveryObservation, observation_id)
        if observation is None:
            return None
        engagement = session.get(Engagement, observation.engagement_id)
        if engagement is None:
            return None
        return _state(session, observation, engagement, consultant_id)


def record_lead_review(session_factory, observation_id: str, data: dict,
                       consultant_id: str) -> Optional[dict]:
    """The Lead approves this observation for internal reliance, at a reliability, or declines it."""
    from sqlalchemy.exc import IntegrityError

    from peak.db.models import DiscoveryObservation, ObservationLeadReview

    unknown = set(data) - _FIELDS
    if unknown:
        raise WorkspaceError("invalid_field", f"Not a review field: {sorted(unknown)[0]}")
    decision, reliability = data.get("decision"), data.get("reliability") or None
    if decision not in DECISIONS:
        raise WorkspaceError("invalid_field", "The decision must be approve_internal or decline.")
    if decision == "approve_internal" and reliability not in RELIABILITY:
        raise WorkspaceError("invalid_field", "An approval needs a reliability: low, medium or high.")
    if decision == "decline" and reliability is not None:
        raise WorkspaceError("invalid_field", "A decline carries no reliability.")
    if not isinstance(data.get("statement_hash"), str) or "current_review_id" not in data:
        raise WorkspaceError("invalid_field", "Name the observation text and the current review you "
                                              "were shown.")

    with session_factory() as session:
        observation = session.get(DiscoveryObservation, observation_id)
        if observation is None:
            return None
        engagement = _workspace_engagement(session, observation.engagement_id)
        if engagement is None:
            return None
        if not engagement.assigned_consultant_id:
            raise WorkspaceError("no_lead_consultant",
                                 "An Admin must assign a consultant to this engagement before a "
                                 "Lead review.")
        if consultant_id != engagement.assigned_consultant_id:
            raise WorkspaceError("not_lead_consultant",
                                 "Only the engagement's Lead Consultant can review an observation.")
        if data["statement_hash"] != statement_hash(observation.observation_text):
            raise WorkspaceError("observation_changed",
                                 "The observation has changed since you opened it. Read it again.")
        rows = _reviews(session, observation.id)
        current = rows[-1] if rows else None
        shown_before = rows[-2].id if len(rows) > 1 else None
        if (current is not None and current.decision == decision
                and current.reliability == reliability
                and current.reviewer_consultant_id == consultant_id
                and current.reviewed_statement == observation.observation_text
                and data["current_review_id"] in (current.id, shown_before)):
            return _state(session, observation, engagement, consultant_id)  # a repeat writes nothing
        if data["current_review_id"] != (current.id if current else None):
            raise WorkspaceError("review_changed",
                                 "This observation's review has changed since you opened it.")
        values = {"id": f"olr_{secrets.token_hex(8)}", "client_id": observation.client_id,
                  "engagement_id": engagement.id, "observation_id": observation.id,
                  "reviewer_consultant_id": consultant_id, "decision": decision,
                  "reliability": reliability, "reviewed_statement": observation.observation_text,
                  "review_number": len(rows) + 1}
        _require_allowed("observation_lead_reviews", "create_observation_lead_review", values)
        session.add(ObservationLeadReview(**values, **WORKSPACE_ENGAGEMENT_CREATION_STAMP))
        try:
            session.commit()
        except IntegrityError:  # another review took this number first
            raise WorkspaceError("review_changed",
                                 "This observation's review has changed since you opened it.") from None
        return _state(session, observation, engagement, consultant_id)
