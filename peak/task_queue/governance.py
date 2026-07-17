"""Deterministic governance guards for the Agent Task Queue / Execution Readiness Boundary
(Phase 26).

Run *before* and *while* a queue/readiness plan is derived. Request-level checks enforce that
a queue request is authorized and scoped, carries an idempotency key and at least one Phase 13
task, and carries **no raw packet/evidence/interview/source content and no credential/secret
fields**. Per-task classification then assigns a deterministic execution-readiness state — and,
critically, **"ready" never means "execute now"**: no task is ever executed, no live flag may
be set, and every valid task still requires human review.

**Critical scope rule:** the request's ``authorization_scope`` must be present and each task's
``owner_id``/``client_id``/``engagement_id`` **and** ``authorization_scope`` must match the
request. Owner/client/engagement matching is necessary but **not sufficient**; the scope must
match too.

This module is **stdlib-only** plus the DB-free Phase 13 registry. It imports no SQLAlchemy,
Alembic, ``peak.db``, live/mock LLM, AgentNet/MCP/resolver/connector, or network module.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import List, Optional, Tuple

from peak.agents.registry import get_agent

from .contracts import (
    ALLOWED_QUEUE_ACTIONS,
    BLOCKED_BY_POLICY,
    BLOCKED_INVALID_SCOPE,
    BLOCKED_LIFECYCLE,
    BLOCKED_MISSING_EVIDENCE,
    BLOCKED_UNKNOWN_AGENT,
    EVIDENCE_DEPENDENT_WORKFLOWS,
    QUEUED_FOR_REVIEW,
    READY_FOR_FUTURE_CONTROLLED_EXECUTION,
    AgentTaskQueueRequest,
)

REVOKED_AUTHORIZATION_SCOPE = "revoked"
BLOCKED_LIFECYCLE_STATUSES = frozenset({"revoked", "archived", "deleted_reference_only"})

# Credential/secret term substrings that must never appear as request/context/task keys.
SECRET_KEY_TERMS = (
    "password",
    "secret",
    "api_key",
    "apikey",
    "token",
    "private_key",
    "privatekey",
    "credential",
    "connection_string",
    "access_key",
)

# Raw-content term substrings that must never appear as request/context/task keys. Phase 26
# accepts ids and references only — never raw payloads, raw text, or file/source bytes.
RAW_CONTENT_KEY_TERMS = (
    "packet_payload",
    "raw_packet",
    "raw_evidence",
    "evidence_text",
    "raw_interview",
    "interview_text",
    "interview_notes",
    "raw_text",
    "raw_content",
    "source_bytes",
    "file_bytes",
    "raw_source",
    "payload",
)

# Prohibited-intent term substrings: any request/context/ad-hoc key that asks Phase 26 to
# execute, reach the network, verify financials, or publish a capsule is denied. Phase 26
# only *plans*; it never carries an execution/network/financial/publication intent.
PROHIBITED_INTENT_KEY_TERMS = (
    "network",
    "http",
    "financial_verif",
    "verify_financial",
    "publish_capsule",
    "capsule_publication",
    "client_facing_approve",
    "live_execution",
    "execute_now",
    "run_agent",
    "mock_execution",
    "mock_agent",
)


@dataclass
class AgentTaskQueueGovernanceDecision:
    """Result of the pre-plan request-level governance checks."""

    permitted: bool = False
    reason_code: Optional[str] = None
    reasons: List[str] = field(default_factory=list)
    warnings: List[str] = field(default_factory=list)


@dataclass
class TaskReadinessClassification:
    """The deterministic readiness classification for one task."""

    readiness_state: str = QUEUED_FOR_REVIEW
    blocked: bool = False
    missing_evidence: bool = False
    reasons: List[str] = field(default_factory=list)
    warnings: List[str] = field(default_factory=list)


def _is_blank(value) -> bool:
    return value is None or (isinstance(value, str) and not value.strip())


def _iter_keys(value):
    """Yield every key found anywhere in a nested dict/list structure (keys only, no values)."""
    if isinstance(value, dict):
        for key, val in value.items():
            yield key
            yield from _iter_keys(val)
    elif isinstance(value, (list, tuple)):
        for item in value:
            yield from _iter_keys(item)


def _prohibited_key_hits(container) -> Tuple[List[str], List[str], List[str]]:
    """Return (secret_names, raw_content_names, intent_names) found in ``container``.

    Scans the object's own ``__dict__`` keys (catching ad-hoc attributes such as an injected
    ``packet_payload``) plus every key nested inside any dict/list attribute value (catching a
    ``context`` metadata dict). Only **key names** are returned — never values — so no secret or
    raw content is echoed.
    """
    secret_hits: List[str] = []
    raw_hits: List[str] = []
    intent_hits: List[str] = []
    keys: List[str] = []
    own = getattr(container, "__dict__", None)
    if isinstance(own, dict):
        for key, val in own.items():
            keys.append(key)
            keys.extend(list(_iter_keys(val)))
    elif isinstance(container, dict):
        keys.extend(list(_iter_keys(container)))
    for key in keys:
        if not isinstance(key, str):
            continue
        low = key.lower()
        if any(term in low for term in SECRET_KEY_TERMS):
            secret_hits.append(key)
        if any(term in low for term in RAW_CONTENT_KEY_TERMS):
            raw_hits.append(key)
        if any(term in low for term in PROHIBITED_INTENT_KEY_TERMS):
            intent_hits.append(key)
    return secret_hits, raw_hits, intent_hits


def _scan_request_for_prohibited_content(request: AgentTaskQueueRequest) -> List[str]:
    """Return safe reason strings for any prohibited (secret / raw-content / intent) keys.

    Scans the request itself, its ``context`` metadata, and each supplied task. Reports key
    names only (never values).
    """
    reasons: List[str] = []

    def _record(hits, where):
        secret_hits, raw_hits, intent_hits = hits
        if secret_hits:
            reasons.append(
                f"{where} contains prohibited credential/secret key(s): "
                + ", ".join(sorted(set(secret_hits)))
            )
        if raw_hits:
            reasons.append(
                f"{where} contains prohibited raw-content key(s): "
                + ", ".join(sorted(set(raw_hits)))
            )
        if intent_hits:
            reasons.append(
                f"{where} contains prohibited execution/network/financial/publication intent "
                "key(s): " + ", ".join(sorted(set(intent_hits)))
            )

    _record(_prohibited_key_hits(request), where="request")
    context = getattr(request, "context", None)
    if isinstance(context, dict):
        _record(_prohibited_key_hits(context), where="request.context")
    for index, task in enumerate(getattr(request, "agent_task_requests", []) or []):
        _record(_prohibited_key_hits(task), where=f"agent_task_requests[{index}]")
    return reasons


def evaluate_agent_task_queue_request(
    request: AgentTaskQueueRequest,
) -> AgentTaskQueueGovernanceDecision:
    """Return a request-level governance decision (no side effects)."""
    reasons: List[str] = []
    warnings: List[str] = []

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

    if _is_blank(getattr(request, "idempotency_key", None)):
        reasons.append("idempotency_key is required")

    auth = getattr(request, "authorization_scope", None)
    if auth == REVOKED_AUTHORIZATION_SCOPE:
        reasons.append("authorization_scope 'revoked' is not permitted")

    action = getattr(request, "requested_action", None)
    if _is_blank(action):
        reasons.append("requested_action is required")
    elif action not in ALLOWED_QUEUE_ACTIONS:
        reasons.append(
            f"requested_action '{action}' is not one of {sorted(ALLOWED_QUEUE_ACTIONS)}"
        )

    lifecycle = getattr(request, "lifecycle_status", None)
    if lifecycle in BLOCKED_LIFECYCLE_STATUSES:
        reasons.append(
            f"lifecycle_status '{lifecycle}' is not permitted "
            "(must not be revoked, archived, or deleted_reference_only)"
        )

    tasks = getattr(request, "agent_task_requests", None) or []
    if not isinstance(tasks, (list, tuple)) or len(tasks) == 0:
        reasons.append("at least one agent_task_request is required")

    reasons.extend(_scan_request_for_prohibited_content(request))

    reason_code = None
    if reasons:
        reason_code = "queue_request_denied"
    return AgentTaskQueueGovernanceDecision(
        permitted=not reasons, reason_code=reason_code, reasons=reasons, warnings=warnings
    )


def task_identity_mismatches(request: AgentTaskQueueRequest, task, index: int) -> List[str]:
    """Return identity/scope mismatch reasons for one task (identity necessary, not sufficient)."""
    reasons: List[str] = []
    for attr in ("owner_id", "client_id", "engagement_id"):
        req_val = getattr(request, attr, None)
        task_val = getattr(task, attr, None)
        if not _is_blank(task_val) and task_val != req_val:
            reasons.append(
                f"agent_task_requests[{index}] {attr} '{task_val}' does not match request "
                f"{attr} '{req_val}'"
            )
    req_scope = getattr(request, "authorization_scope", None)
    task_scope = getattr(task, "authorization_scope", None)
    if _is_blank(task_scope):
        reasons.append(f"agent_task_requests[{index}].authorization_scope is required")
    elif task_scope != req_scope:
        reasons.append(
            f"agent_task_requests[{index}].authorization_scope '{task_scope}' does not match "
            f"request.authorization_scope '{req_scope}' "
            "(owner/client/engagement matching is necessary but not sufficient)"
        )
    return reasons


def _task_has_evidence_input(request: AgentTaskQueueRequest, task) -> bool:
    """True if any evidence/source input is wired for a task (ids/references only)."""
    if getattr(request, "evidence_reference_ids", None):
        return True
    if getattr(request, "source_ingestion_record_id", None):
        return True
    if getattr(task, "input_record_ids", None):
        return True
    return False


def classify_task_readiness(
    request: AgentTaskQueueRequest, task, index: int
) -> TaskReadinessClassification:
    """Classify one task into a deterministic execution-readiness state (no execution).

    Order of precedence: unknown agent -> invalid scope -> blocked lifecycle -> policy
    violation -> missing evidence -> (ready-for-future | queued-for-review). "Ready" means
    structurally ready for a *later* controlled execution phase after review; it never permits
    execution now.
    """
    reasons: List[str] = []
    warnings: List[str] = []

    # 1. Known Phase 13 registry agent?
    entry = get_agent(getattr(task, "agent_name", None))
    if entry is None:
        return TaskReadinessClassification(
            readiness_state=BLOCKED_UNKNOWN_AGENT,
            blocked=True,
            reasons=[
                f"agent_task_requests[{index}] agent "
                f"'{getattr(task, 'agent_name', None)}' is not in the Phase 13 registry"
            ],
        )

    # 2. Identity / scope match.
    scope_reasons = task_identity_mismatches(request, task, index)
    if scope_reasons:
        return TaskReadinessClassification(
            readiness_state=BLOCKED_INVALID_SCOPE, blocked=True, reasons=scope_reasons
        )

    # 3. Task lifecycle not blocked.
    task_lifecycle = getattr(task, "lifecycle_status", None)
    if task_lifecycle in BLOCKED_LIFECYCLE_STATUSES:
        return TaskReadinessClassification(
            readiness_state=BLOCKED_LIFECYCLE,
            blocked=True,
            reasons=[
                f"agent_task_requests[{index}].lifecycle_status '{task_lifecycle}' is not "
                "permitted (must not be revoked, archived, or deleted_reference_only)"
            ],
        )

    # 4. No live-execution / LLM / resolver / client-facing request may be set.
    policy_reasons: List[str] = []
    if getattr(task, "llm_execution_allowed", False):
        policy_reasons.append(
            f"agent_task_requests[{index}].llm_execution_allowed must be False in Phase 26 "
            "(no LLM execution is planned or permitted)"
        )
    if getattr(task, "resolver_context_allowed", False):
        policy_reasons.append(
            f"agent_task_requests[{index}].resolver_context_allowed must be False in Phase 26 "
            "(no AgentNet/resolver context is loaded)"
        )
    if getattr(task, "client_facing_output_requested", False):
        policy_reasons.append(
            f"agent_task_requests[{index}].client_facing_output_requested must be False "
            "(no client-facing output is produced)"
        )
    if policy_reasons:
        return TaskReadinessClassification(
            readiness_state=BLOCKED_BY_POLICY, blocked=True, reasons=policy_reasons
        )

    # 5. Evidence-dependent workflow with no evidence input wired.
    if entry.workflow in EVIDENCE_DEPENDENT_WORKFLOWS and not _task_has_evidence_input(
        request, task
    ):
        return TaskReadinessClassification(
            readiness_state=BLOCKED_MISSING_EVIDENCE,
            blocked=True,
            missing_evidence=True,
            reasons=[
                f"agent_task_requests[{index}] workflow '{entry.workflow}' requires evidence "
                "input, but no evidence_reference_ids / source_ingestion_record_id / "
                "input_record_ids were supplied"
            ],
        )

    # 6. Structurally valid. Distinguish "ready for a future controlled run (after review)"
    #    from merely "queued for review" by whether inputs are wired. Neither permits
    #    execution now.
    if _task_has_evidence_input(request, task):
        return TaskReadinessClassification(
            readiness_state=READY_FOR_FUTURE_CONTROLLED_EXECUTION,
            blocked=False,
            warnings=[
                "ready_for_future_controlled_execution means structurally ready for a later "
                "controlled execution phase after human review — not execution now"
            ],
        )
    return TaskReadinessClassification(readiness_state=QUEUED_FOR_REVIEW, blocked=False)
