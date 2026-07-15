"""Peak internal production-shaped workers.

Phase 14 adds the first real worker — the **Evidence Normalization Worker** — which
produces **production-shaped but review-gated** normalized evidence records. The worker is
deterministic and side-effect-free: **no live LLM call, no AgentNet call, no database
read/write, no network call, no file write, no client-facing output, and no capsule
publication**. Output is never authoritative on its own — it defaults to ``draft`` /
``needs_review``.

See docs/EVIDENCE_NORMALIZATION_WORKER.md and docs/EVIDENCE_RECORD_LIFECYCLE.md.
"""

from __future__ import annotations

from .contracts import (
    EvidenceCompletenessFlags,
    EvidenceNormalizationRequest,
    EvidenceNormalizationResult,
    EvidenceQualitySignals,
    EvidenceReviewGate,
    EvidenceSourceReference,
    NormalizedEvidenceRecord,
    RawEvidenceReference,
)
from .evidence_normalization import (
    assess_completeness,
    assess_quality,
    build_normalized_summary,
    build_normalized_title,
    classify_evidence_type,
    derive_inventory_process_area,
    derive_operational_area,
    normalize_evidence,
)
from .governance import (
    EvidenceGovernanceDecision,
    build_evidence_review_gate,
    evaluate_evidence_normalization_request,
)

__all__ = [
    "EvidenceSourceReference",
    "RawEvidenceReference",
    "EvidenceNormalizationRequest",
    "NormalizedEvidenceRecord",
    "EvidenceNormalizationResult",
    "EvidenceCompletenessFlags",
    "EvidenceQualitySignals",
    "EvidenceReviewGate",
    "EvidenceGovernanceDecision",
    "evaluate_evidence_normalization_request",
    "build_evidence_review_gate",
    "normalize_evidence",
    "classify_evidence_type",
    "derive_operational_area",
    "derive_inventory_process_area",
    "build_normalized_title",
    "build_normalized_summary",
    "assess_completeness",
    "assess_quality",
]
