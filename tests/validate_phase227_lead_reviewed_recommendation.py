#!/usr/bin/env python3
"""Phase 227 — Lead-reviewed observation recommendation (offline; temporary SQLite and store only).

Proves:

1. **Eligibility.** Only a discovery finding whose Phase 226 eligibility has no blocker receives a
   recommendation: none when unreviewed, declined, rated low, edited after review, or reviewed in
   another engagement or for another observation; one at medium or high; one again after the Lead
   reviews the revised wording.
2. **Recommendation.** Exactly one per eligible finding, from the Phase 118 template quoting the
   persisted statement, with a deterministic id and content. No model call, no other wording.
3. **Provenance.** The observation and the Lead review, resolvable to reviewer and reliability. No
   evidence, source or review-record id is invented, and the finding is unchanged.
4. **The evidence path.** The Phase 117 rule is byte-identical; an evidence-backed assessment and
   report are pinned to the pre-Phase 227 output; mixed evidence and observation recommendations
   keep their own provenance.
5. **Report and artifacts.** No eligible observation: report pinned to the baseline. An eligible one:
   the recommendation appears in the assessment, the Final Report and both renditions, the wording
   that became false is corrected, client renditions pass the client check, and stored versions
   round-trip. In the app: stored packages are unchanged, the draft goes stale, nothing is approved
   or released automatically, and reads write nothing.

Exit status: 0 all checks passed; 1 a check failed.
"""

from __future__ import annotations

import dataclasses
import hashlib
import os
import re
import subprocess
import sys
import tempfile
from types import SimpleNamespace

REPO_ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
TESTS = os.path.join(REPO_ROOT, "tests")
for p in (REPO_ROOT, TESTS):
    if p not in sys.path:
        sys.path.insert(0, p)

import validate_phase220_guided_evidence_capture as p220  # noqa: E402  (shared fixtures)
import validate_phase223_phase_work_record as p223  # noqa: E402
import validate_phase226_observation_lead_review as p226  # noqa: E402

BASELINE = "ea1a629"
STATEMENT = "Receipts are keyed a day late."
#: Assessment Markdown, Final Report Markdown and content hash prefixes rendered by the baseline code
#: (``ea1a629``) for an eligible evidence-backed finding beside discovery with no Lead review, and
#: with a declined one.
BASELINE_HASHES = {
    "evidence": ("b532d73d339d0928", "95f02d50691a1ada", "fcc17de15801b944"),
    "evidence_declined": ("ef21a81864c84b49", "95f02d50691a1ada", "fcc17de15801b944"),
}
_failures = []


def check(label, ok):
    print(f"  [{'PASS' if ok else 'FAIL'}] {label}")
    if not ok:
        _failures.append(label)


read, code = p220.read, p220.code
_review, _summaries = p226._review, p226._summaries


def _inputs(eligible=True):
    """Phase 111 reporting inputs with one evidence-backed finding."""
    finding = SimpleNamespace(
        finding_candidate_id="fc_1", cited_evidence_id="evid_1",
        finding_statement="Bin labels do not match the WMS location.", source_reference_id="src_1",
        effective_review_status="approved_internal", stored_review_status="approved_internal",
        review_support_refs=["rev_1"], reliability="medium", claim_scope="operational_finding",
        recommendation_eligible=eligible, recommendation_blocked_reasons=[] if eligible else ["x"])
    return SimpleNamespace(
        engagement={"engagement_id": "e1", "client_id": "c1", "owner_id": "peak_consultants",
                    "authorization_scope": "engagement_authorized"},
        audience="internal", client_facing_allowed=False,
        recommendations_blocked_reasons=[] if eligible else ["no eligible evidence"],
        finding_inputs=[finding], excluded_evidence=[], strict_engagement_packet_reasons=[],
        missing_sections=[])


def _assess(reviews, inputs=None, outside=True):
    from peak.reports.discovery_assessment import build_discovery_assessment_context
    from peak.reports.internal_assessment import build_internal_assessment

    return build_internal_assessment(inputs or _inputs(eligible=False),
                                     build_discovery_assessment_context(_summaries(outside, reviews)))


def _hashes(assessment):
    from peak.reports.final_report import compose_final_report, render_final_report_markdown
    from peak.reports.internal_assessment import render_internal_assessment_markdown
    from peak.workspace.approvals import report_content_hash

    h = lambda s: hashlib.sha256(s.encode()).hexdigest()[:16]  # noqa: E731
    report = compose_final_report(assessment, {"id": "e1", "engagement_label": "L"})
    return (h(render_internal_assessment_markdown(assessment)),
            h(render_final_report_markdown(report)), report_content_hash(report)[:16])


def pinned_scenarios():
    """The scenarios whose output must equal the baseline's. Also run against the baseline tree."""
    return {"evidence": _assess([], _inputs()),
            "evidence_declined": _assess([_review(decision="decline", reliability=None)], _inputs())}


# --------------------------------------------------------------------------- 1-3. rule


def rule_checks():
    print("\n[1. eligibility: only a Phase 226-eligible observation]")
    from peak.reports.internal_assessment import RECOMMENDATION_TEMPLATE

    def recs(reviews, **kw):
        return [r for r in _assess(reviews, **kw).recommendations if r.supporting_observation_ids]

    check("unreviewed: none", recs([]) == [])
    check("declined: none", recs([_review(decision="decline", reliability=None)]) == [])
    check("approved at low reliability: none", recs([_review(reliability="low")]) == [])
    check("approved at medium: one", len(recs([_review()])) == 1)
    check("approved at high: one", len(recs([_review(reliability="high")])) == 1)
    check("the observation changed after review: none",
          recs([_review(statement="Receipts are keyed late.")]) == [])
    check("a review in another engagement, or of another observation: none",
          recs([_review(engagement="e2")]) == [] and recs([_review(observation="dobs_b")]) == [])
    edited = [_review(statement="Receipts are keyed late."),
              _review(2, statement=STATEMENT)]
    check("a new qualifying review of the revised statement: one, from the current review",
          [r.supporting_lead_review_ids for r in recs(edited)] == [["olr_dobs_a_2"]])
    check("a decline after an approval removes it",
          recs([_review(), _review(2, decision="decline", reliability=None)]) == [])

    print("\n[2. recommendation: the Phase 118 template, bounded, deterministic]")
    one = recs([_review()])
    both = recs([_review(), _review(observation="dobs_b",
                                    statement="Cycle counts skip the overflow bay.", reviewer="c1")])
    check("exactly one per eligible observation finding",
          [r.finding_id for r in both] == ["disc_dobs_a", "disc_dobs_b"])
    check("the same records give the same id and content",
          [dataclasses.asdict(r) for r in recs([_review()])] == [dataclasses.asdict(r) for r in one]
          and one[0].recommendation_id == "rec_disc_dobs_a")
    check("the text is the Phase 118 template around the exact persisted statement",
          one[0].text == RECOMMENDATION_TEMPLATE.format(statement=STATEMENT)
          and one[0].text.endswith(f'"{STATEMENT}"'))
    line = f"RECOMMENDATION_TEMPLATE = {RECOMMENDATION_TEMPLATE!r}"
    base = subprocess.run(["git", "show", f"{BASELINE}:peak/reports/internal_assessment.py"],
                          cwd=REPO_ROOT, capture_output=True, text=True).stdout
    check("the template is the one Phase 118 defined, unchanged and not duplicated",
          line in base and read("peak/reports/internal_assessment.py").count("RECOMMENDATION_TEMPLATE =")
          == 1 and "corrective action" not in read("peak/reports/final_report.py"))
    words = one[0].text.replace(STATEMENT, "").lower()
    check("no root cause, prescribed action, ROI, cost, priority, timeline or severity",
          not re.search(r"root cause|because|roi\b|cost|priority|timeline|deadline|severity|"
                        r"critical|implement|install|replace", words))
    check("internal only and requires human review",
          one[0].internal_only is True and one[0].requires_human_review is True)
    for path in ("peak/reports/internal_assessment.py", "peak/reports/final_report.py",
                 "peak/reports/release_presentation.py"):
        check(f"{os.path.basename(path)} imports no model client",
              not re.search(r"^\s*(import|from)\s+\S*(anthropic|openai|peak\.agents|llm)",
                            read(path), re.M | re.I))

    print("\n[3. provenance: the observation and its Lead review, never evidence]")
    a = _assess([_review()])
    rec = [r for r in a.recommendations if r.supporting_observation_ids][0]
    e = {x.finding_id: x for x in a.discovery.recommendation_eligibility}[rec.finding_id]
    check("observation and Lead review identity retained",
          rec.supporting_observation_ids == ["dobs_a"]
          and rec.supporting_lead_review_ids == ["olr_dobs_a_1"])
    check("reviewer and reliability resolve from the review it names",
          e.lead_review.review_id == rec.supporting_lead_review_ids[0]
          and e.lead_review.reviewer == "Cam" and e.lead_review.reliability == "medium")
    check("no evidence, source or review-record id is invented",
          rec.supporting_evidence_ids == [] and rec.supporting_source_ids == []
          and rec.supporting_review_ids == [])
    check("the observation does not become an evidence-backed finding",
          [f.finding_id for f in a.findings] == ["fc_1"])
    plain = _assess([])
    check("the discovery finding is unchanged by its review and recommendation",
          [dataclasses.asdict(f) for f in a.discovery.findings]
          == [dataclasses.asdict(f) for f in plain.discovery.findings])


# --------------------------------------------------------------------------- 4. evidence path


def evidence_checks():
    print("\n[4. the evidence path is unchanged]")
    base = subprocess.run(["git", "show", f"{BASELINE}:peak/reports/packet_view_report.py"],
                          cwd=REPO_ROOT, capture_output=True, text=True)
    check("the Phase 117 eligibility rule is byte-identical to the baseline",
          base.returncode == 0 and base.stdout == read("peak/reports/packet_view_report.py"))
    for name, assessment in pinned_scenarios().items():
        check(f"{name}: assessment, report and content hash equal the baseline's",
              _hashes(assessment) == BASELINE_HASHES[name])
    mixed = _assess([_review()], _inputs())
    ev, ob = mixed.recommendations
    check("mixed: the evidence recommendation first, then the observation's",
          (ev.recommendation_id, ob.recommendation_id) == ("rec_fc_1", "rec_disc_dobs_a")
          and mixed.recommendation_status == "internal_draft")
    check("mixed: each keeps only its own provenance",
          ev.supporting_evidence_ids == ["evid_1"] and ev.supporting_review_ids == ["rev_1"]
          and ev.supporting_observation_ids == [] and ev.supporting_lead_review_ids == []
          and ob.supporting_evidence_ids == [] and ob.supporting_observation_ids == ["dobs_a"])
    blocked = _assess([_review()], _inputs(eligible=False))
    check("an observation recommendation lifts the global block; the evidence finding stays blocked",
          blocked.recommendation_status == "internal_draft" and len(blocked.recommendations) == 1
          and blocked.findings[0].recommendation_id is None)


# --------------------------------------------------------------------------- 5. report


def report_checks():
    print("\n[5. the Final Report and its renditions]")
    from peak.reports import final_report as fr
    from peak.reports.discovery_assessment import (
        RECOMMENDED_TAIL, build_discovery_assessment_context,
    )
    from peak.reports.final_report_docx import render_final_report_docx
    from peak.reports.final_report_html import render_final_report_html
    from peak.reports.internal_assessment import (
        InternalAssessment, render_internal_assessment_markdown,
    )
    from peak.reports.release_presentation import (
        client_presentation, client_presentation_problems, rendition_text,
    )
    from peak.workspace.approvals import report_content_hash
    from peak.workspace.artifacts import final_report_content, final_report_from_content

    for outside in (False, True):
        a = InternalAssessment(engagement_id="e1",
                               discovery=build_discovery_assessment_context(_summaries(outside, [])))
        check(f"no Lead review ({'outside' if outside else 'interviews only'}): pinned to the "
              f"Phase 226 baseline", _hashes(a) == p226.BASELINE_HASHES[outside])

    a = _assess([_review()])
    report = fr.compose_final_report(a, {"id": "e1", "engagement_label": "L"})
    md = fr.render_final_report_markdown(report)
    amd = render_internal_assessment_markdown(a)
    rec_text = fr.RECOMMENDATIONS_TITLE_LEAD_REVIEWED
    check("the assessment lists the recommendation with its observation and Lead review",
          "### rec_disc_dobs_a — for disc_dobs_a" in amd
          and "- Consultant observation: dobs_a (not evidence)" in amd
          and "- Lead review: olr_dobs_a_1" in amd and "- Internal recommendation: rec_disc_dobs_a"
          in amd)
    check("the Final Report carries it in the recommendations section, named as an observation",
          [r.recommendation_id for r in report.recommendations.recommendations] == ["rec_disc_dobs_a"]
          and f"## {rec_text}" in md
          and "consultant observation dobs_a (not evidence), Lead review olr_dobs_a_1" in md)
    check("the observation stays under discovery, never under evidence-backed findings",
          [f.finding_id for f in report.evidence_findings.findings] == ["fc_1"]
          and [f.finding_id for f in report.discovery_summary.findings] == ["disc_dobs_a", "disc_dobs_b"]
          and "Discovery summary (consultant working material)" in md)
    check("the wording that became false is gone; the corrected wording is present",
          "carries no review status, reliability rating, or recommendation eligibility" not in md
          and "no reliability rating, and no recommendation eligibility" not in md
          and "evidence-backed only" not in md and RECOMMENDED_TAIL in md
          and fr.LEAD_REVIEWED_BOUNDARY in md and fr.RECOMMENDATIONS_BOUNDARY_LEAD_REVIEWED in md
          and report.recommendations.material == fr.MATERIAL_GOVERNED_RECOMMENDATIONS)
    check("ordinary discovery is still described as consultant working material, not evidence",
          "It is not reviewed evidence." in md and "it never becomes evidence" in md)
    check("still an internal draft: not client-facing, not approved",
          report.client_facing is False and report.approved_for_client is False)
    unrev = fr.compose_final_report(_assess([]), {"id": "e1", "engagement_label": "L"})
    check("the content hash changes only because the recommendation appears",
          report_content_hash(report) != report_content_hash(unrev))

    content = final_report_content(report)
    check("a stored version round-trips, with its provenance",
          final_report_content(final_report_from_content(content)) == content
          and content["recommendations"]["recommendations"][0]["supporting_lead_review_ids"]
          == ["olr_dobs_a_1"])
    ev_content = final_report_content(fr.compose_final_report(_assess([], _inputs()), {"id": "e1"}))
    check("evidence-backed content omits the new fields, so earlier versions rebuild exactly",
          all("supporting_observation_ids" not in r and "supporting_lead_review_ids" not in r
              for r in ev_content["recommendations"]["recommendations"])
          and final_report_content(final_report_from_content(ev_content)) == ev_content)

    stored = final_report_from_content(content)
    internal = {"web": render_final_report_html(stored), "docx": render_final_report_docx(stored)}
    client = {"web": render_final_report_html(stored, client_presentation(stored)),
              "docx": render_final_report_docx(stored, client_presentation(stored))}
    check("both internal renditions carry the recommendation and its observation provenance",
          all(STATEMENT in rendition_text(k, v) and "olr_dobs_a_1" in rendition_text(k, v)
              and "(not evidence)" in rendition_text(k, v) for k, v in internal.items()))
    check("client renditions pass the client check and name the source without ids",
          client_presentation_problems(client, content) == []
          and all("approved by the engagement lead; not evidence" in rendition_text(k, v)
                  and "Recommendations (evidence-backed or lead-reviewed)" in rendition_text(k, v)
                  for k, v in client.items()))


# --------------------------------------------------------------------------- 6. app


def app_checks(tmp):
    print("\n[6. in the app: packages, approvals, state]")
    import sqlite3

    app, factory, store, client, db = p220._setup(tmp)
    lee, cam = client("lee"), client("cam")
    cam_id = cam.get("/auth/me").json()["consultant"]["id"]
    pid, phase = p220._phase(lee, "Alpha")
    eid = phase["engagement_id"]
    task = phase["tasks"][0]
    text = "Receipts are keyed a day late because the dock log is on paper."
    oid = cam.post(f"/tasks/{task['id']}/observations",
                   json={"observation_text": text, "basis": "observed"}).json()["observation"]["id"]
    assert lee.patch(f"/engagements/{eid}", json={"assigned_consultant_id": cam_id}).status_code == 200

    def review(**kw):
        s = cam.get(f"/observations/{oid}/lead-review").json()["lead_review"]
        body = {"decision": "approve_internal", "reliability": "medium",
                "statement_hash": s["statement_hash"],
                "current_review_id": s["history"][0]["review_id"] if s["history"] else None}
        body.update(kw)
        return cam.post(f"/observations/{oid}/lead-review", json=body)

    def recs():
        return cam.get(f"/engagements/{eid}/assessment").json()["assessment"]["recommendations"]

    def lead_rows():
        con = sqlite3.connect(db)
        rows = con.execute("SELECT * FROM observation_lead_reviews ORDER BY review_number").fetchall()
        con.close()
        return rows

    check("before any review: no recommendation", recs() == [])
    assert lee.post(f"/engagements/{eid}/final-report/packages", json={}).status_code == 201
    pkgs_before = lee.get(f"/engagements/{eid}/final-report/packages").json()["review"]
    readiness = cam.get(f"/phases/{pid}/readiness").json()
    check("the package prepared before the review matches the draft",
          pkgs_before["draft_matches_latest"] is True)
    assert review().status_code == 200
    rows = lead_rows()
    snap = p223._snapshot(db)
    a = cam.get(f"/engagements/{eid}/assessment").json()
    r = cam.get(f"/engagements/{eid}/final-report").json()
    docx = cam.get(f"/engagements/{eid}/final-report.docx")
    pkgs_after = lee.get(f"/engagements/{eid}/final-report/packages").json()["review"]
    check("reads write nothing", p223._snapshot(db) == snap)
    rec = a["assessment"]["recommendations"]
    check("the assessment has exactly one recommendation, tracing to the observation and review",
          len(rec) == 1 and rec[0]["recommendation_id"] == f"rec_disc_{oid}"
          and rec[0]["supporting_observation_ids"] == [oid]
          and rec[0]["supporting_lead_review_ids"] == [rows[0][0]]
          and rec[0]["text"].endswith(f'"{text}"')
          and a["assessment"]["recommendation_status"] == "internal_draft")
    check("the Final Report carries it, and the DOCX export renders",
          [x["recommendation_id"] for x in r["report"]["recommendations"]["recommendations"]]
          == [f"rec_disc_{oid}"] and docx.status_code == 200)
    check("the stored package is unchanged; the draft no longer matches it",
          pkgs_after["packages"] == pkgs_before["packages"]
          and pkgs_after["draft_matches_latest"] is False)
    check("nothing was approved or released automatically",
          all(p["lead_decision"] is None and p["final_decision"] is None
              for p in pkgs_after["packages"]))
    check("the observation, the Lead review row, readiness, tasks and phases are unchanged",
          cam.get(f"/observations/{oid}").json()["observation"]["observation_text"] == text
          and lead_rows() == rows and cam.get(f"/phases/{pid}/readiness").json() == readiness)
    created = lee.post(f"/engagements/{eid}/final-report/packages", json={})
    pkgs_new = lee.get(f"/engagements/{eid}/final-report/packages").json()["review"]
    newest = pkgs_new["packages"][0]
    check("a new package holds the recommendation; it starts unapproved, intact, client-clean",
          created.status_code == 201 and pkgs_new["draft_matches_latest"] is True
          and newest["lead_decision"] is None and newest["final_decision"] is None
          and newest["hash_verified"] is True and newest["client_problems"] == []
          and newest["content_hash"] != pkgs_before["packages"][0]["content_hash"])

    cam.patch(f"/observations/{oid}", json={"observation_text": text + " Since March."})
    check("an edit after review removes the recommendation until a new review", recs() == [])
    assert review().status_code == 200
    again = recs()
    check("the Lead reviews the new wording: one recommendation, same id, new text and review",
          len(again) == 1 and again[0]["recommendation_id"] == f"rec_disc_{oid}"
          and again[0]["text"].endswith('Since March."')
          and again[0]["supporting_lead_review_ids"] == [lead_rows()[-1][0]])
    con = sqlite3.connect(db)
    governed = con.execute("SELECT (SELECT COUNT(*) FROM evidence_references) + "
                           "(SELECT COUNT(*) FROM review_records)").fetchone()[0]
    con.close()
    check("nothing is written to the governed evidence path", governed == 0)


# --------------------------------------------------------------------------- 7. static


def static_checks():
    print("\n[7. static]")
    check("no migration after 026", sorted(f for f in os.listdir(os.path.join(REPO_ROOT, "alembic",
                                                                              "versions"))
                                           if f.endswith(".py"))[-1]
          == "026_observation_lead_reviews.py")
    check("no new table, allowlist action or write in the report path",
          not any(re.search(r"_require_allowed|session\.add|\.commit\(", read(p))
                  for p in ("peak/reports/internal_assessment.py", "peak/reports/final_report.py",
                            "peak/reports/release_presentation.py")))
    check("the web shows the observation source and the governed label",
          "fromLeadReviewedObservation" in read("web/components/final-report-view.tsx")
          and "fromLeadReviewedObservation" in read("web/components/assessment-view.tsx")
          and "Governed · evidence-backed or Lead-reviewed" in read("web/components/assessment-view.tsx"))
    check("the Phase 227 target is in make validate",
          re.search(r"^validate: .*\bvalidate-phase227\b", read("Makefile"), re.M) is not None)


def main() -> int:
    print("Peak Phase 227 Lead-reviewed observation recommendation check")
    print("=" * 61)
    try:
        import argon2, fastapi, httpx, itsdangerous, multipart, sqlalchemy  # noqa: F401,E401
    except ImportError:
        print("  [skip] web dependencies not installed — run with PYTHON=.venv/bin/python")
        return 0
    rule_checks()
    evidence_checks()
    report_checks()
    with tempfile.TemporaryDirectory(prefix="peak_phase227_") as tmp:
        app_checks(tmp)
    static_checks()

    print("\nSummary")
    print(f"  failures : {len(_failures)}")
    print("RESULT: " + ("PASS" if not _failures else "FAIL"))
    return 0 if not _failures else 1


if __name__ == "__main__":
    sys.exit(main())
