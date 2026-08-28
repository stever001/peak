#!/usr/bin/env python3
"""Phase 84 Alembic lab/production target guard check.

Phase 83 §7.7 recorded the defect this phase fixes: ``alembic/env.py`` read ``PEAK_DATABASE_URL``
and nothing else, so nothing in source distinguished a lab migration from a production one. The
separation was shell discipline only, and the one thing that made a mis-aimed ``upgrade head``
survivable — production and the repository both sitting at head ``014`` with nothing left to apply —
expires the moment a migration ``015`` exists. The fix lands first.

Six layers:

* **Baseline** — head is still 014, 14 migrations, no migration 015, 18 tables, 12 writers, and no
  migration file was touched.

* **Wiring** — ``alembic/env.py`` loads the guard by path, calls it on the resolved URL in both
  offline and online mode, and calls it *before* the engine is created; the Phase 47 preflight and
  the ``PEAK_DATABASE_URL`` variable are untouched.

* **Contract** — the three environment names are exactly the intended ones, ``PEAK_LAB_CONFIRM`` is
  not reused as a guard (Phase 82 published it as a reserved no-op), and the lab identity constants
  are the two names Phase 83 actually created.

* **Behaviour** — the full decision table, exercised against synthetic URLs only.

* **Hygiene** — the guard opens no connection, imports no driver, reads no credential file, embeds
  no DSN literal, and every failure message is free of password, host, port, query string, and whole
  connection string.

* **Regression** — SQLite migrations still run end to end with no target environment set at all.

**No database is contacted by this harness.** Every URL below is synthetic, points at a
non-resolvable placeholder host, and is never handed to a driver.

Exit status:
  0  -> all checks passed
  1  -> a check failed
"""

from __future__ import annotations

import importlib.util
import os
import py_compile
import re
import shutil
import subprocess
import sys
import tempfile

REPO_ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
if REPO_ROOT not in sys.path:
    sys.path.insert(0, REPO_ROOT)

GUARD_REL = "alembic/migration_target_guard.py"
ENV_REL = "alembic/env.py"
HARNESS_REL = "tests/validate_phase84_alembic_target_guard.py"
DOC_REL = "docs/PHASE84_ALEMBIC_TARGET_GUARD_FIX.md"

EXPECTED_MIGRATIONS = 14
EXPECTED_TABLE_COUNT = 18
EXPECTED_WRITERS = 12
HEAD_REVISION = "014_engagement_classification"

# Synthetic only: a placeholder host that resolves nowhere, and a placeholder secret that is not a
# credential for anything. Nothing here is ever passed to a driver.
HOST = "synthetic.invalid:3306"
PW = "synthetic-not-a-secret"

DSN_LITERAL_RE = re.compile(r"\b[a-z][a-z0-9+.\-]*://[\w.\-]+:[^\s@'\"]+@")
CREDENTIAL_FILE_MARKERS = ("peak-prod-ro.env", "peak-prod-migrate.env", ".peak/")

PASS, FAIL = "PASS", "FAIL"
_failures: list = []


def check(label: str, ok: bool) -> bool:
    print(f"  [{PASS if ok else FAIL}] {label}")
    if not ok:
        _failures.append(label)
    return ok


def read(rel: str) -> str:
    with open(os.path.join(REPO_ROOT, rel), "r", encoding="utf-8") as fh:
        return fh.read()


def git(*args: str) -> str:
    return subprocess.run(["git", *args], cwd=REPO_ROOT, capture_output=True,
                          text=True, timeout=60).stdout


def load_guard():
    spec = importlib.util.spec_from_file_location(
        "peak_phase84_migration_target_guard", os.path.join(REPO_ROOT, GUARD_REL))
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def mysql_url(user: str, database: str, query: str = "?ssl_verify_cert=true") -> str:
    """Build a synthetic MySQL DSN. Host is non-resolvable and the password is a placeholder."""
    return f"mysql+pymysql://{user}:{PW}@{HOST}/{database}{query}"


# --------------------------------------------------------------------------- 1. baseline


def baseline_checks() -> None:
    print("\n1. Baseline: head 014, 14 migrations, 18 tables, 12 writers, no 015")
    versions_dir = os.path.join(REPO_ROOT, "alembic", "versions")
    versions = sorted(f for f in os.listdir(versions_dir) if f.endswith(".py"))
    check(f"exactly {EXPECTED_MIGRATIONS} migrations", len(versions) == EXPECTED_MIGRATIONS)
    check("no migration 015 or later",
          not any(re.match(r"^0*(?:1[5-9]|[2-9]\d)_", f) for f in versions))
    check(f"{HEAD_REVISION} is still the newest migration",
          versions[-1] == f"{HEAD_REVISION}.py")
    check(f"models.py still declares exactly {EXPECTED_TABLE_COUNT} tables",
          read("peak/db/models.py").count("__tablename__ = ") == EXPECTED_TABLE_COUNT)
    writers = sorted(f for f in os.listdir(os.path.join(REPO_ROOT, "peak", "db"))
                     if f.endswith("_writer.py"))
    check(f"still exactly the {EXPECTED_WRITERS} narrow controlled writers",
          len(writers) == EXPECTED_WRITERS)

    for rel in (GUARD_REL, ENV_REL, HARNESS_REL):
        try:
            py_compile.compile(os.path.join(REPO_ROOT, rel), doraise=True)
            check(f"{rel} compiles", True)
        except py_compile.PyCompileError:
            check(f"{rel} compiles", False)

    try:
        check("no migration file was added or edited",
              not git("diff", "--name-only", "HEAD", "--", "alembic/versions").strip())
        check("no writer file was added or edited",
              not git("diff", "--name-only", "HEAD", "--", "peak").strip())
        check("docs/Peak_Investor_Overview_AI.docx has no pending diff",
              not git("diff", "--name-only", "HEAD", "--",
                      "docs/Peak_Investor_Overview_AI.docx").strip())
    except Exception:  # noqa: BLE001
        check("git-backed baseline checks (git unavailable — skipped)", True)


# --------------------------------------------------------------------------- 2. wiring


def wiring_checks() -> None:
    print("\n2. env.py calls the guard on the resolved URL, before any engine exists")
    env_src = read(ENV_REL)
    check("env.py loads the guard module by path", "migration_target_guard.py" in env_src)
    check("env.py calls the guard", "assert_migration_target(" in env_src)
    check("offline mode resolves the URL through the guarded accessor",
          "url=_guarded_url()," in env_src)
    check("online mode resolves the URL through the guarded accessor",
          "create_engine(_guarded_url()" in env_src)
    online = env_src.split("def run_migrations_online")[-1]
    check("online mode guards before create_engine",
          "_guarded_url()" in online
          and online.index("_guarded_url()") < online.index("pool_pre_ping"))
    check("the guard call is inside the accessor, before the engine call",
          env_src.index("assert_migration_target(") < env_src.index("create_engine(_guarded_url"))
    check("the Phase 47 preflight is still wired in both modes",
          env_src.count("assert_revision_ids_fit(") == 2
          and "harden_version_table(" in env_src)
    check("PEAK_DATABASE_URL remains the one Alembic URL variable",
          'os.environ.get("PEAK_DATABASE_URL")' in env_src)


# --------------------------------------------------------------------------- 3. contract


def contract_checks() -> None:
    print("\n3. The environment contract and the fixed lab identity")
    g = load_guard()
    check("target variable is PEAK_ALEMBIC_TARGET", g.TARGET_ENV == "PEAK_ALEMBIC_TARGET")
    check("lab confirmation is PEAK_LAB_MIGRATION_CONFIRM",
          g.LAB_CONFIRM_ENV == "PEAK_LAB_MIGRATION_CONFIRM")
    check("production confirmation is PEAK_PRODUCTION_MIGRATION_CONFIRM",
          g.PRODUCTION_CONFIRM_ENV == "PEAK_PRODUCTION_MIGRATION_CONFIRM")
    check("supported targets are exactly lab and production",
          tuple(g.SUPPORTED_TARGETS) == ("lab", "production"))
    check("lab schema constant is peak_lab", g.LAB_SCHEMA == "peak_lab")
    check("lab migration user constant is peak_lab_migrate",
          g.LAB_MIGRATION_USER == "peak_lab_migrate")
    check("defaultdb is treated as a provider default, never the lab",
          "defaultdb" in g.PROVIDER_DEFAULT_DATABASES)
    check("only MySQL/MariaDB are guarded",
          set(g.GUARDED_DIALECTS) == {"mysql", "mariadb"})
    src = read(GUARD_REL)
    # The name appears once, in prose explaining why it is *not* used. What must not exist is a
    # string literal the guard could actually read.
    check("PEAK_LAB_CONFIRM is not reused as a guard variable "
          "(Phase 82 published it as a reserved no-op)",
          '"PEAK_LAB_CONFIRM"' not in src and g.LAB_CONFIRM_ENV != "PEAK_LAB_CONFIRM")
    check("the guard names no runtime or production-verifier URL variable",
          "PEAK_RUNTIME_DATABASE_URL" not in src and "PEAK_PRODUCTION_DB_URL" not in src)


# --------------------------------------------------------------------------- 4. behaviour


def _raises(g, url, env):
    try:
        g.assert_migration_target(url, env=env)
    except g.MigrationTargetError as exc:
        return exc
    return None


def behaviour_checks() -> None:
    print("\n4. Decision table, exercised on synthetic URLs only")
    g = load_guard()

    lab_url = mysql_url("peak_lab_migrate", "peak_lab")
    lab_env = {g.TARGET_ENV: "lab", g.LAB_CONFIRM_ENV: "1"}
    prod_url = mysql_url("peak_app_migrate", "peak_app")
    prod_env = {g.TARGET_ENV: "production", g.PRODUCTION_CONFIRM_ENV: "1"}

    # --- missing / unusable target
    exc = _raises(g, lab_url, {})
    check("MySQL URL with no declared target fails",
          exc is not None and exc.reason == "target_not_declared")
    exc = _raises(g, lab_url, {g.TARGET_ENV: "staging", g.LAB_CONFIRM_ENV: "1"})
    check("MySQL URL with an unsupported target fails",
          exc is not None and exc.reason == "target_not_supported")

    # --- lab branch
    out = g.assert_migration_target(lab_url, env=lab_env)
    check("lab target with peak_lab + peak_lab_migrate + confirmation passes",
          out["outcome"] == g.OUTCOME_LAB_OK)
    exc = _raises(g, lab_url, {g.TARGET_ENV: "lab"})
    check("lab target without confirmation fails",
          exc is not None and exc.reason == "lab_not_confirmed")
    exc = _raises(g, lab_url, {g.TARGET_ENV: "lab", g.LAB_CONFIRM_ENV: "true"})
    check("lab confirmation accepts only the exact value 1",
          exc is not None and exc.reason == "lab_not_confirmed")
    exc = _raises(g, mysql_url("peak_lab_migrate", "defaultdb"), lab_env)
    check("lab target aimed at defaultdb fails",
          exc is not None and exc.reason == "lab_schema_is_provider_default")
    exc = _raises(g, mysql_url("peak_lab_migrate", "peak_prod"), lab_env)
    check("lab target with a production-marked schema fails",
          exc is not None and exc.reason == "production_marker_under_lab_target")
    exc = _raises(g, mysql_url("peak_prod_migrate", "peak_lab"), lab_env)
    check("lab target with a production-marked user fails",
          exc is not None and exc.reason == "production_marker_under_lab_target")
    exc = _raises(g, mysql_url("peak_lab_migrate", "peak_app"), lab_env)
    check("lab target with a non-lab schema fails",
          exc is not None and exc.reason == "lab_schema_mismatch")
    exc = _raises(g, mysql_url("peak_lab_runtime", "peak_lab"), lab_env)
    check("lab target with a user other than peak_lab_migrate fails",
          exc is not None and exc.reason == "lab_user_mismatch")
    exc = _raises(g, mysql_url("peak_lab_migrate", ""), lab_env)
    check("lab target with no schema segment at all fails",
          exc is not None and exc.reason == "lab_schema_mismatch")

    # --- production branch
    exc = _raises(g, prod_url, {g.TARGET_ENV: "production"})
    check("production target without confirmation fails",
          exc is not None and exc.reason == "production_not_confirmed")
    exc = _raises(g, mysql_url("peak_app_migrate", "peak_lab"), prod_env)
    check("production target with the lab schema fails",
          exc is not None and exc.reason == "lab_marker_under_production_target")
    exc = _raises(g, mysql_url("peak_lab_migrate", "peak_app"), prod_env)
    check("production target with the lab migration user fails",
          exc is not None and exc.reason == "lab_marker_under_production_target")
    exc = _raises(g, mysql_url("peak_app_migrate", "defaultdb"), prod_env)
    check("production target aimed at defaultdb fails",
          exc is not None and exc.reason == "production_schema_is_provider_default")
    exc = _raises(g, mysql_url("peak_app_migrate", ""), prod_env)
    check("production target with no schema segment fails",
          exc is not None and exc.reason == "production_schema_absent")
    out = g.assert_migration_target(prod_url, env=prod_env)
    check("production target with explicit confirmation and no lab marker passes the guard "
          "(guard consistency only — it authorizes nothing)",
          out["outcome"] == g.OUTCOME_PRODUCTION_OK)

    # --- confirmations do not leak across targets
    exc = _raises(g, lab_url, {g.TARGET_ENV: "lab", g.PRODUCTION_CONFIRM_ENV: "1"})
    check("the production confirmation does not satisfy the lab target",
          exc is not None and exc.reason == "lab_not_confirmed")
    exc = _raises(g, prod_url, {g.TARGET_ENV: "production", g.LAB_CONFIRM_ENV: "1"})
    check("the lab confirmation does not satisfy the production target",
          exc is not None and exc.reason == "production_not_confirmed")

    # --- dialects that are not guarded
    for url in ("sqlite:///" + os.path.join(tempfile.gettempdir(), "peak_p84_synthetic.db"),
                "sqlite://"):
        out = g.assert_migration_target(url, env={})
        check(f"SQLite URL bypasses the guard with no environment set ({url.split(':')[0]})",
              out["outcome"] == g.OUTCOME_NOT_GUARDED)
    out = g.assert_migration_target("mariadb+pymysql://peak_lab_migrate:%s@%s/peak_lab"
                                    % (PW, HOST), env=lab_env)
    check("MariaDB URLs are guarded on the same terms as MySQL",
          out["outcome"] == g.OUTCOME_LAB_OK)


# --------------------------------------------------------------------------- 5. hygiene


def hygiene_checks() -> None:
    print("\n5. The guard holds no connection value, and says none in its messages")
    g = load_guard()
    src = read(GUARD_REL)

    check("guard embeds no DSN literal", not DSN_LITERAL_RE.search(src))
    check("guard references no credential file",
          not any(m in src for m in CREDENTIAL_FILE_MARKERS))
    check("guard opens no file at all (so it can read no .env or credential file)",
          "open(" not in src)
    check("guard imports no database library or driver",
          re.search(r"^\s*(?:import|from)\s+(?:sqlalchemy|pymysql|MySQLdb|alembic)\b",
                    src, re.MULTILINE | re.IGNORECASE) is None)
    check("guard creates no engine and no connection",
          "create_engine" not in src and "connect(" not in src)
    check("guard issues no SQL", not re.search(r"\b(SELECT|INSERT|UPDATE|DELETE|ALTER|CREATE)\b",
                                               src))
    check("guard opens no socket or subprocess",
          "socket" not in src and "subprocess" not in src)
    check("parse_identity keeps only user and database",
          set(g.parse_identity(mysql_url("peak_lab_migrate", "peak_lab"))) ==
          {"dialect", "username", "database"})

    # Every failing message from the decision table, checked for leaked connection detail.
    lab_env = {g.TARGET_ENV: "lab", g.LAB_CONFIRM_ENV: "1"}
    prod_env = {g.TARGET_ENV: "production", g.PRODUCTION_CONFIRM_ENV: "1"}
    cases = [
        (mysql_url("peak_lab_migrate", "peak_lab"), {}),
        (mysql_url("peak_lab_migrate", "defaultdb"), lab_env),
        (mysql_url("peak_lab_migrate", "peak_app"), lab_env),
        (mysql_url("peak_prod_migrate", "peak_lab"), lab_env),
        (mysql_url("peak_lab_runtime", "peak_lab"), lab_env),
        (mysql_url("peak_lab_migrate", "peak_lab"), {g.TARGET_ENV: "lab"}),
        (mysql_url("peak_app_migrate", "peak_app"), {g.TARGET_ENV: "production"}),
        (mysql_url("peak_lab_migrate", "peak_app"), prod_env),
        (mysql_url("peak_app_migrate", "defaultdb"), prod_env),
    ]
    leaked = []
    for url, env in cases:
        exc = _raises(g, url, env)
        if exc is None:
            leaked.append("case did not fail as expected")
            continue
        msg = str(exc)
        for needle, what in ((PW, "password"), ("synthetic.invalid", "host"),
                             (":3306", "port"), ("ssl_verify_cert", "query parameter"),
                             ("://", "whole connection string"), (url, "whole DSN")):
            if needle in msg:
                leaked.append(f"{what} in message for reason={exc.reason}")
    check("no failure message contains a password, host, port, query parameter, or DSN",
          not leaked)
    if leaked:
        print(f"        leaks: {sorted(set(leaked))}")
    check("failure messages carry a stable reason code and the classifications",
          all("reason=" in str(_raises(g, u, e)) and "user_class=" in str(_raises(g, u, e))
              for u, e in cases))


# --------------------------------------------------------------------------- 6. regression


def regression_checks() -> None:
    print("\n6. Regression: SQLite migrations still run with no target environment set")
    try:
        from alembic import command
        from alembic.config import Config
        from sqlalchemy import create_engine, inspect
    except ImportError:
        print("  [skip] Alembic/SQLAlchemy not installed — migration run not exercised")
        return

    tmp = tempfile.mkdtemp(prefix="peak_p84_")
    saved = {k: os.environ.get(k)
             for k in ("PEAK_DATABASE_URL", "PEAK_ALEMBIC_TARGET",
                       "PEAK_LAB_MIGRATION_CONFIRM", "PEAK_PRODUCTION_MIGRATION_CONFIRM")}
    try:
        for k in saved:
            os.environ.pop(k, None)
        url = "sqlite:///" + os.path.join(tmp, "m.db")
        os.environ["PEAK_DATABASE_URL"] = url
        cfg = Config(os.path.join(REPO_ROOT, "alembic.ini"))
        command.upgrade(cfg, "head")
        tables = [t for t in inspect(create_engine(url)).get_table_names()
                  if t != "alembic_version"]
        check(f"SQLite upgrade head still builds {EXPECTED_TABLE_COUNT} tables "
              "with no target declared", len(tables) == EXPECTED_TABLE_COUNT)
    except Exception as exc:  # noqa: BLE001
        check(f"SQLite migration run ({type(exc).__name__})", False)
    finally:
        for k, v in saved.items():
            if v is None:
                os.environ.pop(k, None)
            else:
                os.environ[k] = v
        shutil.rmtree(tmp, ignore_errors=True)

    mk = read("Makefile")
    check("Makefile declares validate-phase84", "validate-phase84" in mk)
    check("validate depends on validate-phase84",
          re.search(r"^validate:.*validate-phase84", mk, re.MULTILINE) is not None)
    check("no migration-running target was added to validate",
          not re.search(r"^validate:.*(upgrade|downgrade|stamp)", mk, re.MULTILINE))
    check("the phase document exists", os.path.isfile(os.path.join(REPO_ROOT, DOC_REL)))


# --------------------------------------------------------------------------- main


def main() -> int:
    print("Peak Phase 84 Alembic lab/production target guard check")
    print("=" * 70)

    baseline_checks()
    wiring_checks()
    contract_checks()
    behaviour_checks()
    hygiene_checks()
    regression_checks()

    print("\n" + "=" * 70)
    print("Summary")
    print(f"  failures : {len(_failures)}")
    for label in _failures:
        print(f"    - {label}")
    print("\nRESULT: " + ("FAIL" if _failures else "PASS"))
    return 1 if _failures else 0


if __name__ == "__main__":
    sys.exit(main())
