#!/usr/bin/env python3
"""Phase 201 consultant web authentication check (offline; temporary SQLite only).

Proves, through the thin FastAPI adapter over ``peak.accounts``:

1. unauthenticated protected access is rejected;
2. valid email/password login succeeds and sets an HttpOnly, 8-hour session cookie;
3. an Admin can list and create consultants, and a created consultant can log in;
4. a Consultant cannot administer consultants;
5. ``/auth/me`` returns the name and role the authenticated shell renders.

Plus the migration 015 structure (upgrade/downgrade on temporary SQLite) and the Admin bootstrap
tool's refusals. No network, no credential, no managed database.

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
SECRET = "phase201-test-secret-" + "x" * 32
ADMIN = {"name": "Steve Rouse", "email": "Steve@Example.com", "password": "admin-password-1"}
CONS = {"name": "Casey Consultant", "email": "casey@example.com", "role": "consultant",
        "password": "consultant-pw-1"}


def check(label, ok):
    print(f"  [{'PASS' if ok else 'FAIL'}] {label}")
    if not ok:
        _failures.append(label)


def migration_checks(tmp):
    print("\n[migration 015]")
    db = os.path.join(tmp, "migrate.sqlite3")
    env = {k: v for k, v in os.environ.items() if not k.startswith("PEAK_")}
    env["PEAK_DATABASE_URL"] = f"sqlite:///{db}"

    def alembic(*args):
        return subprocess.run([sys.executable, "-m", "alembic", *args], cwd=REPO_ROOT, env=env,
                              capture_output=True, text=True)

    up = alembic("upgrade", "015_consultants")
    check("alembic upgrade to 015_consultants succeeds on temporary SQLite", up.returncode == 0)
    con = sqlite3.connect(db)
    cols = [r[1] for r in con.execute("PRAGMA table_info(consultants)")]
    head = con.execute("SELECT version_num FROM alembic_version").fetchone()
    con.close()
    check("the database is at 015_consultants", head == ("015_consultants",))
    check("consultants has exactly id/name/email/password_hash/role/created_at",
          cols == ["id", "name", "email", "password_hash", "role", "created_at"])
    down = alembic("downgrade", "014_engagement_classification")
    con = sqlite3.connect(db)
    gone = con.execute("SELECT name FROM sqlite_master WHERE name='consultants'").fetchone()
    con.close()
    check("downgrade to 014 drops consultants", down.returncode == 0 and gone is None)
    src = open(os.path.join(REPO_ROOT, "alembic/versions/015_consultants.py")).read().lower()
    check("migration 015 carries no data (no INSERT)",
          "insert into" not in src and "bulk_insert" not in src and "op.execute(" not in src)


def api_checks(session_factory):
    from fastapi.testclient import TestClient

    from peak import accounts
    from peak.consultant_api.app import SESSION_COOKIE, create_app
    from peak.db.models import Consultant

    accounts.create_consultant(session_factory, role="admin", **ADMIN)
    app = create_app(session_factory=session_factory, secret_key=SECRET, secure_cookie=True)

    def client():
        return TestClient(app, base_url="https://testserver")

    def login(c, email, password):
        return c.post("/auth/login", json={"email": email, "password": password})

    print("\n[1] unauthenticated access")
    anon = client()
    health = anon.get("/healthz")
    check("GET /healthz -> 200 {status: ok} with no session (no config or secrets)",
          health.status_code == 200 and health.json() == {"status": "ok"})
    check("GET /auth/me without a session -> 401", anon.get("/auth/me").status_code == 401)
    check("GET /consultants without a session -> 401", anon.get("/consultants").status_code == 401)
    check("POST /consultants without a session -> 401",
          anon.post("/consultants", json=CONS).status_code == 401)
    anon.cookies.set(SESSION_COOKIE, "forged.token.value")
    check("forged session token -> 401", anon.get("/auth/me").status_code == 401)

    print("\n[2] login")
    admin = client()
    check("wrong password -> 401", login(admin, ADMIN["email"], "wrong-password!!").status_code == 401)
    check("unknown email -> 401", login(admin, "nobody@example.com", "whatever-pass").status_code == 401)
    r = login(admin, "  steve@EXAMPLE.com ", ADMIN["password"])
    cookie = r.headers.get("set-cookie", "").lower()
    check("valid login (email normalized) -> 200", r.status_code == 200)
    check("cookie is HttpOnly, SameSite=Lax, Secure, 8-hour Max-Age",
          all(x in cookie for x in ("httponly", "samesite=lax", "secure", "max-age=28800")))
    with session_factory() as s:
        stored = s.query(Consultant).one()
    check("stored email is normalized", stored.email == "steve@example.com")
    check("password stored only as an Argon2id hash",
          stored.password_hash.startswith("$argon2id$") and ADMIN["password"] not in stored.password_hash)
    token = r.json().get("token", "")
    check("expired token is rejected",
          accounts.read_session_token(token, SECRET) == stored.id
          and accounts.read_session_token(token, SECRET, max_age=-1) is None)

    print("\n[3] Admin administers consultants")
    check("Admin GET /consultants -> 200", admin.get("/consultants").status_code == 200)
    created = admin.post("/consultants", json=CONS)
    check("Admin POST /consultants -> 201 with role consultant",
          created.status_code == 201 and created.json()["consultant"]["role"] == "consultant")
    dup = admin.post("/consultants", json={**CONS, "email": "CASEY@example.com"})
    check("duplicate email (case variant) -> 409", dup.status_code == 409)
    short = admin.post("/consultants", json={**CONS, "email": "short@example.com", "password": "short"})
    check("too-short password -> 422", short.status_code == 422)
    listed = [c["email"] for c in admin.get("/consultants").json()["consultants"]]
    check("list shows both accounts", listed == ["casey@example.com", "steve@example.com"])
    check("responses never include a password hash",
          "password" not in str(admin.get("/consultants").json()))

    print("\n[4] Consultant cannot administer consultants")
    cons = client()
    check("created consultant can log in", login(cons, CONS["email"], CONS["password"]).status_code == 200)
    check("Consultant GET /consultants -> 403", cons.get("/consultants").status_code == 403)
    check("Consultant POST /consultants -> 403",
          cons.post("/consultants", json={**CONS, "email": "x@example.com"}).status_code == 403)

    print("\n[rate limit] failed sign-ins (Phase 203)")
    from peak.consultant_api.app import LoginThrottle

    now = [1000.0]
    limited = TestClient(create_app(session_factory=session_factory, secret_key=SECRET,
                                    secure_cookie=True,
                                    login_throttle=LoginThrottle(max_failures=3, window_seconds=60,
                                                                 clock=lambda: now[0])),
                         base_url="https://testserver")
    codes = [login(limited, CONS["email"], "wrong-password!!").status_code for _ in range(3)]
    check("failures below the limit stay 401", codes == [401, 401, 401])
    check("at the limit even the right password gets 429",
          login(limited, CONS["email"], CONS["password"]).status_code == 429)
    check("another email is unaffected",
          login(limited, ADMIN["email"], ADMIN["password"]).status_code == 200)
    now[0] += 61
    check("after the window the right password signs in (and clears the count)",
          login(limited, CONS["email"], CONS["password"]).status_code == 200
          and login(limited, CONS["email"], "wrong-password!!").status_code == 401)

    print("\n[5] shell identity + logout")
    me = cons.get("/auth/me")
    check("/auth/me returns name and role for the shell",
          me.status_code == 200 and me.json()["consultant"]["name"] == CONS["name"]
          and me.json()["consultant"]["role"] == "consultant")
    out = cons.post("/auth/logout")
    check("logout -> 204 and clears the session", out.status_code == 204
          and cons.get("/auth/me").status_code == 401)


def bootstrap_checks(session_factory, empty_factory):
    import io
    from contextlib import redirect_stdout

    sys.path.insert(0, os.path.join(REPO_ROOT, "tools"))
    import bootstrap_admin as tool

    from peak import accounts

    print("\n[bootstrap_admin]")
    check("production-style MySQL schema is refused",
          tool.target_label("mysql+pymysql://u:p@h:3306/peak_prod") is None)
    check("peak_lab and SQLite are the only permitted targets",
          tool.target_label("mysql+pymysql://u:p@h:3306/peak_lab") == "lab"
          and tool.target_label("sqlite:///x.sqlite3") == "local")
    prod_url = "mysql+pymysql://peak_prod_runtime:p@h:3306/defaultdb"
    check("production needs --production AND the confirmation AND a production-marked user",
          tool.target_label(prod_url, production=True, confirm="1") == "production"
          and tool.target_label(prod_url, production=True, confirm="") is None
          and tool.target_label(prod_url, production=True, confirm="true") is None
          and tool.target_label("mysql+pymysql://someone:p@h:3306/defaultdb",
                                production=True, confirm="1") is None)
    check("--production refuses lab and local targets",
          tool.target_label("mysql+pymysql://peak_lab_runtime:p@h:3306/peak_lab",
                            production=True, confirm="1") is None
          and tool.target_label("sqlite:///x.sqlite3", production=True, confirm="1") is None)

    def run(factory, argv):
        buf = io.StringIO()
        with redirect_stdout(buf):
            code = tool.main(argv, session_factory=factory, prompt=lambda _p: "bootstrap-pass-1")
        return code, buf.getvalue()

    code, _ = run(session_factory, ["--email", "second@example.com", "--execute"])
    check("refuses when an Admin already exists", code == 1)
    code, _ = run(empty_factory, ["--email", "steve@example.com"])
    check("dry-run by default writes nothing",
          code == 0 and not accounts.admin_exists(empty_factory))
    code, out = run(empty_factory, ["--email", "steve@example.com", "--execute"])
    check("creates Steve Rouse as Admin by default",
          code == 0 and accounts.list_consultants(empty_factory)[0]["name"] == "Steve Rouse"
          and accounts.list_consultants(empty_factory)[0]["role"] == "admin")
    check("output never includes the password or hash",
          "bootstrap-pass-1" not in out and "$argon2" not in out)
    check("bootstrapped Admin authenticates",
          accounts.authenticate(empty_factory, "steve@example.com", "bootstrap-pass-1") is not None)


def main() -> int:
    print("Peak Phase 201 consultant web authentication check")
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

    tmp = tempfile.mkdtemp(prefix="peak_phase201_")
    try:
        migration_checks(tmp)
        factories = []
        for name in ("api.sqlite3", "empty.sqlite3"):
            f = create_session_factory(url=f"sqlite:///{os.path.join(tmp, name)}")
            Base.metadata.create_all(f.kw["bind"])
            factories.append(f)
        api_checks(factories[0])
        bootstrap_checks(factories[0], factories[1])
    finally:
        shutil.rmtree(tmp, ignore_errors=True)

    print("\nSummary")
    print(f"  failures : {len(_failures)}")
    print("RESULT: " + ("PASS" if not _failures else "FAIL"))
    return 0 if not _failures else 1


if __name__ == "__main__":
    sys.exit(main())
