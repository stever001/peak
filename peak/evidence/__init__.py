"""Peak evidence persistence mapping (Phase 18).

Connects the Phase 14 evidence normalization output to the Phase 17 controlled write
boundary: it maps a ``NormalizedEvidenceRecord`` into a production-shaped but review-gated
``EvidencePersistenceDraft`` and routes it through the Phase 17 no-op controlled writer as a
plan targeting ``evidence_references`` / ``create_draft`` — all **DB-aware but not
DB-writing**.

This package (``peak.evidence``) is domain-specific evidence persistence mapping. It is
kept out of ``peak.db`` and imports no SQLAlchemy, no Alembic, and no ``peak.db``
session/model modules. It *does* import the Phase 17 persistence contracts and planner
(``peak.persistence``) because it bridges the two boundaries; Phase 14 worker contracts are
consumed duck-typed by attribute.

Across the package:

- **no database connection, no database read/write, no SQL execution, no stored records**;
- **no live LLM call, no AgentNet call, no MCP/resolver call, no network call**;
- **no file write, no client-facing approval, no financial verification, no capsule publication**.

A **write plan is not a write**, and **evidence workers still do not write directly to the
DB**. See docs/EVIDENCE_PERSISTENCE_MAPPING.md and docs/EVIDENCE_WRITE_PLAN_POLICY.md.
"""

from __future__ import annotations

from .persistence_contracts import (
    ALLOWED_PERSISTENCE_ACTION,
    TARGET_ACTION,
    TARGET_TABLE,
    EvidencePersistenceDecision,
    EvidencePersistenceDraft,
    EvidencePersistenceMappingResult,
    EvidencePersistenceRequest,
    EvidencePersistenceSubjectSnapshot,
)
from .persistence_governance import (
    EvidencePersistenceGovernanceDecision,
    build_evidence_persistence_decision,
    evaluate_evidence_persistence_request,
    validate_evidence_subject_scope,
    validate_normalization_result_for_persistence,
)
from .evidence_record_mapper import (
    build_controlled_write_request,
    build_controlled_write_subject,
    build_evidence_persistence_draft,
    prepare_evidence_persistence,
)

__all__ = [
    # contracts
    "ALLOWED_PERSISTENCE_ACTION",
    "TARGET_TABLE",
    "TARGET_ACTION",
    "EvidencePersistenceSubjectSnapshot",
    "EvidencePersistenceRequest",
    "EvidencePersistenceDraft",
    "EvidencePersistenceDecision",
    "EvidencePersistenceMappingResult",
    # governance
    "EvidencePersistenceGovernanceDecision",
    "evaluate_evidence_persistence_request",
    "validate_evidence_subject_scope",
    "validate_normalization_result_for_persistence",
    "build_evidence_persistence_decision",
    # mapper
    "build_evidence_persistence_draft",
    "build_controlled_write_subject",
    "build_controlled_write_request",
    "prepare_evidence_persistence",
]
