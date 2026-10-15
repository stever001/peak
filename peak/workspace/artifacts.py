"""Artifact identity and immutable artifact versions (Phase 212).

The persistence foundation for docs/ARTIFACT_LIFECYCLE.md. Four functions write or read; none of
them updates or deletes:

- ``create_artifact`` — the stable identity of one logical artifact of an engagement, with a
  snapshot of the engagement's phase label;
- ``create_final_report_version`` — an immutable version holding the canonical business content of
  a Phase 208 ``FinalReport``, its deterministic hash, the version it supersedes, and its source
  references;
- ``get_artifact`` / ``get_artifact_version`` — internal reads.

Version creation is explicit. Nothing here runs on a report read, and the report routes do not call
it. A version starts ``versioned``; approval and release are later phases. Every write names its
(table, action) pair and exact columns and is checked by ``is_allowed_workspace_write``. Records get
the fixed ``WORKSPACE_ENGAGEMENT_CREATION_STAMP`` and exist only under an engagement carrying it.
The creating consultant is always the caller's signed-in consultant.

Version numbers and ids are internal metadata (AL36): nothing here is client-facing.
"""

from __future__ import annotations

import dataclasses
import hashlib
import json
import secrets
from typing import Optional

from peak.persistence.allowlist import (
    WORKSPACE_ENGAGEMENT_CREATION_STAMP,
    is_allowed_workspace_write,
)

from .service import WorkspaceError

ARTIFACT_TYPE_FINAL_REPORT = "final_report"
#: Artifact types this phase can create. ARTIFACT_LIFECYCLE.md §13 names more; each is added when
#: it is implemented.
ARTIFACT_TYPES = (ARTIFACT_TYPE_FINAL_REPORT,)

STATUS_VERSIONED = "versioned"

#: Names the canonical serialization below. Change it only together with the serialization.
FINAL_REPORT_CONTENT_FORMAT = "peak.final_report.canonical_json.v1"

#: ``FinalReport`` fields that describe the live draft's state, not its business content. They are
#: lifecycle metadata, which lives on the version (``version_status``), so they are not hashed:
#: freezing ``approved_for_client: false`` into a version would contradict its later approval.
_DRAFT_STATE_FIELDS = ("status", "audience", "client_facing", "approved_for_client",
                       "requires_human_review")

COMPOSER = "peak.reports.final_report.compose_final_report"


def _require_allowed(table: str, action: str, values: dict) -> None:
    if not is_allowed_workspace_write(table, action, values.keys()):
        raise WorkspaceError("write_not_permitted", f"{table}/{action} may not write these fields.")


# --------------------------------------------------------------------------- canonical content


def final_report_content(report) -> dict:
    """The canonical business content of a ``FinalReport``: every field except draft state."""
    content = dataclasses.asdict(report)
    for name in _DRAFT_STATE_FIELDS:
        content.pop(name, None)
    return content


def _build(hint, value):
    """``value`` (plain JSON data) as an instance of the type ``hint``, recursively."""
    import typing

    if value is None:
        return None
    origin, args = typing.get_origin(hint), typing.get_args(hint)
    if origin is typing.Union:  # Optional[X]
        return _build(next(a for a in args if a is not type(None)), value)
    if origin in (list, typing.List):
        return [_build(args[0], v) for v in value]
    if origin in (dict, typing.Dict):
        return {k: _build(args[1], v) for k, v in value.items()}
    if dataclasses.is_dataclass(hint):
        hints = typing.get_type_hints(hint)
        return hint(**{f.name: _build(hints[f.name], value[f.name])
                       for f in dataclasses.fields(hint) if f.name in value})
    return value


def final_report_from_content(content: dict):
    """Rebuild a ``FinalReport`` from a version's stored canonical content (Phase 213).

    Renditions are rendered from this, never from working state, so every rendition of a package
    derives from the stored version (AL34, AL44). Draft-state fields are not stored and take the
    composer's fixed values. Refuses unless the rebuilt report has exactly the stored content.
    """
    from peak.reports.final_report import FinalReport

    report = _build(FinalReport, content)
    if canonical_json(final_report_content(report)) != canonical_json(content):
        raise WorkspaceError("content_unreadable",
                             "The stored version could not be rebuilt exactly; nothing was rendered.")
    return report


def canonical_json(content: dict) -> str:
    """Deterministic JSON: sorted keys, no insignificant whitespace, UTF-8 text kept as-is."""
    return json.dumps(content, sort_keys=True, separators=(",", ":"), ensure_ascii=False,
                      allow_nan=False)


def content_hash(canonical: str) -> str:
    return hashlib.sha256(canonical.encode("utf-8")).hexdigest()


def _source_references(report) -> dict:
    """Which composer produced the content, and the working-state records it referenced."""
    evidence, sources, reviews, observations, sessions, answers = (set() for _ in range(6))
    for f in report.evidence_findings.findings:
        evidence.add(f.evidence_id)
        sources.update(f.source_reference_ids)
        reviews.update(f.supporting_review_ids)
    for r in report.recommendations.recommendations:
        evidence.update(r.supporting_evidence_ids)
        sources.update(r.supporting_source_ids)
        reviews.update(r.supporting_review_ids)
    for f in report.discovery_summary.findings:
        for value, bucket in ((f.trace.observation_id, observations),
                              (f.trace.session_id, sessions), (f.trace.answer_id, answers)):
            if value:
                bucket.add(value)
    return {
        "composer": COMPOSER,
        "report_kind": report.kind,
        "evidence_ids": sorted(evidence),
        "source_reference_ids": sorted(sources),
        "review_ids": sorted(reviews),
        "recommendation_ids": sorted(r.recommendation_id
                                     for r in report.recommendations.recommendations),
        "discovery_observation_ids": sorted(observations),
        "discovery_session_ids": sorted(sessions),
        "discovery_answer_ids": sorted(answers),
    }


# --------------------------------------------------------------------------- reads


def _artifact_dict(a) -> dict:
    return {
        "id": a.id, "client_id": a.client_id, "engagement_id": a.engagement_id,
        "artifact_type": a.artifact_type, "engagement_phase_label": a.engagement_phase_label,
        "created_by_consultant_id": a.created_by_consultant_id,
        "created_at": a.created_at.isoformat() if a.created_at else None,
    }


def _version_dict(v, superseded_by: Optional[str] = None) -> dict:
    return {
        "id": v.id, "artifact_id": v.artifact_id, "client_id": v.client_id,
        "engagement_id": v.engagement_id, "version_number": v.version_number,
        "content_format": v.content_format, "content_hash": v.content_hash,
        "content": json.loads(v.content_canonical),
        "hash_verified": content_hash(v.content_canonical) == v.content_hash,
        "supersedes_version_id": v.supersedes_version_id,
        "superseded_by_version_id": superseded_by,
        "version_status": v.version_status,
        "created_by_consultant_id": v.created_by_consultant_id,
        "created_at": v.created_at.isoformat() if v.created_at else None,
        "source_references": v.source_references,
    }


def _superseded_by(session, version_id: str) -> Optional[str]:
    from sqlalchemy import select

    from peak.db.models import ArtifactVersion

    return session.scalar(select(ArtifactVersion.id)
                          .where(ArtifactVersion.supersedes_version_id == version_id))


def get_artifact(session_factory, artifact_id: str) -> Optional[dict]:
    """The artifact and its versions in sequence order, without their content."""
    from sqlalchemy import select

    from peak.db.models import Artifact, ArtifactVersion

    with session_factory() as session:
        a = session.get(Artifact, artifact_id)
        if a is None:
            return None
        versions = session.scalars(select(ArtifactVersion)
                                   .where(ArtifactVersion.artifact_id == artifact_id)
                                   .order_by(ArtifactVersion.version_number)).all()
        successor = {v.supersedes_version_id: v.id for v in versions if v.supersedes_version_id}
        out = _artifact_dict(a)
        out["versions"] = [{k: d[k] for k in d if k != "content"}
                           for d in (_version_dict(v, successor.get(v.id)) for v in versions)]
        return out


def get_artifact_version(session_factory, version_id: str) -> Optional[dict]:
    """One version with its stored content, re-hashed to confirm it is unchanged."""
    from peak.db.models import ArtifactVersion

    with session_factory() as session:
        v = session.get(ArtifactVersion, version_id)
        if v is None:
            return None
        return _version_dict(v, _superseded_by(session, v.id))


# --------------------------------------------------------------------------- writes


def _workspace_engagement(session, engagement_id: str):
    """The engagement, if it exists and carries the workspace stamp; otherwise refuse."""
    from peak.db.models import Engagement

    engagement = session.get(Engagement, engagement_id)
    if engagement is None:
        return None
    if any(getattr(engagement, k) != v for k, v in WORKSPACE_ENGAGEMENT_CREATION_STAMP.items()):
        raise WorkspaceError("not_a_workspace_engagement",
                             "Artifacts are available only for consultant-workspace engagements.")
    return engagement


def create_artifact(session_factory, engagement_id: str, artifact_type: str,
                    consultant_id: str) -> Optional[dict]:
    """Create the identity of one logical artifact. ``None`` if the engagement does not exist."""
    from peak.db.models import Artifact

    if artifact_type not in ARTIFACT_TYPES:
        raise WorkspaceError("invalid_field", "Unknown artifact type.")
    with session_factory() as session:
        engagement = _workspace_engagement(session, engagement_id)
        if engagement is None:
            return None
        values = {
            "id": f"art_{secrets.token_hex(8)}", "client_id": engagement.client_id,
            "engagement_id": engagement.id, "artifact_type": artifact_type,
            "engagement_phase_label": engagement.current_phase,
            "created_by_consultant_id": consultant_id,
        }
        _require_allowed("artifacts", "create_artifact", values)
        session.add(Artifact(**values, **WORKSPACE_ENGAGEMENT_CREATION_STAMP))
        session.commit()
    return get_artifact(session_factory, values["id"])


def create_final_report_version(session_factory, artifact_id: str, report,
                                consultant_id: str) -> Optional[dict]:
    """Snapshot a composed ``FinalReport`` as the artifact's next immutable version.

    The new version supersedes the artifact's latest version, which is left exactly as it was. If
    the report's canonical content is identical to the latest version's, no version is created and
    the latest one is returned with ``"created": False`` (an unchanged report is not a new version).
    ``None`` if the artifact does not exist.
    """
    from sqlalchemy import select
    from sqlalchemy.exc import IntegrityError

    from peak.db.models import Artifact, ArtifactVersion

    canonical = canonical_json(final_report_content(report))
    digest = content_hash(canonical)
    with session_factory() as session:
        artifact = session.get(Artifact, artifact_id)
        if artifact is None:
            return None
        if artifact.artifact_type != ARTIFACT_TYPE_FINAL_REPORT:
            raise WorkspaceError("invalid_field", "That artifact is not a final report.")
        _workspace_engagement(session, artifact.engagement_id)
        if report.executive_overview.engagement_id != artifact.engagement_id:
            raise WorkspaceError("invalid_field", "That report belongs to a different engagement.")
        latest = session.scalars(select(ArtifactVersion)
                                 .where(ArtifactVersion.artifact_id == artifact_id)
                                 .order_by(ArtifactVersion.version_number.desc())).first()
        if latest is not None and latest.content_hash == digest:
            return {**_version_dict(latest), "created": False}
        values = {
            "id": f"artv_{secrets.token_hex(8)}", "artifact_id": artifact.id,
            "client_id": artifact.client_id, "engagement_id": artifact.engagement_id,
            "version_number": (latest.version_number + 1) if latest else 1,
            "content_format": FINAL_REPORT_CONTENT_FORMAT, "content_canonical": canonical,
            "content_hash": digest, "supersedes_version_id": latest.id if latest else None,
            "version_status": STATUS_VERSIONED, "created_by_consultant_id": consultant_id,
            "source_references": _source_references(report),
        }
        _require_allowed("artifact_versions", "create_artifact_version", values)
        session.add(ArtifactVersion(**values, **WORKSPACE_ENGAGEMENT_CREATION_STAMP))
        try:
            session.commit()
        except IntegrityError:
            # Another version was created for this artifact at the same moment.
            session.rollback()
            raise WorkspaceError("version_conflict",
                                 "Another version was just created; reload and try again.") from None
    return {**get_artifact_version(session_factory, values["id"]), "created": True}
