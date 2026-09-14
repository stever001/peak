#!/usr/bin/env python3
"""Phase 110 packet-view assembler check — reviews are target-specific.

Stdlib-only, DB-free, env-free. Builds value-safe summaries of the documented Phase 109 lab chain in
memory (ids, statuses, and posture only — no row body) and asserts on the assembler's output:

* the Phase 94 review links to the evidence it targets and to nothing else;
* the Phase 107 evidence stays ``unreviewed`` with its stored ``needs_review`` status intact, yet can
  still be a low-reliability, internal-draft finding candidate;
* the source-availability evidence is not a finding candidate;
* recommendations stay blocked, client-facing output stays disallowed, and the strict
  ``EngagementPacket`` is reported as not valid;
* moving the review's target moves the link — support is never global;
* the module imports no database layer.

Exit status: 0 -> all checks passed; 1 -> a check failed.
"""

from __future__ import annotations

import os
import subprocess
import sys

REPO_ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
if REPO_ROOT not in sys.path:
    sys.path.insert(0, REPO_ROOT)

from peak.reports.packet_view import (  # noqa: E402
    EFFECTIVE_APPROVED_INTERNAL,
    EFFECTIVE_UNREVIEWED,
    assemble_packet_view,
)

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


def chain(review_target=EV_SOURCE_AVAILABILITY):
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
    return assemble_packet_view(engagement, sources, evidence, reviews)


def main() -> int:
    print("Peak Phase 110 packet-view assembler check")
    print("=" * 45)

    view = chain()
    a = view.evidence_by_id(EV_SOURCE_AVAILABILITY)
    b = view.evidence_by_id(EV_R1_COVERAGE)

    print("\n1. The Phase 94 review links to its target only")
    check("source-availability evidence links the review", a.linked_review_ids == [REVIEW])
    check("source-availability evidence is approved_internal", a.effective_review_status == EFFECTIVE_APPROVED_INTERNAL)
    check("R1 coverage evidence links no review", b.linked_review_ids == [])
    check("R1 coverage evidence is unreviewed", b.effective_review_status == EFFECTIVE_UNREVIEWED)
    check("R1 coverage stored review_status stays needs_review", b.stored_review_status == "needs_review")
    check("the review resolves to exactly one evidence item", [r.linked_evidence_id for r in view.reviews] == [EV_SOURCE_AVAILABILITY])
    check("both evidence items resolve their source", a.source_resolved and b.source_resolved)
    check("no unresolved links", view.unresolved_links == [])

    print("\n2. Finding eligibility is separate from review status")
    check("exactly one finding candidate", len(view.finding_candidates) == 1)
    cand = view.finding_candidates[0]
    check("the candidate is the R1 coverage evidence", cand.evidence_id == EV_R1_COVERAGE)
    check("the candidate is low reliability and unreviewed",
          cand.reliability == "low" and cand.effective_review_status == EFFECTIVE_UNREVIEWED and cand.linked_review_ids == [])
    check("the candidate is internal-draft only, not client-facing", cand.internal_draft_only and not cand.client_facing_allowed)
    check("source-availability evidence is not a finding candidate", not a.finding_candidate_allowed)

    print("\n3. Posture")
    check("recommendations are absent and blocked", view.recommendations == [] and view.recommendations_blocked)
    check("no evidence item or view allows client-facing output",
          not view.client_facing_allowed and not any(e.client_facing_allowed for e in view.evidence))
    check("strict EngagementPacket is reported not valid", view.strict_engagement_packet_valid is False)
    check("client_intake is reported missing", "client_intake" in view.missing_sections)
    check("strict evidence items carry no review field", all("review_status" not in e.schema_item for e in view.evidence))

    print("\n4. Review support is not global")
    moved = chain(review_target=EV_R1_COVERAGE)
    check("retargeted review links only the R1 coverage evidence",
          moved.evidence_by_id(EV_R1_COVERAGE).linked_review_ids == [REVIEW]
          and moved.evidence_by_id(EV_SOURCE_AVAILABILITY).linked_review_ids == [])
    check("source-availability evidence becomes unreviewed when not targeted",
          moved.evidence_by_id(EV_SOURCE_AVAILABILITY).effective_review_status == EFFECTIVE_UNREVIEWED)

    print("\n5. The module imports no database layer")
    probe = ("import sys; import peak.reports.packet_view; "
             "print(any(m == 'sqlalchemy' or m.startswith(('sqlalchemy.', 'peak.db')) for m in sys.modules))")
    out = subprocess.run([sys.executable, "-c", probe], cwd=REPO_ROOT, capture_output=True, text=True, timeout=60)
    check("importing the module loads no sqlalchemy or peak.db", out.returncode == 0 and out.stdout.strip() == "False")

    print("\n" + "=" * 45)
    print("Summary")
    print(f"  failures : {len(_failures)}")
    for label in _failures:
        print(f"    - {label}")
    print("\nRESULT: " + ("FAIL" if _failures else "PASS"))
    return 1 if _failures else 0


if __name__ == "__main__":
    raise SystemExit(main())
