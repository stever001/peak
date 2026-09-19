#!/usr/bin/env python3
"""Phase 201 — bootstrap the initial Peak web Admin (Steve Rouse by default).

Creates **exactly one** ``consultants`` row with ``role=admin``, or none. The password is entered
interactively without echo (twice) and is never printed, logged, stored in plaintext, or accepted
as an argument; only its Argon2id hash is written. No credential is hard-coded.

**Refusals.** The tool refuses if any Admin already exists (further accounts are created in the app
by an Admin). It is dry-run unless ``--execute`` is passed.

**Targets.** The session comes from the normal runtime path
(:func:`peak.db.session.create_session_factory`, i.e. ``PEAK_RUNTIME_DATABASE_URL``, the
least-privilege runtime credential). Without ``--production`` only local SQLite and the ``peak_lab``
schema are accepted; any other MySQL/MariaDB URL and every other dialect is refused before any
connection is opened.

**Production (Phase 203)** is a separate, explicit mode. It requires all of: the ``--production``
flag, ``PEAK_PRODUCTION_ADMIN_BOOTSTRAP_CONFIRM=1`` (the exact string), and a MySQL/MariaDB URL whose
user is production-marked (contains ``prod``) and neither user nor schema lab-marked. A lab or local
URL with ``--production`` is refused too, so the flag must match the target. Output never includes a
URL or credential.

Usage (with ``PEAK_RUNTIME_DATABASE_URL`` set for the target)::

    python3 tools/bootstrap_admin.py --email steve@example.com            # dry run
    python3 tools/bootstrap_admin.py --email steve@example.com --execute  # prompts for password
    PEAK_PRODUCTION_ADMIN_BOOTSTRAP_CONFIRM=1 \\
        python3 tools/bootstrap_admin.py --production --email <email> --execute

Exit status: 0 dry-run OK or Admin created; 1 refused or failed; 2 usage/configuration error.
"""

from __future__ import annotations

import argparse
import getpass
import os
import sys
from urllib.parse import urlsplit

REPO_ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
if REPO_ROOT not in sys.path:
    sys.path.insert(0, REPO_ROOT)

DEFAULT_NAME = "Steve Rouse"
LAB_SCHEMA = "peak_lab"
LAB_MARKER = "peak_lab"
PRODUCTION_CONFIRM_ENV = "PEAK_PRODUCTION_ADMIN_BOOTSTRAP_CONFIRM"


def target_label(url: str, production: bool = False, confirm: str = ""):
    """Classify the runtime URL as ``local`` / ``lab`` / ``production``, or ``None`` (refused).

    Only the username and schema are inspected; host, port, password and query are discarded.
    """
    parts = urlsplit(url)
    scheme = parts.scheme.split("+", 1)[0]
    try:
        user = (parts.username or "").lower()
    except ValueError:
        user = ""
    schema = parts.path.lstrip("/").split("/", 1)[0].lower()
    if not production:
        if scheme == "sqlite":
            return "local"
        if scheme in ("mysql", "mariadb"):
            return "lab" if schema == LAB_SCHEMA else None
        return None
    if confirm != "1" or scheme not in ("mysql", "mariadb"):
        return None
    if "prod" not in user or LAB_MARKER in user or LAB_MARKER in schema:
        return None
    return "production"


def read_password(prompt=getpass.getpass) -> str:
    first = prompt("Initial Admin password: ")
    if first != prompt("Confirm password: "):
        raise ValueError("Passwords do not match.")
    return first


def main(argv=None, session_factory=None, prompt=getpass.getpass) -> int:
    parser = argparse.ArgumentParser(description="Create the initial Peak web Admin account.")
    parser.add_argument("--name", default=DEFAULT_NAME, help=f"default: {DEFAULT_NAME}")
    parser.add_argument("--email", required=True)
    parser.add_argument("--execute", action="store_true",
                        help="write the account (default is a dry run)")
    parser.add_argument("--production", action="store_true",
                        help=f"target production (also requires {PRODUCTION_CONFIRM_ENV}=1)")
    args = parser.parse_args(argv)

    from peak import accounts

    try:
        email = accounts.normalize_email(args.email)
    except accounts.AccountError as exc:
        print(f"REFUSED: {exc}")
        return 2

    if session_factory is None:
        from peak.db.session import create_session_factory, get_runtime_database_url

        try:
            label = target_label(get_runtime_database_url(), production=args.production,
                                 confirm=os.environ.get(PRODUCTION_CONFIRM_ENV, ""))
        except RuntimeError as exc:
            print(f"REFUSED: {exc}")
            return 2
        if label is None:
            if args.production:
                print(f"REFUSED: --production needs {PRODUCTION_CONFIRM_ENV}=1 and a production "
                      "MySQL runtime URL (production-marked user, no lab marker).")
            else:
                print(f"REFUSED: without --production only local SQLite or the {LAB_SCHEMA} "
                      "schema is accepted.")
            return 1
        session_factory = create_session_factory()
    else:
        label = "injected"

    print(f"target: {label}")
    if accounts.admin_exists(session_factory):
        print("REFUSED: an Admin already exists. Add further accounts in the web app.")
        return 1
    if not args.execute:
        print(f"DRY-RUN OK: would create Admin {args.name!r} <{email}>. Pass --execute to write.")
        return 0

    try:
        consultant = accounts.create_consultant(
            session_factory, name=args.name, email=email, role="admin",
            password=read_password(prompt),
        )
    except (accounts.AccountError, ValueError) as exc:
        print(f"REFUSED: {exc}")
        return 1
    print(f"CREATED: Admin {consultant['name']!r} <{consultant['email']}> id={consultant['id']}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
