"""Phase 54 — the controlled DB writer for engagement **authorization anchors**.

The twelfth narrow live DB writer in Peak, and the only one that targets a root/identity table.
It accepts a controlled request whose ``record_draft`` is an
:class:`EngagementAuthorizationAnchorDraft` and creates **exactly one** ``engagements`` row —
nothing else. It is a narrow internal persistence boundary, not a generic decision engine, review
engine, workflow engine, CRUD repository, or arbitrary SQL executor.

**Why this writer has to exist.** Every other controlled writer loads the stored ``Engagement``
row at write time and requires ``request.authorization_scope == engagement.authorization_scope``.
That makes the anchor the thing all governed writes descend from — and until Phase 54 nothing in
Peak could create one, because ``engagements`` sits on ``PROHIBITED_TABLES``. Phase 53 recorded
that as the operational blocker. This writer is the governed code path that resolves it.

**Why the fix is a second gate, not a hole in the first.** ``engagements`` **stays** on
``PROHIBITED_TABLES``, so the generic Phase 17 path still refuses it and generic Engagement CRUD
remains impossible. This writer travels a separate one-pair gate,
``ALLOWED_ANCHOR_CREATION_PAIRS`` — exactly ``(engagements,
create_engagement_authorization_anchor)``. ``clients`` is unreachable by either path.

**The stored-subject check is replaced, not weakened.** The generic path's decisive gate compares
the request scope to the *stored* subject's scope. Here the row being created *is* that subject,
so the check would be circular, and manufacturing a subject to satisfy it would hollow out the
invariant everywhere else. Instead
:func:`peak.persistence.governance.evaluate_engagement_anchor_creation_request` imposes gates that
are checkable without a prior row: the exact pair, an absent subject, governed and bounded
identity, an explicit non-revoked scope, an allowed *initial* lifecycle and status, an idempotency
key, and a record draft. The writer then re-enforces each of them at its own boundary.

**Idempotency without new columns.** ``engagements`` has no ``idempotency_key`` /
``payload_fingerprint`` column, and Phase 54 adds no migration. It does not need them: the
anchor's primary key *is* its identity, so the caller-supplied ``engagement_id`` is the
idempotency boundary, and the fingerprint is recomputed from the **stored row's own governed
fields** on replay rather than from a stored hash. Same anchor, same definition → idempotent
replay with no second write. Same anchor id, different definition → a denial, never a silent
overwrite.

**Create-only.** One ``session.add``, one commit. No ``UPDATE``, no ``DELETE``, no ``merge``, no
bulk operation, no raw SQL, no schema operation. Runtime ``SELECT`` + ``INSERT`` is sufficient and
is all this path uses. It never executes an agent (live or mock), never calls an LLM / AgentNet /
MCP / resolver / connector / network, writes no table other than ``engagements``, never creates or
touches a ``Client`` row, and produces no client-facing output, financial verification, or capsule
publication.

**Receipt hygiene.** Receipts and denial reasons carry no credentials, DSN, host, user, database
name, SQL string, stack trace, or raw payload — and never the ``engagement_label``, since a label
can carry a client organisation name. Only governed identifiers, safe status labels, and marker
*categories* are ever reported.

Side-effect boundary: this module performs only the DB work needed to check for an existing
anchor, insert the authorized row, read it back, and commit/roll back. It may import SQLAlchemy
and ``peak.db`` (this is the DB layer). **SQLite is only the fast local structural-smoke path —
not the production-readiness proof path**; managed MySQL test/staging validation is required
before treating this writer as production-ready (see docs/PRODUCTION_PARITY_DB_VALIDATION.md and
docs/MANAGED_MYSQL_PERSISTENCE_RUBRIC.md).

**No production anchor has been created.** Phase 54 adds the code path only; the Phase 51 no-write
/ no-enablement decision stands, and the first production anchor remains separately approved
future work. See docs/PHASE54_CONTROLLED_ENGAGEMENT_AUTHORIZATION_ANCHOR_WRITER.md.
"""

from __future__ import annotations

import hashlib
import json
from typing import Optional, Tuple

from sqlalchemy.exc import IntegrityError, SQLAlchemyError

from peak.persistence.allowlist import is_allowed_anchor_creation_pair
from peak.persistence.contracts import ControlledWriteRequest
from peak.persistence.governance import (
    ALLOWED_ANCHOR_INITIAL_LIFECYCLE,
    ALLOWED_ANCHOR_INITIAL_STATUS,
    ENGAGEMENT_CATEGORY_INTERNAL_TEST,
    evaluate_engagement_anchor_creation_request,
    validate_engagement_classification,
)
# Reuse the public, DB-free Phase 32 value classifier for the short label/scope fields.
from peak.reviewer_decisions.governance import classify_prohibited_value_marker

from .enums import AuthorizationScope
from .models import Engagement
from .session import create_session_factory
from .writer_contracts import (
    ENGAGEMENT_ANCHOR_TARGET_ACTION,
    ENGAGEMENT_ANCHOR_TARGET_TABLE,
    EngagementAuthorizationAnchorDraft,
    EngagementAuthorizationAnchorWriteOutcome,
    EngagementAuthorizationAnchorWriteReceipt,
)

REQUIRED_REVIEW_STATUS = "needs_review"

# Bounds (documented in docs/PHASE54_CONTROLLED_ENGAGEMENT_AUTHORIZATION_ANCHOR_WRITER.md).
MAX_LABEL_LEN = 255
MAX_STATUS_LEN = 32
MAX_IDEM_LEN = 128

#: The scope values an anchor may carry. Restricting to the canonical enum matters more here than
#: elsewhere: a typo'd scope on the anchor would silently fail to match every later writer's
#: request scope, producing an anchor nothing can ever be written under.
_VALID_SCOPES = frozenset(m.value for m in AuthorizationScope)
_REVOKED_SCOPE = AuthorizationScope.revoked.value


def _is_blank(value) -> bool:
    return value is None or (isinstance(value, str) and not value.strip())


def _deny(reason_code: str, message: str, **flags) -> EngagementAuthorizationAnchorWriteReceipt:
    receipt = EngagementAuthorizationAnchorWriteReceipt(
        outcome=EngagementAuthorizationAnchorWriteOutcome.DENIED,
        permitted=False,
        reason_code=reason_code,
        reasons=[message],
    )
    for key, val in flags.items():
        setattr(receipt, key, val)
    return receipt


def _anchor_fingerprint(
    owner_id, client_id, engagement_id, authorization_scope, engagement_label, status,
    review_status, lifecycle_status, engagement_category, real_client_data, client_accessible,
    capsule_publication_authorized,
) -> str:
    """Deterministic fingerprint of an anchor's governed definition.

    Computed from the same field set whether the values come from a request or from a stored row,
    which is what lets a replay be classified without any stored-hash column.
    """
    payload = {
        "owner_id": owner_id,
        "client_id": client_id,
        "engagement_id": engagement_id,
        "authorization_scope": authorization_scope,
        "engagement_label": engagement_label,
        "status": status,
        "review_status": review_status,
        "lifecycle_status": lifecycle_status,
        "engagement_category": engagement_category,
        "real_client_data": bool(real_client_data),
        "client_accessible": bool(client_accessible),
        "capsule_publication_authorized": bool(capsule_publication_authorized),
    }
    blob = json.dumps(payload, sort_keys=True, separators=(",", ":"), default=str)
    return hashlib.sha256(blob.encode("utf-8")).hexdigest()


def _fingerprint_from_request(
    request: ControlledWriteRequest, draft: EngagementAuthorizationAnchorDraft
) -> str:
    return _anchor_fingerprint(
        request.owner_id, request.client_id, request.engagement_id,
        request.authorization_scope, draft.engagement_label, draft.status,
        REQUIRED_REVIEW_STATUS, request.lifecycle_status,
        draft.engagement_category, draft.real_client_data, draft.client_accessible,
        draft.capsule_publication_authorized,
    )


def _fingerprint_from_stored(row: Engagement) -> str:
    return _anchor_fingerprint(
        row.owner_id, row.client_id, row.id, row.authorization_scope,
        row.engagement_label, row.status, row.review_status, row.lifecycle_status,
        row.engagement_category, row.real_client_data, row.client_accessible,
        row.capsule_publication_authorized,
    )


def _pre_db_validate(
    request,
) -> Tuple[Optional[EngagementAuthorizationAnchorWriteReceipt],
           Optional[EngagementAuthorizationAnchorDraft]]:
    """All governance checks that must pass *before* any DB connection is opened.

    Returns ``(denial_receipt, None)`` on failure or ``(None, draft)`` on success. A denial here
    honestly reports ``database_connection_made = False`` and ``sql_execution_made = False``.
    """
    # 1. Concrete request type (reject duck-typed objects at the boundary).
    if not isinstance(request, ControlledWriteRequest):
        return _deny("invalid_request_type",
                     "controlled write request is not a ControlledWriteRequest"), None

    # 2. Exact anchor-creation pair, checked directly and pair-wise.
    if getattr(request, "target_table", None) != ENGAGEMENT_ANCHOR_TARGET_TABLE:
        return _deny("wrong_target_table",
                     f"target_table must be '{ENGAGEMENT_ANCHOR_TARGET_TABLE}'"), None
    if getattr(request, "requested_action", None) != ENGAGEMENT_ANCHOR_TARGET_ACTION:
        return _deny("wrong_target_action",
                     f"requested_action must be '{ENGAGEMENT_ANCHOR_TARGET_ACTION}'"), None
    if not is_allowed_anchor_creation_pair(request.target_table, request.requested_action):
        return _deny("pair_not_allowed",
                     "target_table/requested_action is not the permitted anchor-creation "
                     "pair"), None

    # 3. Independently revalidate through the Phase 54 governance gate (defense in depth).
    governance = evaluate_engagement_anchor_creation_request(request)
    if not governance.permitted:
        return _deny("anchor_governance_not_permitted",
                     "anchor-creation governance did not permit this request",
                     reasons=list(governance.reasons)
                     or ["anchor-creation governance did not permit this request"]), None

    # 4. record_draft must be a concrete anchor draft.
    draft = getattr(request, "record_draft", None)
    if not isinstance(draft, EngagementAuthorizationAnchorDraft):
        return _deny("invalid_record_draft",
                     "record_draft is not an EngagementAuthorizationAnchorDraft"), None

    # 5. Draft identity must agree with the request identity.
    for attr in ("owner_id", "client_id", "engagement_id", "authorization_scope"):
        if getattr(draft, attr, None) != getattr(request, attr, None):
            return _deny("identity_mismatch",
                         f"draft.{attr} does not match request.{attr}"), None

    # 6. authorization_scope must be a canonical, non-revoked scope value.
    scope = request.authorization_scope
    if scope not in _VALID_SCOPES:
        return _deny("invalid_authorization_scope",
                     "authorization_scope is not a recognised governance scope value"), None
    if scope == _REVOKED_SCOPE:
        return _deny("invalid_authorization_scope",
                     "authorization_scope 'revoked' is not permitted"), None

    # 7. Allowed initial lifecycle / engagement status only.
    if request.lifecycle_status not in ALLOWED_ANCHOR_INITIAL_LIFECYCLE:
        return _deny("invalid_initial_lifecycle",
                     "lifecycle_status is not an allowed initial anchor lifecycle"), None
    if getattr(draft, "status", None) not in ALLOWED_ANCHOR_INITIAL_STATUS:
        return _deny("invalid_initial_status",
                     "draft.status is not an allowed initial engagement status"), None

    # 8. Review posture is server-stamped; a caller must not try to pre-advance it.
    if getattr(draft, "review_status", None) != REQUIRED_REVIEW_STATUS:
        return _deny("invalid_draft_review_status",
                     f"draft.review_status must be '{REQUIRED_REVIEW_STATUS}'"), None
    if getattr(draft, "lifecycle_status", None) != request.lifecycle_status:
        return _deny("identity_mismatch",
                     "draft.lifecycle_status does not match request.lifecycle_status"), None

    # 9. Idempotency key present and bounded.
    idem = getattr(request, "idempotency_key", None)
    if _is_blank(idem):
        return _deny("invalid_idempotency_key", "idempotency_key is required"), None
    if not isinstance(idem, str) or len(idem) > MAX_IDEM_LEN:
        return _deny("invalid_idempotency_key",
                     f"idempotency_key must be a string of at most {MAX_IDEM_LEN} "
                     "characters"), None

    # 10. Short free-text fields must not carry credential/DSN/SQL/raw-content markers. Only the
    #     marker *category* is reported — never the offending value.
    label = getattr(draft, "engagement_label", None)
    if label is not None:
        if not isinstance(label, str) or len(label) > MAX_LABEL_LEN:
            return _deny("invalid_engagement_label",
                         f"engagement_label must be a string of at most {MAX_LABEL_LEN} "
                         "characters"), None
        marker = classify_prohibited_value_marker(label)
        if marker is not None:
            return _deny("prohibited_value_marker",
                         f"engagement_label carries a prohibited value marker ({marker})"), None
    if len(draft.status) > MAX_STATUS_LEN:
        return _deny("invalid_initial_status", "draft.status exceeds its bound"), None

    # 11. Phase 56 classification. An internal test engagement must be explicitly categorised,
    #     hold no real client data, be non-client-accessible, and use the reserved client
    #     namespace; a real client engagement must not use that namespace. The reserved value is
    #     a visible marker, never the only control.
    class_reasons = validate_engagement_classification(
        getattr(draft, "engagement_category", None),
        getattr(draft, "real_client_data", None),
        getattr(draft, "client_accessible", None),
        getattr(draft, "capsule_publication_authorized", None),
        request.client_id,
    )
    if class_reasons:
        return _deny("invalid_classification",
                     "engagement classification is not permitted",
                     reasons=class_reasons), None

    return None, draft


def _build_record(request: ControlledWriteRequest,
                  draft: EngagementAuthorizationAnchorDraft) -> Engagement:
    """Explicit field mapping to governed + server-stamped columns (no ``__dict__`` splat)."""
    return Engagement(
        id=request.engagement_id,          # caller-supplied anchor id = idempotency boundary
        client_id=request.client_id,
        owner_id=request.owner_id,
        authorization_scope=request.authorization_scope,
        engagement_label=draft.engagement_label,
        status=draft.status,
        review_status=REQUIRED_REVIEW_STATUS,   # server-stamped
        lifecycle_status=request.lifecycle_status,
        engagement_category=draft.engagement_category,
        real_client_data=bool(draft.real_client_data),
        client_accessible=bool(draft.client_accessible),
        capsule_publication_authorized=bool(draft.capsule_publication_authorized),
        created_by=request.requested_by,
        # created_at / updated_at are DB server_default (server-stamped).
        details_json={
            "source_phase": getattr(request, "source_phase", None),
            "requester_role": request.requester_role,
            "idempotency_key": request.idempotency_key,
        },
    )


def _receipt_from_existing(existing: Engagement, idem: str, outcome: str
                           ) -> EngagementAuthorizationAnchorWriteReceipt:
    return EngagementAuthorizationAnchorWriteReceipt(
        outcome=outcome,
        permitted=True,
        reason_code=outcome,
        stored_record_id=existing.id,
        idempotency_key=idem,
        audit_trace_ref=existing.id,
        database_connection_made=True,
        sql_execution_made=True,
        database_write_made=False,
        stored_record_created=False,
        existing_record_returned=True,
        transaction_committed=False,
        authorization_scope=existing.authorization_scope,
        engagement_status=existing.status,
        review_status=existing.review_status,
        lifecycle_status=existing.lifecycle_status,
        engagement_category=existing.engagement_category,
        real_client_data=existing.real_client_data,
        client_accessible=existing.client_accessible,
        capsule_publication_authorized=existing.capsule_publication_authorized,
        reasons=["exact authorized replay; existing anchor returned, not modified"],
    )


def build_engagement_anchor_controlled_write_request(
    draft: EngagementAuthorizationAnchorDraft,
    *,
    requested_by: str,
    requester_role: str,
    idempotency_key: str,
    source_phase: str = "phase54",
) -> ControlledWriteRequest:
    """Convenience planner: wrap an anchor draft in a ControlledWriteRequest.

    Targets exactly ``engagements`` / ``create_engagement_authorization_anchor`` and opens no
    database connection; a caller passes the result to
    :func:`persist_engagement_authorization_anchor`. ``subject`` is deliberately left ``None`` —
    the anchor being created *is* the stored subject, and the governance gate refuses a request
    that carries one.
    """
    return ControlledWriteRequest(
        owner_id=draft.owner_id,
        client_id=draft.client_id,
        engagement_id=draft.engagement_id,
        requested_by=requested_by,
        requester_role=requester_role,
        authorization_scope=draft.authorization_scope,
        target_table=ENGAGEMENT_ANCHOR_TARGET_TABLE,
        requested_action=ENGAGEMENT_ANCHOR_TARGET_ACTION,
        subject=None,
        record_draft=draft,
        source_phase=source_phase,
        lifecycle_status=draft.lifecycle_status,
        idempotency_key=idempotency_key,
    )


def persist_engagement_authorization_anchor(
    controlled_write_request,
    *,
    session_factory=None,
) -> EngagementAuthorizationAnchorWriteReceipt:
    """Create exactly one ``engagements`` authorization anchor row for an approved request.

    ``session_factory`` is a zero-arg callable returning a SQLAlchemy ``Session`` (defaults to the
    controlled-DB session factory from the environment URL).

    Returns an :class:`EngagementAuthorizationAnchorWriteReceipt`; expected governance failures are
    typed denials, not exceptions. Unexpected infrastructure failures are converted into a safe
    structured ``failed_before_write`` / ``write_outcome_uncertain`` result where feasible.
    """
    # --- Pre-DB governance (no connection opened on denial) ---
    denial, draft = _pre_db_validate(controlled_write_request)
    if denial is not None:
        return denial

    request = controlled_write_request
    idem = request.idempotency_key
    fingerprint = _fingerprint_from_request(request, draft)

    factory = session_factory or create_session_factory()
    session = factory()
    attempted_commit = False
    try:
        # --- Idempotency pre-check on the anchor's own primary key (race covered below) ---
        existing = session.get(Engagement, request.engagement_id)
        if existing is not None:
            if _fingerprint_from_stored(existing) == fingerprint:
                return _receipt_from_existing(
                    existing, idem, EngagementAuthorizationAnchorWriteOutcome.IDEMPOTENT_REPLAY
                )
            return _deny("idempotency_conflict",
                         "an anchor already exists for this engagement_id with a different "
                         "governed definition; the existing anchor was not modified",
                         database_connection_made=True, sql_execution_made=True,
                         existing_record_returned=False)

        # --- Insert exactly one authorized anchor row ---
        record = _build_record(request, draft)
        session.add(record)
        attempted_commit = True
        try:
            session.commit()
        except IntegrityError:
            # Uniqueness race: another writer inserted between our check and commit.
            session.rollback()
            raced = session.get(Engagement, request.engagement_id)
            if raced is not None and _fingerprint_from_stored(raced) == fingerprint:
                return _receipt_from_existing(
                    raced, idem, EngagementAuthorizationAnchorWriteOutcome.IDEMPOTENT_REPLAY
                )
            if raced is not None:
                return _deny("idempotency_conflict",
                             "an anchor already exists for this engagement_id with a different "
                             "governed definition (race); it was not modified",
                             database_connection_made=True, sql_execution_made=True,
                             existing_record_returned=False)
            # Constraint violated but no matching row found — genuinely uncertain.
            return EngagementAuthorizationAnchorWriteReceipt(
                outcome=EngagementAuthorizationAnchorWriteOutcome.WRITE_OUTCOME_UNCERTAIN,
                permitted=True, reason_code="integrity_no_row", idempotency_key=idem,
                database_connection_made=True, sql_execution_made=True,
                database_write_made=False, stored_record_created=False,
                transaction_committed=False, outcome_uncertain=True,
                reasons=["integrity conflict without a matching row; write outcome uncertain"],
            )

        session.refresh(record)  # load server-stamped created_at/updated_at
        created_iso = record.created_at.isoformat() if record.created_at else None
        return EngagementAuthorizationAnchorWriteReceipt(
            outcome=EngagementAuthorizationAnchorWriteOutcome.CREATED,
            permitted=True,
            reason_code="created",
            stored_record_id=record.id,
            idempotency_key=idem,
            audit_trace_ref=record.id,
            database_connection_made=True,
            sql_execution_made=True,
            database_write_made=True,
            stored_record_created=True,
            existing_record_returned=False,
            transaction_committed=True,
            outcome_uncertain=False,
            authorization_scope=record.authorization_scope,
            engagement_status=record.status,
            review_status=record.review_status,
            lifecycle_status=record.lifecycle_status,
            engagement_category=record.engagement_category,
            real_client_data=record.real_client_data,
            client_accessible=record.client_accessible,
            capsule_publication_authorized=record.capsule_publication_authorized,
            created_at=created_iso,
            database_write_at=created_iso,
            reasons=["created one engagement authorization anchor row"],
        )

    except SQLAlchemyError as exc:  # infrastructure failure
        try:
            session.rollback()
        except Exception:  # noqa: BLE001 - rollback best-effort; never re-raise here
            pass
        safe = type(exc).__name__  # never leak SQL / connection details
        if attempted_commit:
            return EngagementAuthorizationAnchorWriteReceipt(
                outcome=EngagementAuthorizationAnchorWriteOutcome.WRITE_OUTCOME_UNCERTAIN,
                permitted=True, reason_code="commit_uncertain", idempotency_key=idem,
                database_connection_made=True, sql_execution_made=True,
                database_write_made=False, stored_record_created=False,
                transaction_committed=False, outcome_uncertain=True,
                reasons=[f"commit outcome could not be confirmed ({safe}); an anchor may or "
                         "may not exist"],
            )
        return EngagementAuthorizationAnchorWriteReceipt(
            outcome=EngagementAuthorizationAnchorWriteOutcome.FAILED_BEFORE_WRITE,
            permitted=True, reason_code="failed_before_write", idempotency_key=idem,
            database_connection_made=True, sql_execution_made=True,
            database_write_made=False, stored_record_created=False,
            transaction_committed=False, outcome_uncertain=False,
            reasons=[f"infrastructure failure before any write ({safe}); no anchor created"],
        )
    finally:
        session.close()
