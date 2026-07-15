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

from dataclasses import dataclass, field
from typing import List

from .allowlist import (
    is_allowed_action,
    is_allowed_table,
    is_prohibited_action,
    is_prohibited_table,
)
from .contracts import ControlledWriteDecision, ControlledWriteRequest

REVOKED_AUTHORIZATION_SCOPE = "revoked"
BLOCKED_LIFECYCLE_STATUSES = frozenset({"revoked", "archived", "deleted_reference_only"})
FIXTURE_TEST_SCOPE = "fixture_test"


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
