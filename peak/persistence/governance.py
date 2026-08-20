"""Deterministic controlled-write guards for the Controlled DB Writer Boundary (Phase 17).

Run *before* any write plan or audit draft is built. These checks enforce that a controlled
write request is authorized and scoped, targets an **allowlisted** table/action, and never
plans a prohibited effect (publish, client-facing approval, financial verification, delete,
migration, seed, credential/secret handling, raw SQL). Planning stays **DB-aware but not
DB-writing**: nothing here connects to a database or performs a write.

**Critical scope rule:** the request's ``authorization_scope`` must equal the subject
record's **stored** ``authorization_scope`` (``subject.stored_authorization_scope``).
Owner/client/engagement matching is necessary but **not sufficient**; the request scope
alone is insufficient. A future controlled writer must load the stored scope from the
controlled DB.

This module is **stdlib-only** and imports no SQLAlchemy, Alembic, or ``peak.db`` module.
Governance vocabulary mirrors the Phase 9 contracts (peak/db/enums.py and
schemas/*.schema.json are the source of truth); the blocking sets are local literals.
"""

from __future__ import annotations

import re
from dataclasses import dataclass, field
from typing import List

from .allowlist import (
    ANCHOR_CREATION_ACTION,
    ANCHOR_CREATION_TABLE,
    is_allowed_action,
    is_allowed_anchor_creation_pair,
    is_allowed_table,
    is_never_writable_table,
    is_prohibited_action,
    is_prohibited_table,
)
from .contracts import ControlledWriteDecision, ControlledWriteRequest

REVOKED_AUTHORIZATION_SCOPE = "revoked"
BLOCKED_LIFECYCLE_STATUSES = frozenset({"revoked", "archived", "deleted_reference_only"})
FIXTURE_TEST_SCOPE = "fixture_test"

# --- Phase 54: anchor-creation gate constants ------------------------------------------------
#: Lifecycle values an authorization anchor may be *created* with. `superseded` is excluded along
#: with the blocked set: a brand-new anchor cannot already have been replaced.
ALLOWED_ANCHOR_INITIAL_LIFECYCLE = frozenset({"active", "pending", "draft"})
#: Engagement domain-status values an anchor may be created with. An authorization anchor is
#: created at the *start* of an engagement, so finished states are not valid initial values.
ALLOWED_ANCHOR_INITIAL_STATUS = frozenset({"prospective", "active"})
# --- Phase 56: engagement classification -----------------------------------------------------
#: The closed engagement-category vocabulary (mirrors ``peak.db.enums.EngagementCategory``; kept
#: as literals so this stdlib-only module never imports ``peak.db``).
ENGAGEMENT_CATEGORY_REAL_CLIENT = "real_client"
ENGAGEMENT_CATEGORY_INTERNAL_TEST = "internal_test"
ALLOWED_ENGAGEMENT_CATEGORIES = frozenset(
    {ENGAGEMENT_CATEGORY_REAL_CLIENT, ENGAGEMENT_CATEGORY_INTERNAL_TEST}
)

#: A reserved namespace makes an internal test record *visible* at a glance. It is deliberately
#: **one marker among several**, never the control by itself: an internal test engagement must
#: also be explicitly categorised, hold no real client data, and be non-client-accessible. The
#: rule is bidirectional — a reserved value may only be used by an internal test engagement, and
#: a real client engagement may never use one, so the two namespaces cannot bleed together.
RESERVED_INTERNAL_TEST_CLIENT_IDS = frozenset({"99999"})
RESERVED_INTERNAL_TEST_CLIENT_PREFIXES = ("99999_", "internal_test_")


def is_reserved_internal_test_client_id(client_id) -> bool:
    """True if ``client_id`` is in the reserved internal-test namespace."""
    if not isinstance(client_id, str):
        return False
    value = client_id.strip()
    return (value in RESERVED_INTERNAL_TEST_CLIENT_IDS
            or value.startswith(RESERVED_INTERNAL_TEST_CLIENT_PREFIXES))


def validate_engagement_classification(
    category, real_client_data, client_accessible, capsule_publication_authorized, client_id,
) -> List[str]:
    """Return the reasons this classification is not permitted (empty list == permitted).

    Encodes the Phase 55 policy as checkable rules:

    * the category must be one of the two closed values;
    * an **internal test** engagement must hold no real client data, must not be
      client-accessible, and must use the reserved client namespace;
    * a **real client** engagement must *not* use the reserved namespace, and must not claim
      capsule publication authority — no real-client publication authority is designed yet;
    * capsule publication may be authorised only when there is no real client data **and** the
      engagement is not client-accessible — the compound rule, checked together.
    """
    reasons: List[str] = []

    if category not in ALLOWED_ENGAGEMENT_CATEGORIES:
        reasons.append(
            f"engagement_category must be one of {sorted(ALLOWED_ENGAGEMENT_CATEGORIES)}"
        )
        return reasons

    for name, value in (("real_client_data", real_client_data),
                        ("client_accessible", client_accessible),
                        ("capsule_publication_authorized", capsule_publication_authorized)):
        if not isinstance(value, bool):
            reasons.append(f"{name} must be a boolean")
    if reasons:
        return reasons

    reserved = is_reserved_internal_test_client_id(client_id)

    if category == ENGAGEMENT_CATEGORY_INTERNAL_TEST:
        if real_client_data:
            reasons.append("internal_test requires real_client_data=false")
        if client_accessible:
            reasons.append("internal_test requires client_accessible=false")
        if not reserved:
            reasons.append(
                "internal_test requires a reserved internal-test client_id namespace "
                "(the reserved value is a visible marker, not the only control)"
            )
    else:  # real_client
        if reserved:
            reasons.append(
                "a real_client engagement must not use the reserved internal-test client_id "
                "namespace"
            )
        if capsule_publication_authorized:
            reasons.append(
                "real_client engagements may not authorise capsule publication here; no "
                "real-client publication authority is designed yet"
            )

    # Compound publication rule — both conditions, checked together, for every category.
    if capsule_publication_authorized and (real_client_data or client_accessible):
        reasons.append(
            "capsule_publication_authorized requires real_client_data=false and "
            "client_accessible=false"
        )

    return reasons


#: Governed identifier shape shared by the anchor's identity fields.
_GOVERNED_ID_RE = re.compile(r"^[A-Za-z0-9_.:/-]+$")
#: Column-width bounds for the anchor's governed fields (mirrors peak/db/models.py).
ANCHOR_FIELD_BOUNDS = {
    "owner_id": 128,
    "client_id": 64,
    "engagement_id": 64,
    "authorization_scope": 48,
    "requested_by": 128,
    "requester_role": 64,
    "idempotency_key": 128,
}


@dataclass
class ControlledWriteGovernanceDecision:
    """Result of the pre-write governance checks."""

    permitted: bool = False
    reasons: List[str] = field(default_factory=list)
    warnings: List[str] = field(default_factory=list)


def _is_blank(value) -> bool:
    return value is None or (isinstance(value, str) and not value.strip())


def validate_write_subject_scope(
    request: ControlledWriteRequest,
) -> ControlledWriteGovernanceDecision:
    """Compare request scope AND identity against the subject's stored snapshot.

    Owner/client/engagement must match (necessary), and
    ``request.authorization_scope == subject.stored_authorization_scope`` (the sufficient
    scope check). Matching identity alone is **not** sufficient.
    """
    reasons: list = []
    subject = getattr(request, "subject", None)
    if subject is None:
        return ControlledWriteGovernanceDecision(permitted=False, reasons=["subject is required"])

    # Identity matching — necessary but not sufficient.
    for attr in ("owner_id", "client_id", "engagement_id"):
        req_val = getattr(request, attr, None)
        sub_val = getattr(subject, attr, None)
        if not _is_blank(req_val) and not _is_blank(sub_val) and req_val != sub_val:
            reasons.append(
                f"subject {attr} '{sub_val}' does not match request {attr} '{req_val}'"
            )

    # Stored-scope matching — the sufficient scope gate.
    req_scope = getattr(request, "authorization_scope", None)
    stored_scope = getattr(subject, "stored_authorization_scope", None)
    if _is_blank(stored_scope):
        reasons.append(
            "subject.stored_authorization_scope is required; a future controlled writer must "
            "load the subject's stored scope, not rely only on the request scope"
        )
    elif req_scope != stored_scope:
        reasons.append(
            f"request.authorization_scope '{req_scope}' does not match "
            f"subject.stored_authorization_scope '{stored_scope}' "
            "(owner/client/engagement matching is necessary but not sufficient)"
        )

    return ControlledWriteGovernanceDecision(permitted=not reasons, reasons=reasons)


def validate_table_action_allowlist(
    request: ControlledWriteRequest,
) -> ControlledWriteGovernanceDecision:
    """The target table and requested action must be explicitly allowlisted, not prohibited."""
    reasons: list = []
    table = getattr(request, "target_table", None)
    action = getattr(request, "requested_action", None)

    if _is_blank(table):
        reasons.append("target_table is required")
    elif is_prohibited_table(table):
        reasons.append(
            f"target_table '{table}' is prohibited "
            "(clients/engagements and financial/resolver tables are excluded from this "
            "early writer boundary until an explicit governance gate exists)"
        )
    elif not is_allowed_table(table):
        reasons.append(f"target_table '{table}' is not on the controlled-write allowlist")

    if _is_blank(action):
        reasons.append("requested_action is required")
    elif is_prohibited_action(action):
        reasons.append(
            f"requested_action '{action}' is prohibited "
            "(publish / client_facing_approve / verify_financial / delete / credential / "
            "secret / seed / migrate / raw_sql are never planned here)"
        )
    elif not is_allowed_action(action):
        reasons.append(f"requested_action '{action}' is not on the controlled-write allowlist")

    return ControlledWriteGovernanceDecision(permitted=not reasons, reasons=reasons)


def evaluate_controlled_write_request(
    request: ControlledWriteRequest,
) -> ControlledWriteGovernanceDecision:
    """Return a governance decision for a controlled write request (no side effects)."""
    reasons: list = []
    warnings: list = []

    # 1. Required identity / authorization / routing fields.
    for attr in (
        "owner_id",
        "client_id",
        "engagement_id",
        "requested_by",
        "requester_role",
        "authorization_scope",
        "target_table",
        "requested_action",
    ):
        if _is_blank(getattr(request, attr, None)):
            reasons.append(f"{attr} is required")

    # 2. idempotency_key is required for future write safety (dedupe / replay protection).
    if _is_blank(getattr(request, "idempotency_key", None)):
        reasons.append("idempotency_key is required for future write safety")

    # 3. authorization_scope must not be revoked.
    auth = getattr(request, "authorization_scope", None)
    if auth == REVOKED_AUTHORIZATION_SCOPE:
        reasons.append("authorization_scope 'revoked' is not permitted")

    # 4. record_draft must be present (the thing a future writer would persist).
    if getattr(request, "record_draft", None) is None:
        reasons.append("record_draft is required")

    # 5. request lifecycle_status must not be revoked/archived/deleted.
    lifecycle = getattr(request, "lifecycle_status", None)
    if lifecycle in BLOCKED_LIFECYCLE_STATUSES:
        reasons.append(
            f"lifecycle_status '{lifecycle}' is not permitted "
            "(must not be revoked, archived, or deleted_reference_only)"
        )

    # 6. subject required; its stored lifecycle must not be revoked/archived/deleted.
    subject = getattr(request, "subject", None)
    if subject is None:
        reasons.append("subject is required")
    else:
        stored_lifecycle = getattr(subject, "stored_lifecycle_status", None)
        if stored_lifecycle in BLOCKED_LIFECYCLE_STATUSES:
            reasons.append(
                f"subject.stored_lifecycle_status '{stored_lifecycle}' is not permitted "
                "(must not be revoked, archived, or deleted_reference_only)"
            )
        # 7. Subject identity + STORED scope comparison (necessary + sufficient).
        scope_check = validate_write_subject_scope(request)
        reasons.extend(scope_check.reasons)

    # 8. Table/action allowlist enforcement.
    allowlist_check = validate_table_action_allowlist(request)
    reasons.extend(allowlist_check.reasons)

    # 9. fixture_test scope must not be mixed with live client/engagement scope.
    scopes = {auth}
    if subject is not None:
        scopes.add(getattr(subject, "stored_authorization_scope", None))
    has_live_ref = not _is_blank(getattr(request, "client_id", None)) or not _is_blank(
        getattr(request, "engagement_id", None)
    )
    if FIXTURE_TEST_SCOPE in scopes and has_live_ref:
        reasons.append("fixture_test scope must not be mixed with live client/engagement scope")

    return ControlledWriteGovernanceDecision(
        permitted=not reasons, reasons=reasons, warnings=warnings
    )


def evaluate_engagement_anchor_creation_request(
    request: ControlledWriteRequest,
) -> ControlledWriteGovernanceDecision:
    """Governance gate for creating an engagement **authorization anchor** (Phase 54).

    This is a separate path from :func:`evaluate_controlled_write_request`, not a relaxation of
    it. The generic path's decisive check is that the request scope equals the *stored* subject's
    scope — which cannot apply here, because the anchor being created *is* the stored subject.
    Asking for that check would be circular, and faking a subject to satisfy it would hollow out
    the invariant everywhere else.

    So the stored-subject check is not weakened; it is **replaced** by a set of gates that are
    strictly checkable without a prior row:

    1. the exact single (table, action) anchor pair — never a table-wide or action-wide grant;
    2. ``subject`` must be absent, so this path can never be confused with, or used to smuggle a
       request through, the subject-bearing generic path;
    3. every governed identity field present, non-blank, governed-charset, and within its column
       bound — an anchor with a malformed identifier would poison every later scope comparison;
    4. an explicit, non-revoked ``authorization_scope`` — the value every later writer matches on;
    5. an allowed *initial* lifecycle and engagement status only;
    6. an idempotency key, for replay safety;
    7. a record draft to persist;
    8. no ``fixture_test`` scope mixed with live client/engagement identity.

    Returns a decision; performs no I/O, opens no connection, and writes nothing.
    """
    reasons: list = []
    warnings: list = []

    table = getattr(request, "target_table", None)
    action = getattr(request, "requested_action", None)

    # 1. Exact anchor pair. Checked pair-wise so neither half alone opens anything.
    if _is_blank(table):
        reasons.append("target_table is required")
    elif is_never_writable_table(table):
        reasons.append(f"target_table '{table}' may never be written through any controlled path")
    if _is_blank(action):
        reasons.append("requested_action is required")
    elif is_prohibited_action(action):
        reasons.append(f"requested_action '{action}' is prohibited")
    if not _is_blank(table) and not _is_blank(action):
        if not is_allowed_anchor_creation_pair(table, action):
            reasons.append(
                f"({table}, {action}) is not the permitted anchor-creation pair "
                f"({ANCHOR_CREATION_TABLE}, {ANCHOR_CREATION_ACTION}); this path grants exactly "
                "one pair and never generic writes to a root/identity table"
            )

    # 2. No stored subject on this path, by construction.
    if getattr(request, "subject", None) is not None:
        reasons.append(
            "subject must be omitted on the anchor-creation path (the anchor being created is "
            "itself the stored subject; a subject here indicates the generic path was intended)"
        )

    # 3. Governed identity/traceability fields: present, governed-charset, within bounds.
    for attr in ("owner_id", "client_id", "engagement_id", "requested_by", "requester_role",
                 "authorization_scope", "idempotency_key"):
        value = getattr(request, attr, None)
        if _is_blank(value):
            reasons.append(f"{attr} is required")
            continue
        if not isinstance(value, str):
            reasons.append(f"{attr} must be a string")
            continue
        bound = ANCHOR_FIELD_BOUNDS.get(attr)
        if bound is not None and len(value) > bound:
            reasons.append(f"{attr} exceeds its {bound}-character bound")
        if attr in ("owner_id", "client_id", "engagement_id", "authorization_scope") \
                and not _GOVERNED_ID_RE.match(value):
            reasons.append(f"{attr} is not a governed identifier")

    # 4. authorization_scope must not be revoked.
    auth = getattr(request, "authorization_scope", None)
    if auth == REVOKED_AUTHORIZATION_SCOPE:
        reasons.append("authorization_scope 'revoked' is not permitted")

    # 5. Allowed initial lifecycle only.
    lifecycle = getattr(request, "lifecycle_status", None)
    if _is_blank(lifecycle):
        reasons.append("lifecycle_status is required for an anchor")
    elif lifecycle in BLOCKED_LIFECYCLE_STATUSES:
        reasons.append(
            f"lifecycle_status '{lifecycle}' is not permitted "
            "(must not be revoked, archived, or deleted_reference_only)"
        )
    elif lifecycle not in ALLOWED_ANCHOR_INITIAL_LIFECYCLE:
        reasons.append(
            f"lifecycle_status '{lifecycle}' is not an allowed initial anchor lifecycle "
            f"({sorted(ALLOWED_ANCHOR_INITIAL_LIFECYCLE)})"
        )

    # 6. record_draft must be present.
    if getattr(request, "record_draft", None) is None:
        reasons.append("record_draft is required")

    # 7. fixture_test scope must not be mixed with live client/engagement identity.
    has_live_ref = not _is_blank(getattr(request, "client_id", None)) or not _is_blank(
        getattr(request, "engagement_id", None)
    )
    if auth == FIXTURE_TEST_SCOPE and has_live_ref:
        reasons.append("fixture_test scope must not be mixed with live client/engagement scope")

    return ControlledWriteGovernanceDecision(
        permitted=not reasons, reasons=reasons, warnings=warnings
    )


def build_controlled_write_decision(request: ControlledWriteRequest) -> ControlledWriteDecision:
    """Evaluate the request and return a ``ControlledWriteDecision`` (no side effects)."""
    governance = evaluate_controlled_write_request(request)
    return ControlledWriteDecision(
        permitted=governance.permitted,
        target_table=getattr(request, "target_table", None),
        requested_action=getattr(request, "requested_action", None),
        reasons=list(governance.reasons),
        warnings=list(governance.warnings),
    )
