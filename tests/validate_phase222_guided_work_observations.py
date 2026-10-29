#!/usr/bin/env python3
"""Phase 222 — guided work observations (offline; temporary SQLite and a temporary local store only).

Proves:

1. **Migration 025.** Upgrade from 024 creates exactly ``observation_task_origins``; its columns
   match the model; an observation has at most one origin (UNIQUE); downgrade removes it; the
   migration carries no data and alters no existing table.
2. **Persistence policy.** The table is append-only; the allowlist has a single create action; the
   ORM refuses update and delete, singly and in bulk.
3. **Recording.** A consultant records an observation during a task, with and without linked
   evidence. It is an ordinary observation of the task's engagement, in the consultant's words,
   recorded by the signed-in consultant, and its origin names the phase and task. The task page
   read lists it; the engagement's observations list it with its origin; other observations have
   none.
4. **Refusals.** Another engagement's evidence, an unknown task, a task of a phase not yet
   authorized, a resolved task, an interview, a task of another engagement, missing text and a
   change of origin on edit are refused, and a refused save writes nothing.
5. **Nothing automatic.** Task records and captured evidence create no observation.
6. **Assessment.** A work observation becomes a discovery-derived finding like any other, quoting
   the consultant's text; the response carries its origin and links beside the assessment.
7. **Boundary.** Recording changes only observations, origins and links. Evidence-backed findings,
   the Final Report's recommendations, task status and phase readiness are unchanged.
8. **No leaks.** No response carries a storage key or device file name.
9. **Static UI checks.** The task page lists and adds observations, degrades without the API, sends
   no generated wording, and labels the source neutrally.

Exit status: 0 all checks passed; 1 a check failed.
"""

from __future__ import annotations

import json
import os
import re
import sqlite3
import sys
import tempfile

REPO_ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
TESTS = os.path.join(REPO_ROOT, "tests")
for p in (REPO_ROOT, TESTS):
    if p not in sys.path:
        sys.path.insert(0, p)

import validate_phase220_guided_evidence_capture as p220  # noqa: E402  (shared fixtures)
from _schema_history import head_descends_from  # noqa: E402

TABLE = "observation_task_origins"
TASK_PAGE = "web/app/(workspace)/phases/[id]/tasks/[taskId]/page.tsx"
UI_FILES = (
    TASK_PAGE,
    "web/components/observed-during.tsx",
    "web/components/discovery-section.tsx",
    "web/components/observation-form.tsx",
    "web/components/assessment-view.tsx",
    "web/app/discovery-actions.ts",
    "web/app/(workspace)/engagements/[id]/assessment/page.tsx",
    "web/app/(workspace)/observations/[id]/edit/page.tsx",
)
_failures = []


def check(label, ok):
    print(f"  [{'PASS' if ok else 'FAIL'}] {label}")
    if not ok:
        _failures.append(label)


code, read, alembic = p220.code, p220.read, p220.alembic


# --------------------------------------------------------------------------- 1. migration


def migration_checks(tmp):
    print("\n[1. migration 025]")
    import sqlalchemy as sa

    import peak.db.models as m

    db = os.path.join(tmp, "mig.sqlite3")

    def inspector():
        return sa.inspect(sa.create_engine(f"sqlite:///{db}"))

    alembic(db, "upgrade", "024_observation_evidence_links").check_returncode()
    before = set(inspector().get_table_names())
    up = alembic(db, "upgrade", "025_observation_task_origins")
    check("upgrade to 025 creates exactly observation_task_origins",
          up.returncode == 0 and set(inspector().get_table_names()) - before == {TABLE})
    check("the head is 025 or descends from it",
          head_descends_from(REPO_ROOT, "025_observation_task_origins"))
    migrated = {c["name"] for c in inspector().get_columns(TABLE)}
    check("the migrated columns match the model",
          migrated == set(m.Base.metadata.tables[TABLE].columns.keys()))
    check("the model is registered in ALL_MODELS", TABLE in {t.__tablename__ for t in m.ALL_MODELS})
    con = sqlite3.connect(db)
    sql = ("INSERT INTO observation_task_origins (id, client_id, engagement_id, observation_id,"
           " phase_id, task_id, review_status, lifecycle_status)"
           " VALUES (?, 'c', 'e', ?, 'p', ?, 'draft', 'draft')")
    con.execute(sql, ("r1", "o1", "t1"))
    con.execute(sql, ("r2", "o2", "t1"))
    try:
        con.execute(sql, ("r3", "o1", "t2"))
        dup_refused = False
    except sqlite3.IntegrityError:
        dup_refused = True
    con.rollback()
    con.close()
    check("UNIQUE(observation) gives an observation at most one origin; a task may have many",
          dup_refused)
    down = alembic(db, "downgrade", "024_observation_evidence_links")
    check("downgrade to 024 removes exactly that table",
          down.returncode == 0 and set(inspector().get_table_names()) == before)
    body = read("alembic/versions/025_observation_task_origins.py").split('"""', 2)[2].lower()
    check("migration 025 carries no data and alters no existing table",
          "insert" not in body and "op.execute" not in body and "add_column" not in body
          and "alter_column" not in body and body.count("create_table") == 1)


# --------------------------------------------------------------------------- 2. policy


def policy_checks(tmp):
    print("\n[2. persistence policy]")
    import sqlalchemy as sa

    from peak.db.models import ObservationTaskOrigin
    from peak.db.session import create_session_factory
    from peak.persistence import allowlist, runtime_persistence as rp

    check("observation_task_origins is append-only (no UPDATE grant needed)",
          rp.RUNTIME_TABLE_PERSISTENCE.get(TABLE) == rp.APPEND_ONLY)
    actions = [a for (t, a) in allowlist.WORKSPACE_WRITE_COLUMNS if t == TABLE]
    check("the allowlist has one create action and nothing else",
          actions == ["create_observation_task_origin"])
    db = os.path.join(tmp, "orm.sqlite3")
    alembic(db, "upgrade", "head").check_returncode()
    factory = create_session_factory(url=f"sqlite:///{db}")
    with factory() as s:
        s.add(ObservationTaskOrigin(id="otor_x", client_id="c", engagement_id="e",
                                    observation_id="o", phase_id="p", task_id="t"))
        s.commit()
    refused = []
    for attempt in ("update", "delete", "bulk_update", "bulk_delete"):
        with factory() as s:
            row = s.get(ObservationTaskOrigin, "otor_x")
            try:
                if attempt == "update":
                    row.task_id = "other"
                    s.commit()
                elif attempt == "delete":
                    s.delete(row)
                    s.commit()
                else:
                    stmt = (sa.update(ObservationTaskOrigin).values(task_id="z")
                            if attempt == "bulk_update" else sa.delete(ObservationTaskOrigin))
                    s.execute(stmt)
                    s.commit()
            except PermissionError:
                refused.append(attempt)
    check("the ORM refuses update and delete, singly and in bulk",
          refused == ["update", "delete", "bulk_update", "bulk_delete"])


# --------------------------------------------------------------------------- 3-8. app


def app_checks(tmp):
    print("\n[3-8. recording, refusals, assessment, boundary, leaks]")
    from peak.workspace import discovery
    from peak.workspace.service import WorkspaceError

    app, factory, store, client, db = p220._setup(tmp)
    lee, cam, anon = client("lee"), client("cam"), client()
    cam_name = "Cam Consultant"
    pid, phase = p220._phase(lee, "Alpha")
    task, other = phase["tasks"][0], phase["tasks"][1]
    tid, eid = task["id"], phase["engagement_id"]
    pid_b, phase_b = p220._phase(lee, "Beta")
    tid_b, eid_b = phase_b["tasks"][0]["id"], phase_b["engagement_id"]
    _, phase_c = p220._phase(lee, "Gamma", authorize=False)
    tid_planned = phase_c["tasks"][0]["id"]

    def upload(task_id, caption):
        grant = cam.get(f"/tasks/{task_id}/evidence").json()["task_evidence"]["upload"]["grant"]
        r = anon.post("/evidence-uploads", data={"grant": grant, "caption": caption},
                      files={"file": ("IMG_4410.JPG", p220.JPEG, "image/jpeg")})
        assert r.status_code == 201, r.text
        return r.json()["evidence"]["id"]

    def observe(text=None, ids=None, task_id=tid, c=cam, **extra):
        body = {**({"observation_text": text} if text is not None else {}),
                **({"evidence_ids": ids} if ids is not None else {}), **extra}
        return c.post(f"/tasks/{task_id}/observations", json=body)

    def listed(task_id=tid):
        return cam.get(f"/tasks/{task_id}/observations").json()["task_observations"]

    check("logged out, a task's observations return 401 (read and write)",
          anon.get(f"/tasks/{tid}/observations").status_code == 401
          and anon.post(f"/tasks/{tid}/observations",
                        json={"observation_text": "x"}).status_code == 401)
    check("an unknown task returns 404 (read and write)",
          cam.get("/tasks/ptask_0000000000000000/observations").status_code == 404
          and observe("x", task_id="ptask_0000000000000000").status_code == 404)
    empty = listed()
    check("a task with no observations lists none, and recording is open",
          empty["observations"] == [] and empty["recording_closed"] is None
          and empty["engagement_id"] == eid and empty["phase_id"] == pid)

    # Nothing automatic: records and captures create no observation.
    counts0 = p220._counts(db)
    r_rec = cam.post(f"/tasks/{tid}/records",
                     json={"record_kind": "note", "record_text": "Dock 3 log is on paper."})
    e1 = upload(tid, "Receiving log, dock 3")
    e2 = upload(other["id"], "Pallet label without a location")
    e_b = upload(tid_b, "Other engagement photo")
    counts1 = p220._counts(db)
    check("a task record and captured evidence create no observation and no origin",
          r_rec.status_code == 201 and counts1["discovery_observations"]
          == counts0["discovery_observations"] and counts1[TABLE] == counts0[TABLE] == 0)

    # Snapshot the derived views before any work observation.
    plain = cam.post(f"/engagements/{eid}/observations",
                     json={"observation_text": "Receiving staff sign for deliveries unseen."}
                     ).json()["observation"]
    assess_before = lee.get(f"/engagements/{eid}/assessment").json()
    report_before = lee.get(f"/engagements/{eid}/final-report").json()
    phase_before = lee.get(f"/phases/{pid}").json()["phase"]
    counts_before = p220._counts(db)

    text_one = "The dock 3 receiving log is keyed into the system a day later."
    r_one = observe(text_one, basis="observed")
    o_one = r_one.json()["observation"]
    origin = o_one["origin"]
    check("a work observation is created (201) in the task's engagement, by the signed-in consultant",
          r_one.status_code == 201 and o_one["engagement_id"] == eid
          and o_one["recorded_by"] == cam_name and o_one["session"] is None)
    check("its text and basis are exactly what the consultant entered",
          o_one["observation_text"] == text_one and o_one["basis"] == "observed")
    check("its origin names the phase and task it was recorded during",
          origin == {"phase_id": pid, "phase_title": phase["title"], "task_id": tid,
                     "task_title": task["title"], "task_sequence": task["sequence"]})
    r_ev = observe("Pallet labels and the receiving log disagree on location.", [e1, e2])
    o_ev = r_ev.json()["observation"]
    ev_links = cam.get(f"/engagements/{eid}/evidence").json()["engagement_evidence"]["links"]
    check("a work observation can link captures of its engagement (this task's and another's)",
          r_ev.status_code == 201 and sorted(i["id"] for i in ev_links.get(o_ev["id"], []))
          == sorted([e1, e2]) and o_one["id"] not in ev_links)

    got = listed()
    check("the task page read lists exactly its observations, each with its origin",
          sorted(o["id"] for o in got["observations"]) == sorted([o_ev["id"], o_one["id"]])
          and all(o["origin"]["task_id"] == tid for o in got["observations"]))
    check("another task of the phase lists none of them", listed(other["id"])["observations"] == [])
    obs_list = cam.get(f"/engagements/{eid}/discovery").json()["discovery"]["observations"]
    by_id = {o["id"]: o for o in obs_list}
    check("the engagement's observations include them with their origin; others have none",
          by_id[o_one["id"]]["origin"]["task_id"] == tid and by_id[plain["id"]]["origin"] is None)
    check("a single observation read carries its origin",
          cam.get(f"/observations/{o_one['id']}").json()["observation"]["origin"] == origin)
    r_edit = cam.patch(f"/observations/{o_one['id']}",
                       json={"observation_text": text_one + " Confirmed with the supervisor."})
    check("a work observation is edited in place like any other, and keeps its origin",
          r_edit.status_code == 200 and r_edit.json()["observation"]["origin"] == origin
          and r_edit.json()["observation"]["observation_text"].endswith("supervisor."))

    # Refusals, and a refused save writes nothing.
    rows_before = p220._counts(db)
    r_cross = observe("Cross engagement.", [e_b])
    r_planned = observe("Not authorized yet.", task_id=tid_planned)
    r_session = observe("With an interview.", session_id="dsess_0000000000000000")
    r_no_text = observe()
    r_blank = observe("   ")
    r_move = cam.patch(f"/observations/{o_one['id']}", json={"task_id": tid_b})
    try:
        discovery.create_observation(factory, eid_b, {"observation_text": "Wrong task."},
                                     "cons_x", task_id=tid)
        wrong_task = None
    except WorkspaceError as exc:
        wrong_task = exc.code
    check("another engagement's evidence is refused (invalid_link)",
          code(r_cross) == "invalid_link")
    check("a task of a phase not yet authorized is refused (phase_not_authorized)",
          code(r_planned) == "phase_not_authorized")
    check("a work observation cannot name an interview, or move to another task on edit (422)",
          r_session.status_code == 422 and r_move.status_code == 422)
    check("a task of another engagement is refused (invalid_link)", wrong_task == "invalid_link")
    check("missing or blank text is refused: nothing is written for the consultant",
          r_no_text.status_code == 422 and code(r_blank) == "invalid_field")
    check("a refused save writes nothing: no observation, origin or link",
          p220._counts(db) == rows_before)
    check("a planned phase's task reads as closed for observations",
          listed(tid_planned)["recording_closed"]["code"] == "phase_not_authorized")

    # Assessment.
    assess_after = lee.get(f"/engagements/{eid}/assessment").json()
    report_after = lee.get(f"/engagements/{eid}/final-report").json()
    phase_after = lee.get(f"/phases/{pid}").json()["phase"]
    findings = {f["trace"]["observation_id"]: f
                for f in assess_after["assessment"]["discovery"]["findings"]}
    plain_finding = findings[plain["id"]]
    work_finding = findings.get(o_one["id"])
    check("a work observation becomes a discovery-derived finding, quoting the consultant's text",
          work_finding is not None and work_finding["statement"].startswith(text_one)
          and set(work_finding) == set(plain_finding)
          and work_finding["trace"]["session_id"] is None)
    check("the response carries each work observation's origin beside the assessment",
          assess_after["observation_origins"] == {o_one["id"]: origin, o_ev["id"]: origin}
          and plain["id"] not in assess_after["observation_origins"])
    check("and its linked evidence beside it too",
          sorted(i["id"] for i in assess_after["observation_evidence"][o_ev["id"]])
          == sorted([e1, e2]))
    check("no origin or task id appears inside the assessment or the Final Report",
          "observation_origins" not in json.dumps(assess_after["assessment"])
          and tid not in json.dumps(assess_after["assessment"])
          and tid not in json.dumps(report_after))

    # Boundary.
    counts_after = p220._counts(db)
    changed = {t for t in counts_after if counts_after[t] != counts_before.get(t)}
    check("recording changed only observations, their origins and links",
          changed <= {"discovery_observations", TABLE, "observation_evidence_links"}
          and counts_after[TABLE] == 2
          and counts_after["discovery_observations"] - counts_before["discovery_observations"] == 2)
    a_before, a_after = assess_before["assessment"], assess_after["assessment"]
    check("evidence-backed findings, recommendations and readiness inputs are unchanged",
          all(a_before.get(k) == a_after.get(k) for k in a_before
              if k not in ("discovery", "generated_at", "created_at")))
    check("the plain observation's finding is unchanged",
          next(f for f in a_before["discovery"]["findings"]
               if f["trace"]["observation_id"] == plain["id"]) == plain_finding)
    check("the Final Report's recommendation material is unchanged",
          json.dumps(report_before.get("report", {}).get("recommendations"), sort_keys=True)
          == json.dumps(report_after.get("report", {}).get("recommendations"), sort_keys=True))
    check("task status and phase readiness are unchanged by observations",
          phase_after["readiness"] == phase_before["readiness"]
          and [t["status"] for t in phase_after["tasks"]]
          == [t["status"] for t in phase_before["tasks"]])
    reads = p220._counts(db)
    listed()
    lee.get(f"/engagements/{eid}/assessment")
    check("reading task observations and the assessment changes no table",
          p220._counts(db) == reads)

    r_na = lee.post(f"/tasks/{other['id']}/not-applicable", json={"reason": "No second dock here."})
    check("a resolved task is closed for new observations (task_resolved)",
          r_na.status_code == 200 and code(observe("Too late.", task_id=other["id"])) == "task_resolved"
          and listed(other["id"])["recording_closed"]["code"] == "task_resolved")

    # No leaks.
    con = sqlite3.connect(db)
    secrets_ = [r[0] for r in con.execute("SELECT storage_key FROM phase_task_evidence")]
    secrets_ += [r[0] for r in con.execute("SELECT file_name FROM phase_task_evidence") if r[0]]
    con.close()
    bodies = [json.dumps(listed()), json.dumps(assess_after), r_one.text, r_ev.text]
    check("no response carries a storage key or device file name",
          secrets_ and not any(s in b for s in secrets_ for b in bodies)
          and not any(k in b for b in bodies for k in ('"storage_key"', '"file_name"')))


# --------------------------------------------------------------------------- 9. static


def static_checks():
    print("\n[9. static UI checks]")
    check("the UI files exist", all(os.path.exists(os.path.join(REPO_ROOT, p)) for p in UI_FILES))
    ui = {p: read(p) for p in UI_FILES}
    page = ui[TASK_PAGE]
    check("the task page lists the task's observations and offers Add observation",
          "getTaskObservations(t.id)" in page and "<ObservationCard" in page
          and "Add observation" in page and "createTaskObservation.bind(null, p.id, t.id" in page)
    check("the task page's form has no interview or question choice",
          re.search(r"<ObservationForm action=\{createTaskObservation[^/]*?(sessions|questions)=",
                    page, re.S) is None)
    check("the task page degrades when the API cannot list observations",
          "!obs ?" in page and "obs && !obs.recording_closed" in page)
    api = read("web/lib/api.ts")
    check("getTaskObservations returns null (never notFound) when unavailable",
          re.search(r"export async function getTaskObservations.{0,400}?\}\s*catch \{\s*return null;",
                    api, re.S) is not None)
    during = ui["web/components/observed-during.tsx"]
    view = ui["web/components/assessment-view.tsx"]
    card = ui["web/components/discovery-section.tsx"]
    check("the source is labelled neutrally: Work observation · Observed during: the task",
          "Observed during:" in during and '"Work observation"' in view
          and ">Work observation<" in card and "<ObservedDuring origin={origin} />" in view
          and "<ObservedDuring origin={o.origin} />" in ui["web/app/(workspace)/observations/[id]/edit/page.tsx"])
    check("the Final Report view is unchanged: it shows no origin",
          "origin" not in read("web/components/final-report-view.tsx"))
    check("no generated wording: the observation text is never filled from a record or capture",
          not re.search(r"observation_text[^\n]*(caption|record_text|result_summary)"
                        r"|(caption|record_text|result_summary)[^\n]*observation_text",
                        "\n".join(ui.values()) + read("peak/workspace/task_observations.py")))
    from peak.workspace import advisory_boundary as b

    new_text = [during, page[page.index("Phase 222"):page.index("Phase 222") + 2400]]
    hits = {t for t in p220._visible_text(new_text) if b.framing_violations(t)}
    hits |= {t for t in p220._visible_text(new_text)
             if re.search(r"\b(audit\w*|complian\w*|certif\w*|attest\w*)\b", t, re.I)}
    check("no audit / compliance / deficiency language in the new UI text", not hits)
    if hits:
        print("    " + "; ".join(sorted(hits)))
    service = read("peak/workspace/task_observations.py")
    check("the service reads no image content and imports no report or finding code",
          not re.search(r"^\s*(import|from)\s+(PIL|exif|pytesseract|cv2|piexif)", service, re.M)
          and "peak.reports" not in service and "peak.workflows" not in service)
    check("the assessment and report builders do not read task origins",
          not any("observation_task_origins" in read(os.path.join(d, f)) or "ObservationTaskOrigin"
                  in read(os.path.join(d, f))
                  for d in ("peak/reports", "peak/workflows")
                  for f in os.listdir(os.path.join(REPO_ROOT, d)) if f.endswith(".py")))
    check("no route removes, edits or moves an origin",
          not re.search(r"@app\.(delete|patch|put)\([^)]*(task_id\}/observations|origin)",
                        read("peak/consultant_api/app.py")))
    check("docs/PHASE222_GUIDED_WORK_OBSERVATIONS.md exists",
          os.path.exists(os.path.join(REPO_ROOT, "docs/PHASE222_GUIDED_WORK_OBSERVATIONS.md")))


def main() -> int:
    print("Peak Phase 222 guided work observations check")
    print("=" * 46)
    try:
        import argon2, fastapi, httpx, itsdangerous, multipart, sqlalchemy  # noqa: F401,E401
    except ImportError:
        print("  [skip] web dependencies not installed — run with PYTHON=.venv/bin/python")
        return 0
    with tempfile.TemporaryDirectory(prefix="peak_phase222_") as tmp:
        migration_checks(tmp)
        policy_checks(tmp)
        app_checks(tmp)
    static_checks()

    print("\nSummary")
    print(f"  failures : {len(_failures)}")
    print("RESULT: " + ("PASS" if not _failures else "FAIL"))
    return 0 if not _failures else 1


if __name__ == "__main__":
    sys.exit(main())
