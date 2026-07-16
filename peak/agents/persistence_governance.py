"""Deterministic guards for the Agent Run Persistence Mapping (Phase 19).

Run *before* any agent run persistence draft or controlled write plan is built. These checks
enforce that a mapping request is authorized and scoped, that the Phase 13 agent output it
carries was itself permitted and side-effect-free and stayed review-gated, and that mapping
stays **DB-aware but not DB-writing** — nothing may create client-facing output, verify
financial impact, or publish a capsule, and no plan is a real write.

**Critical scope rule:** the request's ``authorization_scope`` must equal the stored
engagement/client/subject's **stored** ``authorization_scope``
(``subject_snapshot.stored_authorization_scope``). Because a new agent run record has no
stored DB row yet, the stored subject is the authorization anchor. Owner/client/engagement
matching is necessary but **not sufficient**; the request scope alone is insufficient.

This module is **stdlib-only** and imports no SQLAlchemy, Alembic, or ``peak.db`` module.
Governance vocabulary mirrors the Phase 9 contracts (peak/db/enums.py and
schemas/*.schema.json are the source of truth); the blocking sets are local literals.

The Phase 13 ``AgentTaskResult`` has no ``network_call_made`` or ``capsule_publication_made``
field; those are **not** invented on the input. They are set ``False`` on the draft and the
mapping result.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import List

from .persistence_contracts import (
    ALLOWED_PERSISTENCE_ACTION,
    AgentRunPersistenceDecision,
    AgentRunPersistenceRequest,
    TARGET_ACTION,
    TARGET_TABLE,
)

REVOKED_AUTHORIZATION_SCOPE = "revoked"
BLOCKED_LIFECYCLE_STATUSES = frozenset({"revoked", "archived", "deleted_reference_only"})
FIXTURE_TEST_SCOPE = "fixture_test"

# AgentTaskResult flags that must be False before the output may be persistence-mapped.
# (Any True flag means the Phase 13 harness already had a side effect — refuse to map.)
# Only flags that actually exist on the Phase 13 AgentTaskResult are checked here.
TASK_RESULT_FORBIDDEN_TRUE_FLAGS = (
    "database_write_made",
    "llm_call_made",
    "agentnet_call_made",
    "client_facing_output_created",
)


@dataclass
class AgentRunPersistenceGovernanceDecision:
    """Result of the pre-mapping governance checks."""

    permitted: bool = False
    reasons: List[str] = field(default_factory=list)
    warnings: List[str] = field(default_factory=list)


def _is_blank(value) -> bool:
    return value is None or (isinstance(value, str) and not value.strip())


def _identity_mismatch(request, obj, label: str, reasons: list) -> None:
    """Append a reason for each owner/client/engagement field that is present but differs."""
    for attr in ("owner_id", "client_id", "engagement_id"):
        req_val = getattr(request, attr, None)
        obj_val = getattr(obj, attr, None)
        if not _is_blank(req_val) and not _is_blank(obj_val) and req_val != obj_val:
            reasons.append(f"{label} {attr} '{obj_val}' does not match request {attr} '{req_val}'")


def validate_agent_run_subject_scope(
    request: AgentRunPersistenceRequest,
) -> AgentRunPersistenceGovernanceDecision:
    """Compare request scope AND identity against the stored subject snapshot.

    Owner/client/engagement must match (necessary) the subject snapshot, the task request,
    and — where those fields exist — the run draft, and
    ``request.authorization_scope == subject_snapshot.stored_authorization_scope`` (the
    sufficient scope check). Matching identity alone is **not** sufficient.
    """
    reasons: list = []
    subject = getattr(request, "subject_snapshot", None)
    if subject is None:
        return AgentRunPersistenceGovernanceDecision(
            permitted=False, reasons=["subject_snapshot is required"]
        )

    # Identity matching — necessary but not sufficient.
    _identity_mismatch(request, subject, "subject_snapshot", reasons)
    task_request = getattr(request, "agent_task_request", None)
    if task_request is not None:
        _identity_mismatch(request, task_request, "agent_task_request", reasons)
    run_draft = getattr(request, "agent_run_draft", None)
    if run_draft is not None:
        _identity_mismatch(request, run_draft, "agent_run_draft", reasons)

    # Stored-scope matching — the sufficient scope gate.
    req_scope = getattr(request, "authorization_scope", None)
    stored_scope = getattr(subject, "stored_authorization_scope", None)
    if _is_blank(stored_scope):
        reasons.append(
            "subject_snapshot.stored_authorization_scope is required; a future controlled "
            "writer must load the stored subject's scope, not rely only on the request scope"
        )
    elif req_scope != stored_scope:
        reasons.append(
            f"request.authorization_scope '{req_scope}' does not match "
            f"subject_snapshot.stored_authorization_scope '{stored_scope}' "
            "(owner/client/engagement matching is necessary but not sufficient)"
        )

    return AgentRunPersistenceGovernanceDecision(permitted=not reasons, reasons=reasons)


def validate_agent_task_result_for_persistence(
    request: AgentRunPersistenceRequest,
) -> AgentRunPersistenceGovernanceDecision:
    """The Phase 13 output must be permitted, side-effect-free, and still review-gated."""
    reasons: list = []
    result = getattr(request, "agent_task_result", None)

    if result is None:
        reasons.append("agent_task_result is required")
    else:
        if getattr(result, "permitted", False) is not True:
            reasons.append("agent_task_result must be permitted=true before persistence mapping")
        for flag in TASK_RESULT_FORBIDDEN_TRUE_FLAGS:
            if getattr(result, flag, False) is True:
                reasons.append(
                    f"agent_task_result.{flag} must be false (no side effect may exist)"
                )
        # Review-gated posture must be intact — mapping never advances authority.
        if getattr(result, "output_status", None) != "draft":
            reasons.append("agent_task_result.output_status must be 'draft'")
        if getattr(result, "review_status", None) != "needs_review":
            reasons.append("agent_task_result.review_status must be 'needs_review'")

    return AgentRunPersistenceGovernanceDecision(permitted=not reasons, reasons=reasons)


def evaluate_agent_run_persistence_request(
    request: AgentRunPersistenceRequest,
) -> AgentRunPersistenceGovernanceDecision:
    """Return a governance decision for an agent run persistence request (no side effects)."""
    reasons: list = []
    warnings: list = []

    # 1. Required identity / authorization fields.
    for attr in (
        "owner_id",
        "client_id",
        "engagement_id",
        "requested_by",
        "requester_role",
        "authorization_scope",
    ):
        if _is_blank(getattr(request, attr, None)):
            reasons.append(f"{attr} is required")

    # 2. idempotency_key is required for future write safety.
    if _is_blank(getattr(request, "idempotency_key", None)):
        reasons.append("idempotency_key is required for future write safety")

    # 3. authorization_scope must not be revoked.
    auth = getattr(request, "authorization_scope", None)
    if auth == REVOKED_AUTHORIZATION_SCOPE:
        reasons.append("authorization_scope 'revoked' is not permitted")

    # 4. requested_persistence_action must be the one allowed action.
    action = getattr(request, "requested_persistence_action", None)
    if _is_blank(action):
        reasons.append("requested_persistence_action is required")
    elif action != ALLOWED_PERSISTENCE_ACTION:
        reasons.append(
            f"requested_persistence_action '{action}' is not '{ALLOWED_PERSISTENCE_ACTION}'"
        )

    # 5. The three Phase 13 inputs are all required.
    if getattr(request, "agent_task_request", None) is None:
        reasons.append("agent_task_request is required")
    if getattr(request, "agent_task_result", None) is None:
        reasons.append("agent_task_result is required")
    if getattr(request, "agent_run_draft", None) is None:
        reasons.append("agent_run_draft is required")

    # 6. request lifecycle_status must not be revoked/archived/deleted.
    lifecycle = getattr(request, "lifecycle_status", None)
    if lifecycle in BLOCKED_LIFECYCLE_STATUSES:
        reasons.append(
            f"lifecycle_status '{lifecycle}' is not permitted "
            "(must not be revoked, archived, or deleted_reference_only)"
        )

    # 7. subject_snapshot required; its stored lifecycle must not be revoked/archived/deleted.
    subject = getattr(request, "subject_snapshot", None)
    if subject is None:
        reasons.append("subject_snapshot is required")
    else:
        stored_lifecycle = getattr(subject, "stored_lifecycle_status", None)
        if stored_lifecycle in BLOCKED_LIFECYCLE_STATUSES:
            reasons.append(
                f"subject_snapshot.stored_lifecycle_status '{stored_lifecycle}' is not "
                "permitted (must not be revoked, archived, or deleted_reference_only)"
            )
        # 8. Subject/request/draft identity + STORED scope comparison (necessary + sufficient).
        scope_check = validate_agent_run_subject_scope(request)
        reasons.extend(scope_check.reasons)

    # 9. The carried agent task output must be permitted, side-effect-free, review-gated.
    result_check = validate_agent_task_result_for_persistence(request)
    reasons.extend(result_check.reasons)

    # 10. fixture_test scope must not be mixed with live client/engagement scope.
    scopes = {auth}
    if subject is not None:
        scopes.add(getattr(subject, "stored_authorization_scope", None))
    has_live_ref = not _is_blank(getattr(request, "client_id", None)) or not _is_blank(
        getattr(request, "engagement_id", None)
    )
    if FIXTURE_TEST_SCOPE in scopes and has_live_ref:
        reasons.append("fixture_test scope must not be mixed with live client/engagement scope")

    return AgentRunPersistenceGovernanceDecision(
        permitted=not reasons, reasons=reasons, warnings=warnings
    )


def build_agent_run_persistence_decision(
    request: AgentRunPersistenceRequest,
) -> AgentRunPersistenceDecision:
    """Evaluate the request and return an ``AgentRunPersistenceDecision`` (no side effects)."""
    governance = evaluate_agent_run_persistence_request(request)
    return AgentRunPersistenceDecision(
        permitted=governance.permitted,
        persistence_action=getattr(request, "requested_persistence_action", None),
        target_table=TARGET_TABLE,
        requested_action=TARGET_ACTION,
        reasons=list(governance.reasons),
        warnings=list(governance.warnings),
    )
