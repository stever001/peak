"""One-call consultant internal assessment (Phase 119).

Packages the existing persisted-state route behind one operation, so a consultant-facing caller does
not compose the Phase 113–118 functions by hand::

    engagement_id + caller-owned read-only connection
      -> fetch_engagement_packet_summaries   (Phase 113, read-only)
      -> build_persisted_report_inputs       (Phase 113–117: packet view -> report inputs)
      -> fetch_discovery_summaries           (Phase 206, read-only)
      -> build_discovery_assessment_context  (Phase 206, pure)
      -> build_internal_assessment           (Phase 116–118, plus Phase 206 discovery context)
      -> render_internal_assessment_markdown (Phase 116, plus Phase 206 discovery sections)

**Orchestration only.** No business rule lives here: claim scope, the finding statement,
target-specific review support, recommendation eligibility, and bounded recommendations are all
decided by the modules composed above, unchanged. The result is internal-only
(``client_facing=False``) and always requires human review.

**The evidence route is unchanged by Phase 206.** Discovery is fetched *after* the packet
summaries, so the engagement's Phase 57 visibility check has already passed or refused before any
discovery row is read, and it is attached to the assessment rather than folded into it. An
engagement with no discovery material yields ``discovery=None`` and exactly the document Phases
116–118 produced.

**Read-only.** The caller establishes and owns the connection; this module opens none, reads no
environment variable, and calls no writer. The reader is imported **lazily**, so ``peak.workflows``
still imports without a database driver. See docs/PHASE119_ONE_CALL_CONSULTANT_WORKFLOW.md.
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Optional

from peak.reports.discovery_assessment import build_discovery_assessment_context
from peak.reports.internal_assessment import (
    InternalAssessment,
    build_internal_assessment,
    render_internal_assessment_markdown,
)
from peak.reports.persisted_packet_view import ClaimScopePolicy, build_persisted_report_inputs


@dataclass
class ConsultantInternalAssessmentResult:
    """The assessment object and its rendered Markdown document."""

    assessment: InternalAssessment
    markdown: str


def build_consultant_internal_assessment(connection, engagement_id: str,
                                         mode: Optional[str] = None,
                                         include_internal_test: bool = False,
                                         policy: Optional[ClaimScopePolicy] = None
                                         ) -> ConsultantInternalAssessmentResult:
    """Fetch one engagement's persisted state and return its internal assessment and Markdown.

    ``mode`` and ``include_internal_test`` pass through to the Phase 113 reader (``mode=None`` keeps
    the reader's Phase 57 default); ``policy`` is the legacy-row fallback only. Visibility refusals
    (``LookupError`` / ``EngagementNotVisible``) propagate unchanged, and are raised before any
    discovery row is read.
    """
    from peak.db.discovery_assessment_reader import fetch_discovery_summaries
    from peak.db.engagement_packet_reader import fetch_engagement_packet_summaries

    read_options = {"include_internal_test": include_internal_test}
    if mode is not None:
        read_options["mode"] = mode
    summaries = fetch_engagement_packet_summaries(connection, engagement_id, **read_options)
    discovery = build_discovery_assessment_context(
        fetch_discovery_summaries(connection, engagement_id))
    assessment = build_internal_assessment(
        build_persisted_report_inputs(summaries, policy),
        discovery=discovery if discovery.available else None)
    return ConsultantInternalAssessmentResult(
        assessment=assessment, markdown=render_internal_assessment_markdown(assessment))
