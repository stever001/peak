#!/usr/bin/env python3
"""Phase 213 release packages, two-stage approval and release check (offline; temporary SQLite only).

Humans approve a **release package**: one immutable canonical artifact version bound to the exact
web and DOCX renditions proposed for release, both stored as bytes. Proves, through the
authenticated API:

1. one release package binds one canonical artifact version;
2. the web and DOCX renditions are rendered from that same stored version;
3. both renditions have a stable, immutable identity and hash;
4. the Lead approval binds to the exact package;
5. the final approval binds to the same package;
6. changing working data does not alter an existing package;
7. changing a rendition requires a new package and a new approval cycle;
8. release returns the exact approved package;
9. released web and DOCX are served from storage and never silently regenerated;
10. the different-human rule still holds.

And the release-correctness fixes:

- release renditions use the client presentation: same canonical content, no internal-draft status
  wording, no internal identifiers, a business title; a package whose renditions are not
  client-facing cannot be approved or released;
- each decision records which rendition (web or DOCX) the human reviewed;
- designation and final decisions take a lock on the engagement row as their first statement, so
  the current designation is decided at commit time;
- a rejected package is terminal and is never offered again for an identical re-preparation.

Plus migration 019, the Final Approver designation rules, rejection, stored-content tampering,
append-only immutability, Admin-only Lead assignment, and that nothing reaches client-facing
report output. Three synthetic consultants and one synthetic Admin; reports are composed from real
workspace engagements. No network, no credential, no production contact.

Exit status: 0 all checks passed; 1 a check failed.
"""

from __future__ import annotations

import dataclasses
import hashlib
import io
import json
import os
import subprocess
import sys
import tempfile
import zipfile

REPO_ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
for _p in (REPO_ROOT, os.path.join(REPO_ROOT, "tools")):
    if _p not in sys.path:
        sys.path.insert(0, _p)

_failures = []
PASSWORD = "synthetic-password-213"
SECRET = "synthetic-secret-213-" + "x" * 32
NEW_TABLES = {"artifact_release_packages", "artifact_renditions", "artifact_approvals",
              "artifact_final_approver_designations", "artifact_releases"}


def check(label, ok):
    print(f"  [{'PASS' if ok else 'FAIL'}] {label}")
    if not ok:
        _failures.append(label)


def raises(fn, exc=Exception):
    try:
        fn()
    except exc:
        return True
    return False


def sha(data: bytes) -> str:
    return hashlib.sha256(data).hexdigest()


def docx_text(data: bytes) -> str:
    with zipfile.ZipFile(io.BytesIO(data)) as z:
        return z.read("word/document.xml").decode("utf-8")


def alembic(env, *args):
    return subprocess.run([sys.executable, "-m", "alembic", *args], cwd=REPO_ROOT, env=env,
                          capture_output=True, text=True)


def _env(db):
    env = {k: v for k, v in os.environ.items() if not k.startswith("PEAK_")}
    env["PEAK_DATABASE_URL"] = f"sqlite:///{db}"
    return env


def migration_checks(tmp):
    print("\n[migration 019]")
    import sqlalchemy as sa

    db = os.path.join(tmp, "mig.sqlite3")
    up = alembic(_env(db), "upgrade", "019_artifact_approval_release")
    tables = set(sa.inspect(sa.create_engine(f"sqlite:///{db}")).get_table_names())
    check("upgrade to 019 adds the package, rendition, approval, designation and release tables",
          up.returncode == 0 and NEW_TABLES <= tables)
    down = alembic(_env(db), "downgrade", "018_artifact_versions")
    tables = set(sa.inspect(sa.create_engine(f"sqlite:///{db}")).get_table_names())
    check("downgrade to 018 removes exactly those five tables",
          down.returncode == 0 and not NEW_TABLES & tables
          and {"artifacts", "artifact_versions"} <= tables)
    src = open(os.path.join(REPO_ROOT, "alembic/versions/019_artifact_approval_release.py")).read()
    code_ = src.split('"""', 2)[2].lower()  # the module body, after the docstring
    check("migration 019 carries no data and does not alter artifact_versions",
          "insert" not in code_ and "op.execute" not in code_ and "alter" not in code_
          and "add_column" not in code_)


def purity_checks():
    print("\n[the release renderers render; they never compose or touch storage]")
    import ast

    siblings = {".discovery_assessment", ".final_report", ".internal_assessment",
                ".final_report_docx", ".release_presentation"}
    stdlib = {"__future__", "html", "io", "re", "zipfile", "typing"}
    for rel in ("peak/reports/final_report_html.py", "peak/reports/release_presentation.py"):
        source = open(os.path.join(REPO_ROOT, rel)).read()
        imported = set()
        for node in ast.walk(ast.parse(source)):
            if isinstance(node, ast.Import):
                imported.update(a.name for a in node.names)
            elif isinstance(node, ast.ImportFrom):
                imported.add(("." * node.level) + (node.module or ""))
        check(f"{rel} imports only the stdlib and sibling report modules",
              imported <= stdlib | siblings)
        check(f"{rel} holds no session, query, write or file call",
              not any(t in source for t in ("session.", "session_factory", ".execute(", "insert(", ".commit(",
                                            "open(")))


def build(tmp):
    db = os.path.join(tmp, "app.sqlite3")
    alembic(_env(db), "upgrade", "head").check_returncode()
    from peak.db.session import create_session_factory

    factory = create_session_factory(url=f"sqlite:///{db}")
    import init_discovery_questions as init

    init.initialize(factory)
    return factory


def code(response):
    detail = response.json().get("detail") if response.status_code >= 400 else None
    return detail.get("code") if isinstance(detail, dict) else response.status_code


def main_checks(factory):
    from fastapi.testclient import TestClient
    from sqlalchemy import select, text, update

    from peak import accounts
    from peak.consultant_api.app import create_app
    from peak.db.models import (
        ArtifactApproval, ArtifactFinalApproverDesignation, ArtifactRelease,
        ArtifactReleasePackage, ArtifactRendition, ArtifactVersion,
    )
    from peak.persistence import allowlist
    from peak.reports import final_report_docx, final_report_html
    from peak.reports import release_presentation as rp
    from peak.reports.release_presentation import client_presentation, rendition_text
    from peak.workspace import approvals as ap
    from peak.workspace import artifacts as av

    people = {}
    for key, name, role in (("lee", "Lee Lead", "consultant"), ("fran", "Fran Final", "consultant"),
                            ("sam", "Sam Other", "consultant"), ("ada", "Ada Admin", "admin")):
        people[key] = accounts.create_consultant(factory, name=name, email=f"{key}@example.com",
                                                 role=role, password=PASSWORD)["id"]
    app = create_app(session_factory=factory, secret_key=SECRET, secure_cookie=True)
    c = {}
    for key in people:
        c[key] = TestClient(app, base_url="https://testserver")
        c[key].post("/auth/login", json={"email": f"{key}@example.com", "password": PASSWORD})
    lee, fran, sam, ada = c["lee"], c["fran"], c["sam"], c["ada"]
    anon = TestClient(app, base_url="https://testserver")

    client_id = lee.post("/clients", json={"organization_label": "Synthetic Co 213"}
                         ).json()["client"]["id"]

    def engagement(label, assigned=True):
        body = {"client_id": client_id, "engagement_label": label, "current_phase": "Assessment"}
        if assigned:
            body["assigned_consultant_id"] = people["lee"]
        eid = ada.post("/engagements", json=body).json()["engagement"]["id"]  # Admin assigns
        north_star(eid, f"North Star {label}")
        lee.post(f"/engagements/{eid}/observations",
                 json={"observation_text": f"Cycle counts lag in {label}."})
        return eid

    def north_star(eid, value):
        lee.patch(f"/engagements/{eid}/north-star", json={"north_star": value})

    def prepare(eid, who=lee):
        return who.post(f"/engagements/{eid}/final-report/packages")

    def act(who, pid, path, **body):
        return who.post(f"/release-packages/{pid}/{path}", json=body)

    def decide(who, pid, level, decision, h, note=None, reviewed="web"):
        body = {"decision": decision, "package_hash": h, "reviewed_rendition": reviewed}
        if note is not None:
            body["note"] = note
        return act(who, pid, level, **body)

    def get(pid):
        return lee.get(f"/release-packages/{pid}").json()["package"]

    def through_lead(eid):
        p = prepare(eid).json()["package"]
        decide(lee, p["id"], "lead-approval", "approved", p["package_hash"])
        act(lee, p["id"], "final-approver", consultant_id=people["fran"])
        return p

    # --- assignment protection ----------------------------------------------------------------
    print("\n[only an Admin sets or changes the assigned consultant (the Lead)]")
    ea = engagement("Assignment")
    r = lee.post("/engagements", json={"client_id": client_id, "engagement_label": "Self-assigned",
                                       "assigned_consultant_id": people["lee"]})
    check("a consultant cannot create an engagement with an assigned consultant (403)",
          r.status_code == 403 and code(r) == "admin_required")
    r = sam.patch(f"/engagements/{ea}", json={"assigned_consultant_id": people["sam"]})
    check("a consultant cannot change the assigned consultant (403), and it is unchanged",
          r.status_code == 403 and code(r) == "admin_required"
          and lee.get(f"/engagements/{ea}").json()["engagement"]["assigned_consultant"]["id"]
          == people["lee"])
    check("a consultant cannot clear the assigned consultant (403)",
          sam.patch(f"/engagements/{ea}", json={"assigned_consultant_id": None}).status_code == 403)
    r = sam.patch(f"/engagements/{ea}", json={"current_phase": "Analysis",
                                              "assigned_consultant_id": people["lee"]})
    check("a consultant can still edit other fields; resending the unchanged assignment is allowed",
          r.status_code == 200 and r.json()["engagement"]["current_phase"] == "Analysis")
    check("consultant access is otherwise unchanged: a non-assigned consultant reads the "
          "engagement, its report and discovery, and records an observation",
          sam.get(f"/engagements/{ea}").status_code == 200
          and sam.get(f"/engagements/{ea}/final-report").status_code == 200
          and sam.get(f"/engagements/{ea}/discovery").status_code == 200
          and sam.post(f"/engagements/{ea}/observations",
                       json={"observation_text": "Sam's note."}).status_code == 201)
    r = ada.patch(f"/engagements/{ea}", json={"assigned_consultant_id": people["sam"]})
    check("an Admin can change the assigned consultant",
          r.status_code == 200 and r.json()["engagement"]["assigned_consultant"]["id"]
          == people["sam"])
    check("an Admin can clear it",
          ada.patch(f"/engagements/{ea}", json={"assigned_consultant_id": None}).json()
          ["engagement"]["assigned_consultant"] is None)

    # --- 1-3. the release package --------------------------------------------------------------
    print("\n[1. one release package binds one canonical artifact version]")
    e1 = engagement("One")
    before = lee.get(f"/engagements/{e1}/final-report").json()
    check("an unauthenticated package create is refused (401)",
          anon.post(f"/engagements/{e1}/final-report/packages").status_code == 401)
    r = prepare(e1)
    p1 = r.json()["package"]
    h1 = p1["package_hash"]
    check("POST /final-report/packages creates package 1 in state prepared, nothing decided",
          r.status_code == 201 and p1["created"] and p1["package_number"] == 1
          and p1["state"] == "prepared" and p1["lead_decision"] is None
          and p1["final_decision"] is None and p1["designations"] == [] and p1["release"] is None)
    with factory() as s:
        version = s.get(ArtifactVersion, p1["artifact_version_id"])
        version_hash, version_content = version.content_hash, version.content_canonical
        rows = s.scalars(select(ArtifactRendition)
                         .where(ArtifactRendition.release_package_id == p1["id"])).all()
        stored = {row.rendition_type: row.content_bytes for row in rows}
        same_version = all(row.artifact_version_id == p1["artifact_version_id"] for row in rows)
    check("the package names exactly one version, and carries that version's content hash",
          p1["version_number"] == 1 and p1["content_hash"] == version_hash)
    check("it holds exactly one web and one DOCX rendition, both under that same version",
          set(p1["renditions"]) == {"web", "docx"} and set(stored) == {"web", "docx"}
          and same_version)
    check("reading the report changes nothing and creates no package",
          lee.get(f"/engagements/{e1}/final-report").json() == before
          and len(lee.get(f"/engagements/{e1}/final-report/packages").json()["review"]
                  ["packages"]) == 1)

    print("\n[2. web and DOCX are rendered from that same stored version]")
    rebuilt = av.final_report_from_content(json.loads(version_content))
    check("the stored version rebuilds to exactly its stored content",
          av.content_hash(av.canonical_json(av.final_report_content(rebuilt))) == version_hash)
    pres = client_presentation(rebuilt)
    check("the stored web rendition is exactly the client HTML rendering of the stored version",
          stored["web"] == final_report_html.render_final_report_html(rebuilt, pres))
    check("the stored DOCX rendition is exactly the client DOCX rendering of the stored version",
          stored["docx"] == final_report_docx.render_final_report_docx(rebuilt, pres))
    check("both renditions carry the same business content (the North Star appears in each)",
          b"North Star One" in stored["web"] and "North Star One" in docx_text(stored["docx"]))
    check("the web rendition is static: no script, no external resource",
          b"<script" not in stored["web"].lower() and b"http" not in stored["web"].lower())

    print("\n[client-facing release renditions]")
    web_text, docx_text_ = rendition_text("web", stored["web"]), rendition_text("docx", stored["docx"])
    content = json.loads(version_content)
    check("the package is client-ready: its stored renditions pass the client-presentation check",
          p1["client_problems"] == [])
    check("neither rendition contains Peak's internal status text, footer or count lines",
          not any(" ".join(m.split()) in t for m in rp.PEAK_INTERNAL_MARKERS
                  for t in (web_text, docx_text_))
          and not any(pt.search(t) for pt in rp.PEAK_INTERNAL_PATTERNS
                      for t in (web_text, docx_text_)))
    ids = rp._identifiers(content, set())
    check("neither rendition contains an internal record identifier from the version content",
          ids and not any(i in t for i in ids for t in (web_text, docx_text_)))
    check("the title is the engagement's business name, not \"Final report\"",
          "<h1>One</h1>" in stored["web"].decode() and "Final report" not in docx_text_)
    check("the DOCX file name carries no \"final-report\" and no internal id",
          p1["renditions"]["docx"]["file_name"] == "synthetic-co-213-one.docx")
    statements = ([content["executive_overview"]["north_star"]]
                  + [f["statement"] for f in content["discovery_summary"]["findings"]]
                  + [c["statement"] for g in content["low_hanging_fruit"]["groups"]
                     for c in g["candidates"]])
    check("both renditions carry the same canonical business statements",
          statements and all(st in web_text and st in docx_text_ for st in statements))
    titles = [rp.CLIENT_SECTION_TITLES.get(k, content["section_titles"][k])
              for k in content["section_order"]]
    check("both renditions keep every section, in the canonical order",
          all(t in web_text and t in docx_text_ for t in titles)
          and [web_text.index(t) for t in titles] == sorted(web_text.index(t) for t in titles)
          and [docx_text_.index(t) for t in titles] == sorted(docx_text_.index(t) for t in titles))
    internal_docx = lee.get(f"/engagements/{e1}/final-report.docx").content
    check("the internal draft DOCX export is unchanged: still titled and bannered as a draft",
          "Final report" in rendition_text("docx", internal_docx)
          and "Internal draft" in rendition_text("docx", internal_docx))

    print("\n[3. stable, immutable identity and hash per rendition]")
    hashes = {k: v["rendition_hash"] for k, v in p1["renditions"].items()}
    check("each rendition hash is the sha256 of its stored bytes",
          all(hashes[k] == sha(stored[k]) for k in stored)
          and all(p1["renditions"][k]["byte_length"] == len(stored[k]) for k in stored))
    check("the package hash covers the version, its content hash and both rendition hashes",
          h1 == ap.package_hash(p1["artifact_version_id"], version_hash, hashes)
          and p1["hash_verified"])
    web = lee.get(f"/release-packages/{p1['id']}/web")
    docx = lee.get(f"/release-packages/{p1['id']}/docx")
    check("the web and DOCX routes serve the stored bytes, with their hashes",
          web.content == stored["web"] and docx.content == stored["docx"]
          and web.headers["x-peak-rendition-hash"] == hashes["web"]
          and docx.headers["x-peak-rendition-hash"] == hashes["docx"]
          and web.headers["content-type"].startswith("text/html")
          and "attachment" in docx.headers["content-disposition"])
    again = prepare(e1).json()["package"]
    check("preparing again with unchanged content and renderers creates no package",
          again["created"] is False and again["id"] == p1["id"])
    tokens = [p1["id"], p1["artifact_version_id"], h1, version_hash, *hashes.values()]
    check("no rendition carries a package or version id, a hash or a version number",
          all(t.encode() not in stored["web"] and t not in docx_text(stored["docx"])
              for t in tokens)
          and b"Version 1" not in stored["web"] and "Version 1" not in docx_text(stored["docx"]))

    # --- order and roles --------------------------------------------------------------------
    print("\n[the order and the roles]")
    check("final approval before the Lead approval -> lead_approval_required",
          code(decide(fran, p1["id"], "final-approval", "approved", h1))
          == "lead_approval_required")
    check("designating a Final Approver before the Lead approval -> lead_approval_required",
          code(act(lee, p1["id"], "final-approver", consultant_id=people["fran"]))
          == "lead_approval_required")
    check("release before any approval -> approvals_required",
          code(act(lee, p1["id"], "release", package_hash=h1)) == "approvals_required")
    check("a consultant who is not the engagement's assigned consultant -> not_lead_consultant",
          code(decide(sam, p1["id"], "lead-approval", "approved", h1)) == "not_lead_consultant")
    eu = engagement("Unassigned", assigned=False)
    pu = prepare(eu).json()["package"]
    check("an engagement with no assigned consultant -> no_lead_consultant",
          code(decide(lee, pu["id"], "lead-approval", "approved", pu["package_hash"]))
          == "no_lead_consultant")
    check("a Lead approval with a hash other than the package's -> hash_mismatch",
          code(decide(lee, p1["id"], "lead-approval", "approved", version_hash))
          == "hash_mismatch")

    print("\n[4. the Lead approval binds to the exact package]")
    r = decide(lee, p1["id"], "lead-approval", "approved", h1)
    v = r.json()["package"]
    check("the assigned consultant's Lead approval is recorded: state lead_approved",
          r.status_code == 200 and v["state"] == "lead_approved"
          and v["lead_decision"]["by"] == {"id": people["lee"], "name": "Lee Lead"})
    check("it is bound to this package's hash and to the underlying version's content hash",
          v["lead_decision"]["package_hash"] == h1
          and v["lead_decision"]["content_hash"] == version_hash)
    with factory() as s:
        row = s.scalar(select(ArtifactApproval).where(ArtifactApproval.id
                                                      == v["lead_decision"]["id"]))
        bound = (row.release_package_id, row.artifact_version_id) == (p1["id"],
                                                                      p1["artifact_version_id"])
    check("the approval record names the package and its version", bound)
    check("the Lead level cannot be decided twice",
          code(decide(lee, p1["id"], "lead-approval", "rejected", h1)) == "lead_decision_recorded")

    print("\n[Final Approver designation]")
    check("final approval with no designation -> no_final_approver_designated",
          code(decide(fran, p1["id"], "final-approval", "approved", h1))
          == "no_final_approver_designated")
    check("10. designating the Lead approver as Final Approver -> same_human",
          code(act(lee, p1["id"], "final-approver", consultant_id=people["lee"])) == "same_human")
    check("a consultant who is neither Lead approver nor assignee cannot designate",
          code(act(sam, p1["id"], "final-approver", consultant_id=people["fran"]))
          == "not_lead_consultant")
    check("an unknown consultant cannot be designated",
          code(act(lee, p1["id"], "final-approver", consultant_id="cons_missing"))
          == "invalid_field")
    first = act(lee, p1["id"], "final-approver", consultant_id=people["sam"]).json()["package"]
    second = act(lee, p1["id"], "final-approver", consultant_id=people["fran"]).json()["package"]
    hist = second["designations"]
    check("reassignment adds a designation that supersedes the first; the first is kept",
          [d["consultant"]["id"] for d in hist] == [people["sam"], people["fran"]]
          and hist[1]["supersedes_designation_id"] == hist[0]["id"]
          and hist[0] == first["designations"][0]
          and second["current_designation"]["consultant"]["id"] == people["fran"])
    check("re-designating the current designee is refused",
          code(act(lee, p1["id"], "final-approver", consultant_id=people["fran"]))
          == "already_designated")
    check("the replaced designee can no longer decide -> not_designated_final_approver",
          code(decide(sam, p1["id"], "final-approval", "approved", h1))
          == "not_designated_final_approver")
    check("10. the Lead approver cannot give the final approval -> same_human",
          code(decide(lee, p1["id"], "final-approval", "approved", h1)) == "same_human")
    check("release after only the Lead approval -> approvals_required",
          code(act(lee, p1["id"], "release", package_hash=h1)) == "approvals_required")

    print("\n[5. the final approval binds to the same package]")
    check("a final approval with the wrong hash -> hash_mismatch",
          code(decide(fran, p1["id"], "final-approval", "approved", "f" * 64)) == "hash_mismatch")
    r = decide(fran, p1["id"], "final-approval", "approved", h1, note="Ready for the client.")
    v = r.json()["package"]
    check("Fran's final approval is recorded: state final_approved",
          r.status_code == 200 and v["state"] == "final_approved"
          and v["final_decision"]["by"]["id"] == people["fran"]
          and v["final_decision"]["note"] == "Ready for the client.")
    check("both approvals carry the same package hash, under the designation in force",
          v["final_decision"]["package_hash"] == v["lead_decision"]["package_hash"] == h1
          and v["final_decision"]["designation_id"] == second["current_designation"]["id"])
    check("10. the two approvals come from different humans",
          v["lead_decision"]["by"]["id"] != v["final_decision"]["by"]["id"])
    check("no reassignment after the final decision -> final_decision_recorded",
          code(act(lee, p1["id"], "final-approver", consultant_id=people["sam"]))
          == "final_decision_recorded")

    print("\n[8. release returns the exact approved package]")
    check("a consultant who approved neither level cannot release -> not_an_approver",
          code(act(sam, p1["id"], "release", package_hash=h1)) == "not_an_approver")
    check("release with the wrong hash -> hash_mismatch",
          code(act(fran, p1["id"], "release", package_hash="a" * 64)) == "hash_mismatch")
    check("no package is released yet (404)",
          lee.get(f"/engagements/{e1}/final-report/released").status_code == 404)
    r = act(fran, p1["id"], "release", package_hash=h1)
    v = r.json()["package"]
    check("release succeeds: state released, who and when recorded, bound to the package hash",
          r.status_code == 200 and v["state"] == "released"
          and v["release"]["by"]["id"] == people["fran"] and v["release"]["at"]
          and v["release"]["package_hash"] == h1)
    released = lee.get(f"/engagements/{e1}/final-report/released").json()["package"]
    check("the engagement's released package is exactly the approved package",
          released["id"] == p1["id"] and released["package_hash"] == h1
          and released["renditions"] == p1["renditions"])
    with factory() as s:
        rel = s.scalar(select(ArtifactRelease).where(ArtifactRelease.release_package_id
                                                     == p1["id"]))
        rel_ok = (rel.lead_approval_id == v["lead_decision"]["id"]
                  and rel.final_approval_id == v["final_decision"]["id"]
                  and rel.artifact_version_id == p1["artifact_version_id"])
    check("the release record names the package, its version and the two approvals", rel_ok)
    check("a package is released once -> already_released",
          code(act(fran, p1["id"], "release", package_hash=h1)) == "already_released")

    # --- 9 + 7. renderer changes ------------------------------------------------------------------
    print("\n[9. released web and DOCX are never silently regenerated]")
    real_html, real_docx = (final_report_html.render_final_report_html,
                            final_report_docx.render_final_report_docx)
    final_report_html.render_final_report_html = lambda r, p=rp.INTERNAL: real_html(r, p).replace(
        b"</main>", b"<p>new layout</p></main>")
    final_report_docx.render_final_report_docx = lambda r, p=rp.INTERNAL: real_docx(r, p) + b"\0"
    try:
        web = lee.get(f"/release-packages/{p1['id']}/web").content
        docx = lee.get(f"/release-packages/{p1['id']}/docx").content
        check("after a renderer change, the released web rendition is still the approved bytes",
              web == stored["web"] and sha(web) == hashes["web"])
        check("after a renderer change, the released DOCX is still the approved file",
              docx == stored["docx"] and sha(docx) == hashes["docx"])

        print("\n[7. a changed rendition needs a new package and a new approval cycle]")
        p2 = prepare(e1).json()["package"]
        check("the same content with changed renditions makes package 2 on the same version",
              p2["created"] and p2["package_number"] == 2
              and p2["artifact_version_id"] == p1["artifact_version_id"]
              and p2["content_hash"] == version_hash)
        check("package 2 has new rendition hashes and a new package hash",
              p2["package_hash"] != h1
              and all(p2["renditions"][k]["rendition_hash"] != hashes[k] for k in hashes))
        check("package 2 starts with no approvals, designations or release",
              p2["state"] == "prepared" and p2["lead_decision"] is None
              and p2["final_decision"] is None and p2["designations"] == []
              and p2["release"] is None)
        check("an approval of package 1 cannot be used for package 2 -> hash_mismatch",
              code(decide(lee, p2["id"], "lead-approval", "approved", h1)) == "hash_mismatch")
        p1_now = get(p1["id"])
        check("package 1 stays released with its approvals, and reports its successor",
              p1_now["state"] == "released" and p1_now["superseded_by_package_id"] == p2["id"]
              and p1_now["lead_decision"]["decision"] == "approved")
        check("the released package for the engagement is still package 1 until 2 is released",
              lee.get(f"/engagements/{e1}/final-report/released").json()["package"]["id"]
              == p1["id"])
        e_mid = engagement("Mid-approval")
        pm = through_lead(e_mid)
        final_report_docx.render_final_report_docx = lambda r, p=rp.INTERNAL: real_docx(r, p) + b"\0\0"
        pm2 = prepare(e_mid).json()["package"]
        pm_now = get(pm["id"])
        check("a rendition change during approval supersedes the package; its Lead approval stays "
              "with it and does not carry over",
              pm2["created"] and pm_now["state"] == "superseded"
              and pm_now["lead_decision"]["decision"] == "approved"
              and pm2["lead_decision"] is None and pm2["designations"] == [])
        check("the superseded package cannot be approved -> package_superseded",
              code(decide(fran, pm["id"], "final-approval", "approved", pm["package_hash"]))
              == "package_superseded")
    finally:
        final_report_html.render_final_report_html = real_html
        final_report_docx.render_final_report_docx = real_docx

    # --- not client-facing -> not approvable or releasable --------------------------------------
    print("\n[a package without client-facing renditions cannot be approved or released]")
    ebad = engagement("Leaky")
    final_report_html.render_final_report_html = lambda r, p=rp.INTERNAL: real_html(r, rp.INTERNAL)
    try:
        pbad = prepare(ebad).json()["package"]
    finally:
        final_report_html.render_final_report_html = real_html
    check("a package whose web rendition is the internal draft is flagged not client-ready",
          pbad["client_problems"] and pbad["hash_verified"]
          and any("internal presentation text" in m for m in pbad["client_problems"])
          and any("internal title" in m for m in pbad["client_problems"])
          and any("internal identifier" in m for m in pbad["client_problems"]))
    check("its Lead approval is refused -> not_client_ready",
          code(decide(lee, pbad["id"], "lead-approval", "approved", pbad["package_hash"]))
          == "not_client_ready")
    egate = engagement("Gate")
    pg = through_lead(egate)
    decide(fran, pg["id"], "final-approval", "approved", pg["package_hash"])
    saved = rp.PEAK_INTERNAL_MARKERS
    rp.PEAK_INTERNAL_MARKERS = saved + ("North Star Gate",)  # a stricter check at release time
    try:
        check("release re-checks the stored renditions: a package failing the check is not released",
              code(act(fran, pg["id"], "release", package_hash=pg["package_hash"]))
              == "not_client_ready" and get(pg["id"])["state"] == "final_approved")
    finally:
        rp.PEAK_INTERNAL_MARKERS = saved

    print("\n[business content that says \"final report\" or \"internal\" is still client-ready]")
    words = engagement("Words")
    business_ns = "Deliver the final report on internal inventory controls by May"
    business_obs = "Internal audit asked for the final report; it is not client-facing yet."
    north_star(words, business_ns)
    lee.post(f"/engagements/{words}/observations",
             json={"observation_text": business_obs, "low_hanging_fruit": True,
                   "estimated_effort": "low", "estimated_value": "high"})
    pw = prepare(words).json()["package"]
    web_w = lee.get(f"/release-packages/{pw['id']}/web").content.decode()
    docx_w = rendition_text("docx", lee.get(f"/release-packages/{pw['id']}/docx").content)
    check("the package is client-ready despite those ordinary words in business content",
          pw["client_problems"] == [] and pw["hash_verified"])
    check("the business wording is kept verbatim in both renditions, not sanitized",
          all(t in rendition_text("web", web_w.encode()) and t in docx_w
              for t in (business_ns, business_obs)))
    r = decide(lee, pw["id"], "lead-approval", "approved", pw["package_hash"])
    check("and it can be approved", r.status_code == 200
          and r.json()["package"]["state"] == "lead_approved")
    ename = ada.post("/engagements", json={"client_id": client_id, "engagement_label": "Final report",
                                           "assigned_consultant_id": people["lee"]}
                     ).json()["engagement"]["id"]
    pn = prepare(ename).json()["package"]
    check("an engagement whose own business name is \"Final report\" may use it as its title",
          pn["client_problems"] == []
          and rendition_text("web", lee.get(f"/release-packages/{pn['id']}/web").content)
          .startswith("Final report"))

    # --- reviewed rendition ---------------------------------------------------------------------
    print("\n[each decision records which rendition the human reviewed]")
    erv = engagement("Reviewed")
    prv = prepare(erv).json()["package"]
    r = lee.post(f"/release-packages/{prv['id']}/lead-approval",
                 json={"decision": "approved", "package_hash": prv["package_hash"]})
    check("a decision without the reviewed rendition is refused (422)", r.status_code == 422)
    r = lee.post(f"/release-packages/{prv['id']}/lead-approval",
                 json={"decision": "approved", "package_hash": prv["package_hash"],
                       "reviewed_rendition": "pdf"})
    check("a rendition type the package does not hold is refused (422)", r.status_code == 422)
    decide(lee, prv["id"], "lead-approval", "approved", prv["package_hash"], reviewed="docx")
    act(lee, prv["id"], "final-approver", consultant_id=people["fran"])
    v = decide(fran, prv["id"], "final-approval", "approved", prv["package_hash"],
               reviewed="web").json()["package"]
    check("the Lead reviewed the DOCX and the Final Approver the web page: both recorded",
          v["lead_decision"]["reviewed_rendition"] == "docx"
          and v["final_decision"]["reviewed_rendition"] == "web")
    check("both decisions still bind the whole package by its package hash",
          v["lead_decision"]["package_hash"] == v["final_decision"]["package_hash"]
          == prv["package_hash"] and v["state"] == "final_approved")
    with factory() as s:
        kinds = sorted(a.reviewed_rendition_type for a in s.scalars(
            select(ArtifactApproval).where(ArtifactApproval.release_package_id == prv["id"])))
    check("the approval records store the reviewed rendition type", kinds == ["docx", "web"])

    # --- designation / final decision serialization ---------------------------------------------
    print("\n[designation and final decisions are serialized on the engagement row]")
    from sqlalchemy import event
    from sqlalchemy.dialects import mysql

    from peak.db.models import Engagement

    engine = factory.kw["bind"]
    log = []
    begin = lambda conn: log.append("BEGIN")  # noqa: E731
    stmt = lambda conn, cursor, statement, *a: log.append(" ".join(statement.split()))  # noqa: E731
    event.listen(engine, "begin", begin)
    event.listen(engine, "before_cursor_execute", stmt)
    try:
        elock = engagement("Lock")
        pl = through_lead(elock)
        log.clear()
        act(lee, pl["id"], "final-approver", consultant_id=people["sam"])
        designate_log = list(log)
        log.clear()
        decide(sam, pl["id"], "final-approval", "approved", pl["package_hash"])
        final_log = list(log)
    finally:
        event.remove(engine, "begin", begin)
        event.remove(engine, "before_cursor_execute", stmt)

    def lock_first(entries, insert_table):
        """In the transaction that inserts into ``insert_table``, the first statement locks."""
        txns, current = [], None
        for e in entries:
            if e == "BEGIN":
                current = []
                txns.append(current)
            elif current is not None:
                current.append(e)
        writing = [t for t in txns if any(f"INSERT INTO {insert_table}" in e for e in t)]
        return len(writing) == 1 and writing[0][0].startswith("SELECT engagements.id FROM engagements")

    check("a designation's transaction locks the engagement row before reading anything",
          lock_first(designate_log, "artifact_final_approver_designations"))
    check("a final decision's transaction locks the engagement row before reading anything",
          lock_first(final_log, "artifact_approvals"))
    lock_sql = str(select(Engagement.id).where(Engagement.id == "x").with_for_update()
                   .compile(dialect=mysql.dialect()))
    check("on MySQL that lock is SELECT ... FOR UPDATE", lock_sql.rstrip().endswith("FOR UPDATE"))
    check("the reassignment that committed first decides who may approve: the new designee did",
          get(pl["id"])["final_decision"]["by"]["id"] == people["sam"])

    # --- 6. working data ----------------------------------------------------------------------
    print("\n[6. changing working data does not alter an existing package]")
    e6 = engagement("Six")
    p6 = prepare(e6).json()["package"]
    web_before = lee.get(f"/release-packages/{p6['id']}/web").content
    docx_before = lee.get(f"/release-packages/{p6['id']}/docx").content
    north_star(e6, "Six, edited after the package")
    lee.post(f"/engagements/{e6}/observations", json={"observation_text": "A later note."})
    p6_now = get(p6["id"])
    check("the package, its hashes and its renditions are unchanged",
          p6_now["package_hash"] == p6["package_hash"] and p6_now["hash_verified"]
          and lee.get(f"/release-packages/{p6['id']}/web").content == web_before
          and lee.get(f"/release-packages/{p6['id']}/docx").content == docx_before
          and b"edited after" not in web_before)
    check("the review says the live draft no longer matches the package",
          lee.get(f"/engagements/{e6}/final-report/packages").json()["review"]
          ["draft_matches_latest"] is False)
    r = decide(lee, p6["id"], "lead-approval", "approved", p6["package_hash"])
    check("the existing package stays reviewable and approvable as it was prepared",
          r.status_code == 200 and r.json()["package"]["state"] == "lead_approved")
    p6b = prepare(e6).json()["package"]
    check("changed content makes a new version and a new package, with no inherited approvals",
          p6b["created"] and p6b["version_number"] == 2 and p6b["package_number"] == 2
          and p6b["lead_decision"] is None and b"edited after" in
          lee.get(f"/release-packages/{p6b['id']}/web").content)
    check("the earlier package is superseded and keeps its Lead approval",
          get(p6["id"])["state"] == "superseded"
          and get(p6["id"])["lead_decision"]["decision"] == "approved")

    # --- tampering ------------------------------------------------------------------------------
    print("\n[stored bytes or content that no longer match their hash block every act]")
    et = engagement("Tamper")
    pt = through_lead(et)
    decide(fran, pt["id"], "final-approval", "approved", pt["package_hash"])
    et2 = engagement("Tamper-b")
    pt2 = prepare(et2).json()["package"]
    et3 = engagement("Tamper-c")
    pt3 = prepare(et3).json()["package"]
    with factory() as s:  # raw SQL, below the ORM guards: simulates out-of-band tampering
        s.execute(text("UPDATE artifact_renditions SET content_bytes = :b "
                       "WHERE release_package_id IN (:a, :c) AND rendition_type = 'docx'"),
                  {"b": b"tampered", "a": pt["id"], "c": pt2["id"]})
        s.execute(text("UPDATE artifact_versions SET content_canonical = '{}' WHERE id = :v"),
                  {"v": pt3["artifact_version_id"]})
        s.commit()
    check("a tampered package reports hash_verified false", get(pt["id"])["hash_verified"] is False)
    check("release of a tampered package is refused even with both approvals -> hash_mismatch",
          code(act(fran, pt["id"], "release", package_hash=pt["package_hash"]))
          == "hash_mismatch")
    check("approval of a package with a tampered rendition is refused -> hash_mismatch",
          code(decide(lee, pt2["id"], "lead-approval", "approved", pt2["package_hash"]))
          == "hash_mismatch")
    check("approval of a package whose version content was tampered is refused -> hash_mismatch",
          code(decide(lee, pt3["id"], "lead-approval", "approved", pt3["package_hash"]))
          == "hash_mismatch")
    check("a tampered rendition is not served (422)",
          lee.get(f"/release-packages/{pt2['id']}/docx").status_code == 422)

    # --- rejection ------------------------------------------------------------------------------
    print("\n[rejection applies to the package and blocks progression]")
    e3 = engagement("Three")
    w = prepare(e3).json()["package"]
    rv = decide(lee, w["id"], "lead-approval", "rejected", w["package_hash"],
                note="Recommendations need evidence.").json()["package"]
    check("a Lead rejection is recorded with its note: state rejected, package kept",
          rv["state"] == "rejected" and rv["lead_decision"]["note"] == "Recommendations need evidence."
          and get(w["id"])["hash_verified"])
    check("after a Lead rejection: no designation, no final approval, no release",
          code(act(lee, w["id"], "final-approver", consultant_id=people["fran"]))
          == "lead_approval_required"
          and code(decide(fran, w["id"], "final-approval", "approved", w["package_hash"]))
          == "lead_approval_required"
          and code(act(lee, w["id"], "release", package_hash=w["package_hash"]))
          == "approvals_required")
    e4 = engagement("Four")
    x = through_lead(e4)
    r = decide(fran, x["id"], "final-approval", "rejected", x["package_hash"],
               note="Limitations section is incomplete.")
    check("a final rejection is recorded with its note: state rejected",
          r.json()["package"]["state"] == "rejected"
          and r.json()["package"]["final_decision"]["note"] == "Limitations section is incomplete.")
    check("a final rejection blocks release and reassignment",
          code(act(lee, x["id"], "release", package_hash=x["package_hash"]))
          == "approvals_required"
          and code(act(lee, x["id"], "final-approver", consultant_id=people["sam"]))
          == "final_decision_recorded")
    r = prepare(e4)
    check("a rejected package is terminal: preparing the identical package again is refused",
          code(r) == "package_rejected"
          and len(lee.get(f"/engagements/{e4}/final-report/packages").json()["review"]
                  ["packages"]) == 1)
    north_star(e4, "Four, revised after rejection")
    r = prepare(e4)
    check("after a real change, a new package starts a fresh approval cycle",
          r.status_code == 201 and r.json()["package"]["state"] == "prepared"
          and get(x["id"])["state"] == "superseded")

    # --- immutability ---------------------------------------------------------------------------
    print("\n[append-only: packages, renditions, approvals and releases are immutable]")

    def orm_edit_rendition():
        with factory() as s:
            s.scalars(select(ArtifactRendition)).first().content_bytes = b"x"
            s.commit()

    def bulk_edit_package():
        with factory() as s:
            s.execute(update(ArtifactReleasePackage).values(package_hash="0" * 64))
            s.commit()

    def edit_approval():
        with factory() as s:
            s.execute(update(ArtifactApproval).values(decision="rejected"))
            s.commit()

    def edit_designation():
        with factory() as s:
            s.scalars(select(ArtifactFinalApproverDesignation)).first() \
                .designated_consultant_id = people["lee"]
            s.commit()

    def delete_release():
        with factory() as s:
            s.delete(s.scalars(select(ArtifactRelease)).first())
            s.commit()

    def orm_edit_version():
        with factory() as s:
            s.get(ArtifactVersion, p1["artifact_version_id"]).content_canonical = "{}"
            s.commit()

    check("an ORM edit of rendition bytes is refused", raises(orm_edit_rendition, PermissionError))
    check("a bulk UPDATE of a package is refused", raises(bulk_edit_package, PermissionError))
    check("a bulk UPDATE of an approval is refused", raises(edit_approval, PermissionError))
    check("editing a designation is refused", raises(edit_designation, PermissionError))
    check("deleting a release is refused", raises(delete_release, PermissionError))
    check("an ORM edit of the released version's content is refused",
          raises(orm_edit_version, PermissionError))
    final = get(p1["id"])
    with factory() as s:
        stored_status = s.get(ArtifactVersion, p1["artifact_version_id"]).version_status
    check("the released package is unchanged: same hash, re-verified, still released",
          final["package_hash"] == h1 and final["hash_verified"] and final["state"] == "released"
          and lee.get(f"/release-packages/{p1['id']}/web").content == stored["web"])
    check("artifact_versions itself was never updated (stored version_status is still versioned)",
          stored_status == "versioned")
    pairs = {k for k in allowlist.WORKSPACE_WRITE_COLUMNS
             if k[0] in allowlist.ARTIFACT_RECORD_TABLES | allowlist.ARTIFACT_APPROVAL_TABLES}
    check("the allowlist holds only create actions for artifact tables, none for versions' status",
          pairs == {("artifacts", "create_artifact"),
                    ("artifact_versions", "create_artifact_version"),
                    ("artifact_release_packages", "create_release_package"),
                    ("artifact_renditions", "create_artifact_rendition"),
                    ("artifact_approvals", "create_artifact_approval"),
                    ("artifact_final_approver_designations", "create_final_approver_designation"),
                    ("artifact_releases", "create_artifact_release")})
    routes = [(r.path, m) for r in app.routes for m in getattr(r, "methods", ())
              if "release-packages" in r.path or "/packages" in r.path or "released" in r.path]
    check("no DELETE, PATCH or PUT route and no generic status endpoint for packages",
          routes and all(m in ("GET", "POST", "HEAD") for _, m in routes)
          and not any("status" in p for p, _ in routes))

    return lee, e1, [p1, p2], people


def client_facing_checks(lee, eid, packages, people):
    print("\n[nothing reaches the live report output]")
    from peak.reports.final_report import FinalReport

    # ``approved_for_client`` is the Phase 208 draft flag (always False); nothing else may match.
    fields = {f.name for f in dataclasses.fields(FinalReport)} - {"approved_for_client"}
    check("FinalReport gains no version, package, approval, designation or release field",
          not {n for n in fields if any(w in n for w in ("version", "package", "approv",
                                                          "release", "designat", "artifact"))})
    body = lee.get(f"/engagements/{eid}/final-report").json()
    docx = lee.get(f"/engagements/{eid}/final-report.docx").content
    tokens = [people["fran"], "lead_consultant", "final_approver", "Fran Final",
              "Ready for the client."]
    for p in packages:
        tokens += [p["id"], p["package_hash"], p["artifact_version_id"]]
    check("the report JSON, Markdown and DOCX carry no package, approval or release data",
          all(t not in str(body) and t.encode() not in docx for t in tokens))
    check("the live report is still an unapproved internal draft",
          body["report"]["approved_for_client"] is False and body["report"]["client_facing"] is False)
    for method in ("post", "patch", "put", "delete"):
        r = getattr(lee, method)(f"/engagements/{eid}/final-report")
        check(f"{method.upper()} on the final-report route is still refused ({r.status_code})",
              r.status_code in (404, 405))


def main() -> int:
    print("Phase 213 — Release packages, two-stage approval and release")
    tmp = tempfile.mkdtemp()
    try:
        migration_checks(tmp)
        purity_checks()
        client_facing_checks(*main_checks(build(tmp)))
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
