"""Release packages, two-stage approval, Final Approver designation and release (Phase 213).

Implements docs/ARTIFACT_LIFECYCLE.md §5–§7 and §9A for Final Reports. The layers are:

    canonical artifact version (Phase 212: immutable business content and provenance)
      → release package (that version bound to its exact client-facing renditions)
        → web rendition (static HTML bytes) and DOCX rendition (DOCX bytes), stored
          → Lead Consultant approval → Final Approver approval → release

**Humans approve the release package**, not the version alone: the exact web and DOCX artifacts
proposed for release. Both renditions are rendered once, from the version's *stored* canonical
content (never from working state), and their bytes are stored with the package. Nothing is ever
re-rendered for a package: reviewing, approving, releasing and serving all use the stored bytes, so
a later change to working state or to rendering code cannot alter a package (AL47, AL48). A change
to content or to either rendition produces a new package that needs its own approvals (AL45).

Every act is an append-only record; nothing here updates or deletes. A package's state is derived:

- ``released`` — a release record exists (it stays released after a newer package supersedes it);
- ``superseded`` — a newer package of the same artifact exists and this one was never released;
- ``rejected`` — either approval level recorded a rejection;
- ``final_approved`` / ``lead_approved`` — that level recorded an approval;
- ``prepared`` — nothing yet.

Roles are workflow roles, not account roles (AL18):

- **Lead Consultant** is the engagement's assigned consultant (``engagements.assigned_consultant_id``;
  only an Admin may change it). Lead approval is refused when no consultant is assigned.
- **Final Approver** is explicitly designated per package, after Lead approval, by the Lead approver
  or the engagement's assigned consultant, from existing consultant accounts other than the Lead
  approver. A designation can be reassigned until the final decision exists; reassignment adds a
  row that supersedes the previous one. Only the current designee may decide.

Each decision binds to the package id and the package hash the approver was shown (which covers the
version's content hash and both rendition hashes), and records which rendition the human reviewed.
Every act re-hashes the stored version content and the stored rendition bytes, and refuses if
anything no longer matches. **Renditions are client-facing** (the release presentation layer); a
package whose stored renditions fail the client-presentation check cannot be approved or released.
Designation and final decisions run under a lock on the engagement row, so the current designation
is decided at commit time.
"""

from __future__ import annotations

import hashlib
import json
import secrets
from typing import Optional

from peak.persistence.allowlist import (
    WORKSPACE_ENGAGEMENT_CREATION_STAMP,
    is_allowed_workspace_write,
)

from . import artifacts
from .service import WorkspaceError

LEAD = "lead_consultant"
FINAL = "final_approver"
APPROVED = "approved"
REJECTED = "rejected"
DECISIONS = (APPROVED, REJECTED)
MAX_NOTE_LENGTH = 2000

WEB = "web"
DOCX = "docx"
RENDITION_TYPES = (WEB, DOCX)
#: Names the package-hash construction. Change it only together with ``package_hash``.
PACKAGE_FORMAT = "peak.release_package.v1"


def _require_allowed(table: str, action: str, values: dict) -> None:
    if not is_allowed_workspace_write(table, action, values.keys()):
        raise WorkspaceError("write_not_permitted", f"{table}/{action} may not write these fields.")


def _refuse(code: str, message: str):
    raise WorkspaceError(code, message)


def _sha256(data: bytes) -> str:
    return hashlib.sha256(data).hexdigest()


def report_content_hash(report) -> str:
    """The canonical content hash of a composed ``FinalReport`` (the Phase 212 version hash)."""
    return artifacts.content_hash(artifacts.canonical_json(artifacts.final_report_content(report)))


def package_hash(artifact_version_id: str, content_hash: str, rendition_hashes: dict) -> str:
    """sha256 over the version identity, its content hash, and every rendition hash, canonically."""
    return _sha256(json.dumps(
        {"format": PACKAGE_FORMAT, "artifact_version_id": artifact_version_id,
         "content_hash": content_hash, "renditions": rendition_hashes},
        sort_keys=True, separators=(",", ":")).encode("utf-8"))


def render_final_report_renditions(report) -> dict:
    """``{type: (media_type, file_name, renderer, bytes)}`` for a (rebuilt) FinalReport.

    Both renditions use the **client presentation** (``peak.reports.release_presentation``): the
    same content as the internal draft, without its internal status wording or identifiers.
    """
    from peak.reports import final_report_docx, final_report_html
    from peak.reports.release_presentation import client_presentation

    pres = client_presentation(report)
    return {
        WEB: (final_report_html.HTML_MEDIA_TYPE, None, final_report_html.__name__,
              final_report_html.render_final_report_html(report, pres)),
        DOCX: (final_report_docx.DOCX_MEDIA_TYPE,
               pres.docx_file_name(report, final_report_docx.final_report_docx_filename(report)),
               final_report_docx.__name__,
               final_report_docx.render_final_report_docx(report, pres)),
    }


def _client_problems(package, version, renditions: dict) -> list:
    """Why the stored renditions are not client-facing (AL36, AL37, AL50); empty when they are."""
    from peak.reports.release_presentation import client_presentation_problems

    if not _intact(package, version, renditions):
        return ["the stored package no longer matches its recorded hashes"]
    return client_presentation_problems(
        {kind: r.content_bytes for kind, r in renditions.items()},
        json.loads(version.content_canonical),
        [package.id, package.artifact_id, version.id, package.package_hash, version.content_hash])


def _require_client_ready(package, version, renditions) -> None:
    if _client_problems(package, version, renditions):
        _refuse("not_client_ready",
                "This package's renditions are not client-facing, so it cannot be approved or "
                "released.")


def _require_reviewed(renditions: dict, reviewed: Optional[str]) -> str:
    """The rendition the human says they reviewed: one of this package's, with its bytes intact."""
    r = renditions.get(reviewed or "")
    if reviewed not in RENDITION_TYPES or r is None:
        _refuse("invalid_field", "Say which rendition you reviewed: the web page or the DOCX.")
    if _sha256(r.content_bytes) != r.rendition_hash:
        _refuse("hash_mismatch", "The rendition you reviewed no longer matches its recorded hash.")
    return reviewed


# --------------------------------------------------------------------------- derived chain


def _load(session, package_id: str):
    """(package, version, renditions by type, approvals by level, designations, release, successor)."""
    from sqlalchemy import select

    from peak.db.models import (
        ArtifactApproval, ArtifactFinalApproverDesignation, ArtifactRelease,
        ArtifactReleasePackage, ArtifactRendition, ArtifactVersion,
    )

    package = session.get(ArtifactReleasePackage, package_id)
    if package is None:
        return None
    version = session.get(ArtifactVersion, package.artifact_version_id)
    renditions = {r.rendition_type: r for r in session.scalars(
        select(ArtifactRendition).where(ArtifactRendition.release_package_id == package_id))}
    approvals = {a.approval_level: a for a in session.scalars(
        select(ArtifactApproval).where(ArtifactApproval.release_package_id == package_id))}
    designations = session.scalars(
        select(ArtifactFinalApproverDesignation)
        .where(ArtifactFinalApproverDesignation.release_package_id == package_id)
        .order_by(ArtifactFinalApproverDesignation.designation_number)).all()
    release = session.scalar(select(ArtifactRelease)
                             .where(ArtifactRelease.release_package_id == package_id))
    successor = session.scalar(select(ArtifactReleasePackage.id)
                               .where(ArtifactReleasePackage.supersedes_package_id == package_id))
    return package, version, renditions, approvals, list(designations), release, successor


def _state(approvals: dict, release, successor) -> str:
    if release is not None:
        return "released"
    if successor is not None:
        return "superseded"
    if any(a.decision == REJECTED for a in approvals.values()):
        return "rejected"
    if FINAL in approvals:
        return "final_approved"
    if LEAD in approvals:
        return "lead_approved"
    return "prepared"


def _current_designation(designations: list):
    """The designation no later designation supersedes (designations form one line)."""
    superseded = {d.supersedes_designation_id for d in designations}
    current = [d for d in designations if d.id not in superseded]
    return current[-1] if current else None


def _intact(package, version, renditions: dict) -> bool:
    """The stored version content and the stored rendition bytes still match every recorded hash."""
    if version is None or set(renditions) != set(RENDITION_TYPES):
        return False
    if artifacts.content_hash(version.content_canonical) != version.content_hash \
            or version.content_hash != package.content_hash:
        return False
    hashes = {}
    for kind, r in renditions.items():
        if _sha256(r.content_bytes) != r.rendition_hash:
            return False
        hashes[kind] = r.rendition_hash
    return package_hash(version.id, version.content_hash, hashes) == package.package_hash


def _require_hash(package, version, renditions, submitted: Optional[str]) -> None:
    """The submitted package hash must be this package's, and everything stored must still match."""
    if not submitted or submitted != package.package_hash:
        _refuse("hash_mismatch", "This package is not the one you reviewed; reload and review it.")
    if not _intact(package, version, renditions):
        _refuse("hash_mismatch", "The stored package no longer matches its recorded hashes.")


def _clean_note(note: Optional[str]) -> Optional[str]:
    note = (note or "").strip()
    if len(note) > MAX_NOTE_LENGTH:
        _refuse("invalid_field", f"The note must be at most {MAX_NOTE_LENGTH} characters.")
    return note or None


def _names(session, ids) -> dict:
    from sqlalchemy import select

    from peak.db.models import Consultant

    ids = {i for i in ids if i}
    if not ids:
        return {}
    return dict(session.execute(select(Consultant.id, Consultant.name)
                                .where(Consultant.id.in_(ids))).all())


def _when(dt) -> Optional[str]:
    return dt.isoformat() if dt else None


def _chain_dict(session, loaded) -> dict:
    package, version, renditions, approvals, designations, release, successor = loaded
    people = _names(session, [package.created_by_consultant_id]
                    + [a.approver_consultant_id for a in approvals.values()]
                    + [d.designated_consultant_id for d in designations]
                    + [d.designated_by_consultant_id for d in designations]
                    + ([release.released_by_consultant_id] if release else []))

    def person(cid):
        return {"id": cid, "name": people.get(cid)} if cid else None

    def decision(level):
        a = approvals.get(level)
        if a is None:
            return None
        return {"id": a.id, "decision": a.decision, "by": person(a.approver_consultant_id),
                "at": _when(a.created_at), "note": a.decision_note,
                "package_hash": a.package_hash, "content_hash": a.content_hash,
                "reviewed_rendition": a.reviewed_rendition_type,
                "designation_id": a.designation_id}

    current = _current_designation(designations)
    return {
        "id": package.id, "artifact_id": package.artifact_id,
        "engagement_id": package.engagement_id, "package_number": package.package_number,
        "artifact_version_id": package.artifact_version_id,
        "version_number": version.version_number if version else None,
        "content_hash": package.content_hash, "package_hash": package.package_hash,
        "hash_verified": _intact(package, version, renditions),
        "client_problems": _client_problems(package, version, renditions),
        "renditions": {
            kind: {"id": r.id, "media_type": r.media_type, "file_name": r.file_name,
                   "rendered_by": r.rendered_by, "byte_length": r.byte_length,
                   "rendition_hash": r.rendition_hash}
            for kind, r in sorted(renditions.items())},
        "created_by": person(package.created_by_consultant_id),
        "created_at": _when(package.created_at),
        "supersedes_package_id": package.supersedes_package_id,
        "superseded_by_package_id": successor,
        "state": _state(approvals, release, successor),
        "lead_decision": decision(LEAD),
        "final_decision": decision(FINAL),
        "current_designation": (
            {"id": current.id, "consultant": person(current.designated_consultant_id),
             "by": person(current.designated_by_consultant_id), "at": _when(current.created_at)}
            if current else None),
        "designations": [
            {"id": d.id, "number": d.designation_number,
             "consultant": person(d.designated_consultant_id),
             "by": person(d.designated_by_consultant_id), "at": _when(d.created_at),
             "supersedes_designation_id": d.supersedes_designation_id}
            for d in designations],
        "release": ({"id": release.id, "by": person(release.released_by_consultant_id),
                     "at": _when(release.created_at), "package_hash": release.package_hash}
                    if release else None),
    }


def get_package(session_factory, package_id: str) -> Optional[dict]:
    """One package's derived state, renditions (metadata only) and full approval record."""
    with session_factory() as session:
        loaded = _load(session, package_id)
        return _chain_dict(session, loaded) if loaded else None


def get_rendition(session_factory, package_id: str, rendition_type: str) -> Optional[dict]:
    """The stored bytes of one rendition, exactly as rendered when the package was prepared.

    Never re-rendered. ``None`` if the package or rendition does not exist; refused if the stored
    bytes no longer match their hash.
    """
    from sqlalchemy import select

    from peak.db.models import ArtifactRendition

    with session_factory() as session:
        r = session.scalar(select(ArtifactRendition)
                           .where(ArtifactRendition.release_package_id == package_id,
                                  ArtifactRendition.rendition_type == rendition_type))
        if r is None:
            return None
        if _sha256(r.content_bytes) != r.rendition_hash:
            _refuse("hash_mismatch", "The stored rendition no longer matches its recorded hash.")
        return {"media_type": r.media_type, "file_name": r.file_name, "bytes": r.content_bytes,
                "rendition_hash": r.rendition_hash}


def _final_report_artifact(session, engagement_id: str):
    """The engagement's final-report artifact: the earliest created, if several exist."""
    from sqlalchemy import select

    from peak.db.models import Artifact

    return session.scalars(select(Artifact)
                           .where(Artifact.engagement_id == engagement_id,
                                  Artifact.artifact_type == artifacts.ARTIFACT_TYPE_FINAL_REPORT)
                           .order_by(Artifact.created_at, Artifact.id)).first()


def _packages(session, artifact_id: str):
    from sqlalchemy import select

    from peak.db.models import ArtifactReleasePackage

    return session.scalars(select(ArtifactReleasePackage)
                           .where(ArtifactReleasePackage.artifact_id == artifact_id)
                           .order_by(ArtifactReleasePackage.package_number.desc())).all()


def get_final_report_review(session_factory, engagement_id: str, draft_report=None) -> dict:
    """The final report's release packages, newest first, each with its derived chain.

    With ``draft_report``, also says whether the live draft's content matches the latest package's
    version (if it does not, a new package is needed to release the current content).
    """
    draft_hash = report_content_hash(draft_report) if draft_report is not None else None
    with session_factory() as session:
        artifact = _final_report_artifact(session, engagement_id)
        packages = [] if artifact is None else [
            _chain_dict(session, _load(session, p.id)) for p in _packages(session, artifact.id)]
    return {
        "engagement_id": engagement_id,
        "artifact_id": artifact.id if artifact else None,
        "packages": packages,
        "draft_content_hash": draft_hash,
        "draft_matches_latest": bool(packages) and packages[0]["content_hash"] == draft_hash,
    }


def get_released_package(session_factory, engagement_id: str) -> Optional[dict]:
    """The package current for client delivery (AL30): the most recently released one."""
    from sqlalchemy import select

    from peak.db.models import ArtifactRelease

    with session_factory() as session:
        artifact = _final_report_artifact(session, engagement_id)
        if artifact is None:
            return None
        release = session.scalars(select(ArtifactRelease)
                                  .where(ArtifactRelease.artifact_id == artifact.id)
                                  .order_by(ArtifactRelease.created_at.desc(),
                                            ArtifactRelease.id.desc())).first()
        package_id = release.release_package_id if release else None
    return get_package(session_factory, package_id) if package_id else None


# --------------------------------------------------------------------------- acts


def _insert(session, model, table: str, action: str, values: dict) -> None:
    _require_allowed(table, action, values)
    session.add(model(**values, **WORKSPACE_ENGAGEMENT_CREATION_STAMP))


def _commit(session) -> None:
    from sqlalchemy.exc import IntegrityError

    try:
        session.commit()
    except IntegrityError:
        # Another record for this package or artifact was written at the same moment.
        session.rollback()
        _refuse("decision_conflict", "This changed just now; reload and try again.")


def _ids(row, prefix: str) -> dict:
    """Identity columns shared by every record under one package (or under its version)."""
    version_id = getattr(row, "artifact_version_id", None) or row.id
    return {"id": f"{prefix}_{secrets.token_hex(8)}", "artifact_id": row.artifact_id,
            "artifact_version_id": version_id, "client_id": row.client_id,
            "engagement_id": row.engagement_id}


def prepare_final_report_package(session_factory, engagement_id: str, report,
                                 consultant_id: str) -> Optional[dict]:
    """Fix the composed report as a version (Phase 212) and prepare its release package.

    The renditions are rendered from the version's **stored** content, then stored. If the latest
    package already holds this version with byte-identical renditions, no package is created and it
    is returned with ``"created": False``. Otherwise the new package supersedes the latest one, so it
    alone can be approved; approvals never carry over (AL45).
    """
    from peak.db.models import ArtifactReleasePackage, ArtifactRendition, ArtifactVersion

    with session_factory() as session:
        artifact = _final_report_artifact(session, engagement_id)
        artifact_id = artifact.id if artifact else None
    if artifact_id is None:
        created = artifacts.create_artifact(session_factory, engagement_id,
                                            artifacts.ARTIFACT_TYPE_FINAL_REPORT, consultant_id)
        if created is None:
            return None
        artifact_id = created["id"]
    version_id = artifacts.create_final_report_version(session_factory, artifact_id, report,
                                                       consultant_id)["id"]
    with session_factory() as session:
        version = session.get(ArtifactVersion, version_id)
        artifacts._workspace_engagement(session, version.engagement_id)
        rebuilt = artifacts.final_report_from_content(json.loads(version.content_canonical))
        rendered = render_final_report_renditions(rebuilt)
        hashes = {kind: _sha256(r[3]) for kind, r in rendered.items()}
        digest = package_hash(version.id, version.content_hash, hashes)
        latest = next(iter(_packages(session, artifact_id)), None)
        if latest is not None and latest.package_hash == digest:
            existing = _chain_dict(session, _load(session, latest.id))
            if existing["state"] == "rejected":
                # A rejected package is terminal; the identical package is never offered again.
                _refuse("package_rejected",
                        "This exact package was rejected. Change the report or its presentation, "
                        "then prepare a new package.")
            return {**existing, "created": False}
        package = {**_ids(version, "artpkg"),
                   "package_number": latest.package_number + 1 if latest else 1,
                   "content_hash": version.content_hash, "package_hash": digest,
                   "supersedes_package_id": latest.id if latest else None,
                   "created_by_consultant_id": consultant_id}
        _insert(session, ArtifactReleasePackage, "artifact_release_packages",
                "create_release_package", package)
        for kind, (media_type, file_name, renderer, data) in rendered.items():
            _insert(session, ArtifactRendition, "artifact_renditions",
                    "create_artifact_rendition",
                    {**_ids(version, "artrnd"), "release_package_id": package["id"],
                     "rendition_type": kind, "media_type": media_type, "rendered_by": renderer,
                     "file_name": file_name, "byte_length": len(data), "content_bytes": data,
                     "rendition_hash": hashes[kind]})
        _commit(session)
    return {**get_package(session_factory, package["id"]), "created": True}


def _package_engagement_id(session_factory, package_id: str) -> Optional[str]:
    """The package's engagement id (immutable), read in its own short transaction."""
    from peak.db.models import ArtifactReleasePackage

    with session_factory() as session:
        package = session.get(ArtifactReleasePackage, package_id)
        return package.engagement_id if package else None


def _lock_engagement(session, engagement_id: str) -> None:
    """Serialize designation and final decisions on one engagement (``SELECT ... FOR UPDATE``).

    Must be the **first** statement of the transaction: on MySQL/InnoDB the transaction's read
    snapshot is taken at its first consistent read, so every read after the lock sees whatever a
    competing designation or final decision committed before releasing it. The runtime role already
    holds UPDATE on ``engagements``, which a locking read requires; no row is modified. SQLite ignores
    the clause and serializes writers itself.
    """
    from sqlalchemy import select

    from peak.db.models import Engagement

    session.execute(select(Engagement.id).where(Engagement.id == engagement_id).with_for_update())


def _open_package(session, package_id: str):
    """Load a package that can still be acted on: stamped engagement, not superseded or released."""
    loaded = _load(session, package_id)
    if loaded is None:
        return None
    package, _, _, _, _, release, successor = loaded
    engagement = artifacts._workspace_engagement(session, package.engagement_id)
    if engagement is None:
        return None
    if release is not None:
        _refuse("already_released", "This package has already been released.")
    if successor is not None:
        _refuse("package_superseded", "A newer package supersedes this one; review that package.")
    return engagement, loaded


def _decision_values(package, level: str, decision: str, consultant_id: str,
                     note: Optional[str]) -> dict:
    return {**_ids(package, "artappr"), "release_package_id": package.id,
            "approval_level": level, "decision": decision, "approver_consultant_id": consultant_id,
            "content_hash": package.content_hash, "package_hash": package.package_hash,
            "decision_note": note}


def record_lead_decision(session_factory, package_id: str, decision: str,
                         package_hash_seen: Optional[str], reviewed_rendition: Optional[str],
                         note: Optional[str], consultant_id: str) -> Optional[dict]:
    """The Lead Consultant approves or rejects this exact package (AL15, AL20, AL43).

    ``reviewed_rendition`` records which rendition (web or DOCX) the Lead reviewed (AL51).
    """
    from peak.db.models import ArtifactApproval

    if decision not in DECISIONS:
        _refuse("invalid_field", "The decision must be approved or rejected.")
    note = _clean_note(note)
    with session_factory() as session:
        opened = _open_package(session, package_id)
        if opened is None:
            return None
        engagement, (package, version, renditions, approvals, _, _, _) = opened
        if LEAD in approvals:
            _refuse("lead_decision_recorded", "The Lead Consultant has already decided this package.")
        if not engagement.assigned_consultant_id:
            _refuse("no_lead_consultant",
                    "An Admin must assign a consultant to this engagement before Lead review.")
        if consultant_id != engagement.assigned_consultant_id:
            _refuse("not_lead_consultant",
                    "Only the engagement's assigned consultant can give the Lead approval.")
        _require_hash(package, version, renditions, package_hash_seen)
        _require_client_ready(package, version, renditions)
        reviewed = _require_reviewed(renditions, reviewed_rendition)
        _insert(session, ArtifactApproval, "artifact_approvals", "create_artifact_approval",
                {**_decision_values(package, LEAD, decision, consultant_id, note),
                 "reviewed_rendition_type": reviewed})
        _commit(session)
    return get_package(session_factory, package_id)


def designate_final_approver(session_factory, package_id: str, designee_id: str,
                             consultant_id: str) -> Optional[dict]:
    """Designate, or reassign, this package's Final Approver. Never overwrites a designation."""
    from peak.db.models import ArtifactFinalApproverDesignation, Consultant

    engagement_id = _package_engagement_id(session_factory, package_id)
    if engagement_id is None:
        return None
    with session_factory() as session:
        _lock_engagement(session, engagement_id)  # first statement: see the latest final decision
        opened = _open_package(session, package_id)
        if opened is None:
            return None
        engagement, (package, _, _, approvals, designations, _, _) = opened
        lead = approvals.get(LEAD)
        if lead is None or lead.decision != APPROVED:
            _refuse("lead_approval_required",
                    "A Final Approver can be designated only after the Lead approval.")
        if FINAL in approvals:
            _refuse("final_decision_recorded",
                    "The final decision is recorded; the Final Approver can no longer change.")
        if consultant_id not in (lead.approver_consultant_id, engagement.assigned_consultant_id):
            _refuse("not_lead_consultant",
                    "Only the Lead approver or the engagement's assigned consultant can designate "
                    "the Final Approver.")
        if session.get(Consultant, designee_id or "") is None:
            _refuse("invalid_field", "Choose an existing consultant as Final Approver.")
        if designee_id == lead.approver_consultant_id:
            _refuse("same_human",
                    "The Final Approver must be a different person from the Lead approver.")
        current = _current_designation(designations)
        if current is not None and current.designated_consultant_id == designee_id:
            _refuse("already_designated", "That consultant is already the Final Approver.")
        _insert(session, ArtifactFinalApproverDesignation,
                "artifact_final_approver_designations", "create_final_approver_designation",
                {**_ids(package, "artdsg"), "release_package_id": package.id,
                 "designation_number": (designations[-1].designation_number + 1
                                        if designations else 1),
                 "designated_consultant_id": designee_id,
                 "designated_by_consultant_id": consultant_id,
                 "supersedes_designation_id": current.id if current else None})
        _commit(session)
    return get_package(session_factory, package_id)


def record_final_decision(session_factory, package_id: str, decision: str,
                          package_hash_seen: Optional[str], reviewed_rendition: Optional[str],
                          note: Optional[str], consultant_id: str) -> Optional[dict]:
    """The designated Final Approver approves or rejects the Lead-approved package (AL16, AL17).

    Runs under the engagement lock, so the designation it checks is the one current at commit:
    a reassignment that committed first is seen, and none can commit until this decision has.
    """
    from peak.db.models import ArtifactApproval

    if decision not in DECISIONS:
        _refuse("invalid_field", "The decision must be approved or rejected.")
    note = _clean_note(note)
    engagement_id = _package_engagement_id(session_factory, package_id)
    if engagement_id is None:
        return None
    with session_factory() as session:
        _lock_engagement(session, engagement_id)  # first statement: see the latest designation
        opened = _open_package(session, package_id)
        if opened is None:
            return None
        _, (package, version, renditions, approvals, designations, _, _) = opened
        lead = approvals.get(LEAD)
        if lead is None or lead.decision != APPROVED:
            _refuse("lead_approval_required",
                    "The final decision can be given only after the Lead approval.")
        if FINAL in approvals:
            _refuse("final_decision_recorded", "The final decision on this package is recorded.")
        current = _current_designation(designations)
        if current is None:
            _refuse("no_final_approver_designated", "Designate a Final Approver first.")
        if consultant_id == lead.approver_consultant_id:
            _refuse("same_human",
                    "The Lead approver cannot also give the final approval for this package.")
        if consultant_id != current.designated_consultant_id:
            _refuse("not_designated_final_approver",
                    "Only the designated Final Approver can decide this package.")
        _require_hash(package, version, renditions, package_hash_seen)
        if lead.package_hash != package.package_hash:
            _refuse("hash_mismatch", "The Lead approval was given to a different package.")
        _require_client_ready(package, version, renditions)
        reviewed = _require_reviewed(renditions, reviewed_rendition)
        _insert(session, ArtifactApproval, "artifact_approvals", "create_artifact_approval",
                {**_decision_values(package, FINAL, decision, consultant_id, note),
                 "designation_id": current.id, "reviewed_rendition_type": reviewed})
        _commit(session)
    return get_package(session_factory, package_id)


def release_package(session_factory, package_id: str, package_hash_seen: Optional[str],
                    consultant_id: str) -> Optional[dict]:
    """Record the release of a package both levels approved (AL25, AL46). No delivery happens.

    The released web and DOCX are the package's stored renditions; nothing is re-rendered.
    """
    from peak.db.models import ArtifactRelease

    with session_factory() as session:
        opened = _open_package(session, package_id)
        if opened is None:
            return None
        _, (package, version, renditions, approvals, _, _, _) = opened
        lead, final = approvals.get(LEAD), approvals.get(FINAL)
        if not (lead and final and lead.decision == APPROVED and final.decision == APPROVED):
            _refuse("approvals_required",
                    "Release needs the Lead approval and then the Final Approver's approval.")
        if lead.approver_consultant_id == final.approver_consultant_id:
            _refuse("same_human", "The two approvals must come from different people.")
        if consultant_id not in (lead.approver_consultant_id, final.approver_consultant_id):
            _refuse("not_an_approver",
                    "Only the Lead approver or the Final Approver can release this package.")
        _require_hash(package, version, renditions, package_hash_seen)
        if not lead.package_hash == final.package_hash == package.package_hash:
            _refuse("hash_mismatch", "The approvals were given to a different package.")
        _require_client_ready(package, version, renditions)
        _insert(session, ArtifactRelease, "artifact_releases", "create_artifact_release",
                {**_ids(package, "artrel"), "release_package_id": package.id,
                 "released_by_consultant_id": consultant_id,
                 "content_hash": package.content_hash, "package_hash": package.package_hash,
                 "lead_approval_id": lead.id, "final_approval_id": final.id})
        _commit(session)
    return get_package(session_factory, package_id)
