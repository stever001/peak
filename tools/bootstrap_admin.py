#!/usr/bin/env python3
"""Phase 201 — bootstrap the initial Peak web Admin (Steve Rouse by default).

Creates **exactly one** ``consultants`` row with ``role=admin``, or none. The password is entered
interactively without echo (twice) and is never printed, logged, stored in plaintext, or accepted
as an argument; only its Argon2id hash is written. No credential is hard-coded.

**Refusals.** The tool refuses if any Admin already exists (further accounts are created in the app
by an Admin). It is dry-run unless ``--execute`` is passed.

**Targets.** The session comes from the normal runtime path
(:func:`peak.db.session.create_session_factory`, i.e. ``PEAK_RUNTIME_DATABASE_URL``). Phase 201
authorizes local SQLite and ``peak_lab`` only: a MySQL/MariaDB URL whose schema is not exactly
``peak_lab`` is refused before any connection is opened, and every other dialect is refused. No
production consultant-account write is authorized. Output never includes a URL or credential.

Usage (with ``PEAK_RUNTIME_DATABASE_URL`` pointing at a local SQLite file or ``peak_lab``)::

    python3 tools/bootstrap_admin.py --email steve@example.com            # dry run
    python3 tools/bootstrap_admin.py --email steve@example.com --execute  # prompts for password

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


def target_label(url: str):
    """Classify the runtime URL as ``local`` / ``lab``, or return ``None`` (refused)."""
    scheme = urlsplit(url).scheme.split("+", 1)[0]
    if scheme == "sqlite":
        return "local"
    if scheme in ("mysql", "mariadb"):
        return "lab" if urlsplit(url).path.lstrip("/") == LAB_SCHEMA else None
    return None


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
            label = target_label(get_runtime_database_url())
        except RuntimeError as exc:
            print(f"REFUSED: {exc}")
            return 2
        if label is None:
            print(f"REFUSED: Phase 201 permits local SQLite or the {LAB_SCHEMA} schema only; "
                  "no production consultant-account write is authorized.")
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
