#!/usr/bin/env python3
"""Phase 219 — work-plan initiation and setup workflow (offline; temporary SQLite only).

Proves:

1. **Read-only API additions.** ``GET /phase-templates`` returns the canonical Peak Method template
   catalogue (framing and task outline only). ``GET /engagements/{id}/roadmap`` adds, per item, the
   decisions the transition rules allow now, whether it can be revised, its phase and who decided
   it. Reading creates nothing; a computed suggestion is never stored by being read.
2. **Setup flow through the API the UI calls.** Empty engagement; suggestion → roadmap item (the
   observations the server recomputes); consultant item from the web payload (run under Node);
   accept / defer / decline / revise; phase from an accepted item, once; manual phase with its
   required reason; a planned phase stays non-executable; template tasks loaded before
   authorization are not marked as a scope change, a duplicate template is refused with the API's
   message; authorization by the Lead (another consultant is refused, permissions unchanged);
   the setup stage helper (``web/lib/phase-setup.ts``, under Node) reads every state correctly; the
   authorized phase with tasks accepts Phase 218 work; no discovery observation is created; every
   setup route refuses a logged-out request (401).
3. **Static UI checks.** Routes, actions and components exist; actions call only the Phase 217
   roadmap / phase endpoints; templates are not hard-coded in the web app; no raw ids or JSON
   rendered; no billing, signature or upload fields; advisory-boundary text scan; the Phase 218
   pages link into setup and setup hands off to the Phase 218 work plan; no migration was added.

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
PASSWORD = "phase219-password"
SECRET = "phase219-secret-key-phase219-secret-key"
UI_FILES = (
    "web/app/phase-setup-actions.ts",
    "web/lib/phase-setup.ts",
    "web/components/phase-setup-forms.tsx",
    "web/components/phase-setup-parts.tsx",
    "web/components/work-plan-section.tsx",
    "web/app/(workspace)/engagements/[id]/roadmap/page.tsx",
    "web/app/(workspace)/phases/[id]/setup/page.tsx",
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


def message(response):
    detail = response.json().get("detail")
    return detail.get("message") if isinstance(detail, dict) else None


def read(path):
    with open(os.path.join(REPO_ROOT, path), encoding="utf-8") as f:
        return f.read()


# --------------------------------------------------------------------------- web helpers


def web_helpers(tmp, calls):
    """Run named exports of web/lib/phase-setup.ts under Node: ``[[name, [args...]], ...]``.

    Sets are returned as sorted lists. Returns None when Node or web dependencies are missing.
    """
    node = shutil.which("node")
    if node is None or not os.path.isdir(os.path.join(WEB, "node_modules", "typescript")):
        return None
    script = os.path.join(tmp, "setup_helpers.cjs")
    with open(script, "w", encoding="utf-8") as f:
        f.write("""
const fs = require("fs");
const ts = require(process.argv[2]);
const src = fs.readFileSync(process.argv[3], "utf8");
const js = ts.transpileModule(src, { compilerOptions: { module: ts.ModuleKind.CommonJS,
                                                        target: ts.ScriptTarget.ES2020 } }).outputText;
const mod = { exports: {} };
new Function("module", "exports", "require", js)(mod, mod.exports, require);
const calls = JSON.parse(fs.readFileSync(0, "utf8"));
const out = calls.map(([name, args]) => {
  const v = mod.exports[name](...args);
  return v instanceof Set ? [...v].sort() : v;
});
process.stdout.write(JSON.stringify(out));
""")
    out = subprocess.run([node, script, os.path.join(WEB, "node_modules", "typescript"),
                          os.path.join(WEB, "lib", "phase-setup.ts")],
                         input=json.dumps(calls), capture_output=True, text=True, check=True)
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
    for key, name, role in (("ada", "Ada Admin", "admin"), ("lee", "Lee Lead", "consultant"),
                            ("cam", "Cam Consultant", "consultant")):
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


def _summary(lee, eid, pid):
    return next(p for p in lee.get(f"/engagements/{eid}/phases").json()["phases"] if p["id"] == pid)


def app_checks(tmp):
    from peak.workspace import peak_method_phases as method

    factory, qid, people, c = _setup(tmp)
    ada, lee, cam, anon = c["ada"], c["lee"], c["cam"], c["anon"]

    cid = ada.post("/clients", json={"organization_label": "Synthetic Supply Co"}).json()["client"]["id"]
    eid = ada.post("/engagements", json={"client_id": cid, "engagement_label": "Synthetic Ops",
                                         "assigned_consultant_id": people["lee"]}
                   ).json()["engagement"]["id"]

    print("\n[1. read-only additions; empty engagement]")
    before = _counts(factory)
    roadmap = lee.get(f"/engagements/{eid}/roadmap").json()["roadmap"]
    check("an engagement with no observations has no roadmap items, suggestions or phases",
          roadmap["enabled"] and roadmap["items"] == [] and roadmap["suggestions"] == []
          and lee.get(f"/engagements/{eid}/phases").json()["phases"] == [])
    templates = lee.get("/phase-templates").json()["templates"]
    check("the template list is the canonical Peak Method catalogue, in catalogue order",
          [t["template_key"] for t in templates] == [t["key"] for t in method.TEMPLATES]
          and templates == method.catalogue())
    check("each template carries title, purpose, scope and its ordered task outline",
          all(t["title"] and t["scope_summary"] and t["problem_framing"]
              and [s["sequence"] for s in t["tasks"]] == list(range(1, len(t["tasks"]) + 1))
              for t in templates)
          and [len(t["tasks"]) for t in templates] == [len(t["tasks"]) for t in method.TEMPLATES])
    check("the catalogue exposes no trigger categories or task guidance",
          all("trigger_categories" not in t
              and all(set(s) == {"sequence", "title", "required"} for s in t["tasks"])
              for t in templates))

    obs = [lee.post(f"/engagements/{eid}/observations",
                    json={"observation_text": text, "question_id": qid, "basis": "testimony"}
                    ).json()["observation"]["id"]
           for text in ("Receivers described frequent differences between slips and POs.",
                        "Two shifts receive differently.")]
    before = _counts(factory)
    roadmap = lee.get(f"/engagements/{eid}/roadmap").json()["roadmap"]
    lee.get(f"/engagements/{eid}/roadmap")
    lee.get("/phase-templates")
    check("a computed suggestion appears, citing the observations it rests on",
          [s["template_key"] for s in roadmap["suggestions"]] == ["receiving_accuracy"]
          and set(roadmap["suggestions"][0]["source_observation_ids"]) == set(obs))
    check("reading the roadmap and templates stores nothing (the suggestion is not persisted)",
          _counts(factory) == before and roadmap["items"] == [])

    print("\n[2. roadmap]")
    sugg = roadmap["suggestions"][0]
    r = lee.post(f"/engagements/{eid}/roadmap-items",
                 json={"template_key": sugg["template_key"],
                       "source_observation_ids": sugg["source_observation_ids"]})
    rcv = r.json()["roadmap_item"]
    roadmap = lee.get(f"/engagements/{eid}/roadmap").json()["roadmap"]
    item = roadmap["items"][0]
    check("adding a suggestion stores a proposed Peak Method item and removes the suggestion",
          r.status_code == 201 and rcv["status"] == "proposed" and rcv["origin"] == "peak_method"
          and roadmap["suggestions"] == [])
    check("a proposed item reports its allowed decisions, revisable, no phase, no decider",
          item["decisions"] == ["accepted", "deferred", "declined"] and item["revisable"] is True
          and item["phase_id"] is None and item["decided_by"] is None)

    forms = [{"title": "  Replenishment trigger review ", "problem_framing": "Reorder points vary.",
              "rationale": "Stock-outs interrupt picking.", "expected_outcome": "Agreed triggers.",
              "extra": "ignored"},
             {"title": "Only a title", "problem_framing": " ", "rationale": "",
              "expected_outcome": ""}]
    calls = [["roadmapItemPayload", [forms[0], [obs[1]]]], ["roadmapItemPayload", [forms[1]]]]
    helper = web_helpers(tmp, calls)
    expected = [{"title": "Replenishment trigger review", "problem_framing": "Reorder points vary.",
                 "rationale": "Stock-outs interrupt picking.", "expected_outcome": "Agreed triggers.",
                 "source_observation_ids": [obs[1]]},
                {"title": "Only a title"}]
    if helper is None:
        print("  [skip] node or web/node_modules not installed — using the expected payloads")
    else:
        check("the web form builds a trimmed payload, drops blanks and unknown fields",
              helper == expected)
    payload, partial = helper or expected
    r = lee.post(f"/engagements/{eid}/roadmap-items", json=payload)
    rep = r.json()["roadmap_item"]
    check("the API accepts the consultant item as the web form sends it",
          r.status_code == 201 and rep["origin"] == "consultant"
          and rep["source_observation_ids"] == [obs[1]])
    r = lee.post(f"/engagements/{eid}/roadmap-items", json=partial)
    check("an incomplete item is refused with a readable message",
          code(r) == "invalid_field" and message(r) == "Problem or opportunity is required.")
    r = lee.post(f"/engagements/{eid}/roadmap-items",
                 json={"title": "Audit the receiving dock", "problem_framing": "x",
                       "rationale": "y", "expected_outcome": "z"})
    check("audit framing is refused by the advisory boundary with its message",
          code(r) == "advisory_boundary" and "advisory" in message(r))

    rev = lee.post(f"/roadmap-items/{rep['id']}/revision",
                   json={"title": "Replenishment trigger improvement"}).json()["roadmap_item"]
    roadmap = lee.get(f"/engagements/{eid}/roadmap").json()["roadmap"]
    check("a revision is a new proposed item; the original is kept under superseded",
          rev["supersedes_item_id"] == rep["id"]
          and [i["id"] for i in roadmap["superseded"]] == [rep["id"]]
          and roadmap["superseded"][0]["decisions"] == []
          and roadmap["superseded"][0]["revisable"] is False)

    lee.post(f"/roadmap-items/{rev['id']}/decision", json={"status": "deferred", "note": "Next quarter."})
    deferred = next(i for i in lee.get(f"/engagements/{eid}/roadmap").json()["roadmap"]["items"]
                    if i["id"] == rev["id"])
    check("a deferred item offers return to proposed, accept or decline, and names the decider",
          deferred["decisions"] == ["proposed", "accepted", "declined"]
          and deferred["decided_by"] == "Lee Lead" and deferred["status_note"] == "Next quarter.")
    lee.post(f"/roadmap-items/{rev['id']}/decision", json={"status": "declined"})
    declined = next(i for i in lee.get(f"/engagements/{eid}/roadmap").json()["roadmap"]["items"]
                    if i["id"] == rev["id"])
    check("a declined item offers no decision and cannot be revised",
          declined["decisions"] == [] and declined["revisable"] is False)
    r = lee.post(f"/roadmap-items/{rev['id']}/decision", json={"status": "accepted"})
    check("deciding a declined item is refused with the API's message",
          code(r) == "invalid_transition" and "declined" in message(r))
    r = lee.post(f"/engagements/{eid}/phases", json={"roadmap_item_id": rcv["id"]})
    check("a phase cannot be created from an item that is not accepted",
          code(r) == "roadmap_item_not_accepted")

    print("\n[3. phase creation]")
    lee.post(f"/roadmap-items/{rcv['id']}/decision", json={"status": "accepted"})
    r = lee.post(f"/engagements/{eid}/phases", json={"roadmap_item_id": rcv["id"]})
    phase = r.json()["phase"]
    pid = phase["id"]
    item = next(i for i in lee.get(f"/engagements/{eid}/roadmap").json()["roadmap"]["items"]
                if i["id"] == rcv["id"])
    check("an accepted item becomes a planned phase with the template's scope",
          r.status_code == 201 and phase["status"] == "planned" and phase["origin"] == "roadmap_item"
          and phase["scope_summary"] == method.BY_KEY["receiving_accuracy"]["scope_summary"])
    check("the item now names its phase and offers no further decision",
          item["phase_id"] == pid and item["decisions"] == [])
    check("a second phase for the same item is refused",
          code(lee.post(f"/engagements/{eid}/phases", json={"roadmap_item_id": rcv["id"]}))
          == "phase_exists")
    r = lee.post(f"/engagements/{eid}/phases",
                 json={"title": "Cycle count coaching", "scope_summary": "Coach two counters."})
    check("a manual phase without its reason is refused", code(r) == "invalid_field")
    man = lee.post(f"/engagements/{eid}/phases",
                   json={"title": "Cycle count coaching", "scope_summary": "Coach two counters.",
                         "origin_note": "Client asked during the discovery read-out."}).json()["phase"]
    check("a manual phase with its reason is created, marked manual",
          man["origin"] == "manual" and man["origin_note"] and man["status"] == "planned")

    print("\n[4. planned phase is not executable]")
    t_rec = lee.post(f"/phases/{pid}/template-tasks", json={"template_key": "receiving_accuracy"})
    planned = t_rec.json()["phase"]
    t1 = planned["tasks"][0]["id"]
    check("loading the template before authorization builds the ordered plan, not marked as a "
          "scope change", t_rec.status_code == 200 and len(planned["tasks"]) == 6
          and not any(t["added_after_authorization"] for t in planned["tasks"])
          and planned["work_plan_status"] == "draft")
    r = lee.post(f"/phases/{pid}/template-tasks", json={"template_key": "receiving_accuracy"})
    check("loading the same template twice is refused with the API's message",
          code(r) == "template_already_added"
          and message(r) == "This template's tasks are already in the plan.")
    check("work cannot be recorded or completed on the planned phase",
          code(lee.post(f"/tasks/{t1}/records", json={"record_kind": "note", "record_text": "x"}))
          == "phase_not_authorized"
          and code(lee.post(f"/tasks/{t1}/completion", json={"result_summary": "x"}))
          == "phase_not_authorized")
    check("readiness reports the phase as not authorized",
          any(b["code"] == "phase_not_authorized" for b in planned["readiness"]["blocking"]))

    print("\n[5. authorization]")
    r = cam.post(f"/phases/{pid}/authorization", json={"authorization_basis": "Client agreed."})
    check("a consultant who is not the Lead is refused (403), permissions unchanged",
          r.status_code == 403 and code(r) == "lead_or_admin_required")
    check("authorization needs a basis",
          code(lee.post(f"/phases/{pid}/authorization", json={"authorization_basis": " "}))
          == "invalid_field")
    r = lee.post(f"/phases/{pid}/authorization",
                 json={"authorization_basis": "Operations Manager approved the receiving phase.",
                       "authorization_reference": "Email, 24 Oct"})
    auth = r.json()["phase"]
    check("the Lead records authorization; it is attributed and dated",
          r.status_code == 200 and auth["status"] == "authorized"
          and auth["authorization"]["authorized_by"] == "Lee Lead"
          and auth["authorization"]["reference"] == "Email, 24 Oct"
          and auth["authorization"]["authorized_at"])
    check("authorization cannot be recorded twice",
          code(lee.post(f"/phases/{pid}/authorization", json={"authorization_basis": "Again."}))
          == "phase_closed")
    r = ada.post(f"/phases/{man['id']}/authorization", json={"authorization_basis": "Agreed in person."})
    check("an Admin may record authorization", r.status_code == 200)
    late = lee.post(f"/phases/{man['id']}/template-tasks",
                    json={"template_key": "count_adjustment_practice"}).json()["phase"]
    check("a template loaded after authorization is marked as added after authorization",
          late["tasks"] and all(t["added_after_authorization"] for t in late["tasks"]))

    print("\n[6. setup stage and handoff]")
    summaries = [_summary(lee, eid, pid)]
    fresh = lee.post(f"/engagements/{eid}/phases",
                     json={"title": "Put-away walk", "scope_summary": "Walk put-away.",
                           "origin_note": "Raised on site."}).json()["phase"]
    summaries.append(_summary(lee, eid, fresh["id"]))
    ada.post(f"/phases/{fresh['id']}/authorization", json={"authorization_basis": "Agreed."})
    summaries.append(_summary(lee, eid, fresh["id"]))
    summaries.append(dict(summaries[0], status="planned", work_plan_status="draft", authorized=False))
    summaries.append(dict(summaries[0], status="completed", work_plan_status="closed"))
    calls = ([["setupStage", [s]] for s in summaries] + [["phaseHref", [s]] for s in summaries]
             + [["setupSteps", [summaries[1]]], ["setupSteps", [summaries[0]]],
                ["templatesInPlan", [auth["tasks"]]]])
    helper = web_helpers(tmp, calls)
    if helper is None:
        print("  [skip] node or web/node_modules not installed")
    else:
        n = len(summaries)
        stages, hrefs, steps_new, steps_ready, in_plan = (helper[:n], helper[n:2 * n],
                                                         helper[2 * n], helper[2 * n + 1],
                                                         helper[2 * n + 2])
        check("setup stage is derived from records: ready / both / plan / authorization / completed",
              stages == ["ready", "plan_and_authorization", "plan", "authorization", "completed"])
        check("only a ready or completed phase links to the Phase 218 work plan; others to setup",
              hrefs == [f"/phases/{pid}", f"/phases/{fresh['id']}/setup",
                        f"/phases/{fresh['id']}/setup", f"/phases/{pid}/setup", f"/phases/{pid}"])
        check("the checklist shows plan and authorization outstanding for a new manual phase",
              [s["done"] for s in steps_new] == [True, True, False, False, False]
              and steps_new[0]["label"].startswith("Reason for a manually created phase"))
        check("the checklist is complete for an authorized phase with tasks",
              all(s["done"] for s in steps_ready))
        check("templates already in the plan are read from the tasks", in_plan == ["receiving_accuracy"])

    r = lee.post(f"/tasks/{t1}/records", json={"record_kind": "note", "record_text": "Observed."})
    check("the authorized phase with tasks accepts Phase 218 work", r.status_code == 201)

    with factory() as s:
        from peak.db import models

        check("setup created no discovery observation and no artifact",
              s.query(models.DiscoveryObservation).count() == 2
              and s.query(models.Artifact).count() == 0)

    print("\n[logged out]")
    calls = [("get", "/phase-templates", None), ("get", f"/engagements/{eid}/roadmap", None),
             ("post", f"/engagements/{eid}/roadmap-items", {"title": "x"}),
             ("post", f"/roadmap-items/{rcv['id']}/decision", {"status": "deferred"}),
             ("post", f"/roadmap-items/{rcv['id']}/revision", {"title": "x"}),
             ("get", f"/engagements/{eid}/phases", None),
             ("post", f"/engagements/{eid}/phases", {"title": "x"}),
             ("post", f"/phases/{pid}/authorization", {"authorization_basis": "x"}),
             ("post", f"/phases/{pid}/template-tasks", {"template_key": "receiving_accuracy"})]
    statuses = [getattr(anon, m)(p, **({"json": b} if b is not None else {})).status_code
                for m, p, b in calls]
    check("every route the setup UI calls refuses a logged-out request (401)",
          statuses == [401] * len(calls))


# --------------------------------------------------------------------------- static


def _visible_text(sources):
    out = []
    for s in sources:
        s = re.sub(r"/\*.*?\*/|^\s*//.*$", "", s, flags=re.DOTALL | re.MULTILINE)
        out += re.findall(r'"([^"\n]{3,})"', s) + re.findall(r">([^<>{}\n]{3,})<", s)
    return out


def static_checks():
    print("\n[7. static UI checks]")
    check("the new UI files exist", all(os.path.exists(os.path.join(REPO_ROOT, p)) for p in UI_FILES))
    actions = read("web/app/phase-setup-actions.ts")
    check("server actions exist for every setup step",
          all(f"export async function {n}(" in actions
              for n in ("addSuggestionToRoadmap", "createRoadmapItem", "decideRoadmapItem",
                        "reviseRoadmapItem", "createPhaseFromRoadmapItem", "createManualPhase",
                        "recordPhaseAuthorization", "loadTemplateTasks")))
    endpoints = set(re.findall(r"(?:send|apiFetch)\(`(/[a-z-]+/\$\{[^}]+\}/?[a-z-]*)`", actions))
    normalized = {re.sub(r"\$\{[^}]+\}", "{id}", e) for e in endpoints}
    check("the actions call only Phase 217 roadmap and phase endpoints",
          normalized == {"/engagements/{id}/roadmap", "/engagements/{id}/roadmap-items",
                         "/roadmap-items/{id}/decision", "/roadmap-items/{id}/revision",
                         "/engagements/{id}/phases", "/phases/{id}/authorization",
                         "/phases/{id}/template-tasks"})
    check("the authorization form sends exactly the API's authorization fields",
          '"authorization_basis"' in read("web/components/phase-setup-forms.tsx")
          and "authorization_basis:" in actions and "authorization_reference" in actions)
    proxy = read("web/proxy.ts")
    check("the proxy guards /engagements and /phases",
          '"/engagements/:path*"' in proxy and '"/phases/:path*"' in proxy)

    web_sources = []
    for root, dirs, files in os.walk(WEB):
        dirs[:] = [d for d in dirs if d not in ("node_modules", ".next")]
        web_sources += [read(os.path.relpath(os.path.join(root, f), REPO_ROOT))
                        for f in files if f.endswith((".ts", ".tsx"))]
    from peak.workspace import peak_method_phases as method

    check("no template key, title or task is hard-coded in the web app",
          not any(t["key"] in s or t["title"] in s for t in method.TEMPLATES for s in web_sources))
    ui = {p: read(p) for p in UI_FILES}
    rendered = [s for p, s in ui.items() if p.endswith(".tsx")]
    check("no raw id, template key or JSON is rendered as page text",
          not any(re.search(r">[^<{\n]*\{[\w.?]*\.(id|template_key|source_observation_ids)\}", s)
                  or "JSON.stringify" in s for s in rendered))
    check("no fee, billing, payment, signature or upload field",
          not any(re.search(r'name="[^"]*(fee|price|amount|billing|payment|signature|stripe)',
                            s, re.IGNORECASE) or re.search(r'type="file"|capture=', s)
                  for s in ui.values()))
    check("no setup code calls a discovery observation endpoint",
          not any("/observations" in s for s in ui.values()))

    from peak.workspace import advisory_boundary as b
    hits = {t for t in _visible_text(ui.values()) if b.framing_violations(t)}
    check("no audit / compliance / deficiency language in the new UI text", not hits)
    if hits:
        print("    " + "; ".join(sorted(hits)))

    setup = ui["web/app/(workspace)/phases/[id]/setup/page.tsx"]
    check("setup offers 'Open work plan' into the Phase 218 page only when setup is finished",
          "Open work plan" in setup and 'stage === "ready" || stage === "completed"' in setup
          and "href={`/phases/${p.id}`}" in setup)
    check("setup states that authorization is an operational record, not a proposal, contract or "
          "payment", "This records that the client has authorized this phase of work." in setup
          and "not record a proposal, a signed contract or a payment" in setup)
    phase_page = read("web/app/(workspace)/phases/[id]/page.tsx")
    check("the Phase 218 phase page links back into setup until setup is finished",
          "setupFinished(p)" in phase_page and "/setup`" in phase_page
          and "nextTask(plan)" in phase_page)
    check("the engagement page opens the roadmap and phase setup",
          "/roadmap`" in ui["web/components/work-plan-section.tsx"]
          and "roadmap={roadmap}" in read("web/app/(workspace)/engagements/[id]/page.tsx"))
    roadmap_page = ui["web/app/(workspace)/engagements/[id]/roadmap/page.tsx"]
    check("suggestions are labelled as computed and not saved, apart from stored items",
          "Suggested by Peak · not saved" in roadmap_page and "On the roadmap" in roadmap_page
          and "border-dashed" in roadmap_page)
    versions = os.listdir(os.path.join(REPO_ROOT, "alembic", "versions"))
    # Phase 220 added 023 (evidence); Phase 219 itself added none.
    check("Phase 219 added no migration",
          not any(f"Phase 219" in read(os.path.join("alembic", "versions", v))
                  for v in versions if v.endswith(".py")))
    check("docs/PHASE219_PHASE_SETUP_WORKFLOW.md exists",
          os.path.exists(os.path.join(REPO_ROOT, "docs/PHASE219_PHASE_SETUP_WORKFLOW.md")))


def main() -> int:
    print("Peak Phase 219 phase setup workflow check")
    print("=" * 42)
    try:
        import argon2, fastapi, httpx, itsdangerous, sqlalchemy  # noqa: F401,E401
    except ImportError:
        print("  [skip] web dependencies not installed — run with PYTHON=.venv/bin/python")
        return 0
    with tempfile.TemporaryDirectory(prefix="peak_phase219_") as tmp:
        app_checks(tmp)
    static_checks()

    print("\nSummary")
    print(f"  failures : {len(_failures)}")
    print("RESULT: " + ("PASS" if not _failures else "FAIL"))
    return 0 if not _failures else 1


if __name__ == "__main__":
    sys.exit(main())
