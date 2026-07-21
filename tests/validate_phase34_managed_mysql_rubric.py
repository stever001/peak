#!/usr/bin/env python3
"""Phase 34 managed-MySQL-rubric + AgentNet-publication-policy check.

Stdlib-only, credential-free, no live network. Verifies the production-parity managed MySQL
persistence rubric and the Peak-operated AgentNet publication policy are documented, that the safe
opt-in managed-MySQL Makefile targets/script skip cleanly without a DSN and never print DSNs, and
that no credentials / `.env` values / AgentNet publish code were committed.

Exit status:
  0  -> all checks passed
  1  -> a check failed
"""

from __future__ import annotations

import os
import re
import subprocess
import sys

REPO_ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
PY = sys.executable or "python3"

RUBRIC = "docs/MANAGED_MYSQL_PERSISTENCE_RUBRIC.md"
ISOLATION = "docs/CLIENT_ISOLATION_MODEL.md"
PARITY = "docs/PRODUCTION_PARITY_DB_VALIDATION.md"
PUBPOLICY = "docs/PEAK_OPERATED_AGENTNET_PUBLICATION_POLICY.md"
TOOL = "tools/managed_mysql_check.py"

ENV_VARS = ("PEAK_MANAGED_MYSQL_TEST_DSN", "PEAK_MANAGED_MYSQL_STAGING_DSN",
            "PEAK_MANAGED_MYSQL_PROD_DSN")
MANAGED_TARGETS = ("db-check-managed-test", "managed-mysql-smoke", "managed-mysql-migration-check")

PASS, FAIL = "PASS", "FAIL"
_failures: list = []


def read(rel: str) -> str:
    with open(os.path.join(REPO_ROOT, rel), "r", encoding="utf-8") as fh:
        return fh.read()


def check(label: str, ok: bool) -> None:
    if ok:
        print(f"  [{PASS}] {label}")
    else:
        _failures.append(label)
        print(f"  [{FAIL}] {label}")


def _has(blob: str, *needles: str) -> bool:
    low = blob.lower()
    return all(n.lower() in low for n in needles)


def main() -> int:
    print("Peak Phase 34 managed-MySQL-rubric + AgentNet-publication-policy check")
    print("=" * 68)

    print("\n1. Rubric / isolation / parity docs exist")
    for rel in (RUBRIC, ISOLATION, PARITY, PUBPOLICY, TOOL):
        check(rel, os.path.isfile(os.path.join(REPO_ROOT, rel)))

    print("\n2. Managed MySQL persistence rubric statements")
    rub = re.sub(r"\s+", " ", read(RUBRIC) + " " + read(PARITY) + " " + read(ISOLATION))
    check("managed remote MySQL is the operational data store",
          _has(rub, "managed remote mysql", "operational data store"))
    check("Client Isolation Option A is the default",
          _has(rub, "client isolation option a", "default"))
    check("SQLite is not the production-readiness proof path",
          _has(rub, "sqlite is not the production-readiness proof path"))
    check("managed MySQL test/staging required for production readiness",
          _has(rub, "managed mysql test/staging validation is required"))
    check("production DB is not the main smoke-test target",
          _has(rub, "production db is not the main smoke-test target"))
    check("no broad production delete/cleanup path",
          _has(rub, "no broad production delete"))
    check("environments separated (dev/test/staging/prod)",
          _has(rub, "dev", "test", "staging", "prod"))
    check("client data must never be committed to Git",
          _has(rub, "client data", "never", "git"))

    print("\n3. Env var names documented (no values)")
    for var in ENV_VARS:
        check(f"{var} documented", var in read(RUBRIC))
    # No DSN value should be committed anywhere in the rubric/tool (placeholders only).
    dsn_value_re = re.compile(r"mysql\+pymysql://[A-Za-z0-9]+:[A-Za-z0-9]{4,}@[A-Za-z0-9.\-]+")
    for rel in (RUBRIC, PARITY, TOOL, "Makefile"):
        body = read(rel)
        # Allow explicit placeholders (USER/PASSWORD/HOST); reject anything that looks real.
        hits = [m.group(0) for m in dsn_value_re.finditer(body)
                if not re.search(r"USER|PASSWORD|HOST|DBNAME", m.group(0), re.IGNORECASE)]
        check(f"{rel}: no real DSN value committed", not hits)

    print("\n4. AgentNet publication policy statements")
    pub = re.sub(r"\s+", " ", read(PUBPOLICY))
    check("Client authorizes Peak as publisher in consulting agreement",
          _has(pub, "consulting agreement", "authorized capsule/node publisher"))
    check("Client does not operate AgentNet publishing tools",
          _has(pub, "clients do not operate any agentnet publishing tools"))
    check("Peak operates publishing as a managed service",
          _has(pub, "peak operates all publishing workflows as a managed service"))
    check("no client-facing publisher UI", _has(pub, "no client-facing agentnet publisher ui"))
    check("no client-held publishing credentials",
          _has(pub, "no client-held publishing credentials"))
    check("no client-operated resolver publication tools",
          _has(pub, "no client-operated resolver publication tools"))
    check("no direct client publication path", _has(pub, "no direct client publication path"))
    check("publication remains disabled until future controlled gates",
          _has(pub, "publication remains disabled until future controlled publication gates"))

    print("\n5. Makefile targets present and NOT part of `make validate`")
    mk = read("Makefile")
    for t in MANAGED_TARGETS:
        check(f"target '{t}' defined", f"{t}:" in mk)
    validate_line = next((ln for ln in mk.splitlines() if ln.startswith("validate:")), "")
    check("managed targets are not chained into `make validate`",
          not any(t in validate_line for t in MANAGED_TARGETS)
          and "validate-phase34" in validate_line)

    print("\n6. Managed-MySQL script skips safely with no DSN and never prints a DSN")
    env = {k: v for k, v in os.environ.items() if k not in ENV_VARS}
    proc = subprocess.run(
        [PY, os.path.join(REPO_ROOT, TOOL), "--env", "test", "--mode", "db-check"],
        capture_output=True, text=True, env=env, timeout=60)
    check("no-DSN db-check exits 0 (skip)", proc.returncode == 0)
    check("no-DSN output shows a skip with guidance", "[skip]" in proc.stdout)
    check("no-DSN output names the env var to set", "PEAK_MANAGED_MYSQL_TEST_DSN" in proc.stdout)
    # prod is refused (fail closed).
    proc_prod = subprocess.run(
        [PY, os.path.join(REPO_ROOT, TOOL), "--env", "prod", "--mode", "db-check"],
        capture_output=True, text=True, env=env, timeout=60)
    check("prod environment refused (non-zero exit)", proc_prod.returncode != 0)
    check("prod refusal message present", "REFUSED" in proc_prod.stdout)
    # With a dummy DSN set, the value must never be echoed (dry mode, no --connect).
    dummy = "mysql+pymysql://USER:PASSWORD@HOST:3306/DBNAME_SENTINEL_ZZZ"
    env_dummy = dict(env)
    env_dummy["PEAK_MANAGED_MYSQL_TEST_DSN"] = dummy
    proc_dsn = subprocess.run(
        [PY, os.path.join(REPO_ROOT, TOOL), "--env", "test", "--mode", "db-check"],
        capture_output=True, text=True, env=env_dummy, timeout=60)
    check("configured-DSN run exits 0 (dry runbook)", proc_dsn.returncode == 0)
    check("DSN value never printed",
          "DBNAME_SENTINEL_ZZZ" not in proc_dsn.stdout and dummy not in proc_dsn.stdout)
    check("configured run reports value hidden", "value hidden" in proc_dsn.stdout)

    print("\n7. No committed credentials / .env; no AgentNet publish code")
    # .env is not tracked.
    try:
        tracked = subprocess.run(["git", "-C", REPO_ROOT, "ls-files", ".env"],
                                 capture_output=True, text=True, timeout=10).stdout.strip()
        check(".env is not tracked by git", not tracked)
        settings = subprocess.run(
            ["git", "-C", REPO_ROOT, "ls-files", ".claude/settings.local.json"],
            capture_output=True, text=True, timeout=10).stdout.strip()
        check(".claude/settings.local.json is not tracked", not settings)
    except Exception:
        check(".env tracking check (git unavailable — skipped)", True)
    # No AgentNet publish implementation was added (policy only).
    publish_impl_re = re.compile(r"def\s+\w*publish\w*|agentnet.*\.publish\(|resolver.*\.publish\(",
                                 re.IGNORECASE)
    offenders = []
    for dp, dns, files in os.walk(os.path.join(REPO_ROOT, "peak")):
        for f in files:
            if f.endswith(".py"):
                body = read(os.path.relpath(os.path.join(dp, f), REPO_ROOT))
                if publish_impl_re.search(body):
                    offenders.append(f)
    check("no AgentNet/resolver publish implementation added", not offenders)

    print("\n8. Baseline: Phase 33 commit present; single head 009; db-check expects 15 tables")
    try:
        log = subprocess.run(["git", "-C", REPO_ROOT, "log", "--oneline", "-8"],
                             capture_output=True, text=True, timeout=10).stdout
        check("Phase 33 commit 2c0ef03 present in recent history",
              "2c0ef03" in log or "Phase 33" in log)
    except Exception:
        check("Phase 33 commit present (git unavailable — skipped)", True)
    heads = [f for f in os.listdir(os.path.join(REPO_ROOT, "alembic", "versions"))
             if f.endswith(".py")]
    check("009_intake_note_records migration present",
          any(h.startswith("009_intake_note_records") for h in heads))
    if REPO_ROOT not in sys.path:
        sys.path.insert(0, REPO_ROOT)
    import importlib
    p11mod = importlib.import_module("tests.validate_phase11_db_scaffold")
    expected = list(getattr(p11mod, "EXPECTED_TABLES", []))
    check("db-check EXPECTED_TABLES includes intake_note_records",
          "intake_note_records" in expected)
    check("db-check now expects exactly 15 tables (14 prior + intake_note_records)",
          len(expected) == 15)

    print("\n" + "=" * 68)
    print("Summary")
    print(f"  failures : {len(_failures)}")
    if _failures:
        print(f"\nRESULT: {FAIL} ({len(_failures)} issue(s))")
        return 1
    print(f"\nRESULT: {PASS}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
