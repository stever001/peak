#!/usr/bin/env python3
"""Phase 208 Final Report foundation check (offline; temporary SQLite only).

Proves:

1. the report composes from the existing internal assessment;
2. the North Star appears;
3. discovery and evidence sections remain distinct;
4. low-hanging-fruit grouping is not presented as scoring or ranking;
5. only already-eligible recommendations appear;
6. an engagement with sparse or no discovery still renders;
7. the endpoint is read-only;
8. no migration and no new persistence.

No network, no credential, no client data, no production contact.

Exit status: 0 all checks passed; 1 a check failed.
"""

from __future__ import annotations

import ast
import dataclasses
import os
import subprocess
import sys
import tempfile

REPO_ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
for _p in (REPO_ROOT, os.path.join(REPO_ROOT, "tools")):
    if _p not in sys.path:
        sys.path.insert(0, _p)

_failures = []
SECRET = "phase208-test-secret-" + "x" * 32
PASSWORD = "consultant-pw-208"
NORTH_STAR = "Cut inventory discrepancies in half"
OBSERVATION = "Receiving staff record counts on paper and enter them a day later."
FRUIT = "Cycle counts are scheduled but skipped during peak weeks."
UNFLAGGED = "No single owner for stock accuracy across the two sites."
RANKING_KEYS = {"rank", "ranking", "score", "priority", "roi", "position", "tier"}


def check(label, ok):
    print(f"  [{'PASS' if ok else 'FAIL'}] {label}")
    if not ok:
        _failures.append(label)


def _keys(value):
    """Every dict key anywhere in a JSON-shaped value."""
    if isinstance(value, dict):
        return set(value) | {k for v in value.values() for k in _keys(v)}
    if isinstance(value, list):
        return {k for v in value for k in _keys(v)}
    return set()


def _section(markdown, title):
    """The Markdown between one ``## `` heading and the next."""
    start = markdown.index(f"## {title}")
    end = markdown.find("\n## ", start + 1)
    return markdown[start:end if end != -1 else len(markdown)]


def no_new_persistence_checks():
    print("\n[8. no migration, no new persistence]")
    versions = os.listdir(os.path.join(REPO_ROOT, "alembic", "versions"))
    # A claim about this phase only (Phase 121 convention): it holds while this harness is being
    # authored. Phase 212 legitimately adds 018_artifact_versions.
    import _schema_history as schema_history

    if schema_history.phase_never_committed(REPO_ROOT, "tests/validate_phase208_final_report_foundation.py"):
        check("no migration 018 was added", not any(v.startswith("018") for v in versions))
    check("migration history is still one linear chain", bool(schema_history.migration_chain(REPO_ROOT)))

    from peak.persistence import allowlist

    check("no allowlist action mentions a report",
          not any("report" in action and "final" in action
                  for _, action in allowlist.WORKSPACE_WRITE_COLUMNS))

    path = os.path.join(REPO_ROOT, "peak/reports/final_report.py")
    tree = ast.parse(open(path).read())
    imported = set()
    for node in ast.walk(tree):
        if isinstance(node, ast.Import):
            imported.update(a.name for a in node.names)
        elif isinstance(node, ast.ImportFrom):
            imported.add(("." * node.level) + (node.module or ""))
    check("the composer is pure: it imports only its sibling report modules and stdlib typing",
          imported <= {"__future__", "dataclasses", "typing", ".discovery_assessment",
                       ".internal_assessment"})
    source = open(path).read()
    check("the composer holds no write, session, or cache call",
          not any(t in source for t in ("session.", "session_factory", ".execute(", "insert(",
                                        "update(", "delete(", ".commit(", "lru_cache",
                                        "open(")))


def pure_composition_checks():
    """Recommendation eligibility and grouping over hand-built assessments, no database."""
    print("\n[5. eligible recommendations only; 4. grouping is not ranking]")
    from peak.reports.discovery_assessment import (
        DiscoveryAssessmentContext, DiscoveryFinding, build_low_hanging_fruit,
    )
    from peak.reports.final_report import compose_final_report, render_final_report_markdown
    from peak.reports.internal_assessment import (
        AssessmentFinding, InternalAssessment, InternalRecommendation,
    )

    eligible = AssessmentFinding(finding_id="f_ok", evidence_id="ev_ok", statement="Counts drift.",
                                 statement_available=True, review_status="reviewed",
                                 reliability="high", recommendation_eligible=True,
                                 recommendation_id="rec_f_ok")
    blocked = AssessmentFinding(finding_id="f_no", evidence_id="ev_no", statement="Unconfirmed.",
                                statement_available=True, review_status="unreviewed",
                                recommendation_eligible=False,
                                recommendation_blocked_reasons=["not reviewed"])
    assessment = InternalAssessment(
        engagement_id="eng_x", findings=[eligible, blocked],
        recommendation_status="internal_draft",
        recommendations=[
            InternalRecommendation(recommendation_id="rec_f_ok", finding_id="f_ok", text="ok"),
            # A recommendation for a blocked finding must never reach the report.
            InternalRecommendation(recommendation_id="rec_f_no", finding_id="f_no", text="bad"),
        ])
    report = compose_final_report(assessment)
    check("only the recommendation for the eligible finding appears",
          [r.recommendation_id for r in report.recommendations.recommendations] == ["rec_f_ok"])
    check("the composer does not modify the assessment it was given",
          len(assessment.recommendations) == 2)

    findings = [
        DiscoveryFinding(finding_id="d_c", statement="c", low_hanging_fruit=True,
                         estimated_value="medium", estimated_effort="low"),
        DiscoveryFinding(finding_id="d_a", statement="a", low_hanging_fruit=True,
                         estimated_value="high", estimated_effort="low"),
        DiscoveryFinding(finding_id="d_b", statement="b", low_hanging_fruit=True,
                         estimated_value="high", estimated_effort="low"),
        DiscoveryFinding(finding_id="d_e", statement="e", low_hanging_fruit=True),
    ]
    candidates = build_low_hanging_fruit(findings)
    grouped = compose_final_report(InternalAssessment(discovery=DiscoveryAssessmentContext(
        available=True, findings=findings, low_hanging_fruit=candidates))).low_hanging_fruit
    flat = [c.finding_id for g in grouped.groups for c in g.candidates]
    check("grouping preserves the Phase 206 display order exactly",
          flat == [c.finding_id for c in candidates] == ["d_a", "d_b", "d_c", "d_e"])
    check("consecutive equal value/effort pairs share one group; unstated levels are labelled",
          [g.label for g in grouped.groups] == ["Value High · Effort Low",
                                                "Value Medium · Effort Low",
                                                "Value Not stated · Effort Not stated"])
    check("no group or candidate carries a rank, score, priority or ROI field",
          not (_keys(dataclasses.asdict(grouped)) & RANKING_KEYS))
    markdown = render_final_report_markdown(compose_final_report(InternalAssessment(
        discovery=DiscoveryAssessmentContext(available=True, findings=findings,
                                             low_hanging_fruit=candidates))))
    fruit_md = _section(markdown, "Low-hanging-fruit opportunities")
    check("the section says it is not a score, ranking, priority order, or ROI",
          "not a score, a ranking, or a priority order" in fruit_md
          and "not a formal ranking" in fruit_md and "return-on-investment" in fruit_md)
    check("no numbered list or ordinal appears in the low-hanging-fruit section",
          not any(line.lstrip()[:3] in ("1. ", "2. ", "#1 ") for line in fruit_md.splitlines()))


def api_checks(factory):
    print("\n[final report over the consultant API]")
    from fastapi.testclient import TestClient

    from peak import accounts
    from peak.consultant_api.app import create_app
    from peak.reports.final_report import SECTION_ORDER

    accounts.create_consultant(factory, name="Casey Consultant", email="casey@example.com",
                               role="consultant", password=PASSWORD)
    app = create_app(session_factory=factory, secret_key=SECRET, secure_cookie=True)
    anon = TestClient(app, base_url="https://testserver")
    c = TestClient(app, base_url="https://testserver")
    c.post("/auth/login", json={"email": "casey@example.com", "password": PASSWORD})

    cid = c.post("/clients", json={"organization_label": "Acme Logistics"}).json()["client"]["id"]
    bare = c.post("/engagements", json={"client_id": cid, "engagement_label": "Bare"}
                  ).json()["engagement"]["id"]
    sparse = c.post("/engagements", json={"client_id": cid, "engagement_label": "Sparse"}
                    ).json()["engagement"]["id"]
    eid = c.post("/engagements", json={"client_id": cid, "engagement_label": "Inventory review"}
                 ).json()["engagement"]["id"]

    check("unauthenticated final-report access -> 401",
          anon.get(f"/engagements/{eid}/final-report").status_code == 401)
    check("an unknown engagement -> 404",
          c.get("/engagements/eng_does_not_exist/final-report").status_code == 404)

    # --- 6. sparse / no discovery still renders ------------------------------------------------
    print("\n[6. sparse or no discovery]")
    r = c.get(f"/engagements/{bare}/final-report")
    bare_body = r.json()
    check("an engagement with no discovery renders every section",
          r.status_code == 200 and bare_body["report"]["section_order"] == list(SECTION_ORDER)
          and bare_body["report"]["discovery_summary"]["available"] is False
          and "No discovery material has been recorded" in bare_body["markdown"]
          and "No North Star has been recorded" in bare_body["markdown"])
    c.patch(f"/engagements/{sparse}/north-star", json={"north_star": "Sparse north star"})
    sparse_body = c.get(f"/engagements/{sparse}/final-report").json()
    check("an engagement with only a North Star renders, with its limitations stated",
          sparse_body["report"]["executive_overview"]["north_star"] == "Sparse north star"
          and sparse_body["report"]["low_hanging_fruit"]["groups"] == []
          and "No consultant observation has been recorded"
          in " ".join(sparse_body["report"]["limitations"]["discovery_limitations"]))

    # --- build discovery material --------------------------------------------------------------
    c.patch(f"/engagements/{eid}/north-star",
            json={"north_star": NORTH_STAR,
                  "north_star_context": "Counts disagree with the system every week."})
    sid = c.post(f"/engagements/{eid}/sessions",
                 json={"interviewee_name": "Lee Ray", "interviewee_title": "Warehouse lead"}
                 ).json()["session"]["id"]
    c.post(f"/sessions/{sid}/complete")
    c.post(f"/engagements/{eid}/observations",
           json={"session_id": sid, "observation_text": OBSERVATION, "category": "Receiving",
                 "low_hanging_fruit": True, "estimated_effort": "low", "estimated_value": "high"})
    c.post(f"/engagements/{eid}/observations",
           json={"session_id": sid, "observation_text": FRUIT, "category": "Cycle counting",
                 "low_hanging_fruit": True, "estimated_effort": "medium",
                 "estimated_value": "high"})
    c.post(f"/engagements/{eid}/observations",
           json={"observation_text": UNFLAGGED, "low_hanging_fruit": False})

    body = c.get(f"/engagements/{eid}/final-report").json()
    report, markdown = body["report"], body["markdown"]
    assessment = c.get(f"/engagements/{eid}/assessment").json()["assessment"]

    # --- 1. composes from the existing assessment ---------------------------------------------
    print("\n[1. composes from the existing assessment]")
    check("discovery findings are exactly the assessment's discovery findings",
          report["discovery_summary"]["findings"] == assessment["discovery"]["findings"])
    check("coverage is the assessment's coverage, unchanged",
          report["discovery_summary"]["coverage"] == assessment["discovery"]["coverage"])
    check("evidence findings and limitations are the assessment's, unchanged",
          report["evidence_findings"]["findings"] == assessment["findings"]
          and report["limitations"]["assessment_limitations"] == assessment["limitations"])
    check("the report is internal, unapproved, and requires human review",
          report["status"] == "internal_draft" and report["client_facing"] is False
          and report["approved_for_client"] is False and report["requires_human_review"] is True
          and "Approved for client use: no" in markdown)
    check("the executive overview names the engagement and client",
          report["executive_overview"]["engagement_label"] == "Inventory review"
          and report["executive_overview"]["client_name"] == "Acme Logistics"
          and "Acme Logistics" in markdown)
    check("the summary is counts in fixed wording",
          any("3 consultant observation(s), of which 2 flagged" in line
              for line in report["executive_overview"]["summary"]))

    # --- 2. North Star -------------------------------------------------------------------------
    print("\n[2. North Star]")
    check("the North Star appears in the overview and the document",
          report["executive_overview"]["north_star"] == NORTH_STAR
          and NORTH_STAR in _section(markdown, "Executive overview"))

    # --- 3. discovery and evidence remain distinct ---------------------------------------------
    print("\n[3. discovery and evidence remain distinct]")
    evidence_md = _section(markdown, "Evidence-backed findings")
    recs_md = _section(markdown, "Internal recommendations")
    check("no discovery statement appears in the evidence or recommendation sections",
          not any(s in evidence_md or s in recs_md for s in (OBSERVATION, FRUIT, UNFLAGGED)))
    check("discovery statements appear under the discovery heading",
          all(s in _section(markdown, "Discovery summary") for s in (OBSERVATION, FRUIT, UNFLAGGED)))
    check("sections declare their material kind",
          report["discovery_summary"]["material"] == "consultant_working_material"
          and report["low_hanging_fruit"]["material"] == "consultant_working_material"
          and report["evidence_findings"]["material"] == "evidence_backed_governed"
          and report["recommendations"]["material"] == "evidence_backed_governed")
    check("discovery material created no recommendation",
          report["recommendations"]["recommendations"] == []
          and report["recommendations"]["status"] == "blocked")
    check("the limitations section distinguishes working material from governed evidence",
          "not reviewed evidence" in _section(markdown, "Limitations and human review")
          and "governed material" in _section(markdown, "Limitations and human review"))
    fruit_groups = report["low_hanging_fruit"]["groups"]
    check("low-hanging fruit keeps the assessment's display order",
          [x["statement"] for g in fruit_groups for x in g["candidates"]]
          == [x["statement"] for x in assessment["discovery"]["low_hanging_fruit"]]
          == [OBSERVATION, FRUIT])
    check("the API report carries no ranking field", not (_keys(report) & RANKING_KEYS))

    # --- 7. read-only -------------------------------------------------------------------------
    print("\n[7. the endpoint is read-only]")
    before = c.get(f"/engagements/{eid}/discovery").json()["discovery"]
    for method, kwargs in (("post", {"json": {"north_star": "hijacked"}}),
                           ("patch", {"json": {"report": {}}}),
                           ("put", {"json": {}}), ("delete", {})):
        code = getattr(c, method)(f"/engagements/{eid}/final-report", **kwargs).status_code
        check(f"{method.upper()} on the final-report endpoint is refused ({code})",
              code in (404, 405))
    repeat = c.get(f"/engagements/{eid}/final-report").json()
    check("the report is derived: repeated reads are identical and change nothing",
          repeat == body and c.get(f"/engagements/{eid}/discovery").json()["discovery"] == before)


def build_database(tmp):
    """A temporary SQLite database at head 017, with the question pool initialized."""
    db = os.path.join(tmp, "api.sqlite3")
    env = {k: v for k, v in os.environ.items() if not k.startswith("PEAK_")}
    env["PEAK_DATABASE_URL"] = f"sqlite:///{db}"
    subprocess.run([sys.executable, "-m", "alembic", "upgrade", "017_discovery_workflow"],
                   cwd=REPO_ROOT, env=env, capture_output=True, text=True, check=True)
    from peak.db.session import create_session_factory

    factory = create_session_factory(url=f"sqlite:///{db}")
    import init_discovery_questions as init

    init.initialize(factory)
    return factory


def main() -> int:
    print("Phase 208 — Final Report foundation")
    no_new_persistence_checks()
    pure_composition_checks()
    tmp = tempfile.mkdtemp()
    try:
        api_checks(build_database(tmp))
    finally:
        import shutil

        shutil.rmtree(tmp, ignore_errors=True)
    print("\n" + "=" * 56)
    print("Summary")
    print(f"  failures : {len(_failures)}")
    for failure in _failures:
        print(f"    - {failure}")
    print(f"\nRESULT: {'PASS' if not _failures else 'FAIL'}")
    return 1 if _failures else 0


if __name__ == "__main__":
    raise SystemExit(main())
