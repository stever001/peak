"""Phase 34 — the controlled DB writer for ``intake_note_records``.

The eighth narrow live DB writer in Peak (after the Phase 20 ``agent_run_records``, Phase 21
``evidence_references``, Phase 22 ``review_records``, Phase 24 ``source_ingestion_records``, Phase
27 ``agent_task_queue_records``, Phase 30 ``review_bundle_records``, and Phase 33
``internal_reviewer_decision_records`` writers). It accepts an approved Phase 17 controlled-write
request whose ``record_draft`` is an :class:`IntakeNoteDraft` and creates **exactly one**
``intake_note_records`` row — nothing else. It is a narrow internal persistence boundary, not a
generic decision engine, review engine, workflow engine, CRUD repository, or arbitrary SQL executor.

**First-class operational notes.** Intake notes are first-class operational records (client
interviews, consultant observations, warehouse walkaround notes, discovery calls, source-intake
comments, controlled packet-ingestion outputs, consultant-authored notes). Unlike prior
summary-only writers, this writer intentionally persists **authorized operational note prose**
(``note_text``) — which is acceptable **only in the managed DB**, never in Git / fixtures /
examples / sample packets / logs / receipts / test data. **Receipts and denial reasons never echo
``note_text`` / note body**; only field names and marker *categories* are ever reported.

**No approval / publication / execution.** This writer approves nothing, never calls the Phase 22
review writer, and **never creates a ``review_records`` row**. It never executes an agent (live or
mock), never calls the Phase 13 executor / MockLLM / a live LLM / AgentNet (including any AgentNet
publication) / MCP / resolver / connector / network, never creates an ``agent_run_records`` row,
and produces no client-facing output, financial verification, or capsule publication. Every stored
row is **review-gated and non-final**: ``review_status=needs_review``, ``lifecycle_status=draft``,
``client_facing_approved=false``, ``financial_verified=false``, ``capsule_candidate_ready=false``,
``publication_allowed=false``, ``execution_allowed=false``, ``requires_human_review=true``.

Mandatory write-time rule: the writer does **not** trust the caller-supplied scope. At write time
it loads the authoritative stored authorization subject — the ``Engagement`` row — from the
database and requires ``request.authorization_scope == engagement.authorization_scope``. Identity
matching (owner, client, engagement) is necessary but **not sufficient**; a scope mismatch is
denied even when every identity matches. Missing stored scope and missing request scope are denied.

Content rule: ``note_text`` may carry ordinary operational prose (bounded length) but is rejected
if it carries obvious credential/secret assignments, DB URLs/DSNs, raw SQL, private keys, stack
traces, raw source-byte/generated-output tokens, or an unbounded raw-JSON dump. Short label/ref
fields and ``note_summary`` are held to the stricter public value-marker classifier. Nothing
sensitive is echoed — only field names and marker categories.

Side-effect boundary: this module performs only the DB work needed to read the stored subject,
check idempotency, insert the authorized row, read it back, and commit/roll back. It may import
SQLAlchemy and ``peak.db`` (this is the DB layer). **SQLite is only the fast local structural-smoke
path — not the production-readiness proof path**; managed MySQL test/staging validation is required
before treating this writer as production-ready (see docs/PRODUCTION_PARITY_DB_VALIDATION.md and
docs/MANAGED_MYSQL_PERSISTENCE_RUBRIC.md). See docs/INTAKE_NOTE_CONTROLLED_WRITER.md and
docs/INTAKE_NOTE_IDEMPOTENCY_POLICY.md.
"""

from __future__ import annotations

import hashlib
import json
import re
import uuid
from typing import List, Optional, Tuple

from sqlalchemy.exc import IntegrityError, SQLAlchemyError

from peak.persistence.contracts import ControlledWriteRequest, ControlledWriteSubject
from peak.persistence.write_plan import prepare_controlled_write
# Reuse the public, DB-free Phase 32 value classifier for short label/summary fields.
from peak.reviewer_decisions.governance import classify_prohibited_value_marker

from .models import Engagement, IntakeNoteRecord
from .session import create_session_factory
from .writer_contracts import (
    INTAKE_NOTE_TARGET_ACTION,
    INTAKE_NOTE_TARGET_TABLE,
    IntakeNoteDraft,
    IntakeNoteWriteOutcome,
    IntakeNoteWriteReceipt,
)

BLOCKED_LIFECYCLE_STATUSES = frozenset({"revoked", "archived", "deleted_reference_only"})
SUPPORTED_SUBJECT_TYPES = frozenset({"engagement"})
REQUIRED_REVIEW_STATUS = "needs_review"
REQUIRED_LIFECYCLE_STATUS = "draft"

# Bounds (documented in docs/INTAKE_NOTE_CONTROLLED_WRITER.md).
MAX_NOTE_TEXT_LEN = 16000
MAX_NOTE_SUMMARY_LEN = 500
MAX_LABEL_LEN = 64
MAX_REF_LEN = 128
_ID_PREFIX = "intn_"

# --- note_text prose-safe marker detection --------------------------------------------------
# note_text is a long-form managed-DB storage field, NOT a short label. Ordinary operational prose
# must pass, so bare secret *words* ("password", "token") are allowed — only credential *disclosure*
# shapes and structural markers (DSN, raw SQL, key material, stack trace, raw JSON dump, raw-content
# field tokens) are rejected. Only the marker *category* is ever reported, never the value.
#
# Credential-DISCLOSURE = a credential/key name followed by a ``:``/``=`` and a value. The key name
# may use ``_``/``-``/space separators, so "api key: X", "private key: X", "connection_string=X" are
# all caught, while bare prose ("we discussed the password policy", "the secret shopper process",
# "token counts were not discussed") has no separator+value and passes.
_CRED_ASSIGN_RE = re.compile(
    r"\b(?:"
    r"passwords?|passwd|pwd|"
    r"secret(?:[ _-]?key)?|"
    r"api[ _-]?key|apikey|"
    r"access[ _-]?key|"
    r"private[ _-]?key|"
    r"client[ _-]?secret|"
    r"connection[ _-]?string|"
    r"aws[ _-]?secret[ _-]?access[ _-]?key|"
    r"credentials?|tokens?"
    r")\b\s*[:=]\s*\S",
    re.IGNORECASE)
_AKIA_RE = re.compile(r"\bAKIA[0-9A-Z]{16}\b")
_PRIVKEY_RE = re.compile(r"-----BEGIN (?:RSA |EC |OPENSSH |DSA |PGP )?PRIVATE KEY-----")
# HTTP auth schemes: "bearer <token>" / "basic <token>". Require the immediately-following token to
# carry at least one digit and be >= 6 chars — this catches credential/base64/hex material
# ("Bearer abc123") while leaving ordinary prose ("bearer bonds", "basic training") untouched.
_AUTH_SCHEME_RE = re.compile(
    r"\b(?:bearer|basic)\s+(?=[A-Za-z0-9+/=_.\-]*\d)[A-Za-z0-9+/=_.\-]{6,}",
    re.IGNORECASE)
_STACKTRACE_RE = re.compile(
    r"traceback \(most recent call last\)|File \"[^\"]+\", line \d+", re.IGNORECASE)
_DSN_MARKERS = ("postgres://", "postgresql://", "mysql://", "mysql+pymysql://", "sqlite://",
                "mongodb://", "redis://", "jdbc:", "database_url", "db_url", "dsn=")
_RAW_SQL_MARKERS = ("select * from", "insert into", "delete from", "drop table", "alter table",
                    "create table ", "truncate table")
_RAW_SQL_UPDATE_RE = re.compile(r"\bupdate\b\s+\S.*?\bset\b", re.IGNORECASE | re.DOTALL)
_RAW_CONTENT_TOKENS = ("source_bytes", "generated_output", "packet_payload", "file_bytes",
                       "base64,")
_JSON_KEYVALUE_RE = re.compile(r'"[^"\n]{1,64}"\s*:')


def _note_text_category(text: str) -> Optional[str]:
    """Return a marker *category* if ``note_text`` carries an obvious unsafe marker, else None.

    Prose-safe: designed so ordinary operational note prose passes. Only the category is returned —
    never the offending value. Categories: 'credential/secret', 'DB-URL/DSN', 'raw-SQL',
    'private-key', 'stack-trace', 'raw-content', 'JSON/object'.
    """
    if not isinstance(text, str):
        return None
    low = text.lower()
    if _PRIVKEY_RE.search(text):
        return "private-key"
    if _CRED_ASSIGN_RE.search(text) or _AKIA_RE.search(text) or _AUTH_SCHEME_RE.search(text):
        return "credential/secret"
    if _STACKTRACE_RE.search(text):
        return "stack-trace"
    if any(m in low for m in _DSN_MARKERS):
        return "DB-URL/DSN"
    if any(m in low for m in _RAW_SQL_MARKERS) or _RAW_SQL_UPDATE_RE.search(text):
        return "raw-SQL"
    if any(t in low for t in _RAW_CONTENT_TOKENS):
        return "raw-content"
    stripped = text.strip()
    if stripped.startswith("{") or stripped.startswith("["):
        try:
            parsed = json.loads(stripped)
            if isinstance(parsed, (dict, list)):
                return "JSON/object"
        except (ValueError, TypeError):
            pass
    if len(_JSON_KEYVALUE_RE.findall(text)) >= 3:
        return "JSON/object"
    return None


def _is_blank(value) -> bool:
    return value is None or (isinstance(value, str) and not value.strip())


def _deny(reason_code: str, message: str, **flags) -> IntakeNoteWriteReceipt:
    receipt = IntakeNoteWriteReceipt(
        outcome=IntakeNoteWriteOutcome.DENIED, permitted=False,
        reason_code=reason_code, reasons=[message])
    for key, val in flags.items():
        setattr(receipt, key, val)
    return receipt


def _label_ok(value, max_len: int) -> bool:
    """A short single-line safe label/ref — no newline, bounded, and carrying no unsafe marker."""
    if value is None:
        return True
    if not isinstance(value, str):
        return False
    if "\n" in value or "\r" in value or len(value) > max_len:
        return False
    return classify_prohibited_value_marker(value) is None


def _safe_list(value) -> List[str]:
    return [v for v in (value or []) if isinstance(v, str)]


def _note_text_sha256(text: Optional[str]) -> Optional[str]:
    if not isinstance(text, str):
        return None
    return hashlib.sha256(text.encode("utf-8")).hexdigest()


def _payload_fingerprint(request: ControlledWriteRequest, draft: IntakeNoteDraft) -> str:
    """Deterministic, canonical fingerprint of the write payload + identity (replay-conflict).

    The note body participates as a **hash** (``note_text_sha256``), never as a re-stored copy, so
    the fingerprint stays bounded and no raw content is duplicated. Safe references/metadata only.
    """
    payload = {
        "owner_id": request.owner_id,
        "client_id": request.client_id,
        "engagement_id": request.engagement_id,
        "authorization_scope": getattr(draft, "authorization_scope", None),
        "note_type": getattr(draft, "note_type", None),
        "note_source": getattr(draft, "note_source", None),
        "note_text_sha256": _note_text_sha256(getattr(draft, "note_text", None)),
        "note_summary": getattr(draft, "note_summary", None),
        "captured_by": getattr(draft, "captured_by", None),
        "captured_role": getattr(draft, "captured_role", None),
        "source_ref": getattr(draft, "source_ref", None),
        "source_ingestion_record_id": getattr(draft, "source_ingestion_record_id", None),
        "related_evidence_reference_id": getattr(draft, "related_evidence_reference_id", None),
        "related_review_bundle_record_id": getattr(draft, "related_review_bundle_record_id", None),
        "review_status": getattr(draft, "review_status", None),
        "lifecycle_status": getattr(draft, "lifecycle_status", None),
        "client_facing_approved": bool(getattr(draft, "client_facing_approved", False)),
        "financial_verified": bool(getattr(draft, "financial_verified", False)),
        "capsule_candidate_ready": bool(getattr(draft, "capsule_candidate_ready", False)),
        "publication_allowed": bool(getattr(draft, "publication_allowed", False)),
        "execution_allowed": bool(getattr(draft, "execution_allowed", False)),
        "requires_human_review": bool(getattr(draft, "requires_human_review", True)),
    }
    blob = json.dumps(payload, sort_keys=True, separators=(",", ":"), default=str)
    return hashlib.sha256(blob.encode("utf-8")).hexdigest()


def _identity_mismatches(request: ControlledWriteRequest, draft: IntakeNoteDraft) -> List[str]:
    """Independently compare identity across the request, draft, and engagement subject.
    Necessary, not sufficient — the DB stored-scope check is the authorization gate."""
    mismatches: List[str] = []
    subject = getattr(request, "subject", None)
    for attr in ("owner_id", "client_id", "engagement_id"):
        req_val = getattr(request, attr, None)
        if getattr(draft, attr, None) != req_val:
            mismatches.append(f"draft.{attr} does not match request.{attr}")
        if subject is not None and getattr(subject, attr, None) != req_val:
            mismatches.append(f"subject.{attr} does not match request.{attr}")
    if getattr(draft, "authorization_scope", None) != getattr(request, "authorization_scope", None):
        mismatches.append("draft.authorization_scope does not match request.authorization_scope")
    return mismatches


def _pre_db_validate(
    request,
) -> Tuple[Optional[IntakeNoteWriteReceipt], Optional[IntakeNoteDraft]]:
    """All governance checks that must pass *before* any DB connection is opened."""
    if not isinstance(request, ControlledWriteRequest):
        return _deny("invalid_request_type",
                     "controlled write request is not a ControlledWriteRequest"), None

    plan_result = prepare_controlled_write(request)
    if not getattr(plan_result, "permitted", False):
        return _deny("plan_not_permitted",
                     "Phase 17 controlled-write plan was not permitted",
                     reasons=list(getattr(plan_result, "reasons", []) or [])
                     or ["Phase 17 controlled-write plan was not permitted"]), None
    plan = getattr(plan_result, "write_plan", None)
    if plan is None or getattr(plan, "requires_controlled_db_writer", False) is not True:
        return _deny("writer_not_required",
                     "controlled-write plan does not require the controlled DB writer"), None

    if getattr(request, "target_table", None) != INTAKE_NOTE_TARGET_TABLE:
        return _deny("wrong_target_table",
                     f"target_table must be '{INTAKE_NOTE_TARGET_TABLE}'"), None
    if getattr(request, "requested_action", None) != INTAKE_NOTE_TARGET_ACTION:
        return _deny("wrong_target_action",
                     f"requested_action must be '{INTAKE_NOTE_TARGET_ACTION}'"), None

    draft = getattr(request, "record_draft", None)
    if not isinstance(draft, IntakeNoteDraft):
        return _deny("invalid_record_draft", "record_draft is not an IntakeNoteDraft"), None

    # No caller-supplied server-controlled fields.
    if getattr(draft, "intake_note_id", None) is not None:
        return _deny("caller_supplied_id",
                     "draft.intake_note_id must be None (server-controlled)"), None
    if getattr(draft, "captured_at", None) is not None:
        return _deny("caller_supplied_timestamp",
                     "draft.captured_at must be None (server-stamped created_at is authoritative)"), None

    # Required short-safe label/ref fields.
    for attr, max_len in (("note_type", MAX_LABEL_LEN), ("note_source", MAX_LABEL_LEN),
                          ("captured_by", MAX_REF_LEN)):
        val = getattr(draft, attr, None)
        if _is_blank(val):
            return _deny("missing_note_field", f"draft.{attr} is required"), None
        if not _label_ok(val, max_len):
            return _deny("invalid_note_label",
                         f"draft.{attr} must be a short single-line safe label "
                         "(no newline / marker / over-length)"), None
    # Optional short-safe label/ref fields.
    for attr, max_len in (("captured_role", MAX_LABEL_LEN), ("source_ref", MAX_REF_LEN),
                          ("source_ingestion_record_id", MAX_REF_LEN),
                          ("related_evidence_reference_id", MAX_REF_LEN),
                          ("related_review_bundle_record_id", MAX_REF_LEN)):
        val = getattr(draft, attr, None)
        if not _is_blank(val) and not _label_ok(val, max_len):
            return _deny("invalid_note_ref",
                         f"draft.{attr} must be a short single-line safe reference "
                         "(no newline / marker / over-length)"), None

    # note_text: required bounded operational prose; reject obvious markers without echoing.
    note_text = getattr(draft, "note_text", None)
    if _is_blank(note_text):
        return _deny("missing_note_text", "draft.note_text is required"), None
    if not isinstance(note_text, str):
        return _deny("invalid_note_text", "draft.note_text must be a string"), None
    if len(note_text) > MAX_NOTE_TEXT_LEN:
        return _deny("note_text_too_long",
                     f"draft.note_text exceeds the {MAX_NOTE_TEXT_LEN}-character bound"), None
    cat = _note_text_category(note_text)
    if cat is not None:
        return _deny("prohibited_note_text_content",
                     f"draft.note_text contains a prohibited {cat} marker "
                     "(store operational prose only; secrets/DSNs/SQL/keys/dumps are rejected)"), None

    # note_summary: optional, short, single-line, no unsafe marker.
    summary = getattr(draft, "note_summary", None)
    if not _is_blank(summary):
        if not isinstance(summary, str) or "\n" in summary or "\r" in summary \
                or len(summary) > MAX_NOTE_SUMMARY_LEN:
            return _deny("invalid_note_summary",
                         f"draft.note_summary must be a short single-line note "
                         f"(<= {MAX_NOTE_SUMMARY_LEN} chars)"), None
        scat = classify_prohibited_value_marker(summary)
        if scat is not None:
            return _deny("prohibited_note_summary_content",
                         f"draft.note_summary contains a prohibited {scat} marker"), None

    # Review-gated, non-final posture.
    if getattr(draft, "review_status", None) != REQUIRED_REVIEW_STATUS:
        return _deny("invalid_draft_review_status",
                     f"draft.review_status must be '{REQUIRED_REVIEW_STATUS}'"), None
    if getattr(draft, "lifecycle_status", None) != REQUIRED_LIFECYCLE_STATUS:
        return _deny("invalid_draft_lifecycle_status",
                     f"draft.lifecycle_status must be '{REQUIRED_LIFECYCLE_STATUS}'"), None
    for flag, code in (
        ("client_facing_approved", "prohibited_client_facing"),
        ("financial_verified", "prohibited_financial_verified"),
        ("capsule_candidate_ready", "prohibited_capsule_candidate"),
        ("publication_allowed", "prohibited_publication_allowed"),
        ("execution_allowed", "prohibited_execution_allowed"),
    ):
        if getattr(draft, flag, False) is True:
            return _deny(code, f"draft.{flag} must be false (Phase 34 persists review-gated, "
                               "non-final intake notes only)"), None
    if getattr(draft, "requires_human_review", True) is not True:
        return _deny("prohibited_no_human_review",
                     "draft.requires_human_review must be true"), None

    # Idempotency key present and valid.
    idem = getattr(request, "idempotency_key", None)
    if _is_blank(idem):
        return _deny("invalid_idempotency_key", "idempotency_key is required"), None
    if not isinstance(idem, str) or len(idem) > 128:
        return _deny("invalid_idempotency_key",
                     "idempotency_key must be a string of at most 128 characters"), None

    # Required identity / traceability fields present.
    for attr in ("owner_id", "client_id", "engagement_id", "requested_by", "requester_role",
                 "authorization_scope"):
        if _is_blank(getattr(request, attr, None)):
            return _deny("missing_identity_field", f"request.{attr} is required"), None

    # Engagement authorization subject present, supported type, id present.
    subject = getattr(request, "subject", None)
    if subject is None:
        return _deny("missing_subject", "request.subject is required"), None
    if getattr(subject, "subject_record_type", None) not in SUPPORTED_SUBJECT_TYPES:
        return _deny("unsupported_subject_type",
                     "subject.subject_record_type must be 'engagement'"), None
    if _is_blank(getattr(subject, "subject_record_id", None)):
        return _deny("missing_subject", "subject.subject_record_id is required"), None

    mismatches = _identity_mismatches(request, draft)
    if mismatches:
        return _deny("identity_mismatch", "; ".join(mismatches)), None

    return None, draft


def _build_record(request: ControlledWriteRequest, draft: IntakeNoteDraft,
                  fingerprint: str) -> IntakeNoteRecord:
    """Explicit field mapping — the authorized note body plus safe references (no __dict__ copy)."""
    return IntakeNoteRecord(
        id=_ID_PREFIX + uuid.uuid4().hex[:16],  # server-controlled
        owner_id=request.owner_id,
        client_id=request.client_id,
        engagement_id=request.engagement_id,
        authorization_scope=request.authorization_scope,  # validated == stored scope
        note_type=draft.note_type,
        note_source=draft.note_source,
        note_text=draft.note_text,          # authorized operational prose (managed-DB only)
        note_summary=draft.note_summary,
        captured_by=draft.captured_by,
        captured_role=draft.captured_role,
        source_ref=draft.source_ref,
        source_ingestion_record_id=draft.source_ingestion_record_id,
        related_evidence_reference_id=draft.related_evidence_reference_id,
        related_review_bundle_record_id=draft.related_review_bundle_record_id,
        review_status=REQUIRED_REVIEW_STATUS,       # review-gated (server-stamped)
        lifecycle_status=REQUIRED_LIFECYCLE_STATUS,
        client_facing_approved=False,
        financial_verified=False,
        capsule_candidate_ready=False,
        publication_allowed=False,
        execution_allowed=False,
        requires_human_review=True,
        idempotency_key=request.idempotency_key,
        payload_fingerprint=fingerprint,
        created_by=request.requested_by,
        # created_at / updated_at are DB server_default (server-stamped).
        details_json={
            "warnings": _safe_list(getattr(draft, "warnings", None)),
            "source_phase": getattr(request, "source_phase", None),
            "note_text_sha256": _note_text_sha256(draft.note_text),  # a hash, not a copy
        },
    )


def _find_existing(session, request: ControlledWriteRequest, idem: str):
    """Look up an existing row on the idempotency boundary (owner/client/engagement/key)."""
    return (
        session.query(IntakeNoteRecord)
        .filter_by(
            owner_id=request.owner_id,
            client_id=request.client_id,
            engagement_id=request.engagement_id,
            idempotency_key=idem,
        )
        .one_or_none()
    )


def _receipt_from_existing(existing: IntakeNoteRecord, idem: str,
                           outcome: str) -> IntakeNoteWriteReceipt:
    return IntakeNoteWriteReceipt(
        outcome=outcome, permitted=True, reason_code=outcome,
        stored_record_id=existing.id, idempotency_key=idem, audit_trace_ref=existing.id,
        database_connection_made=True, sql_execution_made=True,
        database_write_made=False, stored_record_created=False,
        existing_record_returned=True, transaction_committed=False,
        note_type=existing.note_type, note_source=existing.note_source,
        review_status=existing.review_status, lifecycle_status=existing.lifecycle_status,
        reasons=["exact authorized replay; existing record returned, not modified"])


def build_intake_note_controlled_write_request(
    draft: IntakeNoteDraft,
    *,
    requested_by: str,
    requester_role: str,
    idempotency_key: str,
    subject: Optional[ControlledWriteSubject] = None,
    source_phase: str = "phase34",
    lifecycle_status: str = "active",
) -> ControlledWriteRequest:
    """Convenience planner: wrap an :class:`IntakeNoteDraft` in a Phase 17 ControlledWriteRequest.

    Targets exactly ``intake_note_records`` / ``create_intake_note_record`` and opens no database
    connection; a caller passes the result to :func:`persist_intake_note_record`. If ``subject`` is
    omitted, an in-memory engagement subject snapshot is derived from the draft's identity (the
    write-time authorization gate still loads and trusts only the *stored* engagement).
    """
    if subject is None:
        subject = ControlledWriteSubject(
            subject_record_id=draft.engagement_id,
            subject_record_type="engagement",
            owner_id=draft.owner_id,
            client_id=draft.client_id,
            engagement_id=draft.engagement_id,
            stored_authorization_scope=draft.authorization_scope,
            stored_lifecycle_status=lifecycle_status,
        )
    return ControlledWriteRequest(
        owner_id=draft.owner_id,
        client_id=draft.client_id,
        engagement_id=draft.engagement_id,
        requested_by=requested_by,
        requester_role=requester_role,
        authorization_scope=draft.authorization_scope,
        target_table=INTAKE_NOTE_TARGET_TABLE,
        requested_action=INTAKE_NOTE_TARGET_ACTION,
        subject=subject,
        record_draft=draft,
        source_phase=source_phase,
        lifecycle_status=lifecycle_status,
        idempotency_key=idempotency_key,
    )


def persist_intake_note_record(
    controlled_write_request,
    *,
    session_factory=None,
) -> IntakeNoteWriteReceipt:
    """Create one review-gated, **non-final** ``intake_note_records`` row.

    ``session_factory`` is a zero-arg callable returning a SQLAlchemy ``Session`` (defaults to the
    controlled-DB session factory from the environment URL). Returns an
    :class:`IntakeNoteWriteReceipt`; expected governance failures are typed denials, not exceptions.
    Receipts and denial reasons **never echo ``note_text`` / note body**. This writer approves
    nothing, publishes nothing, executes nothing, calls no Phase 22 review writer, and creates no
    ``review_records`` / ``agent_run_records`` row.
    """
    denial, draft = _pre_db_validate(controlled_write_request)
    if denial is not None:
        return denial

    request = controlled_write_request
    subject = request.subject
    idem = request.idempotency_key
    fingerprint = _payload_fingerprint(request, draft)

    factory = session_factory or create_session_factory()
    session = factory()
    attempted_commit = False
    try:
        # --- DB-backed authorization: load the authoritative stored subject ---
        engagement = session.get(Engagement, subject.subject_record_id)
        if engagement is None:
            return _deny("missing_subject",
                         "stored authorization subject (engagement) not found",
                         database_connection_made=True, sql_execution_made=True)

        stored_scope = engagement.authorization_scope
        if _is_blank(stored_scope):
            return _deny("missing_stored_scope",
                         "stored subject has no authorization_scope",
                         database_connection_made=True, sql_execution_made=True)
        if request.authorization_scope != stored_scope:
            return _deny("stored_scope_mismatch",
                         "request.authorization_scope does not match the stored subject's "
                         "authorization_scope (identity match is not sufficient)",
                         database_connection_made=True, sql_execution_made=True)

        subj_mismatch = []
        if engagement.owner_id != request.owner_id:
            subj_mismatch.append("engagement.owner_id")
        if engagement.client_id != request.client_id:
            subj_mismatch.append("engagement.client_id")
        if engagement.id != request.engagement_id:
            subj_mismatch.append("engagement.id != request.engagement_id")
        if subj_mismatch:
            return _deny("identity_mismatch",
                         "stored subject identity mismatch: " + ", ".join(subj_mismatch),
                         database_connection_made=True, sql_execution_made=True)

        if engagement.lifecycle_status in BLOCKED_LIFECYCLE_STATUSES:
            return _deny("subject_lifecycle_blocked",
                         f"stored subject lifecycle_status '{engagement.lifecycle_status}' "
                         "is not permitted",
                         database_connection_made=True, sql_execution_made=True)

        # --- Idempotency pre-check (common replay path; race is covered below) ---
        existing = _find_existing(session, request, idem)
        if existing is not None:
            if existing.payload_fingerprint == fingerprint:
                return _receipt_from_existing(
                    existing, idem, IntakeNoteWriteOutcome.IDEMPOTENT_REPLAY)
            return _deny("idempotency_conflict",
                         "idempotency key reused with a different payload/identity",
                         database_connection_made=True, sql_execution_made=True,
                         existing_record_returned=False)

        # --- Insert exactly one authorized row ---
        record = _build_record(request, draft, fingerprint)
        session.add(record)
        attempted_commit = True
        try:
            session.commit()
        except IntegrityError:
            # Uniqueness race: re-query INLINE (not via _find_existing) so a race is still
            # classifiable even if the pre-check helper missed it.
            session.rollback()
            raced = (
                session.query(IntakeNoteRecord)
                .filter_by(
                    owner_id=request.owner_id,
                    client_id=request.client_id,
                    engagement_id=request.engagement_id,
                    idempotency_key=idem,
                )
                .one_or_none()
            )
            if raced is not None and raced.payload_fingerprint == fingerprint:
                return _receipt_from_existing(
                    raced, idem, IntakeNoteWriteOutcome.IDEMPOTENT_REPLAY)
            if raced is not None:
                return _deny("idempotency_conflict",
                             "idempotency key reused with a different payload/identity (race)",
                             database_connection_made=True, sql_execution_made=True,
                             existing_record_returned=False)
            return IntakeNoteWriteReceipt(
                outcome=IntakeNoteWriteOutcome.WRITE_OUTCOME_UNCERTAIN, permitted=True,
                reason_code="integrity_no_row", idempotency_key=idem,
                database_connection_made=True, sql_execution_made=True,
                database_write_made=False, stored_record_created=False,
                transaction_committed=False, outcome_uncertain=True,
                reasons=["integrity conflict without a matching row; write outcome uncertain"])

        session.refresh(record)  # load server-stamped created_at/updated_at
        created_iso = record.created_at.isoformat() if record.created_at else None
        return IntakeNoteWriteReceipt(
            outcome=IntakeNoteWriteOutcome.CREATED, permitted=True, reason_code="created",
            stored_record_id=record.id, idempotency_key=idem, audit_trace_ref=record.id,
            database_connection_made=True, sql_execution_made=True,
            database_write_made=True, stored_record_created=True,
            existing_record_returned=False, transaction_committed=True, outcome_uncertain=False,
            note_type=record.note_type, note_source=record.note_source,
            review_status=record.review_status, lifecycle_status=record.lifecycle_status,
            created_at=created_iso, database_write_at=created_iso,
            reasons=["created one review-gated, non-final intake_note_records row"])

    except SQLAlchemyError as exc:  # infrastructure failure
        try:
            session.rollback()
        except Exception:  # noqa: BLE001 - rollback best-effort; never re-raise here
            pass
        safe = type(exc).__name__  # never leak SQL / connection / note content details
        if attempted_commit:
            return IntakeNoteWriteReceipt(
                outcome=IntakeNoteWriteOutcome.WRITE_OUTCOME_UNCERTAIN, permitted=True,
                reason_code="commit_uncertain", idempotency_key=idem,
                database_connection_made=True, sql_execution_made=True,
                database_write_made=False, stored_record_created=False,
                transaction_committed=False, outcome_uncertain=True,
                reasons=[f"commit outcome could not be confirmed ({safe}); a record may or "
                         "may not exist"])
        return IntakeNoteWriteReceipt(
            outcome=IntakeNoteWriteOutcome.FAILED_BEFORE_WRITE, permitted=True,
            reason_code="failed_before_write", idempotency_key=idem,
            database_connection_made=True, sql_execution_made=True,
            database_write_made=False, stored_record_created=False,
            transaction_committed=False, outcome_uncertain=False,
            reasons=[f"infrastructure failure before any write ({safe}); no row created"])
    finally:
        session.close()
