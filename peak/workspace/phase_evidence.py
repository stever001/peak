"""Guided evidence capture (Phase 220): photos and document photos taken while doing a task.

Engagement → phase → task (→ optionally one task record) → captured evidence.

**Evidence material, nothing more.** A capture is what the consultant photographed. It is never an
observation, a finding, a recommendation, a deficiency or governed assessment evidence
(``evidence_references``), and Peak never reads, parses or interprets its content: no OCR, no
recognition, no metadata extraction. Nothing here creates any other record, changes a task's
status or affects readiness. A task record is still how a consultant says what they found.

**Original bytes, kept unchanged.** The API receives the file, decides its type from its own bytes
(never its name or declared type), hashes it (sha256) and stores it exactly as received under a
server-generated key (``peak.workspace.evidence_storage``). Embedded metadata (EXIF, including any
location) is neither stripped nor read. The row holds metadata, linkage and provenance.

**Insert-only.** No update, no delete. A wrong capture is replaced: the new row supersedes it and
both are kept. Capture follows the same rules as task records: the phase must be authorized and the
task in the plan and not yet resolved; a linked record must be a current record of the same task.

**Access.** Uploads and content reads use short-lived signed grants issued to a signed-in
consultant (:func:`upload_grant`, :func:`content_token`); the bytes are never at a public address
and the storage key never leaves the API.
"""

from __future__ import annotations

import hashlib
import re
import secrets
from typing import Optional

from itsdangerous import BadSignature, SignatureExpired, URLSafeTimedSerializer

from peak.persistence.allowlist import WORKSPACE_ENGAGEMENT_CREATION_STAMP

from . import evidence_storage
from .engagement_phases import _open_task, _require_allowed, _task_for_work, _text
from .service import WorkspaceError

#: Largest accepted upload. An iPad camera photo is a few megabytes.
MAX_BYTES = 20 * 1024 * 1024
CAPTION_LIMIT = 500
EVIDENCE_KINDS = ("photo", "document_photo")
#: Accepted types, decided from the bytes. HEIC/HEIF is kept as the original (Safari shows it).
MEDIA_TYPES = ("image/jpeg", "image/png", "image/heic", "image/heif")
EXTENSIONS = {"image/jpeg": "jpg", "image/png": "png", "image/heic": "heic", "image/heif": "heif"}
#: ISO-BMFF major brands for HEIC (HEVC-coded) and generic HEIF image files.
_HEIC_BRANDS = {b"heic", b"heix", b"heim", b"heis", b"hevc", b"hevx"}
_HEIF_BRANDS = {b"mif1", b"msf1"}

UPLOAD_GRANT_SECONDS = 30 * 60
CONTENT_TOKEN_SECONDS = 15 * 60
_UPLOAD_SALT = "peak.phase220.evidence-upload"
_CONTENT_SALT = "peak.phase220.evidence-content"


def sniff_media_type(data: bytes) -> Optional[str]:
    """The accepted media type these bytes are, or None. Reads only the leading signature."""
    if data[:3] == b"\xff\xd8\xff":
        return "image/jpeg"
    if data[:8] == b"\x89PNG\r\n\x1a\n":
        return "image/png"
    if len(data) >= 12 and data[4:8] == b"ftyp":
        brand = data[8:12]
        if brand in _HEIC_BRANDS:
            return "image/heic"
        if brand in _HEIF_BRANDS:
            return "image/heif"
    return None


def clean_file_name(name) -> Optional[str]:
    """The device's file name, reduced to a plain base name for provenance. Never used as a path."""
    if not isinstance(name, str):
        return None
    base = re.split(r"[\\/]", name)[-1]
    base = "".join(ch for ch in base if ch.isprintable()).strip()[:255]
    return base or None


# --------------------------------------------------------------------------- grants


def upload_grant(secret_key: str, consultant_id: str, task_id: str) -> str:
    return URLSafeTimedSerializer(secret_key, salt=_UPLOAD_SALT).dumps(
        {"c": consultant_id, "t": task_id})


def read_upload_grant(secret_key: str, token: str):
    """``(consultant_id, task_id, expired)``; raises WorkspaceError on a forged or malformed grant.

    An expired grant still names its task (the signature is valid), so the browser can be sent
    back to the right page to try again.
    """
    s = URLSafeTimedSerializer(secret_key, salt=_UPLOAD_SALT)
    try:
        data, expired = s.loads(token or "", max_age=UPLOAD_GRANT_SECONDS), False
    except SignatureExpired:
        data, expired = s.loads(token), True
    except BadSignature:
        raise WorkspaceError("invalid_grant", "The upload link is not valid.") from None
    if not (isinstance(data, dict) and isinstance(data.get("c"), str)
            and isinstance(data.get("t"), str)):
        raise WorkspaceError("invalid_grant", "The upload link is not valid.")
    return data["c"], data["t"], expired


def content_token(secret_key: str, evidence_id: str) -> str:
    return URLSafeTimedSerializer(secret_key, salt=_CONTENT_SALT).dumps({"e": evidence_id})


def read_content_token(secret_key: str, token: str) -> Optional[str]:
    """The evidence id a valid, unexpired content token names, else None."""
    try:
        data = URLSafeTimedSerializer(secret_key, salt=_CONTENT_SALT).loads(
            token or "", max_age=CONTENT_TOKEN_SECONDS)
    except BadSignature:  # includes SignatureExpired
        return None
    return data.get("e") if isinstance(data, dict) and isinstance(data.get("e"), str) else None


# --------------------------------------------------------------------------- reads


def _evidence_dict(e, rows, names, records) -> dict:
    superseded_by = next((o.id for o in rows if o.supersedes_evidence_id == e.id), None)
    record = records.get(e.task_record_id) if e.task_record_id else None
    return {
        "id": e.id, "task_id": e.task_id, "phase_id": e.phase_id,
        "evidence_kind": e.evidence_kind, "caption": e.caption, "media_type": e.media_type,
        "byte_length": e.byte_length, "content_hash": e.content_hash,
        "task_record": ({"id": record.id, "record_kind": record.record_kind,
                         "created_at": record.created_at.isoformat() if record.created_at
                         else None} if record is not None else None),
        "supersedes_evidence_id": e.supersedes_evidence_id, "superseded_by": superseded_by,
        "uploaded_by": names.get(e.uploaded_by_consultant_id),
        "created_at": e.created_at.isoformat() if e.created_at else None,
        # Material the consultant captured; Peak draws no conclusion from it.
        "interpreted": False,
    }


def task_evidence(session_factory, task_id: str) -> Optional[dict]:
    """The task's captured evidence, oldest first, and whether capture is open now.

    Reads only; creates nothing. Storage keys and file names are never returned.
    """
    from sqlalchemy import select

    from peak.db.models import PhaseTask, PhaseTaskEvidence, PhaseTaskRecord

    from .discovery import _names

    with session_factory() as session:
        task = session.get(PhaseTask, task_id)
        if task is None:
            return None
        rows = session.scalars(select(PhaseTaskEvidence).where(PhaseTaskEvidence.task_id == task_id)
                               .order_by(PhaseTaskEvidence.created_at,
                                         PhaseTaskEvidence.id)).all()
        records = {r.id: r for r in session.scalars(
            select(PhaseTaskRecord).where(PhaseTaskRecord.task_id == task_id))}
        names = _names(session, [e.uploaded_by_consultant_id for e in rows])
        try:
            _task_for_work(session, task_id)
            _open_task(task)
            closed = None
        except WorkspaceError as exc:
            closed = {"code": exc.code, "message": str(exc)}
        return {"task_id": task.id, "phase_id": task.phase_id,
                "evidence": [_evidence_dict(e, rows, names, records) for e in rows],
                "capture_closed": closed}


def evidence_content(session_factory, store, evidence_id: str):
    """``(bytes, media_type, evidence_id)`` for one capture, checked against its stored hash."""
    from peak.db.models import PhaseTaskEvidence

    with session_factory() as session:
        e = session.get(PhaseTaskEvidence, evidence_id)
        if e is None:
            return None
        key, media_type, digest, backend = e.storage_key, e.media_type, e.content_hash, \
            e.storage_backend
    if store is None or store.backend != backend:
        raise WorkspaceError("storage_unavailable", "Evidence storage is not available.")
    try:
        data = store.read(key)
    except evidence_storage.EvidenceStoreError:
        raise WorkspaceError("storage_unavailable", "Evidence storage is not available.") \
            from None
    if hashlib.sha256(data).hexdigest() != digest:
        raise WorkspaceError("content_mismatch",
                             "The stored file does not match its recorded hash.")
    return data, media_type, evidence_id


# --------------------------------------------------------------------------- capture


def add_task_evidence(session_factory, store, task_id: str, consultant_id: str, data: dict,
                      content: bytes, file_name=None) -> Optional[dict]:
    """Store one capture for a task and record it. Insert-only; returns the new item."""
    from sqlalchemy import select
    from sqlalchemy.exc import IntegrityError

    from peak.db.models import PhaseTaskEvidence, PhaseTaskRecord

    from .discovery import _names

    unknown = set(data) - {"evidence_kind", "caption", "task_record_id", "supersedes_evidence_id"}
    if unknown:
        raise WorkspaceError("invalid_field", f"Not an evidence field: {sorted(unknown)[0]}")
    kind = data.get("evidence_kind") or "photo"
    if kind not in EVIDENCE_KINDS:
        raise WorkspaceError("invalid_field", "Choose photo or photo of a document.")
    caption = _text(data.get("caption"), "Description", CAPTION_LIMIT)
    if store is None:
        raise WorkspaceError("storage_unavailable", "Evidence capture is not available here yet.")
    if not content:
        raise WorkspaceError("empty_file", "The file was empty.")
    if len(content) > MAX_BYTES:
        raise WorkspaceError("file_too_large",
                             f"The file is larger than {MAX_BYTES // (1024 * 1024)} MB.")
    media_type = sniff_media_type(content)
    if media_type is None:
        raise WorkspaceError("unsupported_type", "Only JPEG, PNG and HEIC/HEIF photos can be added.")

    with session_factory() as session:
        task, phase = _task_for_work(session, task_id)
        if task is None:
            return None
        _open_task(task)
        record_id = data.get("task_record_id") or None
        if record_id is not None:
            record = session.get(PhaseTaskRecord, record_id)
            superseded = record is not None and session.scalar(
                select(PhaseTaskRecord.id).where(PhaseTaskRecord.supersedes_record_id == record.id))
            if record is None or record.task_id != task.id or superseded:
                raise WorkspaceError("invalid_link",
                                     "Evidence can be linked only to a current record of this task.")
        supersedes = data.get("supersedes_evidence_id") or None
        if supersedes is not None:
            old = session.get(PhaseTaskEvidence, supersedes)
            if old is None or old.task_id != task.id:
                raise WorkspaceError("invalid_link", "A replacement must replace evidence of this "
                                                     "task.")
            if session.scalar(select(PhaseTaskEvidence.id).where(
                    PhaseTaskEvidence.supersedes_evidence_id == old.id)):
                raise WorkspaceError("already_replaced", "That evidence has already been replaced.")
        evidence_id = f"ptevd_{secrets.token_hex(8)}"
        key = evidence_storage.evidence_key(task.engagement_id, evidence_id)
        values = {"id": evidence_id, "client_id": task.client_id,
                  "engagement_id": task.engagement_id, "phase_id": task.phase_id,
                  "task_id": task.id, "task_record_id": record_id, "evidence_kind": kind,
                  "caption": caption, "media_type": media_type, "byte_length": len(content),
                  "content_hash": hashlib.sha256(content).hexdigest(),
                  "storage_backend": store.backend, "storage_key": key,
                  "file_name": clean_file_name(file_name), "supersedes_evidence_id": supersedes,
                  "uploaded_by_consultant_id": consultant_id}
        values = {k: v for k, v in values.items() if v is not None}
        _require_allowed("phase_task_evidence", "create_phase_task_evidence", values)
        # Bytes first: a row never points at bytes that were not stored. If the insert then
        # fails, the stored bytes are unreferenced and harmless (there is no delete path).
        try:
            store.put(key, content, media_type)
        except evidence_storage.EvidenceStoreError:
            raise WorkspaceError("storage_unavailable", "The file could not be stored. Try again.") \
                from None
        session.add(PhaseTaskEvidence(**values, **WORKSPACE_ENGAGEMENT_CREATION_STAMP))
        try:
            session.commit()
        except IntegrityError:  # evidence is replaced at most once
            raise WorkspaceError("already_replaced",
                                 "That evidence has already been replaced.") from None
        row = session.get(PhaseTaskEvidence, evidence_id)
        rows = session.scalars(select(PhaseTaskEvidence)
                               .where(PhaseTaskEvidence.task_id == task.id)).all()
        records = {r.id: r for r in session.scalars(
            select(PhaseTaskRecord).where(PhaseTaskRecord.task_id == task.id))}
        return _evidence_dict(row, rows, _names(session, [consultant_id]), records)


def file_extension(media_type: str) -> str:
    return EXTENSIONS.get(media_type, "bin")
