#!/usr/bin/env python3
"""Phase 204 discovery / interview workflow check (offline; temporary SQLite only).

Proves, through the consultant API over ``peak.workspace.discovery``:

1. the engagement North Star persists;
2. an interview can start, save, resume and complete (then becomes read-only);
3. answers persist (yes/no normalized, invalid choices refused);
4. a branch shows or hides its follow-up deterministically;
5. observations persist, with 6. low-hanging-fruit, effort and value;
7. the question pool can add, edit and deactivate (with branch rules validated);
8. historical answers survive a question being edited or deactivated;
9. callers cannot set governance or identity fields, and discovery records carry the stamp.

Plus migration 017 structure, the idempotent question initializer, and allowlist narrowness.
No network, no credential, no client data.

Exit status: 0 all checks passed; 1 a check failed.
"""

from __future__ import annotations

import os
import shutil
import sqlite3
import subprocess
import sys
import tempfile

REPO_ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
if REPO_ROOT not in sys.path:
    sys.path.insert(0, REPO_ROOT)

_failures = []
SECRET = "phase204-test-secret-" + "x" * 32
PASSWORD = "consultant-pw-204"


def check(label, ok):
    print(f"  [{'PASS' if ok else 'FAIL'}] {label}")
    if not ok:
        _failures.append(label)


def migration_checks(tmp):
    print("\n[migration 017]")
    db = os.path.join(tmp, "migrate.sqlite3")
    env = {k: v for k, v in os.environ.items() if not k.startswith("PEAK_")}
    env["PEAK_DATABASE_URL"] = f"sqlite:///{db}"

    def alembic(*args):
        return subprocess.run([sys.executable, "-m", "alembic", *args], cwd=REPO_ROOT, env=env,
                              capture_output=True, text=True).returncode

    up = alembic("upgrade", "017_discovery_workflow")
    con = sqlite3.connect(db)
    tables = {r[0] for r in con.execute("SELECT name FROM sqlite_master WHERE type='table'")}
    eng_cols = {r[1] for r in con.execute("PRAGMA table_info(engagements)")}
    con.close()
    check("upgrade to 017 adds the four discovery tables and the North Star columns",
          up == 0 and {"discovery_questions", "discovery_sessions", "discovery_answers",
                       "discovery_observations"} <= tables
          and {"north_star", "north_star_context"} <= eng_cols)
    down = alembic("downgrade", "016_client_engagement_workspace_fields")
    con = sqlite3.connect(db)
    tables = {r[0] for r in con.execute("SELECT name FROM sqlite_master WHERE type='table'")}
    con.close()
    check("downgrade to 016 removes them", down == 0 and "discovery_sessions" not in tables)
    src = open(os.path.join(REPO_ROOT, "alembic/versions/017_discovery_workflow.py")).read().lower()
    check("migration 017 carries no data (no INSERT, no seed)",
          "insert into" not in src and "bulk_insert" not in src and "op.execute(" not in src)


def allowlist_checks():
    print("\n[workspace allowlist]")
    from peak.persistence import allowlist as a

    pairs = {k: v for k, v in a.WORKSPACE_WRITE_COLUMNS.items()
             if k[0].startswith("discovery_") or k[1] == "set_engagement_north_star"}
    check("ten discovery write actions, none a delete, none touching a forbidden column",
          len(pairs) == 10 and not any("delete" in act for _, act in pairs)
          and not any(cols & a.WORKSPACE_FORBIDDEN_COLUMNS for cols in pairs.values()))
    check("no discovery update action can change identity or engagement links",
          not any(cols & {"id", "client_id", "engagement_id", "session_id", "question_id",
                          "conducted_by_consultant_id", "recorded_by_consultant_id", "seed_key"}
                  for (t, act), cols in pairs.items() if act.startswith("update")))
    check("discovery tables stay off the generic controlled-writer path",
          not any(a.is_allowed_table(t) for t in a.DISCOVERY_RECORD_TABLES | {"discovery_questions"}))


def api_checks(factory, tmp):
    from fastapi.testclient import TestClient
    from sqlalchemy import select

    sys.path.insert(0, os.path.join(REPO_ROOT, "tools"))
    import init_discovery_questions as init

    from peak import accounts
    from peak.consultant_api.app import create_app
    from peak.db.models import (
        DiscoveryAnswer, DiscoveryObservation, DiscoveryQuestion, DiscoverySession, Engagement,
    )

    me = accounts.create_consultant(factory, name="Casey Consultant", email="casey@example.com",
                                    role="consultant", password=PASSWORD)
    app = create_app(session_factory=factory, secret_key=SECRET, secure_cookie=True)
    anon = TestClient(app, base_url="https://testserver")
    c = TestClient(app, base_url="https://testserver")
    c.post("/auth/login", json={"email": "casey@example.com", "password": PASSWORD})
    check("unauthenticated question and discovery access -> 401",
          anon.get("/questions").status_code == 401
          and anon.get("/engagements/x/discovery").status_code == 401)

    print("\n[question pool initialization]")
    import io
    from contextlib import redirect_stdout
    with redirect_stdout(io.StringIO()):
        dry = init.main([], session_factory=factory)
    check("dry run writes nothing", dry == 0 and not c.get("/questions").json()["questions"])
    first = init.initialize(factory)
    second = init.initialize(factory)
    questions = c.get("/questions").json()["questions"]
    check(f"initializer creates the pool once ({first['created']} questions), then is a no-op",
          20 <= first["created"] <= 35 and second == {"created": 0,
                                                      "already_present": first["created"]}
          and len(questions) == first["created"])
    with factory() as s:
        ids = dict(s.execute(select(DiscoveryQuestion.seed_key, DiscoveryQuestion.id)).all())

    cid = c.post("/clients", json={"organization_label": "Acme Logistics", "key_personnel": [
        {"name": "Lee Ray", "role": "Warehouse lead", "email": None, "phone": None}]}).json()["client"]["id"]
    eid = c.post("/engagements", json={"client_id": cid, "engagement_label": "Inventory review"}
                 ).json()["engagement"]["id"]

    print("\n[1] North Star")
    r = c.patch(f"/engagements/{eid}/north-star",
                json={"north_star": "Reduce inventory discrepancies",
                      "north_star_context": "Counts disagree with the system weekly."})
    d = c.get(f"/engagements/{eid}/discovery").json()["discovery"]
    check("North Star and context persist",
          r.status_code == 200 and d["north_star"] == "Reduce inventory discrepancies"
          and d["north_star_context"].startswith("Counts") and d["discovery_enabled"])
    check("key personnel are offered for choosing an interviewee",
          d["key_personnel"][0]["name"] == "Lee Ray")

    print("\n[2-4] interview, answers, branching")
    r = c.post(f"/engagements/{eid}/sessions",
               json={"interviewee_name": "Lee Ray", "interviewee_title": "Warehouse lead"})
    sess = r.json()["session"]
    sid = sess["id"]
    shown = {q["id"] for q in sess["questions"]}
    check("an interview starts in progress, conducted by the signed-in consultant",
          r.status_code == 201 and sess["status"] == "in_progress"
          and sess["conducted_by"] == "Casey Consultant")
    check("branch follow-ups are hidden until their question is answered",
          ids["cc_performed"] in shown and ids["cc_frequency"] not in shown
          and ids["cc_why_not"] not in shown)
    c.put(f"/sessions/{sid}/answers/{ids['cc_performed']}", json={"answer": "No"})
    shown = {q["id"] for q in c.get(f"/sessions/{sid}").json()["session"]["questions"]}
    check("'No' shows the not-performed follow-up and hides the frequency one",
          ids["cc_why_not"] in shown and ids["cc_frequency"] not in shown)
    c.put(f"/sessions/{sid}/answers/{ids['cc_performed']}", json={"answer": "yes"})
    shown = {q["id"] for q in c.get(f"/sessions/{sid}").json()["session"]["questions"]}
    check("changing to 'yes' swaps the follow-ups deterministically",
          ids["cc_frequency"] in shown and ids["cc_why_not"] not in shown)
    check("answering a hidden follow-up is refused (422)",
          c.put(f"/sessions/{sid}/answers/{ids['cc_why_not']}", json={"answer": "x"}).status_code
          == 422)
    c.put(f"/sessions/{sid}/answers/{ids['goal_success']}", json={"answer": "Trustworthy counts."})
    c.put(f"/sessions/{sid}/answers/{ids['cc_frequency']}", json={"answer": "Weekly"})
    check("an answer outside a single-choice list is refused (422)",
          c.put(f"/sessions/{sid}/answers/{ids['acc_confidence']}",
                json={"answer": "Unsure"}).status_code == 422)
    resumed = {q["id"]: q["answer"] for q in c.get(f"/sessions/{sid}").json()["session"]["questions"]}
    check("resuming shows saved answers (yes/no stored normalized)",
          resumed[ids["cc_performed"]] == "yes" and resumed[ids["goal_success"]] == "Trustworthy counts."
          and resumed[ids["cc_frequency"]] == "Weekly")

    print("\n[5-6] observations and low-hanging fruit")
    r = c.post(f"/engagements/{eid}/observations",
               json={"session_id": sid, "category": "Cycle counting",
                     "observation_text": "Counts are skipped during peak weeks.",
                     "low_hanging_fruit": True, "estimated_effort": "low",
                     "estimated_value": "high"})
    obs = r.json()["observation"]
    check("an observation persists with low-hanging fruit, effort, value and its interview",
          r.status_code == 201 and obs["low_hanging_fruit"] is True
          and obs["estimated_effort"] == "low" and obs["estimated_value"] == "high"
          and obs["session"]["id"] == sid and obs["recorded_by"] == "Casey Consultant")
    r = c.patch(f"/observations/{obs['id']}", json={"estimated_value": "medium",
                                                   "low_hanging_fruit": False})
    check("editing an observation persists", r.status_code == 200
          and r.json()["observation"]["estimated_value"] == "medium"
          and r.json()["observation"]["low_hanging_fruit"] is False)
    check("an invalid effort level is refused (422)",
          c.patch(f"/observations/{obs['id']}", json={"estimated_effort": "huge"}).status_code == 422)

    print("\n[9] governance and identity")
    check("a caller cannot set owner/scope or the conducting/recording consultant (422)",
          c.post(f"/engagements/{eid}/sessions", json={"interviewee_name": "X",
                                                       "owner_id": "x"}).status_code == 422
          and c.post(f"/engagements/{eid}/sessions", json={
              "interviewee_name": "X", "conducted_by_consultant_id": "cons_x"}).status_code == 422
          and c.post(f"/engagements/{eid}/observations", json={
              "observation_text": "X", "recorded_by_consultant_id": "cons_x"}).status_code == 422
          and c.patch(f"/observations/{obs['id']}", json={"authorization_scope": "x"}).status_code
          == 422
          and c.patch(f"/engagements/{eid}/north-star", json={"owner_id": "x"}).status_code == 422)
    with factory() as s:
        rows = [s.get(DiscoverySession, sid), s.get(DiscoveryObservation, obs["id"]),
                s.scalars(select(DiscoveryAnswer).where(DiscoveryAnswer.session_id == sid)).first()]
        stamped = all(r.owner_id == "peak_consultants"
                      and r.authorization_scope == "engagement_authorized"
                      and r.engagement_id == eid and r.client_id == cid for r in rows)
        conducted = rows[0].conducted_by_consultant_id == me["id"]
    check("sessions, answers and observations carry the stamp and the engagement identity",
          stamped and conducted)
    with factory() as s:
        s.add(Engagement(id="eng_anchor_test", client_id=cid, engagement_label="Anchor",
                         owner_id="peak_internal_admin", authorization_scope="internal_peak_only"))
        s.commit()
    check("discovery refuses an engagement without the workspace stamp (422)",
          c.post("/engagements/eng_anchor_test/sessions",
                 json={"interviewee_name": "X"}).status_code == 422
          and c.patch("/engagements/eng_anchor_test/north-star",
                      json={"north_star": "X"}).status_code == 422)

    print("\n[7] question pool")
    r = c.post("/questions", json={"prompt": "Which shift has the most adjustments?",
                                   "category": "Labor / workflow", "answer_type": "single_choice",
                                   "choices": ["Day", "Night", "Weekend"]})
    new_q = r.json()["question"]
    check("a question can be added (appended to the end of the pool)",
          r.status_code == 201 and new_q["active"] and new_q["display_order"] > max(
              q["display_order"] for q in questions))
    r = c.patch(f"/questions/{new_q['id']}", json={"prompt": "Which shift records the most adjustments?"})
    check("a question can be edited", r.status_code == 200
          and r.json()["question"]["prompt"].startswith("Which shift records"))
    check("a branch on a later question, or with an impossible value, is refused (422)",
          c.patch(f"/questions/{ids['goal_success']}", json={"branch": {
              "question_id": new_q["id"], "operator": "equals", "value": "Day"}}).status_code == 422
          and c.post("/questions", json={"prompt": "X?", "category": "X", "answer_type": "short_text",
                                         "branch": {"question_id": ids["cc_performed"],
                                                    "operator": "equals", "value": "maybe"}}
                     ).status_code == 422)
    check("an arbitrary branch operator is refused (422)",
          c.post("/questions", json={"prompt": "X?", "category": "X", "answer_type": "short_text",
                                     "branch": {"question_id": ids["cc_performed"],
                                                "operator": "contains", "value": "yes"}}
                 ).status_code == 422)

    print("\n[8] history survives question edits and deactivation")
    c.post(f"/sessions/{sid}/complete")
    done = c.get(f"/sessions/{sid}").json()["session"]
    check("completing makes the interview read-only (answers then refused, 422)",
          done["status"] == "completed" and done["completed_at"]
          and c.put(f"/sessions/{sid}/answers/{ids['goal_pain']}",
                    json={"answer": "x"}).status_code == 422)
    c.patch(f"/questions/{ids['goal_success']}", json={"prompt": "Reworded success question?"})
    c.patch(f"/questions/{ids['goal_success']}", json={"active": False})
    after = c.get(f"/sessions/{sid}").json()["session"]
    check("a deactivated question leaves the flow but its answer stays, with the original prompt",
          ids["goal_success"] not in {q["id"] for q in after["questions"]}
          and any(h["question_id"] == ids["goal_success"] and h["answer"] == "Trustworthy counts."
                  and h["prompt"] == "What outcome would make this engagement clearly successful?"
                  for h in after["history"]))
    check("the question is deactivated, not deleted, and can be reactivated",
          c.patch(f"/questions/{ids['goal_success']}", json={"active": True}).json()["question"]["active"]
          and len(c.get("/questions").json()["questions"]) == len(questions) + 1)


def main() -> int:
    print("Peak Phase 204 discovery / interview workflow check")
    print("=" * 52)
    try:
        import argon2, fastapi, httpx, itsdangerous, sqlalchemy  # noqa: F401,E401
    except ImportError:
        print("  [skip] web dependencies not installed — run with PYTHON=.venv/bin/python after "
              "pip install -r requirements-web.txt for the full check")
        return 0
    import peak.db.models  # noqa: F401  (registers models on Base.metadata)
    from peak.db.base import Base
    from peak.db.session import create_session_factory

    tmp = tempfile.mkdtemp(prefix="peak_phase204_")
    try:
        migration_checks(tmp)
        allowlist_checks()
        factory = create_session_factory(url=f"sqlite:///{os.path.join(tmp, 'api.sqlite3')}")
        Base.metadata.create_all(factory.kw["bind"])
        api_checks(factory, tmp)
    finally:
        shutil.rmtree(tmp, ignore_errors=True)

    print("\nSummary")
    print(f"  failures : {len(_failures)}")
    print("RESULT: " + ("PASS" if not _failures else "FAIL"))
    return 0 if not _failures else 1


if __name__ == "__main__":
    sys.exit(main())
