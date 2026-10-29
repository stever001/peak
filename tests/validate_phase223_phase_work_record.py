#!/usr/bin/env python3
"""Phase 223 — phase work record (offline; temporary SQLite and a temporary local store only).

Proves:

1. **No schema or write path.** Phase 223 adds no migration, table, allowlist action or persistence
   classification. The service and route write nothing, and the route accepts no other method.
2. **Authorization and scoping.** Logged out 401; an unknown phase 404; any signed-in consultant
   reads it, as with every phase read. Only rows of this phase and its engagement appear: another
   engagement's work, an interview or engagement observation, a suggested task, and rows forged
   with a mismatched engagement are left out.
3. **Content and provenance.** Each agreed task's outcome, result summary and not-applicable reason
   verbatim; every record with its corrections; current captures with the replaced ones counted;
   observations written during the task with their linked captures; who and when for each; totals
   that match.
4. **State transitions.** The record follows the phase from planned through authorized work to
   completed, and its readiness is the Phase 217 readiness exactly.
5. **Determinism, and reads write nothing.** Two reads compose the same record; reading changes no
   row anywhere; task and phase state, the assessment and the Final Report are unchanged.
6. **No automatic content, no leaks.** No observation, finding or recommendation is created; no
   storage key, file name or hash is returned.
7. **Degrade path.** ``getPhaseWorkRecord`` returns null (never notFound) when the API cannot
   compose the record; the page says so.
8. **Static UI checks.** Read-only page (no form or action), touch-sized links, no generated
   wording, the advisory-boundary scan, and no report, artifact or publication code reads the record.

Exit status: 0 all checks passed; 1 a check failed.
"""

from __future__ import annotations

import hashlib
import json
import os
import re
import shutil
import sqlite3
import subprocess
import sys
import tempfile

REPO_ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
TESTS = os.path.join(REPO_ROOT, "tests")
for p in (REPO_ROOT, TESTS):
    if p not in sys.path:
        sys.path.insert(0, p)

import validate_phase220_guided_evidence_capture as p220  # noqa: E402  (shared fixtures)

SERVICE = "peak/workspace/phase_work_record.py"
RECORD_PAGE = "web/app/(workspace)/phases/[id]/record/page.tsx"
PHASE_PAGE = "web/app/(workspace)/phases/[id]/page.tsx"
WEB = os.path.join(REPO_ROOT, "web")
_failures = []


def check(label, ok):
    print(f"  [{'PASS' if ok else 'FAIL'}] {label}")
    if not ok:
        _failures.append(label)


code, read = p220.code, p220.read


def _snapshot(db):
    """Every row of every table, hashed: proves a read changed nothing at all."""
    con = sqlite3.connect(db)
    names = sorted(r[0] for r in con.execute(
        "SELECT name FROM sqlite_master WHERE type='table' AND name NOT LIKE 'sqlite_%'"))
    digest = {}
    for n in names:
        rows = sorted(repr(r) for r in con.execute(f'SELECT * FROM "{n}"'))
        digest[n] = hashlib.sha256("\n".join(rows).encode()).hexdigest()
    con.close()
    return digest


def _strip_paths(value):
    """The record without its short-lived content paths (signed tokens carry a timestamp)."""
    if isinstance(value, dict):
        return {k: _strip_paths(v) for k, v in value.items() if k != "content_path"}
    if isinstance(value, list):
        return [_strip_paths(v) for v in value]
    return value


# --------------------------------------------------------------------------- 1. no schema


def schema_checks():
    print("\n[1. no schema change, no write path]")
    from peak.persistence import allowlist, runtime_persistence as rp

    versions = os.listdir(os.path.join(REPO_ROOT, "alembic", "versions"))
    mentions = [v for v in versions if v.endswith(".py") and re.search(
        r"phase.?223|work.?record", read(os.path.join("alembic", "versions", v)), re.I)]
    check("Phase 223 adds no migration (no revision mentions it or the work record)", not mentions)
    check("no table, allowlist action or persistence classification names the work record",
          not any("work_record" in t for t in rp.RUNTIME_TABLE_PERSISTENCE)
          and not any("work_record" in t or "work_record" in a
                      for (t, a) in allowlist.WORKSPACE_WRITE_COLUMNS)
          and "work_record" not in read("peak/db/models.py"))
    src = read(SERVICE)
    check("the service has no write: no add, update, delete, commit or allowlist call",
          not re.search(r"session\.(add|delete|commit|merge|flush|execute\(\s*(update|delete|insert))"
                        r"|_require_allowed|\bupdate\(|\binsert\(", src))
    check("the service imports no report, workflow, artifact, approval or publication code",
          not re.search(r"peak\.(reports|workflows|agentnet)|\b(artifacts|approvals)\b", src))
    check("the service reads no image content",
          not re.search(r"^\s*(import|from)\s+(PIL|exif|pytesseract|cv2|piexif)", src, re.M)
          and "evidence_storage" not in src and "evidence_content" not in src)


# --------------------------------------------------------------------------- 2-6. app


def app_checks(tmp):
    print("\n[2-6. authorization, scoping, content, transitions, determinism, boundary]")
    from peak.db.models import ObservationTaskOrigin, PhaseTaskRecord
    from peak.workspace import engagement_phases, phase_work_record as pwr

    app, factory, store, client, db = p220._setup(tmp)
    lee, cam, anon = client("lee"), client("cam"), client()
    cam_name, lee_name = "Cam Consultant", "Lee Lead"
    lee_id = lee.get("/auth/me").json()["consultant"]["id"]
    pid, phase = p220._phase(lee, "Alpha")
    eid = phase["engagement_id"]
    t = {x["sequence"]: x for x in phase["tasks"]}
    pid_b, phase_b = p220._phase(lee, "Beta")
    eid_b, tid_b = phase_b["engagement_id"], phase_b["tasks"][0]["id"]
    pid_c, _ = p220._phase(lee, "Gamma", authorize=False)

    def record(c=cam, phase_id=pid):
        r = c.get(f"/phases/{phase_id}/work-record")
        return r, (r.json().get("work_record") if r.status_code == 200 else None)

    def upload(task_id, caption, supersedes=None):
        grant = cam.get(f"/tasks/{task_id}/evidence").json()["task_evidence"]["upload"]["grant"]
        data = {"grant": grant, "caption": caption, "evidence_kind": "photo"}
        if supersedes:
            data["supersedes_evidence_id"] = supersedes
        r = anon.post("/evidence-uploads", data=data,
                      files={"file": ("IMG_7731.JPG", p220.JPEG, "image/jpeg")})
        assert r.status_code == 201, r.text
        return r.json()["evidence"]["id"]

    # Authorization.
    check("logged out, the work record returns 401", anon.get(f"/phases/{pid}/work-record")
          .status_code == 401)
    check("an unknown phase returns 404", record(phase_id="ephase_0000000000000000")[0]
          .status_code == 404)
    check("any signed-in consultant reads it (as with every phase read); the Lead and Admin too",
          record()[0].status_code == 200 and record(lee)[0].status_code == 200)
    check("the route accepts no write method (POST, PUT, PATCH, DELETE are 405)",
          all(getattr(cam, m)(f"/phases/{pid}/work-record").status_code == 405
              for m in ("post", "put", "patch", "delete")))

    # Planned and freshly authorized states.
    _, planned = record(phase_id=pid_c)
    check("a planned phase's record: status planned, nothing recorded, readiness says not authorized",
          planned["phase"]["status"] == "planned" and planned["phase"]["authorization"] is None
          and all(planned["totals"][k] == 0 for k in planned["totals"] if k not in ("tasks", "open"))
          and planned["readiness"]["blocking"][0]["code"] == "phase_not_authorized")
    _, fresh = record()
    check("an authorized phase with no work: every agreed task open, nothing recorded",
          fresh["totals"]["tasks"] == 6 and fresh["totals"]["open"] == 6
          and all(not x["records"] and not x["captures"] and not x["observations"]
                  for x in fresh["tasks"])
          and [x["sequence"] for x in fresh["tasks"]] == [1, 2, 3, 4, 5, 6])
    check("the authorization shows what the client agreed to, who recorded it and when",
          fresh["phase"]["authorization"]["basis"] == "Client agreed by email (synthetic)"
          and fresh["phase"]["authorization"]["authorized_by"] == lee_name
          and fresh["phase"]["authorization"]["authorized_at"])
    check("the header names the client and engagement",
          fresh["engagement"] == {"id": eid, "engagement_label": "Alpha",
                                  "client_name": "Synthetic Alpha"})

    # Work, through the Phase 217-222 paths only.
    r1 = cam.post(f"/tasks/{t[1]['id']}/records",
                  json={"record_kind": "note", "record_text": "Dock 3 log is on paper."}
                  ).json()["phase"]
    first_rec = next(r for r in next(x for x in r1["tasks"] if x["id"] == t[1]["id"])["records"])
    cam.post(f"/tasks/{t[1]['id']}/records",
             json={"record_kind": "note", "record_text": "Dock 3 log is on paper; keyed next day.",
                   "supersedes_record_id": first_rec["id"]})
    cap1 = upload(t[1]["id"], "Receiving log, dock 3")
    cap1b = upload(t[1]["id"], "Receiving log, dock 3 (clearer)", supersedes=cap1)
    cap2 = upload(t[2]["id"], "Packing slip without a PO number")
    upload(tid_b, "Other engagement photo")
    plain = cam.post(f"/engagements/{eid}/observations",
                     json={"observation_text": "Engagement-level note, not task work."}
                     ).json()["observation"]
    obs_text = "Receipts are keyed a day after the goods arrive."
    o1 = cam.post(f"/tasks/{t[1]['id']}/observations",
                  json={"observation_text": obs_text, "basis": "observed",
                        "evidence_ids": [cap2, cap1b]}).json()["observation"]
    cam.post(f"/tasks/{tid_b}/observations", json={"observation_text": "Other engagement."})
    summary1 = "Watched three deliveries; all were logged on paper first."
    cam.post(f"/tasks/{t[1]['id']}/completion", json={"result_summary": summary1})
    cam.post(f"/tasks/{t[2]['id']}/records",
             json={"record_kind": "note", "record_text": "Sampled 20 slips; all matched."})
    cam.post(f"/tasks/{t[2]['id']}/completion", json={"result_summary": "No mismatches found."})
    na_reason = "There is no camera on site today."
    cam.post(f"/tasks/{t[5]['id']}/not-applicable", json={"reason": na_reason})
    engagement_phases.add_task(factory, pid, {"title": "Count the returns cage",
                                              "instructions": "Count it.",
                                              "inclusion_reason": "Synthesis suggestion"},
                               lee_id, origin="si_suggested")

    before_read = _snapshot(db)
    assess_before = lee.get(f"/engagements/{eid}/assessment").json()
    report_before = lee.get(f"/engagements/{eid}/final-report").json()
    phase_before = lee.get(f"/phases/{pid}").json()["phase"]
    resp, rec = record()
    by_seq = {x["sequence"]: x for x in rec["tasks"]}
    one, two, three, five = by_seq[1], by_seq[2], by_seq[3], by_seq[5]

    check("outcomes follow the work: done, done, did not apply (condition), open, not applicable, open",
          [by_seq[i]["outcome"] for i in range(1, 7)]
          == ["completed", "completed", "does_not_apply", "open", "not_applicable", "open"])
    check("the result summary and not-applicable reason are the consultant's words, verbatim",
          one["result_summary"] == summary1 and five["not_applicable_reason"] == na_reason
          and one["completed_by"] == cam_name and one["completed_at"])
    check("every record is kept: the correction is current, the earlier version carries superseded_by",
          len(one["records"]) == 2
          and {r["id"]: r["superseded_by"] for r in one["records"]}[first_rec["id"]]
          and [r["record_text"] for r in one["records"] if r["superseded_by"] is None]
          == ["Dock 3 log is on paper; keyed next day."]
          and all(r["recorded_by"] == cam_name for r in one["records"]))
    check("only current captures are listed; the replaced one is counted, not shown",
          [c["id"] for c in one["captures"]] == [cap1b] and one["replaced_captures"] == 1
          and [c["id"] for c in two["captures"]] == [cap2]
          and one["captures"][0]["uploaded_by"] == cam_name
          and one["captures"][0]["interpreted"] is False and one["captures"][0]["content_path"])
    check("observations written during the task appear under it, verbatim, with their origin",
          [o["id"] for o in one["observations"]] == [o1["id"]]
          and one["observations"][0]["observation_text"] == obs_text
          and one["observations"][0]["basis"] == "observed"
          and one["observations"][0]["origin"]["task_id"] == t[1]["id"]
          and one["observations"][0]["recorded_by"] == cam_name
          and not two["observations"] and not three["observations"])
    check("an observation's linked captures come with it, as linked (including another task's)",
          sorted(e["id"] for e in rec["evidence_links"][o1["id"]]) == sorted([cap1b, cap2])
          and {e["id"]: e["task"]["id"] for e in rec["evidence_links"][o1["id"]]}[cap2] == t[2]["id"]
          and rec["evidence_links"][o1["id"]][0]["linked_by"] == cam_name)
    body = json.dumps(rec)
    check("the engagement-level observation and the other engagement's work are left out",
          plain["id"] not in body and eid_b not in body and pid_b not in body and tid_b not in body
          and "Other engagement" not in body)
    check("a suggested task is not agreed work: left out, and counted",
          rec["suggested_not_accepted"] == 1 and "Count the returns cage" not in body
          and len(rec["tasks"]) == 6)
    check("totals match the rows",
          rec["totals"] == {"tasks": 6, "completed": 2, "not_applicable": 1, "does_not_apply": 1,
                            "open": 2, "records": 2, "corrected_records": 1, "captures": 2,
                            "replaced_captures": 1, "observations": 1, "linked_captures": 2})
    check("readiness is the Phase 217 readiness exactly",
          rec["readiness"] == phase_before["readiness"])
    check("the record says it is composed, not stored or interpreted",
          rec["composition"]["stored"] is False and rec["composition"]["interpreted"] is False
          and "Nothing is summarized, inferred or saved" in rec["composition"]["rule"])

    # Determinism, and reads write nothing.
    _, again = record(lee)
    direct = [pwr.phase_work_record(factory, pid) for _ in range(2)]
    check("two reads compose the same record (content paths aside); the service is deterministic",
          _strip_paths(again) == _strip_paths(rec) and direct[0] == direct[1]
          and _strip_paths(rec) == json.loads(json.dumps(direct[0])))
    for _ in range(3):
        record()
        record(phase_id=pid_c)
        record(phase_id="ephase_0000000000000000")
    check("reading the record changes no row in any table", _snapshot(db) == before_read)
    phase_after = lee.get(f"/phases/{pid}").json()["phase"]
    check("task status, phase status and readiness are unchanged by reading",
          phase_after["status"] == phase_before["status"]
          and [x["status"] for x in phase_after["tasks"]]
          == [x["status"] for x in phase_before["tasks"]]
          and phase_after["readiness"] == phase_before["readiness"])
    assess_after = lee.get(f"/engagements/{eid}/assessment").json()
    report_after = lee.get(f"/engagements/{eid}/final-report").json()
    check("no observation, finding or recommendation is created: the assessment and Final Report "
          "are unchanged by reading the record",
          json.dumps(assess_after["assessment"], sort_keys=True)
          == json.dumps(assess_before["assessment"], sort_keys=True)
          and json.dumps(report_after.get("report"), sort_keys=True)
          == json.dumps(report_before.get("report"), sort_keys=True))
    check("the work record appears nowhere in the assessment or Final Report responses",
          "work_record" not in json.dumps(assess_after) and "work_record" not in json.dumps(report_after))

    # Forged rows with a mismatched engagement are never shown.
    with factory() as s:
        s.add(ObservationTaskOrigin(id="otor_forged000000000", client_id="c", engagement_id=eid_b,
                                    observation_id=plain["id"], phase_id=pid, task_id=t[4]["id"]))
        s.add(PhaseTaskRecord(id="ptrec_forged00000000", client_id="c", engagement_id=eid_b,
                              phase_id=pid, task_id=t[4]["id"], record_kind="note",
                              record_text="Forged across engagements.",
                              recorded_by_consultant_id=lee_id))
        s.commit()
    _, scoped = record()
    check("rows naming this phase but another engagement are left out (scoped by both ids)",
          _strip_paths(scoped) == _strip_paths(rec) and "Forged" not in json.dumps(scoped))
    con = sqlite3.connect(db)  # insert-only tables: remove the forged rows with raw SQL
    con.execute("DELETE FROM observation_task_origins WHERE id = 'otor_forged000000000'")
    con.execute("DELETE FROM phase_task_records WHERE id = 'ptrec_forged00000000'")
    con.commit()
    con.close()

    # No leaks.
    con = sqlite3.connect(db)
    secrets_ = [r[0] for r in con.execute("SELECT storage_key FROM phase_task_evidence")]
    secrets_ += [r[0] for r in con.execute("SELECT file_name FROM phase_task_evidence") if r[0]]
    secrets_ += [r[0] for r in con.execute("SELECT content_hash FROM phase_task_evidence")]
    con.close()
    check("no storage key, device file name or hash in the response",
          secrets_ and not any(x in resp.text for x in secrets_)
          and not any(k in resp.text for k in ('"storage_key"', '"file_name"', '"content_hash"')))
    check("no consultant id beyond the records' own (names are shown instead)",
          lee_id not in json.dumps({k: v for k, v in rec.items() if k != "tasks"}))

    # State transition: finish the work and complete the phase; the record follows.
    cam.post(f"/tasks/{t[4]['id']}/records",
             json={"record_kind": "interview_response", "record_text": "Staff key receipts at 4pm."})
    cam.post(f"/tasks/{t[4]['id']}/completion", json={"result_summary": "Interviewed two staff."})
    cam.post(f"/tasks/{t[6]['id']}/records", json={"record_kind": "note", "record_text": "Rework."})
    cam.post(f"/tasks/{t[6]['id']}/completion", json={"result_summary": "Rework at keying."})
    done = cam.post(f"/phases/{pid}/completion")
    _, closed = record()
    check("after the phase is completed, the record shows it closed, who completed it and when",
          done.status_code == 200 and closed["phase"]["status"] == "completed"
          and closed["phase"]["work_plan_status"] == "closed"
          and closed["phase"]["completed_by"] == cam_name and closed["phase"]["completed_at"]
          and closed["readiness"]["ready"] is True and closed["totals"]["open"] == 0)
    check("Phase 220-222 reads still answer for the same task",
          cam.get(f"/tasks/{t[1]['id']}/evidence").status_code == 200
          and cam.get(f"/tasks/{t[1]['id']}/observations").status_code == 200
          and cam.get(f"/engagements/{eid}/evidence").status_code == 200)


# --------------------------------------------------------------------------- 7. degrade


def fetch_checks(tmp):
    print("\n[7. degrade path: getPhaseWorkRecord under Node]")
    node = shutil.which("node")
    if node is None or not os.path.isdir(os.path.join(WEB, "node_modules", "typescript")):
        print("  [skip] Node or web/node_modules not installed")
        return
    script = os.path.join(tmp, "record_fetch.cjs")
    runner = p220._EVIDENCE_FETCH_RUNNER.replace('getTaskEvidence("ptask_x")',
                                                 'getPhaseWorkRecord("ephase_x")')
    with open(script, "w", encoding="utf-8") as f:
        f.write(runner)
    live = {"tasks": [], "totals": {"tasks": 0}, "phase": {"id": "ephase_x"}}
    cases = [{"status": 200, "body": {"work_record": live}},
             {"status": 404, "body": {"detail": "Not Found"}},
             {"status": 500},
             {"throws": True},
             {"status": 200, "body": {"something": "else"}},
             {"status": 401, "body": {"detail": "x"}}]
    out = subprocess.run([node, script, os.path.join(WEB, "node_modules", "typescript"),
                          os.path.join(WEB, "lib", "api.ts")],
                         input=json.dumps(cases), capture_output=True, text=True)
    if out.returncode != 0:
        check("getPhaseWorkRecord runs under Node", False)
        print("    " + out.stderr.strip()[-400:])
        return
    r = json.loads(out.stdout)
    check("available: the API's record is returned unchanged", r[0]["result"] == live)
    check("route absent (404), failing, unreachable or answering something else: null, never "
          "notFound() or an error", all(x["result"] is None and x["error"] is None for x in r[1:5]))
    check("a missing session goes to /login", r[5]["error"] == "redirect:/login")
    check("loading the record is a single GET (no mutation)",
          all(x["calls"] == [{"url": "http://127.0.0.1:8000/phases/ephase_x/work-record",
                              "method": "GET"}] for x in r))


# --------------------------------------------------------------------------- 8. static


def static_checks():
    print("\n[8. static UI checks]")
    page, phase_page = read(RECORD_PAGE), read(PHASE_PAGE)
    check("the record page loads the phase as before, then the record through getPhaseWorkRecord",
          "apiGet<{ phase: EngagementPhaseDetail }>" in page and "getPhaseWorkRecord(p.id)" in page
          and "/work-record" not in page)
    check("the record page degrades: it says the record is unavailable",
          "if (!rec)" in page and "The phase work record is currently unavailable here." in page)
    check("the record page is read-only: no form, server action or action import",
          "<form" not in page and "action=" not in page and "-actions" not in page
          and "use server" not in page)
    check("the phase workspace links to the record (not for a planned phase)",
          "/phases/${p.id}/record" in phase_page and 'p.status !== "planned"' in phase_page)
    links = re.findall(r"<(?:Link|a)\b[^>]*className=\"([^\"]*)\"", page)
    check("every link on the record page is touch-sized", links and all("min-h-touch" in c
                                                                        for c in links))
    check("no id is rendered as text (ids only in hrefs, keys and aria attributes)",
          not re.search(r"(?<![=$])\{[\w.]*\.id\}", page) and not re.search(r"_id\}", page))
    check("no generated wording: nothing on the page is composed from a record or caption",
          not re.search(r"(record_text|caption|result_summary|observation_text)\s*\.\s*(slice|split|"
                        r"replace|substring)", page))
    from peak.workspace import advisory_boundary as b

    texts = p220._visible_text([page, phase_page[phase_page.index("Phase 223"):][:900],
                                read(SERVICE)])
    hits = {x for x in texts if b.framing_violations(x)}
    hits |= {x for x in texts if re.search(r"\b(audit\w*|complian\w*|certif\w*|attest\w*|score\w*"
                                           r"|pass(ed)?|fail(ed)?)\b", x, re.I)}
    check("no audit / compliance / scoring language in the new UI and service text", not hits)
    if hits:
        print("    " + "; ".join(sorted(hits)))
    check("no report, workflow, artifact or AgentNet code reads the work record",
          not any("phase_work_record" in read(os.path.join(d, f)) or "work-record"
                  in read(os.path.join(d, f))
                  for d in ("peak/reports", "peak/workflows", "peak/agentnet")
                  for f in os.listdir(os.path.join(REPO_ROOT, d)) if f.endswith(".py"))
          and "work_record" not in read("peak/workspace/artifacts.py")
          and "work_record" not in read("peak/workspace/approvals.py"))
    check("the Final Report and assessment views do not show the record",
          "WorkRecord" not in read("web/components/final-report-view.tsx")
          and "WorkRecord" not in read("web/components/assessment-view.tsx"))
    app_src = read("peak/consultant_api/app.py")
    check("the API has exactly one work-record route, a GET",
          re.findall(r"@app\.(\w+)\(\"[^\"]*work-record\"", app_src) == ["get"])
    check("docs/PHASE223_PHASE_WORK_RECORD.md exists",
          os.path.exists(os.path.join(REPO_ROOT, "docs/PHASE223_PHASE_WORK_RECORD.md")))


def main() -> int:
    print("Peak Phase 223 phase work record check")
    print("=" * 39)
    try:
        import argon2, fastapi, httpx, itsdangerous, multipart, sqlalchemy  # noqa: F401,E401
    except ImportError:
        print("  [skip] web dependencies not installed — run with PYTHON=.venv/bin/python")
        return 0
    schema_checks()
    with tempfile.TemporaryDirectory(prefix="peak_phase223_") as tmp:
        app_checks(tmp)
        fetch_checks(tmp)
    static_checks()

    print("\nSummary")
    print(f"  failures : {len(_failures)}")
    print("RESULT: " + ("PASS" if not _failures else "FAIL"))
    return 0 if not _failures else 1


if __name__ == "__main__":
    sys.exit(main())
