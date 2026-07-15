"""Peak internal QA / Review Gate (Phase 15) + Review Persistence Boundary (Phase 16).

Phase 15 defines how Peak evaluates worker/agent outputs (e.g. the Phase 14 evidence
drafts) for internal approval, rejection, return for revision, supersession, or continued
review. Decisions are **production-shaped but no-side-effect**: the gate persists nothing
and confers no final authority.

Phase 16 adds the **Review Persistence Boundary** — **DB-aware but not DB-writing**. It
describes how a *future* controlled-DB writer will persist a permitted review outcome as a
``ReviewRecord``, and enforces that a DB-backed review compares the request's
``authorization_scope`` against the subject record's **stored** scope
(``StoredReviewSubjectSnapshot.stored_authorization_scope``) — owner/client/engagement
matching is necessary but not sufficient. It opens no database session and imports no
SQLAlchemy / ``peak.db``.

Across both phases:

- **no database read/write, no database connection, no stored review records**;
- **no live LLM call, no AgentNet call, no MCP/resolver call, no network call**;
- **no file write, no client-facing output, no capsule publication**.

``approve_internal`` means **internal reliance only**. Client-facing approval,
financial-impact verification, and capsule publication remain separate and future;
``client_facing_approved`` and ``capsule_candidate_ready`` stay ``false`` in every case.

See docs/QA_REVIEW_GATE.md, docs/REVIEW_DECISION_MODEL.md,
docs/REVIEW_PERSISTENCE_BOUNDARY.md, and docs/DB_BACKED_REVIEW_SCOPE_POLICY.md.
"""

from __future__ import annotations

from .contracts import (
    ALLOWED_DECISIONS,
    PROHIBITED_DECISIONS,
    ReviewActionPlan,
    ReviewChecklistResult,
    ReviewDecision,
    ReviewDecisionRequest,
    ReviewGateResult,
    ReviewSubjectReference,
)
from .governance import (
    ReviewGovernanceDecision,
    build_review_checklist,
    evaluate_review_request,
    validate_requested_decision,
)
from .persistence_contracts import (
    ALLOWED_PERSISTENCE_ACTIONS,
    REVIEW_RECORDS_TABLE,
    ReviewPersistenceDecision,
    ReviewPersistenceRequest,
    ReviewPersistenceResult,
    ReviewRecordDraft,
    ReviewWritePlan,
    StoredReviewSubjectSnapshot,
)
from .persistence_governance import (
    ReviewPersistenceGovernanceDecision,
    build_persistence_decision,
    evaluate_review_persistence_request,
    validate_gate_result_for_persistence,
    validate_subject_scope_against_request,
)
from .review_gate import (
    build_action_plan,
    derive_next_state,
    evaluate_review_gate,
)
from .review_record_mapper import (
    build_review_record_draft,
    build_review_write_plan,
    prepare_review_persistence,
)

__all__ = [
    # Phase 15 — review gate
    "ALLOWED_DECISIONS",
    "PROHIBITED_DECISIONS",
    "ReviewSubjectReference",
    "ReviewChecklistResult",
    "ReviewDecisionRequest",
    "ReviewDecision",
    "ReviewActionPlan",
    "ReviewGateResult",
    "ReviewGovernanceDecision",
    "evaluate_review_request",
    "validate_requested_decision",
    "build_review_checklist",
    "evaluate_review_gate",
    "derive_next_state",
    "build_action_plan",
    # Phase 16 — review persistence boundary
    "ALLOWED_PERSISTENCE_ACTIONS",
    "REVIEW_RECORDS_TABLE",
    "StoredReviewSubjectSnapshot",
    "ReviewPersistenceRequest",
    "ReviewRecordDraft",
    "ReviewPersistenceDecision",
    "ReviewWritePlan",
    "ReviewPersistenceResult",
    "ReviewPersistenceGovernanceDecision",
    "evaluate_review_persistence_request",
    "validate_subject_scope_against_request",
    "validate_gate_result_for_persistence",
    "build_persistence_decision",
    "build_review_record_draft",
    "build_review_write_plan",
    "prepare_review_persistence",
]
