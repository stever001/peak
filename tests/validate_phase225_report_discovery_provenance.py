#!/usr/bin/env python3
"""Phase 225 — truthful report discovery provenance (offline; temporary SQLite and a temporary local store only).

Proves:

1. **No schema or authority.** No migration, model, allowlist action, policy or verifier-pin change.
2. **The rule.** The wider wording applies only when a finding has no interview session.
3. **The problem, corrected.** With no interview at all, no rendition says the material was recorded
   during interviews: draft JSON, Markdown, DOCX, assessment Markdown or client package.
4. **Interview-only reports are unchanged.** The sentences and the report content are the same as
   before, so a current package still matches its draft.
5. **Stored packages are never touched.** When a later observation changes the sentence, the earlier
   package's rows and bytes stay the same, and the existing notice says the draft has changed.
6. **Nothing else moves.** Findings and traces, eligibility and recommendations stay the same, no
   origin enters the report, the client-facing checks pass, and reads write nothing.
7. **Static UI.** The internal page applies the same test, and origins stay off this view (Phase 222).

Exit status: 0 all checks passed; 1 a check failed.
"""

from __future__ import annotations

import hashlib
import io
import json
import os
import re
import sys
import tempfile
import zipfile
from types import SimpleNamespace

REPO_ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
TESTS = os.path.join(REPO_ROOT, "tests")
for p in (REPO_ROOT, TESTS):
    if p not in sys.path:
        sys.path.insert(0, p)

import validate_phase220_guided_evidence_capture as p220  # noqa: E402  (shared fixtures)
import validate_phase223_phase_work_record as p223  # noqa: E402  (shared fixtures)

HEAD = "025_observation_task_origins"
VIEW = "web/components/final-report-view.tsx"
OBSERVATION_TABLES = {"discovery_observations", "observation_task_origins"}
#: The wording before Phase 225, written out so that it cannot move with the code.
OLD_OPENING = ("Consultant discovery material. Recorded during interviews, not reviewed evidence: it "
               "carries no review status, no reliability rating, and no recommendation eligibility. "
               "It informs the assessment; it does not support a formal recommendation on its own.")
OLD_BOUNDARY = ("Discovery sections hold consultant working material recorded during interviews. It is "
                "not reviewed evidence and carries no review status, reliability rating, or "
                "recommendation eligibility.")
NEW_OPENING = OLD_OPENING.replace("during interviews,", "during interviews or other consulting work,")
NEW_BOUNDARY = OLD_BOUNDARY.replace("during interviews.", "during interviews or other consulting work.")
_failures = []


def check(label, ok):
    print(f"  [{'PASS' if ok else 'FAIL'}] {label}")
    if not ok:
        _failures.append(label)


read = p220.read
_snapshot = p223._snapshot


def _docx_text(data: bytes) -> str:
    with zipfile.ZipFile(io.BytesIO(data)) as z:
        xml = z.read("word/document.xml").decode()
    return " ".join("".join(re.findall(r"<w:t[^>]*>([^<]*)</w:t>", p))
                    for p in re.findall(r"<w:p[ >].*?</w:p>", xml, re.S))


def _html_text(html: str) -> str:
    return " ".join(re.sub(r"<[^>]+>", " ", html).replace("&#x27;", "'").split())


def schema_checks():
    print("\n[1. no schema change, no new authority]")
    from peak.persistence import allowlist, runtime_persistence as rp

    versions = [v for v in os.listdir(os.path.join(REPO_ROOT, "alembic", "versions"))
                if v.endswith(".py")]
    check("Phase 225 adds no migration (025 stays; the only later one is Phase 226's 026)",
          {v for v in versions if v[:3] > "025"} <= {"026_observation_lead_reviews.py"}
          and f"{HEAD}.py" in versions)
    check("the production verifier pin does not move",
          f'EXPECTED_ALEMBIC_HEAD = "{HEAD}"' in read("tools/production_mysql_collation_verify.py"))
    check("no model, policy or allowlist entry names the rule",
          not any("outside_interview" in s for s in (
              read("peak/db/models.py"), read("peak/persistence/allowlist.py"),
              read("peak/persistence/runtime_persistence.py")))
          and "observation_task_origins" in rp.RUNTIME_TABLE_PERSISTENCE
          and ("observation_task_origins", "create_observation_task_origin")
          in allowlist.WORKSPACE_WRITE_COLUMNS)
    src = read("peak/reports/discovery_assessment.py")
    check("no model client is imported by the discovery report module",
          not re.search(r"^\s*(from|import)\s+(anthropic|openai|peak\.agents)", src, re.M))


def rule_checks():
    print("\n[2. the rule]")
    from peak.reports.discovery_assessment import (
        DISCOVERY_NOT_EVIDENCE_TEXT, DISCOVERY_NOT_EVIDENCE_WIDER_TEXT,
        discovery_not_evidence_text as text, recorded_outside_interviews as outside,
    )
    from peak.reports.final_report import BOUNDARY_STATEMENT_WIDER, BOUNDARY_STATEMENTS
    from peak.workspace.advisory_boundary import framing_violations

    def finding(session_id):
        return SimpleNamespace(trace=SimpleNamespace(session_id=session_id))

    check("the unchanged sentences are exactly the earlier wording",
          DISCOVERY_NOT_EVIDENCE_TEXT == OLD_OPENING and BOUNDARY_STATEMENTS[0] == OLD_BOUNDARY)
    check("the wider sentences differ only by the named words",
          DISCOVERY_NOT_EVIDENCE_WIDER_TEXT == NEW_OPENING and BOUNDARY_STATEMENT_WIDER == NEW_BOUNDARY)
    check("no findings, or none given: the existing sentence",
          text([]) == OLD_OPENING and text(None) == OLD_OPENING)
    check("every finding from an interview: the existing sentence",
          text([finding("s1"), finding("s2")]) == OLD_OPENING and not outside([finding("s1")]))
    check("mixed: the wider sentence", text([finding("s1"), finding(None)]) == NEW_OPENING)
    check("none from an interview: the wider sentence", text([finding(None)]) == NEW_OPENING
          and outside([finding("")]))
    check("the wider wording crosses no advisory boundary",
          not framing_violations(NEW_OPENING) and not framing_violations(NEW_BOUNDARY))


#: A fixed report rendered by the baseline code (``bd3c6bb``): sha256 prefixes of its content hash,
#: Markdown, web rendition and assessment Markdown. The baseline had no rule, so equality here means
#: these reports are byte-identical and their packages still match.
BASELINE = {
    "interview_only": ("a047a5c42a45785d", "9c1d7b7516edad5f", "157b1a5436e25267", "b37d4bea2cc088e9"),
    "no_findings": ("634478ecc7c79340", "5ff50bcd8cee31bb", "435dac344c678046", "4dae6aa99749ea4c"),
    "outside": ("4673371fee27f2ce", "b55e626fcef37708", "f768169302719add", "3eafb328ee7d5313"),
}


def baseline_checks():
    print("\n[2b. against the baseline code's output]")
    import dataclasses

    from peak.reports.discovery_assessment import (
        DiscoveryAssessmentContext, DiscoveryFinding, DiscoveryTrace, InterviewCoverage,
    )
    from peak.reports.final_report import compose_final_report, render_final_report_markdown
    from peak.reports.final_report_html import render_final_report_html
    from peak.reports.internal_assessment import (
        InternalAssessment, render_internal_assessment_markdown,
    )
    from peak.workspace.approvals import report_content_hash

    def blank(f):
        kind = str(f.type)
        return [] if "List" in kind else 0 if "int" in kind else False if "bool" in kind else None

    def finding(i, sid):
        return DiscoveryFinding(
            finding_id=f"disc_{i}", statement=f"S{i}", category="c",
            source_type="discovery_observation", source_ids=[i], basis="observed",
            trace=DiscoveryTrace(session_id=sid, interviewee_name="Dana" if sid else None,
                                 observation_id=i, recorded_by="Cam"))

    def prefixes(findings):
        coverage = InterviewCoverage(**{f.name: blank(f)
                                        for f in dataclasses.fields(InterviewCoverage)})
        assessment = InternalAssessment(engagement_id="e", discovery=DiscoveryAssessmentContext(
            findings=findings, available=True, coverage=coverage))
        report = compose_final_report(assessment, {"id": "e", "engagement_label": "L"})

        def h(v):
            return hashlib.sha256(v if isinstance(v, bytes) else v.encode()).hexdigest()[:16]

        return (report_content_hash(report)[:16], h(render_final_report_markdown(report)),
                h(render_final_report_html(report)), h(render_internal_assessment_markdown(assessment)))

    check("a report from interviews only is byte-identical to the baseline's",
          prefixes([finding("a", "s1"), finding("b", "s2")]) == BASELINE["interview_only"])
    check("a report with no findings is byte-identical to the baseline's",
          prefixes([]) == BASELINE["no_findings"])
    outside = prefixes([finding("a", None)])
    check("a report with material from outside interviews differs in all four, as intended",
          all(a != b for a, b in zip(outside, BASELINE["outside"])))


def app_checks(tmp):
    app, factory, store, client, db = p220._setup(tmp)
    lee = client("lee")

    def report(eid):
        return lee.get(f"/engagements/{eid}/final-report").json()

    def review(eid):
        return lee.get(f"/engagements/{eid}/final-report/packages").json()["review"]

    def prepare(eid):
        r = lee.post(f"/engagements/{eid}/final-report/packages", json={})
        assert r.status_code == 201, r.text
        return r.json()["package"]

    def web(pkg):
        return lee.get(f"/release-packages/{pkg['id']}/web").text

    def docx(pkg):
        return lee.get(f"/release-packages/{pkg['id']}/docx").content

    def interview_observation(eid, text):
        sid = lee.post(f"/engagements/{eid}/sessions",
                       json={"interviewee_name": "Dana Receiver"}).json()["session"]["id"]
        r = lee.post(f"/engagements/{eid}/observations",
                     json={"observation_text": text, "session_id": sid, "basis": "testimony"})
        assert r.status_code == 201, r.text

    print("\n[3. the problem, corrected: phase work and no interview]")
    pid, phase = p220._phase(lee, "Alpha")
    eid = phase["engagement_id"]
    task = phase["tasks"][0]
    text = "Keying runs a day behind because the log is on paper."
    plain = report(eid)
    check("before any observation: the existing wording, with no finding",
          plain["report"]["discovery_summary"]["findings"] == []
          and plain["report"]["limitations"]["boundary_statements"][0] == OLD_BOUNDARY)
    r = lee.post(f"/tasks/{task['id']}/observations",
                 json={"observation_text": text, "basis": "observed"})
    assert r.status_code == 201, r.text
    before_reads = _snapshot(db)
    got = report(eid)
    s = got["report"]["discovery_summary"]
    check("the engagement has no interview, and the finding has no session",
          s["coverage"]["total_sessions"] == 0 and s["findings"][0]["trace"]["session_id"] is None)
    check("draft: the boundary statement is the wider one",
          got["report"]["limitations"]["boundary_statements"][0] == NEW_BOUNDARY)
    check("draft Markdown: the wider opening, and no old sentence",
          NEW_OPENING in got["markdown"] and NEW_BOUNDARY in got["markdown"]
          and OLD_OPENING not in got["markdown"] and OLD_BOUNDARY not in got["markdown"])
    draft_docx = _docx_text(lee.get(f"/engagements/{eid}/final-report.docx").content)
    check("draft DOCX: the wider sentences, and no old sentence",
          NEW_OPENING in draft_docx and NEW_BOUNDARY in draft_docx
          and OLD_OPENING not in draft_docx and OLD_BOUNDARY not in draft_docx)
    a = lee.get(f"/engagements/{eid}/assessment").json()
    check("assessment Markdown: the wider opening, and no old sentence",
          NEW_OPENING in a["markdown"] and OLD_OPENING not in a["markdown"])
    check("reading the draft, its DOCX and the assessment writes nothing",
          _snapshot(db) == before_reads)

    pkg = prepare(eid)
    client_html = _html_text(web(pkg))
    client_docx = _docx_text(docx(pkg))
    check("client package, web and DOCX: the wider sentences, and no old sentence",
          all(NEW_OPENING in x and NEW_BOUNDARY in x and OLD_OPENING not in x
              and OLD_BOUNDARY not in x for x in (client_html, client_docx)))
    check("the per-finding trace stays as it was", "recorded outside an interview" in client_html)
    check("the renditions still pass the client-facing checks", pkg["client_problems"] == [])
    blob = json.dumps(got["report"]) + client_html + client_docx
    check("no phase, task or origin enters the report or the client package",
          pid not in blob and task["id"] not in blob and task["title"] not in blob
          and "written_after_work" not in blob and "observation_origins" not in got)
    check("the finding stays working material: no eligibility field, no recommendation",
          s["findings"][0]["status"] == "consultant_working_material"
          and "recommendation_eligible" not in s["findings"][0]
          and got["report"]["recommendations"]["recommendations"] == []
          and got["report"]["evidence_findings"]["findings"] == [])
    fresh = lee.get(f"/phases/{pid}").json()["phase"]
    check("task and phase state are untouched",
          fresh["status"] == "authorized"
          and fresh["tasks"][0]["status"] == task["status"])

    print("\n[4. an engagement-level observation is covered by the same rule]")
    _, phase_d = p220._phase(lee, "Delta")
    eid_d = phase_d["engagement_id"]
    r = lee.post(f"/engagements/{eid_d}/observations", json={"observation_text": "On the walk-through."})
    assert r.status_code == 201, r.text
    check("the wider boundary statement applies",
          report(eid_d)["report"]["limitations"]["boundary_statements"][0] == NEW_BOUNDARY)

    print("\n[5. interview-only reports are unchanged]")
    _, phase_b = p220._phase(lee, "Beta")
    eid_b = phase_b["engagement_id"]
    interview_observation(eid_b, "The dock supervisor keeps the real count in a notebook.")
    got_b = report(eid_b)
    check("the boundary statement and opening are the earlier wording",
          got_b["report"]["limitations"]["boundary_statements"][0] == OLD_BOUNDARY
          and OLD_OPENING in got_b["markdown"] and NEW_OPENING not in got_b["markdown"])
    content = got_b["report"]
    from peak.reports.final_report import BOUNDARY_STATEMENTS

    check("the whole boundary list is the fixed list, in order, so report content is unchanged",
          content["limitations"]["boundary_statements"] == list(BOUNDARY_STATEMENTS))
    pkg_b = prepare(eid_b)
    check("its package matches its draft on a later read",
          review(eid_b)["draft_matches_latest"] is True)
    check("its client package carries the earlier wording",
          OLD_OPENING in _html_text(web(pkg_b)) and NEW_OPENING not in _html_text(web(pkg_b)))

    print("\n[6. stored packages are never touched]")
    web_before, docx_before = web(pkg_b), docx(pkg_b)
    review_before = review(eid_b)["packages"][0]
    rows_before = _snapshot(db)
    r = lee.post(f"/tasks/{phase_b['tasks'][0]['id']}/observations",
                 json={"observation_text": "The notebook also holds put-away locations."})
    assert r.status_code == 201, r.text
    changed = {t for t in rows_before if rows_before[t] != _snapshot(db)[t]}
    check("a later work observation changes only observation rows", changed == OBSERVATION_TABLES)
    check("the earlier package's bytes are identical",
          web(pkg_b) == web_before and docx(pkg_b) == docx_before)
    after = review(eid_b)
    latest = after["packages"][0]
    check("its state and hashes are unchanged, and it still verifies",
          latest["state"] == review_before["state"]
          and latest["package_hash"] == review_before["package_hash"]
          and latest["content_hash"] == review_before["content_hash"]
          and latest["hash_verified"] is True)
    check("the existing notice now says the draft has changed",
          after["draft_matches_latest"] is False)
    wider_now = report(eid_b)["report"]
    check("the draft is now the wider wording, and a mixed report keeps its interview trace",
          wider_now["limitations"]["boundary_statements"][0] == NEW_BOUNDARY
          and {bool(f["trace"]["session_id"])
               for f in wider_now["discovery_summary"]["findings"]} == {True, False})
    pkg_b2 = prepare(eid_b)
    check("a new package carries the wider wording and is a new package, and the old one stays",
          NEW_OPENING in _html_text(web(pkg_b2)) and pkg_b2["id"] != pkg_b["id"]
          and web(pkg_b) == web_before)
    check("the new package has its own content hash",
          pkg_b2["content_hash"] != review_before["content_hash"])


def static_checks():
    print("\n[7. static UI and renderers]")
    view = read(VIEW)
    check("the internal page applies the same test to its opening line",
          "s.findings.some((f) => !f.trace.session_id)" in view
          and "Recorded during interviews or other consulting work." in view
          and "Recorded during interviews." in view)
    check("origins stay off this view (the Phase 222 rule): the task stays one tap away",
          "origin" not in view and "Open observation" in read("web/components/assessment-view.tsx"))
    for path in ("peak/reports/final_report.py", "peak/reports/final_report_html.py",
                 "peak/reports/final_report_docx.py", "peak/reports/internal_assessment.py"):
        src = read(path)
        check(f"{os.path.basename(path)} takes the sentence from the one rule",
              "discovery_not_evidence_text" in src and "DISCOVERY_NOT_EVIDENCE_TEXT" not in src)
    trace = re.search(r"class DiscoveryTrace:.*?(?=\n\n\n|\n@dataclass)",
                      read("peak/reports/discovery_assessment.py"), re.S).group(0)
    check("the report's trace gains no field", "phase" not in trace and "task" not in trace
          and "origin" not in trace)
    check("the report modules read no phase or origin table",
          not any(re.search(r"ObservationTaskOrigin|EngagementPhase|PhaseTask", read(p))
                  for p in ("peak/reports/discovery_assessment.py", "peak/reports/final_report.py")))
    check("the Phase 225 target is in make validate",
          re.search(r"^validate: .*\bvalidate-phase225\b", read("Makefile"), re.M) is not None)


def main() -> int:
    print("Peak Phase 225 report discovery provenance check")
    print("=" * 49)
    try:
        import argon2, fastapi, httpx, itsdangerous, multipart, sqlalchemy  # noqa: F401,E401
    except ImportError:
        print("  [skip] web dependencies not installed — run with PYTHON=.venv/bin/python")
        return 0
    schema_checks()
    rule_checks()
    baseline_checks()
    with tempfile.TemporaryDirectory(prefix="peak_phase225_") as tmp:
        app_checks(tmp)
    static_checks()

    print("\nSummary")
    print(f"  failures : {len(_failures)}")
    print("RESULT: " + ("PASS" if not _failures else "FAIL"))
    return 0 if not _failures else 1


if __name__ == "__main__":
    sys.exit(main())
