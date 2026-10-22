#!/usr/bin/env python3
"""Phase 217 — engagement roadmap and guided work plan foundation (offline; temporary SQLite only).

Proves:

1. **Advisory boundary.** The framing check refuses audit, compliance, certification, assurance,
   attestation, deficiency, material-weakness and violation language and allows ordinary advisory
   language (including "controls"). Every Peak Method template string passes it, and no status,
   record kind or readiness code carries audit/compliance semantics.
2. **Migration 022.** It goes up and down, creates exactly the four new tables, carries no data,
   and its CHECK constraints refuse values outside each vocabulary.
3. **Roadmap.** Suggestions are deterministic and rest only on consultant observations (answers
   never trigger one). An engagement holds several ordered items; a Peak Method item must cite
   observations of its own engagement; a revision supersedes and keeps the original; an accepted
   item is still not authorized work.
4. **Phases.** A phase comes from one accepted roadmap item or is created manually with a reason.
   Several phases are separately authorized; only the Lead or an Admin records authorization; no
   work is recorded before it.
5. **Work plan.** Tasks belong to exactly one phase and are ordered. Dependencies, a deterministic
   condition, required/optional and records-required are enforced. Completion needs the consultant's
   result summary; records are insert-only and corrections supersede. Media kinds are reserved.
   Suggested tasks never join the plan or block it silently; post-authorization additions are marked.
6. **Readiness.** Incomplete required tasks block; completed required tasks permit; optional and
   unmet-condition tasks do not block; a phase completes only when ready.
7. **No fabrication.** Reads create nothing; templates create no records; no discovery observation
   or finding is created by phase work; the Final Report is unchanged.

``--example`` also prints the receiving example end to end.

Exit status: 0 all checks passed; 1 a check failed.
"""

from __future__ import annotations

import json
import os
import re
import sqlite3
import subprocess
import sys
import tempfile

REPO_ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
if REPO_ROOT not in sys.path:
    sys.path.insert(0, REPO_ROOT)

PASSWORD = "phase217-password"
SECRET = "phase217-secret-key-phase217-secret-key"
NEW_TABLES = {"roadmap_items", "engagement_phases", "phase_tasks", "phase_task_records"}
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


# --------------------------------------------------------------------------- 1. boundary


def boundary_checks():
    print("\n[1. advisory boundary]")
    from peak.db import models
    from peak.workspace import advisory_boundary as b
    from peak.workspace import engagement_phases as ep
    from peak.workspace import peak_method_phases as pm

    refused = ["Receiving audit", "Inventory compliance test", "Non-compliance with policy",
               "noncompliant receipts", "Certify the count", "Assurance over receiving",
               "Attest to accuracy", "Control deficiency in adjustments",
               "Material weaknesses noted", "Policy violations", "The auditor's sample"]
    check("the framing check refuses every audit / compliance / assurance phrasing",
          all(b.framing_violations(t) for t in refused))
    allowed = ["Review how receiving controls work in practice", "Receiving variance and rework",
               "Observed workflow friction", "Inconsistency between shifts", "Improvement opportunity",
               "Review a sample of purchase orders and packing slips"]
    check("ordinary advisory language (including 'controls') passes",
          not any(b.framing_violations(t) for t in allowed))
    check("lists and nested values are checked too",
          b.framing_violations(["fine", {"q": "an audit question"}]) == ["audit"])
    check("no governed audit capability exists", b.GOVERNED_AUDIT_CAPABILITY_AVAILABLE is False)

    def strings(value):
        if isinstance(value, str):
            yield value
        elif isinstance(value, dict):
            for v in value.values():
                yield from strings(v)
        elif isinstance(value, (list, tuple)):
            for v in value:
                yield from strings(v)

    check("every Peak Method template string stays inside the boundary",
          not any(b.framing_violations(s) for s in strings(pm.TEMPLATES)))
    vocab = (models.ROADMAP_ITEM_STATUSES + models.WORK_ORIGINS + models.ENGAGEMENT_PHASE_STATUSES
             + models.ENGAGEMENT_PHASE_ORIGINS + models.PHASE_TASK_STATUSES
             + models.PHASE_TASK_RECORD_KINDS)
    terms = re.compile(r"audit|complian|certif|assur|attest|deficien|pass|fail|score|violation",
                       re.IGNORECASE)
    check("no status, origin or record kind carries audit / compliance / pass-fail semantics",
          not any(terms.search(v) for v in vocab))
    src = open(os.path.join(REPO_ROOT, "peak/workspace/engagement_phases.py")).read()
    codes = set(re.findall(r'"code": "(\w+)"|block\("(\w+)"', src))
    codes = {c for pair in codes for c in pair if c}
    check("readiness codes carry no audit / compliance semantics",
          codes and not any(terms.search(c) for c in codes))
    check("readiness rule text stays inside the boundary",
          not b.framing_violations(ep.READINESS_RULE))
    check("the record kinds mirror the model vocabulary",
          ep.RECORD_KINDS == models.PHASE_TASK_RECORD_KINDS
          and pm.EVIDENCE_KINDS == models.PHASE_TASK_RECORD_KINDS
          and set(ep.MEDIA_RECORD_KINDS) == {"photo", "document_photo", "document"}
          and ep.RECORD_BASES == models.DISCOVERY_OBSERVATION_BASES)
    ok = True
    for t in pm.TEMPLATES:
        keys = [s["key"] for s in t["tasks"]]
        for i, s in enumerate(t["tasks"]):
            earlier = set(keys[:i])
            ok &= set(s["depends_on"]) <= earlier
            ok &= s["condition"] is None or (s["condition"][0] in earlier
                                            and s["condition"][1] in pm.EVIDENCE_KINDS)
            ok &= set(s["suggested_evidence"]) <= set(pm.EVIDENCE_KINDS)
    check("template dependencies and conditions name earlier tasks and known record kinds", ok)


# --------------------------------------------------------------------------- 2. migration


def migration_checks(tmp):
    print("\n[2. migration 022]")
    import sqlalchemy as sa

    db = os.path.join(tmp, "mig.sqlite3")

    def tables():
        return set(sa.inspect(sa.create_engine(f"sqlite:///{db}")).get_table_names())

    alembic(db, "upgrade", "021_discovery_observation_trace_basis").check_returncode()
    before = tables()
    up = alembic(db, "upgrade", "022_engagement_roadmap_work_plan")
    check("upgrade to 022 creates exactly the four new tables",
          up.returncode == 0 and tables() - before == NEW_TABLES)
    con = sqlite3.connect(db)
    bad = []
    for sql in (
        "INSERT INTO roadmap_items (id, client_id, engagement_id, sequence, title, problem_framing,"
        " rationale, expected_outcome, origin, status, created_by_consultant_id, review_status,"
        " lifecycle_status) VALUES ('r', 'c', 'e', 1, 't', 'p', 'r', 'o', 'consultant',"
        " 'audited', 'x', 'draft', 'draft')",
        "INSERT INTO engagement_phases (id, client_id, engagement_id, origin, title, scope_summary,"
        " status, created_by_consultant_id, review_status, lifecycle_status) VALUES ('p', 'c', 'e',"
        " 'manual', 't', 's', 'compliant', 'x', 'draft', 'draft')",
        "INSERT INTO phase_tasks (id, client_id, engagement_id, phase_id, sequence, title,"
        " instructions, origin, status, created_by_consultant_id, review_status, lifecycle_status)"
        " VALUES ('t', 'c', 'e', 'p', 1, 't', 'i', 'consultant', 'passed', 'x', 'draft', 'draft')",
        "INSERT INTO phase_task_records (id, client_id, engagement_id, phase_id, task_id,"
        " record_kind, record_text, recorded_by_consultant_id, review_status, lifecycle_status)"
        " VALUES ('r', 'c', 'e', 'p', 't', 'finding', 'x', 'x', 'draft', 'draft')",
    ):
        try:
            con.execute(sql)
            bad.append(sql[:40])
        except sqlite3.IntegrityError:
            pass
    con.close()
    check("the migrated CHECK constraints refuse values outside each vocabulary", not bad)
    down = alembic(db, "downgrade", "021_discovery_observation_trace_basis")
    check("downgrade to 021 removes exactly those tables",
          down.returncode == 0 and tables() == before)
    src = open(os.path.join(REPO_ROOT,
                            "alembic/versions/022_engagement_roadmap_work_plan.py")).read()
    body = src.split('"""', 2)[2].lower()
    check("migration 022 carries no data and alters no existing table",
          "insert" not in body and "op.execute" not in body and "add_column" not in body
          and "alter_column" not in body)
    import peak.db.models as m
    check("the models declare the same four tables",
          NEW_TABLES <= set(m.Base.metadata.tables)
          and {t.__tablename__ for t in m.ALL_MODELS} >= NEW_TABLES)


# --------------------------------------------------------------------------- 3-7. app


def _setup(tmp):
    from fastapi.testclient import TestClient

    from peak import accounts
    from peak.consultant_api.app import create_app
    from peak.db.session import create_session_factory
    from peak.workspace import discovery

    db = os.path.join(tmp, "app.sqlite3")
    alembic(db, "upgrade", "head").check_returncode()
    factory = create_session_factory(url=f"sqlite:///{db}")
    q = {}
    for key, category, prompt in (
            ("rcv_walkthrough", "Receiving and storage", "Walk me through receiving."),
            ("count_method", "Counting and adjustments", "How are counts done?"),
            ("rtn_damaged", "Returns and stock condition", "How are returns handled?")):
        q[key] = discovery.create_question(factory, {"prompt": prompt, "category": category,
                                                     "answer_type": "long_text"},
                                           seed_key=key)["id"]
    people = {}
    for key, name, role in (("ada", "Ada Admin", "admin"), ("lee", "Lee Lead", "consultant"),
                            ("pat", "Pat Consultant", "consultant")):
        people[key] = accounts.create_consultant(factory, name=name, email=f"{key}@example.com",
                                                 role=role, password=PASSWORD)["id"]
    app = create_app(session_factory=factory, secret_key=SECRET, secure_cookie=True)
    clients = {}
    for key in people:
        clients[key] = TestClient(app, base_url="https://testserver")
        clients[key].post("/auth/login", json={"email": f"{key}@example.com", "password": PASSWORD})
    return factory, q, people, clients


def _counts(factory):
    from sqlalchemy import func, select

    from peak.db import models

    with factory() as s:
        return {m.__tablename__: s.scalar(select(func.count()).select_from(m.__table__))
                for m in models.ALL_MODELS}


def app_checks(tmp, show_example=False):
    from peak.db import models
    from peak.persistence import allowlist
    from peak.workspace import engagement_phases as ep
    from peak.workspace.service import WorkspaceError

    factory, q, people, c = _setup(tmp)
    ada, lee, pat = c["ada"], c["lee"], c["pat"]

    cid = ada.post("/clients", json={"organization_label": "Synthetic Supply Co"}).json()["client"]["id"]
    eid = ada.post("/engagements", json={"client_id": cid, "engagement_label": "Synthetic Ops",
                                         "assigned_consultant_id": people["lee"]}
                   ).json()["engagement"]["id"]
    other = ada.post("/engagements", json={"client_id": cid, "engagement_label": "Answers only"}
                     ).json()["engagement"]["id"]

    print("\n[3. roadmap]")
    # Discovery: an interview answer and consultant observations.
    sid = lee.post(f"/engagements/{eid}/sessions", json={"interviewee_name": "Rae Receiver"}
                   ).json()["session"]["id"]
    lee.put(f"/sessions/{sid}/answers/{q['rcv_walkthrough']}",
            json={"answer": "Slips often disagree with the PO."})
    obs = []
    for text, qid in (("Receivers described frequent quantity differences between packing slips "
                       "and purchase orders.", q["rcv_walkthrough"]),
                      ("Two shifts receive differently: one counts before put-away, one after.",
                       q["rcv_walkthrough"]),
                      ("Adjustments are entered without a recorded reason.", q["count_method"])):
        obs.append(lee.post(f"/engagements/{eid}/observations",
                            json={"observation_text": text, "question_id": qid, "basis": "testimony"}
                            ).json()["observation"]["id"])
    # The other engagement has only an answer, no observation.
    osid = lee.post(f"/engagements/{other}/sessions", json={"interviewee_name": "Ola"}
                    ).json()["session"]["id"]
    lee.put(f"/sessions/{osid}/answers/{q['rcv_walkthrough']}", json={"answer": "Receiving is chaos."})
    other_obs = lee.post(f"/engagements/{other}/observations",
                         json={"observation_text": "Unrelated note."}).json()["observation"]["id"]

    before = _counts(factory)
    roadmap = lee.get(f"/engagements/{eid}/roadmap").json()["roadmap"]
    again = lee.get(f"/engagements/{eid}/roadmap").json()["roadmap"]
    sugg = {s["template_key"]: s for s in roadmap["suggestions"]}
    check("suggestions rest on cited observations: receiving (2) and count/adjustment (1)",
          set(sugg) == {"receiving_accuracy", "count_adjustment_practice"}
          and set(sugg["receiving_accuracy"]["source_observation_ids"]) == set(obs[:2])
          and sugg["count_adjustment_practice"]["source_observation_ids"] == [obs[2]])
    check("suggestions are deterministic and reading creates nothing",
          roadmap == again and _counts(factory) == before)
    check("answers never trigger a suggestion (answers-only engagement has none)",
          lee.get(f"/engagements/{other}/roadmap").json()["roadmap"]["suggestions"] == [])

    r = lee.post(f"/engagements/{eid}/roadmap-items", json={"template_key": "receiving_accuracy"})
    check("a Peak Method item without cited observations is refused (ungrounded)",
          code(r) == "ungrounded_suggestion")
    r = lee.post(f"/engagements/{eid}/roadmap-items",
                 json={"template_key": "receiving_accuracy", "source_observation_ids": [other_obs]})
    check("observations of another engagement cannot ground an item", code(r) == "invalid_field")
    r = lee.post(f"/engagements/{eid}/roadmap-items",
                 json={"title": "Receiving compliance audit", "problem_framing": "p",
                       "rationale": "r", "expected_outcome": "o"})
    check("an audit/compliance-framed roadmap item is refused (advisory_boundary)",
          code(r) == "advisory_boundary")
    rcv = lee.post(f"/engagements/{eid}/roadmap-items",
                   json={"template_key": "receiving_accuracy",
                         "source_observation_ids": sugg["receiving_accuracy"]["source_observation_ids"]}
                   ).json()["roadmap_item"]
    cnt = lee.post(f"/engagements/{eid}/roadmap-items",
                   json={"template_key": "count_adjustment_practice",
                         "source_observation_ids": [obs[2]]}).json()["roadmap_item"]
    man = pat.post(f"/engagements/{eid}/roadmap-items",
                   json={"title": "Item master clean-up", "problem_framing": "Duplicate items.",
                         "rationale": "Seen during the walk-through.",
                         "expected_outcome": "One record per item."}).json()["roadmap_item"]
    roadmap = lee.get(f"/engagements/{eid}/roadmap").json()["roadmap"]
    check("an engagement holds several ordered roadmap items (1, 2, 3)",
          [i["sequence"] for i in roadmap["items"]] == [1, 2, 3]
          and [i["id"] for i in roadmap["items"]] == [rcv["id"], cnt["id"], man["id"]])
    check("roadmap items record origin, template, method version and source observations",
          rcv["origin"] == "peak_method" and rcv["template_key"] == "receiving_accuracy"
          and rcv["method_version"] and set(rcv["source_observation_ids"]) == set(obs[:2])
          and man["origin"] == "consultant" and man["source_observation_ids"] == [])
    check("suggestions already on the roadmap are not suggested again",
          roadmap["suggestions"] == [])
    check("every item is proposed and none is authorized work",
          all(i["status"] == "proposed" and i["authorized_work"] is False
              for i in roadmap["items"]))

    r = lee.post(f"/engagements/{eid}/phases", json={"roadmap_item_id": rcv["id"]})
    check("a proposed roadmap item cannot become a phase", code(r) == "roadmap_item_not_accepted")
    rev = pat.post(f"/roadmap-items/{man['id']}/revision",
                   json={"expected_outcome": "One clean record per item, with an owner."}
                   ).json()["roadmap_item"]
    with factory() as s:
        old = s.get(models.RoadmapItem, man["id"])
        old_state = (old.status, old.expected_outcome)
    check("a revision supersedes; the original framing is kept unchanged",
          rev["supersedes_item_id"] == man["id"] and rev["sequence"] == 3
          and old_state == ("superseded", "One record per item."))
    check("a superseded item cannot be decided or revised again",
          code(lee.post(f"/roadmap-items/{man['id']}/decision", json={"status": "accepted"}))
          == "invalid_transition"
          and code(lee.post(f"/roadmap-items/{man['id']}/revision", json={"title": "x"}))
          == "invalid_transition")
    acc = lee.post(f"/roadmap-items/{rcv['id']}/decision",
                   json={"status": "accepted", "note": "Client asked for a proposal."}
                   ).json()["roadmap_item"]
    lee.post(f"/roadmap-items/{cnt['id']}/decision", json={"status": "deferred"})
    check("accepting records who and when, and is still not authorized work",
          acc["status"] == "accepted" and acc["decided_by_consultant_id"] == people["lee"]
          and acc["authorized_work"] is False)
    check("a roadmap item cannot be revised once accepted",
          code(lee.post(f"/roadmap-items/{rcv['id']}/revision", json={"title": "x"}))
          == "invalid_transition")

    print("\n[4. phases]")
    with factory() as s:
        phases_before = s.query(models.EngagementPhase).count()
    check("accepting a roadmap item creates no phase", phases_before == 0)
    phase = lee.post(f"/engagements/{eid}/phases", json={"roadmap_item_id": rcv["id"]}
                     ).json()["phase"]
    pid = phase["id"]
    check("a phase from an accepted item is planned, unauthorized, and linked to the item",
          phase["status"] == "planned" and phase["authorized"] is False
          and phase["origin"] == "roadmap_item" and phase["roadmap_item_id"] == rcv["id"]
          and phase["title"] == "Receiving Accuracy and Workflow Improvement"
          and phase["authorization"] is None and phase["work_plan_status"] == "not_started")
    check("a roadmap item becomes at most one phase",
          code(lee.post(f"/engagements/{eid}/phases", json={"roadmap_item_id": rcv["id"]}))
          == "phase_exists")
    check("an accepted item with a phase can no longer be declined",
          code(lee.post(f"/roadmap-items/{rcv['id']}/decision", json={"status": "declined"}))
          == "phase_exists")
    check("a manual phase needs a stated reason",
          code(lee.post(f"/engagements/{eid}/phases",
                        json={"title": "Pick path review", "scope_summary": "Review pick paths."}))
          == "invalid_field")
    check("a manual phase framed as a compliance test is refused",
          code(lee.post(f"/engagements/{eid}/phases",
                        json={"title": "Compliance test of picking", "scope_summary": "s",
                              "origin_note": "n"})) == "advisory_boundary")
    manual = lee.post(f"/engagements/{eid}/phases",
                      json={"title": "Pick path review", "scope_summary": "Review pick paths.",
                            "origin_note": "Client asked directly during a site visit."}
                      ).json()["phase"]
    check("a manual phase records its provenance", manual["origin"] == "manual"
          and manual["origin_note"] and manual["roadmap_item_id"] is None)

    r = lee.post(f"/phases/{pid}/template-tasks", json={})
    plan = r.json()["phase"]
    tasks = plan["tasks"]
    check("the item's Peak Method template becomes six ordered tasks on this phase only",
          r.status_code == 200 and [t["sequence"] for t in tasks] == [1, 2, 3, 4, 5, 6]
          and all(t["phase_id"] == pid and t["origin"] == "peak_method" for t in tasks)
          and plan["work_plan_status"] == "draft")
    check("a template is added only once",
          code(lee.post(f"/phases/{pid}/template-tasks", json={})) == "template_already_added")
    check("template tasks create no records", all(t["records"] == [] for t in tasks))
    t1, t2, t3, t4, t5, t6 = (t["id"] for t in tasks)
    check("tasks carry instructions, why, what to observe, evidence, questions, expected result",
          all(t["instructions"] and t["why_it_matters"] and t["what_to_observe"]
              and t["suggested_evidence"] and t["expected_result"] for t in tasks)
          and tasks[1]["follow_up_questions"] and "mismatch" in tasks[1]["suggested_evidence"])
    check("dependencies and the conditional follow-up are bound to task ids",
          tasks[2]["depends_on_task_ids"] == [t2]
          and tasks[2]["condition"] == {"task_id": t2, "record_kind": "mismatch"}
          and tasks[5]["depends_on_task_ids"] == [t1, t2, t3, t4]
          and tasks[4]["required"] is False)
    check("no work is recorded before authorization",
          code(lee.post(f"/tasks/{t1}/records", json={"record_kind": "note", "record_text": "x"}))
          == "phase_not_authorized")
    check("an unauthorized phase is not ready",
          lee.get(f"/phases/{pid}/readiness").json()["readiness"]["blocking"][0]["code"]
          == "phase_not_authorized")
    check("only the Lead or an Admin records authorization (403 for another consultant)",
          pat.post(f"/phases/{pid}/authorization",
                   json={"authorization_basis": "Signed proposal."}).status_code == 403)
    check("authorization needs a stated basis",
          code(lee.post(f"/phases/{pid}/authorization", json={"authorization_basis": " "}))
          == "invalid_field")
    auth = lee.post(f"/phases/{pid}/authorization",
                    json={"authorization_basis": "Client signed the Phase 1 proposal and fee.",
                          "authorization_reference": "Proposal P-1"}).json()["phase"]
    check("the Lead's authorization is recorded with basis, reference, who and when",
          auth["status"] == "authorized" and auth["authorization"]["basis"].startswith("Client")
          and auth["authorization"]["authorized_by_consultant_id"] == people["lee"]
          and auth["work_plan_status"] == "active")
    check("a phase is authorized once",
          code(lee.post(f"/phases/{pid}/authorization", json={"authorization_basis": "again"}))
          == "phase_closed")
    m_auth = ada.post(f"/phases/{manual['id']}/authorization",
                      json={"authorization_basis": "Separate engagement letter."}).json()["phase"]
    phases = lee.get(f"/engagements/{eid}/phases").json()["phases"]
    check("several phases on one engagement are separately authorized (Admin may authorize)",
          m_auth["status"] == "authorized" and len(phases) == 2
          and {p["status"] for p in phases} == {"authorized"}
          and len({p["authorization"]["authorized_at"] is not None for p in phases}) == 1)

    print("\n[5. work plan]")
    r = lee.post(f"/tasks/{t1}/completion", json={"result_summary": "Done."})
    check("a records-required task cannot be completed without a record", code(r) == "record_required")
    r = lee.post(f"/tasks/{t2}/records", json={"record_kind": "photo", "record_text": "bin 4"})
    check("photo / document capture is reserved for later (refused, not faked)",
          code(r) == "evidence_capture_not_available")
    r = lee.post(f"/tasks/{t1}/records", json={"record_kind": "finding", "record_text": "x"})
    check("an unknown record kind is refused", r.status_code == 422)
    r = lee.post(f"/tasks/{t1}/records",
                 json={"record_kind": "note", "basis": "observed",
                       "record_text": "Truck unloaded to staging; slips checked after put-away."})
    t1_state = next(t for t in r.json()["phase"]["tasks"] if t["id"] == t1)
    check("recording work starts the task and attributes the record to the signed-in consultant",
          t1_state["status"] == "in_progress"
          and t1_state["records"][0]["recorded_by_consultant_id"] == people["lee"])
    check("an empty result summary is refused",
          code(lee.post(f"/tasks/{t1}/completion", json={"result_summary": "  "})) == "invalid_field")
    lee.post(f"/tasks/{t1}/completion",
             json={"result_summary": "Observed workflow recorded; counts happen after put-away."})
    m1 = lee.post(f"/tasks/{t2}/records",
                  json={"record_kind": "mismatch", "record_text": "Short shipped by 2 cases.",
                        "basis": "document",
                        "structured": {"reference": "PO 1001 / PS 88", "expected": "10 cases",
                                       "observed": "8 cases"}}).json()["phase"]
    rec1 = next(t for t in m1["tasks"] if t["id"] == t2)["records"][0]["id"]
    fix = lee.post(f"/tasks/{t2}/records",
                   json={"record_kind": "mismatch", "record_text": "Short shipped by 3 cases.",
                         "supersedes_record_id": rec1,
                         "structured": {"reference": "PO 1001 / PS 88", "expected": "10 cases",
                                        "observed": "7 cases"}}).json()["phase"]
    t2_recs = next(t for t in fix["tasks"] if t["id"] == t2)["records"]
    check("a correction supersedes; the original record is kept",
          len(t2_recs) == 2 and t2_recs[0]["superseded_by"] == t2_recs[1]["id"]
          and t2_recs[0]["record_text"] == "Short shipped by 2 cases.")
    check("a record is corrected at most once",
          code(lee.post(f"/tasks/{t2}/records",
                        json={"record_kind": "mismatch", "record_text": "again",
                              "supersedes_record_id": rec1})) == "already_superseded")
    check("structured fields are checked per kind",
          code(lee.post(f"/tasks/{t2}/records",
                        json={"record_kind": "mismatch", "record_text": "x",
                              "structured": {"verdict": "non-compliant"}})) == "invalid_field")
    try:
        with factory() as s:
            row = s.get(models.PhaseTaskRecord, rec1)
            row.record_text = "edited"
            s.commit()
        immutable = False
    except PermissionError:
        immutable = True
    check("task records are immutable in the ORM (no update or delete)", immutable)
    lee.post(f"/tasks/{t2}/records", json={"record_kind": "note",
                                           "record_text": "Sample: 20 receipts from the last month."})
    lee.post(f"/tasks/{t2}/completion", json={"result_summary": "20 receipts; 1 mismatch."})
    r = lee.post(f"/tasks/{t6}/completion", json={"result_summary": "Patterns."})
    check("a task cannot be completed before its prerequisites", code(r) == "prerequisites_incomplete")
    ready = lee.get(f"/phases/{pid}/readiness").json()["readiness"]
    check("the conditional follow-up applies once its condition task recorded a mismatch",
          any(b["code"] == "required_task_incomplete" and b["task_id"] == t3
              for b in ready["blocking"]))
    lee.post(f"/tasks/{t3}/records", json={"record_kind": "interview_response", "basis": "testimony",
                                           "record_text": "Shorts are written on the slip; "
                                                          "nobody updates the PO.",
                                           "structured": {"interviewee_role": "Receiver"}})
    lee.post(f"/tasks/{t3}/completion", json={"result_summary": "Shorts are not fed back."})
    lee.post(f"/tasks/{t4}/records", json={"record_kind": "interview_response",
                                           "record_text": "Waiting for paperwork slows us most.",
                                           "structured": {"interviewee_role": "Receiving lead",
                                                          "question": "What slows receiving down?"}})
    lee.patch(f"/tasks/{t4}", json={"consultant_notes": "The client's external auditor visits in "
                                                        "March; staff mentioned it."})
    lee.post(f"/tasks/{t4}/completion", json={"result_summary": "Two interviews recorded."})
    check("consultant notes record what happened and are not filtered",
          lee.get(f"/phases/{pid}").json()["phase"]["tasks"][3]["consultant_notes"]
          .startswith("The client's external auditor"))

    added = lee.post(f"/phases/{pid}/tasks",
                     json={"title": "Time the receiving cycle", "instructions": "Time three receipts.",
                           "inclusion_reason": "The client asked for timings during the visit.",
                           "suggested_evidence": ["measurement"]}).json()["phase"]["tasks"][-1]
    check("a task added after authorization is marked as a scope change",
          added["added_after_authorization"] is True and added["origin"] == "consultant"
          and added["sequence"] == 7)
    check("a task framed as an audit step is refused",
          code(lee.post(f"/phases/{pid}/tasks",
                        json={"title": "Audit receiving", "instructions": "i",
                              "inclusion_reason": "r"})) == "advisory_boundary")
    check("the API cannot claim a synthesis origin",
          lee.post(f"/phases/{pid}/tasks", json={"title": "t", "instructions": "i",
                                                 "inclusion_reason": "r",
                                                 "origin": "si_suggested"}).status_code == 422)
    sugg_phase = ep.add_task(factory, pid, {"title": "Compare receiving by shift",
                                            "instructions": "Compare the two shifts.",
                                            "inclusion_reason": "Conflicting interview accounts."},
                             people["lee"], origin="si_suggested")
    suggested = sugg_phase["tasks"][-1]
    check("a synthesis-suggested task enters as suggested, outside the plan",
          suggested["status"] == "suggested" and suggested["origin"] == "si_suggested")
    check("a suggested task cannot be worked or completed until accepted",
          code(lee.post(f"/tasks/{suggested['id']}/completion",
                        json={"result_summary": "inferred"})) == "task_not_accepted"
          and code(lee.post(f"/tasks/{suggested['id']}/records",
                            json={"record_kind": "note", "record_text": "x"}))
          == "task_not_accepted")

    print("\n[6. readiness]")
    ready = lee.get(f"/phases/{pid}/readiness").json()["readiness"]
    blocking = {b.get("task_id") for b in ready["blocking"]}
    check("incomplete required tasks block readiness (task 6 and the added task 7)",
          not ready["ready"] and blocking == {t6, added["id"]})
    check("the optional photo task and the suggested task do not block",
          t5 not in blocking and suggested["id"] not in blocking
          and any(n["code"] == "optional_incomplete" and n["task_id"] == t5 for n in ready["notes"])
          and any(n["code"] == "suggestion_pending" for n in ready["notes"]))
    check("completing the phase is refused while not ready",
          code(lee.post(f"/phases/{pid}/completion")) == "phase_not_ready")
    lee.post(f"/tasks/{added['id']}/not-applicable",
             json={"reason": "Client withdrew the timing request."})
    lee.post(f"/tasks/{t6}/records", json={"record_kind": "note",
                                           "record_text": "Pattern: shorts are noted on paper "
                                                          "but never reach the PO, causing rework "
                                                          "at invoice matching."})
    lee.post(f"/tasks/{t6}/completion", json={"result_summary": "One recurring pattern recorded."})
    ready = lee.get(f"/phases/{pid}/readiness").json()["readiness"]
    check("completed required tasks permit readiness (optional and suggested still open)",
          ready["ready"] and ready["blocking"] == []
          and ready["required_tasks"] == ready["required_resolved"] == 6)
    check("readiness notes show the not-applicable resolution and the scope addition",
          {"resolved_not_applicable", "added_after_authorization"}
          <= {n["code"] for n in ready["notes"] if n["task_id"] == added["id"]})
    final_before = lee.get(f"/engagements/{eid}/final-report")
    done = lee.post(f"/phases/{pid}/completion").json()["phase"]
    check("a ready phase completes, recording who and when",
          done["status"] == "completed" and done["completed_by_consultant_id"] == people["lee"]
          and done["work_plan_status"] == "closed")
    check("a completed phase accepts no more work",
          code(lee.post(f"/tasks/{t5}/records", json={"record_kind": "note", "record_text": "x"}))
          == "phase_closed")

    # A conditional task whose condition is not met does not block (manual phase).
    mp = manual["id"]
    check("a phase with no work plan is not ready",
          lee.get(f"/phases/{mp}/readiness").json()["readiness"]["blocking"][0]["code"]
          == "no_work_plan")
    a = lee.post(f"/phases/{mp}/tasks", json={"title": "Walk the pick paths",
                                              "instructions": "Walk the three busiest paths.",
                                              "inclusion_reason": "Core of the agreed scope.",
                                              "requires_record": True}
                 ).json()["phase"]["tasks"][0]["id"]
    b = lee.post(f"/phases/{mp}/tasks", json={"title": "Follow up on path mismatches",
                                              "instructions": "Ask how mismatches are handled.",
                                              "inclusion_reason": "Only if mismatches appear.",
                                              "depends_on_task_ids": [a],
                                              "condition": {"task_id": a, "record_kind": "mismatch"}}
                 ).json()["phase"]["tasks"][1]["id"]
    pending = lee.get(f"/phases/{mp}/readiness").json()["readiness"]
    check("a conditional required task waits on its condition",
          any(x["code"] == "condition_pending" and x["task_id"] == b for x in pending["blocking"]))
    lee.post(f"/tasks/{a}/records", json={"record_kind": "measurement", "record_text": "Path 1",
                                          "structured": {"measure": "walk time", "value": 4.5,
                                                         "unit": "minutes"}})
    lee.post(f"/tasks/{a}/completion", json={"result_summary": "Walked; no mismatches seen."})
    unmet = lee.get(f"/phases/{mp}/readiness").json()["readiness"]
    check("a conditional task whose condition was not met does not block",
          unmet["ready"] and any(n["code"] == "condition_not_met" and n["task_id"] == b
                                 for n in unmet["notes"]))

    print("\n[7. no fabrication, governance]")
    after = _counts(factory)
    check("phase work created no discovery observation, answer or finding",
          all(after[t] == before[t] for t in ("discovery_observations", "discovery_answers",
                                              "discovery_sessions")))
    with factory() as s:
        recs = s.query(models.PhaseTaskRecord).all()
        rows = (s.query(models.RoadmapItem).all() + s.query(models.EngagementPhase).all()
                + s.query(models.PhaseTask).all() + recs)
    check("every task record was written by a signed-in consultant",
          recs and all(r.recorded_by_consultant_id in people.values() for r in recs))
    check("every new row carries the workspace stamp",
          all(r.owner_id == "peak_consultants" and r.authorization_scope == "engagement_authorized"
              for r in rows))
    with factory() as s:
        completed = [t for t in s.query(models.PhaseTask).all() if t.status == "completed"]
    check("every completed task has a consultant-written result and completer",
          all(t.result_summary and t.completed_by_consultant_id in people.values()
              for t in completed))
    final_after = lee.get(f"/engagements/{eid}/final-report")
    check("the Final Report does not change with phase work",
          final_before.status_code == final_after.status_code == 200
          and final_before.json()["report"] == final_after.json()["report"]
          and "Short shipped" not in final_after.text
          and "Review a sample of purchase orders" not in final_after.text)
    pairs = [(t, a) for (t, a) in allowlist.WORKSPACE_WRITE_COLUMNS
             if t in allowlist.ENGAGEMENT_PHASE_RECORD_TABLES]
    check("no delete action; task records are create-only; every pair passes the predicate",
          not any("delete" in a for _, a in pairs)
          and [a for t, a in pairs if t == "phase_task_records"] == ["create_phase_task_record"]
          and all(allowlist.is_allowed_workspace_write(t, a, allowlist.WORKSPACE_WRITE_COLUMNS[(t, a)])
                  for t, a in pairs))
    framing = allowlist.ROADMAP_ITEM_FRAMING_COLUMNS | allowlist.PHASE_TASK_FRAMING_COLUMNS
    check("no update action writes a framing column, or any governance column",
          not any(allowlist.WORKSPACE_WRITE_COLUMNS[(t, a)] & framing
                  for t, a in pairs if not a.startswith("create_"))
          and not any(allowlist.WORKSPACE_WRITE_COLUMNS[p] & allowlist.WORKSPACE_FORBIDDEN_COLUMNS
                      for p in pairs))
    try:
        ep.decide_roadmap_item(factory, cnt["id"], "authorized", None, people["lee"])
        refused = False
    except WorkspaceError as exc:
        refused = exc.code == "invalid_transition"
    check("no roadmap transition leads to authorization", refused)
    check("a missing engagement holds no roadmap or phase (404)",
          lee.post("/engagements/eng_missing/roadmap-items", json={"title": "t"}).status_code
          == 404 and lee.get("/engagements/eng_missing/phases").status_code == 404)

    if show_example:
        print("\n[example] Receiving Accuracy and Workflow Improvement")
        print(json.dumps({"roadmap": lee.get(f"/engagements/{eid}/roadmap").json()["roadmap"],
                          "phase": lee.get(f"/phases/{pid}").json()["phase"]}, indent=2))


def main() -> int:
    print("Peak Phase 217 engagement roadmap and guided work plan check")
    print("=" * 62)
    try:
        import argon2, fastapi, httpx, itsdangerous, sqlalchemy  # noqa: F401,E401
    except ImportError:
        print("  [skip] web dependencies not installed — run with PYTHON=.venv/bin/python")
        return 0
    with tempfile.TemporaryDirectory(prefix="peak_phase217_") as tmp:
        boundary_checks()
        migration_checks(tmp)
        app_checks(tmp, show_example="--example" in sys.argv)
    for doc in ("docs/PHASE217_ENGAGEMENT_ROADMAP_WORK_PLAN.md",
                "docs/ADVISORY_ENGAGEMENT_BOUNDARY.md"):
        check(f"{doc} exists", os.path.exists(os.path.join(REPO_ROOT, doc)))
    contract = open(os.path.join(REPO_ROOT, "docs/PEAK_PROJECT_CONTRACT.md")).read()
    check("the Contract books the advisory boundary (C21)",
          "### C21 — Advisory engagement boundary" in contract)

    print("\nSummary")
    print(f"  failures : {len(_failures)}")
    print("RESULT: " + ("PASS" if not _failures else "FAIL"))
    return 0 if not _failures else 1


if __name__ == "__main__":
    sys.exit(main())
