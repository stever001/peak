#!/usr/bin/env python3
"""Phase 216 — discovery instrument hardening check (offline; temporary SQLite only).

Proves:

1. **Instrument.** The catalogue has 29 core questions and 17 conditional follow-ups. Every entry
   defines all 12 rationale fields and a source provenance. Branches are valid and deterministic,
   and evidence requests use the three agreed choices. The material SMB inventory domains are
   covered, and a session runs 29 to 42 questions.
2. **Migration 021.** It goes up and down, adds only nullable columns to ``discovery_observations``
   and ``discovery_questions``, carries no data, and enforces the basis vocabulary.
3. **Rollout.** The seed tool adds the instrument after an existing Phase 204 pool and retires the
   superseded questions by deactivation only. Old rows, wording and answers (with their prompt
   snapshots) are untouched, and a second run is a no-op.
4. **Canonical vs supplemental.** Only an Admin edits or deactivates a canonical question. A
   supplemental question records its field-use provenance, is asked only in its engagement, and
   never becomes canonical through the API. Its usage is derived, not stored.
5. **Observation trace and basis.** An observation may name the question that prompted it (within
   its engagement) and its basis. The assessment and report carry both. Answers never become
   findings, and discovery is still not evidence (Contract C4).
6. **Governance.** No delete action and no forbidden column is added, and the artifact
   immutability models are unchanged.

Exit status: 0 all checks passed; 1 a check failed.
"""

from __future__ import annotations

import io
import itertools
import os
import re
import sqlite3
import subprocess
import sys
import tempfile
from contextlib import redirect_stdout
from types import SimpleNamespace

REPO_ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
for _p in (REPO_ROOT, os.path.join(REPO_ROOT, "tools")):
    if _p not in sys.path:
        sys.path.insert(0, _p)

PASSWORD = "phase216-password"
SECRET = "phase216-secret-key-phase216-secret-key"
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


# --------------------------------------------------------------------------- 1. instrument


def instrument_checks():
    print("\n[1. instrument catalogue]")
    from peak.workspace import discovery
    from peak.workspace import discovery_instrument as d
    from peak.workspace.initial_questions import INITIAL_QUESTIONS

    keys = [q["key"] for q in d.QUESTIONS]
    check("29 core questions and 17 conditional follow-ups, unique keys",
          len(d.CORE_KEYS) == 29 and len(d.FOLLOW_UP_KEYS) == 17 and len(set(keys)) == 46)
    check("labor_rework is a core question",
          "labor_rework" in d.CORE_KEYS)
    check("the superseded set is exactly the 29 Phase 204 keys, and no new key reuses one",
          set(d.SUPERSEDED_PHASE204_KEYS) == {q["key"] for q in INITIAL_QUESTIONS}
          and not set(keys) & set(d.SUPERSEDED_PHASE204_KEYS))

    def complete(q):
        r = q["rationale"]
        return (set(r) == set(d.RATIONALE_FIELDS) and r["question"] == q["question"]
                and all(isinstance(r[f], str) and r[f].strip() for f in d.RATIONALE_FIELDS
                        if f not in ("purpose", "finding_classes"))
                and r["purpose"] and set(r["purpose"]) <= set(d.PURPOSE_TYPES)
                and set(r["finding_classes"]) <= set(d.FINDING_CLASSES))
    check("every question defines all 12 rationale fields (purpose and classes from the vocabularies)",
          all(complete(q) for q in d.QUESTIONS))
    check("14 provisional finding-class codes",
          len(d.FINDING_CLASSES) == 14)

    position = {k: i for i, k in enumerate(keys)}

    def branch_ok(q):
        if q["core"]:
            return q["branch"] is None
        parent_key, operator, value = q["branch"]
        parent = d.BY_KEY.get(parent_key)
        if parent is None or position[parent_key] >= position[q["key"]] or not parent["core"]:
            return False
        if operator not in discovery.BRANCH_OPERATORS:
            return False
        if parent["type"] == "yes_no":
            return value in ("yes", "no")
        return parent["type"] == "single_choice" and value in parent["choices"]
    check("core questions never branch; every follow-up branches on an earlier core gate with a "
          "valid value", all(branch_ok(q) for q in d.QUESTIONS))
    gates = {q["branch"][0] for q in d.QUESTIONS if q["branch"]}
    check("ten diagnostic gates", len(gates) == 10)
    evidence = [q for q in d.QUESTIONS if q["rationale"]["purpose"] == ["evidence request"]]
    check("six evidence-request follow-ups, each answered Provided / Will provide / Not available",
          len(evidence) == 6 and all(not q["core"] and q["type"] == "single_choice"
                                     and q["choices"] == ["Provided", "Will provide", "Not available"]
                                     for q in evidence))
    check("evidence-request wording marks it as a request, not evidence",
          all(q["question"].startswith("Evidence request:") for q in evidence))

    domains = " | ".join(q["rationale"]["domain"].lower() for q in d.QUESTIONS)
    required = ("inventory accuracy", "receiving", "putaway", "storage", "replenishment",
                "picking", "cycle counting", "physical inventory", "adjustments", "returns",
                "damaged", "obsolete", "master data", "system-of-record", "integrations",
                "ownership", "controls", "metrics", "staffing", "root causes",
                "business impact", "future state", "traceability")
    missing = [r for r in required if r not in domains]
    check(f"the material SMB inventory domains are covered ({len(required)} checked)", not missing)

    # Session size, over every combination of gate answers (exhaustive and deterministic).
    rows = [SimpleNamespace(id=q["key"], active=True,
                            branch_question_id=q["branch"][0] if q["branch"] else None,
                            branch_operator=q["branch"][1] if q["branch"] else None,
                            branch_value=q["branch"][2] if q["branch"] else None)
            for q in d.QUESTIONS]
    options = [(g, ["yes", "no"] if d.BY_KEY[g]["type"] == "yes_no" else d.BY_KEY[g]["choices"])
               for g in sorted(gates, key=position.get)]
    sizes = set()
    for combo in itertools.product(*[vals for _, vals in options]):
        answers = dict(zip([g for g, _ in options], combo))
        sizes.add(sum(1 for _, visible in discovery._visible_flow(rows, answers) if visible))
    unanswered = sum(1 for _, visible in discovery._visible_flow(rows, {}) if visible)
    check("before any gate is answered an interview shows the 29 core questions", unanswered == 29)
    # Three gates (count_method, adj_reviewed, kpi_reviewed) open one side of a pair whatever the
    # answer, so a fully answered interview has at least 32 questions.
    check(f"a fully answered interview shows 32 to 42 questions (observed {min(sizes)}–{max(sizes)})",
          min(sizes) == 32 and max(sizes) == 42)
    first = [v for _, v in discovery._visible_flow(rows, {"count_method": "Both"})]
    again = [v for _, v in discovery._visible_flow(rows, {"count_method": "Both"})]
    check("branching is deterministic: the same answers always show the same questions",
          first == again)

    print("\n[1b. source provenance]")
    check("every question has a provenance entry",
          set(d.PROVENANCE) == set(d.BY_KEY))
    used_ok = all(
        all(s["source"] in d.SOURCES and s["supports"]
            and set(s["supports"]) <= set(d.SOURCE_SUPPORTS) for s in p["primary_sources"])
        and all(f in d.SOURCES for f in p["further_reading"])
        and p["revision_triggers"].strip() and p["primary_sources"]
        for p in d.PROVENANCE.values())
    check("every cited source is registered, with what it supports; every entry names a revision "
          "trigger", used_ok)

    def basis_ok(p):
        names = {s["source"] for s in p["primary_sources"]}
        return p["basis"] == ("peak_method_design" if names == {"peak_method_design"}
                              else "mixed" if "peak_method_design" in names else "external")
    check("a Peak Method design choice is labelled as such (basis follows the sources)",
          all(basis_ok(p) for p in d.PROVENANCE.values()))
    check("registered sources have a kind from the vocabulary and a title",
          all(s["kind"] in d.SOURCE_KINDS and s["title"] for s in d.SOURCES.values()))
    external = {k: v for k, v in d.SOURCES.items()
                if v["kind"] not in ("peak_method_design", "peak_field_observation")}
    check(f"all {len(external)} external sources carry verified author and year or edition "
          f"(verified {d.SOURCES_VERIFIED_ON})",
          d.SOURCES_VERIFIED_ON and all(v.get("author") and (v.get("year") or v.get("edition"))
                                        for v in external.values()))
    check("no page-level citation is claimed",
          not any(re.search(r"\bp{1,2}\.\s*\d", str(v)) for v in d.SOURCES.values()))
    field = d.SOURCES["peak_field_observation"]
    check("consultant-added questions are a recognized internal source, cited without client "
          "information", field["kind"] == "peak_field_observation"
          and field["title"] == "Peak field observation / consultant-added question from prior "
                                "engagement")

    print("\n[1c. governing rule]")
    for path in ("peak/workspace/discovery_instrument.py", "peak/workspace/discovery.py"):
        text = " ".join(open(os.path.join(REPO_ROOT, path)).read().split())
        check(f"{path} states that answers never create findings, evidence or recommendations",
              re.search(r"creates? a finding", text) and "governed evidence" in text
              and re.search(r"authoriz\w* a recommendation", text))
    src = open(os.path.join(REPO_ROOT, "peak/workspace/discovery.py")).read().lower()
    check("question selection imports no model client (no LLM-chosen next question)",
          not re.search(r"import (anthropic|openai)|from (anthropic|openai)", src))


# --------------------------------------------------------------------------- 2. migration


def migration_checks(tmp):
    print("\n[2. migration 021]")
    import sqlalchemy as sa

    db = os.path.join(tmp, "mig.sqlite3")

    def columns(table):
        return {c["name"] for c in sa.inspect(sa.create_engine(f"sqlite:///{db}"))
                .get_columns(table)}

    obs_new = {"question_id", "basis"}
    q_new = {"engagement_id", "added_by_consultant_id", "rationale", "domain", "finding_classes"}
    up = alembic(db, "upgrade", "021_discovery_observation_trace_basis")
    check("upgrade to 021 adds the observation and question columns",
          up.returncode == 0 and obs_new <= columns("discovery_observations")
          and q_new <= columns("discovery_questions"))
    con = sqlite3.connect(db)
    nullable = all(not r[3] for t, cols in (("discovery_observations", obs_new),
                                            ("discovery_questions", q_new))
                   for r in con.execute(f"PRAGMA table_info({t})") if r[1] in cols)
    con.close()
    check("every new column is nullable", nullable)
    # The named basis CHECK is created where ALTER TABLE can add one (MySQL); a database built from
    # the models carries it on every dialect.
    import peak.db.models as m
    eng = sa.create_engine(f"sqlite:///{os.path.join(tmp, 'models.sqlite3')}")
    m.Base.metadata.create_all(eng)
    con = sqlite3.connect(os.path.join(tmp, "models.sqlite3"))
    try:
        con.execute("INSERT INTO discovery_observations (id, client_id, engagement_id, "
                    "observation_text, low_hanging_fruit, recorded_by_consultant_id, basis) "
                    "VALUES ('dobs_x', 'c', 'e', 't', 0, 'cons', 'hearsay')")
        refused = False
    except sqlite3.IntegrityError:
        refused = True
    con.close()
    check("the model's basis CHECK refuses a value outside the vocabulary", refused)
    mig = open(os.path.join(REPO_ROOT,
                            "alembic/versions/021_discovery_observation_trace_basis.py")).read()
    check("migration 021 creates the same named CHECK on MySQL",
          'create_check_constraint("ck_discovery_observations_basis"' in mig
          and "'testimony', 'observed', 'document', 'measured', " in mig)
    down = alembic(db, "downgrade", "020_internal_test_engagement_retirement")
    check("downgrade to 020 removes exactly those columns",
          down.returncode == 0 and not obs_new & columns("discovery_observations")
          and not q_new & columns("discovery_questions"))
    src = open(os.path.join(REPO_ROOT,
                            "alembic/versions/021_discovery_observation_trace_basis.py")).read()
    body = src.split('"""', 2)[2].lower()
    import peak.db.models as m
    targets = set(re.findall(r'"(\w+)"', body)) & set(m.Base.metadata.tables)
    check("migration 021 carries no data and touches only the two discovery tables",
          "insert" not in body and "op.execute" not in body
          and targets == {"discovery_observations", "discovery_questions"})


# --------------------------------------------------------------------------- 3-6. app


def app_checks(tmp):
    from fastapi.testclient import TestClient
    from sqlalchemy import select

    import init_discovery_questions as init
    from peak import accounts
    from peak.consultant_api.app import create_app
    from peak.db import models
    from peak.db.session import create_session_factory
    from peak.persistence import allowlist
    from peak.workspace import discovery
    from peak.workspace import discovery_instrument as d
    from peak.workspace.initial_questions import INITIAL_QUESTIONS

    db = os.path.join(tmp, "app.sqlite3")
    alembic(db, "upgrade", "head").check_returncode()
    factory = create_session_factory(url=f"sqlite:///{db}")

    # A pool exactly as Phase 205 seeded production: the 29 Phase 204 questions.
    keyed = {}
    for index, item in enumerate(INITIAL_QUESTIONS):
        data = {"prompt": item["prompt"], "category": item["category"],
                "answer_type": item["type"], "display_order": (index + 1) * 10}
        if item.get("choices"):
            data["choices"] = list(item["choices"])
        if item.get("branch"):
            parent, op, value = item["branch"]
            data["branch"] = {"question_id": keyed[parent], "operator": op, "value": value}
        keyed[item["key"]] = discovery.create_question(factory, data, seed_key=item["key"])["id"]

    people = {}
    for key, name, role in (("ada", "Ada Admin", "admin"), ("lee", "Lee Consultant", "consultant")):
        people[key] = accounts.create_consultant(factory, name=name, email=f"{key}@example.com",
                                                 role=role, password=PASSWORD)["id"]
    app = create_app(session_factory=factory, secret_key=SECRET, secure_cookie=True)
    ada, lee = (TestClient(app, base_url="https://testserver") for _ in range(2))
    ada.post("/auth/login", json={"email": "ada@example.com", "password": PASSWORD})
    lee.post("/auth/login", json={"email": "lee@example.com", "password": PASSWORD})

    cid = lee.post("/clients", json={"organization_label": "Synthetic Co"}).json()["client"]["id"]
    eid = lee.post("/engagements", json={"client_id": cid, "engagement_label": "Synthetic A"}
                   ).json()["engagement"]["id"]
    other = lee.post("/engagements", json={"client_id": cid, "engagement_label": "Synthetic B"}
                     ).json()["engagement"]["id"]

    # An interview answered against the old pool, before the rollout.
    old_sid = lee.post(f"/engagements/{eid}/sessions",
                       json={"interviewee_name": "Pat Picker"}).json()["session"]["id"]
    lee.put(f"/sessions/{old_sid}/answers/{keyed['goal_success']}", json={"answer": "Counts we trust."})
    lee.put(f"/sessions/{old_sid}/answers/{keyed['cc_performed']}", json={"answer": "yes"})
    lee.put(f"/sessions/{old_sid}/answers/{keyed['cc_frequency']}", json={"answer": "Monthly"})
    # An Admin edit to a legacy question before the rollout.
    ada.patch(f"/questions/{keyed['goal_pain']}", json={"prompt": "Edited legacy wording?"})

    def snapshot():
        with factory() as s:
            qs = {q.id: (q.prompt, q.category, q.answer_type, q.choices, q.display_order,
                         q.branch_question_id, q.branch_value, q.seed_key)
                  for q in s.scalars(select(models.DiscoveryQuestion)
                                     .where(models.DiscoveryQuestion.id.in_(keyed.values())))}
            ans = {a.id: (a.question_id, a.question_prompt_snapshot, a.answer_text)
                   for a in s.scalars(select(models.DiscoveryAnswer))}
        return qs, ans

    print("\n[3. rollout: insert the instrument, retire the Phase 204 pool]")
    before_q, before_a = snapshot()
    out = io.StringIO()
    with redirect_stdout(out):
        dry = init.main([], session_factory=factory)
    check("dry run reports 46 to create and 29 to retire, and writes nothing",
          dry == 0 and "would create 46" in out.getvalue() and "would retire 29" in out.getvalue()
          and snapshot() == (before_q, before_a))
    result = init.initialize(factory)
    check("execute creates 46 and retires 29",
          result == {"created": 46, "already_present": 0, "retired": 29})
    after_q, after_a = snapshot()
    with factory() as s:
        rows = s.scalars(select(models.DiscoveryQuestion)).all()
    old_rows = [q for q in rows if q.id in keyed.values()]
    new_rows = [q for q in rows if q.seed_key in d.BY_KEY]
    check("no question was deleted: 29 old + 46 new rows",
          len(rows) == 75 and len(old_rows) == 29 and len(new_rows) == 46)
    check("every superseded question is inactive; every instrument question is active",
          not any(q.active for q in old_rows) and all(q.active for q in new_rows))
    check("old questions keep their wording, order and branches (only 'active' changed)",
          after_q == before_q)
    check("the Admin-edited legacy wording is kept, not overwritten",
          after_q[keyed["goal_pain"]][0] == "Edited legacy wording?")
    check("every stored answer and its prompt snapshot is untouched", after_a == before_a)
    check("instrument questions are ordered after the old pool",
          min(q.display_order for q in new_rows) > max(q.display_order for q in old_rows))
    with factory() as s:
        prompts = {q.seed_key: q.prompt for q in new_rows}
    check("instrument wording is stored exactly as catalogued",
          all(prompts[k] == d.BY_KEY[k]["question"] for k in d.BY_KEY))
    check("a second run is a no-op",
          init.initialize(factory) == {"created": 0, "already_present": 46, "retired": 0})
    history = lee.get(f"/sessions/{old_sid}").json()["session"]["history"]
    check("the old interview keeps its answers under their original prompts",
          any(h["question_id"] == keyed["goal_success"] and h["answer"] == "Counts we trust."
              and h["prompt"] == "What outcome would make this engagement clearly successful?"
              for h in history))
    ids = {q.seed_key: q.id for q in new_rows}

    print("\n[4. canonical questions are Admin-controlled]")
    canonical = ids["goal_north_star"]
    r1 = lee.patch(f"/questions/{canonical}", json={"prompt": "Rewritten by a consultant?"})
    r2 = lee.patch(f"/questions/{canonical}", json={"active": False})
    r3 = lee.patch(f"/questions/{keyed['goal_success']}", json={"active": True})
    check("a Consultant cannot reword, deactivate or reactivate a canonical question (403)",
          [x.status_code for x in (r1, r2, r3)] == [403, 403, 403]
          and code(r1) == "admin_required")
    q = lee.get(f"/questions/{canonical}").json()["question"]
    check("the canonical question is unchanged", q["prompt"] == d.BY_KEY["goal_north_star"]["question"]
          and q["active"] and q["canonical"] and q["seed_key"] == "goal_north_star")
    r = ada.patch(f"/questions/{canonical}", json={"prompt": d.BY_KEY["goal_north_star"]["question"]})
    check("an Admin can edit a canonical question", r.status_code == 200)
    check("the service refuses a canonical edit without an Admin role, by default",
          _raises(lambda: discovery.update_question(factory, canonical, {"active": False}),
                  "admin_required"))
    check("the API cannot create a canonical question (seed_key is not accepted, 422)",
          lee.post("/questions", json={"prompt": "X?", "category": "X", "answer_type": "short_text",
                                       "seed_key": "goal_north_star"}).status_code == 422)

    print("\n[4b. supplemental questions and their field-use provenance]")
    body = {"prompt": "Do weekend shifts post adjustments without review?",
            "category": "Counting and adjustments", "answer_type": "yes_no",
            "engagement_id": eid}
    check("an engagement supplemental question needs a rationale (422)",
          lee.post("/questions", json=body).status_code == 422)
    check("finding-class tags must come from the vocabulary (422)",
          lee.post("/questions", json={**body, "rationale": "x",
                                       "finding_classes": ["NOPE"]}).status_code == 422)
    check("the author cannot be supplied by the caller (422)",
          lee.post("/questions", json={**body, "rationale": "x",
                                       "added_by_consultant_id": people["ada"]}).status_code == 422)
    r = lee.post("/questions", json={**body, "rationale": "The adjustment history shows weekend spikes.",
                                     "domain": "Controls and authorization",
                                     "finding_classes": ["CTRL", "ACC"],
                                     "branch": {"question_id": ids["adj_reviewed"],
                                                "operator": "equals", "value": "no"}})
    sup = r.json().get("question", {})
    check("a Consultant adds one: engagement, author, rationale, tags, parent and created_at kept",
          r.status_code == 201 and sup["engagement_id"] == eid
          and sup["added_by_consultant_id"] == people["lee"]
          and sup["rationale"].startswith("The adjustment history")
          and sup["domain"] == "Controls and authorization"
          and sup["finding_classes"] == ["ACC", "CTRL"]
          and sup["branch"]["question_id"] == ids["adj_reviewed"] and sup["created_at"])
    check("it is supplemental, never canonical", sup["canonical"] is False and sup["seed_key"] is None)
    check("its engagement cannot be changed afterwards (422)",
          lee.patch(f"/questions/{sup['id']}", json={"engagement_id": other}).status_code == 422)
    check("a Consultant can edit their supplemental question's rationale",
          lee.patch(f"/questions/{sup['id']}", json={"rationale": "Weekend spikes in the history."}
                    ).json()["question"]["rationale"] == "Weekend spikes in the history.")
    check("a question in another engagement cannot branch on it (422)",
          lee.post("/questions", json={"prompt": "Y?", "category": "X", "answer_type": "short_text",
                                       "engagement_id": other, "rationale": "y",
                                       "branch": {"question_id": sup["id"], "operator": "equals",
                                                  "value": "yes"}}).status_code == 422)
    check("an unstamped engagement cannot take a supplemental question (422)",
          _anchor(factory, cid) and lee.post("/questions", json={
              **body, "engagement_id": "eng_anchor_216", "rationale": "x"}).status_code == 422)
    global_body = {"prompt": "Global question?", "category": "Close", "answer_type": "short_text"}
    r = lee.post("/questions", json=global_body)
    check("a Consultant cannot add a global question (403 admin_required)",
          r.status_code == 403 and code(r) == "admin_required")
    check("the service refuses a global question without an Admin role, by default",
          _raises(lambda: discovery.create_question(factory, global_body, actor_id=people["lee"]),
                  "admin_required"))
    g = ada.post("/questions", json=global_body).json()["question"]
    check("an Admin can add a global question; it is Admin-controlled but not canonical",
          g["engagement_id"] is None and g["added_by_consultant_id"] == people["ada"]
          and g["admin_controlled"] and not g["canonical"] and g["seed_key"] is None)
    r1 = lee.patch(f"/questions/{g['id']}", json={"prompt": "Reworded?"})
    r2 = lee.patch(f"/questions/{g['id']}", json={"active": False})
    check("a Consultant cannot edit or deactivate a global question (403)",
          [r1.status_code, r2.status_code] == [403, 403]
          and lee.get(f"/questions/{g['id']}").json()["question"]["prompt"] == "Global question?")
    check("an engagement supplemental question is not Admin-controlled",
          sup["admin_controlled"] is False)

    sid = lee.post(f"/engagements/{eid}/sessions",
                   json={"interviewee_name": "Lee Ray"}).json()["session"]["id"]
    lee.put(f"/sessions/{sid}/answers/{ids['adj_reviewed']}", json={"answer": "no"})
    flow = {q["id"] for q in lee.get(f"/sessions/{sid}").json()["session"]["questions"]}
    sid_b = lee.post(f"/engagements/{other}/sessions",
                     json={"interviewee_name": "Sam Shift"}).json()["session"]["id"]
    lee.put(f"/sessions/{sid_b}/answers/{ids['adj_reviewed']}", json={"answer": "no"})
    flow_b = {q["id"] for q in lee.get(f"/sessions/{sid_b}").json()["session"]["questions"]}
    check("the supplemental question is asked in its engagement (behind its gate) and nowhere else",
          sup["id"] in flow and sup["id"] not in flow_b and g["id"] in flow and g["id"] in flow_b)
    check("answering it in another engagement's interview is refused (422)",
          lee.put(f"/sessions/{sid_b}/answers/{sup['id']}", json={"answer": "yes"}).status_code
          == 422)
    lee.put(f"/sessions/{sid}/answers/{sup['id']}", json={"answer": "yes"})
    check("the engagement's question list includes it; the other engagement's does not",
          sup["id"] in {q["id"] for q in lee.get(f"/questions?engagement_id={eid}").json()["questions"]}
          and sup["id"] not in {q["id"] for q in
                                lee.get(f"/questions?engagement_id={other}").json()["questions"]})

    print("\n[5. observation trace and basis]")
    obs_body = {"session_id": sid, "observation_text": "Weekend adjustments are posted unreviewed.",
                "category": "CTRL"}
    check("an unknown basis is refused (422)",
          lee.post(f"/engagements/{eid}/observations",
                   json={**obs_body, "basis": "hearsay"}).status_code == 422)
    check("a question outside the engagement is refused (422)",
          lee.post(f"/engagements/{other}/observations",
                   json={"observation_text": "x", "question_id": sup["id"]}).status_code == 422
          and lee.post(f"/engagements/{eid}/observations",
                       json={**obs_body, "question_id": "dq_missing"}).status_code == 422)
    r = lee.post(f"/engagements/{eid}/observations",
                 json={**obs_body, "question_id": sup["id"], "basis": "testimony"})
    o1 = r.json().get("observation", {})
    check("an observation records its prompting question and basis",
          r.status_code == 201 and o1["basis"] == "testimony"
          and o1["question"]["id"] == sup["id"] and o1["question"]["prompt"] == sup["prompt"])
    o2 = lee.post(f"/engagements/{eid}/observations",
                  json={"observation_text": "Adjustment report reviewed: 40% of value on weekends.",
                        "question_id": ids["adj_reviewed"], "basis": "document"}
                  ).json()["observation"]
    o3 = lee.post(f"/engagements/{eid}/observations",
                  json={"observation_text": "No basis recorded here."}).json()["observation"]
    r = lee.patch(f"/observations/{o3['id']}", json={"basis": "inferred"})
    check("basis can be set later and cleared", r.json()["observation"]["basis"] == "inferred"
          and lee.patch(f"/observations/{o3['id']}", json={"basis": None}
                        ).json()["observation"]["basis"] is None)
    check("the usage of a supplemental question is derived: answered once, in one observation",
          lee.get(f"/questions/{sup['id']}").json()["question"]["usage"]
          == {"answered": 1, "observations": 1})
    disc = lee.get(f"/engagements/{eid}/discovery").json()["discovery"]
    check("the engagement's discovery offers its questions for 'prompted by', not other engagements'",
          sup["id"] in {q["id"] for q in disc["questions"]}
          and keyed["goal_success"] not in {q["id"] for q in disc["questions"]})

    assessment = lee.get(f"/engagements/{eid}/assessment").json()["assessment"]["discovery"]
    findings = {f["trace"]["observation_id"]: f for f in assessment["findings"]}
    with factory() as s:
        n_answers = len(s.scalars(select(models.DiscoveryAnswer)
                                  .where(models.DiscoveryAnswer.engagement_id == eid)).all())
        sup_answer = s.scalars(select(models.DiscoveryAnswer).where(
            models.DiscoveryAnswer.session_id == sid,
            models.DiscoveryAnswer.question_id == sup["id"])).one()
    check("answers never become findings: one finding per observation, none per answer",
          len(findings) == 3 and n_answers >= 5)
    f1, f2 = findings[o1["id"]], findings[o2["id"]]
    check("a finding traces to the question and, in its interview, to the answer's prompt snapshot",
          f1["trace"]["question_id"] == sup["id"] and f1["trace"]["answer_id"] == sup_answer.id
          and f1["trace"]["question_prompt"] == sup_answer.question_prompt_snapshot)
    check("outside an interview, the trace names the question's current prompt and no answer",
          f2["trace"]["question_id"] == ids["adj_reviewed"] and f2["trace"]["answer_id"] is None
          and f2["trace"]["question_prompt"] == d.BY_KEY["adj_reviewed"]["question"])
    check("the finding quotes the observation, never the answer text",
          f1["statement"] == obs_body["observation_text"] and "yes" != f1["statement"])
    check("each finding carries its basis as recorded",
          (f1["basis"], f2["basis"], findings[o3["id"]]["basis"]) == ("testimony", "document", None))
    check("discovery findings still have no evidence or recommendation fields (C4)",
          not any(k in f1 for k in ("recommendation_eligible", "review_status", "reliability",
                                    "claim_scope")))

    report = lee.get(f"/engagements/{eid}/final-report").json()
    md = report["markdown"]
    check("the Final Report shows each basis and says which findings rest on testimony or "
          "inference", "Basis: Client testimony" in md
          and "Basis: Document or system record reviewed by the consultant" in md
          and "Basis: Basis not recorded" in md
          and "1 discovery finding rest on client testimony or consultant inference only." in md
          and "1 discovery finding have no recorded basis." in md)
    check("the Final Report still states that discovery is not evidence",
          "not reviewed evidence" in md)
    from peak.reports.final_report_docx import render_final_report_docx
    from peak.reports.final_report_html import render_final_report_html
    from peak.reports.final_report import FinalReport
    from peak.workspace import artifacts
    rebuilt = artifacts._build(FinalReport, report["report"])
    html = render_final_report_html(rebuilt)
    docx = render_final_report_docx(rebuilt)
    check("the web and DOCX renditions show the basis",
          "Basis: Client testimony" in (html if isinstance(html, str) else html.decode())
          and _docx_has(docx, "Basis: Client testimony"))

    print("\n[6. governance]")
    pairs = {k: v for k, v in allowlist.WORKSPACE_WRITE_COLUMNS.items()
             if k[0].startswith("discovery_")}
    check("no discovery delete action; no forbidden column; no generic writer path",
          not any("delete" in act for _, act in pairs)
          and not any(cols & allowlist.WORKSPACE_FORBIDDEN_COLUMNS for cols in pairs.values())
          and not any(allowlist.is_allowed_table(t) for t in
                      allowlist.DISCOVERY_RECORD_TABLES | {"discovery_questions"}))
    check("engagement and author are create-only; seed_key is never an update column",
          not pairs[("discovery_questions", "update_discovery_question")]
          & {"engagement_id", "added_by_consultant_id", "seed_key"})
    check("artifact immutability models unchanged (seven insert-only tables)",
          len(models._IMMUTABLE_ARTIFACT_MODELS) == 7)


def _raises(fn, expected_code):
    from peak.workspace import WorkspaceError

    try:
        fn()
    except WorkspaceError as exc:
        return exc.code == expected_code
    return False


def _anchor(factory, client_id):
    from peak.db import models

    with factory() as s:
        s.add(models.Engagement(id="eng_anchor_216", client_id=client_id, engagement_label="Anchor",
                                owner_id="peak_internal_admin",
                                authorization_scope="internal_peak_only"))
        s.commit()
    return True


def _docx_has(data, text):
    import zipfile

    with zipfile.ZipFile(io.BytesIO(data)) as z:
        return text in z.read("word/document.xml").decode("utf-8")


def main() -> int:
    print("Peak Phase 216 discovery instrument check")
    print("=" * 44)
    try:
        import argon2, fastapi, httpx, itsdangerous, sqlalchemy  # noqa: F401,E401
    except ImportError:
        print("  [skip] web dependencies not installed — run with PYTHON=.venv/bin/python")
        return 0
    with tempfile.TemporaryDirectory(prefix="peak_phase216_") as tmp:
        instrument_checks()
        migration_checks(tmp)
        app_checks(tmp)
    doc = os.path.join(REPO_ROOT, "docs/PHASE216_DISCOVERY_INSTRUMENT.md")
    check("the Phase 216 record exists", os.path.exists(doc))

    print("\nSummary")
    print(f"  failures : {len(_failures)}")
    print("RESULT: " + ("PASS" if not _failures else "FAIL"))
    return 0 if not _failures else 1


if __name__ == "__main__":
    sys.exit(main())
