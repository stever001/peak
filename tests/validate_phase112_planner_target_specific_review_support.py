#!/usr/bin/env python3
"""Phase 112 planner check — review support is target-specific.

Stdlib-only, DB-free, env-free. Plans the documented Phase 109 lab chain in memory (ids, claim
scopes, and review targets only — no row body) through the Phase 36 internal assessment planner and
asserts that:

* the Phase 94 review, which targets ``evid_f094cbe4b47d4048``, supports no finding citing
  ``evid_8151dad609974ea0``;
* the source-availability evidence gets no finding slot and supports no recommendation slot;
* retargeting the review moves support with it, and reviewed evidence alone creates no
  recommendation;
* an untargeted review reference supports nothing;
* recommendations and client-facing posture stay blocked;
* the new reference fields are governed, the plan is deterministic, and the planner agrees with the
  Phase 110/111 packet-view bridge on the same case.

Exit status: 0 -> all checks passed; 1 -> a check failed.
"""

from __future__ import annotations

import os
import sys

REPO_ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
if REPO_ROOT not in sys.path:
    sys.path.insert(0, REPO_ROOT)

from peak.reports import (  # noqa: E402
    GovernedRecordReference as Ref,
    InternalAssessmentReportPlanRequest as Req,
    prepare_internal_assessment_report_plan as plan_it,
)
from peak.reports.contracts import (  # noqa: E402
    RECOMMENDATION_BLOCKED_NO_REVIEW,
    RECOMMENDATION_INTERNAL_DRAFT,
    REVIEW_RECORD_SUPPORT_CAVEAT,
)
from peak.reports.packet_view import assemble_packet_view  # noqa: E402
from peak.reports.packet_view_report import build_report_inputs_from_packet_view  # noqa: E402

_failures = []

ENG, SRC = "lab_internal_test_001", "ing_d67b76327aba4add"
EV_A, EV_B = "evid_f094cbe4b47d4048", "evid_8151dad609974ea0"  # source availability / R1 coverage
REVIEW, DECISION = "rev_70b5da9f14d54488", "ird_phase112_test"
IDENTITY = {"owner_id": "peak_internal_admin", "client_id": "99999", "engagement_id": ENG,
            "authorization_scope": "internal_peak_only"}


def check(label, ok):
    print(f"  [{'PASS' if ok else 'FAIL'}] {label}")
    if not ok:
        _failures.append(label)


def plan(review=None, decisions=(), evidence=None):
    if review is None:
        review = Ref(record_id=REVIEW, record_type="review_records", target_record_ids=[EV_A])
    if evidence is None:
        evidence = [Ref(record_id=EV_A, record_type="evidence_references", claim_scope="source_availability_only"),
                    Ref(record_id=EV_B, record_type="evidence_references", claim_scope="operational_finding")]
    return plan_it(Req(**IDENTITY, requested_by="peak_internal_admin", requester_role="internal_admin",
                       report_plan_id="rpt_plan_phase112", source_ingestion_refs=[SRC],
                       evidence_reference_ids=evidence, review_record_ids=[review],
                       internal_reviewer_decision_record_ids=list(decisions)))


def main() -> int:
    print("Peak Phase 112 planner target-specific review support check")
    print("=" * 60)

    res = plan()
    p = res.report_plan

    print("\n1. The Phase 94 review does not support the Phase 107 finding")
    check("the plan is permitted", res.outcome == "planned" and p is not None)
    check("exactly one finding slot", len(p.finding_candidates) == 1)
    f = p.finding_candidates[0]
    check("the finding cites evid_8151dad609974ea0", f.evidence_support_refs == [EV_B])
    check("the finding has no review support", f.review_support_refs == [])
    check("the finding stays blocked for want of review support",
          f.readiness_state == RECOMMENDATION_BLOCKED_NO_REVIEW and "targets" in (f.blocked_reason or ""))
    check("no finding carries the Phase 94 review", all(REVIEW not in x.review_support_refs for x in p.finding_candidates))
    check("source-availability evidence gets no finding slot",
          all(EV_A not in x.evidence_support_refs for x in p.finding_candidates))
    check("the plan records the source-availability exclusion",
          any("source_availability_only" in r for r in p.reasons))
    check("the plan records the target-specific caveat",
          REVIEW_RECORD_SUPPORT_CAVEAT in p.reasons and "target-specific" in REVIEW_RECORD_SUPPORT_CAVEAT)

    print("\n2. Recommendations stay blocked or absent")
    check("no reviewer decision, no recommendation slot", p.recommendation_candidates == [])
    with_decision = plan(decisions=[DECISION]).report_plan
    rec = with_decision.recommendation_candidates[0]
    check("a recommendation slot cites only the operational evidence", rec.evidence_support_refs == [EV_B])
    check("it is blocked because its evidence is unreviewed",
          rec.readiness_state == RECOMMENDATION_BLOCKED_NO_REVIEW and rec.review_support_refs == [])
    check("nothing is client-facing, publishable, or financially verified",
          not p.client_facing_approved and not p.publication_allowed and not p.financial_verified
          and all(not x.client_facing_approved and not x.publication_allowed and x.requires_human_review
                  for x in list(p.finding_candidates) + list(with_decision.recommendation_candidates))
          and not res.client_facing_output_created)

    print("\n3. Support follows the review's actual target")
    moved = plan(review=Ref(record_id=REVIEW, record_type="review_records", target_record_ids=[EV_B])).report_plan
    mf = moved.finding_candidates[0]
    check("a review of evid_8151dad609974ea0 supports its finding",
          mf.review_support_refs == [REVIEW] and mf.readiness_state == RECOMMENDATION_INTERNAL_DRAFT)
    check("reviewed evidence alone creates no recommendation", moved.recommendation_candidates == [])
    check("a retargeted finding is still not client-facing", not mf.client_facing_approved and mf.requires_human_review)

    print("\n4. An untargeted review supports nothing")
    plain = plan(review=REVIEW).report_plan
    check("a plain review id gives the finding no support",
          plain.finding_candidates[0].review_support_refs == []
          and plain.finding_candidates[0].readiness_state == RECOMMENDATION_BLOCKED_NO_REVIEW)
    check("the plan records that the review names no target", any("name no target" in r for r in plain.reasons))
    typed_no_target = plan(review=Ref(record_id=REVIEW, record_type="review_records")).report_plan
    check("a typed review with no target gives no support", typed_no_target.finding_candidates[0].review_support_refs == [])

    print("\n5. The new fields are governed")
    unsafe = plan(review=Ref(record_id=REVIEW, target_record_ids=["evid_x\nDROP"]))
    check("an unsafe target id is denied", unsafe.outcome == "denied" and unsafe.reason_code == "prohibited_content")
    bad_scope = plan(evidence=[Ref(record_id=EV_B, claim_scope="inventory_accuracy")])
    check("an unrecognized claim scope is denied",
          bad_scope.outcome == "denied" and bad_scope.reason_code == "reference_identity_mismatch")
    misplaced_target = plan(evidence=[Ref(record_id=EV_B, target_record_ids=[EV_A])])
    check("targets on an evidence reference are denied",
          misplaced_target.outcome == "denied" and misplaced_target.reason_code == "reference_identity_mismatch")
    misplaced_scope = plan(review=Ref(record_id=REVIEW, claim_scope="operational_finding"))
    check("a claim scope on a review reference is denied",
          misplaced_scope.outcome == "denied" and misplaced_scope.reason_code == "reference_identity_mismatch")

    print("\n6. Deterministic")
    check("the same request yields the same fingerprint", plan().plan_fingerprint == res.plan_fingerprint)
    check("a different review target changes the fingerprint",
          plan(review=Ref(record_id=REVIEW, target_record_ids=[EV_B])).plan_fingerprint != res.plan_fingerprint)

    print("\n7. The planner agrees with the packet-view bridge")
    common = dict(IDENTITY, evidence_type="other", source_type="other", reliability="low",
                  review_status="needs_review", output_status="draft", lifecycle_status="active",
                  source_reference_id=SRC)

    def bridge(target):
        view = assemble_packet_view(
            dict(IDENTITY, engagement_category="internal_test"),
            [dict(IDENTITY, source_ingestion_id=SRC)],
            [dict(common, evidence_id=EV_A, claim_scope="source_availability_only"),
             dict(common, evidence_id=EV_B, claim_scope="operational_finding")],
            [dict(IDENTITY, review_id=REVIEW, target_id=target, subject_record_type="evidence_reference",
                  decision="approve_internal", review_status="approved_internal")])
        return build_report_inputs_from_packet_view(view).finding_inputs

    check("both paths give the Phase 107 finding no review support",
          [x.cited_evidence_id for x in bridge(EV_A)] == [EV_B] and bridge(EV_A)[0].review_support_refs == []
          and f.review_support_refs == [])
    check("both paths move support when the review targets evid_8151dad609974ea0",
          bridge(EV_B)[0].review_support_refs == [REVIEW] == mf.review_support_refs)

    print("\n" + "=" * 60)
    print("Summary")
    print(f"  failures : {len(_failures)}")
    for label in _failures:
        print(f"    - {label}")
    print("\nRESULT: " + ("FAIL" if _failures else "PASS"))
    return 1 if _failures else 0


if __name__ == "__main__":
    raise SystemExit(main())
