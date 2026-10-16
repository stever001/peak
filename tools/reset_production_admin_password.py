#!/usr/bin/env python3
"""Reset the password of the one production Peak Admin, ``admin@peakinventorysolutions.com``.

A narrow recovery tool, not a general password-reset feature: it can change exactly one column
(``password_hash``) of exactly one row, the Admin whose email is ``TARGET_EMAIL``. It cannot reset
any other account, change an email, role, id or ``created_at``, or create an account.

**Password.** Entered interactively without echo, twice. It is never accepted as an argument or an
environment variable, and neither the password nor its hash is printed, logged or stored outside
the database. Hashing and the length rule are Peak's own (``peak.accounts.service``, Argon2id).

**Refusals, all before any write:**
- ``--email`` must equal ``TARGET_EMAIL`` exactly;
- ``PEAK_PRODUCTION_ADMIN_PASSWORD_RESET_CONFIRM=1`` must be set;
- the connection must be a production MySQL URL: production-marked user, no lab marker (the same
  check as ``tools/bootstrap_admin.py --production``);
- exactly one consultant must have that email, and its role must be ``admin``;
- the two entries must match and satisfy the password rule.

**Credential.** ``PEAK_DATABASE_URL``, the migration credential, which ``peak/db/session.py``
reserves for migration and bootstrap tools. The production runtime role holds no UPDATE on
``consultants`` and none is granted for this. The URL is never printed.

**Dry run by default.** Without ``--execute`` it checks the target and stops. With ``--execute`` it
prompts, then in one transaction locks the row, re-checks it, updates only ``password_hash``,
confirms id, email, role and ``created_at`` are unchanged, and commits. Afterwards it verifies that
the new password signs in.

Usage (from the repository root, in your own terminal)::

    PEAK_PRODUCTION_ADMIN_PASSWORD_RESET_CONFIRM=1 \\
        python3 tools/reset_production_admin_password.py --email admin@peakinventorysolutions.com
    ... --execute   # prompts for the new password twice

Exit status: 0 dry-run OK or password reset; 1 refused or failed; 2 usage/configuration error.
"""

from __future__ import annotations

import argparse
import getpass
import os
import sys

REPO_ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
for _p in (REPO_ROOT, os.path.join(REPO_ROOT, "tools")):
    if _p not in sys.path:
        sys.path.insert(0, _p)

TARGET_EMAIL = "admin@peakinventorysolutions.com"
CONFIRM_ENV = "PEAK_PRODUCTION_ADMIN_PASSWORD_RESET_CONFIRM"
URL_ENV = "PEAK_DATABASE_URL"


def read_new_password(prompt=getpass.getpass) -> str:
    first = prompt("New Admin password: ")
    if first != prompt("Confirm new password: "):
        raise ValueError("Passwords do not match.")
    return first


def _target_row(session):
    """The one Admin row with ``TARGET_EMAIL``, or a refusal reason."""
    from sqlalchemy import func, select

    from peak.db.models import Consultant

    matches = session.scalar(select(func.count()).select_from(Consultant)
                             .where(Consultant.email == TARGET_EMAIL))
    if matches != 1:
        return None, f"expected exactly one consultant with {TARGET_EMAIL}, found {matches}"
    row = session.scalar(select(Consultant).where(Consultant.email == TARGET_EMAIL))
    if row.role != "admin":
        return None, f"the consultant with {TARGET_EMAIL} is not an Admin"
    return row, None


def _identity(row) -> tuple:
    return (row.id, row.email, row.role, row.name, row.created_at)


def main(argv=None, session_factory=None, prompt=getpass.getpass, env=None) -> int:
    env = os.environ if env is None else env
    parser = argparse.ArgumentParser(description=f"Reset the password of {TARGET_EMAIL} (production).")
    parser.add_argument("--email", required=True, help=f"must be exactly {TARGET_EMAIL}")
    parser.add_argument("--execute", action="store_true", help="write (default is a dry run)")
    args = parser.parse_args(argv)

    if args.email != TARGET_EMAIL:
        print(f"REFUSED: this tool resets only {TARGET_EMAIL}.")
        return 2
    if env.get(CONFIRM_ENV, "") != "1":
        print(f"REFUSED: set {CONFIRM_ENV}=1 to confirm a production Admin password reset.")
        return 1

    if session_factory is None:
        from bootstrap_admin import target_label

        from peak.db.session import create_session_factory

        url = env.get(URL_ENV, "")
        if not url:
            print(f"REFUSED: {URL_ENV} (the production migration credential) is not set.")
            return 2
        if target_label(url, production=True, confirm="1") != "production":
            print(f"REFUSED: {URL_ENV} is not a production MySQL URL (production-marked user, "
                  "no lab marker).")
            return 1
        session_factory = create_session_factory(url=url)
        label = "production"
    else:
        label = "injected"
    print(f"target: {label}")

    with session_factory() as session:
        row, reason = _target_row(session)
        if row is None:
            print(f"REFUSED: {reason}.")
            return 1
        target_id = row.id
    if not args.execute:
        print(f"DRY-RUN OK: would reset the password of Admin <{TARGET_EMAIL}> id={target_id}. "
              "Pass --execute to write.")
        return 0

    from sqlalchemy import select, update

    from peak import accounts
    from peak.accounts import service as account_service
    from peak.db.models import Consultant

    try:
        password = account_service._validate_password(read_new_password(prompt))
    except (accounts.AccountError, ValueError) as exc:
        print(f"REFUSED: {exc}")
        return 1
    new_hash = account_service._hasher.hash(password)

    with session_factory() as session:
        row = session.scalar(select(Consultant).where(Consultant.id == target_id).with_for_update())
        if row is None or (row.email, row.role) != (TARGET_EMAIL, "admin"):
            session.rollback()
            print("REFUSED: the target Admin changed before the write; nothing was written.")
            return 1
        before = _identity(row)
        result = session.execute(
            update(Consultant)
            .where(Consultant.id == target_id, Consultant.email == TARGET_EMAIL,
                   Consultant.role == "admin")
            .values(password_hash=new_hash)
            .execution_options(synchronize_session=False))
        if result.rowcount != 1:
            session.rollback()
            print("REFUSED: the update did not match exactly one row; nothing was written.")
            return 1
        session.expire_all()
        after = _identity(session.get(Consultant, target_id))
        if after != before:
            session.rollback()
            print("REFUSED: identity columns would change; nothing was written.")
            return 1
        session.commit()

    signed_in = accounts.authenticate(session_factory, TARGET_EMAIL, password)
    del password
    if not signed_in or signed_in["id"] != target_id:
        print("FAILED: the password was written but the sign-in check did not pass.")
        return 1
    print(f"RESET: password updated for Admin <{TARGET_EMAIL}> id={target_id}; "
          "id, email, role and created_at unchanged; the new password signs in.")
    return 0


if __name__ == "__main__":
    sys.exit(main())
