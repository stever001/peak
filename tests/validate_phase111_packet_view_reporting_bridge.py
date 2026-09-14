#!/usr/bin/env python3
"""Phase 111 packet-view reporting bridge check — the functional route, end to end.

Stdlib-only, DB-free, env-free. Builds value-safe summaries of the documented Phase 109 lab chain in
memory (ids, statuses, posture — no row body), then runs the route reporting will use:

    assemble_packet_view -> build_report_inputs_from_packet_view -> MockAgentExecutor

and asserts that the Phase 94 review of ``evid_f094cbe4b47d4048`` gives no support to the finding
citing ``evid_8151dad609974ea0``; that the finding is one unreviewed, low-reliability,
internal-draft input; that recommendations and client-facing output stay blocked; that strict
``EngagementPacket`` insufficiency is carried; and that the reporting agent receives only
finding-backed record ids.

Exit status: 0 -> all checks passed; 1 -> a check failed.
"""

from __future__ import annotations

import dataclasses
import os
import subprocess
import sys

REPO_ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
if REPO_ROOT not in sys.path:
    sys.path.insert(0, REPO_ROOT)

from peak.agents.executor import MockAgentExecutor  # noqa: E402
from peak.reports.packet_view import assemble_packet_view  # noqa: E402
from peak.reports.packet_view_report import build_report_inputs_from_packet_view  # noqa: E402

_failures = []

ENG, SRC = "lab_internal_test_001", "ing_d67b76327aba4add"
EV_SOURCE_AVAILABILITY, EV_R1_COVERAGE = "evid_f094cbe4b47d4048", "evid_8151dad609974ea0"
REVIEW = "rev_70b5da9f14d54488"
IDENTITY = {"owner_id": "peak_internal_admin", "client_id": "99999", "engagement_id": ENG,
            "authorization_scope": "internal_peak_only"}


def check(label, ok):
    print(f"  [{'PASS' if ok else 'FAIL'}] {label}")
    if not ok:
        _failures.append(label)


def route(review_target=EV_SOURCE_AVAILABILITY):
    engagement = dict(IDENTITY, engagement_category="internal_test", real_client_data=False,
                      client_accessible=False, capsule_publication_authorized=False)
    sources = [dict(IDENTITY, source_ingestion_id=SRC, review_status="needs_review",
                    output_status="draft", lifecycle_status="active")]
    common = dict(IDENTITY, evidence_type="other", source_type="other", reliability="low",
                  review_status="needs_review", output_status="draft", lifecycle_status="active",
                  source_reference_id=SRC)
    evidence = [
        dict(common, evidence_id=EV_SOURCE_AVAILABILITY, claim_scope="source_availability_only"),
        dict(common, evidence_id=EV_R1_COVERAGE, claim_scope="operational_finding"),
    ]
    reviews = [dict(IDENTITY, review_id=REVIEW, target_id=review_target,
                    subject_record_type="evidence_reference", decision="approve_internal",
                    review_status="approved_internal", authoritative=False)]
    return build_report_inputs_from_packet_view(assemble_packet_view(engagement, sources, evidence, reviews))


def main() -> int:
    print("Peak Phase 111 packet-view reporting bridge check")
    print("=" * 50)

    inputs = route()

    print("\n1. One internal-draft finding, with no leaked review support")
    check("exactly one finding input", len(inputs.finding_inputs) == 1)
    f = inputs.finding_inputs[0]
    check("the finding cites evid_8151dad609974ea0", f.cited_evidence_id == EV_R1_COVERAGE)
    check("the finding's review support is empty", f.review_support_refs == [])
    check("the Phase 94 review supports no finding",
          all(REVIEW not in x.review_support_refs for x in inputs.finding_inputs))
    check("stored status needs_review, effective status unreviewed",
          f.stored_review_status == "needs_review" and f.effective_review_status == "unreviewed")
    check("reliability low, claim scope operational_finding",
          f.reliability == "low" and f.claim_scope == "operational_finding")
    check("internal draft only, human review required",
          f.readiness_state == "internal_draft_candidate" and f.internal_draft_only and f.requires_human_review)
    check("the finding source traces to the source record",
          f.source_reference_id == SRC and inputs.evidence_trace[EV_R1_COVERAGE]["source_resolved"])
    check("source-availability evidence is excluded as not an operational finding",
          [(x.evidence_id, x.reason) for x in inputs.excluded_evidence]
          == [(EV_SOURCE_AVAILABILITY, "source availability only; not an operational finding")])

    print("\n2. Recommendations and client-facing output stay blocked")
    check("the finding is not client-facing", not f.client_facing_allowed and not inputs.client_facing_allowed)
    check("the finding is not recommendation-eligible", not f.recommendation_eligible)
    check("blocked because unreviewed and low reliability",
          any("not internally approved" in r for r in f.recommendation_blocked_reasons)
          and any("reliability is low" in r for r in f.recommendation_blocked_reasons))
    check("recommendations are empty and blocked", inputs.recommendations == [] and inputs.recommendations_blocked)
    check("audience is internal", inputs.audience == "internal")

    print("\n3. Strict EngagementPacket insufficiency is carried")
    check("strict EngagementPacket is reported not valid", inputs.strict_engagement_packet_valid is False)
    check("reasons name client_intake", any("client_intake" in r for r in inputs.strict_engagement_packet_reasons))
    check("client_intake is reported missing", "client_intake" in inputs.missing_sections)

    print("\n4. The reporting agent receives only finding-backed records")
    task = inputs.report_task_request
    check("task targets initial_report_generation_agent", task is not None and task.agent_name == "initial_report_generation_agent")
    check("input records are the cited evidence and its source only", task.input_record_ids == [EV_R1_COVERAGE, SRC])
    check("the unrelated review and evidence are not passed", REVIEW not in task.input_record_ids and EV_SOURCE_AVAILABILITY not in task.input_record_ids)
    check("no client-facing output or live LLM requested", not task.client_facing_output_requested and not task.llm_execution_allowed)
    result = MockAgentExecutor().execute(task)
    check("the existing executor permits and plans the run", result.permitted and result.status == "planned_mock_no_execution")
    check("the run makes no DB write, LLM call, AgentNet call, resolver use, or client-facing output",
          not result.database_write_made and not result.llm_call_made and not result.agentnet_call_made
          and not result.resolver_context_used and not result.client_facing_output_created)

    print("\n5. Support follows the review's actual target")
    moved = route(review_target=EV_R1_COVERAGE)
    mf = moved.finding_inputs[0]
    check("a review of evid_8151dad609974ea0 supports its finding",
          mf.review_support_refs == [REVIEW] and mf.effective_review_status == "approved_internal")
    check("a reviewed low-reliability finding is still not recommendation-eligible or client-facing",
          not mf.recommendation_eligible and not mf.client_facing_allowed and moved.recommendations == [])
    check("the review is passed to the agent only when it targets the cited evidence",
          moved.report_task_request.input_record_ids == [EV_R1_COVERAGE, SRC, REVIEW])

    print("\n6. Deterministic and pure")
    check("the same input yields the same reporting inputs", dataclasses.asdict(route()) == dataclasses.asdict(inputs))
    source = open(os.path.join(REPO_ROOT, "peak", "reports", "packet_view_report.py")).read()
    check("the bridge does not use the planner's category-level review support",
          "internal_assessment_planner" not in source and "_review_support" not in source)
    probe = ("import sys; import peak.reports.packet_view_report; "
             "print(any(m == 'sqlalchemy' or m.startswith(('sqlalchemy.', 'peak.db')) for m in sys.modules))")
    out = subprocess.run([sys.executable, "-c", probe], cwd=REPO_ROOT, capture_output=True, text=True, timeout=60)
    check("importing the bridge loads no sqlalchemy or peak.db", out.returncode == 0 and out.stdout.strip() == "False")

    print("\n" + "=" * 50)
    print("Summary")
    print(f"  failures : {len(_failures)}")
    for label in _failures:
        print(f"    - {label}")
    print("\nRESULT: " + ("FAIL" if _failures else "PASS"))
    return 1 if _failures else 0


if __name__ == "__main__":
    raise SystemExit(main())
