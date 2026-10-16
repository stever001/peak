#!/usr/bin/env python3
"""Check tools/reset_production_admin_password.py (offline; temporary SQLite only).

Proves the tool resets only the password of the one Admin ``admin@peakinventorysolutions.com``:
dry run by default; exact email; confirmation variable; production URL check; exactly one
matching Admin; matching, valid entries; only ``password_hash`` changes; the new password signs
in and the old one stops working; no password or hash is printed; no password argument exists.

Exit status: 0 all checks passed; 1 a check failed.
"""

from __future__ import annotations

import contextlib
import io
import os
import subprocess
import sys
import tempfile

REPO_ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
for _p in (REPO_ROOT, os.path.join(REPO_ROOT, "tools")):
    if _p not in sys.path:
        sys.path.insert(0, _p)

_failures = []
TARGET = "admin@peakinventorysolutions.com"
OLD, NEW = "old-password-reset-test", "new-password-reset-test"
CONFIRM = {"PEAK_PRODUCTION_ADMIN_PASSWORD_RESET_CONFIRM": "1"}


def check(label, ok):
    print(f"  [{'PASS' if ok else 'FAIL'}] {label}")
    if not ok:
        _failures.append(label)


def factory_at(tmp, name):
    db = os.path.join(tmp, name)
    env = {k: v for k, v in os.environ.items() if not k.startswith("PEAK_")}
    env["PEAK_DATABASE_URL"] = f"sqlite:///{db}"
    subprocess.run([sys.executable, "-m", "alembic", "upgrade", "head"], cwd=REPO_ROOT, env=env,
                   capture_output=True, check=True)
    from peak.db.session import create_session_factory

    return create_session_factory(url=f"sqlite:///{db}")


def run(argv, factory=None, answers=(), env=CONFIRM):
    import reset_production_admin_password as tool

    feed = iter(answers)
    out = io.StringIO()
    with contextlib.redirect_stdout(out):
        code = tool.main(argv, session_factory=factory, prompt=lambda _: next(feed), env=env)
    return code, out.getvalue()


def rows(factory):
    from sqlalchemy import select

    from peak.db.models import Consultant

    with factory() as s:
        return {r.id: (r.email, r.role, r.name, r.created_at, r.password_hash)
                for r in s.scalars(select(Consultant))}


def main() -> int:
    from peak import accounts

    with tempfile.TemporaryDirectory() as tmp:
        f = factory_at(tmp, "a.sqlite3")
        admin = accounts.create_consultant(f, name="Steve Rouse", email=TARGET, role="admin",
                                           password=OLD)["id"]
        other_admin = accounts.create_consultant(f, name="Other Admin", email="other@example.com",
                                                 role="admin", password=OLD)["id"]
        accounts.create_consultant(f, name="Con Sultant", email="c@example.com", role="consultant",
                                   password=OLD)
        execute = ["--email", TARGET, "--execute"]

        print("\n[refusals before any write]")
        before = rows(f)
        code, out = run(["--email", "other@example.com", "--execute"], f, (NEW, NEW))
        check("any other email is refused (exit 2)", code == 2 and "REFUSED" in out)
        code, out = run(["--email", TARGET.upper(), "--execute"], f, (NEW, NEW))
        check("the email must match exactly", code == 2)
        code, out = run(execute, f, (NEW, NEW), env={})
        check("the confirmation variable is required", code == 1 and "REFUSED" in out)
        code, out = run(execute, None, (NEW, NEW),
                        env={**CONFIRM, "PEAK_DATABASE_URL": "sqlite:///x.sqlite3"})
        check("a non-production URL is refused before connecting", code == 1 and "REFUSED" in out)
        code, out = run(execute, None, (NEW, NEW),
                        env={**CONFIRM, "PEAK_DATABASE_URL": "mysql+pymysql://peak_lab_migrate:x@h/peak_lab"})
        check("a lab URL is refused", code == 1)
        code, out = run(execute, f, (NEW, "different-password-x"))
        check("mismatched entries are refused", code == 1 and "do not match" in out)
        code, out = run(execute, f, ("short", "short"))
        check("a password outside Peak's rule is refused", code == 1)
        check("nothing was written by any refusal", rows(f) == before)
        code, out = run(["--email", TARGET], f)
        check("dry run is the default and writes nothing",
              code == 0 and "DRY-RUN OK" in out and admin in out and rows(f) == before)

        print("\n[the reset]")
        code, out = run(execute, f, (NEW, NEW))
        after = rows(f)
        check("--execute resets and reports success", code == 0 and "RESET" in out)
        check("only the target's password_hash changed",
              after[admin][:4] == before[admin][:4] and after[admin][4] != before[admin][4]
              and all(after[k] == v for k, v in before.items() if k != admin))
        check("the new password signs in; the old one no longer does",
              accounts.authenticate(f, TARGET, NEW) is not None
              and accounts.authenticate(f, TARGET, OLD) is None)
        check("the other Admin's password is untouched",
              accounts.authenticate(f, "other@example.com", OLD)["id"] == other_admin)
        check("no password or hash appears in the output",
              NEW not in out and OLD not in out and after[admin][4] not in out
              and "$argon2" not in out)

        print("\n[target row checks]")
        g = factory_at(tmp, "b.sqlite3")
        code, out = run(execute, g, (NEW, NEW))
        check("zero matching Admins is refused", code == 1 and "found 0" in out)
        accounts.create_consultant(g, name="Not Admin", email=TARGET, role="consultant", password=OLD)
        code, out = run(execute, g, (NEW, NEW))
        check("a non-Admin with the target email is refused",
              code == 1 and "not an Admin" in out and accounts.authenticate(g, TARGET, OLD))

    print("\n[source]")
    src = open(os.path.join(REPO_ROOT, "tools/reset_production_admin_password.py")).read()
    check("no password argument or password environment variable",
          "--password" not in src and "PASSWORD\"" not in src.replace("RESET_CONFIRM", ""))
    check("the password comes from getpass and Peak's own hasher",
          "getpass.getpass" in src and "account_service._hasher.hash" in src)
    check("the only column written is password_hash",
          src.count(".values(") == 1 and ".values(password_hash=new_hash)" in src)

    print("\n========================================================")
    print(f"  failures : {len(_failures)}")
    print(f"\nRESULT: {'PASS' if not _failures else 'FAIL'}")
    return 1 if _failures else 0


if __name__ == "__main__":
    sys.exit(main())
