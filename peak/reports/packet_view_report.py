"""Packet-view reporting bridge (Phase 111) — a ``PacketView`` in, reporting inputs out.

Turns the Phase 110 packet view into what the reporting workflow consumes: finding inputs that
keep each cited evidence item's posture, an evidence trace, explicit exclusions, blocked
recommendations, and an ``AgentTaskRequest`` for the existing ``initial_report_generation_agent``
scoped to finding-backed records only.

**Review support comes only from the packet view's target-specific links.** A finding's
``review_support_refs`` are the reviews linked to the evidence it cites — never every review in the
engagement. This path does not use the Phase 36 planner's category-level review support, which
counts any review as support for every finding.

**Nothing is upgraded.** Unreviewed evidence may back an internal-draft finding and nothing more.
No finding input is client-facing or recommendation-eligible; recommendations are always empty and
blocked here, with reasons. Strict ``EngagementPacket`` insufficiency is carried through unchanged.

Side-effect boundary: pure functions over an in-memory ``PacketView``. No database connection, no
SQLAlchemy / Alembic / ``peak.db`` import, no environment read, no file or network access, no
writer, and no agent execution — the task request is built, not run. Output is deterministic. See
docs/PHASE111_PACKET_VIEW_REPORTING_BRIDGE.md.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Dict, List, Optional

from peak.agents.contracts import AgentTaskRequest
from peak.agents.registry import get_agent

from .contracts import AUDIENCE_INTERNAL, RECOMMENDATION_INTERNAL_DRAFT, SECTION_OPERATIONAL_FINDINGS
from .packet_view import (
    CLAIM_SCOPE_OPERATIONAL_FINDING,
    CLAIM_SCOPE_SOURCE_AVAILABILITY,
    EFFECTIVE_APPROVED_INTERNAL,
    EFFECTIVE_UNREVIEWED,
    PacketView,
)

REPORTING_AGENT = "initial_report_generation_agent"
REPORTING_ACTION = "draft_internal_assessment_report"
NO_RECOMMENDATION_INPUT = "the packet view carries no reviewed, finding-backed recommendation input"


@dataclass
class ReportFindingInput:
    """One internal-draft finding input, backed by exactly one evidence item and its own reviews."""

    finding_candidate_id: str
    cited_evidence_id: str
    section_id: str = SECTION_OPERATIONAL_FINDINGS
    source_reference_id: Optional[str] = None
    stored_review_status: Optional[str] = None
    effective_review_status: str = EFFECTIVE_UNREVIEWED
    review_support_refs: List[str] = field(default_factory=list)  # reviews of the cited evidence only
    reliability: Optional[str] = None
    claim_scope: Optional[str] = None
    readiness_state: str = RECOMMENDATION_INTERNAL_DRAFT
    internal_draft_only: bool = True
    requires_human_review: bool = True
    client_facing_allowed: bool = False
    recommendation_eligible: bool = False
    recommendation_blocked_reasons: List[str] = field(default_factory=list)


@dataclass
class ExcludedEvidence:
    """An evidence item that backs no finding input, and why."""

    evidence_id: str
    reason: str


@dataclass
class PacketViewReportInputs:
    """Reporting inputs derived from a packet view. Internal audience only."""

    engagement: Dict[str, object] = field(default_factory=dict)
    audience: str = AUDIENCE_INTERNAL
    finding_inputs: List[ReportFindingInput] = field(default_factory=list)
    excluded_evidence: List[ExcludedEvidence] = field(default_factory=list)
    evidence_trace: Dict[str, Dict[str, object]] = field(default_factory=dict)
    recommendations: List[object] = field(default_factory=list)
    recommendations_blocked: bool = True
    recommendations_blocked_reasons: List[str] = field(default_factory=list)
    client_facing_allowed: bool = False
    strict_engagement_packet_valid: bool = False
    strict_engagement_packet_reasons: List[str] = field(default_factory=list)
    missing_sections: List[str] = field(default_factory=list)
    report_task_request: Optional[AgentTaskRequest] = None
    warnings: List[str] = field(default_factory=list)


def _exclusion_reason(evidence) -> str:
    if evidence.claim_scope == CLAIM_SCOPE_SOURCE_AVAILABILITY:
        return "source availability only; not an operational finding"
    if evidence.claim_scope != CLAIM_SCOPE_OPERATIONAL_FINDING:
        return "not marked as an operational finding"
    if evidence.effective_review_status not in (EFFECTIVE_UNREVIEWED, EFFECTIVE_APPROVED_INTERNAL):
        return f"a linked review did not approve it ({evidence.effective_review_status})"
    return f"lifecycle status '{evidence.lifecycle_status}' is not active"


def _recommendation_blocked_reasons(evidence) -> List[str]:
    reasons = []
    if evidence.effective_review_status != EFFECTIVE_APPROVED_INTERNAL:
        reasons.append(f"cited evidence is not internally approved ({evidence.effective_review_status})")
    if evidence.reliability in (None, "low"):
        reasons.append(f"cited evidence reliability is {evidence.reliability or 'unspecified'}")
    reasons.append(NO_RECOMMENDATION_INPUT)
    return reasons


def build_report_inputs_from_packet_view(view: PacketView) -> PacketViewReportInputs:
    """Build reporting inputs from a ``PacketView`` without widening any evidence posture."""
    inputs = PacketViewReportInputs(
        engagement=dict(view.engagement),
        strict_engagement_packet_valid=False,
        strict_engagement_packet_reasons=list(view.strict_engagement_packet_reasons),
        missing_sections=list(view.missing_sections),
        recommendations_blocked_reasons=[view.recommendations_blocked_reason,
                                         "no finding input is recommendation-eligible"],
        warnings=list(view.warnings),
    )

    candidate_ids = {c.evidence_id for c in view.finding_candidates}
    cited = sorted((e for e in view.evidence if e.evidence_id in candidate_ids), key=lambda e: e.evidence_id)
    for e in sorted(view.evidence, key=lambda e: e.evidence_id):
        if e.evidence_id not in candidate_ids:
            inputs.excluded_evidence.append(ExcludedEvidence(e.evidence_id, _exclusion_reason(e)))

    for index, e in enumerate(cited):
        inputs.finding_inputs.append(ReportFindingInput(
            finding_candidate_id=f"fnd_{index:03d}",
            cited_evidence_id=e.evidence_id,
            source_reference_id=e.source_reference_id,
            stored_review_status=e.stored_review_status,
            effective_review_status=e.effective_review_status,
            review_support_refs=list(e.linked_review_ids),
            reliability=e.reliability,
            claim_scope=e.claim_scope,
            recommendation_blocked_reasons=_recommendation_blocked_reasons(e),
        ))
        inputs.evidence_trace[e.evidence_id] = {
            "source_reference_id": e.source_reference_id,
            "source_resolved": e.source_resolved,
            "review_support_refs": list(e.linked_review_ids),
        }

    if not inputs.finding_inputs:
        inputs.warnings.append("no finding input: no report task request was built")
        return inputs

    entry = get_agent(REPORTING_AGENT)
    record_ids = set()
    for f in inputs.finding_inputs:
        record_ids.add(f.cited_evidence_id)
        record_ids.update(f.review_support_refs)
        if f.source_reference_id:
            record_ids.add(f.source_reference_id)
    inputs.report_task_request = AgentTaskRequest(
        agent_name=entry.agent_name,
        workflow=entry.workflow,
        owner_id=view.engagement.get("owner_id"),
        client_id=view.engagement.get("client_id"),
        engagement_id=view.engagement.get("engagement_id"),
        requested_action=REPORTING_ACTION,
        input_record_ids=sorted(record_ids),
        prompt_contract_path=entry.prompt_contract_path,
        authorization_scope=view.engagement.get("authorization_scope"),
        review_status="needs_review",
        lifecycle_status="draft",
        resolver_context_allowed=False,
        llm_execution_allowed=False,
        client_facing_output_requested=False,
    )
    return inputs
