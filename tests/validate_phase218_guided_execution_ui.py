#!/usr/bin/env python3
"""Phase 218 — iPad-first guided execution UI (offline; temporary SQLite only).

Proves:

1. **Read-only API additions.** ``GET /phases/{id}`` adds each task's ``work_state`` (applies,
   prerequisites, condition task, record still needed, completion blockers), the roadmap source,
   and names (authorized by, completed by, recorded by). Reading creates nothing, and completion is
   refused with exactly the first blocker the read reported.
2. **Guided flow through the API the UI calls.** Planned versus authorized phases; ordered tasks;
   required and optional; all four record kinds sent with the payloads ``web/lib/work-plan.ts``
   builds (run under Node); correction by supersession; completion blocked, then allowed;
   not applicable with a reason; a suggested task accepted; readiness moving to ready; phase
   completion; logged-out requests refused (401).
3. **Static UI checks.** The routes, server actions and components exist; the proxy guards
   ``/phases``; no photo or document capture is offered; the new UI carries no audit or compliance
   language; work-plan code calls no discovery observation endpoint; the record form is never
   prefilled from guidance; no migration was added.

Exit status: 0 all checks passed; 1 a check failed.
"""

from __future__ import annotations

import json
import os
import re
import shutil
import subprocess
import sys
import tempfile

REPO_ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
if REPO_ROOT not in sys.path:
    sys.path.insert(0, REPO_ROOT)

WEB = os.path.join(REPO_ROOT, "web")
PASSWORD = "phase218-password"
SECRET = "phase218-secret-key-phase218-secret-key"
UI_FILES = (
    "web/app/work-plan-actions.ts",
    "web/lib/work-plan.ts",
    "web/components/work-plan-actions.tsx",
    "web/components/work-plan-parts.tsx",
    "web/components/work-plan-record-form.tsx",
    "web/components/work-plan-section.tsx",
    "web/app/(workspace)/phases/[id]/page.tsx",
    "web/app/(workspace)/phases/[id]/tasks/[taskId]/page.tsx",
)
_failures = []


def check(label, ok):
    print(f"  [{'PASS' if ok else 'FAIL'}] {label}")
    if not ok:
        _failures.append(label)


def alembic(db, *args):
    env = {k: v for k, v in os.environ.items() if not k.startswith("PEAK_")}
    env["PEAK_DATABASE_URL"] = f"sqlite:///{db}"
    return subprocess.run([sys.executable, "-m", "alembic", *args], cwd=REPO_ROOT, env=env,
                          capture_output=True, text=True)


def code(response):
    detail = response.json().get("detail") if response.status_code >= 400 else None
    return detail.get("code") if isinstance(detail, dict) else response.status_code


def read(path):
    with open(os.path.join(REPO_ROOT, path), encoding="utf-8") as f:
        return f.read()


# --------------------------------------------------------------------------- web payloads


def web_payloads(tmp, cases):
    """``recordPayload`` from web/lib/work-plan.ts, run under Node on each form-field dict.

    Returns None when Node or the web dependencies are not installed.
    """
    node = shutil.which("node")
    if node is None or not os.path.isdir(os.path.join(WEB, "node_modules", "typescript")):
        return None
    script = os.path.join(tmp, "payloads.cjs")
    with open(script, "w", encoding="utf-8") as f:
        f.write("""
const fs = require("fs");
const ts = require(process.argv[2]);
const src = fs.readFileSync(process.argv[3], "utf8");
const js = ts.transpileModule(src, { compilerOptions: { module: ts.ModuleKind.CommonJS,
                                                        target: ts.ScriptTarget.ES2020 } }).outputText;
const mod = { exports: {} };
new Function("module", "exports", "require", js)(mod, mod.exports, require);
const cases = JSON.parse(fs.readFileSync(0, "utf8"));
process.stdout.write(JSON.stringify(cases.map((c) => mod.exports.recordPayload(c))));
""")
    out = subprocess.run([node, script, os.path.join(WEB, "node_modules", "typescript"),
                          os.path.join(WEB, "lib", "work-plan.ts")],
                         input=json.dumps(cases), capture_output=True, text=True, check=True)
    return json.loads(out.stdout)


# --------------------------------------------------------------------------- app


def _setup(tmp):
    from fastapi.testclient import TestClient

    from peak import accounts
    from peak.consultant_api.app import create_app
    from peak.db.session import create_session_factory
    from peak.workspace import discovery

    db = os.path.join(tmp, "app.sqlite3")
    alembic(db, "upgrade", "head").check_returncode()
    factory = create_session_factory(url=f"sqlite:///{db}")
    qid = discovery.create_question(factory, {"prompt": "Walk me through receiving.",
                                              "category": "Receiving and storage",
                                              "answer_type": "long_text"},
                                    seed_key="rcv_walkthrough")["id"]
    people = {}
    for key, name, role in (("ada", "Ada Admin", "admin"), ("lee", "Lee Lead", "consultant")):
        people[key] = accounts.create_consultant(factory, name=name, email=f"{key}@example.com",
                                                 role=role, password=PASSWORD)["id"]
    app = create_app(session_factory=factory, secret_key=SECRET, secure_cookie=True)
    clients = {}
    for key in people:
        clients[key] = TestClient(app, base_url="https://testserver")
        clients[key].post("/auth/login", json={"email": f"{key}@example.com", "password": PASSWORD})
    clients["anon"] = TestClient(app, base_url="https://testserver")
    return factory, qid, people, clients


def _counts(factory):
    from sqlalchemy import func, select

    from peak.db import models

    with factory() as s:
        return {m.__tablename__: s.scalar(select(func.count()).select_from(m.__table__))
                for m in models.ALL_MODELS}


def app_checks(tmp):
    from peak.db import models
    from peak.workspace import engagement_phases as ep

    factory, qid, people, c = _setup(tmp)
    ada, lee, anon = c["ada"], c["lee"], c["anon"]

    cid = ada.post("/clients", json={"organization_label": "Synthetic Supply Co"}).json()["client"]["id"]
    eid = ada.post("/engagements", json={"client_id": cid, "engagement_label": "Synthetic Ops",
                                         "assigned_consultant_id": people["lee"]}
                   ).json()["engagement"]["id"]
    obs = [lee.post(f"/engagements/{eid}/observations",
                    json={"observation_text": text, "question_id": qid, "basis": "testimony"}
                    ).json()["observation"]["id"]
           for text in ("Receivers described frequent differences between slips and POs.",
                        "Two shifts receive differently.")]
    item = lee.post(f"/engagements/{eid}/roadmap-items",
                    json={"template_key": "receiving_accuracy", "source_observation_ids": obs}
                    ).json()["roadmap_item"]
    lee.post(f"/roadmap-items/{item['id']}/decision", json={"status": "accepted"})
    pid = lee.post(f"/engagements/{eid}/phases", json={"roadmap_item_id": item["id"]}
                   ).json()["phase"]["id"]
    lee.post(f"/phases/{pid}/template-tasks", json={})

    print("\n[1. read-only API additions]")
    before = _counts(factory)
    planned = lee.get(f"/phases/{pid}").json()["phase"]
    check("reading a phase creates nothing", _counts(factory) == before)
    check("a planned phase shows its roadmap source and no authorization",
          planned["status"] == "planned" and planned["authorization"] is None
          and planned["roadmap_item"] == {"id": item["id"], "title": item["title"],
                                          "status": "accepted"})
    tasks = planned["tasks"]
    t1, t2, t3, t4, t5, t6 = (t["id"] for t in tasks)
    check("tasks are ordered 1-6 with required and optional marked",
          [t["sequence"] for t in tasks] == [1, 2, 3, 4, 5, 6]
          and [t["required"] for t in tasks] == [True, True, True, True, False, True])
    ws = {t["id"]: t["work_state"] for t in tasks}
    check("every task carries a work_state with the five fields",
          all(set(w) == {"applies", "prerequisites", "condition_task", "record_missing",
                         "completion_blockers"} for w in ws.values()))
    check("prerequisites name the earlier tasks with sequence, title and resolved",
          ws[t6]["prerequisites"] == [{"task_id": t["id"], "sequence": t["sequence"],
                                       "title": t["title"], "resolved": False}
                                      for t in tasks[:4]])
    check("the conditional task names its condition task; whether it applies is still open",
          ws[t3]["condition_task"] == {"task_id": t2, "sequence": 2, "title": tasks[1]["title"]}
          and ws[t3]["applies"] is None and ws[t1]["applies"] is True)
    check("records-required tasks report a record still needed; the optional one does not",
          ws[t1]["record_missing"] is True and ws[t5]["record_missing"] is False)
    check("completion blockers carry the API's codes in check order",
          [b["code"] for b in ws[t1]["completion_blockers"]] == ["record_required"]
          and [b["code"] for b in ws[t4]["completion_blockers"]]
          == ["prerequisites_incomplete", "record_required"])
    check("work cannot be recorded on a planned phase",
          code(lee.post(f"/tasks/{t1}/records", json={"record_kind": "note", "record_text": "x"}))
          == "phase_not_authorized")

    lee.post(f"/phases/{pid}/authorization",
             json={"authorization_basis": "Client signed the Phase 1 proposal."})
    phase = lee.get(f"/phases/{pid}").json()["phase"]
    check("an authorized phase shows who authorized it, by name",
          phase["status"] == "authorized" and phase["authorization"]["authorized_by"] == "Lee Lead")
    r = lee.post(f"/tasks/{t1}/completion", json={"result_summary": "Done."})
    check("completion is refused with exactly the first blocker the read reported",
          code(r) == ws[t1]["completion_blockers"][0]["code"]
          and r.json()["detail"]["message"] == ws[t1]["completion_blockers"][0]["message"])

    print("\n[2. guided flow with the web payloads]")
    forms = [
        {"record_kind": "note", "record_text": "  Truck unloaded to staging.  ", "basis": "observed",
         "structured_question": "ignored for a note"},
        {"record_kind": "mismatch", "record_text": "Short shipped by 2 cases.", "basis": "document",
         "structured_reference": "PO 1001 / PS 88", "structured_expected": "10 cases",
         "structured_observed": "8 cases", "structured_resolution": ""},
        {"record_kind": "interview_response", "record_text": "We count after put-away.",
         "structured_question": "When do you count?", "structured_interviewee_role": "receiving lead",
         "basis": ""},
        {"record_kind": "measurement", "record_text": "Dock to stock took 95 minutes.",
         "structured_measure": "dock-to-stock time", "structured_value": "95",
         "structured_unit": "minutes"},
    ]
    payloads = web_payloads(tmp, forms)
    if payloads is None:
        print("  [skip] node or web/node_modules not installed — using the expected payloads")
    expected = [
        {"record_kind": "note", "record_text": "Truck unloaded to staging.", "basis": "observed"},
        {"record_kind": "mismatch", "record_text": "Short shipped by 2 cases.", "basis": "document",
         "structured": {"reference": "PO 1001 / PS 88", "expected": "10 cases",
                        "observed": "8 cases"}},
        {"record_kind": "interview_response", "record_text": "We count after put-away.",
         "structured": {"question": "When do you count?", "interviewee_role": "receiving lead"}},
        {"record_kind": "measurement", "record_text": "Dock to stock took 95 minutes.",
         "structured": {"measure": "dock-to-stock time", "value": 95, "unit": "minutes"}},
    ]
    if payloads is not None:
        check("the web form builds trimmed payloads, drops blanks and other kinds' fields, "
              "and sends a numeric value as a number", payloads == expected)
    payloads = payloads or expected
    note, mismatch, interview, measurement = payloads

    r1 = lee.post(f"/tasks/{t1}/records", json=note)
    r2 = lee.post(f"/tasks/{t2}/records", json=mismatch)
    r4 = lee.post(f"/tasks/{t4}/records", json=interview)
    r1b = lee.post(f"/tasks/{t1}/records", json=measurement)
    check("the API accepts all four record kinds as the web form sends them",
          [r.status_code for r in (r1, r2, r4, r1b)] == [201, 201, 201, 201])
    phase = r1b.json()["phase"]
    task = {t["id"]: t for t in phase["tasks"]}
    rec = task[t1]["records"]
    check("records come back with structured fields and the recorder's name",
          next(r for r in rec if r["record_kind"] == "measurement")["structured"]
          == {"measure": "dock-to-stock time", "value": 95, "unit": "minutes"}
          and {r["recorded_by"] for r in rec} == {"Lee Lead"})
    check("recording starts the task and clears 'record still needed'",
          task[t1]["status"] == "in_progress" and task[t1]["work_state"]["record_missing"] is False
          and task[t1]["work_state"]["completion_blockers"] == [])
    check("task 3's condition stays open until task 2 is completed",
          task[t3]["work_state"]["applies"] is None)

    first = next(r for r in rec if r["record_kind"] == "note")["id"]
    fix = dict(note, record_text="Truck unloaded to staging; slips checked after put-away.",
               supersedes_record_id=first)
    phase = lee.post(f"/tasks/{t1}/records", json=fix).json()["phase"]
    rec = next(t for t in phase["tasks"] if t["id"] == t1)["records"]
    original = next(r for r in rec if r["id"] == first)
    correction = next(r for r in rec if r["supersedes_record_id"] == first)
    check("a correction supersedes; the original is kept unchanged and points to it",
          len(rec) == 3 and original["record_text"] == "Truck unloaded to staging."
          and original["superseded_by"] == correction["id"]
          and correction["record_text"].endswith("after put-away."))

    r = lee.post(f"/tasks/{t1}/completion",
                 json={"result_summary": "Receiving recorded; counts happen after put-away."})
    t1_done = next(t for t in r.json()["phase"]["tasks"] if t["id"] == t1)
    check("completion succeeds once nothing blocks, attributed by name",
          r.status_code == 200 and t1_done["status"] == "completed"
          and t1_done["completed_by"] == "Lee Lead"
          and [b["code"] for b in t1_done["work_state"]["completion_blockers"]] == ["task_resolved"])
    phase = lee.post(f"/tasks/{t2}/completion",
                     json={"result_summary": "Two of ten POs differed."}).json()["phase"]
    check("a completed task 2 with a mismatch makes the conditional task 3 apply",
          next(t for t in phase["tasks"] if t["id"] == t3)["work_state"]["applies"] is True)

    check("not applicable needs a reason",
          code(lee.post(f"/tasks/{t3}/not-applicable", json={"reason": " "})) == "invalid_field")
    r = lee.post(f"/tasks/{t3}/not-applicable",
                 json={"reason": "Staff resolved the one mismatch on the spot; nothing to follow."})
    phase = r.json()["phase"]
    check("a task resolved not applicable keeps its reason and shows in readiness",
          next(t for t in phase["tasks"] if t["id"] == t3)["not_applicable_reason"]
          and any(n["task_id"] == t3 for n in phase["readiness"]["notes"]))

    suggested = ep.add_task(factory, pid, {
        "title": "Walk the returns cage", "instructions": "Note how returns re-enter stock.",
        "inclusion_reason": "Raised in the receiving interviews."}, people["lee"],
        origin="si_suggested")
    sug = next(t for t in suggested["tasks"] if t["status"] == "suggested")
    check("a suggested task shows as suggested and is blocked until accepted",
          sug["work_state"]["applies"] is None
          and [b["code"] for b in sug["work_state"]["completion_blockers"]] == ["task_not_accepted"]
          and code(lee.post(f"/tasks/{sug['id']}/completion", json={"result_summary": "x"}))
          == "task_not_accepted")
    r = lee.post(f"/tasks/{sug['id']}/acceptance")
    acc = next(t for t in r.json()["phase"]["tasks"] if t["id"] == sug["id"])
    check("accepting adds it to the plan, marked as added after authorization",
          r.status_code == 200 and acc["status"] == "open" and acc["added_after_authorization"])

    readiness = lee.get(f"/phases/{pid}").json()["phase"]["readiness"]
    check("readiness is not ready while required tasks are open",
          readiness["ready"] is False
          and {b["task_id"] for b in readiness["blocking"]} == {t4, t6, sug["id"]})
    check("phase completion is refused while not ready",
          lee.post(f"/phases/{pid}/completion").status_code >= 400)
    lee.post(f"/tasks/{t4}/completion", json={"result_summary": "Two interviews agree."})
    lee.post(f"/tasks/{t6}/records", json={"record_kind": "note", "record_text": "Pattern: late checks."})
    lee.post(f"/tasks/{t6}/completion", json={"result_summary": "Slips are checked late."})
    lee.post(f"/tasks/{sug['id']}/not-applicable", json={"reason": "No returns this week."})
    phase = lee.get(f"/phases/{pid}").json()["phase"]
    check("readiness moves to ready; the optional task does not hold it back",
          phase["readiness"]["ready"] is True
          and any(n["code"] == "optional_incomplete" and n["task_id"] == t5
                  for n in phase["readiness"]["notes"]))
    r = lee.post(f"/phases/{pid}/completion")
    check("the phase completes once ready", r.status_code == 200
          and lee.get(f"/phases/{pid}").json()["phase"]["status"] == "completed")

    with factory() as s:
        obs_count = s.query(models.DiscoveryObservation).count()
    check("phase work created no discovery observation", obs_count == 2)

    print("\n[logged out]")
    calls = [("get", f"/engagements/{eid}/phases", None), ("get", f"/phases/{pid}", None),
             ("post", f"/tasks/{t5}/records", {"record_kind": "note", "record_text": "x"}),
             ("post", f"/tasks/{t5}/completion", {"result_summary": "x"}),
             ("post", f"/tasks/{t5}/not-applicable", {"reason": "x"}),
             ("post", f"/tasks/{t5}/acceptance", None), ("post", f"/phases/{pid}/completion", None)]
    statuses = [getattr(anon, m)(p, **({"json": b} if b is not None else {})).status_code
                for m, p, b in calls]
    check("every route the UI calls refuses a logged-out request (401)",
          statuses == [401] * len(calls))


# --------------------------------------------------------------------------- static


def static_checks():
    print("\n[3. static UI checks]")
    check("the new UI files exist", all(os.path.exists(os.path.join(REPO_ROOT, p)) for p in UI_FILES))
    actions = read("web/app/work-plan-actions.ts")
    check("server actions exist for record, complete, not applicable, accept, complete phase",
          all(f"export async function {n}(" in actions
              for n in ("recordTaskWork", "completeTask", "resolveTaskNotApplicable",
                        "acceptSuggestedTask", "completePhase")))
    check("the actions call only the Phase 217 task and phase endpoints",
          set(re.findall(r"send\(`(/\w+)/", actions)) == {"/tasks", "/phases"}
          and "/observations" not in actions)
    check("the proxy guards /phases", '"/phases/:path*"' in read("web/proxy.ts"))
    check("the engagement page lists its phases",
          "WorkPlanSection" in read("web/app/(workspace)/engagements/[id]/page.tsx"))

    lib = read("web/lib/work-plan.ts")
    forms = lib[lib.index("export const RECORD_FORMS"):lib.index("export const WORK_RECORD_KINDS")]
    offered = re.findall(r"^  (\w+): \{$", forms, re.MULTILINE)
    check("the record form offers exactly note, interview response, measurement, mismatch",
          offered == ["note", "interview_response", "measurement", "mismatch"])
    ui = {p: read(p) for p in UI_FILES}
    check("no file upload or camera input anywhere in the new UI",
          not any(re.search(r'type="file"|capture=|accept="image', s) for s in ui.values()))
    form = read("web/components/work-plan-record-form.tsx")
    check("the record form is never prefilled from the task's guidance",
          not re.search(r"defaultValue=\{[^}]*(task|guidance|expected|instructions|what_to_observe)",
                        form) and "expected_result" not in form and "instructions" not in form)
    check("the record form never offers a media kind", "MEDIA_KINDS" not in form)

    from peak.workspace import advisory_boundary as b
    visible = []
    for p, s in ui.items():
        s = re.sub(r"/\*.*?\*/|^\s*//.*$", "", s, flags=re.DOTALL | re.MULTILINE)
        visible += re.findall(r'"([^"\n]{3,})"', s) + re.findall(r">([^<>{}\n]{3,})<", s)
    hits = {t for t in visible if b.framing_violations(t)}
    check("no audit / compliance / deficiency language in the new UI text", not hits)
    if hits:
        print("    " + "; ".join(sorted(hits)))
    check("no work-plan code calls a discovery observation endpoint",
          not any("/observations" in s for s in ui.values()))
    versions = os.listdir(os.path.join(REPO_ROOT, "alembic", "versions"))
    check("no migration was added (head stays 022)",
          not any(v.startswith("023") for v in versions))
    check("docs/PHASE218_GUIDED_EXECUTION_UI.md exists",
          os.path.exists(os.path.join(REPO_ROOT, "docs/PHASE218_GUIDED_EXECUTION_UI.md")))


def main() -> int:
    print("Peak Phase 218 guided execution UI check")
    print("=" * 42)
    try:
        import argon2, fastapi, httpx, itsdangerous, sqlalchemy  # noqa: F401,E401
    except ImportError:
        print("  [skip] web dependencies not installed — run with PYTHON=.venv/bin/python")
        return 0
    with tempfile.TemporaryDirectory(prefix="peak_phase218_") as tmp:
        app_checks(tmp)
    static_checks()

    print("\nSummary")
    print(f"  failures : {len(_failures)}")
    print("RESULT: " + ("PASS" if not _failures else "FAIL"))
    return 0 if not _failures else 1


if __name__ == "__main__":
    sys.exit(main())
