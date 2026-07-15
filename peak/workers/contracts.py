"""Contracts for the Evidence Normalization Worker (Phase 14).

Production-shaped but **review-gated** dataclasses. The worker can produce high-quality,
structured normalized evidence, but that evidence is never authoritative on its own: every
result defaults to ``output_status = draft`` / ``review_status = needs_review`` with
``authoritative = False`` and ``client_facing_approved = False``.

**Source contracts only — no stored records.** Nothing here calls an LLM, AgentNet, an MCP
connector, a resolver, a database, or the network, and nothing produces client-facing
output. See docs/EVIDENCE_NORMALIZATION_WORKER.md and docs/EVIDENCE_RECORD_LIFECYCLE.md.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import List, Optional

# Review-gate defaults for any normalized evidence produced in Phase 14.
DEFAULT_OUTPUT_STATUS = "draft"
DEFAULT_REVIEW_STATUS = "needs_review"
DEFAULT_LIFECYCLE_STATUS = "active"


@dataclass
class EvidenceSourceReference:
    """Where a piece of evidence originated (pointer/metadata; no sensitive content)."""

    source_reference_id: Optional[str] = None
    source_type: Optional[str] = None
    source_name: Optional[str] = None
    source_location: Optional[str] = None
    captured_by: Optional[str] = None
    captured_at: Optional[str] = None
    source_system: Optional[str] = None
    authorization_scope: Optional[str] = None


@dataclass
class RawEvidenceReference:
    """A raw, pre-normalization evidence reference (metadata + a short non-sensitive preview)."""

    raw_reference_id: Optional[str] = None
    source_reference: Optional[EvidenceSourceReference] = None
    content_type: Optional[str] = None
    observed_at: Optional[str] = None
    observation_context: Optional[str] = None
    raw_text_preview: Optional[str] = None
    attachment_reference: Optional[str] = None
    location_context: Optional[str] = None


@dataclass
class EvidenceNormalizationRequest:
    """A request to normalize one raw evidence reference into a review-gated record."""

    owner_id: Optional[str] = None
    client_id: Optional[str] = None
    engagement_id: Optional[str] = None
    requested_by: Optional[str] = None
    workflow: Optional[str] = None
    authorization_scope: Optional[str] = None
    review_status: Optional[str] = None
    lifecycle_status: Optional[str] = None
    raw_evidence: Optional[RawEvidenceReference] = None
    normalize_for: Optional[str] = None


@dataclass
class EvidenceCompletenessFlags:
    """Which inputs were present when the record was normalized."""

    has_source_reference: bool = False
    has_observed_at: bool = False
    has_source_location: bool = False
    has_raw_text_preview: bool = False
    has_capture_metadata: bool = False
    complete: bool = False
    missing_fields: List[str] = field(default_factory=list)


@dataclass
class EvidenceQualitySignals:
    """Conservative, deterministic quality signals for a normalized record."""

    reliability: str = "low"
    confidence_level: str = "low"
    has_minimum_context: bool = False
    warnings: List[str] = field(default_factory=list)
    notes: str = ""


@dataclass
class NormalizedEvidenceRecord:
    """A production-shaped, review-gated normalized evidence record (never stored here)."""

    evidence_record_id: Optional[str] = None
    owner_id: Optional[str] = None
    client_id: Optional[str] = None
    engagement_id: Optional[str] = None
    source_reference_id: Optional[str] = None
    evidence_type: Optional[str] = None
    normalized_title: Optional[str] = None
    normalized_summary: Optional[str] = None
    observed_condition: Optional[str] = None
    operational_area: Optional[str] = None
    inventory_process_area: Optional[str] = None
    source_type: Optional[str] = None
    source_location: Optional[str] = None
    confidence_level: str = "low"
    completeness_flags: Optional[EvidenceCompletenessFlags] = None
    quality_signals: Optional[EvidenceQualitySignals] = None
    output_status: str = DEFAULT_OUTPUT_STATUS
    review_status: str = DEFAULT_REVIEW_STATUS
    lifecycle_status: str = DEFAULT_LIFECYCLE_STATUS
    authoritative: bool = False
    client_facing_approved: bool = False
    capsule_candidate_ready: bool = False
    warnings: List[str] = field(default_factory=list)
    reasons: List[str] = field(default_factory=list)


@dataclass
class EvidenceReviewGate:
    """The review posture stamped onto every normalized record (defaults are the gate)."""

    output_status: str = DEFAULT_OUTPUT_STATUS
    review_status: str = DEFAULT_REVIEW_STATUS
    lifecycle_status: str = DEFAULT_LIFECYCLE_STATUS
    authoritative: bool = False
    client_facing_approved: bool = False
    capsule_candidate_ready: bool = False
    requires_human_review: bool = True
    notes: str = (
        "worker-normalized evidence is review-gated; it is not authoritative merely "
        "because a worker created it"
    )


@dataclass
class EvidenceNormalizationResult:
    """The controlled result of a normalization run (no side effects)."""

    permitted: bool = False
    status: str = "rejected"
    normalized_record: Optional[NormalizedEvidenceRecord] = None
    output_status: str = DEFAULT_OUTPUT_STATUS
    review_status: str = DEFAULT_REVIEW_STATUS
    lifecycle_status: str = DEFAULT_LIFECYCLE_STATUS
    authoritative: bool = False
    client_facing_approved: bool = False
    database_write_made: bool = False
    llm_call_made: bool = False
    agentnet_call_made: bool = False
    network_call_made: bool = False
    capsule_publication_made: bool = False
    reasons: List[str] = field(default_factory=list)
    warnings: List[str] = field(default_factory=list)
