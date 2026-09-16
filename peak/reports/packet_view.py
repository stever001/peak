"""Packet-view assembly (Phase 110) — stored-record summaries in, a workflow-consumable view out.

Takes **already-fetched, value-safe summaries** of one engagement and its source-ingestion,
evidence-reference, and review records, and returns a ``PacketView``: schema-shaped evidence items
plus the sections the strict ``EngagementPacket`` cannot hold — sources, reviews, per-evidence review
links, posture, and what is missing.

**Reviews are target-specific.** A review is linked to an evidence item only when its ``target_id``
is that item's id (and its ``subject_record_type``, if given, is ``evidence_reference``). A shared
source, engagement, or phase never links a review to evidence it did not target. Evidence with no
linked review is ``unreviewed``. The stored ``review_status`` on the evidence row and the effective
review status derived from links are always two separate fields; nothing here implies the stored row
changed.

**Finding eligibility is separate from review status.** An evidence item is an internal finding
candidate only when its summary explicitly carries ``claim_scope="operational_finding"``. A
source-availability or unmarked item never is. Candidates are internal-draft only.

**Recommendations are always blocked.** This view accepts no recommendation input and creates none.

Side-effect boundary: pure functions over in-memory summaries. No database connection, no
SQLAlchemy / Alembic / ``peak.db`` import, no environment read, no file or network access, no
writer, and no LLM / AgentNet / resolver call. Summaries must not carry row bodies; ``summary`` is
passed through only if the caller supplied it. See docs/PHASE110_PACKET_VIEW_ASSEMBLER.md.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Dict, Iterable, List, Optional

#: Explicit claim-scope markings a caller may put on an evidence summary.
CLAIM_SCOPE_OPERATIONAL_FINDING = "operational_finding"
CLAIM_SCOPE_SOURCE_AVAILABILITY = "source_availability_only"

#: Effective review statuses, derived per evidence item from the reviews that target it.
EFFECTIVE_UNREVIEWED = "unreviewed"
EFFECTIVE_APPROVED_INTERNAL = "approved_internal"
EFFECTIVE_REVIEWED_NOT_APPROVED = "reviewed_not_approved"

#: A linked review approves only with this decision *and* this resulting status.
APPROVING_DECISION = "approve_internal"
APPROVING_REVIEW_STATUS = "approved_internal"

EVIDENCE_SUBJECT_TYPE = "evidence_reference"
IDENTITY_FIELDS = ("owner_id", "client_id", "engagement_id", "authorization_scope")
_INACTIVE_LIFECYCLES = frozenset({"superseded", "revoked", "archived", "deleted_reference_only"})

RECOMMENDATIONS_BLOCKED_REASON = (
    "the packet view accepts no recommendation input and creates none; recommendations need "
    "reviewed, finding-backed support supplied through a separate, approved path")
STRICT_PACKET_REASONS = (
    "client_intake is required by the strict EngagementPacket schema and is not supplied",
    "the strict EngagementPacket schema has no section for source or review records",
    "strict EngagementPacket evidence items cannot carry review status",
)


@dataclass
class EvidenceView:
    """One evidence item: stored fields, target-specific review links, and eligibility."""

    evidence_id: str
    evidence_type: Optional[str] = None
    source_type: Optional[str] = None
    reliability: Optional[str] = None
    stored_review_status: Optional[str] = None
    output_status: Optional[str] = None
    lifecycle_status: Optional[str] = None
    source_reference_id: Optional[str] = None
    source_resolved: bool = False
    claim_scope: Optional[str] = None
    # Phase 117: true only when the persisted-state adapter marks the summary as the stored statement.
    finding_statement_persisted: bool = False
    linked_review_ids: List[str] = field(default_factory=list)
    effective_review_status: str = EFFECTIVE_UNREVIEWED
    finding_candidate_allowed: bool = False
    client_facing_allowed: bool = False
    schema_item: Dict[str, object] = field(default_factory=dict)  # strict evidence-reference shape


@dataclass
class ReviewView:
    """One review record and whether its target resolved to an evidence item in this view."""

    review_id: str
    target_id: Optional[str] = None
    subject_record_type: Optional[str] = None
    decision: Optional[str] = None
    review_status: Optional[str] = None
    authoritative: bool = False
    linked_evidence_id: Optional[str] = None


@dataclass
class FindingCandidateView:
    """An internal-draft finding slot backed by exactly one evidence item. Never client-facing."""

    evidence_id: str
    reliability: Optional[str] = None
    effective_review_status: str = EFFECTIVE_UNREVIEWED
    linked_review_ids: List[str] = field(default_factory=list)
    internal_draft_only: bool = True
    client_facing_allowed: bool = False


@dataclass
class PacketView:
    """The assembled view. Internal-only; strict ``EngagementPacket`` validity is always false."""

    engagement: Dict[str, object] = field(default_factory=dict)
    sources: List[Dict[str, object]] = field(default_factory=list)
    evidence: List[EvidenceView] = field(default_factory=list)
    reviews: List[ReviewView] = field(default_factory=list)
    finding_candidates: List[FindingCandidateView] = field(default_factory=list)
    recommendations: List[object] = field(default_factory=list)
    recommendations_blocked: bool = True
    recommendations_blocked_reason: str = RECOMMENDATIONS_BLOCKED_REASON
    client_facing_allowed: bool = False
    strict_engagement_packet_valid: bool = False
    strict_engagement_packet_reasons: List[str] = field(default_factory=lambda: list(STRICT_PACKET_REASONS))
    missing_sections: List[str] = field(default_factory=list)
    unresolved_links: List[str] = field(default_factory=list)
    excluded_record_ids: List[str] = field(default_factory=list)
    warnings: List[str] = field(default_factory=list)

    def evidence_by_id(self, evidence_id: str) -> Optional[EvidenceView]:
        return next((e for e in self.evidence if e.evidence_id == evidence_id), None)


def _get(record, key, default=None):
    if isinstance(record, dict):
        return record.get(key, default)
    return getattr(record, key, default)


def _identity_mismatch(record, engagement) -> List[str]:
    return [f for f in IDENTITY_FIELDS if _get(record, f) != _get(engagement, f)]


def _effective_review_status(linked_reviews: List[ReviewView]) -> str:
    """Unreviewed without links; approved only if every linked review approves. Never upgrades."""
    if not linked_reviews:
        return EFFECTIVE_UNREVIEWED
    if all(r.decision == APPROVING_DECISION and r.review_status == APPROVING_REVIEW_STATUS
           for r in linked_reviews):
        return EFFECTIVE_APPROVED_INTERNAL
    return EFFECTIVE_REVIEWED_NOT_APPROVED


def assemble_packet_view(engagement, sources: Iterable = (), evidence: Iterable = (),
                         reviews: Iterable = ()) -> PacketView:
    """Assemble a ``PacketView`` from already-fetched, value-safe record summaries.

    ``engagement`` needs ``engagement_id``, ``client_id``, ``owner_id``, and ``authorization_scope``;
    records whose identity does not match it are excluded and reported. Records are emitted in
    sorted id order, so the same input always yields the same view.
    """
    view = PacketView()
    view.engagement = {
        "engagement_id": _get(engagement, "engagement_id"),
        "client_id": _get(engagement, "client_id"),
        "owner_id": _get(engagement, "owner_id"),
        "authorization_scope": _get(engagement, "authorization_scope"),
        "engagement_category": _get(engagement, "engagement_category"),
        "real_client_data": bool(_get(engagement, "real_client_data", False)),
        "client_accessible": bool(_get(engagement, "client_accessible", False)),
        "capsule_publication_authorized": bool(_get(engagement, "capsule_publication_authorized", False)),
    }

    def admitted(records, id_key):
        kept = []
        for record in records:
            record_id = _get(record, id_key)
            mismatch = _identity_mismatch(record, engagement)
            if mismatch:
                view.excluded_record_ids.append(record_id)
                view.warnings.append(f"{record_id} excluded: identity mismatch on {', '.join(mismatch)}")
            else:
                kept.append(record)
        return sorted(kept, key=lambda r: str(_get(r, id_key)))

    source_records = admitted(sources, "source_ingestion_id")
    evidence_records = admitted(evidence, "evidence_id")
    review_records = admitted(reviews, "review_id")

    source_ids = set()
    for s in source_records:
        source_ids.add(_get(s, "source_ingestion_id"))
        view.sources.append({
            "source_ingestion_id": _get(s, "source_ingestion_id"),
            "source_reference_id": _get(s, "source_reference_id"),
            "stored_review_status": _get(s, "review_status"),
            "output_status": _get(s, "output_status"),
            "lifecycle_status": _get(s, "lifecycle_status"),
            "authoritative": bool(_get(s, "authoritative", False)),
        })

    evidence_ids = {_get(e, "evidence_id") for e in evidence_records}
    links: Dict[str, List[ReviewView]] = {eid: [] for eid in evidence_ids}
    for r in review_records:
        subject = _get(r, "subject_record_type")
        target = _get(r, "target_id")
        review = ReviewView(
            review_id=_get(r, "review_id"), target_id=target, subject_record_type=subject,
            decision=_get(r, "decision"), review_status=_get(r, "review_status"),
            authoritative=bool(_get(r, "authoritative", False)))
        if target in evidence_ids and subject in (None, EVIDENCE_SUBJECT_TYPE):
            review.linked_evidence_id = target
            links[target].append(review)
        else:
            view.unresolved_links.append(f"{review.review_id} -> {target}: no evidence item in this view")
        view.reviews.append(review)

    for e in evidence_records:
        eid = _get(e, "evidence_id")
        linked = links[eid]
        source_ref = _get(e, "source_reference_id")
        item = EvidenceView(
            evidence_id=eid,
            evidence_type=_get(e, "evidence_type"),
            source_type=_get(e, "source_type"),
            reliability=_get(e, "reliability"),
            stored_review_status=_get(e, "review_status"),
            output_status=_get(e, "output_status"),
            lifecycle_status=_get(e, "lifecycle_status"),
            source_reference_id=source_ref,
            source_resolved=source_ref in source_ids,
            claim_scope=_get(e, "claim_scope"),
            finding_statement_persisted=(bool(_get(e, "finding_statement_persisted", False))
                                         and _get(e, "summary") is not None),
            linked_review_ids=[r.review_id for r in linked],
            effective_review_status=_effective_review_status(linked),
        )
        if source_ref and not item.source_resolved:
            view.unresolved_links.append(f"{eid} -> {source_ref}: no source record in this view")
        item.finding_candidate_allowed = (
            item.claim_scope == CLAIM_SCOPE_OPERATIONAL_FINDING
            and item.lifecycle_status not in _INACTIVE_LIFECYCLES
            and item.effective_review_status != EFFECTIVE_REVIEWED_NOT_APPROVED)
        item.schema_item = {
            "evidence_id": eid,
            "evidence_type": item.evidence_type,
            "source_type": item.source_type,
            "reliability": item.reliability,
            "sensitive_data_flag": bool(_get(e, "sensitive_data_flag", False)),
            "related_object_ids": [source_ref] if source_ref else [],
        }
        if _get(e, "summary") is not None:
            item.schema_item["summary"] = _get(e, "summary")
        view.evidence.append(item)
        if item.finding_candidate_allowed:
            view.finding_candidates.append(FindingCandidateView(
                evidence_id=eid, reliability=item.reliability,
                effective_review_status=item.effective_review_status,
                linked_review_ids=list(item.linked_review_ids)))

    view.missing_sections = ["client_intake", "inventory_system_profile"]
    if any(_get(e, "summary") is None for e in evidence_records):
        view.missing_sections.append("evidence summary text (not supplied)")
    return view
