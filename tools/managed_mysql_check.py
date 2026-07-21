#!/usr/bin/env python3
"""Managed MySQL production-parity check / runbook (Phase 34).

A **safe, credential-free, opt-in** helper for the managed remote MySQL persistence rubric
(docs/MANAGED_MYSQL_PERSISTENCE_RUBRIC.md and docs/PRODUCTION_PARITY_DB_VALIDATION.md).

Design guarantees (this is not a generic DB tool):
  * It reads the target DSN **only** from an environment variable — never from Git, never a literal.
  * It **never prints the DSN** (only "configured (value hidden)" / "not configured").
  * It accepts **only** the ``test`` and ``staging`` environments. ``prod`` is refused (fail closed)
    — production is never the smoke-test target and no destructive path is offered here.
  * With **no DSN set** it prints clear guidance and **skips** (exit 0) so ``make validate`` and CI
    stay green without credentials or network.
  * By default it is a **dry runbook** (config check + steps). A real connection is attempted only
    with the explicit ``--connect`` flag *and* a DSN present — never as part of ``make validate``.
  * It performs **no writes, no seed, no delete/cleanup, and no migration downgrade** against any
    managed database. ``--connect`` does at most a read-only ``SELECT 1`` and an Alembic head read.

Exit status:
  0  -> skipped (no DSN) or dry runbook printed, or read-only connect succeeded
  2  -> misuse (e.g. prod requested) or an explicit --connect check failed
"""

from __future__ import annotations

import argparse
import os
import sys

ENV_DSN_VARS = {
    "test": "PEAK_MANAGED_MYSQL_TEST_DSN",
    "staging": "PEAK_MANAGED_MYSQL_STAGING_DSN",
}
# Documented but intentionally NOT selectable here — production is never a smoke target.
PROD_DSN_VAR = "PEAK_MANAGED_MYSQL_PROD_DSN"

MODES = ("db-check", "smoke", "migration-check")


def _runbook(mode: str, env: str) -> list:
    common = [
        "Managed MySQL is the operational data store; SQLite is only a fast local structural smoke",
        "path and is NOT the production-readiness proof path.",
        f"Target environment: {env} (managed, non-production).",
    ]
    if mode == "db-check":
        return common + [
            "Runbook (run manually against the managed test/staging DB, credentials out of Git):",
            "  1. Confirm the environment DSN is exported (never committed).",
            "  2. Apply migrations to head:  alembic upgrade head",
            "  3. Verify the expected governed tables/columns and single Alembic head.",
        ]
    if mode == "smoke":
        return common + [
            "Runbook (managed test/staging only; use a dedicated synthetic smoke tenant):",
            "  1. Seed a synthetic Engagement authorization subject for the smoke tenant.",
            "  2. Exercise each narrow controlled writer's authorized-create + idempotent-replay.",
            "  3. Assert receipts carry no secrets/DSN/SQL/raw content; no broad delete cleanup.",
        ]
    return common + [
        "Runbook (managed test/staging ONLY — never production):",
        "  1. alembic upgrade head",
        "  2. alembic downgrade -1 then alembic upgrade head (reversibility) on the TEST DB only.",
        "  3. Confirm a single linear Alembic head after re-upgrade.",
        "Note: migration downgrade/re-upgrade must never be run against the production client DB.",
    ]


def main(argv=None) -> int:
    parser = argparse.ArgumentParser(description="Managed MySQL production-parity check / runbook.")
    parser.add_argument("--env", choices=("test", "staging", "prod"), default="test",
                        help="Managed environment (test/staging only; prod is refused).")
    parser.add_argument("--mode", choices=MODES, default="db-check")
    parser.add_argument("--connect", action="store_true",
                        help="Opt-in read-only connectivity check (never run by make validate).")
    args = parser.parse_args(argv)

    print("Peak managed MySQL production-parity check")
    print("=" * 42)

    if args.env == "prod":
        print("REFUSED: production is never the smoke-test target and is not selectable here.")
        print(f"({PROD_DSN_VAR} is documented for operations only; this tool serves test/staging.)")
        return 2

    dsn_var = ENV_DSN_VARS[args.env]
    dsn = os.environ.get(dsn_var)

    if not dsn:
        print(f"[skip] {dsn_var} is not set — no managed MySQL {args.env} DSN configured.")
        print("       This is expected for local/CI runs; managed MySQL validation is opt-in and")
        print("       requires no credentials in Git. To run it, export the DSN out-of-band:")
        print(f"         export {dsn_var}='mysql+pymysql://USER:PASSWORD@HOST:3306/DBNAME'")
        print(f"       then re-run this target. Mode requested: {args.mode}.")
        return 0  # skip cleanly — keeps `make validate` / CI green without credentials

    # A DSN is present. NEVER print it.
    print(f"[ok] {dsn_var} is configured (value hidden). Environment: {args.env}. Mode: {args.mode}.")
    for line in _runbook(args.mode, args.env):
        print(f"  {line}")

    if not args.connect:
        print("[dry] Runbook printed only (no connection). Pass --connect for a read-only check.")
        return 0

    # Opt-in, read-only connectivity check. Never writes, seeds, deletes, or migrates.
    try:
        from sqlalchemy import create_engine, text
    except ImportError:
        print("[skip] SQLAlchemy not installed; cannot run --connect check (structural runbook only).")
        return 0
    try:
        engine = create_engine(dsn, pool_pre_ping=True)
        with engine.connect() as conn:
            conn.execute(text("SELECT 1"))
        print("[ok] read-only connectivity check succeeded (SELECT 1).")
        return 0
    except Exception as exc:  # noqa: BLE001 - report type only; never leak DSN/credentials
        print(f"[fail] managed MySQL connectivity check failed ({type(exc).__name__}).")
        return 2


if __name__ == "__main__":
    sys.exit(main())
