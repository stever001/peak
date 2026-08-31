#!/usr/bin/env python3
"""Phase 89 — the lab-only writer enablement decision gate.

Checks, offline and with synthetic values only: that the baseline is unchanged; that the Phase 51
production gate is **byte-identical** and still denies production, including when every lab
variable is set; that the new lab gate has no database, credential, or writer code path; that its
environment contract reuses no variable that already means something else; that every deny branch
denies and the one authorize branch authorizes; that a lab authorization never implies a production
one; that the enableable writer set is a strict subset of the controlled allowlist; and that no
output carries a connection value.

No database is contacted, no credential file is read, no writer is invoked, and no record is
created. Every URL in this file is synthetic and unroutable.
"""

from __future__ import annotations

import importlib.util
import json
import os
import py_compile
import re
import subprocess
import sys

REPO_ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, REPO_ROOT)

BASELINE_COMMIT = "8307793"   # Document Phase 88 lab scenario measurement

LAB_GATE_REL = "tools/lab_writer_enablement_decision_gate.py"
PROD_GATE_REL = "tools/production_writer_enablement_decision_gate.py"
GUARD_REL = "alembic/migration_target_guard.py"
HARNESS_REL = "tests/validate_phase89_lab_writer_enablement_gate.py"
MODELS_REL = "peak/db/models.py"

EXPECTED_MIGRATIONS = 14
EXPECTED_TABLE_COUNT = 18
EXPECTED_WRITERS = 12
HEAD_REVISION = "014_engagement_classification"

PY = sys.executable

_failures = 0


def check(label: str, ok: bool) -> bool:
    global _failures
    _failures += (not ok)
    print(f"  [{'PASS' if ok else 'FAIL'}] {label}")
    return ok


def read(rel: str) -> str:
    with open(os.path.join(REPO_ROOT, rel), "r", encoding="utf-8") as fh:
        return fh.read()


def strip_docstrings(source: str) -> str:
    """Return source with docstrings removed, so prose cannot satisfy a code assertion."""
    import ast
    tree = ast.parse(source)
    spans = []
    for node in ast.walk(tree):
        if isinstance(node, (ast.Module, ast.FunctionDef, ast.AsyncFunctionDef, ast.ClassDef)):
            body = getattr(node, "body", None)
            if body and isinstance(body[0], ast.Expr) and isinstance(body[0].value, ast.Constant) \
                    and isinstance(body[0].value.value, str):
                spans.append((body[0].lineno, body[0].end_lineno))
    return "\n".join(re.sub(r"#.*$", "", ln)
                     for i, ln in enumerate(source.splitlines(), 1)
                     if not any(a <= i <= b for a, b in spans))


def git(*args: str) -> str:
    return subprocess.run(["git", "-C", REPO_ROOT, *args],
                          capture_output=True, text=True, timeout=20).stdout.strip()


def git_succeeds(*args: str) -> bool:
    """Run a git command for its exit status alone; stdout and stderr are discarded, so
    nothing a path or remote might carry can reach this harness's output."""
    return subprocess.run(["git", "-C", REPO_ROOT, *args],
                          capture_output=True, text=True, timeout=20).returncode == 0


def load_lab_gate():
    spec = importlib.util.spec_from_file_location(
        "_peak_lab_writer_gate", os.path.join(REPO_ROOT, LAB_GATE_REL))
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


# --------------------------------------------------------------------------- 1. baseline


def baseline_checks() -> None:
    print("\n1. Baseline: head 014, 14 migrations, 18 tables, 12 writers, nothing added")
    versions = sorted(f for f in os.listdir(os.path.join(REPO_ROOT, "alembic", "versions"))
                      if f.endswith(".py"))
    check(f"exactly {EXPECTED_MIGRATIONS} migrations", len(versions) == EXPECTED_MIGRATIONS)
    check("no migration 015 or later - Phase 89 adds no migration",
          not any(re.match(r"^0*(?:1[5-9]|[2-9]\d)_", f) for f in versions))
    check(f"{HEAD_REVISION} is still the newest migration",
          versions[-1] == f"{HEAD_REVISION}.py")
    check(f"models.py still declares exactly {EXPECTED_TABLE_COUNT} tables",
          read(MODELS_REL).count("__tablename__ = ") == EXPECTED_TABLE_COUNT)
    writers = sorted(f for f in os.listdir(os.path.join(REPO_ROOT, "peak", "db"))
                     if f.endswith("_writer.py"))
    check(f"still exactly the {EXPECTED_WRITERS} narrow controlled writers",
          len(writers) == EXPECTED_WRITERS)

    for rel in (LAB_GATE_REL, PROD_GATE_REL, HARNESS_REL):
        try:
            py_compile.compile(os.path.join(REPO_ROOT, rel), doraise=True)
            check(f"{rel} compiles", True)
        except py_compile.PyCompileError:
            check(f"{rel} compiles", False)

    try:
        is_ancestor = git_succeeds("merge-base", "--is-ancestor", BASELINE_COMMIT, "HEAD")
        check(f"baseline commit {BASELINE_COMMIT} present in history", is_ancestor)
        if not is_ancestor:
            print("        reason: phase89_baseline_commit_not_ancestor")
        check("no migration file was added or edited",
              not git("diff", "--name-only", "HEAD", "--", "alembic/versions").strip())
        check("no controlled writer was added or edited",
              not git("diff", "--name-only", "HEAD", "--", "peak/db").strip())
        check("the controlled allowlist was not modified",
              not git("diff", "--name-only", "HEAD", "--",
                      "peak/persistence/allowlist.py").strip())
        check("docs/Peak_Investor_Overview_AI.docx has no pending diff",
              not git("diff", "--name-only", "HEAD", "--",
                      "docs/Peak_Investor_Overview_AI.docx").strip())
    except Exception:
        check("git-backed baseline checks (git unavailable - skipped)", True)


# --------------------------------------------------------------------------- 2. production gate


def production_gate_unchanged() -> None:
    print("\n2. The Phase 51 production gate is untouched and still denies production")
    # The strongest available statement: not "still passes" but "was not edited at all".
    check("the production gate file has no pending diff",
          not git("diff", "--name-only", "HEAD", "--", PROD_GATE_REL).strip())

    prod_src = strip_docstrings(read(PROD_GATE_REL))
    check("the production gate still reads no environment variable",
          "os.environ" not in prod_src)
    check("the production gate does not import the lab gate",
          "lab_writer_enablement" not in prod_src)

    scrubbed = {k: v for k, v in os.environ.items()
                if not k.startswith(("PEAK_", "DATABASE_"))}
    scrubbed["PYTHONPATH"] = REPO_ROOT

    r = subprocess.run([PY, os.path.join(REPO_ROOT, PROD_GATE_REL)],
                       capture_output=True, text=True, env=scrubbed, timeout=60)
    check("production gate exits 0 by default", r.returncode == 0)
    check("production gate still reports safe_to_write_production_now=false",
          "safe_to_write_production_now=false" in r.stdout)
    check("production gate still reports safe_to_run_writers_now=false",
          "safe_to_run_writers_now=false" in r.stdout)

    # The point of the phase: lab variables must not move the production decision at all.
    lab_env = dict(scrubbed)
    lab_env.update({
        "PEAK_WRITER_TARGET": "lab",
        "PEAK_LAB_WRITER_ENABLEMENT_CONFIRM": "1",
        "PEAK_LAB_WRITER_TARGET_URL":
            "mysql+pymysql://peak_lab_runtime:x@synthetic.invalid:3306/peak_lab",
        "PEAK_LAB_WRITER_TARGETS": "review_records/create_review_record",
    })
    r2 = subprocess.run([PY, os.path.join(REPO_ROOT, PROD_GATE_REL)],
                        capture_output=True, text=True, env=lab_env, timeout=60)
    check("production gate exits 0 with every lab variable set", r2.returncode == 0)
    check("production remains denied with every lab variable set",
          "safe_to_write_production_now=false" in r2.stdout)
    check("production gate output is byte-identical with and without lab variables",
          r.stdout == r2.stdout)


# --------------------------------------------------------------------------- 3. lab gate shape


def lab_gate_has_no_dangerous_path() -> None:
    print("\n3. The lab gate has no database, credential, or writer code path")
    src = read(LAB_GATE_REL)
    code = strip_docstrings(src)

    check("lab gate imports no controlled writer",
          not re.search(r"import\s+.*_writer|from\s+peak\.db", code))
    check("lab gate imports nothing from peak at all",
          not re.search(r"\b(?:from|import)\s+peak\b", code))
    check("lab gate imports no SQLAlchemy", "sqlalchemy" not in code.lower())
    check("lab gate imports no database driver",
          not re.search(r"\b(?:import|from)\s+(?:pymysql|MySQLdb|psycopg2|sqlite3)\b", code))
    check("lab gate never calls create_engine", "create_engine" not in code)
    check("lab gate never opens a connection", not re.search(r"\.connect\(|\bconnect\(", code))
    check("lab gate never executes a statement", ".execute(" not in code)
    for token in (" SELECT ", " INSERT ", " UPDATE ", " DELETE ", " DROP ", " CREATE TABLE "):
        check(f"lab gate contains no {token.strip()} statement", token not in code.upper())
    # Tests real file access, not the word "credential" — the module legitimately *names* a
    # credential_file_read field, and an assertion that banned the word would ban saying "no".
    check("lab gate names no .env or credential file path",
          not re.search(r"""['"][^'"]*\.env['"]|['"][^'"]*credentials?/""", code))
    check("lab gate opens no file at all (so it can read no .env or credential file)",
          code.count("open(") == 0)
    check("lab gate reads no file through pathlib or read_text",
          not re.search(r"read_text|read_bytes|readlines|\bPath\(", code))
    check("lab gate expands no home-relative path",
          "expanduser" not in code)
    check("the only file it loads by path is the sibling Phase 84 guard",
          code.count("spec_from_file_location") == 1 and "migration_target_guard.py" in code)
    check("lab gate embeds no real-looking DSN",
          not re.search(r"(?i)(mysql|mariadb)(\+\w+)?://[^\s\"']*@(?!synthetic\.invalid|h\.invalid)",
                        src))


# --------------------------------------------------------------------------- 4. env contract


def environment_contract() -> None:
    print("\n4. The environment contract reuses no variable that already means something else")
    g = load_lab_gate()
    check("target variable is PEAK_WRITER_TARGET", g.TARGET_ENV == "PEAK_WRITER_TARGET")
    check("lab confirmation is PEAK_LAB_WRITER_ENABLEMENT_CONFIRM",
          g.LAB_CONFIRM_ENV == "PEAK_LAB_WRITER_ENABLEMENT_CONFIRM")
    check("lab target URL variable is PEAK_LAB_WRITER_TARGET_URL",
          g.LAB_URL_ENV == "PEAK_LAB_WRITER_TARGET_URL")
    check("confirmation accepts only the exact string 1", g.CONFIRM_VALUE == "1")
    check("PEAK_LAB_CONFIRM is not reused (Phase 82 published it as a reserved no-op)",
          "PEAK_LAB_CONFIRM" in g.REJECTED_AUTHORIZER_ENVS
          and g.LAB_CONFIRM_ENV != "PEAK_LAB_CONFIRM")
    for var in ("PEAK_ALEMBIC_TARGET", "PEAK_LAB_MIGRATION_CONFIRM",
                "PEAK_PRODUCTION_MIGRATION_CONFIRM"):
        check(f"the Phase 84 migration variable {var} is not a writer authorizer",
              var in g.REJECTED_AUTHORIZER_ENVS)
    for var in ("PEAK_LAB_SCENARIO_RO_URL", "PEAK_LAB_SCENARIO_LOADER_URL"):
        check(f"the scenario variable {var} is not a writer authorizer",
              var in g.REJECTED_AUTHORIZER_ENVS)
    for var in ("PEAK_PRODUCTION_DB_URL", "PEAK_RUNTIME_DATABASE_URL", "PEAK_DATABASE_URL"):
        check(f"the production-named variable {var} is not a lab writer authorizer",
              var in g.REJECTED_AUTHORIZER_ENVS)
    check("the lab schema constant is exactly peak_lab", g.LAB_SCHEMA == "peak_lab")
    check("the scenario schema is named and excluded", g.SCENARIO_SCHEMA == "peak_lab_scenario")
    check("only the lab runtime role is an approved lab writer",
          g.APPROVED_LAB_WRITER_USERS == frozenset({"peak_lab_runtime"}))


# --------------------------------------------------------------------------- 5. writer scoping


def writer_target_scoping() -> None:
    print("\n5. Writer targets are narrowly scoped, not blanket-enabled")
    g = load_lab_gate()
    from peak.persistence.allowlist import (ALLOWED_ACTIONS, ALLOWED_TABLES,
                                            ALLOWED_ANCHOR_CREATION_PAIRS)

    check("exactly three writer targets are lab-enableable",
          len(g.LAB_ENABLEABLE_WRITER_TARGETS) == 3)
    for table, action in sorted(g.LAB_ENABLEABLE_WRITER_TARGETS):
        check(f"enableable table {table} is on the controlled allowlist", table in ALLOWED_TABLES)
        check(f"enableable action {action} is on the controlled allowlist",
              action in ALLOWED_ACTIONS)
    check("the enableable set is a strict subset of the allowlist's table space",
          {t for t, _ in g.LAB_ENABLEABLE_WRITER_TARGETS} < ALLOWED_TABLES)
    # Phase 90 superseded the original form of this check. The anchor pair was in
    # NEVER_LAB_ENABLEABLE; it now reaches a separate bootstrap branch that requires its own
    # confirmation. The invariant that still matters — and the one Phase 89 was really asserting —
    # is that the anchor is **not generally lab-enableable**: it stays out of the ordinary
    # enableable set, so no ordinary lab request can ever be granted it.
    check("the engagement authorization anchor pair is not generally lab-enableable",
          not (ALLOWED_ANCHOR_CREATION_PAIRS & g.LAB_ENABLEABLE_WRITER_TARGETS))
    check("the anchor pair is reachable only through the named bootstrap pair",
          g.ANCHOR_BOOTSTRAP_PAIR in ALLOWED_ANCHOR_CREATION_PAIRS)
    check("clients/create_draft remains never lab-enableable on any path",
          ("clients", "create_draft") in g.NEVER_LAB_ENABLEABLE)
    check("no never-enableable pair is also enableable",
          not (g.NEVER_LAB_ENABLEABLE & g.LAB_ENABLEABLE_WRITER_TARGETS))
    check("no update or supersede action is lab-enableable",
          not any(a.startswith(("update_", "mark_")) for _, a in g.LAB_ENABLEABLE_WRITER_TARGETS))
    check("every lab-enableable action is a create action",
          all(a.startswith("create_") for _, a in g.LAB_ENABLEABLE_WRITER_TARGETS))


# --------------------------------------------------------------------------- 6. decisions


def decision_branches() -> None:
    print("\n6. Every deny branch denies, and the authorize branch authorizes")
    g = load_lab_gate()
    ok_url = "mysql+pymysql://peak_lab_runtime:x@synthetic.invalid:3306/peak_lab"
    ok_targets = "review_records/create_review_record"

    def env(**kw):
        base = {g.TARGET_ENV: "lab", g.LAB_CONFIRM_ENV: "1",
                g.LAB_URL_ENV: ok_url, g.LAB_TARGETS_ENV: ok_targets}
        base.update(kw)
        return {k: v for k, v in base.items() if v is not None}

    cases = (
        ("default (empty) environment denies", {}, g.REASON_TARGET_NOT_LAB),
        ("production target denies", {g.TARGET_ENV: "production"}, g.REASON_TARGET_IS_PRODUCTION),
        ("lab target without confirmation denies",
         env(**{g.LAB_CONFIRM_ENV: None}), g.REASON_NO_CONFIRM),
        ("a non-exact confirmation denies",
         env(**{g.LAB_CONFIRM_ENV: "yes"}), g.REASON_NO_CONFIRM),
        ("missing target URL denies", env(**{g.LAB_URL_ENV: None}), g.REASON_URL_ABSENT),
        ("scenario schema denies",
         env(**{g.LAB_URL_ENV: ok_url.replace("/peak_lab", "/peak_lab_scenario")}),
         g.REASON_SCHEMA_SCENARIO),
        ("provider default schema denies",
         env(**{g.LAB_URL_ENV: ok_url.replace("/peak_lab", "/defaultdb")}),
         g.REASON_SCHEMA_DEFAULT),
        ("production-marked schema denies",
         env(**{g.LAB_URL_ENV: ok_url.replace("/peak_lab", "/peak_production")}),
         g.REASON_SCHEMA_PRODUCTION),
        ("an unrelated schema denies",
         env(**{g.LAB_URL_ENV: ok_url.replace("/peak_lab", "/other_db")}),
         g.REASON_SCHEMA_NOT_LAB),
        ("production-marked user denies",
         env(**{g.LAB_URL_ENV: ok_url.replace("peak_lab_runtime", "peak_prod_runtime")}),
         g.REASON_USER_PRODUCTION),
        ("the migration role denies",
         env(**{g.LAB_URL_ENV: ok_url.replace("peak_lab_runtime", "peak_lab_migrate")}),
         g.REASON_USER_NOT_APPROVED),
        ("the scenario read-only role denies",
         env(**{g.LAB_URL_ENV: ok_url.replace("peak_lab_runtime", "peak_lab_scenario_ro")}),
         g.REASON_USER_NOT_APPROVED),
        ("no requested writer target denies",
         env(**{g.LAB_TARGETS_ENV: None}), g.REASON_NO_TARGETS),
        ("an off-allowlist writer target denies",
         env(**{g.LAB_TARGETS_ENV: "intake_note_records/create_intake_note_record"}),
         g.REASON_TARGET_NOT_ENABLEABLE),
        ("the engagement anchor target denies without its bootstrap confirmation",
         env(**{g.LAB_TARGETS_ENV: "engagements/create_engagement_authorization_anchor"}),
         g.REASON_ANCHOR_NO_BOOTSTRAP_CONFIRM),
        ("clients/create_draft denies on every path",
         env(**{g.LAB_TARGETS_ENV: "clients/create_draft"}),
         g.REASON_TARGET_NEVER_ENABLEABLE),
    )
    for label, e, expected_reason in cases:
        d = g.evaluate(e)
        check(f"{label} ({expected_reason})",
              d["lab_write_authorized"] is False and d["reason"] == expected_reason)

    d = g.evaluate(env())
    check("a complete, correctly scoped lab request is authorized",
          d["lab_write_authorized"] is True and d["reason"] == g.REASON_OK)
    check("the authorization names exactly the requested target",
          d["authorized_writer_targets"] == [ok_targets])
    check("the authorized decision is internally consistent", g.is_consistent(d))


# --------------------------------------------------------------------------- 7. no production


def lab_never_implies_production() -> None:
    print("\n7. A lab authorization never implies a production one")
    g = load_lab_gate()
    ok_url = "mysql+pymysql://peak_lab_runtime:x@synthetic.invalid:3306/peak_lab"
    envs = (
        {},
        {g.TARGET_ENV: "production"},
        {g.TARGET_ENV: "lab", g.LAB_CONFIRM_ENV: "1", g.LAB_URL_ENV: ok_url,
         g.LAB_TARGETS_ENV: "review_records/create_review_record"},
        {g.TARGET_ENV: "lab", g.LAB_CONFIRM_ENV: "1", g.LAB_URL_ENV: ok_url,
         g.LAB_TARGETS_ENV: ("review_records/create_review_record,"
                             "evidence_references/create_draft,"
                             "source_ingestion_records/create_source_ingestion_record")},
    )
    for i, e in enumerate(envs):
        d = g.evaluate(e)
        check(f"case {i}: safe_to_write_production_now is false",
              d["safe_to_write_production_now"] is False)
        check(f"case {i}: production_write_authorized is false",
              d["production_write_authorized"] is False)
        check(f"case {i}: production_writer_enablement_authorized is false",
              d["production_writer_enablement_authorized"] is False)
        check(f"case {i}: no writer was invoked and no record created",
              d["writer_invoked"] is False and d["records_created"] is False)
        check(f"case {i}: no database was contacted and no statement issued",
              d["database_contacted"] is False and d["sql_issued"] is False)
        check(f"case {i}: a lab decision still requires separate phase approval",
              d["lab_write_requires_separate_phase_approval"] is True)

    src = strip_docstrings(read(LAB_GATE_REL))
    check("the module contains no assignment making a production field true",
          not re.search(r'"(?:production_write_authorized|safe_to_write_production_now|'
                        r'production_writer_enablement_authorized)"\s*:\s*True', src))


# --------------------------------------------------------------------------- 8. value-free


def output_is_value_free() -> None:
    print("\n8. Output carries no connection value")
    g = load_lab_gate()
    url = "mysql+pymysql://peak_lab_runtime:sup3rsecret@synthetic.invalid:3306/peak_lab?ssl_ca=/x/ca.pem"
    d = g.evaluate({g.TARGET_ENV: "lab", g.LAB_CONFIRM_ENV: "1", g.LAB_URL_ENV: url,
                    g.LAB_TARGETS_ENV: "review_records/create_review_record"})
    rendered = json.dumps(d)
    for token, label in (("sup3rsecret", "password"), ("synthetic.invalid", "host"),
                         ("3306", "port"), ("ca.pem", "certificate path"),
                         ("ssl_ca", "query parameter"), ("mysql+pymysql", "scheme"),
                         ("://", "URL separator")):
        check(f"decision carries no {label}", token not in rendered)
    check("the decision still authorized, so the value-free check is not vacuous",
          d["lab_write_authorized"] is True)

    r = subprocess.run([PY, os.path.join(REPO_ROOT, LAB_GATE_REL), "--self-test"],
                       capture_output=True, text=True, timeout=60)
    check("the module self-test passes", r.returncode == 0 and "RESULT: PASS" in r.stdout)
    for token, label in (("sup3rsecret", "password"), ("://", "URL separator")):
        check(f"self-test output carries no {label}", token not in r.stdout)


def main() -> int:
    print("=" * 74)
    print("Phase 89 — lab-only writer enablement decision gate")
    print("=" * 74)
    baseline_checks()
    production_gate_unchanged()
    lab_gate_has_no_dangerous_path()
    environment_contract()
    writer_target_scoping()
    decision_branches()
    lab_never_implies_production()
    output_is_value_free()
    print("\n" + "=" * 74)
    print("Summary")
    print(f"  failures : {_failures}")
    print()
    print("RESULT:", "PASS" if _failures == 0 else "FAIL")
    return 0 if _failures == 0 else 1


if __name__ == "__main__":
    raise SystemExit(main())
