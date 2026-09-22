#!/usr/bin/env python3
"""Phase 206 discovery-to-assessment integration check (offline; temporary SQLite only).

Proves, through the consultant API over the one-call assessment workflow:

1. the North Star appears in the assessment;
2. completed / in-progress interview counts are correct;
3. a consultant observation becomes a discovery-derived finding, quoted exactly;
4. the low-hanging-fruit flag, effort and value appear;
5. traceability back to the observation, interview and consultant is preserved;
6. discovery material does **not** become evidence;
7. discovery material does **not** create an eligible formal recommendation;
8. existing evidence-backed recommendation behaviour is unchanged;
9. an engagement with no discovery data still renders;
10. the read endpoint cannot be used to mutate anything.

Plus: no migration 018, no new workspace write action, and coverage reports counts rather than a
percentage over a branch-ambiguous denominator.

No network, no credential, no client data, no production contact.

Exit status: 0 all checks passed; 1 a check failed.
"""

from __future__ import annotations

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
SECRET = "phase206-test-secret-" + "x" * 32
PASSWORD = "consultant-pw-206"
OBSERVATION = "Receiving staff record counts on paper and enter them a day later."
FRUIT = "Cycle counts are scheduled but skipped during peak weeks."
UNFLAGGED = "No single owner for stock accuracy across the two sites."


def check(label, ok):
    print(f"  [{'PASS' if ok else 'FAIL'}] {label}")
    if not ok:
        _failures.append(label)


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


def no_new_persistence_checks():
    """Phase 206 is derived: no migration 018, no new table, no new write action."""
    print("\n[no new persisted state]")
    versions = os.listdir(os.path.join(REPO_ROOT, "alembic", "versions"))
    check("no migration 018 was added", not any(v.startswith("018") for v in versions))

    from peak.persistence import allowlist

    discovery_actions = {k for k in allowlist.WORKSPACE_WRITE_COLUMNS
                         if k[0].startswith("discovery_") or k[1] == "set_engagement_north_star"}
    check("the workspace write allowlist still holds exactly the ten Phase 204 discovery actions",
          len(discovery_actions) == 10)
    check("no allowlist action mentions assessment",
          not any("assessment" in action for _, action in allowlist.WORKSPACE_WRITE_COLUMNS))

    reader_src = open(os.path.join(REPO_ROOT, "peak/db/discovery_assessment_reader.py")).read()
    check("the discovery reader issues no write statement",
          not any(verb in reader_src for verb in ("insert(", "update(", "delete(", "session.add")))

    import ast

    projection_path = os.path.join(REPO_ROOT, "peak/reports/discovery_assessment.py")
    tree = ast.parse(open(projection_path).read())
    imported = set()
    for node in ast.walk(tree):
        if isinstance(node, ast.Import):
            imported.update(a.name for a in node.names)
        elif isinstance(node, ast.ImportFrom):
            imported.add(node.module or "")
    check("the projection is pure: it imports no database, network or model client",
          not any(m.split(".")[0] in {"peak", "sqlalchemy", "requests", "httpx", "anthropic",
                                      "openai", "os", "socket"}
                  for m in imported if m),
          )


def projection_checks():
    """Pure-projection rules, with no database at all."""
    print("\n[projection rules]")
    from peak.reports.discovery_assessment import (
        DiscoveryFinding, build_discovery_assessment_context, build_discovery_findings,
        build_interview_coverage, build_low_hanging_fruit,
    )

    empty = build_discovery_assessment_context(None)
    check("no summaries produce an unavailable context rather than an error",
          empty.available is False and empty.findings == [] and empty.coverage.total_sessions == 0)

    check("a discovery finding has no recommendation-eligibility field at all",
          not any(f.name in ("recommendation_eligible", "review_status", "reliability",
                             "claim_scope")
                  for f in dataclasses.fields(DiscoveryFinding)))

    observations = [
        {"observation_id": "o1", "session_id": "s1", "category": "Receiving",
         "observation_text": OBSERVATION, "low_hanging_fruit": True,
         "estimated_effort": "low", "estimated_value": "high",
         "recorded_by_consultant_id": "c1"},
        {"observation_id": "o2", "session_id": None, "category": None,
         "observation_text": "   ", "low_hanging_fruit": True,
         "estimated_effort": None, "estimated_value": None, "recorded_by_consultant_id": "c1"},
    ]
    sessions = [{"session_id": "s1", "interviewee_name": "Lee Ray", "status": "completed",
                 "conducted_by_consultant_id": "c1"}]
    findings = build_discovery_findings(observations, sessions, {"c1": "Casey"})
    check("an empty observation states nothing and becomes no finding", len(findings) == 1)
    check("the finding statement is the observation quoted exactly",
          findings[0].statement == OBSERVATION)
    check("the finding is internal-only working material requiring human review",
          findings[0].internal_only and findings[0].requires_human_review
          and findings[0].status == "consultant_working_material")

    ordered = build_low_hanging_fruit([
        DiscoveryFinding(finding_id="d_c", statement="c", low_hanging_fruit=True,
                         estimated_value="medium", estimated_effort="low"),
        DiscoveryFinding(finding_id="d_a", statement="a", low_hanging_fruit=True,
                         estimated_value="high", estimated_effort="medium"),
        DiscoveryFinding(finding_id="d_b", statement="b", low_hanging_fruit=True,
                         estimated_value="high", estimated_effort="low"),
        DiscoveryFinding(finding_id="d_d", statement="d", low_hanging_fruit=False),
        DiscoveryFinding(finding_id="d_e", statement="e", low_hanging_fruit=True),
    ])
    check("only flagged observations are candidates, grouped high value then low effort, "
          "with unstated levels last",
          [c.finding_id for c in ordered] == ["d_b", "d_a", "d_c", "d_e"])

    branched = build_interview_coverage(
        sessions=[{"session_id": "s1", "interviewee_name": "Lee Ray", "status": "completed"}],
        answers=[{"session_id": "s1", "question_id": "q1", "answer_text": "yes"},
                 {"session_id": "s1", "question_id": "q2", "answer_text": "   "}],
        active_questions=[{"question_id": "q1", "branch_question_id": None},
                          {"question_id": "q2", "branch_question_id": None},
                          {"question_id": "q3", "branch_question_id": "q1"}])
    check("a blank answer is not coverage, and branching is reported as ambiguous",
          branched.answered_questions == 1 and branched.unbranched_active_questions == 2
          and branched.branching_makes_percentage_ambiguous is True)
    unbranched = build_interview_coverage(
        sessions=[], answers=[],
        active_questions=[{"question_id": "q1", "branch_question_id": None}])
    check("with no branching the denominator is unambiguous",
          unbranched.branching_makes_percentage_ambiguous is False)


def api_checks(factory):
    print("\n[assessment over the consultant API]")
    from fastapi.testclient import TestClient

    from peak import accounts
    from peak.consultant_api.app import create_app

    accounts.create_consultant(factory, name="Casey Consultant", email="casey@example.com",
                               role="consultant", password=PASSWORD)
    app = create_app(session_factory=factory, secret_key=SECRET, secure_cookie=True)
    anon = TestClient(app, base_url="https://testserver")
    c = TestClient(app, base_url="https://testserver")
    c.post("/auth/login", json={"email": "casey@example.com", "password": PASSWORD})

    cid = c.post("/clients", json={"organization_label": "Acme Logistics"}).json()["client"]["id"]
    bare = c.post("/engagements", json={"client_id": cid, "engagement_label": "Bare"}
                  ).json()["engagement"]["id"]
    eid = c.post("/engagements", json={"client_id": cid, "engagement_label": "Inventory review"}
                 ).json()["engagement"]["id"]

    check("unauthenticated assessment access -> 401",
          anon.get(f"/engagements/{eid}/assessment").status_code == 401)
    check("an unknown engagement -> 404",
          c.get("/engagements/eng_does_not_exist/assessment").status_code == 404)

    # --- 9. an engagement with no discovery data still renders --------------------------------
    r = c.get(f"/engagements/{bare}/assessment")
    bare_body = r.json()
    check("an engagement with no discovery data still renders",
          r.status_code == 200 and bare_body["assessment"]["discovery"] is None
          and bare_body["assessment"]["findings"] == []
          and "Internal assessment" in bare_body["markdown"])
    check("its document says so rather than omitting the discovery headings",
          "No discovery material has been recorded" in bare_body["markdown"]
          and "No North Star has been recorded" in bare_body["markdown"])

    # --- build discovery material -------------------------------------------------------------
    c.patch(f"/engagements/{eid}/north-star",
            json={"north_star": "Cut inventory discrepancies in half",
                  "north_star_context": "Counts disagree with the system every week."})
    sid = c.post(f"/engagements/{eid}/sessions",
                 json={"interviewee_name": "Lee Ray", "interviewee_title": "Warehouse lead"}
                 ).json()["session"]["id"]
    # Answer questions every interview sees. A branch follow-up is hidden until its parent matches,
    # so answering one would be refused and the count would depend on branch visibility.
    questions = [q for q in c.get("/questions").json()["questions"] if not q["branch"]]
    def valid_answer(question):
        """An answer the Phase 204 validator accepts for this question's type."""
        if question["answer_type"] == "yes_no":
            return "yes"
        if question["answer_type"] == "single_choice":
            return question["choices"][0]
        return "An answer"

    answered_ok = 0
    for question in questions[:4]:
        posted = c.put(f"/sessions/{sid}/answers/{question['id']}",
                       json={"answer": valid_answer(question)})
        answered_ok += posted.status_code == 200
    c.post(f"/sessions/{sid}/complete")
    c.post(f"/engagements/{eid}/sessions",
           json={"interviewee_name": "Dana Cruz", "interviewee_title": "Ops manager"})
    c.post(f"/engagements/{eid}/observations",
           json={"session_id": sid, "observation_text": OBSERVATION, "category": "Receiving",
                 "low_hanging_fruit": True, "estimated_effort": "low", "estimated_value": "high"})
    c.post(f"/engagements/{eid}/observations",
           json={"session_id": sid, "observation_text": FRUIT, "category": "Cycle counting",
                 "low_hanging_fruit": True, "estimated_effort": "medium",
                 "estimated_value": "high"})
    c.post(f"/engagements/{eid}/observations",
           json={"observation_text": UNFLAGGED, "category": "Management reporting",
                 "low_hanging_fruit": False})

    body = c.get(f"/engagements/{eid}/assessment").json()
    assessment, markdown = body["assessment"], body["markdown"]
    discovery = assessment["discovery"]

    # --- 1. North Star -------------------------------------------------------------------------
    check("the North Star appears in the assessment and its document",
          discovery["north_star"] == "Cut inventory discrepancies in half"
          and "Cut inventory discrepancies in half" in markdown
          and discovery["north_star_context"].startswith("Counts disagree"))

    # --- 2. interview coverage -----------------------------------------------------------------
    coverage = discovery["coverage"]
    check("completed and in-progress interview counts are correct",
          coverage["total_sessions"] == 2 and coverage["completed_sessions"] == 1
          and coverage["in_progress_sessions"] == 1)
    check("interviewees and roles are represented",
          coverage["interviewees"] == ["Dana Cruz", "Lee Ray"]
          and coverage["interviewee_titles"] == ["Ops manager", "Warehouse lead"])
    check("answered questions are counted, not estimated as a pool-wide percentage",
          answered_ok == 4 and coverage["answered_questions"] == 4
          and coverage["answered_unbranched_questions"] == 4
          and coverage["branching_makes_percentage_ambiguous"] is True
          and "%" not in markdown)

    # --- 3/4. observations become findings, with the consultant's own levels -------------------
    statements = [f["statement"] for f in discovery["findings"]]
    check("each consultant observation becomes a discovery-derived finding, quoted exactly",
          len(discovery["findings"]) == 3 and OBSERVATION in statements and FRUIT in statements
          and UNFLAGGED in statements)
    flagged = [f for f in discovery["findings"] if f["statement"] == OBSERVATION][0]
    check("the low-hanging-fruit flag, effort and value appear on the finding",
          flagged["low_hanging_fruit"] is True and flagged["estimated_effort"] == "low"
          and flagged["estimated_value"] == "high" and flagged["category"] == "Receiving")
    check("only flagged observations reach the low-hanging-fruit section, best grouping first",
          [c_["statement"] for c_ in discovery["low_hanging_fruit"]] == [OBSERVATION, FRUIT])
    check("the document labels the grouping as a display grouping, not a ranking or ROI",
          "not a score, a ranking, or a priority order" in markdown and "ROI" in markdown)

    # --- 5. traceability ------------------------------------------------------------------------
    trace = flagged["trace"]
    check("traceability names the interview, the interviewee, the observation and the consultant",
          trace["session_id"] == sid and trace["interviewee_name"] == "Lee Ray"
          and trace["observation_id"] == flagged["source_ids"][0]
          and trace["recorded_by"] == "Casey Consultant")
    check("the document answers 'where did this come from?' in readable terms",
          "interview with Lee Ray" in markdown and "recorded by Casey Consultant" in markdown)
    unlinked = [f for f in discovery["findings"] if f["statement"] == UNFLAGGED][0]
    check("an observation recorded outside an interview is still traceable to its record",
          unlinked["trace"]["session_id"] is None
          and unlinked["trace"]["observation_id"] is not None)

    # --- 6. discovery is not evidence -----------------------------------------------------------
    check("discovery material does not become an evidence-backed finding",
          assessment["findings"] == []
          and not any(OBSERVATION in str(f) for f in assessment["findings"]))
    check("a discovery finding carries no review status, reliability, claim scope or eligibility",
          all(k not in flagged for k in ("review_status", "reliability", "claim_scope",
                                         "recommendation_eligible")))
    check("discovery material is marked internal-only and requiring human review",
          flagged["internal_only"] is True and flagged["requires_human_review"] is True
          and discovery["internal_only"] is True and discovery["requires_human_review"] is True)
    check("the document states plainly that discovery is not reviewed evidence",
          "not reviewed evidence" in markdown and "Client-facing: no" in markdown)

    # --- 7/8. recommendation behaviour is unchanged ---------------------------------------------
    check("discovery material creates no formal recommendation",
          assessment["recommendations"] == []
          and assessment["recommendation_status"] == "blocked")
    check("the recommendation posture matches the engagement with no discovery at all",
          assessment["recommendation_status"] == bare_body["assessment"]["recommendation_status"]
          and assessment["recommendations"] == bare_body["assessment"]["recommendations"])

    # --- 10. the read endpoint is read-only -----------------------------------------------------
    before = c.get(f"/engagements/{eid}/discovery").json()["discovery"]
    for method, kwargs in (("post", {"json": {"north_star": "hijacked"}}),
                           ("patch", {"json": {"findings": []}}),
                           ("put", {"json": {}}), ("delete", {})):
        code = getattr(c, method)(f"/engagements/{eid}/assessment", **kwargs).status_code
        check(f"{method.upper()} on the assessment endpoint is refused ({code})",
              code in (404, 405))
    repeat = c.get(f"/engagements/{eid}/assessment").json()
    check("the assessment is derived, not stored: repeated reads are identical and change nothing",
          repeat["assessment"] == assessment
          and c.get(f"/engagements/{eid}/discovery").json()["discovery"] == before)


def main() -> int:
    print("Phase 206 — discovery-to-assessment integration")
    no_new_persistence_checks()
    projection_checks()
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
