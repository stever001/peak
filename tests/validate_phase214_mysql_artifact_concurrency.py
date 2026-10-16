#!/usr/bin/env python3
"""Phase 214 real-MySQL concurrency check: Final Approver reassignment vs the final decision.

The Phase 213 cutover prerequisite. Two independent connections race on one engagement against a
**live MySQL 8.x server**; a third connection watches InnoDB so the blocking is observed, not
inferred from rendered SQL:

- Scenario A: a final decision (approve, then reject) holds the engagement ``FOR UPDATE`` lock; a
  reassignment waits on that lock, resumes after the decision commits, and is refused
  (``final_decision_recorded``).
- Scenario B: a reassignment holds the lock; the old designee's final decision waits, resumes after
  the reassignment commits, and is refused (``not_designated_final_approver``). The new designee is
  then the only consultant who can decide.

Holding the lock: transaction 1 is paused in ``before_commit``, after its locking read and checks
and before its commit, while transaction 2 is started. The pause is released only once
``performance_schema.data_lock_waits`` shows transaction 2's connection waiting on transaction 1's
connection for the ``engagements`` row.

Setup runs against a **disposable server only**: the URL must name a loopback host. The script
creates the schema and two users, applies the real migrations ``alembic upgrade head`` (so 018/019
run on MySQL too), gives the runtime user exactly the production runtime grants (SELECT, INSERT on
the schema; UPDATE on clients, engagements and the four discovery tables; no DELETE), then drops
everything it created. The schema is named ``peak_lab`` and the migration user ``peak_lab_migrate``
because the Phase 84 migration target guard accepts only that identity for a non-production
MySQL target; the loopback check is what keeps this off the managed lab.

Usage:
    PEAK_PHASE214_MYSQL_SERVER_URL=mysql+pymysql://root@127.0.0.1:33214/ \\
        .venv/bin/python tests/validate_phase214_mysql_artifact_concurrency.py

Exit status: 0 all checks passed; 1 a check failed; 2 refused to run.
"""

from __future__ import annotations

import os
import secrets
import subprocess
import sys
import threading
import time

REPO_ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
for _p in (REPO_ROOT, os.path.join(REPO_ROOT, "tools")):
    if _p not in sys.path:
        sys.path.insert(0, _p)

SERVER_URL_ENV = "PEAK_PHASE214_MYSQL_SERVER_URL"
LOOPBACK = {"127.0.0.1", "localhost", "::1"}
SCHEMA = "peak_lab"  # the only non-production identity the migration target guard accepts
MIGRATE_USER = "peak_lab_migrate"
RUNTIME_USER = "peak_p214_runtime"
#: The production runtime grants recorded in Phase 205/207, reproduced exactly.
RUNTIME_UPDATE_TABLES = ("clients", "engagements", "discovery_questions", "discovery_sessions",
                         "discovery_answers", "discovery_observations")
ARTIFACT_TABLES = ("artifacts", "artifact_versions", "artifact_release_packages",
                   "artifact_renditions", "artifact_approvals",
                   "artifact_final_approver_designations", "artifact_releases")
PASSWORD = "synthetic-password-214"
SECRET = "synthetic-secret-214-" + "x" * 32
WAIT_TIMEOUT = 15.0

_failures = []


def check(label, ok):
    print(f"  [{'PASS' if ok else 'FAIL'}] {label}")
    if not ok:
        _failures.append(label)


def _server():
    from sqlalchemy.engine import make_url

    raw = os.environ.get(SERVER_URL_ENV)
    if not raw:
        sys.exit(f"refused: set {SERVER_URL_ENV} to a disposable loopback MySQL server URL")
    url = make_url(raw)
    if url.get_backend_name() != "mysql" or url.host not in LOOPBACK:
        print(f"refused: {SERVER_URL_ENV} must be a mysql URL on a loopback host")
        sys.exit(2)
    return url.set(database=None)


def _setup(admin, server):
    """Create the schema and users; return (migration URL, runtime URL). Refuses an existing schema."""
    from sqlalchemy import text

    with admin.connect() as c:
        version = c.execute(text("SELECT VERSION()")).scalar()
        if c.execute(text("SELECT COUNT(*) FROM information_schema.schemata WHERE schema_name = :s"),
                     {"s": SCHEMA}).scalar():
            print(f"refused: schema {SCHEMA} already exists on this server; use a fresh server")
            sys.exit(2)
    migrate_pw, runtime_pw = secrets.token_hex(16), secrets.token_hex(16)
    with admin.begin() as c:
        c.execute(text(f"CREATE DATABASE `{SCHEMA}` CHARACTER SET utf8mb4"))
        for user, pw in ((MIGRATE_USER, migrate_pw), (RUNTIME_USER, runtime_pw)):
            c.execute(text(f"CREATE USER '{user}'@'%' IDENTIFIED BY '{pw}'"))
        c.execute(text(f"GRANT ALL ON `{SCHEMA}`.* TO '{MIGRATE_USER}'@'%'"))
    url = server.set(database=SCHEMA, query={"charset": "utf8mb4"})
    return (version, url.set(username=MIGRATE_USER, password=migrate_pw),
            url.set(username=RUNTIME_USER, password=runtime_pw))


def _grant_runtime(admin):
    from sqlalchemy import text

    with admin.begin() as c:
        c.execute(text(f"GRANT SELECT, INSERT ON `{SCHEMA}`.* TO '{RUNTIME_USER}'@'%'"))
        for table in RUNTIME_UPDATE_TABLES:
            c.execute(text(f"GRANT UPDATE ON `{SCHEMA}`.`{table}` TO '{RUNTIME_USER}'@'%'"))


def _teardown(admin):
    from sqlalchemy import text

    with admin.begin() as c:
        c.execute(text(f"DROP DATABASE IF EXISTS `{SCHEMA}`"))
        for user in (MIGRATE_USER, RUNTIME_USER):
            c.execute(text(f"DROP USER IF EXISTS '{user}'@'%'"))


def _migrate(migrate_url):
    env = {k: v for k, v in os.environ.items() if not k.startswith("PEAK_")}
    env.update(PEAK_DATABASE_URL=migrate_url.render_as_string(hide_password=False),
               PEAK_ALEMBIC_TARGET="lab", PEAK_LAB_MIGRATION_CONFIRM="1")
    run = lambda *a: subprocess.run([sys.executable, "-m", "alembic", *a], cwd=REPO_ROOT,  # noqa: E731
                                    env=env, capture_output=True, text=True)
    up = run("upgrade", "head")
    if up.returncode != 0:
        print(up.stderr[-2000:])
    return up.returncode == 0, run("current").stdout.strip()


class Race:
    """Transaction 1 pauses before commit while transaction 2 runs on its own connection."""

    def __init__(self, url):
        from sqlalchemy import create_engine, event
        from sqlalchemy.orm import sessionmaker

        self.engines = [create_engine(url, pool_size=1, max_overflow=0) for _ in range(2)]
        self.factories = [sessionmaker(bind=e, expire_on_commit=False) for e in self.engines]
        self.conn_ids = [set(), set()]
        for i, e in enumerate(self.engines):
            event.listen(e, "connect", lambda dbapi, rec, i=i: self.conn_ids[i].add(dbapi.thread_id()))
        self.paused, self.go = threading.Event(), threading.Event()
        self.pause_armed = True

        def hold(session):
            if self.pause_armed:
                self.pause_armed = False
                self.paused.set()
                self.go.wait(WAIT_TIMEOUT)
        event.listen(self.factories[0], "before_commit", hold)

    def run(self, monitor, first, second):
        """Run ``first(factory)`` holding the lock, then ``second(factory)``; return the evidence."""
        out = [{}, {}]

        def call(i, fn):
            try:
                out[i]["result"] = fn(self.factories[i])
            except Exception as exc:  # noqa: BLE001 — the refusal is the expected outcome
                out[i]["error"] = exc
            out[i]["done_at"] = time.monotonic()

        t1 = threading.Thread(target=call, args=(0, first))
        t1.start()
        held = self.paused.wait(WAIT_TIMEOUT)
        t2 = threading.Thread(target=call, args=(1, second))
        t2.start()
        wait = _await_lock_wait(monitor, self.conn_ids[1], self.conn_ids[0])
        time.sleep(0.5)
        second_blocked = t2.is_alive()
        released_at = time.monotonic()
        self.go.set()
        t1.join(WAIT_TIMEOUT)
        t2.join(WAIT_TIMEOUT + 60)
        for e in self.engines:
            e.dispose()
        return {"held": held, "wait": wait, "second_blocked": second_blocked,
                "released_at": released_at, "first": out[0], "second": out[1]}


def _await_lock_wait(monitor, requesters, blockers):
    """Poll InnoDB until a requester connection waits on a blocker connection's engagements lock."""
    from sqlalchemy import text

    q = text("""
        SELECT rt.PROCESSLIST_ID AS requester, bt.PROCESSLIST_ID AS blocker,
               rl.OBJECT_NAME AS object_name, rl.LOCK_MODE AS mode, bl.LOCK_MODE AS held_mode
        FROM performance_schema.data_lock_waits w
        JOIN performance_schema.data_locks rl ON rl.ENGINE_LOCK_ID = w.REQUESTING_ENGINE_LOCK_ID
        JOIN performance_schema.data_locks bl ON bl.ENGINE_LOCK_ID = w.BLOCKING_ENGINE_LOCK_ID
        JOIN performance_schema.threads rt ON rt.THREAD_ID = w.REQUESTING_THREAD_ID
        JOIN performance_schema.threads bt ON bt.THREAD_ID = w.BLOCKING_THREAD_ID""")
    deadline = time.monotonic() + WAIT_TIMEOUT
    while time.monotonic() < deadline:
        with monitor.connect() as c:
            for row in c.execute(q).mappings():
                if row["requester"] in requesters and row["blocker"] in blockers:
                    return dict(row)
        time.sleep(0.05)
    return None


def _report_race(ev, expected_code):
    first, second = ev["first"], ev["second"]
    check("transaction 1 took the engagement lock and paused before commit", ev["held"])
    w = ev["wait"]
    check("InnoDB shows transaction 2's connection waiting on transaction 1's connection",
          w is not None)
    check("the contended lock is an exclusive lock on the engagements row",
          w is not None and w["object_name"] == "engagements"
          and w["mode"].startswith("X") and w["held_mode"].startswith("X"))
    check("transaction 2 was still blocked while transaction 1 held the lock", ev["second_blocked"])
    check("transaction 1 committed successfully",
          "error" not in first and first.get("result") is not None)
    err = second.get("error")
    check(f"transaction 2 resumed only after the release and was refused ({expected_code})",
          second.get("done_at", 0) > ev["released_at"]
          and getattr(err, "code", None) == expected_code)
    if err is not None and getattr(err, "code", None) != expected_code:
        print(f"      transaction 2 raised {type(err).__name__}: {getattr(err, 'code', err)}")


def scenarios(runtime_url, monitor):
    from fastapi.testclient import TestClient
    from sqlalchemy import select

    from peak import accounts
    from peak.consultant_api.app import create_app
    from peak.db.models import ArtifactApproval, ArtifactFinalApproverDesignation
    from peak.db.session import create_session_factory
    from peak.workspace import approvals as ap
    import init_discovery_questions as init

    factory = create_session_factory(url=runtime_url)
    init.initialize(factory)
    people = {}
    for key, name, role in (("lee", "Lee Lead", "consultant"), ("fran", "Fran Final", "consultant"),
                            ("sam", "Sam Second", "consultant"), ("ada", "Ada Admin", "admin")):
        people[key] = accounts.create_consultant(factory, name=name, email=f"{key}@example.com",
                                                 role=role, password=PASSWORD)["id"]
    app = create_app(session_factory=factory, secret_key=SECRET, secure_cookie=True)
    c = {}
    for key in people:
        c[key] = TestClient(app, base_url="https://testserver")
        c[key].post("/auth/login", json={"email": f"{key}@example.com", "password": PASSWORD})
    lee, ada = c["lee"], c["ada"]
    client_id = lee.post("/clients", json={"organization_label": "Synthetic Co 214"}
                         ).json()["client"]["id"]

    def through_designation(label):
        """An engagement whose package has the Lead approval and Fran as Final Approver."""
        eid = ada.post("/engagements", json={"client_id": client_id, "engagement_label": label,
                                             "current_phase": "Assessment",
                                             "assigned_consultant_id": people["lee"]}
                       ).json()["engagement"]["id"]
        lee.patch(f"/engagements/{eid}/north-star", json={"north_star": f"North Star {label}"})
        lee.post(f"/engagements/{eid}/observations",
                 json={"observation_text": f"Cycle counts lag in {label}."})
        p = lee.post(f"/engagements/{eid}/final-report/packages").json()["package"]
        lead = lee.post(f"/release-packages/{p['id']}/lead-approval",
                        json={"decision": "approved", "package_hash": p["package_hash"],
                              "reviewed_rendition": "web"})
        des = lee.post(f"/release-packages/{p['id']}/final-approver",
                       json={"consultant_id": people["fran"]})
        ok = lead.status_code == 200 and des.status_code == 200
        return p, ok

    def final(pid, h, decision, who):
        return lambda f: ap.record_final_decision(f, pid, decision, h, "web", None, people[who])

    def reassign(pid, to):
        return lambda f: ap.designate_final_approver(f, pid, people[to], people["lee"])

    def stored(pid):
        with factory() as s:
            approvals = list(s.scalars(select(ArtifactApproval).where(
                ArtifactApproval.release_package_id == pid)))
            designations = list(s.scalars(select(ArtifactFinalApproverDesignation).where(
                ArtifactFinalApproverDesignation.release_package_id == pid)
                .order_by(ArtifactFinalApproverDesignation.designation_number)))
        return approvals, designations

    for decision in ("approved", "rejected"):
        print(f"\n[Scenario A ({decision}): the final decision holds the lock; "
              "a reassignment waits]")
        p, ok = through_designation(f"A {decision}")
        check("fixture: package prepared, Lead-approved, Fran designated (through the API)", ok)
        ev = Race(runtime_url).run(monitor, final(p["id"], p["package_hash"], decision, "fran"),
                                   reassign(p["id"], "sam"))
        _report_race(ev, "final_decision_recorded")
        approvals, designations = stored(p["id"])
        finals = [a for a in approvals if a.approval_level == ap.FINAL]
        check("stored: one final decision, by Fran, bound to Fran's designation; no reassignment",
              len(finals) == 1 and finals[0].approver_consultant_id == people["fran"]
              and finals[0].decision == decision
              and [d.designated_consultant_id for d in designations] == [people["fran"]]
              and finals[0].designation_id == designations[0].id)

    for decision in ("approved", "rejected"):
        print(f"\n[Scenario B ({decision}): a reassignment holds the lock; "
              "the old designee's final decision waits]")
        p, ok = through_designation(f"B {decision}")
        check("fixture: package prepared, Lead-approved, Fran designated (through the API)", ok)
        ev = Race(runtime_url).run(monitor, reassign(p["id"], "sam"),
                                   final(p["id"], p["package_hash"], decision, "fran"))
        _report_race(ev, "not_designated_final_approver")
        approvals, designations = stored(p["id"])
        check("stored: the reassignment to Sam committed; no final decision by Fran",
              [d.designated_consultant_id for d in designations] == [people["fran"], people["sam"]]
              and not [a for a in approvals if a.approval_level == ap.FINAL])
        try:
            final(p["id"], p["package_hash"], decision, "fran")(factory)
            fran_code = None
        except ap.WorkspaceError as exc:
            fran_code = exc.code
        check("Fran (old designee) is still refused afterwards",
              fran_code == "not_designated_final_approver")
        result = final(p["id"], p["package_hash"], decision, "sam")(factory)
        approvals, designations = stored(p["id"])
        finals = [a for a in approvals if a.approval_level == ap.FINAL]
        check("Sam (new designee) is the only valid Final Approver: the decision is recorded "
              "against Sam's designation",
              result is not None and len(finals) == 1
              and finals[0].approver_consultant_id == people["sam"]
              and finals[0].designation_id == designations[-1].id)


def grant_checks(runtime_url):
    """The production runtime grants suffice for the lock and refuse artifact UPDATE/DELETE."""
    from sqlalchemy import create_engine, text
    from sqlalchemy.exc import OperationalError, ProgrammingError

    print("\n[the production runtime grants, reproduced on the disposable server]")
    engine = create_engine(runtime_url)

    def denied(sql):
        try:
            with engine.begin() as c:
                c.execute(text(sql))
        except (OperationalError, ProgrammingError) as exc:
            return exc.orig.args[0] == 1142  # ER_TABLEACCESS_DENIED_ERROR
        return False

    with engine.begin() as c:
        c.execute(text("SELECT id FROM engagements LIMIT 1 FOR UPDATE"))
    check("SELECT ... FOR UPDATE on engagements succeeds with UPDATE on engagements", True)
    check("UPDATE is refused by the database on every artifact table",
          all(denied(f"UPDATE `{t}` SET id = id WHERE 1 = 0") for t in ARTIFACT_TABLES))
    check("DELETE is refused by the database on every artifact table",
          all(denied(f"DELETE FROM `{t}` WHERE 1 = 0") for t in ARTIFACT_TABLES))
    engine.dispose()


def main() -> int:
    from sqlalchemy import create_engine

    server = _server()
    admin = create_engine(server)
    version, migrate_url, runtime_url = _setup(admin, server)
    try:
        print(f"[disposable MySQL server: {version}, loopback]")
        check("the server is MySQL 8.x", version.startswith("8."))
        migrated, current = _migrate(migrate_url)
        check("alembic upgrade head applies every migration (017 -> 018 -> 019 and later) on MySQL",
              migrated and current.endswith("(head)"))
        if not migrated:
            return 1
        _grant_runtime(admin)
        scenarios(runtime_url, admin)
        grant_checks(runtime_url)
    finally:
        admin.dispose()
        _teardown(create_engine(server))
    print(f"\n{'PASS' if not _failures else 'FAIL'}: {len(_failures)} failure(s)")
    return 1 if _failures else 0


if __name__ == "__main__":
    sys.exit(main())
