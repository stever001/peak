#!/usr/bin/env python3
"""Phase 113 check — persisted-state summaries drive the packet-view reporting route.

Stdlib-only and **database-free**: the fetch layer's *shape* is exercised with in-memory summaries
built to match what a read-only ``SELECT`` of whitelisted columns returns. No connection is opened,
no fixture database is created, and no row body appears here — only ids, statuses, relationship
keys, and the caller-supplied claim scopes the database has no column for.

Asserts that:

* fetched-shaped summaries feed ``assemble_packet_view`` unchanged;
* target-specific review support survives the persisted-state adapter — the Phase 94 review targets
  only the Phase 93 evidence, and the Phase 107 evidence stays unreviewed with its stored status
  reported separately;
* report inputs cite the Phase 107 finding and its source only;
* planner references carry the same target, so planner and packet view agree;
* ``claim_scope`` is caller-supplied, is refused when unrecognised, and is refused for a row whose
  persisted areas are unspecified;
* recommendations, client-facing output, and a strict ``EngagementPacket`` stay blocked;
* the read module selects whitelisted columns only, never a narrative body, and issues no write;
* the adapter loads no SQLAlchemy and no ``peak.db``.

Exit status: 0 -> all checks passed; 1 -> a check failed.
"""

from __future__ import annotations

import dataclasses
import os
import re
import subprocess
import sys

REPO_ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
if REPO_ROOT not in sys.path:
    sys.path.insert(0, REPO_ROOT)

from peak.agents.executor import MockAgentExecutor  # noqa: E402
from peak.reports import (  # noqa: E402
    InternalAssessmentReportPlanRequest as Req,
    prepare_internal_assessment_report_plan as plan_it,
)
from peak.reports.persisted_packet_view import (  # noqa: E402
    ClaimScopePolicy,
    build_persisted_packet_view,
    build_persisted_planner_references,
    build_persisted_report_inputs,
)

_failures = []

ENG, SRC = "lab_internal_test_001", "ing_d67b76327aba4add"
EV_SOURCE_AVAILABILITY = "evid_f094cbe4b47d4048"   # Phase 93 — record existence only
EV_R1_COVERAGE = "evid_8151dad609974ea0"           # Phase 107 — the operational claim
REVIEW = "rev_70b5da9f14d54488"                    # Phase 94 — targets the Phase 93 evidence
IDENTITY = {"owner_id": "peak_internal_admin", "client_id": "99999", "engagement_id": ENG,
            "authorization_scope": "internal_peak_only"}

READER = os.path.join("peak", "db", "engagement_packet_reader.py")
ADAPTER = os.path.join("peak", "reports", "persisted_packet_view.py")


def check(label, ok):
    print(f"  [{'PASS' if ok else 'FAIL'}] {label}")
    if not ok:
        _failures.append(label)


def read(rel):
    with open(os.path.join(REPO_ROOT, rel), encoding="utf-8") as handle:
        return handle.read()


def fetched(review_target=EV_SOURCE_AVAILABILITY, areas=True):
    """Summaries shaped exactly as the whitelisted SELECTs return them — no row bodies."""
    def evidence(evidence_id, operational_area, process_area):
        return {**IDENTITY, "evidence_id": evidence_id, "evidence_type": "other",
                "source_type": "other", "reliability": "low", "evidence_status": "collected",
                "review_status": "needs_review", "output_status": "draft",
                "lifecycle_status": "active", "sensitive_data_flag": False,
                "source_reference_id": SRC, "operational_area": operational_area,
                "inventory_process_area": process_area}

    return {
        "engagement": {"engagement_id": ENG, "client_id": "99999",
                       "owner_id": "peak_internal_admin",
                       "authorization_scope": "internal_peak_only",
                       "engagement_category": "internal_test", "real_client_data": False,
                       "client_accessible": False, "capsule_publication_authorized": False,
                       "status": None, "review_status": "needs_review",
                       "lifecycle_status": "active"},
        "sources": [{**IDENTITY, "source_ingestion_id": SRC,
                     "source_reference_id": "pkt_lab_measurement_001",
                     "review_status": "needs_review", "output_status": "draft",
                     "lifecycle_status": "active"}],
        "evidence": [evidence(EV_R1_COVERAGE, "inventory" if areas else "unspecified",
                              "on_hand_attribution" if areas else "unspecified"),
                     evidence(EV_SOURCE_AVAILABILITY, "unspecified", "unspecified")],
        "reviews": [{**IDENTITY, "review_id": REVIEW, "target_id": review_target,
                     "subject_record_type": "evidence_reference", "decision": "approve_internal",
                     "review_status": "approved_internal", "new_status": "approved_internal",
                     "authoritative": False, "output_status": "draft",
                     "lifecycle_status": "active"}],
    }


POLICY = ClaimScopePolicy(
    claim_scopes={EV_R1_COVERAGE: "operational_finding",
                  EV_SOURCE_AVAILABILITY: "source_availability_only"})


def main() -> int:
    print("Peak Phase 113 persisted-state reporting path check")
    print("=" * 56)

    summaries = fetched()
    view = build_persisted_packet_view(summaries, POLICY)

    print("\n1. Fetched-shaped summaries assemble into a packet view")
    check("the engagement identity comes from the fetched row",
          view.engagement["engagement_id"] == ENG and view.engagement["client_id"] == "99999"
          and view.engagement["owner_id"] == "peak_internal_admin"
          and view.engagement["authorization_scope"] == "internal_peak_only")
    check("no fetched record is excluded for identity mismatch", view.excluded_record_ids == [])
    check("both evidence rows resolve to the fetched source",
          [e.source_reference_id for e in view.evidence] == [SRC, SRC]
          and all(e.source_resolved for e in view.evidence))
    check("the fetched source is carried as its own section",
          [s["source_ingestion_id"] for s in view.sources] == [SRC])
    check("no link is left unresolved", view.unresolved_links == [])

    print("\n2. Target-specific review support survives the adapter")
    reviewed = view.evidence_by_id(EV_SOURCE_AVAILABILITY)
    unreviewed = view.evidence_by_id(EV_R1_COVERAGE)
    check("the Phase 94 review links only to the Phase 93 evidence",
          reviewed.linked_review_ids == [REVIEW] and unreviewed.linked_review_ids == [])
    check("the Phase 107 evidence is unreviewed", unreviewed.effective_review_status == "unreviewed")
    check("its stored review status is reported separately and unchanged",
          unreviewed.stored_review_status == "needs_review")
    check("the reviewed row's stored status is also unchanged",
          reviewed.stored_review_status == "needs_review"
          and reviewed.effective_review_status == "approved_internal")
    check("only the operational-finding row is a candidate",
          [c.evidence_id for c in view.finding_candidates] == [EV_R1_COVERAGE])

    print("\n3. Report inputs cite the Phase 107 finding and its source only")
    inputs = build_persisted_report_inputs(summaries, POLICY)
    check("exactly one finding input", len(inputs.finding_inputs) == 1)
    finding = inputs.finding_inputs[0]
    check("it cites evid_8151dad609974ea0", finding.cited_evidence_id == EV_R1_COVERAGE)
    check("it references ing_d67b76327aba4add", finding.source_reference_id == SRC)
    check("the Phase 94 review gives it no support", finding.review_support_refs == [])
    check("it stays unreviewed and low reliability",
          finding.effective_review_status == "unreviewed" and finding.reliability == "low")
    check("the source-availability row backs no finding",
          [x.evidence_id for x in inputs.excluded_evidence] == [EV_SOURCE_AVAILABILITY]
          and "source availability only" in inputs.excluded_evidence[0].reason)
    task = inputs.report_task_request
    check("the reporting agent receives only finding-backed record ids",
          task is not None and task.input_record_ids == [EV_R1_COVERAGE, SRC])
    check("no live LLM, resolver context, or client-facing output is requested",
          not task.llm_execution_allowed and not task.resolver_context_allowed
          and not task.client_facing_output_requested)
    result = MockAgentExecutor().execute(task)
    check("the existing executor plans the run and executes nothing",
          result.permitted and result.status == "planned_mock_no_execution"
          and not result.database_write_made and not result.llm_call_made
          and not result.agentnet_call_made and not result.resolver_context_used
          and not result.client_facing_output_created)

    print("\n4. Planner references agree with the packet view")
    refs = build_persisted_planner_references(summaries, POLICY)
    review_ref = refs.review_record_ids[0]
    check("the review reference targets only its actual target",
          review_ref.record_id == REVIEW and review_ref.target_record_ids == [EV_SOURCE_AVAILABILITY])
    check("evidence references carry the policy's claim scopes",
          {r.record_id: r.claim_scope for r in refs.evidence_reference_ids}
          == {EV_R1_COVERAGE: "operational_finding",
              EV_SOURCE_AVAILABILITY: "source_availability_only"})
    check("references carry the fetched identity",
          all(r.owner_id == "peak_internal_admin" and r.client_id == "99999"
              and r.engagement_id == ENG and r.authorization_scope == "internal_peak_only"
              for r in refs.evidence_reference_ids + refs.review_record_ids
              + refs.source_ingestion_refs))
    plan = plan_it(Req(**IDENTITY, requested_by="peak_internal_admin",
                       requester_role="internal_admin", report_plan_id="rpt_plan_phase113",
                       source_ingestion_refs=list(refs.source_ingestion_refs),
                       evidence_reference_ids=list(refs.evidence_reference_ids),
                       review_record_ids=list(refs.review_record_ids)))
    check("the planner accepts the references", plan.outcome == "planned" and plan.report_plan)
    candidates = plan.report_plan.finding_candidates
    check("the planner plans one finding slot, for the Phase 107 evidence",
          len(candidates) == 1 and candidates[0].evidence_support_refs == [EV_R1_COVERAGE])
    check("planner and packet view agree the Phase 94 review supports no finding",
          not candidates[0].review_support_refs and finding.review_support_refs == [])

    print("\n5. claim_scope is caller-supplied, and the persisted areas can only refuse")
    none_supplied = build_persisted_packet_view(summaries, None)
    check("no policy means no finding candidate", none_supplied.finding_candidates == [])
    check("the view records that claim_scope is not a stored field",
          any("claim_scope is not a stored field" in w for w in none_supplied.warnings))
    check("the view records that summary text was not read",
          any("summary text is not a stored field" in w for w in none_supplied.warnings))
    guarded = build_persisted_packet_view(
        summaries, ClaimScopePolicy(claim_scopes={EV_SOURCE_AVAILABILITY: "operational_finding"}))
    check("operational_finding is refused when both persisted areas are unspecified",
          guarded.finding_candidates == []
          and any("areas are both unspecified" in w for w in guarded.warnings))
    unknown = build_persisted_packet_view(
        summaries, ClaimScopePolicy(claim_scopes={EV_R1_COVERAGE: "financially_verified"}))
    check("an unrecognised claim scope is refused",
          unknown.finding_candidates == []
          and any("is not a recognised scope" in w for w in unknown.warnings))
    check("with no caller summary the view reports the text as not supplied",
          any("evidence summary text (not supplied)" in s for s in view.missing_sections)
          and view.evidence_by_id(EV_R1_COVERAGE).schema_item.get("summary") is None)
    summarised = build_persisted_packet_view(
        summaries, ClaimScopePolicy(claim_scopes=POLICY.claim_scopes,
                                    summaries={EV_R1_COVERAGE: "internal coverage note",
                                               EV_SOURCE_AVAILABILITY: "internal existence note"}))
    check("a caller-supplied summary is passed through, never invented",
          summarised.evidence_by_id(EV_R1_COVERAGE).schema_item["summary"] == "internal coverage note"
          and not any("summary text (not supplied)" in s for s in summarised.missing_sections))

    print("\n6. Posture stays blocked")
    check("recommendations are empty and blocked",
          inputs.recommendations == [] and inputs.recommendations_blocked
          and inputs.recommendations_blocked_reasons)
    check("the finding is not recommendation-eligible",
          not finding.recommendation_eligible and finding.recommendation_blocked_reasons)
    check("nothing is client-facing",
          not inputs.client_facing_allowed and not finding.client_facing_allowed
          and not view.client_facing_allowed)
    check("the strict EngagementPacket stays insufficient, with reasons",
          inputs.strict_engagement_packet_valid is False
          and any("client_intake" in r for r in inputs.strict_engagement_packet_reasons))
    check("client_intake is reported missing", "client_intake" in inputs.missing_sections)

    print("\n7. The read layer is read-only and selects no body")
    reader = read(READER)
    check("the read module issues no INSERT / UPDATE / DELETE",
          not re.search(r"\b(insert|update|delete)\s*\(", reader, re.IGNORECASE))
    check("it imports no writer and creates no session or engine",
          not re.search(r"\b(persist_\w+|\w+_writer|create_session_factory|create_engine|sessionmaker)\b",
                        reader))
    check("it reads no environment variable and holds no URL",
          "os.environ" not in reader and "getenv" not in reader and "://" not in reader)
    check("it selects no narrative column",
          not re.search(r"\b(EvidenceReference|ReviewRecord|Engagement|SourceIngestionRecord)\."
                        r"(summary|reason|engagement_label|location_descriptor)\b", reader))
    check("it extracts only the three whitelisted details_json keys",
          re.findall(r'details\["([a-z_]+)"\]', reader)
          == ["source_reference_id", "operational_area", "inventory_process_area"])
    check("it reuses the Phase 57 read-isolation primitive",
          "engagement_read_isolation" in reader and "is_visible_in_mode" in reader)
    check("it refuses an engagement that is not visible in the requested mode",
          "EngagementNotVisible" in reader)
    check("it hard-codes no engagement, evidence, source, or review id",
          not re.search(r"\b(lab_internal_test_001|evid_[0-9a-f]{8,}|ing_[0-9a-f]{8,}|rev_[0-9a-f]{8,})\b",
                        reader))
    adapter = read(ADAPTER)
    check("the adapter hard-codes no record id",
          not re.search(r"\b(lab_internal_test_001|evid_[0-9a-f]{8,}|ing_[0-9a-f]{8,}|rev_[0-9a-f]{8,})\b",
                        adapter))
    probe = ("import sys; import peak.reports.persisted_packet_view; "
             "print(any(m == 'sqlalchemy' or m.startswith(('sqlalchemy.', 'peak.db')) "
             "for m in sys.modules))")
    out = subprocess.run([sys.executable, "-c", probe], cwd=REPO_ROOT, capture_output=True,
                         text=True, timeout=60)
    check("importing the adapter loads no sqlalchemy or peak.db",
          out.returncode == 0 and out.stdout.strip() == "False")

    print("\n8. Deterministic")
    check("the same summaries yield the same report inputs",
          dataclasses.asdict(build_persisted_report_inputs(fetched(), POLICY))
          == dataclasses.asdict(inputs))
    check("a different review target moves support with it",
          build_persisted_report_inputs(fetched(review_target=EV_R1_COVERAGE),
                                        POLICY).finding_inputs[0].review_support_refs == [REVIEW])

    print("\n" + "=" * 56)
    print("Summary")
    print(f"  failures : {len(_failures)}")
    for label in _failures:
        print(f"  - {label}")
    print("\nRESULT: " + ("PASS" if not _failures else "FAIL"))
    return 1 if _failures else 0


if __name__ == "__main__":
    raise SystemExit(main())
