#!/usr/bin/env python3
"""Phase 209 Final Report DOCX export check (offline; temporary SQLite only).

Proves:

1. the DOCX is generated from the composed FinalReport;
2. all six sections are present, in order;
3. the North Star appears;
4. the recommendations are exactly the existing report's eligible recommendations;
5. discovery and evidence labels remain distinct;
6. the endpoint returns a DOCX attachment;
7. no migration, no persistence, no write action.

Word formatting is not tested exhaustively — only that the package is valid WordprocessingML whose
paragraph text carries the report. No network, no credential, no production contact.

Exit status: 0 all checks passed; 1 a check failed.
"""

from __future__ import annotations

import ast
import io
import os
import sys
import tempfile
import zipfile
import xml.etree.ElementTree as ET

REPO_ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
for _p in (REPO_ROOT, os.path.join(REPO_ROOT, "tools"), os.path.join(REPO_ROOT, "tests")):
    if _p not in sys.path:
        sys.path.insert(0, _p)

from validate_phase208_final_report_foundation import (  # noqa: E402  (shared fixture setup)
    PASSWORD, SECRET, build_database,
)

_failures = []
NORTH_STAR = "Halve the weekly count discrepancies"
OBSERVATION = "Pickers re-key bin locations from a printed list."
FRUIT = "Damaged-goods returns sit unprocessed for days."
W = "{http://schemas.openxmlformats.org/wordprocessingml/2006/main}"
DOCX_MIME = "application/vnd.openxmlformats-officedocument.wordprocessingml.document"


def check(label, ok):
    print(f"  [{'PASS' if ok else 'FAIL'}] {label}")
    if not ok:
        _failures.append(label)


def paragraphs(docx_bytes):
    """[(style, text)] for every body paragraph, table cells included, in document order."""
    with zipfile.ZipFile(io.BytesIO(docx_bytes)) as z:
        root = ET.fromstring(z.read("word/document.xml"))
    out = []
    for p in root.iter(f"{W}p"):
        style = p.find(f"{W}pPr/{W}pStyle")
        text = "".join(t.text or "" for t in p.iter(f"{W}t"))
        out.append((style.get(f"{W}val") if style is not None else None, text))
    return out


def sections(paras, titles):
    """{title: [paragraph text]} split at Heading1 paragraphs."""
    result, current = {}, None
    for style, text in paras:
        if style == "Heading1":
            current = text
            result[current] = []
        elif current is not None:
            result[current].append(text)
    return {t: result.get(t, []) for t in titles}


def pure_checks():
    print("\n[1. generated from FinalReport; 4. eligible recommendations only]")
    from peak.reports.discovery_assessment import (
        DiscoveryAssessmentContext, DiscoveryFinding, build_low_hanging_fruit,
    )
    from peak.reports.final_report import compose_final_report
    from peak.reports.final_report_docx import render_final_report_docx
    from peak.reports.internal_assessment import (
        AssessmentFinding, InternalAssessment, InternalRecommendation,
    )

    findings = [DiscoveryFinding(finding_id="d1", statement=FRUIT, low_hanging_fruit=True,
                                 estimated_value="high", estimated_effort="low")]
    assessment = InternalAssessment(
        engagement_id="eng_x",
        findings=[
            AssessmentFinding(finding_id="f_ok", evidence_id="ev_ok", statement="Counts drift.",
                              statement_available=True, review_status="reviewed",
                              recommendation_eligible=True, recommendation_id="rec_f_ok"),
            AssessmentFinding(finding_id="f_no", evidence_id="ev_no", statement="Unconfirmed.",
                              statement_available=True, review_status="unreviewed"),
        ],
        recommendation_status="internal_draft",
        recommendations=[
            InternalRecommendation(recommendation_id="rec_f_ok", finding_id="f_ok",
                                   text="ELIGIBLE-REC-TEXT", supporting_evidence_ids=["ev_ok"]),
            InternalRecommendation(recommendation_id="rec_f_no", finding_id="f_no",
                                   text="BLOCKED-REC-TEXT"),
        ],
        discovery=DiscoveryAssessmentContext(available=True, north_star=NORTH_STAR,
                                             findings=findings,
                                             low_hanging_fruit=build_low_hanging_fruit(findings)))
    report = compose_final_report(assessment, {"engagement_label": "Pure", "client": {"name": "C"}})
    data = render_final_report_docx(report)
    with zipfile.ZipFile(io.BytesIO(data)) as z:
        names = set(z.namelist())
        well_formed = all(ET.fromstring(z.read(n)) is not None for n in names)
    check("the DOCX is a valid package with document, styles, numbering and footer parts",
          {"[Content_Types].xml", "_rels/.rels", "word/document.xml", "word/styles.xml",
           "word/numbering.xml", "word/footer1.xml"} <= names and well_formed)
    check("rendering is deterministic: the same report yields the same bytes",
          render_final_report_docx(report) == data)
    text = " ".join(t for _, t in paragraphs(data))
    check("the eligible recommendation appears and the blocked one does not",
          "ELIGIBLE-REC-TEXT" in text and "BLOCKED-REC-TEXT" not in text)
    check("the renderer does not modify the report",
          [r.recommendation_id for r in report.recommendations.recommendations] == ["rec_f_ok"])
    check("body paragraphs use named styles (formatting is centralized in styles.xml)",
          {s for s, _ in paragraphs(data)} - {None}
          <= {"Title", "Subtitle", "Heading1", "Heading2", "Heading3", "NorthStar",
              "MaterialLabel", "Notice", "ListBullet", "Detail", "TableText"})


def persistence_checks():
    print("\n[7. no migration, no persistence, no write action]")
    versions = os.listdir(os.path.join(REPO_ROOT, "alembic", "versions"))
    # A claim about this phase only (Phase 121 convention): it holds while this harness is being
    # authored. Phase 212 legitimately adds 018_artifact_versions.
    import _schema_history as schema_history

    if schema_history.phase_never_committed(REPO_ROOT, "tests/validate_phase209_final_report_docx_export.py"):
        check("no migration 018 was added", not any(v.startswith("018") for v in versions))
    check("migration history is still one linear chain", bool(schema_history.migration_chain(REPO_ROOT)))
    path = os.path.join(REPO_ROOT, "peak/reports/final_report_docx.py")
    source = open(path).read()
    imported = set()
    for node in ast.walk(ast.parse(source)):
        if isinstance(node, ast.Import):
            imported.update(a.name for a in node.names)
        elif isinstance(node, ast.ImportFrom):
            imported.add(("." * node.level) + (node.module or ""))
    check("the renderer imports only the stdlib and its sibling report modules",
          imported <= {"__future__", "io", "re", "zipfile", "typing", "xml.sax.saxutils",
                       ".discovery_assessment", ".final_report", ".internal_assessment"})
    check("the renderer holds no session, query, write, cache or file call",
          not any(t in source for t in ("session.", "session_factory", ".execute(", "insert(", ".commit(",
                                        "lru_cache", "open(")))
    from peak.persistence import allowlist

    check("no allowlist write action mentions a report or export",
          not any("report" in a or "export" in a or "docx" in a
                  for _, a in allowlist.WORKSPACE_WRITE_COLUMNS))


def api_checks(factory):
    from fastapi.testclient import TestClient

    from peak import accounts
    from peak.consultant_api.app import create_app
    from peak.reports.final_report import SECTION_ORDER, SECTION_TITLES
    from peak.reports.final_report_docx import MATERIAL_LABELS

    accounts.create_consultant(factory, name="Dana Consultant", email="dana@example.com",
                               role="consultant", password=PASSWORD)
    app = create_app(session_factory=factory, secret_key=SECRET, secure_cookie=True)
    anon = TestClient(app, base_url="https://testserver")
    c = TestClient(app, base_url="https://testserver")
    c.post("/auth/login", json={"email": "dana@example.com", "password": PASSWORD})
    cid = c.post("/clients", json={"organization_label": "Acme Logistics"}).json()["client"]["id"]
    bare = c.post("/engagements", json={"client_id": cid, "engagement_label": "Bare"}
                  ).json()["engagement"]["id"]
    eid = c.post("/engagements", json={"client_id": cid, "engagement_label": "Inventory review"}
                 ).json()["engagement"]["id"]
    c.patch(f"/engagements/{eid}/north-star", json={"north_star": NORTH_STAR})
    sid = c.post(f"/engagements/{eid}/sessions", json={"interviewee_name": "Lee Ray"}
                 ).json()["session"]["id"]
    c.post(f"/engagements/{eid}/observations",
           json={"session_id": sid, "observation_text": OBSERVATION, "low_hanging_fruit": False})
    c.post(f"/engagements/{eid}/observations",
           json={"session_id": sid, "observation_text": FRUIT, "low_hanging_fruit": True,
                 "estimated_effort": "low", "estimated_value": "high"})

    print("\n[6. the endpoint returns a DOCX attachment]")
    url = f"/engagements/{eid}/final-report.docx"
    check("unauthenticated export -> 401", anon.get(url).status_code == 401)
    check("unknown engagement -> 404",
          c.get("/engagements/eng_does_not_exist/final-report.docx").status_code == 404)
    r = c.get(url)
    disposition = r.headers.get("content-disposition", "")
    check("200 with the DOCX media type",
          r.status_code == 200 and r.headers["content-type"] == DOCX_MIME)
    check("attachment disposition with a client/engagement filename",
          disposition == 'attachment; filename="final-report-acme-logistics-inventory-review.docx"')
    for method in ("post", "put", "patch", "delete"):
        code = getattr(c, method)(url).status_code
        check(f"{method.upper()} on the export endpoint is refused ({code})", code == 405)
    check("repeated exports are byte-identical (derived, nothing stored)", c.get(url).content == r.content)

    paras = paragraphs(r.content)
    report = c.get(f"/engagements/{eid}/final-report").json()["report"]
    titles = [SECTION_TITLES[k] for k in SECTION_ORDER]
    by_section = sections(paras, titles)

    print("\n[2. six sections, in order; 3. North Star]")
    check("the Heading 1 paragraphs are exactly the six report sections, in order",
          [t for s, t in paras if s == "Heading1"] == titles == [
              report["section_titles"][k] for k in report["section_order"]])
    check("the North Star appears on the title page and in the executive overview",
          ("NorthStar", NORTH_STAR) in paras
          and NORTH_STAR in by_section[SECTION_TITLES["executive_overview"]])

    print("\n[4. recommendations match the report; 5. labels distinct]")
    recs_text = " ".join(by_section[SECTION_TITLES["recommendations"]])
    check("recommendations section matches the report (none here; discovery created none)",
          report["recommendations"]["recommendations"] == []
          and "No recommendation is available" in recs_text)
    discovery_label, evidence_label = MATERIAL_LABELS["consultant_working_material"], \
        MATERIAL_LABELS["evidence_backed_governed"]
    labels = {t: [p for p in by_section[t] if p in (discovery_label, evidence_label)]
              for t in titles}
    check("discovery and low-hanging-fruit sections carry only the working-material label",
          labels[SECTION_TITLES["discovery_summary"]] == [discovery_label]
          and labels[SECTION_TITLES["low_hanging_fruit"]] == [discovery_label])
    check("evidence and recommendation sections carry only the governed label",
          labels[SECTION_TITLES["evidence_findings"]] == [evidence_label]
          and labels[SECTION_TITLES["recommendations"]] == [evidence_label])
    evidence_and_recs = " ".join(by_section[SECTION_TITLES["evidence_findings"]]) + recs_text
    check("no discovery statement appears in the evidence or recommendation sections",
          OBSERVATION not in evidence_and_recs and FRUIT not in evidence_and_recs)
    fruit = " ".join(by_section[SECTION_TITLES["low_hanging_fruit"]])
    check("low-hanging fruit keeps its grouping label and not-a-ranking statements",
          "Value High · Effort Low" in fruit and "not a formal ranking" in fruit
          and report["low_hanging_fruit"]["not_ranked_note"] in fruit)
    with zipfile.ZipFile(io.BytesIO(r.content)) as z:
        footer = z.read("word/footer1.xml").decode()
    check("every page footer says internal draft, not client-facing, requires review, with page "
          "numbers", "Internal draft" in footer and "Not client-facing" in footer
          and "Requires consultant review" in footer and "PAGE" in footer)

    bare_r = c.get(f"/engagements/{bare}/final-report.docx")
    check("an engagement with no discovery still exports all six sections",
          bare_r.status_code == 200
          and [t for s, t in paragraphs(bare_r.content) if s == "Heading1"] == titles)


def main() -> int:
    print("Phase 209 — Final Report DOCX export")
    pure_checks()
    persistence_checks()
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
