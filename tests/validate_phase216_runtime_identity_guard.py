#!/usr/bin/env python3
"""Phase 216 — the API refuses to start on a non-runtime database user (offline; no connection).

The production API had been configured with the read-only verifier's URL. While the verifier held
platform-default global privileges, writes worked; once it was reduced to SELECT, they failed. This
harness proves ``require_runtime_identity`` and the ``create_app`` startup path:
- refuse the verifier and migration users anywhere;
- in production (MySQL ``defaultdb`` schema, or a ``prod`` username) accept only the runtime user;
- leave lab, local SQLite and injected session factories alone;
- never put the URL, host or password in the refusal.

Exit status: 0 all checks passed; 1 a check failed.
"""

from __future__ import annotations

import os
import subprocess
import sys

REPO_ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
if REPO_ROOT not in sys.path:
    sys.path.insert(0, REPO_ROOT)

_failures = []
SECRET_PW = "s3cret-pw-never-printed"
HOST = "db-host-never-printed.example.invalid"


def check(label, ok):
    print(f"  [{'PASS' if ok else 'FAIL'}] {label}")
    if not ok:
        _failures.append(label)


def url(user, schema="defaultdb", scheme="mysql+pymysql"):
    return f"{scheme}://{user}:{SECRET_PW}@{HOST}:3306/{schema}?ssl-mode=REQUIRED"


def refusal(u):
    from peak.db.session import require_runtime_identity

    try:
        require_runtime_identity(u)
    except RuntimeError as exc:
        return str(exc)
    return None


def main() -> int:
    from peak.db import session

    print("[guard: refused]")
    for user, schema in (("peak_prod_verify_ro", "defaultdb"), ("peak_prod_migrate", "defaultdb"),
                         ("PEAK_PROD_VERIFY_RO", "defaultdb"), ("peak_prod_verify_ro", "peak_lab"),
                         ("avnadmin", "defaultdb"), ("peak_prod_readonly", "other")):
        msg = refusal(url(user, schema))
        check(f"{user} on {schema} is refused", msg is not None)
        check(f"  refusal names no password, host or URL ({user})",
              msg is not None and SECRET_PW not in msg and HOST not in msg and "://" not in msg)

    print("[guard: accepted]")
    for label, u in (("peak_prod_runtime on defaultdb", url("peak_prod_runtime")),
                     ("lab runtime on peak_lab", url("peak_lab_runtime", "peak_lab")),
                     ("local SQLite file", "sqlite:////tmp/peak-local.sqlite3"),
                     ("in-memory SQLite", "sqlite://")):
        check(f"{label} is accepted", refusal(u) is None)
    check("the deny-list is exactly the verifier and migration users",
          session.FORBIDDEN_RUNTIME_USERS == {"peak_prod_verify_ro", "peak_prod_migrate"})

    print("[create_app startup path, isolated subprocess]")
    probe = ("import sys; sys.path.insert(0, %r)\n"
             "from peak.consultant_api.app import create_app\n"
             "try:\n    create_app()\nexcept RuntimeError as e:\n    print('REFUSED', e); sys.exit(3)\n"
             "print('STARTED')\n") % REPO_ROOT
    base = {k: v for k, v in os.environ.items() if not k.startswith("PEAK_")}
    base["PEAK_WEB_SECRET_KEY"] = "test-secret-key-for-guard-harness-only"

    def start(runtime_url):
        env = dict(base, PEAK_RUNTIME_DATABASE_URL=runtime_url)
        return subprocess.run([sys.executable, "-c", probe], env=env, capture_output=True, text=True,
                              cwd=REPO_ROOT)

    for user in ("peak_prod_verify_ro", "peak_prod_migrate"):
        r = start(url(user))
        out = r.stdout + r.stderr
        check(f"create_app() refuses to start as {user}", r.returncode == 3 and "REFUSED" in r.stdout)
        check(f"  startup output names no password or host ({user})", SECRET_PW not in out and HOST not in out)
    r = start(url("peak_prod_runtime"))
    check("create_app() starts as peak_prod_runtime (engine is lazy; no connection made)",
          r.returncode == 0 and "STARTED" in r.stdout)
    r = start("sqlite://")
    check("create_app() starts on local SQLite", r.returncode == 0 and "STARTED" in r.stdout)

    from peak.consultant_api.app import create_app
    from peak.db.session import create_session_factory

    create_app(session_factory=create_session_factory(url="sqlite://"), secret_key="x" * 32)
    check("an injected session factory bypasses the environment guard (harness path unchanged)", True)

    print(f"\nRESULT: {'PASS' if not _failures else 'FAIL'} ({len(_failures)} failure(s))")
    return 1 if _failures else 0


if __name__ == "__main__":
    sys.exit(main())
